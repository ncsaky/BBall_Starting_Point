"""How real NBA contracts are shaped: salary path (rising, flat, declining) and final-season options (CONTRACT-TERMS).

Reads the 2025-26 preseason salary table (HoopsHype, data/canonical/universe_2025_26_preseason.json), which lists
option years, and counts, among veteran contracts with at least two seasons listed (rookie-scale deals excluded:
their team options are set by the CBA):
- the salary path between the first two listed seasons: rising (> +1%), flat (within 1%), declining (< -1%);
- the size of the raise as a share of the first listed season;
- whether the last season is a player option or a team option;
by first-season salary band. Writes data/research/contract_structure_shares_2025_26.json and prints the table.

    PYTHONPATH=src .venv/bin/python scripts/contract_structure_shares.py
"""
from __future__ import annotations

import json
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BANDS = ((0, 3_000_000, "minimum (under $3M)"), (3_000_000, 15_000_000, "$3M-$15M"),
         (15_000_000, 35_000_000, "$15M-$35M"), (35_000_000, 10**10, "$35M and up"))


def band(salary: float) -> str:
    return next(label for low, high, label in BANDS if low <= salary < high)


def main() -> None:
    snap = json.loads((ROOT / "data/canonical/universe_2025_26_preseason.json").read_text())
    rookie_ids = set()
    for c in snap["contracts"]:
        rows = [r for r in c.get("seasons") or [] if r.get("salary") is not None]
        if any(r.get("option_type") == "qualifying_offer" for r in rows):
            rookie_ids.add(c["player_id"])   # first-round scale deals end with a qualifying-offer row in this table
    counts: dict[str, Counter] = defaultdict(Counter)
    raises: dict[str, list[float]] = defaultdict(list)
    for c in snap["contracts"]:
        if c["player_id"] in rookie_ids:
            continue
        rows = sorted((r for r in c.get("seasons") or [] if r.get("salary") is not None
                       and r.get("option_type") != "qualifying_offer"), key=lambda r: r["season"])
        if len(rows) < 2:
            continue
        first, second = float(rows[0]["salary"]), float(rows[1]["salary"])
        if first <= 0:
            continue
        change = (second - first) / first
        b = band(first)
        path = "rising" if change > 0.01 else "declining" if change < -0.01 else "flat"
        counts[b][path] += 1
        counts["all"][path] += 1
        if path != "flat":
            raises[b].append(change)
            raises["all"].append(change)
        last = rows[-1].get("option_type")
        option = "player" if last == "player_option" else "team" if last == "team_option" else "none"
        counts[b]["option_" + option] += 1
        counts["all"]["option_" + option] += 1
        counts[b]["contracts"] += 1
        counts["all"]["contracts"] += 1
    out = {}
    for b, row in counts.items():
        n = row["contracts"]
        rising = sorted(x for x in raises[b] if x > 0)
        out[b] = {
            "contracts": n,
            "path_share": {p: round(row[p] / n, 3) for p in ("rising", "flat", "declining")},
            "option_share": {o: round(row["option_" + o] / n, 3) for o in ("none", "player", "team")},
            "median_raise": round(rising[len(rising) // 2], 4) if rising else None,
        }
    payload = {"source": "data/canonical/universe_2025_26_preseason.json (HoopsHype salary pages, April 2026)",
               "method": __doc__.strip().splitlines()[0], "bands": out}
    (ROOT / "data/research/contract_structure_shares_2025_26.json").write_text(json.dumps(payload, indent=1) + "\n")
    for b, row in sorted(out.items(), key=lambda kv: -kv[1]["contracts"]):
        print(f"{b:22s} n={row['contracts']:3d} path {row['path_share']} options {row['option_share']} median raise {row['median_raise']}")


if __name__ == "__main__":
    main()
