"""Resume the captured stalled 2029 draft on a disposable copy, preserving its prefix."""
import json

from long_term_health import OUT, ROOT, canonical, check_protection, fingerprints, sha, write
from nba_gm_data.app_actions import dispatch_app_action
from nba_gm_data.save import load_save
from nba_gm_data.save_recovery import create_export, restore_export


def verify():
    directory = OUT / "draft-slot-repair-final"
    path = directory / "saves/replay.json"
    if path.exists():
        raise FileExistsError("Repair replay exists; preserve the original evidence")
    source = json.loads((OUT / "career-913/run.json").read_text())["save_path"]
    source_hash = sha(source)
    before = load_save(source)
    assert before["state"]["current_date"] == "2029-06-25"
    assert before["draft_state"]["current_index"] == 24
    path.parent.mkdir(parents=True, exist_ok=True)
    archive = create_export(source)
    (directory / "input.nbagm.zip").write_bytes(archive)
    restore_export(path, archive)
    baseline = canonical()
    result = dispatch_app_action("draft_sim_all", {"save_path": str(path), "team": "GSW", "year": "2029", "seed": 913},
                                 root=ROOT, save_dir=path.parent, canonical=baseline)
    after = load_save(path)
    assert result["status"] == "simulated", result
    assert after["draft_state"]["status"] == "completed"
    assert after["state"]["current_date"] == "2029-06-25"
    assert after["draft_state"]["applied_selection_ids"][:24] == before["draft_state"]["applied_selection_ids"]
    for key in ("generated_players", "generated_traits"):
        original = {r["id"]: r for r in before[key]}
        updated = {r["id"]: r for r in after[key]}
        assert all(updated[pid] == row for pid, row in original.items()), key
    for pid, contract in before["contract_overrides"].items():
        assert after["contract_overrides"][pid] == contract, pid
    cohort = [r for r in after["incoming_rookies"] if str(r["draft_year"]) == "2029"]
    order = after["draft_orders"]["2029"]["draft_order"]
    assert len(cohort) == len({r["player_id"] for r in cohort}) == len(order) == 59
    assert {r["overall_pick"] for r in cohort} == {r["overall_pick"] for r in order}
    counts = {k: len(after[k]) for k in ("incoming_rookies", "generated_players", "generated_traits", "rookie_contracts")}
    again = dispatch_app_action("draft_sim_all", {"save_path": str(path), "team": "GSW", "year": "2029", "seed": 913},
                                root=ROOT, save_dir=path.parent, canonical=baseline)
    repeated = load_save(path)
    assert {k: len(repeated[k]) for k in counts} == counts
    assert repeated["draft_state"]["applied_selection_ids"] == after["draft_state"]["applied_selection_ids"]
    assert sha(source) == source_hash
    check_protection()
    report = {"status": "passed", "source_hashes": fingerprints(), "source_save_sha256": source_hash,
              "source": source, "date": after["state"]["current_date"], "eligible_selections": len(order),
              "previously_applied": 24, "newly_applied": result["result"]["applied_count"],
              "prefix_preserved": True, "original_players_traits_contracts_preserved": True,
              "repeat_did_not_duplicate_records": True, "input_archive_sha256": sha(directory / "input.nbagm.zip")}
    write(directory / "verification.json", report)
    print(json.dumps({k: v for k, v in report.items() if k != "source_hashes"}, indent=2), flush=True)


if __name__ == "__main__":
    verify()
