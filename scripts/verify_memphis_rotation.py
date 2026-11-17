"""Reproduce traded-player minute loss using disposable copies of Memphis."""
import argparse
from datetime import date, timedelta
import json
from pathlib import Path
from unittest.mock import patch

from nba_gm_data import save as sv
from nba_gm_data.app_actions import dispatch_app_action, load_app_canonical
from nba_gm_data.history_store import load_history_records
from nba_gm_data.save_recovery import create_export, restore_export
from long_term_health import sha, write
from verify_simulation_consistency import business_state, digest

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "output/memphis-rotation-fix-2026-10-24"
SOURCE = ROOT / "output/history-performance-2026-10-24/preview/disposable-saves/mem_1101441579.json"
STAR_IDS = ["player_mia-giannis-antetokounmpo", "player_mia-bam-adebayo", "player_mia-andrew-wiggins"]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("stage", choices=("before", "after"))
    parser.add_argument("--label", default="")
    args = parser.parse_args()
    OUT.mkdir(parents=True, exist_ok=True)
    source_hash = sha(SOURCE)
    canonical = load_app_canonical(ROOT)
    fixture = OUT / "controlled-input.nbagm.zip"
    if args.stage == "before":
        assert not fixture.exists()
        original = create_export(SOURCE)
        (OUT / "original-copy.nbagm.zip").write_bytes(original)
        path = OUT / "setup.json"
        restore_export(path, original)
        saved = sv.load_save(path)
        active = sv.canonical_with_save(canonical, saved)
        roster = [p for p in active["players"] if p.get("team_id") == "team_mem"]
        requested = {p["id"]: 0 for p in roster}
        for pid in STAR_IDS:
            requested[pid] = 32
        for name, value in (("Cam Spencer", 32), ("Cedric Coward", 26), ("Scotty Pippen Jr.", 20),
                            ("Grayson Allen", 26), ("Malik Monk", 20), ("Cameron Boozer", 20)):
            requested[next(p["id"] for p in roster if p["name"] == name)] = value
        assert sum(requested.values()) == 240
        # A zero-minute bench injury must never erase healthy traded starters.
        # This controlled injury is added only to the disposable test fixture.
        bench = next(h for h in saved["health_states"] if h["player_id"] == "player_mem-javon-small")
        bench.update(availability_status="out", current_injury_id="rotation_test_bench_injury",
                     return_date="2027-02-10", days_left=11)
        sv.write_save(path, saved)
        fixture.write_bytes(create_export(path))
        write(OUT / "fixture.json", {"source_hash": source_hash, "requested": requested,
              "source_date": saved["state"]["current_date"],
              "note": "Requested 32 MPG for each traded star is a controlled test, not a claim to recover the user's lost exact settings. Bench injury exists only in the copied fixture."})
    config = json.loads((OUT / "fixture.json").read_text())
    requested = config["requested"]
    report = {"stage": args.stage, "source_hash": source_hash, "cases": {}}
    states = {}
    for mode in (["bulk"] if args.stage == "before" else ["daily", "bulk"]):
        directory = OUT / (args.stage + args.label) / mode
        directory.mkdir(parents=True, exist_ok=False)
        path = directory / "disposable.json"
        restore_export(path, fixture.read_bytes())
        saved = sv.load_save(path)
        before_games = set(saved["schedule_state"]["simulated_game_ids"])
        result = dispatch_app_action("set_rotation_minutes", {"save_path": str(path), "team": "MEM",
            "minutes": requested, "locked_player_ids": [pid for pid, value in requested.items() if value]},
            root=ROOT, save_dir=directory, canonical=canonical)
        saved = sv.load_save(path)
        submitted = {pid: saved["rotation_overrides"]["team_mem"].get(pid) for pid in STAR_IDS}
        dashboard = {p["id"]: p for p in result["dashboard"]["rotation"]}
        row = {"after_submit": submitted,
               "dashboard": {pid: dashboard[pid]["rotation_target_minutes"] for pid in STAR_IDS}}
        target = (date.fromisoformat(config["source_date"]) + timedelta(days=5)).isoformat()
        current = config["source_date"]
        game_inputs = {}
        simulate = sv.sim_game_with_context

        def observe(context, *positional, **keywords):
            result = simulate(context, *positional, **keywords)
            if "team_mem" in (result.home_team_id, result.away_team_id):
                game_inputs[result.game_id] = {p["id"]: p["minutes_projection"] for p in context["canonical"]["players"]
                                               if p.get("team_id") == "team_mem"}
            return result

        with patch.object(sv, "sim_game_with_context", side_effect=observe):
            while current < target:
                payload = {"days": 1} if mode == "daily" else {"to_date": target, "checkpoint_days": 31}
                dispatch_app_action("advance_save", {**payload, "save_path": str(path), "seed": 1101441579},
                                    root=ROOT, save_dir=directory, canonical=canonical)
                saved = sv.load_save(path)
                current = saved["state"]["current_date"]
        fresh_ids = set(saved["schedule_state"]["simulated_game_ids"]) - before_games
        all_games = [*load_history_records(path, saved, "game_results"), *saved["game_results"]]
        games = {g["game_id"]: g for g in all_games if g["game_id"] in fresh_ids
                 and "team_mem" in (g["home_team_id"], g["away_team_id"])}
        row.update(end_date=current, boxes={gid: {line["player_id"]: line["minutes"] for line in game["player_lines"]
                     if line["player_id"] in STAR_IDS} for gid, game in games.items()},
                   game_inputs={gid: {pid: values.get(pid, 0) for pid in STAR_IDS} for gid, values in game_inputs.items()},
                   final_targets={pid: saved["rotation_overrides"]["team_mem"].get(pid) for pid in STAR_IDS})
        states[mode] = business_state(sv.load_save(path, include_history=True))
        if args.stage == "after":
            assert submitted == {pid: 32 for pid in STAR_IDS}, row
            assert all(row["dashboard"][pid] == 32 for pid in STAR_IDS), row
            assert set(STAR_IDS) <= saved["rotation_overrides"]["team_mem"].keys(), row
            assert row["final_targets"] == {pid: 32 for pid in STAR_IDS}, row
            assert games, "The interval must actually include Memphis games"
            for gid, game in games.items():
                overtime = max(int(team.get("overtime_periods") or 0) for team in game["team_lines"])
                lines = {line["player_id"]: line["minutes"] for line in game["player_lines"] if line.get("team_id") == "team_mem"}
                assert abs(sum(lines.values()) - (240 + 25 * overtime)) < .15
                for pid, expected in game_inputs[gid].items():
                    actual = lines.get(pid, 0)
                    if expected == 0:
                        assert actual == 0, (gid, pid, expected, actual)
                    else:
                        assert abs(actual - expected) <= 4 + 5 * overtime, (gid, pid, expected, actual)
        report["cases"][mode] = row
        print(mode, json.dumps(row), flush=True)
    if args.stage == "after":
        assert states["daily"] == states["bulk"]
        report["daily_bulk_equal"] = True
    report["business_digests"] = {mode: digest(state) for mode, state in states.items()}
    assert sha(SOURCE) == source_hash, "The user's save changed during verification; do not overwrite it"
    report["original_manifest_unchanged"] = True
    write(OUT / f"{args.stage}{args.label}-report.json", report)


if __name__ == "__main__":
    main()
