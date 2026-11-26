#!/usr/bin/env python3
"""RATINGS-FIVE-INPUTS: which inputs moved between two built inputs files, and the largest movers.

    PYTHONPATH=src .venv/bin/python scripts/research/five_inputs_diff.py BEFORE.json.gz AFTER.json.gz [--top 15]
"""
from __future__ import annotations

import argparse
import json
import statistics
import sys
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from five_inputs_evidence import load_inputs  # noqa: E402


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("before", type=Path)
    ap.add_argument("after", type=Path)
    ap.add_argument("--top", type=int, default=15)
    ap.add_argument("--keys", default="")
    args = ap.parse_args()
    a, b = load_inputs(args.before), load_inputs(args.after)
    moved = defaultdict(list)
    for pid in a.keys() & b.keys():
        for k, v in a[pid].items():
            if k in b[pid] and abs(b[pid][k] - v) > 1e-9:
                moved[k].append((b[pid][k] - v, pid))
    print("input: players moved, mean |change|, largest |change|")
    for k in sorted(moved, key=lambda k: -len(moved[k])):
        d = [abs(x) for x, _ in moved[k]]
        print(f"  {k:24s} {len(d):4d}  {statistics.fmean(d):.4f}  {max(d):.4f}")
    for k in [k for k in args.keys.split(",") if k]:
        rows = sorted(moved.get(k, []), key=lambda r: -abs(r[0]))[:args.top]
        print(f"\nlargest movers {k}:")
        for dv, pid in rows:
            print(f"  {pid:40s} {a[pid][k]:.3f} -> {b[pid][k]:.3f} ({dv:+.3f})")


if __name__ == "__main__":
    main()
