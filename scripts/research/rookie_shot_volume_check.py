#!/usr/bin/env python3
"""ROOKIE-SEASON: can a player's three-point volume come from his inputs when he has no NBA shooting record?

Players without two seasons of NBA shooting history (every rookie) get their three-point attempts per 36 from an old
formula on the shooting-range rating (offense.offensive_profile fallback): about 2-3 a game for this year's top
rookie guards against 9 real (Acuff). This compares, for veterans WITH a record, their real attempts per 36 with
  old       the fallback formula (what a rookie gets);
  inputs    his shot-location habit (T02 three share) times the field-goal attempts his fitted points per 36 imply at
            his shooting percentages (offense.input_three_volume).
and the same for real three-point percentage (old fallback vs the three-point grade as he shoots, S.three_mode).

    PYTHONPATH=src .venv/bin/python scripts/research/rookie_shot_volume_check.py output/rookie-fit-2/season_v2_s17
"""
from __future__ import annotations

import argparse
import statistics
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from nba_gm_data.app_actions import load_app_canonical  # noqa: E402
from nba_gm_data.save import canonical_with_save, load_save  # noqa: E402
from nba_gm_data.ratings_model import effective_inputs  # noqa: E402
from nba_gm_data.sim import canonical_sim_cache  # noqa: E402
from nba_gm_data import box_rates, offense  # noqa: E402


def corr(xs, ys):
    mx, my = statistics.fmean(xs), statistics.fmean(ys)
    sxy = sum((x - mx) * (y - my) for x, y in zip(xs, ys))
    sxx = sum((x - mx) ** 2 for x in xs)
    syy = sum((y - my) ** 2 for y in ys)
    return sxy / (sxx * syy) ** 0.5


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("probe_dir", type=Path)
    args = parser.parse_args()
    save = load_save(args.probe_dir / "saves/league.json")
    active = canonical_with_save(load_app_canonical(ROOT), save)
    priors = active.get("meta", {}).get("offensive_profiles", {})
    cache = canonical_sim_cache(active)
    rows = []
    rookies = []
    for p in active["players"]:
        prior = priors.get(p["id"]) or {}
        traits = {k: float(v["value"]) for k, v in cache["traits_by_player"].get(p["id"], {}).items()}
        inputs = effective_inputs(active, p["id"])
        if not inputs or not traits:
            continue
        bare = {**active, "meta": {**active.get("meta", {}), "offensive_profiles": {}}}
        offense.INPUT_SHOT_VOLUME = False
        old = offense.offensive_profile(bare, p, traits)
        offense.INPUT_SHOT_VOLUME = True
        est = offense.input_three_volume(inputs, old)
        if est is None:
            continue
        if str(p.get("draft_year")) == "2026":
            rookies.append((p["name"], old["three_per36"], est, old["three_pct"], old["three_pct"]))
        if prior.get("volume_weight", 0) < 0.9 or "three_pct" not in prior:
            continue
        rows.append({"name": p["name"], "real": prior["three_per36"], "old": old["three_per36"], "new": est,
                     "real_pct": prior["three_pct"], "old_pct": old["three_pct"], "new_pct": old["three_pct"],
                     "grade": box_rates._flat(inputs).get("S.three_mode"), "att": prior["three_per36"]})
    # Three-point percentage on the three-point grade as he shoots it, weighted by attempts (players who shoot).
    fit_rows = [r for r in rows if r["grade"] is not None and r["att"] >= 2]
    w = [r["att"] for r in fit_rows]
    mx = sum(r["grade"] * wi for r, wi in zip(fit_rows, w)) / sum(w)
    my = sum(r["real_pct"] * wi for r, wi in zip(fit_rows, w)) / sum(w)
    b = (sum(wi * (r["grade"] - mx) * (r["real_pct"] - my) for r, wi in zip(fit_rows, w))
         / sum(wi * (r["grade"] - mx) ** 2 for r, wi in zip(fit_rows, w)))
    print(f"three-point percentage on grade (2+ attempts per 36, {len(fit_rows)} players): "
          f"{my - b * mx:.4f} + {b:.5f} x grade; r {corr([r['grade'] for r in fit_rows], [r['real_pct'] for r in fit_rows]):.3f}")
    print(f"veterans with a full NBA shooting record: {len(rows)}")
    for key, label in (("old", "old fallback"), ("new", "from inputs")):
        err = [r[key] - r["real"] for r in rows]
        print(f"  three attempts per 36, {label:13s}: r {corr([r[key] for r in rows], [r['real'] for r in rows]):.3f} "
              f"mean miss {statistics.fmean(abs(e) for e in err):.2f}, bias {statistics.fmean(err):+.2f} "
              f"(real mean {statistics.fmean(r['real'] for r in rows):.2f})")
        hi = [r for r in rows if r["real"] >= 7]
        print(f"    real 7+ a 36 ({len(hi)}): mean {label} {statistics.fmean(r[key] for r in hi):.2f} "
              f"vs real {statistics.fmean(r['real'] for r in hi):.2f}")
    for key, label in (("old_pct", "old fallback"), ("new_pct", "from inputs")):
        err = [r[key] - r["real_pct"] for r in rows]
        print(f"  three-point percentage, {label:13s}: r {corr([r[key] for r in rows], [r['real_pct'] for r in rows]):.3f} "
              f"mean miss {statistics.fmean(abs(e) for e in err):.3f}, bias {statistics.fmean(err):+.3f}")
    print("\n2026 rookies: three attempts per 36 old -> inputs, percentage old -> inputs")
    for name, o, n, op, np_ in sorted(rookies, key=lambda r: -r[2])[:20]:
        print(f"  {name[:24]:24s} {o:5.2f} -> {n:5.2f}   {op:.3f} -> {np_:.3f}")


if __name__ == "__main__":
    main()
