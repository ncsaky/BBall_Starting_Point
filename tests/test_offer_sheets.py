"""FA-REAL slice 3: offer sheets and matching (offer_sheets). Legal terms (2-4 years, 5% raises, the Arenas rule, the
maximum qualifying offer's three years), the bidder's reserved room, matching rules and the deadline, the year's trade
block after a match, the player's choice, the user's Match or Pass, and the AI's bids on a real league."""
from __future__ import annotations

from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

from nba_gm_data import cap_ledger as cl, offer_sheets as os_, offseason_decisions as od, save as sv
from nba_gm_data.transactions import recently_signed_player_ids

SEASON = "2027-28"
EXPIRING = "2026-27"
TODAY = "2027-07-02"
MLE = cl.exception_amount("non_taxpayer_mle", SEASON)


def roster(team: str, payroll: float, count: int = 13) -> tuple[list, list]:
    players = [{"id": f"{team}_{i}", "name": f"{team} {i}", "team_id": team, "age": 28, "draft_year": 2018}
               for i in range(count)]
    contracts = [{"player_id": p["id"], "seasons": [{"season": SEASON, "salary": payroll / count}]} for p in players]
    return players, contracts


def world(*, incumbent_payroll: float = 150e6, bidder_payroll: float = 110e6, minutes: float = 26.0,
          draft_round: int = 1, draft_year: int = 2023, previous: float = 5e6, maximum_qo: bool = False,
          user_team: str = "human") -> tuple[dict, dict]:
    """Team t holds restricted free agent 'rfa' (qualifying offer $7M); team b has cap room."""
    t_players, t_contracts = roster("t", incumbent_payroll)
    b_players, b_contracts = roster("b", bidder_payroll)
    rfa = {"id": "rfa", "name": "Young Wing", "team_id": None, "age": 23, "draft_year": draft_year,
           "draft_round": draft_round, "draft_position": 10 if draft_round == 1 else 40, "minutes_projection": minutes}
    contract = {"player_id": "rfa", "signed_season": f"{draft_year}-{str(draft_year + 1)[-2:]}",
                "seasons": [{"season": EXPIRING, "salary": previous}]}
    league = {"teams": [{"id": "t", "abbrev": "T"}, {"id": "b", "abbrev": "B"}],
              "players": t_players + b_players + [rfa], "contracts": t_contracts + b_contracts + [contract]}
    save = {"version": "league_save_v1", "meta": {"season": EXPIRING, "user_team_id": user_team, "seed": 17},
            "state": {"current_date": TODAY, "phase": "free_agency"},
            "free_agent_player_ids": ["rfa"],
            "contract_overrides": {"rfa": {"team_id": "t", "signed_season": contract["signed_season"],
                                           "seasons": contract["seasons"]}},
            "re_signing_rights": [{"player_id": "rfa", "team_id": "t", "season": EXPIRING, "status": "entered_open_market"}],
            "free_agency_state": {"season": EXPIRING, "day": 3, "status": "active", "player_asks_millions": {"rfa": 10.0}}}
    service = 2027 - draft_year
    od.store(save)["qualifying_offers"][f"{SEASON}:rfa"] = {
        "player_id": "rfa", "team_id": "t", "season": SEASON, "status": "tendered", "amount": 7_000_000,
        "years_of_service": service, "previous_salary": previous, "market_millions": 10.0,
        "maximum": maximum_qo, "max_qo_amount": 40_000_000 if maximum_qo else None}
    return league, save


def rfa(league: dict) -> dict:
    return next(p for p in league["players"] if p["id"] == "rfa")


class SheetTerms(unittest.TestCase):
    def test_two_to_four_years_with_raises_up_to_five_percent(self):
        league, save = world()
        self.assertFalse(os_.sheet_terms(save, rfa(league), 10e6, 1)["ok"])
        self.assertFalse(os_.sheet_terms(save, rfa(league), 10e6, 5)["ok"])
        terms = os_.sheet_terms(save, rfa(league), 10e6, 3, raise_rate=0.08)
        self.assertTrue(terms["ok"])
        self.assertEqual(terms["salaries"], [10_000_000, 10_500_000, 11_000_000], "raises cut to 5% of year one")
        self.assertFalse(terms["arenas"], "a first-rounder after four seasons is outside the Arenas band")

    def test_a_maximum_qualifying_offer_means_at_least_three_years(self):
        league, save = world(maximum_qo=True)
        self.assertFalse(os_.sheet_terms(save, rfa(league), 10e6, 2)["ok"])
        self.assertTrue(os_.sheet_terms(save, rfa(league), 10e6, 3)["ok"])

    def test_arenas_rule(self):
        league, save = world(draft_round=2, draft_year=2025, previous=2e6)     # two years in the league
        player = rfa(league)
        self.assertIn("Arenas", os_.sheet_terms(save, player, MLE + 1e6, 3)["reason"])
        back = os_.sheet_terms(save, player, MLE, 3, backload=True)
        self.assertTrue(back["ok"], back)
        top = cl.true_max_salary(SEASON, 2) * 1.10
        self.assertEqual(back["salaries"], [round(MLE), round(MLE * 1.05), round(top)])
        self.assertEqual(back["bidder_charges"], [round(sum(back["salaries"]) / 3)] * 3, "the bidder counts the average")
        self.assertEqual(back["incumbent_charges"], back["salaries"], "his team counts the real salaries")
        four = os_.sheet_terms(save, player, MLE, 4, backload=True)
        self.assertEqual(four["salaries"][3], round(round(top) * 1.045))
        self.assertFalse(os_.sheet_terms(save, player, MLE - 1e6, 3, backload=True)["ok"], "the jump needs year one at the limit")
        # The 2026-27 example in the research: $15.044M, $15.796M, $45.364M.
        example = cl.true_max_salary("2026-27", 2) * 1.10
        self.assertAlmostEqual(example / 1e6, 45.364, places=2)


class BidderAndReservation(unittest.TestCase):
    def test_bidder_pays_with_room_and_the_room_stays_reserved(self):
        league, save = world()
        player = rfa(league)
        terms = os_.sheet_terms(save, player, 20e6, 3)
        quote = os_.bidder_quote(league, save, "b", player, terms)
        self.assertTrue(quote["ok"], quote.get("message"))
        self.assertEqual(quote["payment"]["route"], "cap_room")
        self.assertEqual([s["salary"] for s in quote["payment"]["schedule"]], terms["salaries"])
        before = cl.team_payroll(league, save, "b", SEASON, include_reservations=True)
        sheet = os_.sign_sheet(save, player, "b", terms, quote, by="ai", reason="test")
        self.assertEqual(sheet["match_deadline"], "2027-07-03", "his team decides by the end of the next day")
        held = cl.reservations(save, "b", SEASON)
        self.assertEqual(held.get("cap_room"), 20e6)
        # The same room can't fund a second big signing while the sheet waits.
        other = {"id": "other", "name": "Other", "age": 27, "draft_year": 2019, "team_id": None}
        second = cl.quote(league, save, "b", other, 45e6, 2, season=SEASON, route="cap_room")
        self.assertFalse(second["ok"])
        self.assertGreater(before["cap_room"], 45e6, "it would have fit without the reserved sheet")
        # One sheet per player at a time.
        self.assertIn("already signed an offer sheet", os_.can_receive_sheet(save, "rfa", "b"))
        self.assertIn("offer sheet", od.blocked_for_team(save, "rfa", "t"), "nobody signs him while the sheet waits")
        self.assertFalse(od.accept_qualifying_offer({}, save, "rfa", "test"), "the sheet binds him")

    def test_sheets_open_july_first(self):
        league, save = world()
        save["state"]["current_date"] = "2027-06-30"
        self.assertIn("July 1", os_.can_receive_sheet(save, "rfa", "b"))
        save["state"]["current_date"] = "2027-07-01"
        self.assertIsNone(os_.can_receive_sheet(save, "rfa", "b"))
        self.assertIn("own restricted", os_.can_receive_sheet(save, "rfa", "t"))

    def test_an_offer_sheet_never_uses_bird_rights(self):
        league, save = world(bidder_payroll=190e6)
        player = rfa(league)
        terms = os_.sheet_terms(save, player, 20e6, 3)
        quote = os_.bidder_quote(league, save, "b", player, terms)
        self.assertFalse(quote["ok"], "over the cap, the full mid-level doesn't reach $20M")
        small = os_.sheet_terms(save, player, 12e6, 3)
        paid = os_.bidder_quote(league, save, "b", player, small)
        self.assertEqual(paid["payment"]["route"], "non_taxpayer_mle")
        self.assertFalse(os_.bidder_quote(league, save, "b", player, small, route="bird")["ok"])


class Matching(unittest.TestCase):
    def signed(self, **kwargs) -> tuple[dict, dict, dict]:
        league, save = world(**kwargs)
        player = rfa(league)
        terms = os_.sheet_terms(save, player, 18e6, 3)
        quote = os_.bidder_quote(league, save, "b", player, terms)
        return league, save, os_.sign_sheet(save, player, "b", terms, quote, by="ai", reason="test")

    def test_bird_rights_match_over_the_cap_and_block_trades_for_a_year(self):
        league, save, sheet = self.signed(incumbent_payroll=180e6)
        choice = os_.incumbent_choice(league, save, sheet)
        self.assertTrue(choice["match"], choice["reason"])
        self.assertEqual(choice["quote"]["payment"]["route"], "bird")
        with patch("nba_gm_data.save.canonical_with_save", return_value=league):
            result = os_.settle({}, save, sheet, True, by="team", reason=choice["reason"], active=league)
        self.assertTrue(result["ok"], result)
        override = save["contract_overrides"]["rfa"]
        self.assertEqual(override["team_id"], "t")
        self.assertEqual([r["salary"] for r in override["seasons"]], sheet["salaries"])
        self.assertEqual(override["trade_eligible_date"], "2028-07-01")
        self.assertIn("rfa", recently_signed_player_ids(save, "2028-03-01"), "no trade for a year")
        self.assertNotIn("rfa", recently_signed_player_ids(save, "2028-07-02"))
        self.assertEqual(cl.reservations(save, "b", SEASON), {}, "the bidder's room is free again")
        self.assertEqual(od.qo_record(save, SEASON, "rfa")["status"], "signed")

    def test_a_hard_capped_team_cannot_match_even_with_bird_rights(self):
        league, save, sheet = self.signed(incumbent_payroll=200e6)
        cl.trigger_hard_cap(save, "t", SEASON, "first_apron", "using the full mid-level exception")
        choice = os_.incumbent_choice(league, save, sheet)
        self.assertFalse(choice["legal"])
        self.assertEqual(choice["kind"], "cannot")
        self.assertIn("hard-capped", choice["reason"])
        with patch("nba_gm_data.save.canonical_with_save", return_value=league):
            self.assertFalse(os_.settle({}, save, sheet, True, by="user", reason="x", active=league)["ok"])
            result = os_.settle({}, save, sheet, False, by="team", reason=choice["reason"], active=league)
        self.assertTrue(result["ok"])
        override = save["contract_overrides"]["rfa"]
        self.assertEqual(override["team_id"], "b")
        self.assertEqual(override["payment_route"], "cap_room")
        self.assertFalse(any(r["player_id"] == "rfa" and r["team_id"] == "t" for r in save["re_signing_rights"]))
        self.assertTrue(cl.team_year(save, "b", SEASON)["used_room"], "the reserved payment is committed")

    def test_an_expensive_reserve_over_the_tax_is_let_go(self):
        league, save, sheet = self.signed(incumbent_payroll=205e6, minutes=11.0)
        choice = os_.incumbent_choice(league, save, sheet)
        self.assertTrue(choice["legal"])
        self.assertFalse(choice["match"])
        self.assertEqual(choice["kind"], "expensive_reserve")
        regular = os_.incumbent_choice(league, save, sheet, {**rfa(league), "minutes_projection": 26.0})
        self.assertTrue(regular["match"], "a regular is matched even over the tax")

    def test_the_deadline_and_who_decides(self):
        league, save, sheet = self.signed()
        with patch("nba_gm_data.save.canonical_with_save", return_value=league):
            self.assertEqual(os_.resolve_due({}, save), [], "the AI team waits for its deadline day")
            save["state"]["current_date"] = sheet["match_deadline"]
            done = os_.resolve_due({}, save)
        self.assertEqual([s["status"] for s in done], ["matched"])

    def test_the_users_sheet_waits_for_the_user_or_the_clock(self):
        league, save, sheet = self.signed(user_team="t")
        save["meta"]["human_team_ids"] = ["t"]
        save["state"]["current_date"] = sheet["match_deadline"]
        with patch("nba_gm_data.save.canonical_with_save", return_value=league):
            self.assertEqual(os_.resolve_due({}, save, force_ai=True), [], "only the user decides his own sheet")
            self.assertEqual([s["id"] for s in os_.user_decisions_due(save)], [sheet["id"]])
            view = os_.sheet_view(league, save, sheet, "t")
            self.assertTrue(view["can_match"])
            self.assertEqual(len(view["cap_effect"]), 3)
            self.assertEqual(view["cap_effect"][0]["adds_millions"], 18.0)
            self.assertIn("matches", view["advice"]["reason"])
            done = os_.resolve_due({}, save, expire_user=True)
        self.assertEqual(done[0]["status"], "passed", "when time runs out he joins the bidder")


class PlayerChoice(unittest.TestCase):
    def test_he_signs_a_sheet_that_reaches_his_price_now(self):
        league, save = world()
        player = rfa(league)
        want = od.rfa_reservation(save, player, 10e6, 0.4)
        self.assertFalse(os_.player_takes_sheet(save, player, want - 200_000, 0.4)[0])
        self.assertTrue(os_.player_takes_sheet(save, player, want + 1, 0.4)[0])
        self.assertFalse(os_.player_takes_sheet(save, player, 6.9e6, 1.0)[0], "never below his qualifying offer")


class RealLeague(unittest.TestCase):
    """The AI bids on a real league, and the screen shows what the save writes (rule 4)."""

    @classmethod
    def setUpClass(cls):
        from nba_gm_data.app_actions import load_app_canonical
        cls.root = Path(__file__).resolve().parents[1]
        cls.canonical = load_app_canonical(cls.root)

    def make_restricted(self, saved: dict, team_abbrev: str) -> dict:
        """Turn a young free agent into another team's restricted free agent (a tendered qualifying offer)."""
        active = sv.canonical_with_save(self.canonical, saved)
        team = next(t for t in active["teams"] if t["abbrev"] == team_abbrev)
        player = next(p for p in active["players"] if p["id"] in saved["free_agent_player_ids"]
                      and float(p.get("age") or 30) <= 25 and float(p.get("minutes_projection") or 0) >= 14)
        saved.setdefault("re_signing_rights", []).append(
            {"player_id": player["id"], "team_id": team["id"], "season": saved["meta"]["season"],
             "status": "entered_open_market"})
        next_season = cl.cap_year(saved)
        od.store(saved)["qualifying_offers"][f"{next_season}:{player['id']}"] = {
            "player_id": player["id"], "team_id": team["id"], "season": next_season, "status": "tendered",
            "amount": 3_000_000, "years_of_service": 4, "market_millions": 8.0, "name": player.get("name"),
            "deadline": "2027-06-29"}
        return player

    def test_offer_sheet_quote_is_what_the_save_writes(self):
        from nba_gm_data.app_actions import dispatch_app_action
        with TemporaryDirectory() as folder:
            path = Path(folder) / "sheet.json"
            sv.create_league_save(self.root, self.canonical, "TOR", path, seed=17)
            saved = sv.load_save(path)
            sv.set_save_date_phase(saved, "2027-07-02")
            player = self.make_restricted(saved, "BOS")
            saved.setdefault("free_agency_state", {})["player_asks_millions"] = {player["id"]: 8.0}
            sv.write_save(path, saved)

            def action(name, **payload):
                return dispatch_app_action(name, {"save_path": str(path), **payload}, root=self.root,
                                           save_dir=folder, canonical=self.canonical)
            terms = {"team": "TOR", "player_id": player["id"], "years": 3, "aav_millions": 12.0}
            quote = action("free_agent_offer_quote", **terms)
            self.assertTrue(quote["offer_sheet"]["is_offer_sheet"])
            self.assertTrue(quote["quote"]["ok"], quote["quote"])
            self.assertIn("Reserved until BOS decides", quote["quote"]["locks"])
            self.assertEqual([r["salary_millions"] for r in quote["quote"]["schedule"]], [12.0, 12.6, 13.2])
            self.assertFalse(action("free_agent_offer_quote", **{**terms, "years": 1})["quote"]["ok"])
            result = action("submit_free_agent_offer", **terms)
            self.assertEqual(result["status"], "offer_sheet_signed", result)
            room = action("free_agency_room", team="TOR")
            mine = room["offer_sheets"]["yours"]
            self.assertEqual(len(mine), 1)
            self.assertEqual([y["salary_millions"] for y in mine[0]["years"]], [12.0, 12.6, 13.2])
            self.assertEqual(mine[0]["paid_with"], quote["quote"]["label"])
            # BOS decides the next day; the contract written is the sheet's.
            after = sv.load_save(path)
            sv.set_save_date_phase(after, "2027-07-03")
            os_.resolve_due(self.canonical, after)
            sheet = os_.all_sheets(after)[0]
            self.assertIn(sheet["status"], {"matched", "passed"})
            self.assertTrue(sheet["decision_reason"])
            written = after["contract_overrides"][player["id"]]
            self.assertEqual([r["salary"] for r in written["seasons"]], [12_000_000, 12_600_000, 13_200_000])

    def test_user_match_or_pass_flow_and_the_ai_bid(self):
        from nba_gm_data.app_actions import dispatch_app_action
        with TemporaryDirectory() as folder:
            path = Path(folder) / "match.json"
            sv.create_league_save(self.root, self.canonical, "TOR", path, seed=17)
            saved = sv.load_save(path)
            sv.set_save_date_phase(saved, "2027-07-02")
            player = self.make_restricted(saved, "TOR")
            saved.setdefault("free_agency_state", {}).update(player_asks_millions={player["id"]: 8.0})
            # An AI bid at full appeal always goes through; at zero it never does (the frequency knob).
            with patch.dict(os_.RULES["bidder"], {"pass_rate": 0.0}):
                self.assertEqual(os_.ai_sheet_pass(self.canonical, saved, label="t0"), [])
            with patch.dict(os_.RULES["bidder"], {"pass_rate": 1000.0}):
                signed = os_.ai_sheet_pass(self.canonical, saved, label="t1")
            self.assertEqual([s["player_id"] for s in signed], [player["id"]])
            self.assertTrue(signed[0]["bid_reason"].startswith(sv.team_id_to_abbrev(signed[0]["bidder_team_id"])))
            sv.write_save(path, saved)

            def action(name, **payload):
                return dispatch_app_action(name, {"save_path": str(path), **payload}, root=self.root,
                                           save_dir=folder, canonical=self.canonical)
            room = action("free_agency_room", team="TOR")
            waiting = room["offer_sheets"]["for_you"]
            self.assertEqual(len(waiting), 1)
            self.assertIn("advice", waiting[0])
            self.assertTrue(waiting[0]["cap_effect"])
            from nba_gm_data.app_actions import league_activity_payload
            news = league_activity_payload(self.canonical, path)
            texts = [m for m in (news.get("assistant_messages") or []) if m.get("kind") == "offer_sheet"]
            self.assertTrue(texts and texts[0]["target"] == "offer-sheet")
            after = sv.load_save(path)
            sv.set_save_date_phase(after, signed[0]["match_deadline"])
            sv.write_save(path, after)
            blocked = action("advance_free_agency", team="TOR", mode="day")
            self.assertEqual(blocked["status"], "decision_needed")
            decided = action("offer_sheet_decision", team="TOR", sheet_id=signed[0]["id"], match=True)
            self.assertEqual(decided["status"], "matched", decided)
            final = sv.load_save(path)
            self.assertEqual(final["contract_overrides"][player["id"]]["team_id"], sv.resolve_team(
                sv.canonical_with_save(self.canonical, final), "TOR")["id"])


if __name__ == "__main__":
    unittest.main()
