"""Conformance tests (E4): the same checks for every destination.

    python3 tests/conformance.py aws                       # the deployed AWS backend
    python3 tests/conformance.py local http://localhost:8787 TOKEN

Each check is one clause of the contract. A destination conforms when all
checks pass. The AI checks cost a little on AWS (about USD 0.001 in total).
"""

import base64
import json
import os
import sys
import urllib.request
import uuid

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CHOICES = ["normal", "warning", "danger"]


def target():
    if len(sys.argv) >= 2 and sys.argv[1] == "aws":
        backend = os.path.join(REPO, "backend")
        outputs = json.load(open(os.path.join(backend, ".build", "outputs.json")))
        tokens = json.load(open(os.path.join(backend, ".secrets", "devices.json")))
        return "aws", outputs["AwsCloudBackend"]["ApiUrl"].rstrip("/"), next(iter(tokens.values()))
    if len(sys.argv) >= 4 and sys.argv[1] == "local":
        return "local", sys.argv[2].rstrip("/"), sys.argv[3]
    sys.exit(__doc__)


NAME, URL, TOKEN = target()


def call(op, body, token=None):
    request = urllib.request.Request(
        f"{URL}/v1/{op}",
        data=json.dumps(body).encode(),
        headers={
            "content-type": "application/json",
            "x-device-token": TOKEN if token is None else token,
            "x-request-id": str(uuid.uuid4()),
        },
        method="POST",
    )
    with urllib.request.urlopen(request, timeout=90) as res:
        return json.load(res)


def expect_ok(r):
    assert r["ok"] and r["code"] == 0, f"expected success, got {r['code']}: {r['error']}"
    return r["result"]


def expect_code(r, code):
    assert r["code"] == code, f"expected error {code}, got {r['code']}: {r['error']}"
    assert r["error"], "the error must come with a message"


def lines_of(csv_text):
    import csv
    import io

    return list(csv.reader(io.StringIO(csv_text)))


# --- checks ---


def begin_reaches_the_cloud():  # §3
    expect_ok(call("ping", {}))


def wrong_token_is_refused():  # §7, §8
    expect_code(call("ping", {}, token="wrong"), 4)


def save_appends_in_order():  # §4.2
    name = f"test/{uuid.uuid4().hex}.csv"
    for v in ["1", "2.5", "three"]:
        expect_ok(call("save", {"name": name, "value": v}))
    rows = lines_of(expect_ok(call("load", {"name": name})))
    assert [r[1] for r in rows] == ["1", "2.5", "three"], rows
    assert all(r[0].endswith("Z") and "T" in r[0] for r in rows), "time must be UTC ISO 8601"


def save_keeps_commas_and_newlines():  # §4.2 (CSV quoting)
    name = f"test/{uuid.uuid4().hex}.csv"
    value = 'a,b "c"\nd'
    expect_ok(call("save", {"name": name, "value": value}))
    assert lines_of(expect_ok(call("load", {"name": name})))[0][1] == value


def save_rejects_large_values():  # §4.2
    expect_code(call("save", {"name": "test/big.csv", "value": "x" * 1025}), 6)


def names_are_checked():  # §4.1
    for bad in ["", "a..b", "/abs", "sp ace", "x" * 129]:
        expect_code(call("save", {"name": bad, "value": "1"}), 12)


def load_reads_placed_files():  # §4.4
    with open(os.path.join(REPO, "backend", "files", "config.json"), encoding="utf-8") as f:
        assert expect_ok(call("load", {"name": "config.json"})) == f.read()


def load_reports_missing():  # §4.4
    expect_code(call("load", {"name": f"test/{uuid.uuid4().hex}.csv"}), 5)


def load_returns_the_last_lines():  # §4.4
    name = f"test/{uuid.uuid4().hex}.csv"
    for v in ["1", "2", "3", "4"]:
        expect_ok(call("save", {"name": name, "value": v}))
    rows = lines_of(expect_ok(call("load", {"name": name, "last": 2})))
    assert [r[1] for r in rows] == ["3", "4"], rows
    with open(os.path.join(REPO, "backend", "files", "config.json"), encoding="utf-8") as f:
        last_line = f.read().splitlines(keepends=True)[-1]
    assert expect_ok(call("load", {"name": "config.json", "last": 1})) == last_line


def remove_deletes_saved_records():  # §4.5
    name = f"test/{uuid.uuid4().hex}.csv"
    expect_ok(call("save", {"name": name, "value": "1"}))
    expect_ok(call("remove", {"name": name}))
    expect_code(call("load", {"name": name}), 5)
    expect_code(call("remove", {"name": name}), 5)
    expect_code(call("remove", {"name": "config.json"}), 5)  # placed files cannot be removed


def list_shows_saved_names():  # §4.6
    folder = f"test/{uuid.uuid4().hex}/"
    for n in ["b.csv", "a.csv"]:
        expect_ok(call("save", {"name": folder + n, "value": "1"}))
    assert expect_ok(call("list", {"prefix": folder})) == f"{folder}a.csv\n{folder}b.csv\n"
    expect_ok(call("remove", {"name": folder + "a.csv"}))
    assert expect_ok(call("list", {"prefix": folder})) == f"{folder}b.csv\n"


def image():
    with open(os.path.join(REPO, "tests", "fixtures", "red_circle.jpg"), "rb") as f:
        return base64.b64encode(f.read()).decode()


def save_binary_replaces_and_is_kept_apart():  # §4.3 (MVP+)
    name = f"test/{uuid.uuid4().hex}.jpg"
    expect_ok(call("save", {"name": name, "value": "1"}))
    expect_ok(call("save", {"name": name, "binary": image()}))  # an image replaces lines
    expect_code(call("save", {"name": name, "value": "2"}), 7)  # no lines on an image
    expect_code(call("load", {"name": name}), 7)  # images are not loaded as text
    assert name + "\n" in expect_ok(call("list", {"prefix": "test/"}))
    expect_ok(call("remove", {"name": name}))
    expect_code(call("load", {"name": name}), 5)


def save_rejects_large_binary():  # §4.3 (MVP+)
    big = base64.b64encode(b"x" * (1024 * 1024 + 1)).decode()
    expect_code(call("save", {"name": "test/big.bin", "binary": big}), 6)


def ask_answers_about_an_image():  # §6 (MVP+)
    r = call("ask", {"prompt": "What is the main color of this image? One word.", "image": image(),
                     "choices": ["red", "green", "blue", "white"]})
    if r["code"] != 10:
        assert expect_ok(r) in ["red", "green", "blue", "white"], r


def run_passes_input_and_output():  # §5
    assert expect_ok(call("run", {"name": "detectAnomaly", "input": "38.2"})) == "anomaly"
    assert expect_ok(call("run", {"name": "detectAnomaly", "input": "21"})) == "normal"


def run_reports_missing_function():  # §5
    expect_code(call("run", {"name": "noSuchFunction", "input": ""}), 5)


def run_reports_errors_inside():  # §5
    r = call("run", {"name": "detectAnomaly", "input": "abc"})
    expect_code(r, 9)
    assert "abc" in r["error"], "the function's own message must be passed on"


def run_stops_at_timeout():  # §5
    expect_code(call("run", {"name": "testSleep", "input": "4", "timeoutMs": 1000}), 8)


def run_rejects_large_input():  # §5
    expect_code(call("run", {"name": "detectAnomaly", "input": "1" * (64 * 1024 + 1)}), 6)


def ask_answers_in_text():  # §6
    assert expect_ok(call("ask", {"prompt": "Reply with the word OK.", "data": ""})).strip()


def ask_choices_are_always_one_of_them():  # §6
    for data in ["21 C", "35 C", "55 C"]:
        r = call("ask", {"prompt": "How safe is this server room?", "data": data, "choices": CHOICES})
        if r["code"] == 10:  # allowed by the contract: the AI failed twice
            continue
        assert expect_ok(r) in CHOICES, r


def unknown_request_is_reported():  # §8
    expect_code(call("nope", {}), 5)


CHECKS = [
    begin_reaches_the_cloud,
    wrong_token_is_refused,
    save_appends_in_order,
    save_keeps_commas_and_newlines,
    save_rejects_large_values,
    names_are_checked,
    load_reads_placed_files,
    load_reports_missing,
    load_returns_the_last_lines,
    remove_deletes_saved_records,
    list_shows_saved_names,
    save_binary_replaces_and_is_kept_apart,
    save_rejects_large_binary,
    ask_answers_about_an_image,
    run_passes_input_and_output,
    run_reports_missing_function,
    run_reports_errors_inside,
    run_stops_at_timeout,
    run_rejects_large_input,
    ask_answers_in_text,
    ask_choices_are_always_one_of_them,
    unknown_request_is_reported,
]

if __name__ == "__main__":
    failed = 0
    print(f"Conformance tests against {NAME} ({URL})\n")
    for check in CHECKS:
        try:
            check()
            print(f"  pass  {check.__name__}")
        except Exception as e:
            failed += 1
            print(f"  FAIL  {check.__name__}: {e}")
    print(f"\n{len(CHECKS) - failed}/{len(CHECKS)} passed")
    sys.exit(1 if failed else 0)
