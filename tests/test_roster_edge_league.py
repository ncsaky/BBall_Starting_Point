"""FA-REAL slice 4 on a real new career: the real opening-night two-ways, the opening-roster window's answer, and the
user's actions (camp invite, two-way signing and conversion, roster submission) through the app's action boundary."""
from __future__ import annotations

import shutil
import tempfile
import unittest
from pathlib import Path

from nba_gm_data import camp, save as sv, two_way
from nba_gm_data.app_actions import dispatch_app_action, load_app_canonical

ROOT = Path(__file__).resolve().parents[1]


class RosterEdgeLeague(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = Path(tempfile.mkdtemp())
        cls.canonical = load_app_canonical(ROOT)
        result = dispatch_app_action("create_save", {"team": "GSW", "seed": 17, "save_name": "edge"},
                                     root=ROOT, save_dir=cls.tmp, canonical=cls.canonical)
        cls.path = Path(result.get("save_path") or result.get("save"))

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.tmp, ignore_errors=True)

    def act(self, name, **payload):
        return dispatch_app_action(name, {"save_path": str(self.path), **payload}, root=ROOT, save_dir=self.tmp,
                                   canonical=self.canonical)

    def test_real_opening_two_ways_and_the_roster_window(self):
        saved = sv.load_save(self.path)
        records = two_way.contracts(saved)
        self.assertGreaterEqual(len(records), 80, "the real 2026-27 opening two-ways (83 on 30 teams)")
        self.assertTrue(all(saved["roster_overrides"].get(pid) is None for pid in records), "off the 15")
        pool = set(saved.get("free_agent_player_ids") or [])
        released = saved.get("released_free_agents") or {}
        self.assertFalse(pool & set(records), "two-way players are not free agents")
        self.assertFalse(set(released) & set(records), "nor lost roster cuts")
        active = sv.canonical_with_save(self.canonical, saved)
        for team in active["teams"]:
            self.assertLessEqual(two_way.standard_roster_count(active, saved, team["id"]), 15)
        room = self.act("roster_cutdown")
        self.assertIn(room["status"], {"clear", "required", "short"})
        self.assertEqual(room["roster"]["two_way_limit"], 3)
        self.assertEqual(len(room["roster"]["two_ways"]), len(two_way.team_two_ways(saved, "team_gsw")))
        self.assertTrue(all("guarantee" in row and "clears_waivers" in row for row in room["players"]))

    def test_user_actions_camp_two_way_and_submit(self):
        saved = sv.load_save(self.path)
        sv.set_save_date_phase(saved, "2026-10-12")
        # Open a two-way place and keep the user's roster at 15 standard players.
        place = two_way.team_two_ways(saved, "team_gsw")[0]["player_id"]
        two_way.release(saved, place, when="2026-10-12", by="user")
        sv.write_save(self.path, saved)
        active = sv.canonical_with_save(self.canonical, saved)
        young = sorted((p for p in active["players"] if p["id"] in saved["free_agent_player_ids"]
                        and two_way.eligibility(saved, p, "team_gsw", "2026-27", 1)["ok"]),
                       key=lambda p: p["id"])
        invited = self.act("camp_invite", team="GSW", player_id=young[0]["id"])
        self.assertEqual(invited["status"], "signed", invited)
        self.assertTrue(camp.is_camp_deal(sv.load_save(self.path), young[0]["id"]))
        moved = self.act("camp_to_two_way", team="GSW", player_id=young[0]["id"])
        self.assertEqual(moved["status"], "converted", moved)
        self.assertEqual(two_way.two_way_team(sv.load_save(self.path), young[0]["id"]), "team_gsw")
        full = self.act("two_way_sign", team="GSW", player_id=young[1]["id"])
        self.assertEqual(full["status"], "blocked", "all three places are filled again")
        submitted = self.act("submit_roster", team="GSW")
        self.assertEqual(submitted["status"], "submitted", submitted)
        self.assertTrue(submitted["room"]["roster"]["submitted"])


if __name__ == "__main__":
    unittest.main()
