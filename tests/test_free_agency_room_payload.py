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
    """FA-REAL: the builder's cap verdict (JavaScript) is the engine's quote (cap_ledger via play.signing_cap_check,
    sent by free_agent_offer_quote): on a grid of payrolls and offers the browser says yes exactly when the engine does."""

    def js_verdicts(self, quotes: list[dict], rules: dict | None = None) -> list[dict]:
        source = APP_JS.read_text()
        start = source.index("function freeAgencyCapVerdict(")
        end = source.index("function requestFreeAgencyQuote(", start)
        script = (source[start:end]
                  + "\nconst input=JSON.parse(require('fs').readFileSync(0,'utf8'));"
                  + "process.stdout.write(JSON.stringify(input.quotes.map(q=>freeAgencyCapVerdict(q,input.rules))));")
        result = subprocess.run(["node", "-e", script], input=json.dumps({"quotes": quotes, "rules": rules or {}}),
                                capture_output=True, text=True, check=True)
        return json.loads(result.stdout)

    @staticmethod
    def league(payroll: float) -> dict:
        players = [{"id": f"cha_{i}", "team_id": "team_cha", "age": 28, "draft_year": 2018} for i in range(13)]
        contracts = [{"player_id": p["id"], "seasons": [{"season": "2027-28", "salary": payroll / 13}]} for p in players]
        return {"players": players + [{"id": "fa", "age": 27, "draft_year": 2020, "team_id": None}], "contracts": contracts,
                "teams": [{"id": "team_cha", "abbrev": "CHA"}]}

    def test_cap_verdict_matches_engine(self):
        from nba_gm_data.app_actions import quote_view
        save = {"meta": {"season": "2026-27"}, "state": {"phase": "free_agency", "current_date": "2027-07-03"}}
        views, expected = [], []
        for payroll in (120e6, 160e6, 205e6, 215e6, 225e6):
            active = self.league(payroll)
            for aav in (1.9, 2.4, 6.0, 6.1, 9.0, 15.0, 15.1, 30.0, 45.0, 60.0):
                with patch.object(play, "resolve_team", return_value={"id": "team_cha", "abbrev": "CHA"}):
                    check = play.signing_cap_check(active, save, "CHA", aav, player=active["players"][-1], years=2)
                views.append(quote_view(check))
                expected.append(bool(check["ok"]))
        self.assertIn(True, expected)
        self.assertIn(False, expected)
        got = [bool(row["ok"]) for row in self.js_verdicts(views)]
        self.assertEqual(got, expected)

    def test_unreviewed_waived_salary_blocks_everything_in_both(self):
        save = {"meta": {"season": "2026-27"}, "state": {"phase": "free_agency", "current_date": "2027-07-03"},
                "waived_salary_obligations": [{"team_id": "team_cha", "seasons": [{"season": "2027-28", "salary": None}]}]}
        active = self.league(120e6)
        with patch.object(play, "resolve_team", return_value={"id": "team_cha", "abbrev": "CHA"}):
            self.assertFalse(play.signing_cap_check(active, save, "CHA", 1.9, player=active["players"][-1])["ok"])
        got = self.js_verdicts([{"ok": True}], {"blocked_reason": "Waived salary requires review."})
        self.assertFalse(got[0]["ok"])


if __name__ == "__main__":
    unittest.main()
