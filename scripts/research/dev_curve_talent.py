"""Development-only probe: how the engine's own player value (fitted impact) moves with age, level and draft slot.

No games are played. The opening 2026-27 league (new ratings) plus two made-up draft classes (entering July 2027)
develop month by month through health.advance_development, exactly as a save does, with minutes reset each July
from league rank and ages advanced. Each June it records every player's fitted impact (points per 100 possessions,
Basketball Index LEBRON units: the value behind the player card's OVR) and his physical capacity grades.

It measures underlying ability, with no box-score noise, so its level table compares with the real table whose
starting third comes from the season before (dev_curve_box.py prior), not with same-season thirds.

    PYTHONPATH=src:scripts/research .venv/bin/python scripts/research/dev_curve_talent.py --out output/dev-curve/talent-before
"""
from __future__ import annotations

import argparse
import copy
import json
import statistics as st
import sys
import time
from collections import defaultdict
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts" / "research"))

PHYSICAL = ("P05", "P06", "P07", "P08", "P09", "P11", "P12")
NAMED = ("Victor Wembanyama", "Cooper Flagg", "AJ Dybantsa", "Chet Holmgren", "Shai Gilgeous-Alexander",
         "Nikola Jokic", "Nikola Jokić", "Luka Doncic", "Luka Dončić", "Giannis Antetokounmpo", "LeBron James",
         "Stephen Curry", "Darryn Peterson", "Cameron Boozer", "Ace Bailey", "Dylan Harper", "Stephon Castle",
         "Amen Thompson", "Anthony Edwards", "Jalen Williams", "Kevin Durant")


def grade(record: dict[str, Any] | None) -> float | None:
    value = (record or {}).get("value") or {}
    if "grade" in value:
        return float(value["grade"])
    display = value.get("display_grade") or {}
    return float(display["grade"]) if "grade" in display else None


def snapshot(ctx: dict[str, Any], players: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    from nba_gm_data import impact_value, ratings_model, save

    traits = save.trait_values_by_player(ctx)
    out = {}
    for p in players:
        impact = impact_value.player_impact(ctx, p, traits.get(p["id"]))
        if impact is None:
            continue
        inputs = ratings_model.effective_inputs(ctx, p["id"]) or {}
        out[p["id"]] = {"age": float(p["age"]), "minutes": float(p.get("minutes_projection") or 0.0),
                        "impact": round(impact["overall"], 3), "offense": round(impact["offense"], 3),
                        "defense": round(impact["defense"], 3),
                        "physical": {k: grade(inputs.get(k)) for k in PHYSICAL},
                        "stamina": round(float(traits.get(p["id"], {}).get("stamina_cardio", 0.0)), 2)}
    return out


def assign_minutes(players: list[dict[str, Any]], last: dict[str, dict[str, Any]], minutes_by_rank: list[float],
                   rookies: set[str]) -> None:
    order = sorted((p for p in players if p["id"] in last), key=lambda p: -last[p["id"]]["impact"])
    for rank, p in enumerate(order):
        lo, hi = max(0, rank - 10), min(len(minutes_by_rank), rank + 11)
        minutes = float(st.median(minutes_by_rank[lo:hi] or [0.0]))
        p["minutes_projection"] = round(minutes, 1)
        p["rotation_priority"] = ("development_priority" if p["id"] in rookies
                                  else "core_rotation" if minutes >= 26 else "rotation" if minutes >= 16
                                  else "deep_rotation" if minutes >= 8 else "fringe")


def run(seasons: int, seed: int, classes: list[int], class_seeds: list[int]) -> dict[str, Any]:
    import prospect_realism as pr
    from nba_gm_data import health, ratings_model, save

    started = time.time()
    league, generated = pr.build_generated("inputs", classes, class_seeds)
    entry_year = {r["id"]: int(r["year"]) for r in generated}
    pick = {r["id"]: int(r["pick"]) for r in generated}
    players = [p for p in league["players"] if p.get("team_id") and p.get("age") is not None]
    for p in players:
        if p["id"] not in entry_year and p.get("overall_pick"):
            pick.setdefault(p["id"], int(p["overall_pick"]))
    ids = {p["id"] for p in players}
    ctx = {k: league[k] for k in ("meta", "teams", "staff_profiles", "gameplay_staff_slots")}
    ctx["players"] = [copy.deepcopy(p) for p in players]
    ctx["traits"] = [dict(t) for t in league["traits"] if t["player_id"] in ids]
    ctx["player_health_states"] = []
    model = league[ratings_model.MODEL_KEY]
    ctx[ratings_model.MODEL_KEY] = {**model, "input_deltas": {}, "generated": dict(model.get("generated", {}))}
    by_id = {p["id"]: p for p in ctx["players"]}
    real = [p for p in ctx["players"] if p["id"] not in entry_year]
    opening = snapshot(ctx, real)
    minutes_by_rank = sorted((float(p.get("minutes_projection") or 0.0) for p in real), reverse=True)
    impacts_sorted = sorted((r["impact"] for r in opening.values()), reverse=True)
    history: dict[int, dict[str, dict[str, Any]]] = {2026: opening}
    print(f"loaded {len(ctx['players'])} players in {time.time() - started:.0f}s", flush=True)
    for season in range(2026, 2026 + seasons):
        active = [p for p in ctx["players"] if entry_year.get(p["id"], 0) <= season]
        rookies = {pid for pid, y in entry_year.items() if season - y < 2 and pick.get(pid, 99) <= 20}
        if season > 2026:
            for p in active:
                if p["id"] in history[season - 1]:
                    p["age"] = float(p["age"]) + 1
            # Rookies keep the minutes rookie_player_record gave them by draft slot in their first season.
            assign_minutes([p for p in active if p["id"] in history[season - 1]], history[season - 1],
                           minutes_by_rank, rookies)
        view = {**ctx, "players": active}
        for month in [f"{season}-{m:02d}" for m in range(7, 13)] + [f"{season + 1}-{m:02d}" for m in range(1, 7)]:
            events = health.advance_development(view, month, seed=seed)["events"]
            save.apply_development_events(ctx, events)
        history[season + 1] = snapshot(ctx, active)
        print(f"season {season}-{season + 1 - 2000:02d} done at {time.time() - started:.0f}s", flush=True)
    meta = {}
    for p in ctx["players"]:
        meta[p["id"]] = {"name": p.get("name"), "pick": pick.get(p["id"]), "entry": entry_year.get(p["id"]),
                         "generated": p["id"] in entry_year, "position": p.get("position")}
    return {"seed": seed, "seasons": seasons, "classes": classes, "class_seeds": class_seeds,
            "opening_impacts_sorted": impacts_sorted, "players": meta,
            "history": {str(k): v for k, v in history.items()}, "seconds": round(time.time() - started, 1)}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", required=True)
    parser.add_argument("--seasons", type=int, default=7)
    parser.add_argument("--seed", type=int, default=1)
    parser.add_argument("--classes", default="2027")
    parser.add_argument("--class-seeds", default="1,2")
    parser.add_argument("--params", help="JSON object of health/ratings_model constants to override (tuning)")
    args = parser.parse_args()
    if args.params:
        from nba_gm_data import health, ratings_model
        for key, value in json.loads(args.params).items():
            module = ratings_model if hasattr(ratings_model, key) else health
            if key == "INPUTS_AGE_FACTOR":
                value = tuple(tuple(p) for p in value)
            elif key == "INPUTS_DECLINE":
                value = {**health.INPUTS_DECLINE, **{k: tuple(v) for k, v in value.items()}}
            setattr(module, key, value)
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    result = run(args.seasons, args.seed, [int(y) for y in args.classes.split(",") if y],
                 [int(s) for s in args.class_seeds.split(",") if s])
    (out / f"talent_seed{args.seed}.json").write_text(json.dumps(result) + "\n")
    print(f"wrote {out}/talent_seed{args.seed}.json in {result['seconds']}s")


if __name__ == "__main__":
    main()
