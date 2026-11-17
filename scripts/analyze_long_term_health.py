"""Describe roster selection, draft outcomes and star turnover without changing saves."""
from collections import defaultdict
import json

from audit_roster_floor import decompose, rating, roster
from long_term_health import OUT, annual_snapshots, canonical, check_protection, write
from ten_season_soak import distribution
from nba_gm_data.save import load_save, player_display_attribute_summary
from nba_gm_data.health import prospect_development_realization
from nba_gm_data.talent import trait_ceiling


def band(pick):
    return "1-3" if pick <= 3 else "4-14" if pick <= 14 else "15-30" if pick <= 30 else "31-60"


def star_flow(before, after):
    old, new = roster(before), roster(after)
    common = old.keys() & new.keys()
    up = [pid for pid in common if rating(old[pid]) < 90 <= rating(new[pid])]
    down = [pid for pid in common if rating(new[pid]) < 90 <= rating(old[pid])]
    entering = [pid for pid in new.keys() - old.keys() if rating(new[pid]) >= 90]
    leaving = [pid for pid in old.keys() - new.keys() if rating(old[pid]) >= 90]
    start = sum(rating(p) >= 90 for p in old.values())
    end = sum(rating(p) >= 90 for p in new.values())
    assert start + len(up) - len(down) + len(entering) - len(leaving) == end
    describe = lambda ids, pool: [{"id": pid, "name": pool[pid]["name"], "age": pool[pid]["age"],
                                   "draft_year": pool[pid].get("draft_year"), "overall": rating(pool[pid])}
                                  for pid in sorted(ids)]
    return {"from": before["date"], "to": after["date"], "before": start, "after": end,
            "crossing_up": describe(up, new), "crossing_down": describe(down, old),
            "roster_entries": describe(entering, new), "roster_departures": describe(leaving, old)}


def cohort_outcomes(rookies, snapshots, histories, initial_grades, retired, exited, endpoint):
    ids = [r["player_id"] for r in rookies]
    assert len(ids) == len(set(ids)), "Duplicate rookie identity"
    observations = defaultdict(list)
    for snapshot in snapshots:
        for player in snapshot["players"]:
            observations[player["id"]].append((snapshot["date"], player))
    final = {p["id"]: p for p in snapshots[-1]["players"]}
    rows = []
    for rookie in rookies:
        pid = rookie["player_id"]
        seasons = []
        for history in histories:
            if int(history["season"][:4]) < int(rookie["draft_year"]):
                continue
            line = history.get("player_season_stats", {}).get(pid, {})
            games = int(line.get("games") or 0)
            minutes = float(line.get("minutes") or 0)
            seasons.append({"season": history["season"], "games": games, "minutes": minutes,
                            "mpg": minutes / games if games else 0,
                            "rotation": games >= 10 and minutes / games >= 12})
        records = observations[pid]
        entry = initial_grades.get(pid)
        samples = [rating(row) for _, row in records]
        if entry is not None:
            samples.append(entry)
        sampled_peak = max(samples, default=None)
        thresholds = {str(threshold): next(({"date": stamp, "age": row["age"]} for stamp, row in records
                                          if rating(row) >= threshold), None) for threshold in (80, 90)}
        rows.append({"id": pid, "name": rookie["name"], "year": int(rookie["draft_year"]),
                     "pick": int(rookie["overall_pick"]), "band": band(int(rookie["overall_pick"])),
                     "potential": rookie.get("potential"), "entry_overall": entry,
                     "sampled_peak_overall": sampled_peak,
                     "sampled_peak_gain": sampled_peak - entry if sampled_peak is not None and entry is not None else None,
                     "first_observed_threshold": thresholds, "seasons_observed": len(seasons),
                     "rotation_seasons": sum(s["rotation"] for s in seasons),
                     "career_games_recorded": sum(s["games"] for s in seasons),
                     "career_minutes_recorded": sum(s["minutes"] for s in seasons),
                     "rostered_at_endpoint": bool(final.get(pid, {}).get("rostered")),
                     "actual_retirement": pid in retired - exited, "league_exit": pid in exited,
                     "seasons": seasons})
    grouped = defaultdict(list)
    for row in rows:
        grouped[f"{row['year']}:{row['band']}"].append(row)
    return {"endpoint": endpoint, "roster_and_rating_census_date": snapshots[-1]["date"],
            "scope": "All picks included, including non-survivors. Rotation means at least 10 recorded games and 12 MPG in a completed season; archived totals may include playoffs. Rating peaks and ages are sampled at annual censuses, not exact career peaks. Young cohorts remain right-censored. A rotation specialist is not automatically a bust because of low OVR.",
            "groups": {key: {"picks": len(pool), "rostered": sum(p["rostered_at_endpoint"] for p in pool),
                             "ever_rotation": sum(p["rotation_seasons"] > 0 for p in pool),
                             "no_recorded_appearances": sum(p["career_games_recorded"] == 0 for p in pool),
                             "sampled_90_plus": sum(p["sampled_peak_overall"] is not None and p["sampled_peak_overall"] >= 90 for p in pool),
                             "peak_overall": distribution(p["sampled_peak_overall"] for p in pool if p["sampled_peak_overall"] is not None),
                             "min_completed_seasons_observed": min(p["seasons_observed"] for p in pool)}
                       for key, pool in sorted(grouped.items())}, "players": rows}


def capacity_bounds(initial, seed):
    players = {p["id"]: p for p in initial["players"]}
    capped = []
    complete = defaultdict(int)
    for trait in initial["traits"]:
        player = players[trait["player_id"]]
        profile = (trait.get("components") or {}).get("career_capacity") or {}
        ceiling = trait_ceiling(player, trait["trait_key"], profile, prospect_development_realization(player, seed), seed)
        if ceiling is not None:
            complete[player["id"]] += 1
        capped.append({**trait, "value": ceiling if ceiling is not None else trait["value"]})
    view = {"meta": initial["meta"], "players": [{**p, "minutes_projection": 36} for p in initial["players"]],
            "traits": capped, "_allow_internal_caches": True}
    return {pid: player_display_attribute_summary(view, pid)["overall"]
            for pid, count in complete.items() if count == 15}


def analyze():
    source = canonical()
    output = {}
    for directory in sorted(OUT.glob("career-*")):
        seed = int(directory.name.split("-")[-1])
        run = json.loads((directory / "run.json").read_text())
        saved = load_save(run["save_path"])
        snapshots = annual_snapshots(directory)
        initial = {"meta": source["meta"], "players": [{**p, "minutes_projection": 24} for p in saved["generated_players"]],
                   "traits": saved["generated_traits"], "_allow_internal_caches": True}
        grades = {p["id"]: player_display_attribute_summary(initial, p["id"])["overall"] for p in initial["players"]}
        cohorts = cohort_outcomes(saved["incoming_rookies"], snapshots, saved["season_history"], grades,
                                  set(saved.get("retired_player_ids") or []), set(saved.get("league_exit_player_ids") or []),
                                  saved["state"]["current_date"])
        bounds = capacity_bounds(initial, seed)
        for row in cohorts["players"]:
            row["idealized_36mpg_capacity_overall"] = bounds.get(row["id"])
        cohorts["capacity_bound_scope"] = "All 15 seeded skill ceilings reached simultaneously at 36 MPG, ignoring aging, injury and learning time. An optimistic structural upper bound, not a prediction or a promised player potential. Missing capacity records are not treated as zero."
        retired = {r["player_id"]: r for report in saved.get("retirement_reports", []) for r in report["retirements"]}
        output[str(seed)] = {"endpoint": saved["state"]["current_date"],
                            "census_endpoint": snapshots[-1]["date"], "status": run["status"],
                            "floor_intervals": [decompose(a, b) for a, b in zip(snapshots, snapshots[1:])],
                            "star_intervals": [star_flow(a, b) for a, b in zip(snapshots, snapshots[1:])],
                            "cohorts": cohorts, "retirement_ages": distribution(r["age"] for r in retired.values()),
                            "retirement_records": list(retired.values())}
    check_protection()
    write(OUT / "analysis.json", output)
    print(json.dumps({seed: {"endpoint": r["endpoint"], "census_endpoint": r["census_endpoint"],
                             "last_floor_interval": r["floor_intervals"][-1],
                             "cohort_groups": r["cohorts"]["groups"]} for seed, r in output.items()}, indent=2))


if __name__ == "__main__":
    analyze()
