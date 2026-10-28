"""Local adapter: the same save / load / run / ask, handled on this computer.

    python3 local/cloud_local.py                  # talk to the board over USB serial
    python3 local/cloud_local.py --http 8787      # also accept requests over the LAN
    python3 local/cloud_local.py stats            # how often each call ran

The contract comes from backend/runtime/core.py, the same code the AWS backend
uses. Only the destination differs:
    save / load -> SQLite (local/data.db)
    run         -> backend/functions/<name>.py, run with python3 (the same files Lambda runs)
    ask         -> Ollama (a local LLM server, http://localhost:11434)

Over serial, the board sends one request per line and this program answers on
the same line format:
    @cloud {"op": "save", "id": "...", "body": {...}}
    @cloud {"id": "...", "ok": true, "code": 0, "error": "", "result": "..."}
Any other line from the board (Serial.println) is shown here, so this program
also works as the serial monitor.
"""

import argparse
import base64
import json
import os
import re
import secrets
import sqlite3
import subprocess
import sys
import threading
import time
import urllib.error
import urllib.request
import uuid
from datetime import datetime, timedelta, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
sys.path.insert(0, os.path.join(REPO, "backend", "runtime"))

from core import ERR_NOT_FOUND, ERR_RUN_FAILED, ERR_SERVER, ERR_TIMEOUT, Adapter, CloudError, Core  # noqa: E402

PREFIX = "@cloud "
SERIAL_DEVICE = object()  # requests over USB come from the board plugged into this computer
FUNCTION_NAME = re.compile(r"^[A-Za-z][A-Za-z0-9_]{0,63}$")

# Runs the user's function in a fresh python3, so edits take effect at once
# and a stuck function can be stopped. Prints the result on the last line.
RUNNER = r"""
import importlib.util, inspect, json, sys
spec = importlib.util.spec_from_file_location("user_function", sys.argv[1])
mod = importlib.util.module_from_spec(spec)
try:
    spec.loader.exec_module(mod)
    data = sys.stdin.read()
    if len(inspect.signature(mod.run).parameters) >= 2:
        result = mod.run(data, {"device": sys.argv[2], "destination": "local"})
    else:
        result = mod.run(data)
    print("\n" + json.dumps({"output": "" if result is None else str(result)}))
except Exception as e:
    print("\n" + json.dumps({"error": str(e)}))
"""


class LocalAdapter(Adapter):
    def __init__(self, db_path, functions_dir, files_dir, ollama_url, model, vision_model, http_token):
        self.db = sqlite3.connect(db_path, check_same_thread=False)
        self.lock = threading.Lock()
        with self.lock:
            self.db.executescript(
                """
                CREATE TABLE IF NOT EXISTS records (
                    seq INTEGER PRIMARY KEY AUTOINCREMENT,
                    device TEXT, name TEXT, ts TEXT, request_id TEXT, value TEXT);
                CREATE INDEX IF NOT EXISTS records_name ON records (device, name, seq);
                CREATE TABLE IF NOT EXISTS blobs (
                    device TEXT, name TEXT, data BLOB, PRIMARY KEY (device, name));
                CREATE TABLE IF NOT EXISTS calls (
                    ts TEXT, device TEXT, op TEXT, name TEXT, code INTEGER, ms INTEGER,
                    bytes_in INTEGER, bytes_out INTEGER, tokens_in INTEGER, tokens_out INTEGER);
                """
            )
        self.functions_dir = functions_dir
        self.files_dir = files_dir
        self.ollama_url = ollama_url.rstrip("/")
        self.model = model
        self.vision_model = vision_model
        self.http_token = http_token

    def authenticate(self, token):
        if token is SERIAL_DEVICE:
            return "local-serial"
        if self.http_token and token == self.http_token:
            return "local-lan"
        return None

    def append(self, device, name, ts, request_id, value):
        with self.lock:
            self.db.execute(
                "INSERT INTO records (device, name, ts, request_id, value) VALUES (?, ?, ?, ?, ?)",
                (device, name, ts, request_id, value),
            )
            self.db.commit()

    def records(self, device, name):
        with self.lock:
            rows = self.db.execute(
                "SELECT ts, value FROM records WHERE device = ? AND name = ? ORDER BY seq",
                (device, name),
            ).fetchall()
        return rows

    def remove(self, device, name):
        with self.lock:
            deleted = self.db.execute(
                "DELETE FROM records WHERE device = ? AND name = ?", (device, name)
            ).rowcount
            deleted += self.db.execute(
                "DELETE FROM blobs WHERE device = ? AND name = ?", (device, name)
            ).rowcount
            self.db.commit()
        return deleted

    def put_binary(self, device, name, data):
        self.remove(device, name)  # an image replaces whatever was there
        with self.lock:
            self.db.execute("INSERT INTO blobs VALUES (?, ?, ?)", (device, name, data))
            self.db.commit()

    def is_binary(self, device, name):
        with self.lock:
            return self.db.execute(
                "SELECT 1 FROM blobs WHERE device = ? AND name = ?", (device, name)
            ).fetchone() is not None

    def names(self, device, prefix):
        with self.lock:
            rows = self.db.execute(
                "SELECT name FROM records WHERE device = ? AND substr(name, 1, ?) = ? "
                "UNION SELECT name FROM blobs WHERE device = ? AND substr(name, 1, ?) = ? "
                "ORDER BY name",
                (device, len(prefix), prefix, device, len(prefix), prefix),
            ).fetchall()
        return [r[0] for r in rows]

    def file(self, name):
        path = os.path.join(self.files_dir, name)
        if not os.path.isfile(path):
            return None
        with open(path, encoding="utf-8", errors="replace") as f:
            return f.read()

    def invoke(self, name, data, device, request_id, timeout_ms):
        path = os.path.join(self.functions_dir, f"{name}.py")
        if not FUNCTION_NAME.match(name) or not os.path.isfile(path):
            raise CloudError(
                ERR_NOT_FOUND,
                f'There is no function "{name}". Put {name}.py in backend/functions/.',
            )
        try:
            done = subprocess.run(
                [sys.executable, "-c", RUNNER, path, device],
                input=data,
                capture_output=True,
                text=True,
                timeout=timeout_ms / 1000,
            )
        except subprocess.TimeoutExpired:
            raise CloudError(ERR_TIMEOUT, f'"{name}" did not finish within {timeout_ms // 1000} s.')
        lines = done.stdout.rstrip("\n").split("\n")
        for line in lines[:-1]:  # print() inside the function shows up here
            if line:
                print(f"  [{name}] {line}")
        try:
            outcome = json.loads(lines[-1])
        except (ValueError, IndexError):
            raise CloudError(ERR_RUN_FAILED, f'An error occurred in "{name}": {done.stderr.strip()}')
        if "error" in outcome:
            raise CloudError(ERR_RUN_FAILED, f'An error occurred in "{name}": {outcome["error"]}')
        return outcome["output"]

    def complete(self, system, text, log, image=None):
        user = {"role": "user", "content": text}
        if image:
            user["images"] = [base64.b64encode(image).decode()]
        request = urllib.request.Request(
            f"{self.ollama_url}/api/chat",
            data=json.dumps(
                {
                    "model": self.vision_model if image else self.model,
                    "messages": [{"role": "system", "content": system}, user],
                    "stream": False,
                    "options": {"temperature": 0.2},
                }
            ).encode(),
            headers={"content-type": "application/json"},
        )
        try:
            with urllib.request.urlopen(request, timeout=120) as res:
                answer = json.load(res)
        except (urllib.error.URLError, TimeoutError) as e:
            print(f"ollama error: {e!r}")
            raise CloudError(
                ERR_SERVER, "The local AI is not available. Check that Ollama is running."
            )
        log["tokensIn"] = log.get("tokensIn", 0) + answer.get("prompt_eval_count", 0)
        log["tokensOut"] = log.get("tokensOut", 0) + answer.get("eval_count", 0)
        return answer.get("message", {}).get("content", "")

    def log_call(self, device, op, request_id, entry):
        with self.lock:
            self.db.execute(
                "INSERT INTO calls VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    datetime.now(timezone.utc).isoformat(),
                    device,
                    op,
                    entry.get("name", ""),
                    entry.get("code", 0),
                    entry.get("ms", 0),
                    entry.get("in", 0),
                    entry.get("out", 0),
                    entry.get("tokensIn", 0),
                    entry.get("tokensOut", 0),
                ),
            )
            self.db.commit()


def reply(request_id, code, error, result):
    return {"id": request_id, "ok": code == 0, "code": code, "error": error, "result": result}


# --- USB serial ---------------------------------------------------------------


def find_port():
    from serial.tools import list_ports

    candidates = [
        p.device
        for p in list_ports.comports()
        if re.search(r"usbserial|usbmodem|SLAB|wchusbserial|ttyUSB|ttyACM|COM\d+", p.device)
    ]
    if len(candidates) == 1:
        return candidates[0]
    if not candidates:
        sys.exit("No board found. Plug in the board, or give the port with --port.")
    sys.exit("Several boards found: " + ", ".join(candidates) + ". Choose one with --port.")


def serve_serial(core, port, baud):
    import serial

    link = serial.Serial()
    link.port = port
    link.baudrate = baud
    link.timeout = 0.2
    link.dtr = False  # opening the port must not hold the ESP32 in reset
    link.rts = False
    link.open()
    print(f"Listening on {port} ({baud} bps). Lines from the board are shown below.")
    buffer = b""
    while True:
        buffer += link.read(link.in_waiting or 1)
        while b"\n" in buffer:
            raw, buffer = buffer.split(b"\n", 1)
            line = raw.decode("utf-8", errors="replace").rstrip("\r")
            if not line.startswith(PREFIX):
                print(line)
                continue
            op = "?"
            try:
                message = json.loads(line[len(PREFIX):])
                op = str(message.get("op", ""))
                request_id = str(message.get("id") or uuid.uuid4())
                code, error, result = core.handle(op, message.get("body"), SERIAL_DEVICE, request_id)
            except (ValueError, AttributeError):
                request_id, code, error, result = "", ERR_SERVER, "The request was broken.", ""
            answer = PREFIX + json.dumps(reply(request_id, code, error, result), ensure_ascii=False)
            link.write((answer + "\n").encode("utf-8"))
            print(f"  -> {op}: {'ok' if code == 0 else f'error {code}: {error}'}")


# --- LAN (HTTP) ---------------------------------------------------------------


def serve_http(core, port):
    class Handler(BaseHTTPRequestHandler):
        def do_POST(self):
            length = int(self.headers.get("content-length") or 0)
            try:
                body = json.loads(self.rfile.read(length) or b"{}")
            except ValueError:
                body = None
            request_id = self.headers.get("x-request-id") or str(uuid.uuid4())
            code, error, result = core.handle(
                self.path, body, self.headers.get("x-device-token", ""), request_id
            )
            data = json.dumps(reply(request_id, code, error, result), ensure_ascii=False).encode()
            self.send_response(200)
            self.send_header("content-type", "application/json")
            self.send_header("content-length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)

        def log_message(self, *args):
            pass

    server = ThreadingHTTPServer(("0.0.0.0", port), Handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    return server


# --- stats --------------------------------------------------------------------


def show_stats(db_path, days):
    db = sqlite3.connect(db_path)
    since = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()
    rows = db.execute(
        """SELECT op || ' ' || name, COUNT(*), SUM(code != 0), CAST(AVG(ms) AS INTEGER)
           FROM calls WHERE ts >= ? GROUP BY op, name ORDER BY op, name""",
        (since,),
    ).fetchall()
    print(f"Last {days} days\n")
    print("call".ljust(32) + "times".rjust(7) + "errors".rjust(8) + "avg ms".rjust(9))
    for name, times, errors, ms in rows:
        print(name.strip().ljust(32) + str(times).rjust(7) + str(errors).rjust(8) + str(ms).rjust(9))
    print("\nThe local AI is free; it only uses this computer.")


def main():
    sys.stdout.reconfigure(line_buffering=True)  # show the board's lines at once
    parser = argparse.ArgumentParser(description="Local adapter for the cloud library.")
    parser.add_argument("command", nargs="?", default="serve", choices=["serve", "stats"])
    parser.add_argument("--port", help="serial port of the board (found automatically if only one)")
    parser.add_argument("--baud", type=int, default=115200)
    parser.add_argument("--no-serial", action="store_true", help="do not open a serial port")
    parser.add_argument("--http", type=int, metavar="PORT", help="also accept requests over the LAN")
    parser.add_argument("--db", default=os.path.join(HERE, "data.db"))
    parser.add_argument("--functions", default=os.path.join(REPO, "backend", "functions"))
    parser.add_argument("--files", default=os.path.join(REPO, "backend", "files"))
    parser.add_argument("--ollama", default="http://localhost:11434")
    parser.add_argument("--model", default="qwen2.5:3b")
    parser.add_argument("--vision-model", default="qwen2.5vl:3b", help="model for questions with an image")
    parser.add_argument("--days", type=int, default=7)
    args = parser.parse_args()

    if args.command == "stats":
        show_stats(args.db, args.days)
        return

    token = os.environ.get("CLOUD_LOCAL_TOKEN") or secrets.token_urlsafe(18)
    core = Core(
        LocalAdapter(args.db, args.functions, args.files, args.ollama, args.model, args.vision_model, token)
    )
    if args.http:
        serve_http(core, args.http)
        print(f"Accepting requests on port {args.http}. Device token: {token}")
    if args.no_serial:
        while True:
            time.sleep(3600)
    serve_serial(core, args.port or find_port(), args.baud)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        pass
