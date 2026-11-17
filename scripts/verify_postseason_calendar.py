"""Exercise real app actions and game simulation on isolated postseason saves."""
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import time

from nba_gm_data import save as sv
from nba_gm_data.app_actions import dispatch_app_action, load_app_canonical
from nba_gm_data.save_recovery import create_export, restore_export

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "output/postseason-calendar-2026-10-24"


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    canonical = load_app_canonical(ROOT)
    directory = OUT / "saves"
    directory.mkdir(exist_ok=True)
    initial = directory / "entry.json"
    if not initial.exists():
        save = sv.create_league_save(ROOT, canonical, "MEM", initial, seed=17)
        sv.set_save_date_phase(save, "2027-04-12")
        save["lifecycle_state"] = {"through_date":"2027-04-12", "health_game_ids":[]}
        save["pending_roster_cutdowns"] = []
        for i, team in enumerate(canonical["teams"]):
            save["team_records"][team["id"]].update(wins=60-i, losses=22+i)
        sv.write_save(initial, save)
    else:
        assert not sv.load_save(initial).get("playoff_state", {}).get("games"), "Entry fixture was played; do not overwrite it."

    def action(path, **payload):
        start = time.monotonic()
        result = dispatch_app_action("advance_save", {"save_path":str(path), **payload},
                                     root=ROOT, save_dir=directory, canonical=canonical)
        print(path.stem, result["home"]["save"]["current_date"], result["status"],
              result["result"].get("games_simulated"), round(time.monotonic()-start, 2), flush=True)
        return result

    checkpoint = action(initial, days=8)
    assert checkpoint["status"] == "postseason"
    save = sv.load_save(initial)
    assert not save["playoff_state"]["games"]
    room = dispatch_app_action("playoff_room", {"save_path":str(initial)}, root=ROOT, save_dir=directory, canonical=canonical)
    assert len(room["series"]) == 8 and all(s["score"] == [0,0] for s in room["series"])
    dashboard = sv.team_dashboard(ROOT, canonical, initial, "MEM")
    assert all(p["games"] == 0 and p["display_mpg"] == 0 for p in dashboard["rotation"])
    fixture = create_export(initial)
    states = {}
    report = {"checkpoint":checkpoint["postseason_checkpoint"], "initial_series":len(room["series"]), "modes":{}}
    for mode in ("daily", "bulk"):
        path = directory / f"{mode}-{time.time_ns()}.json"
        restore_export(path, fixture)
        if mode == "daily":
            action(path, next_event=True, postseason_confirmed="2027-04-13")
            for day in range(14, 21):
                action(path, to_date=f"2027-04-{day:02d}")
        else:
            action(path, days=7, postseason_confirmed="2027-04-13")
        saved = sv.load_save(path)
        state = {key:deepcopy(saved.get(key)) for key in (
            "state", "playoff_state", "playoff_player_stats", "player_season_stats", "health_states",
            "development_events", "rotation_overrides", "ai_role_assignments", "team_records",
            "roster_overrides", "contract_overrides", "lifecycle_state")}
        states[mode] = state
        games = saved["playoff_state"]["games"]
        assert len([g for g in games if g["gameDate"] < "2027-04-18"]) == 6
        assert len(games) == 22
        assert all(row["games"] > 0 for row in saved["playoff_player_stats"].values() if row["minutes"] > 0)
        assert sum(row["points"] for row in saved["playoff_player_stats"].values()) > 0
        for team in ("East", "West"):
            participant = saved["playoff_state"]["play_in"][team]["teams"]["7"]
            dash = sv.team_dashboard(ROOT, canonical, path, participant)
            assert max(p["games"] for p in dash["rotation"]) >= 1
            assert max(p["points_per_game"] for p in dash["rotation"]) > 0
        report["modes"][mode] = {"date":saved["state"]["current_date"], "games":len(games),
            "stat_rows":len(saved["playoff_player_stats"]),
            "state_digest":hashlib.sha256(json.dumps(state, sort_keys=True).encode()).hexdigest()}
    report["daily_bulk_equal"] = states["daily"] == states["bulk"]
    (OUT / "verification.json").write_text(json.dumps(report, indent=2))
    assert report["daily_bulk_equal"], "Real engine daily/bulk mismatch; inspect saved copies."
    print(json.dumps(report, indent=2), flush=True)


if __name__ == "__main__":
    main()
