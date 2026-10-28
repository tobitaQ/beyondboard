"""Agreement between the two raters' step counts (Spearman's rho), as reported in the paper.

Usage: python3 tools/step_agreement.py
The counts are copied from the two raters' records:
  rater 1: the authors' counts (the paper's tables)
  rater 2: evaluation/second_rater/e1_rater2.md (summary table)
Arduino Cloud apps 1-2 exclude the dashboard check (recounted 2026-10-17: checking the result is
not counted for any approach); apps 3-5 are the earlier webhook version that rater 2 counted.
Order: apps 1-5 for AWS direct, then Arduino Cloud, then BeyondBoard.
"""

RATER1 = {
    "steps, including one-time setup": [12, 16, 17, 18, 19, 7, 8, 14, 14, 15, 11, 12, 13, 12, 12],
    "web-console steps, including setup": [7, 9, 10, 11, 11, 5, 6, 9, 9, 10, 1, 1, 1, 2, 2],
    "steps per application (no setup)": [12, 16, 17, 18, 19, 7, 8, 14, 14, 15, 4, 5, 6, 5, 5],
}
RATER2 = {
    "steps, including one-time setup": [10, 15, 12, 14, 15, 8, 11, 15, 18, 18, 12, 13, 13, 13, 13],
    "web-console steps, including setup": [5, 9, 7, 9, 10, 7, 10, 14, 17, 17, 0, 0, 0, 1, 1],
    "steps per application (no setup)": [8, 13, 10, 11, 12, 7, 10, 13, 15, 15, 5, 6, 6, 5, 5],
}


def ranks(values):
    order = sorted(range(len(values)), key=lambda i: values[i])
    result = [0.0] * len(values)
    i = 0
    while i < len(order):
        j = i
        while j + 1 < len(order) and values[order[j + 1]] == values[order[i]]:
            j += 1
        for k in range(i, j + 1):
            result[order[k]] = (i + j) / 2 + 1  # average rank for ties
        i = j + 1
    return result


def spearman(a, b):
    ra, rb = ranks(a), ranks(b)
    n = len(a)
    ma, mb = sum(ra) / n, sum(rb) / n
    num = sum((x - ma) * (y - mb) for x, y in zip(ra, rb))
    den = (sum((x - ma) ** 2 for x in ra) * sum((y - mb) ** 2 for y in rb)) ** 0.5
    return num / den


for name in RATER1:
    print(f"{name}: rho = {spearman(RATER1[name], RATER2[name]):.2f}")
