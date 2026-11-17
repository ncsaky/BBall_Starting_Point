"""Read completed overnight careers without advancing or modifying their saves."""
from collections import defaultdict
import gc
import json

from analyze_long_term_health import cohort_outcomes
from audit_roster_floor import decompose, rating, summary
from long_term_health import OUT, annual_snapshots, check_inputs, check_protection, fingerprints, sha, write
from nba_gm_data.history_store import load_history_records
from nba_gm_data.save import load_save
from ten_season_soak import distribution
from league_health_audit import regular_complete


def main():
    check_inputs()
    check_protection()
    batch = json.loads((OUT / "overnight/status.json").read_text())
    assert fingerprints() == batch["source_hashes"]
    result = {"batch_status": batch["status"], "finished_at": batch["finished_at"],
              "scope": "Frozen V4 baseline and recorded runtime epochs, fixed-24-minute presentation ratings. Five independent simulation seeds share the same underlying draft universe; they are not five independently drawn prospect universes.",
              "completed": {}, "excluded": {}}
    for seed, job in sorted(batch["jobs"].items()):
        directory = OUT / f"career-{seed}"
        run = json.loads((directory / "run.json").read_text())
        if job["status"] != "completed":
            result["excluded"][seed] = job
            continue
        path = run["save_path"]
        before_hash = sha(path)
        saved = load_save(path)
        snaps = annual_snapshots(directory)
        assert len(snaps) == 11 and len(saved["season_history"]) == 10
        assert saved["state"]["current_date"] == snaps[-1]["date"] == "2036-10-01"
        for season in saved["season_history"]:
            regular_complete({"team_records": season["team_records"]})
            assert season["draft_result"]["status"] == "already_present"
        rookies = saved["incoming_rookies"]
        assert len({r["player_id"] for r in rookies}) == len(rookies)
        by_year = defaultdict(list)
        for rookie in rookies:
            by_year[str(rookie["draft_year"])].append(rookie)
        assert set(by_year) == {str(year) for year in range(2027, 2037)}
        for year, pool in by_year.items():
            planned = saved["draft_orders"][year]["draft_order"]
            assert len(pool) == len(planned)
            assert {r["overall_pick"] for r in pool} == {r["overall_pick"] for r in planned}
        events = load_history_records(path, saved, "development_events") + saved.get("development_events", [])
        event_by_id = {}
        for event in events:
            assert event["id"] not in event_by_id or event_by_id[event["id"]] == event
            event_by_id[event["id"]] = event
        assert len({(e["player_id"], e["month"]) for e in event_by_id.values()}) == len(event_by_id)
        months = defaultdict(set)
        for event in event_by_id.values():
            months[event["player_id"]].add(event["month"])
        missing = [{"id": r["player_id"], "missing": sorted({f"{r['draft_year']}-{m:02}" for m in (7,8,9)} - months[r["player_id"]])}
                   for r in rookies if r.get("roster_status") == "signed_rookie"]
        missing = [row for row in missing if row["missing"]]
        retired = set(saved.get("retired_player_ids", [])) - set(saved.get("league_exit_player_ids", []))
        retirements = [r for report in saved.get("retirement_reports", []) for r in report["retirements"]]
        assert len(retirements) == len(retired) and {r["player_id"] for r in retirements} == retired
        cohorts = cohort_outcomes(rookies, snaps, saved["season_history"], {}, retired,
                                  set(saved.get("league_exit_player_ids", [])), saved["state"]["current_date"])
        mature = [r for r in cohorts["players"] if r["year"] <= 2030]
        endpoint = [p for p in snaps[-1]["players"] if p["rostered"]]
        generated_stars = [p for p in endpoint if int(p.get("draft_year") or 0) >= 2027 and rating(p) >= 90]
        annual = []
        for snap in snaps:
            roster = [p for p in snap["players"] if p["rostered"]]
            annual.append({"date": snap["date"], **summary(roster), "distribution": distribution(rating(p) for p in roster),
                           "generated_90_plus": sum(int(p.get("draft_year") or 0) >= 2027 and rating(p) >= 90 for p in roster),
                           "35_plus": sum(p["age"] >= 35 for p in roster)})
        cohort_bands = {}
        for band in ("1-3", "4-14", "15-30", "31-60"):
            pool = [p for p in mature if p["band"] == band]
            cohort_bands[band] = {"picks": len(pool), "ever_rotation": sum(p["rotation_seasons"] > 0 for p in pool),
                                  "sampled_90_plus": sum((p["sampled_peak_overall"] or 0) >= 90 for p in pool),
                                  "still_rostered": sum(p["rostered_at_endpoint"] for p in pool)}
        row = {"annual": annual, "floor_accounting": decompose(snaps[0], snaps[-1]),
               "new_stars_at_endpoint": [{"name": p["name"], "age": p["age"], "draft_year": p["draft_year"], "overall": rating(p)} for p in generated_stars],
               "endpoint_star_ages": distribution(p["age"] for p in endpoint if rating(p) >= 90),
               "retirement_ages": distribution(p["age"] for p in retirements), "actual_retirements": len(retired),
               "league_exits": len(saved.get("league_exit_player_ids", [])),
               "mature_2027_2030_cohorts": cohort_bands,
               "validation": {"complete_seasons": 10, "regular_games": 12300, "draft_picks": len(rookies),
                              "unique_development_records": len(event_by_id), "missing_rookie_summer_records": missing,
                              "retirement_records_reconciled": True, "min_roster_size": min(snaps[-1]["roster_counts_by_team"].values())}}
        assert sha(path) == before_hash
        result["completed"][seed] = row
        print(seed, json.dumps({"start": annual[0], "end": annual[-1], "new_stars": len(generated_stars),
                               "retirement_ages": row["retirement_ages"], "cohorts": cohort_bands,
                               "validation": row["validation"]}), flush=True)
        del saved, events, event_by_id, cohorts, snaps
        gc.collect()
    check_protection()
    check_inputs()
    write(OUT / "overnight/morning-review.json", result)
    print("Saved morning-review.json", flush=True)


if __name__ == "__main__":
    main()
