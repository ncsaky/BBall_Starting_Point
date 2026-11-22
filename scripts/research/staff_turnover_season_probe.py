"""Run full schedules through the standard game and staff models with fixed player rosters."""
from __future__ import annotations

import argparse
from collections import defaultdict
from datetime import date, timedelta
from pathlib import Path

from league_health_audit import regular_complete
from two_season_league_probe import ROOT, record_staff_snapshot

from nba_gm_data import save as career
from nba_gm_data.app_actions import load_app_canonical
from nba_gm_data.schema import to_plain
from nba_gm_data.sim import build_sim_indices, load_sim_context, load_sim_reference, sim_game_with_context
from nba_gm_data.staff import simulate_ai_staff_changes


def review(canonical: dict, save: dict, previous: str, today: str, seed: int) -> None:
    career.set_save_date_phase(save, today)
    recs = simulate_ai_staff_changes(canonical, save, previous, today, seed=seed, limit=8)
    career.apply_ai_staff_recommendations(canonical, save, recs, seed)


def advance_staff_year(canonical: dict, save: dict, seed: int, year: int) -> None:
    completed = save["meta"]["season"]
    save.setdefault("season_history", []).append({"season": completed, "team_records": save["team_records"]})
    summer_review = getattr(career, "offseason_coaching_recommendations", None)
    if summer_review is not None:
        recs = summer_review(canonical, save)
        career.apply_ai_staff_recommendations(canonical, save, {"recommendations": recs}, seed)

    season = career.season_label_from_start(year + 1)
    save["meta"]["season"] = season
    save["meta"]["season_start_year"] = year + 1
    save["meta"]["season_index"] = int(save["meta"].get("season_index") or 0) + 1
    career.set_save_date_phase(save, f"{year + 1}-10-01")
    save["team_records"] = career.initial_team_records(canonical)
    save["schedule_state"] = {"simulated_game_ids": []}
    save["team_game_logs"] = []
    save["player_game_logs"] = []
    save["player_season_stats"] = {}
    save["game_results"] = []
    save["season_schedules"][season] = career.generate_future_schedule(ROOT, season, year + 1)
    career.age_staff_contracts(save, canonical, seed=seed)
    if summer_review is not None:
        today = save["state"]["current_date"]
        recs = simulate_ai_staff_changes(canonical, save, today, today, seed=seed, limit=180, vacancies_only=True)
        career.apply_ai_staff_recommendations(canonical, save, recs, seed, offseason_appointment=True)


def run(out: Path, *, seed: int, seasons: int) -> None:
    canonical = load_app_canonical(ROOT)
    save = career.create_league_save(ROOT, canonical, "GSW", out / "seed.json", seed=seed, ratings_model="inputs_v1")
    # Equal healthy-roster conditions in both versions. The career probe's markets,
    # development, injuries and playoffs are outside this staff-only comparison.
    save["health_states"] = []
    tables = load_sim_reference(ROOT)
    start = int(save["meta"]["season"][:4])
    for year in range(start, start + seasons):
        active = career.canonical_with_save(canonical, save)
        context = load_sim_context(ROOT, active, reference=tables, indices=False)
        context["schedule"] = career.schedule_for_save(ROOT, save)
        context["indices"] = build_sim_indices(context)
        games = defaultdict(list)
        for game in context["schedule"]:
            games[game["gameDate"]].append(game)
        first_day = f"{year}-10-21"
        career.set_save_date_phase(save, first_day)
        remember = getattr(career, "remember_opening_coaching_staff", None)
        if remember is not None:
            remember(save)
        record_staff_snapshot(out, save)
        context["indices"]["coach_by_team"] = career.save_coach_ratings(active, save)
        day = date.fromisoformat(first_day)
        while day <= date(year + 1, 4, 12):
            today = day.isoformat()
            for game in games[today]:
                result = sim_game_with_context(context, str(game["externalGameId"]), mode="sandbox-sim", seed=seed)
                career.record_game_result(save, canonical, game, to_plain(result))
            if (day.day == 1 and day.month != 10) or (day.month == 2 and day.day == 5):
                review(active, save, (day - timedelta(days=1)).isoformat(), today, seed)
                context["indices"]["coach_by_team"] = career.save_coach_ratings(active, save)
                context["sim_cache"] = {"player_pools": {}, "team_features": {}, "game_contexts": {}}
            day += timedelta(days=1)
        regular_complete(save)
        print(f"{save['meta']['season']}: all 1,230 regular-season games completed", flush=True)
        for month_day in ("06-17", "06-27", "07-01", "08-01", "09-01", "09-30"):
            review(active, save, f"{year + 1}-{month_day}", f"{year + 1}-{month_day}", seed)
        advance_staff_year(canonical, save, seed, year)
    career.set_save_date_phase(save, f"{start + seasons}-10-21")
    record_staff_snapshot(out, save)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--seed", type=int, default=17)
    parser.add_argument("--seasons", type=int, default=2)
    args = parser.parse_args()
    args.out.mkdir(parents=True, exist_ok=True)
    run(args.out, seed=args.seed, seasons=args.seasons)


if __name__ == "__main__":
    main()
