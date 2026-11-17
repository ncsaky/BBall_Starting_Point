"""Verify repaired feeder pairings on a disposable export of the Memphis save."""
import hashlib
import json
from pathlib import Path
import time

from nba_gm_data import save as sv
from nba_gm_data.app_actions import dispatch_app_action, load_app_canonical, playoff_room_payload
from nba_gm_data.save_locking import save_lock
from nba_gm_data.save_recovery import create_export, restore_export

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "output/history-performance-2026-10-24/preview/disposable-saves/mem_1101441579.json"
OUT = ROOT / "output/playoff-bracket-flow-2026-10-24"


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    directory = OUT / "saves"
    directory.mkdir(exist_ok=True)
    path = directory / f"memphis-unplayed-{time.time_ns()}.json"
    canonical = load_app_canonical(ROOT)
    with save_lock(SOURCE):
        source_hash = hashlib.sha256(SOURCE.read_bytes()).hexdigest()
        archive = create_export(SOURCE)
    restore_export(path, archive)
    before = sv.load_save(path)
    first = [s for s in before["playoff_state"]["series"] if s["round"] == "first_round"]
    semis = [s for s in before["playoff_state"]["series"] if s["round"] == "conference_semifinals"]
    assert len(semis) == 4 and all(not s.get("game_ids") for s in semis)
    expected = []
    for conf in ("East", "West"):
        sources = [s for s in first if s["conference"] == conf]
        expected.extend(frozenset(s["winner_team_id"] for s in sources[i:i+2]) for i in (0,2))
    manifest_before = path.read_bytes()
    preview = playoff_room_payload(canonical, path)
    preview_pairs = [frozenset(s["team_ids"]) for s in preview["series"] if s["round"] == "conference_semifinals"]
    assert preview_pairs == expected
    assert path.read_bytes() == manifest_before, "A bracket read must not write the save."
    result = dispatch_app_action("advance_save", {"save_path":str(path), "postseason_sim":"game", "next_event":True},
                                 root=ROOT, save_dir=directory, canonical=canonical)
    after = sv.load_save(path)
    played_semis = [s for s in after["playoff_state"]["series"] if s["round"] == "conference_semifinals"]
    assert [frozenset(s["team_ids"]) for s in played_semis] == expected
    assert all(len(s["game_ids"]) == 1 for s in played_semis)
    assert first == [s for s in after["playoff_state"]["series"] if s["round"] == "first_round"]
    assert result["result"]["games_simulated"] == 4
    report = {"from":before["state"]["current_date"], "through":after["state"]["current_date"],
              "before_pairings":[s["team_ids"] for s in semis], "after_pairings":[s["team_ids"] for s in played_semis],
              "source_series_ids":[s["source_series_ids"] for s in played_semis], "games_played":4,
              "previous_first_round_unchanged":True, "preview_read_did_not_write":True,
              "source_sha256_before":source_hash,
              "source_sha256_after":hashlib.sha256(SOURCE.read_bytes()).hexdigest()}
    (OUT / "engine-verification.json").write_text(json.dumps(report, indent=2))
    print(json.dumps(report, indent=2), flush=True)


if __name__ == "__main__":
    main()
