"""Real versus generated draft prospects: entry level, growth and year-4 outcomes.

Shared helpers plus three commands:

    PYTHONPATH=src .venv/bin/python scripts/research/prospect_realism.py real
    PYTHONPATH=src .venv/bin/python scripts/research/prospect_realism.py generated [--seeds 1,2,3] [--years 2027,...]
    PYTHONPATH=src .venv/bin/python scripts/research/prospect_realism.py report

"real" reads the canonical 2026-27 league (players drafted 2019-2026 with their pick) in both rating sets, the
local Basketball Index growth history (2015-16 to 2025-26) and a Basketball-Reference draft list
(output/prospect-realism/real_drafts_2013_2023.csv, local only). "generated" builds generated draft classes the
way a save does (draft class -> rookie record -> rookie traits -> 94 inputs in the new ratings), then develops
them month by month for four seasons with health.advance_development. Results go to output/prospect-realism/.
"""
from __future__ import annotations

import argparse
import copy
import csv
import gzip
import json
import statistics as st
import sys
import time
from collections import Counter, defaultdict
from pathlib import Path
from types import SimpleNamespace
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "output" / "prospect-realism"
UNIVERSE = ROOT / "data" / "canonical" / "universe_2026_27_offseason.json"
BBI_HISTORY = ROOT / "data" / "research" / "bbi" / "tools" / "growth_history.csv.gz"
DRAFT_CSV = OUT / "real_drafts_2013_2023.csv"

PICK_RANGES = (("1-3", 1, 3), ("4-10", 4, 10), ("11-20", 11, 20), ("21-30", 21, 30), ("31-60", 31, 60))
# League-rank tiers. 30 teams: about one star per team is top 30; five starters per team is top 150;
# a ten-man rotation is top 300. Below the 450th player is roughly out of the league.
TIERS = (("star", 25), ("starter", 150), ("rotation", 300), ("bench", 450))
TIER_NAMES = ("star", "starter", "rotation", "bench", "out")

SKILL_GROUPS = {
    "shooting": [f"S{i:02d}" for i in range(1, 10)],
    "finishing": [f"S{i:02d}" for i in range(10, 16)],
    "creation": [f"S{i:02d}" for i in range(16, 21)],
    "playmaking": [f"F{i:02d}.{k}" for i in range(1, 10) for k in ("recognition", "execution")],
    "rebounding": [f"S{i:02d}" for i in range(29, 33)],
    "defense": [f"S{i:02d}" for i in range(33, 47)],
    "athletic_tools": ["P05", "P06", "P07", "P10"],
    "strength_tools": ["P08", "P09"],
}


def pick_range(pick: Any) -> str:
    try:
        pick = int(pick)
    except (TypeError, ValueError):
        return "undrafted"
    for name, low, high in PICK_RANGES:
        if low <= pick <= high:
            return name
    return "undrafted"


def tier_for_rank(rank: int | None) -> str:
    if rank is None:
        return "out"
    for name, limit in TIERS:
        if rank <= limit:
            return name
    return "out"


def q(values: list[float], *points: float) -> list[float | None]:
    values = sorted(v for v in values if v is not None)
    if not values:
        return [None for _ in points]
    out = []
    for p in points:
        idx = p * (len(values) - 1)
        lo, hi = int(idx), min(len(values) - 1, int(idx) + 1)
        out.append(round(values[lo] + (values[hi] - values[lo]) * (idx - lo), 2))
    return out


# ---------------------------------------------------------------------------------------------- game helpers

def load_league(mode: str) -> dict[str, Any]:
    from nba_gm_data import ratings_model

    league = json.loads(UNIVERSE.read_text())
    if mode == "inputs":
        ratings_model.install_inputs_model(league, ROOT)
    return league


NEUTRAL_MINUTES = 24.0


def card(league: dict[str, Any], pid: str) -> dict[str, float]:
    """Card offense/defense/overall at a neutral 24 minutes (the AI's role view), so workload never mixes in."""
    from nba_gm_data import save

    player = save.players_by_id_index(league)[pid]
    saved = player.get("minutes_projection")
    player["minutes_projection"] = NEUTRAL_MINUTES
    try:
        s = save.player_attribute_summary(league, pid)
    finally:
        player["minutes_projection"] = saved
    return {"overall": float(s["overall"]), "offense": float(s["offense"]), "defense": float(s["defense"])}


def input_groups(league: dict[str, Any], pid: str) -> dict[str, float]:
    from nba_gm_data import ratings_model

    inputs = ratings_model.effective_inputs(league, pid) or {}
    out = {}
    for group, ids in SKILL_GROUPS.items():
        grades = []
        for input_id in ids:
            value = (inputs.get(input_id) or {}).get("value") or {}
            grade = value.get("grade") if "grade" in value else (value.get("display_grade") or {}).get("grade")
            if grade is not None:
                grades.append(float(grade))
        out[group] = round(st.mean(grades), 2) if grades else None
    height = ((inputs.get("P01") or {}).get("value") or {}).get("measurements") or []
    out["height_cm"] = round(st.mean(height[0]["interval"]), 1) if height else None
    return out


def league_thresholds(league: dict[str, Any]) -> dict[str, Any]:
    """OVR at each tier cut in the opening real league, plus a minutes-by-OVR map."""
    rows = []
    for p in league["players"]:
        if p.get("team_id"):
            rows.append((card(league, p["id"])["overall"], float(p.get("minutes_projection") or 0)))
    rows.sort(key=lambda r: -r[0])
    overall = [r[0] for r in rows]
    cuts = {name: overall[min(limit, len(overall)) - 1] for name, limit in TIERS}
    return {"cuts": cuts, "overall_sorted": overall, "minutes_by_rank": [r[1] for r in rows]}


def rank_in_league(overall_sorted: list[float], value: float) -> int:
    """1-based rank this OVR would hold in the opening league."""
    lo, hi = 0, len(overall_sorted)
    while lo < hi:
        mid = (lo + hi) // 2
        if overall_sorted[mid] >= value:
            lo = mid + 1
        else:
            hi = mid
    return lo + 1


# ---------------------------------------------------------------------------------------------- real side

def real_game_cohorts(mode: str) -> dict[str, Any]:
    league = load_league(mode)
    thresholds = league_thresholds(league)
    players = []
    for p in league["players"]:
        if not p.get("team_id"):
            continue
        year = p.get("draft_year")
        status = p.get("draft_status")
        if not year and status != "undrafted":
            continue
        c = card(league, p["id"])
        row = {
            "id": p["id"], "name": p["name"], "draft_year": int(year) if year else None,
            "pick": int(p["draft_position"]) if p.get("draft_position") else None,
            "range": pick_range(p.get("draft_position")) if status != "undrafted" else "undrafted",
            "age": float(p.get("age") or 0), "position": p.get("position"),
            "off_role": p.get("primary_off_role"), "def_role": p.get("primary_def_role"),
            "height": p.get("height_inches"), **c,
            "league_rank": rank_in_league(thresholds["overall_sorted"], c["overall"]),
            "minutes": float(p.get("minutes_projection") or 0),
        }
        if mode == "inputs":
            row["groups"] = input_groups(league, p["id"])
        players.append(row)
    return {"mode": mode, "thresholds": {k: v for k, v in thresholds.items() if k != "minutes_by_rank"},
            "minutes_by_rank": thresholds["minutes_by_rank"], "players": players}


def read_draft_csv() -> list[dict[str, Any]]:
    if not DRAFT_CSV.exists():
        return []
    with DRAFT_CSV.open() as handle:
        return list(csv.DictReader(handle))


def norm(name: str) -> str:
    from nba_gm_data.utils import normalize_name

    return normalize_name(name)


def bbi_draft_outcomes() -> dict[str, Any]:
    """Follow 2015-2022 draft picks through Basketball Index offensive talent and minutes, seasons 1-4.

    Offense-only: the growth file's defensive and overall series cover mostly players still active in
    2025-26 (survivors), while expected offensive LEBRON covers ~500 players a season. Ranks are within each
    season among all players with a value; minutes come from the same file's 3PT rows.
    """
    picks = read_draft_csv()
    by_name: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in picks:
        by_name[norm(row["player"])].append(row)
    seasons: dict[str, dict[str, dict[str, float]]] = defaultdict(dict)
    with gzip.open(BBI_HISTORY, "rt") as handle:
        for row in csv.DictReader(handle):
            if row["metric"] == "xo_lebron" and row["actual"]:
                seasons[row["season"]].setdefault(norm(row["player"]), {})["xo"] = float(row["actual"])
                seasons[row["season"]][norm(row["player"])]["age"] = float(row["age"] or 0)
            elif row["metric"] == "3PT" and row["minutes"]:
                seasons[row["season"]].setdefault(norm(row["player"]), {})["minutes"] = float(row["minutes"])
    ranks: dict[str, dict[str, int]] = {}
    for season, rows in seasons.items():
        ordered = sorted((r["xo"], n) for n, r in rows.items() if "xo" in r)
        ranks[season] = {n: len(ordered) - i for i, (_, n) in enumerate(ordered)}
    season_stats = {}
    for season, rows in seasons.items():
        values = sorted(r["xo"] for r in rows.values() if "xo" in r)
        lo, mid, hi = q(values, .25, .5, .75)
        season_stats[season] = {"count": len(values), "q25": lo, "median": mid, "q75": hi}
    output = []
    for row in picks:
        year = int(row["draft_year"])
        if year < 2015 or year > 2022:
            continue
        name = norm(row["player"])
        history = []
        for k in range(1, 5):
            season = f"{year + k - 1}-{str(year + k)[-2:]}"
            if season not in seasons:
                history.append(None)
                continue
            rec = seasons[season].get(name)
            history.append(None if rec is None else {
                "season": season, "xo": rec.get("xo"), "rank": ranks[season].get(name),
                "minutes": rec.get("minutes", 0.0), "age": rec.get("age")})
        output.append({"draft_year": year, "pick": int(row["pick"]), "range": pick_range(row["pick"]),
                       "player": row["player"], "history": history,
                       "career_minutes": float(row["minutes"] or 0), "career_vorp": float(row["vorp"] or 0) if row["vorp"] else None,
                       "career_ws": float(row["win_shares"] or 0) if row["win_shares"] else None,
                       "career_bpm": float(row["bpm"]) if row["bpm"] else None,
                       "career_games": int(row["games"] or 0) if row["games"] else 0})
    return {"picks": output, "seasons": season_stats}


def minutes_role(minutes: float | None) -> str:
    """Season minutes to a role tier (82 games): starter ~25+ mpg, rotation ~13+ mpg, bench any minutes."""
    if not minutes:
        return "out"
    if minutes >= 2000:
        return "starter"
    if minutes >= 1000:
        return "rotation"
    return "bench"


def command_real(_args: argparse.Namespace) -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    result = {"game": {mode: real_game_cohorts(mode) for mode in ("inputs", "legacy")}, "bbi": bbi_draft_outcomes()}
    (OUT / "real.json").write_text(json.dumps(result))
    print("wrote", OUT / "real.json")


# ---------------------------------------------------------------------------------------------- generated side

def generated_class_players(year: int, seed: int, talent_model: bool = True) -> list[tuple[dict, list[dict], dict]]:
    """Rookie player records and traits for one generated class, drafted in public-rank order."""
    from nba_gm_data import draft
    from nba_gm_data.schema import to_plain

    records = to_plain(draft.generate_draft_class_records(str(year), seed, talent_model=talent_model))
    prospects = sorted(records["draft_prospects"], key=lambda p: int(p["rank"]))
    traits_by = defaultdict(list)
    for trait in records["draft_prospect_traits"]:
        traits_by[trait["prospect_id"]].append(trait)
    out = []
    for pick, prospect in enumerate(prospects, start=1):
        team = {"id": f"team_gen{pick % 30:02d}", "abbrev": f"G{pick % 30:02d}"}
        onboarding = {"draft_year": str(year), "overall_pick": pick, "name": prospect["name"],
                      "source_ids": prospect.get("source_ids")}
        contract = SimpleNamespace(id=f"contract_{year}_{seed}_{pick}")
        player = draft.rookie_player_record(onboarding, prospect, team, contract)
        player["id"] = f"gen_{year}_{seed}_{pick:02d}"
        traits = draft.rookie_trait_records(player, prospect, traits_by[prospect["id"]])
        out.append((player, traits, prospect))
    return out


def build_generated(mode: str, years: list[int], seeds: list[int]) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    """A fresh league with every generated rookie appended, installed the way a save load does."""
    from nba_gm_data import ratings_model

    league = json.loads(UNIVERSE.read_text())
    teams = sorted(t["id"] for t in league["teams"])
    rows = []
    for year in years:
        for seed in seeds:
            for player, traits, prospect in generated_class_players(year, seed):
                # Spread rookies over real teams so development sees the real range of staff.
                player["team_id"] = teams[(int(player["overall_pick"]) * 7 + seed + year) % len(teams)]
                league["players"].append(player)
                league["traits"].extend(traits)
                rows.append({"id": player["id"], "year": year, "seed": seed, "pick": player["overall_pick"],
                             "range": pick_range(player["overall_pick"]), "archetype": prospect["archetype"],
                             "position": prospect["position"], "age": float(player["age"]),
                             "height": prospect["height_inches"], "weight": prospect["weight_lbs"],
                             "current_ability": prospect["current_ability"], "potential": prospect["potential"],
                             "public_potential": (prospect.get("scouting_prior") or {}).get("potential", prospect["potential"]),
                             "minutes": player["minutes_projection"], "priority": player["rotation_priority"]})
    if mode == "inputs":
        ratings_model.install_inputs_model(league, ROOT)
    return league, rows


def minutes_for_rank(minutes_by_rank: list[float], rank: int) -> float:
    """Typical real minutes for a player at this league OVR rank (median of a +-10 rank window)."""
    lo, hi = max(0, rank - 11), min(len(minutes_by_rank), rank + 10)
    return float(st.median(minutes_by_rank[lo:hi] or [0.0]))


def develop(league: dict[str, Any], rows: list[dict[str, Any]], thresholds: dict[str, Any], seasons: int = 4,
            seed: int = 1) -> dict[str, list[dict[str, float]]]:
    """Monthly development from the July after the draft; minutes reset from league rank each July."""
    from nba_gm_data import health, ratings_model, save

    ids = sorted(r["id"] for r in rows)
    id_set = set(ids)
    ctx = {k: league[k] for k in ("meta", "teams", "staff_profiles", "gameplay_staff_slots")}
    ctx["players"] = [copy.deepcopy(p) for p in league["players"] if p["id"] in id_set]
    ctx["traits"] = [dict(t) for t in league["traits"] if t["player_id"] in id_set]
    ctx["player_health_states"] = []
    if ratings_model.uses_inputs_model(league):
        model = league[ratings_model.MODEL_KEY]
        ctx[ratings_model.MODEL_KEY] = {**model, "input_deltas": {}, "generated": dict(model.get("generated", {}))}
    by_id = {p["id"]: p for p in ctx["players"]}
    year0 = {r["id"]: int(r["year"]) for r in rows}
    history = {pid: [card(ctx, pid)] for pid in ids}
    for season in range(min(year0.values()), max(year0.values()) + seasons):
        active = [pid for pid in ids if year0[pid] <= season < year0[pid] + seasons]
        if not active:
            continue
        for pid in active:
            p = by_id[pid]
            if season > year0[pid]:
                p["age"] = float(p["age"]) + 1
                rank = rank_in_league(thresholds["overall_sorted"], history[pid][-1]["overall"])
                minutes = minutes_for_rank(thresholds["minutes_by_rank"], rank)
                p["minutes_projection"] = round(minutes, 1)
                p["rotation_priority"] = (
                    "development_priority" if season - year0[pid] < 2 and int(p["overall_pick"]) <= 20
                    else "core_rotation" if minutes >= 26 else "rotation" if minutes >= 16
                    else "deep_rotation" if minutes >= 8 else "fringe")
        view = {**ctx, "players": [by_id[pid] for pid in active]}
        for month in [f"{season}-{m:02d}" for m in range(7, 13)] + [f"{season + 1}-{m:02d}" for m in range(1, 7)]:
            events = health.advance_development(view, month, seed=seed)["events"]
            save.apply_development_events(ctx, events)
        for pid in active:
            history[pid].append(card(ctx, pid))
    groups = {pid: input_groups(ctx, pid) for pid in ids} if ratings_model.uses_inputs_model(league) else {}
    return {"history": history, "groups_after": groups}


def command_generated(args: argparse.Namespace) -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    years = [int(y) for y in args.years.split(",")]
    seeds = [int(s) for s in args.seeds.split(",")]
    result = {}
    for mode in args.modes.split(","):
        started = time.time()
        thresholds = league_thresholds(load_league(mode))
        league, rows = build_generated(mode, years, seeds)
        for row in rows:
            row.update(card(league, row["id"]))
            row["league_rank"] = rank_in_league(thresholds["overall_sorted"], row["overall"])
            if mode == "inputs":
                row["groups"] = input_groups(league, row["id"])
        print(mode, "entry built", len(rows), round(time.time() - started, 1), "s", flush=True)
        histories, groups_after = {}, {}
        if args.seasons:
            for seed in seeds:
                result_seed = develop(league, [r for r in rows if r["seed"] == seed], thresholds, args.seasons, seed)
                histories.update(result_seed["history"])
                groups_after.update(result_seed["groups_after"])
                print(mode, "seed", seed, "developed", round(time.time() - started, 1), "s", flush=True)
        for row in rows:
            row["history"] = histories.get(row["id"], [])
            row["ranks"] = [rank_in_league(thresholds["overall_sorted"], h["overall"]) for h in row["history"]]
            row["groups_after"] = groups_after.get(row["id"])
        result[mode] = {"rows": rows, "thresholds": {"cuts": thresholds["cuts"]}}
    name = args.out or "generated.json"
    (OUT / name).write_text(json.dumps(result))
    print("wrote", OUT / name)


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("real")
    gen = sub.add_parser("generated")
    gen.add_argument("--years", default="2027,2028,2029,2030,2031")
    gen.add_argument("--seeds", default="1,2,3")
    gen.add_argument("--seasons", type=int, default=4)
    gen.add_argument("--modes", default="inputs,legacy")
    gen.add_argument("--out", default="")
    args = parser.parse_args(argv)
    {"real": command_real, "generated": command_generated}[args.command](args)


if __name__ == "__main__":
    main()
