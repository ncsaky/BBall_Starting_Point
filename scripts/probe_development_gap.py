"""Reconstruct the flagged rookie's July skill calculation without save writes."""
from copy import deepcopy
import json
from pathlib import Path
from unittest.mock import patch

from long_term_health import OUT, sha, write
from nba_gm_data import health
from nba_gm_data.history_store import load_history_records
from nba_gm_data.save import load_save

ROOT = Path(__file__).resolve().parents[1]
DEST = ROOT / "output/development-retention-diagnosis-2026-10-24"
PID = "rookie_player_2027-team-atl-dajuan-bennett"


def main():
    run = json.loads((OUT / "career-71/run.json").read_text())
    path = run["save_path"]
    digest = sha(path)
    saved = load_save(path)
    events = load_history_records(path, saved, "development_events") + saved["development_events"]
    player = deepcopy(next(p for p in saved["generated_players"] if p["id"] == PID))
    traits = deepcopy([t for t in saved["generated_traits"] if t["player_id"] == PID])
    team_july = next(e for e in events if e["month"] == "2027-07" and e["team_id"] == player["team_id"])
    # Generated traits retain entry values; development is a separate ledger.
    assert all(t["value"] == round(t["components"]["career_capacity"]["entry_value"], 2) for t in traits)
    injuries = [e for e in saved.get("injury_events", []) if e.get("player_id") == PID]
    assert not injuries, "Historical health requires a separate reconstruction"
    context = {"players": [player], "traits": traits}
    deltas = {}
    calculate = health.monthly_trait_delta

    def record(*args, **kwargs):
        value = calculate(*args, **kwargs)
        deltas[args[1]] = value
        return value

    with patch.object(health, "coach_development_by_team", return_value={}), \
            patch.object(health, "development_staff_modifiers", return_value=team_july["staff_context"]), \
            patch.object(health, "monthly_trait_delta", side_effect=record):
        result = health.advance_development(context, "2027-07", seed=71)
    report = {"player": player, "traits": traits, "staff_context": team_july["staff_context"],
              "source_save": path, "source_sha256": digest, "month": "2027-07", "seed": 71,
              "reconstruction_scope": "Entry trait values, generated age/role, same-team archived July staff context, no recorded injury. Not a full replay of the season.",
              "raw_deltas": deltas, "max_abs_raw_delta": max(abs(v) for v in deltas.values()),
              "result": result,
              "existing_months": sorted({e["month"] for e in events if e["player_id"] == PID})}
    assert len(deltas) == 15
    assert sha(path) == digest
    write(DEST / ("gap-probe-after.json" if result["event_count"] else "gap-probe.json"), report)
    print(json.dumps({k: v for k, v in report.items() if k not in {"player", "traits", "staff_context"}}, indent=2))


if __name__ == "__main__":
    main()
