"""The contract, shared by every destination.

`Core` checks names and limits, builds the CSV for load, makes the AI pick one
of the choices, and turns failures into the error codes of §7. A destination
(AWS, local PC, ...) only implements `Adapter`: where records are kept, how a
function runs, and which AI answers. So the meaning of each call stays the same
when the destination changes.
"""

import base64
import binascii
import csv
import io
import re
import time
from collections import deque
from datetime import datetime, timezone

# Error codes of the contract
OK = 0
ERR_AUTH = 4
ERR_NOT_FOUND = 5
ERR_TOO_LARGE = 6
ERR_TYPE_MISMATCH = 7
ERR_TIMEOUT = 8
ERR_RUN_FAILED = 9
ERR_AI_FORMAT = 10
ERR_LIMIT = 11
ERR_INVALID_NAME = 12
ERR_SERVER = 13

RECORD_MAX = 1024
LOAD_MAX = 16 * 1024
RUN_INPUT_MAX = 64 * 1024
RUN_OUTPUT_MAX = 16 * 1024
ASK_INPUT_MAX = 16 * 1024
BINARY_MAX = 1024 * 1024  # images and other binary data (MVP+)
IMAGE_MAX = 3 * 1024 * 1024
RUN_TIMEOUT_DEFAULT_MS = 10_000
RUN_TIMEOUT_MAX_MS = 60_000

NAME = re.compile(r"^[A-Za-z0-9._/-]{1,128}$")

SYSTEM_TEXT = (
    "You answer questions sent from a small device such as an Arduino. "
    "Answer briefly and plainly, in the language of the question."
)


class CloudError(Exception):
    def __init__(self, code, message):
        super().__init__(message)
        self.code = code
        self.message = message


class Adapter:
    """What a destination provides. Raise CloudError for expected failures."""

    def authenticate(self, token):
        """Return the device name for `token`, or None."""
        raise NotImplementedError

    def append(self, device, name, ts, request_id, value):
        raise NotImplementedError

    def records(self, device, name):
        """Yield (time, value) in the order they were received."""
        raise NotImplementedError

    def remove(self, device, name):
        """Delete what `device` saved under `name` (records or binary). Return how many were deleted."""
        raise NotImplementedError

    def put_binary(self, device, name, data):
        """Save bytes under `name`, replacing records or bytes already there (MVP+)."""
        raise NotImplementedError

    def is_binary(self, device, name):
        """True if `name` holds bytes saved with put_binary."""
        return False

    def names(self, device, prefix):
        """Return the names `device` has saved under, starting with `prefix`, sorted."""
        raise NotImplementedError

    def file(self, name):
        """Return the text of a file placed by the user (backend/files/), or None."""
        raise NotImplementedError

    def invoke(self, name, data, device, request_id, timeout_ms):
        """Run the user's function `name`. Return its output as a string.
        Raise CloudError(ERR_NOT_FOUND / ERR_TIMEOUT / ERR_RUN_FAILED)."""
        raise NotImplementedError

    def complete(self, system, text, log, image=None):
        """Ask the AI, with an optional JPEG `image` (bytes). Add tokensIn / tokensOut to `log`."""
        raise NotImplementedError

    def count_ask(self, device):
        """Count one question. Raise CloudError(ERR_LIMIT) when over the limit."""

    def log_call(self, device, op, request_id, entry):
        """Keep the call log."""

    ask_max_chars = 1000


class Core:
    def __init__(self, adapter):
        self.adapter = adapter

    def handle(self, path_or_op, body, token, request_id):
        """Returns (code, error, result). Never raises."""
        started = time.time()
        op = path_or_op.rsplit("/", 1)[-1]
        device = None
        log = {"in": 0, "out": 0, "name": ""}
        try:
            device = self.adapter.authenticate(token)
            if not device:
                raise CloudError(
                    ERR_AUTH,
                    "This device is not registered. Check that aws_config.h is up to date.",
                )
            if not isinstance(body, dict):
                raise CloudError(ERR_SERVER, "The request was broken. Update the library.")
            ops = {
                "ping": self.ping,
                "save": self.save,
                "load": self.load,
                "remove": self.remove,
                "list": self.list,
                "run": self.run,
                "ask": self.ask,
            }
            if op not in ops or ("/" in path_or_op and not path_or_op.startswith("/v1/")):
                raise CloudError(ERR_NOT_FOUND, f'Unknown request "{path_or_op}". Update the library.')
            log["in"] = len(str(body))
            log["name"] = str(body.get("name", ""))
            result = ops[op](device, body, request_id, log)
            log["out"] = len(result)
            return OK, "", result
        except CloudError as e:
            log["code"] = e.code
            return e.code, e.message, ""
        except Exception as e:  # never leak destination-specific errors to the device
            print(f"[{request_id}] unexpected error: {e!r}")
            log["code"] = ERR_SERVER
            return ERR_SERVER, "Something went wrong in the cloud. Try again later.", ""
        finally:
            if device:
                log["ms"] = int((time.time() - started) * 1000)
                try:
                    self.adapter.log_call(device, op, request_id, log)
                except Exception as e:
                    print(f"[{request_id}] could not write the call log: {e!r}")

    # --- ping (used by begin) ---

    def ping(self, device, body, request_id, log):
        return device

    # --- save / load (§4) ---

    def save(self, device, body, request_id, log):
        name = body.get("name")
        check_name(name)
        if "binary" in body:
            data = decode_base64(body["binary"])
            if len(data) > BINARY_MAX:
                raise CloudError(ERR_TOO_LARGE, "The data is too large (limit 1MB).")
            self.adapter.put_binary(device, name, data)
            return ""
        if self.adapter.is_binary(device, name):
            raise CloudError(
                ERR_TYPE_MISMATCH, f'"{name}" holds an image or other data, so lines cannot be added.'
            )
        value = str(body.get("value", ""))
        if len(value.encode("utf-8")) > RECORD_MAX:
            raise CloudError(ERR_TOO_LARGE, "The value is too large (limit 1KB per save).")
        ts = datetime.now(timezone.utc).isoformat(timespec="milliseconds").replace("+00:00", "Z")
        self.adapter.append(device, name, ts, request_id, value)
        return ""

    def load(self, device, body, request_id, log):
        name = body.get("name")
        check_name(name)
        if self.adapter.is_binary(device, name):
            raise CloudError(ERR_TYPE_MISMATCH, f'"{name}" holds an image or other data and cannot be loaded as text.')
        last = int(body.get("last") or 0)  # 0: everything; N: only the last N lines
        rows = self.adapter.records(device, name)
        if last > 0:
            rows = deque(rows, maxlen=last)
        lines = io.StringIO()
        writer = csv.writer(lines, lineterminator="\n")
        found = False
        for ts, value in rows:
            found = True
            writer.writerow([ts, value])
            if lines.tell() > LOAD_MAX:
                raise CloudError(ERR_TOO_LARGE, too_large(name))
        if found:
            return lines.getvalue()
        text = self.adapter.file(name)
        if text is None:
            raise CloudError(ERR_NOT_FOUND, f'"{name}" was not found.')
        if last > 0:
            text = "".join(text.splitlines(keepends=True)[-last:])
        if len(text.encode("utf-8")) > LOAD_MAX:
            raise CloudError(ERR_TOO_LARGE, too_large(name))
        return text

    def remove(self, device, body, request_id, log):
        name = body.get("name")
        check_name(name)
        if self.adapter.remove(device, name) == 0:
            raise CloudError(
                ERR_NOT_FOUND,
                f'"{name}" was not saved by this device. (Files in backend/files/ cannot be removed.)',
            )
        return ""

    def list(self, device, body, request_id, log):
        prefix = str(body.get("prefix", ""))
        if prefix:
            check_name(prefix)
        names = self.adapter.names(device, prefix)
        text = "".join(n + "\n" for n in names)
        if len(text.encode("utf-8")) > LOAD_MAX:
            raise CloudError(ERR_TOO_LARGE, "Too many names to list (limit 16KB). Use a prefix.")
        return text

    # --- run (§5) ---

    def run(self, device, body, request_id, log):
        name = str(body.get("name", ""))
        data = str(body.get("input", ""))
        if len(data.encode("utf-8")) > RUN_INPUT_MAX:
            raise CloudError(ERR_TOO_LARGE, "The input is too large (limit 64KB).")
        timeout_ms = int(body.get("timeoutMs") or RUN_TIMEOUT_DEFAULT_MS)
        timeout_ms = max(1000, min(timeout_ms, RUN_TIMEOUT_MAX_MS))
        output = self.adapter.invoke(name, data, device, request_id, timeout_ms)
        if len(output.encode("utf-8")) > RUN_OUTPUT_MAX:
            raise CloudError(ERR_TOO_LARGE, f'The result of "{name}" is too large (limit 16KB).')
        return output

    # --- ask (§6) ---

    def ask(self, device, body, request_id, log):
        prompt = str(body.get("prompt", ""))
        data = str(body.get("data", ""))
        choices = body.get("choices") or []
        if len((prompt + data).encode("utf-8")) > ASK_INPUT_MAX:
            raise CloudError(ERR_TOO_LARGE, "The question and data are too large (limit 16KB).")
        image = None
        if body.get("image"):
            image = decode_base64(body["image"])
            if len(image) > IMAGE_MAX:
                raise CloudError(ERR_TOO_LARGE, "The image is too large (limit 3MB).")
        self.adapter.count_ask(device)

        text = prompt if not data else f"{prompt}\n\nData:\n{data}"
        if not choices:
            return self.adapter.complete(SYSTEM_TEXT, text, log, image)[: self.adapter.ask_max_chars]

        choices = [str(c) for c in choices]
        system = (
            SYSTEM_TEXT
            + " Reply with exactly one of these options and nothing else: "
            + " | ".join(choices)
        )
        for _ in range(2):  # one retry if the answer is not one of the choices
            answer = self.adapter.complete(system, text, log, image).strip().strip("\"'`.")
            for c in choices:
                if answer.lower() == c.lower():
                    return c
        raise CloudError(ERR_AI_FORMAT, "The AI's answer was not one of the choices.")


def decode_base64(text):
    try:
        return base64.b64decode(str(text), validate=True)
    except (binascii.Error, ValueError):
        raise CloudError(ERR_SERVER, "The data was broken on the way. Try again.")


def too_large(name):
    return f'"{name}" is too large to load (limit 16KB). Load only the last lines: load(name, 10).'


def check_name(name):
    if not isinstance(name, str) or not NAME.match(name) or ".." in name or name.startswith("/"):
        raise CloudError(
            ERR_INVALID_NAME,
            f'"{name}" cannot be used as a name. Use letters, digits and . _ - / (up to 128).',
        )
