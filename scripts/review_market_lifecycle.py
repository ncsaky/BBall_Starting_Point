"""Summarize the overnight audit's observations, never its playable saves.

This can run while the batch is active: observation files publish atomically.
Sampling establishes associations, not the causal effect of being unsigned.
"""
from collections import Counter, defaultdict
import argparse
import gzip
import json
from pathlib import Path
import statistics

OUT = Path(__file__).resolve().parents[1] / "output/market-lifecycle-2026-10-25"


def read(path):
    with gzip.open(path, "rt") as handle:
        return json.load(handle)


def mean(values):
    rows = list(values)
    return round(statistics.fmean(rows), 4) if rows else None


def floor_accounting(first, last):
    before = {row["id"]: row["fixed24_engine"] for row in first["players"] if row["rostered"]}
    after = {row["id"]: row["fixed24_engine"] for row in last["players"] if row["rostered"]}
    if not before or not after:
        return {}
    start_mean = statistics.fmean(before.values())
    retained = before.keys() & after.keys()
    entrants = after.keys() - before.keys()
    departures = before.keys() - after.keys()
    growth = sum(after[pid] - before[pid] for pid in retained) / len(after)
    entry = sum(after[pid] - start_mean for pid in entrants) / len(after)
    exit_effect = -sum(before[pid] - start_mean for pid in departures) / len(after)
    total = statistics.fmean(after.values()) - start_mean
    assert abs(growth + entry + exit_effect - total) < 1e-8
    return {"scope": "Fixed-24-minute engine OVR, rostered pool. Entrants/departures include free-agent status changes, not just draft/retirement.",
            "from": first["date"], "to": last["date"], "rostered_before": len(before), "rostered_after": len(after),
            "mean_before": round(start_mean, 4), "mean_after": mean(after.values()),
            "mean_change": round(total, 4), "retained_player_rating_component": round(growth, 4),
            "entry_composition_component": round(entry, 4), "departure_composition_component": round(exit_effect, 4),
            "retained": len(retained), "entrants": len(entrants), "departures": len(departures)}


def valid_observations(recorded):
    snapshots = []
    invalid_at = None
    for snap in recorded:
        season_end = int(snap["season"][:4]) + 1
        if snap["date"] >= f"{season_end}-10-01":
            invalid_at = snap["date"]
            break
        snapshots.append(snap)
    return snapshots, invalid_at


def career(directory):
    run_path = directory / "run.json"
    if not run_path.exists():
        return {"status": "not_created"}
    run = json.loads(run_path.read_text())
    recorded = [read(path) for path in sorted((directory / "observations").glob("*.json.gz"))]
    snapshots, invalid_at = valid_observations(recorded)
    if not snapshots:
        return {"status": "no_observations", "endpoint": run["endpoint"]}
    first, latest = snapshots[0], snapshots[-1]
    histories = defaultdict(list)
    for snapshot in snapshots:
        for row in snapshot["players"]:
            histories[row["id"]].append({**row, "sample_date": snapshot["date"]})
    generated = []
    for pid, rows in histories.items():
        initial, end = rows[0], rows[-1]
        if not initial.get("draft_year") or int(initial["draft_year"]) < 2027:
            continue
        generated.append({"id": pid, "name": initial["name"], "draft_year": initial["draft_year"],
                          "pick": initial.get("overall_pick"), "entry_engine": initial["fixed24_engine"],
                          "sampled_peak_engine": max(row["fixed24_engine"] for row in rows),
                          "last_engine": end["fixed24_engine"], "last_observed": end["sample_date"],
                          "unsigned_samples": sum(not row["rostered"] for row in rows),
                          "zero_projected_minutes_samples": sum(not row.get("minutes") for row in rows),
                          "sampled_rotation_opportunity": any(row.get("mpg", 0) >= 16 for row in rows)})
    markets = {}
    for path in sorted((directory / "markets").glob("*.json.gz")):
        market = read(path)
        markets[(market["season"], market["day"], market["status"])] = market
    market_summaries = []
    for key, market in sorted(markets.items(), key=lambda pair: str(pair[0])):
        candidates = [row for row in market["players"] if row.get("diagnosis") == "never_bid_on_despite_room_candidate"
                      and row.get("safe_year_limit", 0) > 0]
        premium = [row for row in market["players"] if row["overall"] >= 80]
        market_summaries.append({"season": key[0], "day": key[1], "status": key[2],
                                 "remaining_free_agents": len(market["players"]), "remaining_80_plus": len(premium),
                                 "80_plus_without_active_bids": sum(not row["active_bids"] for row in premium),
                                 "never_bid_with_room_review_candidates": sorted(candidates, key=lambda row: -row["overall"]),
                                 "offer_statuses": dict(Counter(offer.get("status") for offer in market["offers"])),
                                 "teams_with_20m_hard_cap_room": [team for team, row in market["teams"].items()
                                     if float(row["cap"].get("hard_cap_space_millions") or 0) >= 20]})
    latest_rows = latest["players"]
    ages = defaultdict(list)
    positions = defaultdict(list)
    for row in latest_rows:
        if row["rostered"]:
            ages[str(int(float(row["age"] or 0)))].append(row["fixed24_engine"])
            positions[str(row.get("position"))].append(row["fixed24_engine"])
    events = {event["id"]: event for snap in snapshots for event in snap.get("development_events", [])}
    timings = [row["seconds"] for row in run["actions"] if not row.get("timing_unknown")]
    return {"status": "invalid_after_missed_rollover" if invalid_at else run["status"],
            "endpoint": latest["date"], "run_endpoint": run["endpoint"],
            "excluded_observations": len(recorded) - len(snapshots), "invalid_from": invalid_at,
            "complete_seasons": run["complete_seasons"],
            "observations": len(snapshots), "market_days": market_summaries,
            "floor_accounting": floor_accounting(first, latest), "generated_careers": generated,
            "latest_rostered_age_counts": {age: len(values) for age, values in ages.items()},
            "latest_neutral_engine_mean_by_age": {age: mean(values) for age, values in ages.items()},
            "latest_neutral_engine_mean_by_position": {position: mean(values) for position, values in positions.items()},
            "retirements": latest["retired_count"], "league_exits": latest["league_exit_count"],
            "new_development_records_observed": len(events),
            "development_context": {"unsigned_events": sum(not row.get("team_id") for row in events.values()),
                                    "zero_minutes_events": sum(not row.get("minutes_context") for row in events.values()),
                                    "evaluated_plateaus": sum(not row.get("trait_deltas") for row in events.values())},
            "timing": {"actions": len(timings), "mean_seconds": mean(timings), "max_seconds": max(timings, default=0)}}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=Path, default=OUT)
    args = parser.parse_args()
    out = args.output_dir.resolve()
    manifest = json.loads((out / "manifest.json").read_text())
    report = {"scope": manifest["scope"],
              "limits": "Opportunity counts are snapshot samples, not exact unsigned durations or causal estimates. Generated players need multiple completed years before bust/star rates are interpretable. Ratings are fixed-minute engine values unless a display OVR is explicitly named.",
              "careers": {str(seed): career(out / f"career-{seed}") for seed in manifest["seeds"]}}
    path = out / "review.json"
    temporary = path.with_suffix(".json.tmp")
    temporary.write_text(json.dumps(report, indent=2) + "\n")
    temporary.replace(path)
    for seed, row in report["careers"].items():
        print(f"Seed {seed}: {row.get('endpoint', 'not created')} | {row.get('complete_seasons', 0)} seasons | "
              f"{len(row.get('market_days', []))} market checkpoints | {row.get('retirements', 0)} retirements")
    print(f"Detailed review: {path}")


if __name__ == "__main__":
    main()
