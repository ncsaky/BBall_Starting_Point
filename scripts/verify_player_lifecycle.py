"""Real GUI-action postseason/offseason parity using copies of disposable audits."""
from __future__ import annotations

import argparse
from collections import Counter
import gc
import hashlib
import json
from pathlib import Path
import time
from contextlib import nullcontext
from unittest.mock import patch

from nba_gm_data.app_actions import dispatch_app_action, load_app_canonical
from nba_gm_data.history_store import load_history_records
from nba_gm_data.save import canonical_with_save, load_save
from nba_gm_data.save_recovery import create_export, restore_export
from ten_season_soak import SoakRunner

ROOT = Path(__file__).resolve().parents[1]


def normalize(value):
    if isinstance(value, dict):
        return {k: normalize(v) for k, v in value.items() if k not in {"created_at", "updated_at", "save_path", "revision"}}
    if isinstance(value, list):
        return [normalize(v) for v in value]
    return value


def digest(value):
    return hashlib.sha256(json.dumps(normalize(value), sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def meaningful(canonical, path):
    saved = load_save(path)
    active = canonical_with_save(canonical, saved)
    keys = ("state", "health_states", "injury_events", "development_trait_totals", "applied_development_months", "generated_health_profiles", "roster_overrides", "contract_overrides", "free_agent_player_ids", "playoff_state", "playoff_player_stats", "free_agency_state", "transaction_logs", "generated_players", "generated_traits", "game_results")
    return {**{key: saved.get(key) for key in keys}, "players": active["players"], "traits": active["traits"], "contracts": active["contracts"]}


def run(out, seed, postseason_dir=None):
    folder = out / f"seed{seed}"
    folder.mkdir(parents=True, exist_ok=True)
    source = ROOT / f"output/transaction-realism-audit/fixed-seed{seed}/phase_saves/season_01_playoffs.json"
    checkpoint_source = Path(postseason_dir) / f"seed{seed}/postseason.json" if postseason_dir else None
    if checkpoint_source and checkpoint_source.exists():
        source = checkpoint_source.resolve()
    paths = {mode: folder / f"{mode}.json" for mode in ("bulk", "daily")}
    if any(p.exists() for p in paths.values()):
        raise FileExistsError("Use a new output directory; verification never replaces a previous run")
    source_hash = hashlib.sha256(source.read_bytes()).hexdigest()
    archive = create_export(source)
    for path in paths.values():
        restore_export(path, archive)
    canonical = load_app_canonical(ROOT)
    report = {"seed": seed, "source": str(source), "source_sha256": source_hash,
              "lottery_policy": "Identical controlled lottery draw in both branches; production deliberately uses SystemRandom on reveal.",
              "source_hashes": {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in (ROOT / "src/nba_gm_data").glob("*.py")},
              "comparisons": [], "actions": []}
    started = time.monotonic()

    def checkpoint():
        (folder / "verification.json").write_text(json.dumps(report, indent=2, sort_keys=True) + "\n")

    def action(branch, name, **payload):
        tick = time.monotonic()
        with patch("nba_gm_data.save.lottery_seed", return_value=seed) if name == "draft_reveal_lottery" else nullcontext():
            result = dispatch_app_action(name, {"save_path": paths[branch], "seed": seed, **payload}, root=ROOT, save_dir=folder, canonical=canonical)
        report["actions"].append({"mode": branch, "action": name, "date": load_save(paths[branch])["state"]["current_date"], "status": result.get("status"), "seconds": round(time.monotonic() - tick, 3)})
        checkpoint()
        print(seed, branch, name, report["actions"][-1]["date"], flush=True)
        return result

    def compare(label):
        a, b = (meaningful(canonical, paths[m]) for m in ("bulk", "daily"))
        differences = [k for k in a if digest(a[k]) != digest(b[k])]
        report["comparisons"].append({"stage": label, "equal": not differences, "differing_fields": differences, "hashes": {k: digest(a[k]) for k in a}})
        checkpoint()
        if differences:
            raise AssertionError(f"{label} differs: {differences}")

    if load_save(paths["bulk"]).get("playoff_state", {}).get("status") == "completed":
        prior = json.loads((source.parent / "verification.json").read_text())
        evidence = next(c for c in prior["comparisons"] if c["stage"] == "playoffs_all_vs_day_with_reload" and c["equal"])
        report["prior_postseason_verification"] = {"report": str(source.parent / "verification.json"), "comparison": evidence, "source_hashes": prior["source_hashes"]}
        compare("verified_postseason_checkpoint_copies")
    else:
        action("bulk", "simulate_playoff_all")
        for _ in range(40):
            if load_save(paths["daily"]).get("playoff_state", {}).get("status") == "completed":
                break
            action("daily", "simulate_playoff_game")
        else:
            raise AssertionError("Playoffs did not finish")
        compare("playoffs_all_vs_day_with_reload")
    restore_export(folder / "postseason.json", create_export(paths["bulk"]))
    for mode in paths:
        action(mode, "draft_reveal_lottery", year="2027", team="DET")
        action(mode, "draft_sim_all", year="2027", team="DET")
        action(mode, "advance_save", to_date="2027-06-27")
    compare("identical_lottery_and_draft")
    restore_export(folder / "re_signing.json", create_export(paths["bulk"]))
    action("bulk", "advance_re_signing", mode="open_market", team="DET")
    action("daily", "advance_re_signing", mode="day", team="DET")
    action("daily", "advance_re_signing", mode="open_market", team="DET")
    compare("re_signing_jump_vs_day")
    restore_export(folder / "free_agency.json", create_export(paths["bulk"]))
    action("bulk", "advance_free_agency", mode="end", team="DET")
    for _ in range(5):
        action("daily", "advance_free_agency", mode="day", team="DET")
    action("daily", "advance_free_agency", mode="end", team="DET")
    compare("free_agency_end_vs_days")
    for mode in paths:
        runner = SoakRunner(argparse.Namespace(root=str(ROOT), output_dir=str(folder), seed=seed, team="DET"))
        runner.canonical = canonical
        runner.payload["save_path"] = str(paths[mode])
        runner.save_dir = folder
        runner.resolve_user_roster_cutdown()
        runner.resolve_user_staff_retention()
        action(mode, "advance_save", next_event=True)
    compare("rollover")
    report["human_cutdowns_at_rollover"] = load_save(paths["bulk"]).get("pending_roster_cutdowns", [])
    for mode in paths:
        runner.payload["save_path"] = str(paths[mode])
        runner.resolve_user_roster_cutdown()
        runner.resolve_user_staff_retention()
        action(mode, "advance_save", to_date="2027-10-21")
    compare("opening_night_after_identical_user_cutdowns")
    saved = load_save(paths["bulk"])
    assert saved["state"]["current_date"] == "2027-10-21", saved["state"]
    assert saved["state"]["phase"] == "regular_season", saved["state"]
    active = canonical_with_save(canonical, saved)
    months = {e["month"] for e in [*load_history_records(paths["bulk"], saved, "development_events"), *saved.get("development_events", [])]}
    expected = {f"2027-{m:02}" for m in range(5, 11)}
    assert expected <= months, (expected - months)
    generated = {p["id"] for p in saved["generated_players"]}
    profiles = {p["player_id"] for p in active["player_health_profiles"]}
    assert generated <= profiles
    roster = Counter(p["team_id"] for p in active["players"] if p.get("team_id") and not p.get("_inactive_player"))
    assert max(roster.values()) <= 15, roster
    assert hashlib.sha256(source.read_bytes()).hexdigest() == source_hash
    report.update(status="passed", seconds=round(time.monotonic() - started, 3), newly_covered_months=sorted(expected), generated_players=len(generated), generated_missing_health_profiles=len(generated - profiles), max_roster=max(roster.values()))
    checkpoint()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", required=True)
    parser.add_argument("--seeds", default="17,29")
    parser.add_argument("--postseason-dir", help="Reuse an audit-owned postseason snapshot with recorded successful parity evidence when present")
    args = parser.parse_args()
    out = Path(args.output).resolve()
    if ROOT / "saves" == out or ROOT / "saves" in out.parents:
        raise ValueError("Output cannot be inside playable saves")
    gc.disable()
    for seed in map(int, args.seeds.split(",")):
        run(out, seed, args.postseason_dir)
