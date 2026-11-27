#!/usr/bin/env python3
"""Do injury names agree with how long players are out, and how many games does a season of injuries cost?

Two measurements of the injury model the game uses (INJURY-NAMES, 2026-11-26):

  --draws N   N recoveries per body part from injury_model.sample_recovery: games missed by diagnosis (5th, 50th and
              95th percentile, longest), long absences with minor-sounding names, serious injuries over in a few games,
              and the mean games missed per injury (weighted by how often each part is hurt in the real records).
  --seasons K K seeded runs of --years regular seasons through health.simulate_health (generated schedules, fixed
              rosters, injuries carried over): injuries, games they cost, long and carried-over absences.

    PYTHONPATH=src .venv/bin/python scripts/research/injury_diagnosis_check.py [--draws 100000] [--seasons 8 --years 3] [--json OUT]
"""
from __future__ import annotations

import argparse
import json
import random
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path
from statistics import mean

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))
from nba_gm_data import health, save  # noqa: E402
from nba_gm_data import injury_model as im  # noqa: E402
from nba_gm_data.app_actions import load_app_canonical  # noqa: E402

# Names a fan reads as a knock or an ordinary ailment: none should keep a player out half a season.
MINOR = re.compile(r"contusion|bruise$|soreness|unspecified|spasms|^illness|^flu|headache|tightness|conditioning|rest$"
                   r"|^[a-z ]+ injury$|^[a-z ]+ illness$", re.I)
# Names a fan reads as serious: none should be over in a handful of games (dental work and face or finger fractures,
# played through behind a mask or tape, aside).
SERIOUS = re.compile(r"^(?!dental|nose|orbital|head|finger).*(ACL tear|rupture|surgery|fracture|meniscus tear|tendon tear)", re.I)
LONG_GAMES = 40
SHORT_GAMES = 5


def pct(values: list[int], q: float) -> int:
    return values[min(len(values) - 1, int(q * len(values)))]


def draws(n: int, seed: int) -> dict:
    model = im.load_model(ROOT)
    by_label: dict[str, list[int]] = defaultdict(list)
    per_part, long_minor, long_total, short_serious, serious_total = {}, 0.0, 0.0, 0.0, 0.0
    weights = {part: info["anchor_per_1000_games"] for part, info in model["parts"].items()}
    total_weight = sum(weights.values())
    for part in sorted(weights):
        rng = random.Random(f"{seed}:{part}")
        games = []
        w = weights[part] / total_weight / n
        for _ in range(n):
            case = im.sample_recovery(ROOT, part, rng)
            g = int(case["days"]) // 2
            games.append(g)
            by_label[case["label"]].append(g)
            if g >= LONG_GAMES:
                long_total += w
                long_minor += w if MINOR.search(case["label"]) else 0.0
            if SERIOUS.search(case["label"]):
                serious_total += w
                short_serious += w if g < SHORT_GAMES else 0.0
        games.sort()
        costing = [g for g in games if g >= 1]
        per_part[part] = {"weight": weights[part] / total_weight, "mean_games": round(mean(games), 3),
                          "cost_share": round(len(costing) / n, 4),
                          "p50": pct(games, .5), "p90": pct(games, .9), "p99": pct(games, .99), "max": games[-1],
                          "share_over_10": round(sum(g > 10 for g in games) / n, 4),
                          "share_over_20": round(sum(g > 20 for g in games) / n, 4),
                          "share_40_plus": round(sum(g >= 40 for g in games) / n, 5),
                          "share_82_plus": round(sum(g >= 82 for g in games) / n, 5)}
    labels = {}
    for label, games in by_label.items():
        games.sort()
        labels[label] = {"n": len(games), "min": games[0], "p5": pct(games, .05), "p50": pct(games, .5),
                         "p95": pct(games, .95), "max": games[-1]}
    league = {key: round(sum(v[key] * v["weight"] for v in per_part.values()), 4)
              for key in ("mean_games", "cost_share", "share_over_10", "share_over_20", "share_40_plus", "share_82_plus")}
    league["long_with_minor_name"] = round(long_minor / long_total, 4) if long_total else 0.0
    league["serious_name_under_5_games"] = round(short_serious / serious_total, 4) if serious_total else 0.0
    return {"league": league, "parts": per_part, "labels": labels}


def seasons(k: int, seed: int, years: int) -> dict:
    """k seeded runs of `years` seasons back to back (fixed rosters, nobody ages; injuries and absences carry over)."""
    canonical = load_app_canonical(ROOT)
    names = {p["id"]: p["name"] for p in canonical["players"]}
    schedules = [save.generate_future_schedule(ROOT, f"{y}-{str(y + 1)[2:]}", y)["games"] for y in range(2026, 2026 + years)]
    rows, examples = [], []
    for i in range(k):
        canonical["player_health_states"], canonical["injury_events"] = [], []
        missed_before = 0
        for year, games in enumerate(schedules):
            start = 2026 + year
            last_day = max(str(g["gameDate"])[:10] for g in games)
            r = health.simulate_health(ROOT, canonical, games[0]["gameDate"], games[-1]["gameDate"], seed=seed + 1000 * year + i,
                                       schedule=games, season_schedule=games)
            ev = r["events"]
            canonical["player_health_states"] = r["final_states"]
            canonical["injury_events"] = canonical["injury_events"] + ev
            missed = sum(int(s.get("games_missed") or 0) for s in r["final_states"])
            cost = [e for e in ev if int(e.get("expected_days_missed") or 0) >= 2]
            long = [e for e in cost if int(e["expected_games_missed"]) >= LONG_GAMES]
            rows.append({
                "season": year + 1, "injuries": len(ev), "injuries_costing_a_game": len(cost),
                "games_missed_in_season": missed - missed_before,
                "games_reported": sum(int(e.get("expected_games_missed") or 0) for e in ev),
                "over_10_games": sum(int(e["expected_games_missed"]) > 10 for e in cost),
                "40_plus": len(long), "40_plus_minor_name": sum(bool(MINOR.search(e["diagnosis"])) for e in long),
                "serious_name_under_5": sum(bool(SERIOUS.search(e["diagnosis"]))
                                            and int(e.get("expected_games_missed") or 0) < SHORT_GAMES for e in ev),
                "acl_or_achilles_tears": sum(e["diagnosis"] in ("ACL tear", "Achilles tendon rupture") for e in ev),
                "lasting_effect_injuries": sum(bool(im.lasting_trait_deltas(e)) for e in ev),
                "out_past_season": sum(str(e["return_date"]) > last_day for e in ev),
                "back_after_november_1": sum(str(e["return_date"]) > f"{start + 1}-11-01" for e in ev),
                "out_two_summers": sum(str(e["return_date"]) >= f"{start + 2}-01-01" for e in ev),
                "longest_reported_games": max((int(e.get("expected_games_missed") or 0) for e in ev), default=0),
            })
            missed_before = missed
            if i == 0 and year == 0:
                examples = [(names.get(e["player_id"]), e["diagnosis"], int(e["expected_games_missed"]), e["return_date"])
                            for e in sorted(long, key=lambda e: -int(e["expected_games_missed"]))]
    by_season = {str(y): {key: round(mean(row[key] for row in rows if row["season"] == y), 2) for key in rows[0] if key != "season"}
                 for y in range(1, years + 1)}
    overall = {key: round(mean(row[key] for row in rows), 2) for key in rows[0] if key != "season"}
    return {"runs": k, "years": years, "first_seed": seed, "mean": overall, "by_season": by_season, "rows": rows,
            "long_examples": examples}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--draws", type=int, default=100_000, help="recoveries per body part (0 skips)")
    ap.add_argument("--seasons", type=int, default=0, help="seeded runs of full-season replays (0 skips)")
    ap.add_argument("--years", type=int, default=1, help="seasons back to back in each run")
    ap.add_argument("--seed", type=int, default=2026)
    ap.add_argument("--json", help="write everything here")
    ap.add_argument("--labels", action="store_true", help="print the games range of every diagnosis")
    a = ap.parse_args()
    out = {}
    if a.draws:
        out["draws"] = draws(a.draws, a.seed)
        league = out["draws"]["league"]
        print("per injury (parts weighted by the real records):", league)
        print("part          weight  mean  p50 p90 p99 max  >10    >20    40+")
        for part, v in sorted(out["draws"]["parts"].items(), key=lambda kv: -kv[1]["weight"]):
            print(f"{part:12s} {v['weight']:6.3f} {v['mean_games']:6.2f} {v['p50']:3d} {v['p90']:3d} {v['p99']:3d} {v['max']:3d} "
                  f"{v['share_over_10']:6.3f} {v['share_over_20']:6.3f} {v['share_40_plus']:7.4f}")
        if a.labels:
            print("diagnosis: draws, games min / 5th / 50th / 95th / max")
            for label, v in sorted(out["draws"]["labels"].items(), key=lambda kv: -kv[1]["n"]):
                print(f"  {label:38s} {v['n']:7d}  {v['min']:3d} {v['p5']:3d} {v['p50']:3d} {v['p95']:3d} {v['max']:3d}")
    if a.seasons:
        out["seasons"] = seasons(a.seasons, a.seed, a.years)
        print(f"{a.seasons} runs of {a.years} season(s), mean per season:", out["seasons"]["mean"])
        for year, row in out["seasons"]["by_season"].items():
            print(f"  season {year}:", row)
        for row in out["seasons"]["long_examples"][:15]:
            print("  ", row)
    if a.json:
        Path(a.json).parent.mkdir(parents=True, exist_ok=True)
        Path(a.json).write_text(json.dumps(out, indent=1) + "\n")


if __name__ == "__main__":
    main()
