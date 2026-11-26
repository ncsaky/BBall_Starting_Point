#!/usr/bin/env python3
"""Compact NBA.com's 2025-26 play-type tables (Synergy, offense, per player) into the tracked evidence file.

Reads the raw responses saved in output/ratings-evidence/nba_playtypes_2026/ (git-ignored; see SOURCE.md there) and
writes data/research/nba_synergy_playtypes_2025_26.json: per player (canonical id, joined by name against the universe) and
play type, possessions, points, field goals and the possessions that ended in free throws, summed over the teams he
played for. Also each player's total possessions across all play types (NBA.com's own possession share: possessions /
POSS_PCT, read from his largest play type).

    PYTHONPATH=src .venv/bin/python -I scripts/research/compact_nba_playtypes.py
"""
from __future__ import annotations

import json
import sys
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))
RAW = ROOT / "output/ratings-evidence/nba_playtypes_2026"
OUT = ROOT / "data/research/nba_synergy_playtypes_2025_26.json"
UNIVERSES = ("data/canonical/universe_2026_27_offseason.json", "data/canonical/universe_2025_26_preseason.json")
PLAY_TYPES = ("Transition", "Isolation", "PRBallHandler", "PRRollman", "Postup", "Spotup", "Handoff", "Cut",
              "OffScreen", "OffRebound", "Misc")


def main() -> None:
    from nba_gm_data.input_estimator import _normalize
    ids: dict[str, str] = {}
    for rel in UNIVERSES:
        for p in json.loads((ROOT / rel).read_text())["players"]:
            ids.setdefault(_normalize(p["name"]), p["id"])
    meta = json.loads((RAW / "fetch_meta.json").read_text())
    players: dict[str, dict] = defaultdict(lambda: {"name": None, "nba_id": None, "teams": set(), "types": {},
                                                    "total_poss": 0.0, "_ref": 0.0})
    for pt in PLAY_TYPES:
        rs = json.loads((RAW / f"synergy_{pt}_offensive_2025-26.json").read_text())["resultSets"][0]
        for row in rs["rowSet"]:
            r = dict(zip(rs["headers"], row))
            key = str(r["PLAYER_ID"])
            p = players[key]
            p["name"], p["nba_id"] = r["PLAYER_NAME"], r["PLAYER_ID"]
            p["teams"].add(r["TEAM_ABBREVIATION"])
            poss = float(r["POSS"] or 0)
            t = p["types"].setdefault(pt, [0.0, 0.0, 0.0, 0.0, 0.0])   # poss, pts, fgm, fga, ft_poss
            t[0] += poss
            t[1] += float(r["PTS"] or 0)
            t[2] += float(r["FGM"] or 0)
            t[3] += float(r["FGA"] or 0)
            t[4] += poss * float(r["FT_POSS_PCT"] or 0)
            # One row per player-team: per team, total possessions = poss / share. Players traded mid-season appear
            # once per team, so their total is summed over teams from each team's largest play type.
            p.setdefault("_team_ref", {})
            ref = p["_team_ref"].get(r["TEAM_ABBREVIATION"])
            if r["POSS_PCT"] and (ref is None or poss > ref[0]):
                p["_team_ref"][r["TEAM_ABBREVIATION"]] = (poss, poss / float(r["POSS_PCT"]))
    out, unmatched = {}, []
    for key, p in players.items():
        total = sum(v[1] for v in p.pop("_team_ref", {}).values())
        cid = ids.get(_normalize(p["name"]))
        if cid is None:   # suffix differences ("Bobby Portis Jr." vs "Bobby Portis")
            bare = _normalize(p["name"].replace(" Jr.", "").replace(" Sr.", "").replace(" III", "").replace(" II", ""))
            cid = ids.get(bare) or next((v for k, v in ids.items() if k.startswith(bare) and len(k) - len(bare) <= 3), None)
        rec = {"name": p["name"], "nba_id": p["nba_id"], "teams": sorted(p["teams"]), "total_poss": round(total, 1),
               "types": {k: [round(x, 2) for x in v] for k, v in sorted(p["types"].items())}}
        if cid:
            out[cid] = rec
        else:
            unmatched.append(p["name"])
    payload = {
        "source": "NBA.com stats API, Synergy play types (https://stats.nba.com/stats/synergyplaytypes), the endpoint the "
                  "public pages https://www.nba.com/stats/players/<playtype> call",
        "season": "2025-26", "season_type": "Regular Season", "type_grouping": "offensive", "per_mode": "Totals",
        "fetched_at": meta["fetched_at"], "urls": meta["urls"],
        "columns": {"types": ["possessions", "points", "fgm", "fga", "possessions ending in free throws"],
                    "total_poss": "possessions across all play types, from NBA.com's possession share of each team's "
                                  "largest play type, summed over teams"},
        "qualifier": "NBA.com lists a player in a play type only with 10+ possessions of it; absent means fewer, not zero",
        "raw_copy": "output/ratings-evidence/nba_playtypes_2026/ (git-ignored)",
        "unmatched": sorted(unmatched),
        "players": dict(sorted(out.items())),
    }
    OUT.write_text(json.dumps(payload, indent=0, ensure_ascii=False) + "\n")
    print(f"{len(out)} players matched, {len(unmatched)} unmatched -> {OUT.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
