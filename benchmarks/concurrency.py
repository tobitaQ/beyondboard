"""E2: ten devices calling at the same time, simulated from this computer.

    python3 benchmarks/concurrency.py aws
    python3 benchmarks/concurrency.py local http://localhost:8787 TOKEN

Each simulated device runs save and run ROUNDS times and ask ASKS times,
all devices at once. Writes benchmarks/results/concurrency-<destination>.csv
and prints the median and 95th percentile per call.
"""

import csv
import json
import math
import os
import statistics
import sys
import threading
import time
import urllib.request
import uuid

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DEVICES = 10
ROUNDS = 20
ASKS = 3


def target():
    if len(sys.argv) >= 2 and sys.argv[1] == "aws":
        backend = os.path.join(ROOT, "backend")
        outputs = json.load(open(os.path.join(backend, ".build", "outputs.json")))
        tokens = json.load(open(os.path.join(backend, ".secrets", "devices.json")))
        return "aws", outputs["AwsCloudBackend"]["ApiUrl"].rstrip("/"), next(iter(tokens.values()))
    if len(sys.argv) >= 4 and sys.argv[1] == "local":
        return "local", sys.argv[2].rstrip("/"), sys.argv[3]
    sys.exit(__doc__)


NAME, URL, TOKEN = target()


def call(op, body):
    request = urllib.request.Request(
        f"{URL}/v1/{op}",
        data=json.dumps(body).encode(),
        headers={
            "content-type": "application/json",
            "x-device-token": TOKEN,
            "x-request-id": str(uuid.uuid4()),
        },
        method="POST",
    )
    start = time.perf_counter()
    with urllib.request.urlopen(request, timeout=120) as res:
        code = json.load(res)["code"]
    return (time.perf_counter() - start) * 1000, code


def device(n, rows, lock):
    work = []
    for i in range(ROUNDS):
        work.append(("save", {"name": f"bench/device{n}.csv", "value": str(20 + i)}))
        work.append(("run", {"name": "detectAnomaly", "input": str(25 + i % 10)}))
    for i in range(ASKS):
        work.append(
            (
                "ask",
                {
                    "prompt": "How safe is this server room?",
                    "data": f"{20 + n + i} C",
                    "choices": ["normal", "warning", "danger"],
                },
            )
        )
    for op, body in work:
        ms, code = call(op, body)
        with lock:
            rows.append({"destination": NAME, "device": n, "op": op, "ms": round(ms, 1), "code": code})


def main():
    rows, lock = [], threading.Lock()
    threads = [threading.Thread(target=device, args=(n, rows, lock)) for n in range(DEVICES)]
    started = time.perf_counter()
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    total = time.perf_counter() - started

    out = os.path.join(ROOT, "benchmarks", "results", f"concurrency-{NAME}.csv")
    with open(out, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=["destination", "device", "op", "ms", "code"])
        writer.writeheader()
        writer.writerows(rows)

    print(f"{NAME}: {DEVICES} devices at once, {len(rows)} calls in {total:.1f} s -> {out}\n")
    print("op      calls  errors  median ms  p95 ms")
    for op in ["save", "run", "ask"]:
        ms = sorted(r["ms"] for r in rows if r["op"] == op)
        errors = sum(1 for r in rows if r["op"] == op and r["code"] != 0)
        p95 = ms[math.ceil(len(ms) * 0.95) - 1]
        print(f"{op:6}{len(ms):7}{errors:8}{statistics.median(ms):11.0f}{p95:8.0f}")


if __name__ == "__main__":
    main()
