"""Rebuild when each real 2026-27 contract was signed and how long it originally ran (CONTRACT-TERMS part 1).

Writes data/canonical/contract_history_2026_27.json from the evidence listed in nba_gm_data/contract_history.py and
prints the counts by kind of evidence. Run from the repo root:

    PYTHONPATH=src .venv/bin/python scripts/build_contract_history.py
"""
from __future__ import annotations

import json
from collections import Counter
from pathlib import Path

from nba_gm_data.career_stats import career_record
from nba_gm_data.contract_ai import opening_bird_since
from nba_gm_data.contract_history import HISTORY_FILE, build_contract_history

ROOT = Path(__file__).resolve().parents[1]


def first_nba_start(player: dict) -> int | None:
    """First season of his real NBA career (ESPN career seasons), as a start year."""
    starts = [int(str(row.get("season"))[:4]) for row in (career_record(player) or {}).get("seasons") or []
              if str(row.get("season") or "")[:4].isdigit()]
    return min(starts) if starts else None


def main() -> None:
    universe = json.loads((ROOT / "data/canonical/universe_2026_27_offseason.json").read_text())
    snapshot = json.loads((ROOT / "data/canonical/universe_2025_26_preseason.json").read_text())
    history = build_contract_history(universe, snapshot, ROOT, bird_since=opening_bird_since,
                                     first_nba_start=first_nba_start)
    payload = {
        "season": "2026-27",
        "notes": ("When each real contract was signed and how long it originally ran, rebuilt from evidence "
                  "(nba_gm_data/contract_history.py). original_contract_years is null when the length is unknown; "
                  "original_contract_years_min is then the number of seasons the evidence confirms."),
        "counts": dict(Counter(r["kind"] for r in history.values())),
        "contracts": dict(sorted(history.items())),
    }
    (ROOT / HISTORY_FILE).write_text(json.dumps(payload, indent=1, sort_keys=True) + "\n")
    print(json.dumps(payload["counts"], indent=1))
    before = Counter(int(c.get("original_contract_years") or 0) for c in universe["contracts"] if c.get("seasons"))
    after = Counter(r.get("original_contract_years") for r in history.values())
    print("original length before (salary-table count):", sorted(before.items()))
    print("original length after (None = unknown):", sorted(after.items(), key=lambda kv: (kv[0] is None, kv[0] or 0)))


if __name__ == "__main__":
    main()
