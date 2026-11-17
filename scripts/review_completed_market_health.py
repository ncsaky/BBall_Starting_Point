"""Review saved audit observations without advancing a game or loading its DB."""
from collections import Counter, defaultdict
from datetime import datetime
import argparse
import gzip
import hashlib
import json
from pathlib import Path
import statistics

from nba_gm_data.save import presentation_rating_value
from review_market_lifecycle import floor_accounting
from ten_season_soak import distribution


def read(path):
    with gzip.open(path, "rt") as handle:
        return json.load(handle)


def digest(path):
    result = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            result.update(block)
    return result.hexdigest()


def fixed_display(row):
    return presentation_rating_value(row["fixed24_engine"])


def metrics(players):
    rows = list(players)
    return {"count": len(rows), "fixed24_display": distribution(fixed_display(p) for p in rows),
            "fixed24_engine": distribution(p["fixed24_engine"] for p in rows),
            "fixed24_display_at_least": {str(t): sum(fixed_display(p) >= t for p in rows) for t in (60, 70, 80, 85, 90)},
            "age": distribution(float(p["age"]) for p in rows if p.get("age") is not None)}


def draft_band(pick):
    return "1-3" if pick <= 3 else "4-14" if pick <= 14 else "15-30" if pick <= 30 else "31+"


def market_summary(markets):
    # Pre-day room reads can add bids. Keep both observations; opening means
    # the earliest day-one roster, while outcomes use the committed completion.
    rows = sorted(markets, key=lambda item: item[0])
    opening = next((m for _, m in rows if m.get("day") == 1), None)
    final = next((m for _, m in reversed(rows) if m.get("status") == "completed"), None)
    if not opening or not final:
        return {"complete": False}
    premium = {p["id"]: p for p in opening["players"] if p["overall"] >= 80}
    offers = final["offers"]
    signed = {p["player_id"] for p in offers if p.get("status") == "accepted"}
    remaining = {p["id"] for p in final["players"]}
    suitors = defaultdict(set)
    for offer in offers:
        if offer.get("team_id"):
            suitors[offer["player_id"]].add(offer["team_id"])
    return {"complete": True, "opening_80_plus": len(premium),
            "opening_80_plus_signed_via_offers": len(premium.keys() & signed),
            "opening_80_plus_still_free": [p for pid, p in premium.items() if pid in remaining],
            "opening_80_plus_no_longer_free_without_signed_offer": sorted(premium.keys() - signed - remaining),
            "opening_80_plus_multiple_suitors": sum(len(suitors[pid]) >= 2 for pid in premium),
            "opening_80_plus_signed_at_5m_or_less": [{**p, "player": premium[p["player_id"]]} for p in offers if p.get("status") == "accepted"
                and p["player_id"] in premium and float(p.get("aav_millions") or 0) <= 5],
            "total_signed_offers": sum(p.get("status") == "accepted" for p in offers),
            "remaining_80_plus": [p for p in final["players"] if p["overall"] >= 80],
            "final_never_bid_room_screen_candidates": [p for p in final["players"]
                if p.get("diagnosis") == "never_bid_on_despite_room_candidate" and p.get("safe_year_limit", 0) > 0]}


def career(out, seed, job):
    directory = out / f"career-{seed}"
    run = json.loads((directory / "run.json").read_text())
    source_path = Path(run["save_path"]).resolve()
    if not source_path.is_relative_to(out):
        raise ValueError("Audit save is not inside the recorded result directory")
    source_hash = digest(source_path)
    saved = json.loads(source_path.read_text())
    first = last = None
    annual = {}
    generated = {}
    development = set()
    duplicate_development_keys = set()
    regular_dates = set()
    for path in sorted((directory / "observations").glob("*.json.gz")):
        snap = read(path)
        if snap["date"] >= f"{int(snap['season'][:4]) + 1}-10-01":
            raise ValueError(f"Invalid season clock in {path}")
        first = first or snap
        last = snap
        if snap["date"].endswith("-10-01"):
            annual[snap["date"]] = snap
        regular_complete = snap["phase"] == "regular_season" and snap["date"].endswith("-04-12")
        if regular_complete:
            regular_dates.add(snap["date"])
        for event in snap.get("development_events", []):
            key = (event["player_id"], event["month"])
            if key in development:
                duplicate_development_keys.add(key)
            development.add(key)
        for player in snap["players"]:
            year = int(player.get("draft_year") or 0)
            if year < 2027:
                continue
            pid = player["id"]
            row = generated.setdefault(pid, {"id": pid, "name": player["name"], "year": year,
                "pick": int(player.get("overall_pick") or 999), "entry": fixed_display(player),
                "peak": fixed_display(player), "rotation_seasons": set()})
            row["peak"] = max(row["peak"], fixed_display(player))
            if regular_complete and int(player.get("games") or 0) >= 20 and float(player.get("mpg") or 0) >= 16:
                row["rotation_seasons"].add(snap["season"])
    endpoint = {p["id"]: p for p in last["players"]}
    mature = [p for p in generated.values() if p["year"] <= 2030]
    bands = {}
    for band in ("1-3", "4-14", "15-30", "31+"):
        pool = [p for p in mature if draft_band(p["pick"]) == band]
        bands[band] = {"count": len(pool), "entry": distribution(p["entry"] for p in pool),
            "sampled_peak": distribution(p["peak"] for p in pool),
            "sampled_peak_90_plus": sum(p["peak"] >= 90 for p in pool),
            "at_least_one_completed_rotation_season": sum(bool(p["rotation_seasons"]) for p in pool),
            "still_rostered": sum(endpoint.get(p["id"], {}).get("rostered", False) for p in pool)}
    retirees = [p for r in last.get("retirement_reports", []) for p in r["retirements"]]
    rookie_ids = [p["player_id"] for p in last["incoming_rookies"]]
    rookie_slots = Counter((str(p["draft_year"]), int(p["overall_pick"])) for p in last["incoming_rookies"])
    planned_slots = Counter((year, int(p["overall_pick"])) for year, order in saved["draft_orders"].items()
                            if year in {str(p["draft_year"]) for p in last["incoming_rookies"]}
                            for p in order["draft_order"])
    missing_summers = [{"id": p["player_id"], "year": p["draft_year"], "missing": missing}
        for p in last["incoming_rookies"]
        if p.get("roster_status") == "signed_rookie"
        and (missing := [f"{p['draft_year']}-{m:02}" for m in (7, 8, 9)
                        if (p["player_id"], f"{p['draft_year']}-{m:02}") not in development])]
    annual_rows = []
    for stamp, snap in sorted(annual.items()):
        roster = [p for p in snap["players"] if p["rostered"]]
        annual_rows.append({"date": stamp, **metrics(roster),
            "generated_90_plus": sum(int(p.get("draft_year") or 0) >= 2027 and fixed_display(p) >= 90 for p in roster),
            "age_35_plus": sum(float(p.get("age") or 0) >= 35 for p in roster),
            "unsigned_80_plus": sum(not p["rostered"] and fixed_display(p) >= 80 for p in snap["players"])})
    by_market = defaultdict(list)
    for path in sorted((directory / "markets").glob("*.json.gz")):
        market = read(path)
        by_market[market["season"]].append((path.name, market))
    markets = {season: market_summary(rows) for season, rows in sorted(by_market.items())}
    timings = defaultdict(list)
    by_season = defaultdict(list)
    for action in run["actions"]:
        if action.get("timing_unknown"):
            continue
        timings[action["action"]].append(action["seconds"])
        stamp = action["from"]
        ending_year = int(stamp[:4]) + (int(stamp[5:7]) >= 10)
        by_season[ending_year].append(action["seconds"])
    validation = []
    for season in saved["season_history"]:
        records = list(season["team_records"].values())
        validation.append({"season": season.get("season"), "teams": len(records),
            "games": sum(int(p["wins"]) for p in records),
            "all_82_games": all(int(p["wins"]) + int(p["losses"]) == 82 for p in records)})
    assert digest(source_path) == source_hash
    return {"status": job["status"], "complete_seasons": run["complete_seasons"],
        "endpoint": run["endpoint"], "started_at": run["started_at"], "source_save_sha256": source_hash,
        "annual": annual_rows,
        "floor_accounting_same_october_dates": floor_accounting(annual[min(annual)], last),
        "mature_2027_2030_cohorts": bands,
        "generated_endpoint_stars": [{"id": p["id"], "name": p["name"], "year": p["draft_year"],
            "age": p["age"], "fixed24_display": fixed_display(p)} for p in endpoint.values()
            if p["rostered"] and int(p.get("draft_year") or 0) >= 2027 and fixed_display(p) >= 90],
        "late_pick_sampled_stars": [{k: p[k] for k in ("id", "name", "year", "pick", "entry", "peak")}
            for p in generated.values() if p["pick"] >= 15 and p["peak"] >= 90],
        "retirement_ages": distribution(p["age"] for p in retirees), "retirements": len(retirees),
        "league_exits": last["league_exit_count"], "markets": markets,
        "timing": {"recorded_action_hours": round(sum(sum(v) for v in timings.values()) / 3600, 3),
            "by_action": {key: {"count": len(v), "total_seconds": round(sum(v), 2), "median_seconds": round(statistics.median(v), 2), "max_seconds": max(v)} for key, v in timings.items()},
            "minutes_by_season_ending_year": {str(year): round(sum(v) / 60, 2) for year, v in sorted(by_season.items())}},
        "validation": {"archived_seasons": validation, "regular_season_observations": len(regular_dates),
            "drafted_players": len(rookie_ids), "unique_drafted_players": len(set(rookie_ids)),
            "draft_slots_match_saved_orders": rookie_slots == planned_slots,
            "observed_development_player_months": len(development),
            "repeated_observation_development_keys": len(duplicate_development_keys),
            "missing_signed_rookie_summer_records": missing_summers,
            "retirement_ids_unique": len(retirees) == len({p["player_id"] for p in retirees}),
            "retirement_count_matches_census": len(retirees) == last["retired_count"]}}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--report-dir", type=Path, required=True)
    args = parser.parse_args()
    out, dest = args.output_dir.resolve(), args.report_dir.resolve()
    if dest.is_relative_to(out):
        raise ValueError("Write derived review outside the original experiment")
    status = json.loads((out / "status.json").read_text())
    manifest = json.loads((out / "manifest.json").read_text())
    result = {"source": str(out), "manifest": manifest, "batch_status": status["status"],
        "scope": "Read-only observation review; no app actions, DB access, ratings tuning or simulation. Fixed-24-minute OVR transformed with the game's unchanged presentation scale. Repeated simulation seeds, not independent draft universes. Rotation outcome means >=20 games and >=16 MPG in a complete regular-season endpoint, not an inferred potential/bust label.",
        "careers": {str(seed): career(out, seed, status["jobs"][str(seed)]) for seed in manifest["seeds"]}}
    start = min(datetime.fromisoformat(p["started_at"]) for p in result["careers"].values())
    result["batch_elapsed_hours_including_pauses"] = round((datetime.fromisoformat(status["finished_at"]) - start).total_seconds() / 3600, 2)
    result["total_verified_complete_seasons"] = sum(p["complete_seasons"] for p in result["careers"].values())
    dest.mkdir(parents=True, exist_ok=True)
    (dest / "completed-review.json").write_text(json.dumps(result, indent=2) + "\n")
    for seed, row in result["careers"].items():
        print(seed, json.dumps({"status":row["status"], "seasons":row["complete_seasons"],
            "start_90_plus":row["annual"][0]["fixed24_display_at_least"]["90"],
            "end_90_plus":row["annual"][-1]["fixed24_display_at_least"]["90"],
            "generated_stars":len(row["generated_endpoint_stars"]),
            "missing_summers":len(row["validation"]["missing_signed_rookie_summer_records"])}), flush=True)
    print(f"Saved {dest / 'completed-review.json'}", flush=True)


if __name__ == "__main__":
    main()
