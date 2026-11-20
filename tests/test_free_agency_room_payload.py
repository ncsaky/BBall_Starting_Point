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


def market_save(day: int = 2, offers: list | None = None, asks: dict | None = None, phase: str = "free_agency") -> dict:
    return {"state": {"current_date": "2027-07-02", "phase": phase}, "meta": {"season": "2026-27"},
            "free_agency_state": {"season": "2026-27", "day": day, "day_count": 5, "status": "active",
                                  "player_asks_millions": asks or {}},
            "free_agent_offers": offers or [], "team_records": {}}


def rival_bid(player_id: str, aav: float, interest: float, team_id: str = "team_bkn", years: int = 4) -> dict:
    return {"id": f"bid_{team_id}_{player_id}", "season": "2026-27", "source": "ai", "player_id": player_id,
            "team_id": team_id, "years": years, "aav_millions": aav, "interest_score": interest, "status": "active"}


CHA = {"id": "team_cha", "abbrev": "CHA"}


class AcceptFloorParityTests(unittest.TestCase):
    """The price the builder shows is the price manual_save_pool_signing applies (TRADE-VOLUME: the rival bids' rule)."""

    def sign(self, save: dict, candidate: dict, years: int, aav: float, guaranteed: bool) -> dict:
        # Legality (how the team pays) is the cap ledger's job and is tested in test_cap_ledger; here every offer is
        # payable so the test isolates the price rule.
        from nba_gm_data import cap_ledger
        payment = {"route": "cap_room", "season": "2027-28", "salary": aav * 1e6, "amount": aav * 1e6,
                   "schedule": [{"season": f"{2027 + k}-{str(2028 + k)[-2:]}", "salary": s, "cap_charge": s}
                                for k, s in enumerate(cap_ledger.raise_schedule(aav * 1e6, years, 0.05))]}
        with patch.object(play, "load_save", return_value=save), patch.object(play, "write_save"), \
                patch.object(play, "resolve_team", return_value=CHA), \
                patch.object(play, "signing_cap_check", return_value={"ok": True, "payment": payment}), \
                patch.object(play, "extension_retirement_blocked", return_value=False):
            return play.manual_save_pool_signing({}, Path("unused"), candidate, "CHA", years, aav, 7, guaranteed=guaranteed)

    def floors(self, save: dict, candidate: dict) -> dict:
        return aa.free_agent_offer_floors({}, save, candidate, CHA, 5)

    def test_shown_price_is_the_engine_threshold_for_every_role_length_and_guarantee(self):
        for minutes in (0.0, 4.0, 12.5, 18.0, 25.7, 30.1, 36.0):
            candidate = player(minutes)
            ask = max(1.8, round(minutes * 0.48, 1))
            for save in (market_save(day=2, asks={candidate["id"]: ask}),
                         market_save(day=4, asks={candidate["id"]: ask},
                                     offers=[rival_bid(candidate["id"], round(ask * 1.05, 1), 70.0)]),
                         market_save(phase="re_signing", asks={candidate["id"]: ask})):
                floors = self.floors(save, candidate)
                for key, guaranteed in (("guaranteed", True), ("non_guaranteed", False)):
                    for years in (1, 3, 5):
                        floor = floors["by_years"][key][str(years)]
                        with self.subTest(minutes=minutes, mode=floors["rule"]["mode"], guaranteed=guaranteed, years=years):
                            if floor is None:
                                self.assertFalse(self.sign(save, candidate, years, 90.0, guaranteed)["accepted"])
                                continue
                            at = self.sign(save, candidate, years, floor, guaranteed)
                            self.assertTrue(at["accepted"], "the shown price is accepted")
                            self.assertEqual(at["decision"]["ask_threshold_millions"], floor)
                            if floor > play.league_minimum_aav_millions():
                                below = self.sign(save, candidate, years, round(floor - 0.1, 1), guaranteed)
                                self.assertFalse(below["accepted"], "one $0.1M step under the shown price is refused")

    def test_non_guaranteed_costs_more(self):
        candidate = player(30.1)
        floors = self.floors(market_save(asks={candidate["id"]: 14.4}), candidate)
        self.assertGreater(floors["default"]["non_guaranteed"], floors["default"]["guaranteed"])

    def test_price_tracks_the_market_ask_not_projected_minutes(self):
        # The old rule priced a 30-minute player at 30 x 0.45 = $13.5M whatever his market; now a $28.8M ask costs
        # about his ask (the bar drops through the week, so day 5 is cheaper than day 2).
        candidate = player(30.1)
        day2 = self.floors(market_save(day=2, asks={candidate["id"]: 28.8}), candidate)["by_years"]["guaranteed"]["4"]
        day5 = self.floors(market_save(day=5, asks={candidate["id"]: 28.8}), candidate)["by_years"]["guaranteed"]["4"]
        self.assertGreater(day2, 28.8 * 0.85)
        self.assertLess(day5, day2)

    def test_user_offer_loses_to_a_better_rival_bid(self):
        # Brandon Miller's case: ask $28.8M, a rival bid of $30.4M. The old rule signed him with the user for $13.6M.
        candidate = player(30.1, id="p_miller")
        bid = rival_bid("p_miller", 30.4, 81.0)
        save = market_save(day=3, asks={"p_miller": 28.8}, offers=[bid])
        cheap = self.sign(save, candidate, 4, 13.6, True)
        self.assertFalse(cheap["accepted"])
        at_ask = self.sign(save, candidate, 4, 28.8, True)
        self.assertFalse(at_ask["accepted"])
        self.assertEqual(at_ask["decision"]["decision"], "prefers_rival_bid")
        floor = self.floors(save, candidate)["by_years"]["guaranteed"]["4"]
        self.assertIsNotNone(floor)
        self.assertGreater(floor, 30.4 * 0.95, "he needs about the rival's money or more")
        self.assertTrue(self.sign(save, candidate, 4, floor, True)["accepted"])
        # The AI bids' own rule picks the same winner: the higher interest, then the higher salary.
        user_interest = self.sign(save, candidate, 4, floor, True)["decision"]["interest"]
        self.assertGreaterEqual((user_interest, floor), (bid["interest_score"], bid["aav_millions"]))


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
