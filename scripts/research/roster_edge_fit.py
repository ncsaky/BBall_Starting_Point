#!/usr/bin/env python3
"""Summarize and test the public roster-edge evidence without network access."""
from __future__ import annotations

import argparse
from collections import Counter
import json
from pathlib import Path
from statistics import mean

YEARS = (2023, 2024, 2025, 2026)
DATA = Path(__file__).resolve().parents[2] / "data/research/roster_edge_2023_2026.json"


def count_holdouts(counts):
    """Predict a year's count with the average of the other three years."""
    return {
        year: {
            "observed": counts[year],
            "prediction": round(mean(counts[other] for other in YEARS if other != year), 2),
        }
        for year in YEARS
    }


def sign_and_trades(rows):
    counts = Counter(row["summer"] for row in rows)
    return {
        "signed_players": dict(counts),
        "receiving_teams": {year: len({r["receiver"] for r in rows if r["summer"] == year}) for year in YEARS},
        "receiver_mechanisms": dict(Counter(row["receiver_mechanism"] for row in rows)),
        "count_holdouts": count_holdouts(counts),
    }


def validate(data):
    for section, rows in data["decisions"].items():
        for row in rows:
            if row["summer"] not in YEARS or not row["sources"] or set(row["sources"]) - data["sources"].keys():
                raise ValueError(f"Invalid year or citation in {section}: {row}")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data", type=Path, default=DATA)
    args = parser.parse_args()
    data = json.loads(args.data.read_text(encoding="utf-8"))
    validate(data)
    result = {"sign_and_trades": sign_and_trades(data["decisions"]["sign_and_trades"])}
    print(json.dumps(result, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
