#!/usr/bin/env python3
"""Build data.json for the new player card mockup (design_concepts/new_player_card).

Reads the canonical player inputs, the universe file and the registry; writes
design_concepts/new_player_card/data.json for three contrasting players.

Provisional OVR / OFF / DEF method: see the docstring of nba_gm_data.player_profile (shared with the game).
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from nba_gm_data import ratings_model  # noqa: E402
from nba_gm_data.player_profile import (  # noqa: E402
    GROUP_OF, layer_of, league_reference, pct_of,
)

UNIVERSE = ROOT / "data/canonical/universe_2026_27_offseason.json"
OUT = ROOT / "design_concepts/new_player_card/data.json"
FEATURED = ["player_bos-jayson-tatum", "player_min-rudy-gobert", "player_cha-kon-knueppel"]


def main():
    inputs_key, league_inputs = ratings_model._load_inputs_keyed(ROOT)
    ref = league_reference(inputs_key, league_inputs)
    reg, ex, pct, pos_avg = ref["reg"], ref["ex"], ref["pct"], ref["pos_avg"]
    pids, positions = ref["pids"], ref["positions"]
    assert len(reg) == 94, len(reg)
    uni = {p["id"]: p for p in json.load(open(UNIVERSE))["players"]}
    prov = ref["display"]
    league_stats = ref["league"]

    inputs_meta = []
    for iid, m in reg.items():
        inputs_meta.append({"id": iid, "name": m["name"], "kind": m["kind"], "units": m["units"],
                            "outcomes": m["outcomes"], "meaning": m["meaning"],
                            "layer": layer_of(iid), "group": GROUP_OF.get(iid)})

    players = []
    for pid in FEATURED:
        u = uni[pid]
        rec = []
        for iid in reg:
            e = ex[pid][iid]
            row = {"id": iid, "kind": e["kind"], "evidence": e["evidence"], "value": e["value"]}
            for k in ("interval", "intervals", "unit", "protocol"):
                if e.get(k) is not None:
                    row[k] = e[k]
            row["pct"] = None if e["kind"] == "distribution" else round(pct[pid][iid], 1)
            row["pos_avg"] = pos_avg[u["position"]][iid]
            if e["kind"] == "measure":
                # Bars for measurements are drawn on the league percentile scale.
                row["pos_avg_pct"] = round(pct_of(ref, iid, row["pos_avg"]), 1)
                if row.get("interval"):
                    row["interval_pct"] = [round(pct_of(ref, iid, x), 1) for x in row["interval"]]
            rec.append(row)
        players.append({
            "id": pid, "name": u["name"], "team": u["team_abbrev"], "position": u["position"],
            "age": u["age"], "height_inches": u["height_inches"], "weight_lbs": u["weight_lbs"],
            "wingspan_inches": u["wingspan_inches"], "headshot_url": u.get("headshot_url"),
            "minutes_projection": u["minutes_projection"], "primary_off_role": u["primary_off_role"],
            "secondary_off_role": u["secondary_off_role"], "primary_def_role": u["primary_def_role"],
            "rotation_priority": u["rotation_priority"],
            "provisional": {k: round(v, 1) for k, v in prov[pid].items()},
            "inputs": rec,
        })

    OUT.parent.mkdir(parents=True, exist_ok=True)
    json.dump({"inputs": inputs_meta, "players": players, "league": league_stats,
               "positions": positions}, open(OUT, "w"), separators=(",", ":"))

    # Console summary.
    for p in players:
        lay = {1: [0, 0], 2: [0, 0], 3: [0, 0]}
        for r in p["inputs"]:
            L = layer_of(r["id"])
            lay[L][1] += 1
            lay[L][0] += r["evidence"] == "player"
        print(p["name"], p["provisional"], {f"L{k}": f"{a}/{b} from player data" for k, (a, b) in lay.items()})
    print("league max display:", {k: round(v, 1) for k, v in league_stats.items()})


if __name__ == "__main__":
    main()
