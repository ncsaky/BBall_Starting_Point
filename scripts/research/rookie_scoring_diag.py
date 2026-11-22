#!/usr/bin/env python3
"""ROOKIE-SEASON: why do the best simulated rookies score less per minute than real ones? (measurement only)

Reads a finished probe save (scripts/research/rookie_season_probe.py) and, for every player with 500+ simulated
minutes, compares:
  fit     his points-per-36 feature (box_rates.POINTS_INPUTS on his inputs; the engine's expected scoring rate)
  sim     his simulated season points per 36
  real    his real points per 36 (2026-27 so far for rookies; 2025-26 for everyone else, Basketball Reference)
and his involvement tendency (T08) against his real usage rate.

    PYTHONPATH=src .venv/bin/python scripts/research/rookie_scoring_diag.py output/rookie-fit-2/season_v2_s17
"""
from __future__ import annotations

import argparse
import json
import statistics
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "scripts" / "research"))

import real_prospects as rp  # noqa: E402
from nba_gm_data.app_actions import load_app_canonical  # noqa: E402
from nba_gm_data.save import canonical_with_save, load_save  # noqa: E402
from nba_gm_data.sim import player_feature_vector  # noqa: E402
from nba_gm_data.ratings_model import effective_inputs  # noqa: E402
from nba_gm_data import box_rates  # noqa: E402

LINES = ROOT / "data/research/rookie_real_lines.json"


def real_2026_lines() -> dict[str, dict]:
    """2025-26 season per-36 points and usage for every player (Basketball Reference advanced + totals pages)."""
    import rookie_real_lines as rl
    adv = rl.advanced(2026)
    out = {}
    text = (rl.PAGES / "NBA_2026_totals.html").read_text(encoding="utf-8", errors="replace")
    for row in rl.table(text, "totals_stats"):
        pid = row.get("_id")
        if not pid or not row.get("mp", "").isdigit():
            continue
        if pid in out:
            continue   # the first row is the season total for a traded player
        mp = float(row["mp"])
        a = adv.get(pid) or {}
        out[rp.name_key(row.get("name_display") or a.get("name") or "")] = {
            "mp": mp, "pts": float(row.get("pts") or 0), "usg": a.get("usg_pct"), "ts": a.get("ts_pct")}
    return out


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("probe_dir", type=Path)
    parser.add_argument("--json", type=Path)
    args = parser.parse_args()
    save = load_save(args.probe_dir / "saves/league.json")
    canonical = load_app_canonical(ROOT)
    active = canonical_with_save(canonical, save)
    stats = save.get("player_season_stats", {})
    real_old = real_2026_lines()
    lines = json.loads(LINES.read_text())
    real_new = {rp.name_key(r["name"]): r for r in lines["season_2027"]["rookies"]}
    rows = []
    for p in active["players"]:
        s = stats.get(p["id"]) or {}
        minutes = float(s.get("minutes") or 0)
        if minutes < 500:
            continue
        feat = player_feature_vector(active, p).features
        inputs = effective_inputs(active, p["id"]) or {}
        t08 = box_rates.tendency_from_inputs(inputs, "T08")
        rookie = str(p.get("draft_year")) == "2026"
        key = rp.name_key(p.get("name") or "")
        real = real_new.get(key) if rookie else real_old.get(key)
        real_p36 = real_usg = None
        if real:
            mp = real.get("mp") or 0
            if mp >= 200:
                real_p36 = 36 * real["pts"] / mp
                real_usg = real.get("usg_pct", real.get("usg"))
        rows.append({"name": p.get("name"), "team": p.get("team_abbrev"), "rookie": rookie, "age": p.get("age"),
                     "fit": feat.get("points_per36"), "sim": 36 * float(s.get("points") or 0) / minutes,
                     "mpg": minutes / max(1, float(s.get("games") or 1)), "t08": t08, "real_p36": real_p36,
                     "real_usg": real_usg})
    def show(title, subset):
        print(f"\n{title} ({len(subset)})")
        print(f"  {'name':22s} {'team':4s} {'mpg':>5s} {'T08':>6s} {'fit':>5s} {'sim':>5s} {'real':>5s} {'usg':>5s}")
        for r in subset:
            print(f"  {r['name'][:22]:22s} {str(r['team'])[:4]:4s} {r['mpg']:5.1f} {r['t08'] or 0:6.3f} {r['fit'] or 0:5.1f} "
                  f"{r['sim']:5.1f} {r['real_p36'] or 0:5.1f} {r['real_usg'] or 0:5.1f}")
    rookies = sorted([r for r in rows if r["rookie"]], key=lambda r: -(r["real_p36"] or 0))
    show("rookies (500+ simulated minutes), by real points per 36", rookies)
    vets = [r for r in rows if not r["rookie"] and r["real_p36"] and r["fit"]]
    # How the fit and the simulation track real scoring, by bands of real points per 36.
    print("\nveterans: real points per 36 band -> mean fit / sim / real")
    for lo, hi in ((0, 12), (12, 16), (16, 20), (20, 24), (24, 40)):
        band = [r for r in vets if lo <= r["real_p36"] < hi]
        if band:
            print(f"  {lo:2d}-{hi:2d}: n {len(band):3d} fit {statistics.fmean(r['fit'] for r in band):5.1f} "
                  f"sim {statistics.fmean(r['sim'] for r in band):5.1f} real {statistics.fmean(r['real_p36'] for r in band):5.1f}")
    print("\nveterans: real usage band -> mean T08 / fit / sim / real points per 36")
    for lo, hi in ((0, 16), (16, 20), (20, 24), (24, 28), (28, 40)):
        band = [r for r in vets if r["real_usg"] and lo <= r["real_usg"] < hi]
        if band:
            print(f"  usage {lo:2d}-{hi:2d}: n {len(band):3d} T08 {statistics.fmean(r['t08'] or 0 for r in band):.3f} "
                  f"fit {statistics.fmean(r['fit'] for r in band):5.1f} sim {statistics.fmean(r['sim'] for r in band):5.1f} "
                  f"real {statistics.fmean(r['real_p36'] for r in band):5.1f}")
    rk = [r for r in rookies if r["real_p36"] and r["real_usg"]]
    print("\nrookies with real lines: real usage band -> mean T08 / fit / sim / real points per 36")
    for lo, hi in ((0, 16), (16, 20), (20, 24), (24, 28), (28, 40)):
        band = [r for r in rk if lo <= r["real_usg"] < hi]
        if band:
            print(f"  usage {lo:2d}-{hi:2d}: n {len(band):3d} T08 {statistics.fmean(r['t08'] or 0 for r in band):.3f} "
                  f"fit {statistics.fmean(r['fit'] for r in band):5.1f} sim {statistics.fmean(r['sim'] for r in band):5.1f} "
                  f"real {statistics.fmean(r['real_p36'] for r in band):5.1f}")
    if args.json:
        args.json.write_text(json.dumps(rows, indent=1))


if __name__ == "__main__":
    main()
