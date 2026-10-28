"""E2: summarize the latency and concurrency results.

Reads benchmarks/results/latency-*.csv (from LatencyBench on the board) and
benchmarks/results/concurrency-*.csv (from concurrency.py) and prints, for each
file and operation: n, errors, median, p95, min, max (ms).

p95 is the nearest rank, sorted[ceil(0.95 * n) - 1], the same as
concurrency.py. With n = 30 this is the 29th value; with n = 1 it is the only value.
All rows are counted, including failed calls (code != 0), which are also shown as errors.

Usage: python3 benchmarks/summarize.py
"""

import csv
import glob
import math
import os
import statistics

RESULTS = os.path.join(os.path.dirname(os.path.abspath(__file__)), "results")
OPS = ["begin", "save", "load", "run", "ask"]


def read(path):
    """Returns (source label, [(op, ms, code)]) for one result file."""
    label = os.path.basename(path)[: -len(".csv")]
    rows = []
    with open(path, newline="") as f:
        for r in csv.DictReader(f):
            if "kind" in r and r["kind"] != "bench":  # latency files also hold heap and end markers
                continue
            if not r.get("ms"):
                continue
            rows.append((r["op"], float(r["ms"]), int(r["code"])))
    return label, rows


def p95(values):
    s = sorted(values)
    return s[math.ceil(len(s) * 0.95) - 1]


def main():
    paths = sorted(glob.glob(os.path.join(RESULTS, "latency-*.csv")))
    paths += sorted(glob.glob(os.path.join(RESULTS, "concurrency-*.csv")))
    print(f"{'source':24}{'op':7}{'n':>5}{'errors':>8}{'median':>9}{'p95':>9}{'min':>9}{'max':>9}")
    for path in paths:
        label, rows = read(path)
        ops = [op for op in OPS if any(r[0] == op for r in rows)]
        ops += sorted({r[0] for r in rows} - set(ops))
        for op in ops:
            ms = [r[1] for r in rows if r[0] == op]
            errors = sum(1 for r in rows if r[0] == op and r[2] != 0)
            print(
                f"{label:24}{op:7}{len(ms):5}{errors:8}{statistics.median(ms):9.1f}"
                f"{p95(ms):9.1f}{min(ms):9.1f}{max(ms):9.1f}"
            )


if __name__ == "__main__":
    main()
