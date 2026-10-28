"""Agreement between two raters: percent agreement and Cohen's kappa per column.

Usage: python3 tools/agreement.py [--binary] rater1.csv rater2.csv [column ...]
--binary compares only "sketch rewrite or not" (a code containing S, such as S or S+C, against
everything else), as reported in the paper (kappa 0.89 and 0.85).
Both CSV files need an `id` column; rows are matched by id. Codes are compared
as strings after stripping spaces; columns default to those both files share.
"""
import csv
import sys
from collections import Counter


def read(path):
    with open(path, newline="") as f:
        return {row["id"].strip(): row for row in csv.DictReader(f)}


def kappa(pairs):
    n = len(pairs)
    observed = sum(a == b for a, b in pairs) / n
    left = Counter(a for a, _ in pairs)
    right = Counter(b for _, b in pairs)
    expected = sum(left[c] * right[c] for c in left) / (n * n)
    # Undefined (0/0) when both raters put every item in one category.
    return observed, (observed - expected) / (1 - expected) if expected < 1 else None


def rewrite(code):
    return "S" if "S" in code.split("+") else "not S"


def main():
    args = sys.argv[1:]
    binary = "--binary" in args
    args = [a for a in args if a != "--binary"]
    r1, r2 = read(args[0]), read(args[1])
    ids = sorted(set(r1) & set(r2), key=lambda x: (len(x), x))
    shared = [c for c in next(iter(r1.values())) if c != "id" and c in next(iter(r2.values()))]
    columns = args[2:] or shared
    print(f"items: {len(ids)}")
    for col in columns:
        pairs = [(r1[i][col].strip(), r2[i][col].strip()) for i in ids]
        if binary:
            pairs = [(rewrite(a), rewrite(b)) for a, b in pairs]
        observed, k = kappa(pairs)
        shown = "undefined (one category)" if k is None else f"{k:.2f}"
        print(f"{col}: agreement {observed:.0%}, Cohen's kappa {shown}")
        for i, (a, b) in zip(ids, pairs):
            if a != b:
                print(f"  #{i}: {a} vs {b}")


if __name__ == "__main__":
    main()
