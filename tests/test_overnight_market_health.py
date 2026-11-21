"""Safety and measurement checks for the standalone overnight experiment."""
from copy import deepcopy
import json
from pathlib import Path
import sys
import tempfile
import unittest
from types import SimpleNamespace
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import overnight_market_health as audit


class OvernightMarketHealthTests(unittest.TestCase):
    def test_disk_monitor_tolerates_disappearing_wal_files(self):
        stable = unittest.mock.Mock()
        stable.stat.return_value = SimpleNamespace(st_size=1234, st_mode=0o100644)
        vanished = unittest.mock.Mock()
        vanished.stat.side_effect = FileNotFoundError("closed SQLite WAL")
        directory = unittest.mock.Mock()
        directory.stat.return_value = SimpleNamespace(st_size=500, st_mode=0o040755)
        root = unittest.mock.Mock()
        root.rglob.return_value = [stable, vanished, directory]
        self.assertEqual(audit.directory_bytes(root), 1234)

    def test_disk_monitor_does_not_hide_real_permission_failures(self):
        entry = unittest.mock.Mock()
        entry.stat.side_effect = PermissionError("unreadable audit storage")
        root = unittest.mock.Mock()
        root.rglob.return_value = [entry]
        with self.assertRaises(PermissionError):
            audit.directory_bytes(root)

    def save(self, phase="regular_season", stamp="2027-01-01"):
        return {"meta": {"season": "2026-27"}, "state": {"phase": phase, "current_date": stamp},
                "team_records": {str(i): {"wins": 41, "losses": 41} for i in range(30)}}

    def test_refuses_playable_or_parent_output_paths(self):
        with self.assertRaises(ValueError):
            audit.output_path(audit.ROOT / "saves")
        with self.assertRaises(ValueError):
            audit.output_path(audit.ROOT / "output")
        out = audit.ROOT / "output/test-market"
        with self.assertRaises(ValueError):
            audit.safe_save_path(out, audit.ROOT / "saves/memphis.json")
        self.assertEqual(audit.safe_save_path(out, out / "career-17/saves/a.json"),
                         out / "career-17/saves/a.json")

    def test_free_agency_is_observed_daily_then_final_cleanup(self):
        saved = self.save("free_agency", "2027-07-01")
        saved["free_agency_state"] = {"status": "active"}
        # FA-REAL slice 3 (rule changed): hands-off, the GM takes the assistant's advice on a rival's offer sheet.
        self.assertEqual(audit.select_action(saved, "2036-10-01"),
                         ("advance_free_agency", {"mode": "day", "team": "GSW", "follow_advice": True}))
        saved["free_agency_state"]["status"] = "completed"
        self.assertEqual(audit.select_action(saved, "2036-10-01")[1]["mode"], "end")

    def test_postseason_entry_and_exit_are_explicit(self):
        saved = self.save("playoffs", "2027-04-13")
        action, payload = audit.select_action(saved, "2036-10-01")
        self.assertEqual(action, "advance_save")
        self.assertEqual(payload["postseason_sim"], "all")
        self.assertEqual(payload["postseason_confirmed"], "2027-04-13")
        with patch.object(audit, "postseason_exit_required", return_value=True):
            self.assertEqual(audit.select_action(saved, "2036-10-01"),
                             ("advance_save", {"postseason_exit": True}))

    def test_revealed_lottery_enters_draft_without_repeating_reveal(self):
        saved = self.save("draft_lottery", "2027-06-22")
        before = audit.marker(saved)
        self.assertEqual(audit.select_action(saved, "2036-10-01")[0], "draft_reveal_lottery")
        saved["draft_orders"] = {"2027": {"draft_order": []}}
        self.assertNotEqual(audit.marker(saved), before)
        self.assertEqual(audit.select_action(saved, "2036-10-01"), ("advance_save", {"draft_enter": True}))

    def test_second_completed_draft_is_progress_even_with_same_index_status_and_date(self):
        before = self.save("draft", "2028-06-25")
        before["draft_state"] = {"year": "2027", "current_index": 60, "status": "completed"}
        before["incoming_rookies"] = [{"player_id": str(i)} for i in range(60)]
        after = deepcopy(before)
        after["draft_state"]["year"] = "2028"
        after["incoming_rookies"] += [{"player_id": f"new-{i}"} for i in range(60)]
        self.assertNotEqual(audit.marker(before), audit.marker(after))
        self.assertEqual(audit.marker(after), audit.marker(deepcopy(after)))

    def test_month_advances_stop_at_deadline_and_endpoint(self):
        saved = self.save(stamp="2027-02-01")
        self.assertEqual(audit.select_action(saved, "2036-10-01")[1]["to_date"], "2027-02-05")
        saved["state"]["current_date"] = "2027-02-05"
        self.assertEqual(audit.select_action(saved, "2036-10-01")[1]["trade_deadline_confirmed"], "2027-02-05")
        saved["state"]["current_date"] = "2027-01-01"
        self.assertEqual(audit.select_action(saved, "2027-01-08")[1]["to_date"], "2027-01-08")

    def test_completed_season_camp_requires_next_event_not_a_date_jump(self):
        saved = self.save("training_camp", "2027-09-01")
        self.assertEqual(audit.select_action(saved, "2036-10-01"),
                         ("advance_save", {"next_event": True}))
        saved["state"]["current_date"] = "2026-09-01"
        self.assertEqual(audit.select_action(saved, "2036-10-01"),
                         ("advance_save", {"to_date": "2026-10-01"}))

    def test_calendar_cannot_silently_run_a_second_year_of_the_same_season(self):
        saved = self.save("preseason", "2027-10-01")
        with self.assertRaisesRegex(RuntimeError, "without a real season rollover"):
            audit.validate_season_clock(saved)
        saved["meta"]["season"] = "2027-28"
        audit.validate_season_clock(saved)

    def test_rollover_requires_history_advance_and_reset_records(self):
        before = self.save("training_camp", "2027-09-01")
        after = deepcopy(before)
        after["state"]["current_date"] = "2027-10-01"
        with self.assertRaisesRegex(RuntimeError, "expected new season"):
            audit.validate_rollover(before, after)
        after["meta"]["season"] = "2027-28"
        after["season_history"] = [{"team_records": deepcopy(before["team_records"])}]
        with self.assertRaisesRegex(RuntimeError, "reset new-season team records"):
            audit.validate_rollover(before, after)
        after["team_records"] = {str(i): {"wins": 0, "losses": 0} for i in range(30)}
        audit.validate_rollover(before, after)

    def test_premium_no_bid_diagnostic_does_not_confuse_rejections_with_no_interest(self):
        active = {"players": [{"id": "p", "age": 23}], "teams": [{"id": "t", "abbrev": "T"}]}
        saved = self.save("free_agency", "2027-07-05")
        saved.update(free_agent_player_ids=["p"], free_agent_offers=[], free_agency_state={
            "season": "2026-27", "day": 5, "player_asks_millions": {"p": 20}})
        snap = {"date": "2027-07-05", "players": [{"id": "p", "name": "Young starter", "age": 23,
                "display": 86, "fixed24_engine": 68, "rostered": False}]}
        with patch.object(audit, "team_cap_summary", return_value={}), \
                patch.object(audit.play, "signing_cap_check", return_value={"ok": True}), \
                patch.object(audit.play, "extension_safe_year_limit", return_value=4):
            result = audit.market_snapshot(active, saved, snap)
            row = result["players"][0]
            self.assertEqual(row["teams_with_room_and_slots_at_ask"], ["t"])
            self.assertEqual(row["diagnosis"], "never_bid_on_despite_room_candidate")
            saved["free_agent_offers"] = [{"id": "old", "player_id": "p", "team_id": "t",
                                           "status": "rejected", "season": "2026-27"}]
            row = audit.market_snapshot(active, saved, snap)["players"][0]
            self.assertEqual(row["active_bids"], 0)
            self.assertEqual(row["historical_bids"], 1)
            self.assertEqual(row["diagnosis"], "prior_interest_or_rejections")

    def test_compressed_checkpoint_round_trip(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "snapshot.json.gz"
            value = {"players": [{"id": "p", "fixed24_engine": 63.5}]}
            audit.write_gzip(path, value)
            self.assertEqual(audit.read_gzip(path), value)
            self.assertFalse(path.with_name(path.name + ".tmp").exists())


if __name__ == "__main__":
    unittest.main()
