#!/usr/bin/env python3
"""ROOKIE-SEASON: card overall, impact and shot profile of every player, for a before/after diff (measurement only).

Run once with --old (the old shooting-range fallback for players without an NBA shooting record) and once without,
then compare the two JSON files with --diff.

    PYTHONPATH=src .venv/bin/python scripts/research/rookie_profile_effect.py SAVE --old --out old.json
    PYTHONPATH=src .venv/bin/python scripts/research/rookie_profile_effect.py SAVE --out new.json
    python3 scripts/research/rookie_profile_effect.py --diff old.json new.json
"""
from __future__ import annotations

import argparse
import json
import statistics
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))


def snapshot(save_path: Path, old: bool) -> dict:
    from nba_gm_data import offense
    if old:
        offense.INPUT_SHOT_VOLUME = False
    from nba_gm_data.app_actions import load_app_canonical
    from nba_gm_data.save import canonical_with_save, load_save
    from nba_gm_data.player_profile import engine_header
    from nba_gm_data.sim import player_feature_vector
    save = load_save(save_path)
    active = canonical_with_save(load_app_canonical(ROOT), save)
    out = {}
    for p in active["players"]:
        if p.get("_inactive_player") or not p.get("team_id"):
            continue
        head = engine_header(active, p["id"]) or {}
        feat = player_feature_vector(active, p).features
        out[p["id"]] = {"name": p.get("name"), "rookie": str(p.get("draft_year")) == "2026",
                        "has_record": p["id"] in active.get("meta", {}).get("offensive_profiles", {}),
                        "ovr": head.get("ovr"), "impact": (head.get("impact") or {}).get("ovr"),
                        "off": head.get("off"), "def": head.get("def"),
                        "three_per36": feat.get("three_per36"), "three_pct": feat.get("three_pct"),
                        "points_per36": feat.get("points_per36"), "spacing": feat.get("spacing")}
    return out


def diff(a: dict, b: dict) -> None:
    for label, pick in (("2026 rookies", lambda r: r["rookie"]),
                        ("others without a full record", lambda r: not r["rookie"] and not r["has_record"]),
                        ("veterans with a record", lambda r: r["has_record"])):
        ids = [pid for pid in a if pid in b and pick(a[pid])]
        if not ids:
            continue
        print(f"{label} ({len(ids)})")
        for key in ("ovr", "impact", "three_per36", "three_pct", "points_per36", "spacing"):
            d = [float(b[i][key] or 0) - float(a[i][key] or 0) for i in ids if a[i].get(key) is not None]
            if d:
                print(f"  {key:13s} mean change {statistics.fmean(d):+.3f}  largest {max(d, key=abs):+.3f}")
    rook = sorted((pid for pid in a if a[pid]["rookie"] and pid in b), key=lambda pid: -float(b[pid]["ovr"] or 0))
    print("\nrookies: overall old -> new, threes per 36, points per 36")
    for pid in rook[:30]:
        x, y = a[pid], b[pid]
        print(f"  {x['name'][:24]:24s} ovr {x['ovr']} -> {y['ovr']}  impact {x['impact']} -> {y['impact']}  "
              f"3PA/36 {x['three_per36']:.2f} -> {y['three_per36']:.2f}  3P% {x['three_pct']:.3f} -> {y['three_pct']:.3f}  "
              f"pts/36 {x['points_per36']:.1f} -> {y['points_per36']:.1f}")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("save", type=Path, nargs="?")
    parser.add_argument("--old", action="store_true")
    parser.add_argument("--out", type=Path)
    parser.add_argument("--diff", type=Path, nargs=2)
    args = parser.parse_args()
    if args.diff:
        diff(json.loads(args.diff[0].read_text()), json.loads(args.diff[1].read_text()))
        return
    args.out.write_text(json.dumps(snapshot(args.save, args.old)))


if __name__ == "__main__":
    main()
