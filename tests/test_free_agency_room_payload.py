"""Free-agency room: the offer builder shows the engine's own signing numbers.

The builder tells the user what salary a free agent signs for, and whether the cap allows it, before anything is
sent. These tests keep those previews equal to the rules `submit_free_agent_offer` actually runs.
"""
from __future__ import annotations

import json
import shutil
import subprocess
import unittest
from pathlib import Path
from unittest.mock import patch

from nba_gm_data import app_actions as aa
from nba_gm_data import play

ROOT = Path(__file__).resolve().parents[1]
APP_JS = ROOT / "src/nba_gm_data/gui/app.js"


def player(minutes: float, **extra) -> dict:
    return {"id": f"p{minutes}", "name": "Test Player", "age": 27, "position": "SF", "minutes_projection": minutes,
            "team_id": None, **extra}


class AcceptFloorParityTests(unittest.TestCase):
    def engine_threshold(self, candidate: dict, guaranteed: bool) -> tuple[float, bool]:
        """Run the real manual_save_pool_signing decision without touching disk."""
        save = {"state": {"current_date": "2027-07-02", "phase": "free_agency"}, "meta": {"season": "2026-27"}}
        with patch.object(play, "load_save", return_value=save), patch.object(play, "write_save"), \
                patch.object(play, "resolve_team", return_value={"id": "team_cha", "abbrev": "CHA"}), \
                patch.object(play, "extension_retirement_blocked", return_value=False):
            floor = aa.free_agent_accept_floor_millions(candidate, guaranteed)
            below = play.manual_save_pool_signing({}, Path("unused"), candidate, "CHA", 3, aa.smallest_offer_at_or_above(floor) - 0.1, 7, guaranteed=guaranteed)
            at = play.manual_save_pool_signing({}, Path("unused"), candidate, "CHA", 3, aa.smallest_offer_at_or_above(floor), 7, guaranteed=guaranteed)
        self.assertFalse(below["accepted"], "one $0.1M step under the shown price is refused")
        self.assertTrue(at["accepted"], "the shown price is accepted")
        return at["decision"]["ask_threshold_millions"], at["accepted"]

    def test_shown_price_is_the_engine_threshold_for_every_role_and_guarantee(self):
        for minutes in (0.0, 4.0, 12.5, 18.0, 25.7, 30.1, 36.0):
            for guaranteed in (True, False):
                with self.subTest(minutes=minutes, guaranteed=guaranteed):
                    candidate = player(minutes)
                    threshold, _ = self.engine_threshold(candidate, guaranteed)
                    self.assertAlmostEqual(round(aa.free_agent_accept_floor_millions(candidate, guaranteed), 2), threshold, places=6)

    def test_non_guaranteed_costs_more(self):
        candidate = player(30.1)
        self.assertGreater(aa.free_agent_accept_floor_millions(candidate, False), aa.free_agent_accept_floor_millions(candidate, True))

    def test_price_rounds_up_to_an_offer_the_engine_accepts(self):
        self.assertEqual(aa.smallest_offer_at_or_above(13.545), 13.6)
        self.assertEqual(aa.smallest_offer_at_or_above(13.5), 13.5)
        self.assertEqual(aa.smallest_offer_at_or_above(13.500000000000002), 13.6)
        self.assertEqual(aa.smallest_offer_at_or_above(1.9), 1.9)
        for value in (2.0000001, 7.25, 16.254, 13.05, 30 * 0.45):
            offer = aa.smallest_offer_at_or_above(value)
            self.assertGreaterEqual(offer, value)
            self.assertLess(offer - value, 0.1 + 1e-9)


@unittest.skipUnless(shutil.which("node"), "node is needed to run the browser preview")
class CapPreviewParityTests(unittest.TestCase):
    """The builder's live cap verdict (JavaScript) agrees with play.signing_cap_check on a grid of offers."""

    def js_checks(self, cases: list[dict]) -> list[dict]:
        source = APP_JS.read_text()
        start = source.index("function freeAgencyCapCheck(")
        end = source.index("function freeAgencyCapSeasons(", start)
        script = (
            "const money=v=>`$${Number(v).toFixed(1)}M`;\n" + source[start:end]
            + "\nconst cases=JSON.parse(require('fs').readFileSync(0,'utf8'));"
            + "process.stdout.write(JSON.stringify(cases.map(c=>freeAgencyCapCheck(c.rules,c.cap,c.aav))));"
        )
        result = subprocess.run(["node", "-e", script], input=json.dumps(cases), capture_output=True, text=True, check=True)
        return json.loads(result.stdout)

    def test_cap_verdict_matches_engine(self):
        cases, expected = [], []
        for tax_room, hard_room in ((67.3, 89.3), (10.0, 30.0), (-5.0, 12.0), (-8.0, -2.0)):
            for allow in (False, True):
                for aav in (1.9, 1.95, 2.0, 9.9, 10.0, 10.1, 12.0, 29.9, 30.0, 30.1, 67.3, 67.4, 89.3, 90.0):
                    cap = {"tax_space_millions": tax_room, "hard_cap_space_millions": hard_room, "unresolved_waived_contract_count": 0}
                    with patch.object(play, "resolve_team", return_value={"id": "team_cha", "abbrev": "CHA"}), \
                            patch.object(play, "team_cap_summary", return_value=cap):
                        engine = play.signing_cap_check({}, {"meta": {"season": "2026-27"}, "state": {"phase": "free_agency"}}, "CHA", aav, allow_tax_exceed=allow)
                    cases.append({"rules": {"minimum_aav_millions": play.league_minimum_aav_millions(), "allow_tax_exceed": allow, "blocked_reason": None},
                                  "cap": cap, "aav": aav})
                    expected.append(bool(engine["ok"]))
        got = [bool(row["ok"]) for row in self.js_checks(cases)]
        mismatches = [(case["cap"]["tax_space_millions"], case["cap"]["hard_cap_space_millions"], case["rules"]["allow_tax_exceed"], case["aav"])
                      for case, a, b in zip(cases, got, expected) if a != b]
        self.assertEqual(mismatches, [])

    def test_unreviewed_waived_salary_blocks_everything_in_both(self):
        cap = {"tax_space_millions": 50.0, "hard_cap_space_millions": 70.0, "unresolved_waived_contract_count": 1}
        with patch.object(play, "resolve_team", return_value={"id": "team_cha", "abbrev": "CHA"}), \
                patch.object(play, "team_cap_summary", return_value=cap):
            self.assertFalse(play.signing_cap_check({}, {"meta": {}, "state": {}}, "CHA", 1.9)["ok"])
        got = self.js_checks([{"rules": {"minimum_aav_millions": 1.9, "blocked_reason": "Waived salary requires review."}, "cap": cap, "aav": 1.9}])
        self.assertFalse(got[0]["ok"])


if __name__ == "__main__":
    unittest.main()
