"""League spread of every input development moves, for scaling development onto the 94 inputs.

Development is computed in hidden-rating points and routed onto the inputs (ratings_model.route_trait_deltas). It used
to add the same grade points to every input, but the league spread of physical capacity grades (conditioning,
recovery, agility: about 3-5 grade points) is a quarter of a technique grade's (about 14), so the same move was four
times as large relative to the league and stamina could jump 10+ points in a season. Writing each input's spread lets
the routing move every input by the same share of its own league spread.

Spread = population standard deviation over the opening 2026-27 league (data/canonical/player_inputs_2026_27.json),
of the value development moves: a technique "grade", a physical capacity's "display_grade", or standing jump height
(cm). Reference = the median spread of the technique grades, so a typical skill keeps its old step size.

    PYTHONPATH=src .venv/bin/python scripts/research/dev_curve_spread.py
"""
from __future__ import annotations

import json
import statistics as st
from pathlib import Path

from nba_gm_data import ratings_model as rm

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / rm.INPUT_SPREAD_FILE


def main() -> None:
    league = rm.load_league_inputs(ROOT)
    values: dict[str, list[float]] = {}
    for inputs in league.values():
        for input_id, record in inputs.items():
            if input_id in rm.JUMP_CM_PER_GRADE_POINT and rm._jump_field(record):
                values.setdefault(input_id, []).append(float(record["value"]["measurements"][0]["value"]))
                continue
            field = rm._grade_field(input_id, record)
            if field == "grade":
                values.setdefault(input_id, []).append(float(record["value"]["grade"]))
            elif field == "display_grade":
                values.setdefault(input_id, []).append(float(record["value"]["display_grade"]["grade"]))
    spread = {k: round(st.pstdev(v), 4) for k, v in sorted(values.items()) if len(v) >= 30}
    technique = [v for k, v in spread.items() if not k.startswith("P")]
    reference = round(st.median(technique), 4)
    OUT.write_text(json.dumps({
        "description": "League standard deviation of each input development moves (opening 2026-27 league). "
                       "Built by scripts/research/dev_curve_spread.py; read by ratings_model.route_trait_deltas.",
        "players": len(league), "reference": reference, "spread": spread}, indent=1) + "\n")
    physical = {k: v for k, v in spread.items() if k.startswith("P")}
    print(f"{len(spread)} inputs, reference {reference}; physical {physical}; "
          f"technique range {min(technique):.1f}-{max(technique):.1f}")


if __name__ == "__main__":
    main()
