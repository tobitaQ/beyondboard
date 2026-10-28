"""Score the on-device and the cloud face detector against WIDER FACE (PROTOCOL.md).

Usage: python3 analyze.py   (reads selection.csv and results/*_pass*.txt)
Prints count accuracy, detection precision/recall/F1 at IoU 0.5, paired tests,
bootstrap 95% confidence intervals, and latency; writes results/summary.csv.
"""
import csv
import glob
import math
import os
import random
import statistics

from scipy.stats import binomtest, wilcoxon

HERE = os.path.dirname(os.path.abspath(__file__))


def boxes(text, corners):
    out = []
    for part in filter(None, text.strip().split(";")):
        a, b, c, d = (int(v) for v in part.split())
        out.append((a, b, c - a, d - b) if corners else (a, b, c, d))
    return out


def iou(p, q):
    ax, ay, aw, ah = p
    bx, by, bw, bh = q
    w = max(0, min(ax + aw, bx + bw) - max(ax, bx))
    h = max(0, min(ay + ah, by + bh) - max(ay, by))
    inter = w * h
    return inter / (aw * ah + bw * bh - inter) if inter else 0.0


def match(pred, truth):
    """Greedy one-to-one matching by descending IoU >= 0.5; returns true positives."""
    pairs = sorted(((iou(p, t), i, j) for i, p in enumerate(pred) for j, t in enumerate(truth)), reverse=True)
    used_p, used_t, tp = set(), set(), 0
    for v, i, j in pairs:
        if v < 0.5:
            break
        if i not in used_p and j not in used_t:
            used_p.add(i)
            used_t.add(j)
            tp += 1
    return tp


def read_pass(path):
    rows = {}
    with open(path) as f:
        lines = [l for l in f.read().splitlines() if l and l[:2].isdigit() and "," in l]
    for l in lines:
        cols = l.split(",", 4)
        if len(cols) == 5 and cols[0] not in rows:  # face rows, not the ask rows
            rows[cols[0]] = cols
    return rows


def load(arm, corners):
    passes = [read_pass(p) for p in sorted(glob.glob(os.path.join(HERE, "results", f"{arm}_pass*.txt")))]
    first = passes[0]
    result = {i: {"faces": int(c[1]), "boxes": boxes(c[4], corners)} for i, c in first.items()}
    times = [int(c[2]) + int(c[3]) for p in passes for c in p.values()]
    parts = [(int(c[2]), int(c[3])) for p in passes for c in p.values()]
    return result, times, parts


def p95(values):
    s = sorted(values)
    return s[math.ceil(len(s) * 0.95) - 1]


def main():
    truth = {}
    with open(os.path.join(HERE, "selection.csv")) as f:
        for r in csv.DictReader(f):
            truth[r["id"]] = boxes(r["boxes"], corners=False)
    ids = sorted(truth)
    arms = {"on-device": load("ondevice", True), "cloud": load("cloud", False)}
    rng = random.Random(1)
    summary = []
    errors = {}
    exact = {}
    for name, (res, times, parts) in arms.items():
        err = [res[i]["faces"] - len(truth[i]) for i in ids]
        errors[name] = [abs(e) for e in err]
        exact[name] = [e == 0 for e in err]
        faces_ids = [i for i in ids if truth[i]]
        empty_ids = [i for i in ids if not truth[i]]
        tp = sum(match(res[i]["boxes"], truth[i]) for i in ids)
        npred = sum(len(res[i]["boxes"]) for i in ids)
        ntrue = sum(len(truth[i]) for i in ids)
        prec, rec = tp / npred if npred else 0, tp / ntrue
        f1 = 2 * prec * rec / (prec + rec) if prec + rec else 0
        boot = []
        for _ in range(10000):
            sample = [rng.choice(ids) for _ in ids]
            boot.append(statistics.mean(abs(res[i]["faces"] - len(truth[i])) for i in sample))
        boot.sort()
        row = {
            "arm": name,
            "mae": round(statistics.mean(errors[name]), 3),
            "mae_ci": f"{boot[249]:.2f}-{boot[9749]:.2f}",
            "signed_error": round(statistics.mean(err), 3),
            "exact": f"{sum(exact[name])}/{len(ids)}",
            "exact_faces": f"{sum(exact[name][ids.index(i)] for i in faces_ids)}/{len(faces_ids)}",
            "false_alarm_no_face": f"{sum(res[i]['faces'] > 0 for i in empty_ids)}/{len(empty_ids)}",
            "precision": round(prec, 3),
            "recall": round(rec, 3),
            "f1": round(f1, 3),
            "time_median_ms": statistics.median(times),
            "time_p95_ms": p95(times),
            "part1_median_ms": statistics.median(p[0] for p in parts),
            "part2_median_ms": statistics.median(p[1] for p in parts),
        }
        summary.append(row)
        for k, v in row.items():
            print(f"{name:10s} {k}: {v}")
        print()
    w = wilcoxon(errors["on-device"], errors["cloud"], zero_method="wilcox")
    b = sum(1 for a, c in zip(exact["on-device"], exact["cloud"]) if a and not c)
    c = sum(1 for a, c_ in zip(exact["on-device"], exact["cloud"]) if c_ and not a)
    mc = binomtest(min(b, c), b + c, 0.5).pvalue if b + c else 1.0
    print(f"Wilcoxon on |count error|: W={w.statistic}, p={w.pvalue:.4g}")
    print(f"McNemar (exact) on exact match: only on-device {b}, only cloud {c}, p={mc:.4g}")
    with open(os.path.join(HERE, "results", "summary.csv"), "w", newline="") as f:
        out = csv.DictWriter(f, fieldnames=list(summary[0]))
        out.writeheader()
        out.writerows(summary)
        f.write(f"# Wilcoxon |count error| W={w.statistic} p={w.pvalue:.4g}; McNemar exact p={mc:.4g} (b={b}, c={c})\n")


if __name__ == "__main__":
    main()
