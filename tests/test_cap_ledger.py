"""FA-REAL slice 1: the money calculator (cap_ledger). The research's scenarios (docs/agents/tasks/fa-realism-research.md,
"Scenarios to check") plus the exact lines, maximum and minimum salaries, raise schedules and trade dates."""
from __future__ import annotations

from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

from nba_gm_data import cap_ledger as cl, cap_rules, contract_ai as ca, play, save as sv

SEASON = "2027-28"            # the cap year of the summer-2027 market
TODAY = "2027-07-03"          # after July 1: holds and empty-spot charges count
LINES = cap_rules.cap_lines_for_season(SEASON)


def league(payroll: float, *, team: str = "t", count: int = 13, extra: list | None = None) -> dict:
    """A league view where ``team`` has ``payroll`` in signed salaries for 2027-28 over ``count`` players."""
    players = [{"id": f"{team}_{i}", "name": f"Player {i}", "team_id": team, "age": 28, "draft_year": 2018}
               for i in range(count)]
    contracts = [{"player_id": p["id"], "seasons": [{"season": SEASON, "salary": payroll / count}]} for p in players]
    data = {"players": players, "contracts": contracts, "teams": [{"id": team, "abbrev": team.upper()}]}
    for player, contract in extra or []:
        data["players"].append(player)
        if contract:
            data["contracts"].append(contract)
    return data


def summer(**extra) -> dict:
    return {"meta": {"season": "2026-27", "user_team_id": "human"},
            "state": {"current_date": TODAY, "phase": "free_agency"}, **extra}


def outsider(pid: str = "fa", age: float = 27, draft_year: int = 2019) -> dict:
    return {"id": pid, "name": f"Free Agent {pid}", "age": age, "draft_year": draft_year, "team_id": None}


def own_free_agent(previous: float, signed: str = "2024-25", pid: str = "own") -> tuple[dict, dict, dict]:
    """His expiring contract, his Bird clock (signed ``signed``) and the team's right to re-sign him."""
    player = outsider(pid, age=27, draft_year=2019)
    contract = {"player_id": pid, "signed_season": signed, "seasons": [{"season": "2026-27", "salary": previous}]}
    override = {"team_id": "t", "signed_season": signed, "seasons": contract["seasons"]}
    right = {"player_id": pid, "team_id": "t", "season": "2026-27", "status": "exclusive_review_window"}
    return player, contract, {"override": override, "right": right}


class LinesAndSalaries(unittest.TestCase):
    def test_exact_2026_27_lines_without_rounding(self):
        lines = cap_rules.cap_lines_for_season("2026-27")
        self.assertEqual((lines["salary_cap"], lines["tax_line"], lines["first_apron"], lines["second_apron"],
                          lines["salary_floor"]), (164_961_000, 200_428_000, 209_015_000, 221_686_000, 148_465_000))
        self.assertEqual(LINES["salary_cap"], round(164_961_000 * 1.035))

    def test_true_max_by_service_or_105_percent_of_previous(self):
        self.assertEqual(round(cl.true_max_salary("2026-27", 3)), 41_240_250)
        self.assertEqual(round(cl.true_max_salary("2026-27", 8)), 49_488_300)
        self.assertEqual(round(cl.true_max_salary("2026-27", 12)), 57_736_350)
        self.assertEqual(round(cl.true_max_salary("2026-27", 3, previous_salary=50_000_000)), 52_500_000)

    def test_minimum_scale_by_service_and_the_veteran_minimum_cap_charge(self):
        self.assertEqual([cl.minimum_salary("2026-27", s) for s in (0, 1, 2, 3, 10, 15)],
                         [1_357_763, 2_185_116, 2_449_421, 2_537_526, 3_876_529, 3_876_529])
        # A one-year minimum for a 10-year veteran pays $3.88M but counts $2.45M (the league reimburses the rest).
        self.assertEqual(cl.minimum_cap_charge("2026-27", 10, 1), 2_449_421)
        self.assertEqual(cl.minimum_cap_charge("2026-27", 10, 2), 3_876_529, "two-year minimums are not reimbursed")
        self.assertEqual(cl.minimum_cap_charge("2026-27", 2, 1), 2_449_421)

    def test_raises_are_a_share_of_year_one_not_compounded(self):
        self.assertEqual(cl.raise_schedule(30_000_000, 3, 0.08), [30_000_000, 32_400_000, 34_800_000])
        self.assertNotEqual(cl.raise_schedule(30_000_000, 3, 0.08)[2], 34_992_000, "the old compounding")
        self.assertEqual(cl.raise_schedule(10_000_000, 4, 0.05), [10_000_000, 10_500_000, 11_000_000, 11_500_000])

    def test_ai_re_signing_terms_use_the_legal_schedule(self):
        star = {"id": "s", "age": 26, "minutes_projection": 34, "_star_ask_millions": 30.0, "draft_year": 2020,
                "_bird": {"level": "full"}}
        terms = sv.ai_re_signing_contract_terms({"player_season_stats": {}}, star, SEASON)
        # CONTRACT-TERMS: AI deals take a salary path at the real shares (this one draws flat); each path is the legal
        # schedule off year one (8% with Bird rights).
        expected = {"rising": [30_000_000, 32_400_000, 34_800_000], "flat": [30_000_000] * 3,
                    "declining": [30_000_000, 27_600_000, 25_200_000]}[terms["salary_path"]]
        self.assertEqual([r["salary"] for r in terms["seasons"]][:3], expected)
        with patch("nba_gm_data.contract_terms.ai_structure", return_value={"path": "rising", "option": "none"}):
            terms = sv.ai_re_signing_contract_terms({"player_season_stats": {}}, star, SEASON)
        self.assertEqual([r["salary"] for r in terms["seasons"]][:3], [30_000_000, 32_400_000, 34_800_000])

    def test_trade_dates_for_new_signings(self):
        self.assertEqual(cl.trade_eligible_date("2027-07-06", SEASON), "2027-12-15")
        self.assertEqual(cl.trade_eligible_date("2027-10-01", SEASON), "2028-01-01", "three months when later")
        # A big Bird raise (over 20%) that leaves the team over the cap waits until January 15.
        self.assertEqual(cl.trade_eligible_date("2027-07-06", SEASON, route="bird", bird_level="full",
                                                previous_salary=10e6, first_salary=20e6, over_cap_after=True),
                         "2028-01-15")
        self.assertEqual(cl.trade_eligible_date("2027-07-06", SEASON, route="bird", bird_level="full",
                                                previous_salary=10e6, first_salary=11e6, over_cap_after=True),
                         "2027-12-15")


class HoldsAndRoom(unittest.TestCase):
    def setUp(self):
        player, contract, rights = own_free_agent(10_000_000)
        self.own = player
        self.data = league(145_000_000, extra=[(player, contract), (outsider(), None)])
        self.save = summer(contract_overrides={"own": rights["override"]}, re_signing_rights=[rights["right"]],
                           free_agent_player_ids=["own", "fa"])

    def payroll(self):
        return cl.team_payroll(self.data, self.save, "t", SEASON)

    def test_full_bird_hold_is_190_percent_below_the_average_salary(self):
        p = self.payroll()
        self.assertEqual([(h["player_id"], h["kind"]) for h in p["holds"]], [("own", "full_bird")])
        self.assertEqual(p["holds"][0]["amount"], 19_000_000)
        self.assertAlmostEqual(p["cap_room"], LINES["salary_cap"] - 145e6 - 19e6, delta=2)
        self.assertAlmostEqual(p["tax_payroll"], 145_000_000, delta=1, msg="holds don't count for the tax or the aprons")

    def test_keep_the_19m_hold_re_sign_him_for_less_then_use_the_freed_room(self):
        outside = next(p for p in self.data["players"] if p["id"] == "fa")
        before = cl.quote(self.data, self.save, "t", outside, 15e6, 3)
        self.assertNotEqual(before["route"], "cap_room", "only $6.7M of room while his $19M hold is on the books")
        # Re-sign him for $8M with his Bird rights (the real application path writes the contract and commits).
        resign = cl.quote(self.data, self.save, "t", self.own, 8e6, 3)
        self.assertEqual(resign["route"], "bird")
        offer = {"id": "o1", "player_id": "own", "team_id": "t", "years": 3, "aav_millions": 8.0, "day": 1,
                 "season": "2026-27", "status": "active", "payment": resign["payment"]}
        negotiation = play.negotiation_from_free_agency_offer(self.save, offer, self.own, {"id": "t", "abbrev": "T"}, 7)
        self.save.setdefault("pending_contract_negotiations", []).append(negotiation)
        self.save["version"] = "league_save_v1"
        with patch("nba_gm_data.contract_ai.queue_press_event_if_user_involved"):
            result = ca.apply_contract_to_save_state(self.save, negotiation["negotiation"]["id"], date=TODAY)
        self.assertEqual(result["status"], "applied")
        written = self.save["contract_overrides"]["own"]
        self.assertEqual([r["salary"] for r in written["seasons"]], [8_000_000, 8_640_000, 9_280_000], "8% Bird raises")
        self.assertEqual(written["payment_route"], "bird")
        self.assertEqual(written["trade_eligible_date"], "2027-12-15")
        after = self.payroll()
        self.assertEqual(after["holds"], [])
        self.assertAlmostEqual(after["cap_room"], LINES["salary_cap"] - 153e6, delta=2)
        paid = cl.quote(self.data, self.save, "t", outside, 15e6, 3)
        self.assertEqual(paid["route"], "cap_room", "the room his lower salary freed")
        self.assertIn("gives up the full and taxpayer mid-level", paid["locks"])

    def test_renouncing_frees_the_hold_and_the_bird_rights(self):
        preview = cl.renounce_preview(self.data, self.save, "t", "own")
        self.assertAlmostEqual(preview["cap_room_after_millions"] - preview["cap_room_before_millions"], 19.0, places=1)
        self.assertTrue(cl.renounce(self.save, "t", "own"))
        self.assertEqual(self.payroll()["holds"], [])
        self.assertIsNone(cl.incumbent_bird(self.data, self.save, self.own, "t"), "no Bird rights after renouncing")
        self.assertEqual(cl.quote(self.data, self.save, "t", self.own, 20e6, 3)["route"], "cap_room")

    def test_empty_roster_spots_below_12_carry_a_rookie_minimum_from_july_1(self):
        data = league(100_000_000, count=9)
        p = cl.team_payroll(data, summer(), "t", SEASON)
        self.assertEqual(p["empty_roster_spots"], 3)
        self.assertEqual(p["roster_charge"], 3 * cl.minimum_salary(SEASON, 0))
        june = summer(state={"current_date": "2027-06-27", "phase": "re_signing"})
        self.assertEqual(cl.team_payroll(data, june, "t", SEASON)["empty_roster_spots"], 0)

    def test_ai_renounces_only_when_it_opens_real_room(self):
        # $145M + $19M hold: renouncing opens about $25M, more than the full mid-level -> the AI renounces a player it
        # is not keeping, and keeps him when he is in its plans.
        self.assertEqual(cl.ai_renounce_for_room(self.data, self.save, "t", {"own"}), [])
        self.assertEqual(cl.ai_renounce_for_room(self.data, self.save, "t", set()), ["own"])
        heavy = league(185_000_000, extra=[(self.own, None)])
        _, _, rights = own_free_agent(10_000_000)
        save = summer(contract_overrides={"own": rights["override"]}, re_signing_rights=[rights["right"]])
        self.assertEqual(cl.ai_renounce_for_room(heavy, save, "t", set()), [], "still over the cap: keep the hold")


class ExceptionsAndHardCaps(unittest.TestCase):
    def test_a_team_with_cap_room_loses_the_full_mid_level(self):
        data, save = league(120_000_000, extra=[(outsider("a"), None), (outsider("b"), None)]), summer()
        a, b = data["players"][-2:]
        room = cl.quote(data, save, "t", a, 45e6, 4)
        self.assertEqual(room["route"], "cap_room")
        cl.commit(save, "t", "a", room["payment"])
        save["roster_overrides"] = {"a": "t"}
        save["contract_overrides"] = {"a": {"team_id": "t", "signed_season": SEASON,
                                            "seasons": cl.contract_seasons(room["payment"])}}
        p = cl.team_payroll(data, save, "t", SEASON)
        self.assertFalse(p["exceptions"]["non_taxpayer_mle"]["available"])
        self.assertFalse(p["exceptions"]["bi_annual"]["available"])
        self.assertTrue(p["exceptions"]["room_mle"]["available"])
        second = cl.quote(data, save, "t", b, 9e6, 3)
        self.assertEqual(second["route"], "room_mle")
        self.assertFalse(cl.quote(data, save, "t", b, 12e6, 3)["ok"], "the room mid-level is smaller")

    def test_the_full_mid_level_splits_and_hard_caps_at_the_first_apron(self):
        data, save = league(190_000_000, extra=[(outsider("a"), None), (outsider("b"), None)]), summer()
        a, b = data["players"][-2:]
        first = cl.quote(data, save, "t", a, 9e6, 3)
        self.assertEqual(first["route"], "non_taxpayer_mle")
        self.assertIn("hard-caps T at the first apron", first["locks"])
        cl.commit(save, "t", "a", first["payment"])
        self.assertEqual(cl.hard_cap(save, "t", SEASON)["level"], "first_apron")
        balance = cl.exception_amount("non_taxpayer_mle", SEASON) - 9e6
        self.assertEqual(cl.quote(data, save, "t", b, 6e6, 2)["route"], "non_taxpayer_mle", f"${balance/1e6:.2f}M left")
        self.assertFalse(cl.quote(data, save, "t", b, 7e6, 2, route="non_taxpayer_mle")["ok"])

    def test_a_taxpayer_team_uses_the_taxpayer_mid_level(self):
        data, save = league(218_000_000, extra=[(outsider(), None)]), summer()   # above the first apron
        fa = data["players"][-1]
        full = cl.quote(data, save, "t", fa, 6e6, 2, route="non_taxpayer_mle")
        self.assertFalse(full["ok"], "the full mid-level would take it past the first apron")
        q = cl.quote(data, save, "t", fa, 6e6, 2)
        self.assertEqual(q["route"], "taxpayer_mle")
        self.assertIn("second apron", q["locks"])
        self.assertFalse(cl.quote(data, save, "t", fa, 7e6, 2)["ok"], "more than the taxpayer amount")
        self.assertFalse(cl.quote(data, save, "t", fa, 6e6, 3)["ok"], "taxpayer mid-level deals are at most two years")
        self.assertEqual(cl.quote(data, save, "t", fa, 2.6e6, 1)["route"], "minimum")

    def test_a_hard_capped_team_cant_use_bird_rights_past_its_ceiling(self):
        player, contract, rights = own_free_agent(15_000_000)
        data = league(200_000_000, extra=[(player, contract), (outsider(), None)])
        save = summer(contract_overrides={"own": rights["override"]}, re_signing_rights=[rights["right"]])
        mle = cl.quote(data, save, "t", data["players"][-1], 8e6, 2)
        self.assertEqual(mle["route"], "non_taxpayer_mle")
        cl.commit(save, "t", "fa", mle["payment"])
        save["roster_overrides"] = {"fa": "t"}
        save["contract_overrides"]["fa"] = {"team_id": "t", "signed_season": SEASON,
                                            "seasons": cl.contract_seasons(mle["payment"])}
        blocked = cl.quote(data, save, "t", player, 20e6, 4)
        self.assertFalse(blocked["ok"])
        bird_row = next(r for r in blocked["routes"] if r["route"] == "bird")
        self.assertIn("hard-capped at the first apron", bird_row["reason"])
        fits = LINES["first_apron"] - 208e6
        self.assertEqual(cl.quote(data, save, "t", player, fits - 1000, 4)["route"], "bird", "under the ceiling: fine")

    def test_bird_rights_go_past_both_aprons_when_no_hard_cap_is_triggered(self):
        player, contract, rights = own_free_agent(30_000_000, signed="2023-24")
        data = league(225_000_000, extra=[(player, contract)])
        save = summer(contract_overrides={"own": rights["override"]}, re_signing_rights=[rights["right"]])
        q = cl.quote(data, save, "t", player, 35e6, 5)
        self.assertEqual((q["route"], q["payment"]["bird_level"]), ("bird", "full"))
        self.assertEqual(q["payment"]["schedule"][4]["salary"], round(35e6 * 1.32))
        self.assertIsNone(q["payment"]["hard_cap"])

    def test_early_bird_needs_two_years(self):
        player, contract, rights = own_free_agent(8_000_000, signed="2025-26")
        data = league(230_000_000, extra=[(player, contract)])
        save = summer(contract_overrides={"own": rights["override"]}, re_signing_rights=[rights["right"]])
        one = cl.quote(data, save, "t", player, 12e6, 1)
        self.assertFalse(one["ok"])
        self.assertIn("at least two years", next(r for r in one["routes"] if r["route"] == "bird")["reason"])
        two = cl.quote(data, save, "t", player, 12e6, 2)
        self.assertEqual((two["route"], two["payment"]["bird_level"]), ("bird", "early"))

    def test_the_max_is_enforced_when_signing(self):
        data, save = league(60_000_000, extra=[(outsider(draft_year=2023), None)]), summer()
        over = cl.quote(data, save, "t", data["players"][-1], 45e6, 4)   # 4 years of service: 25% max = $42.7M
        self.assertFalse(over["ok"])
        self.assertIn("maximum salary", over["message"])

    def test_the_bi_annual_cannot_be_used_two_years_in_a_row(self):
        data = league(205_000_000, extra=[(outsider(), None)])
        save = summer(cap_ledger={"version": 1, "seasons": {"2026-27": {"t": {"used": {"bi_annual": 5e6},
                                                                                 "signings": [], "used_room": False}}}})
        p = cl.team_payroll(data, save, "t", SEASON)
        self.assertFalse(p["exceptions"]["bi_annual"]["available"])
        self.assertIn("two seasons in a row", p["exceptions"]["bi_annual"]["reason"])

    def test_outstanding_offers_hold_their_money(self):
        data, save = league(190_000_000, extra=[(outsider("a"), None), (outsider("b"), None)]), summer()
        a, b = data["players"][-2:]
        q = cl.quote(data, save, "t", a, 12e6, 3)
        offer = cl.reserve({"id": "x", "team_id": "t", "player_id": "a", "status": "active", "aav_millions": 12.0}, q["payment"])
        save["free_agent_offers"] = [offer]
        self.assertFalse(cl.quote(data, save, "t", b, 12e6, 3, route="non_taxpayer_mle")["ok"], "the bid holds $12M")
        self.assertTrue(cl.quote(data, save, "t", a, 12e6, 3)["ok"], "his own bid doesn't block him")
        offer["status"] = "rejected"
        self.assertTrue(cl.quote(data, save, "t", b, 12e6, 3, route="non_taxpayer_mle")["ok"], "released")

    def test_waiver_claims_need_room_an_exception_or_a_minimum_contract(self):
        data, save = league(200_000_000), summer()
        self.assertEqual(cl.absorb_route(data, save, "t", 8e6, 8e6, 2)["route"], "non_taxpayer_mle")
        self.assertFalse(cl.absorb_route(data, save, "t", 20e6, 20e6, 2)["ok"])
        self.assertEqual(cl.absorb_route(data, save, "t", 2e6, 2e6, 1, minimum=True)["route"], "minimum")


class ScreenMatchesSave(unittest.TestCase):
    """Rule 4: the offer screen's quote is what the save writes."""

    @classmethod
    def setUpClass(cls):
        from nba_gm_data.app_actions import load_app_canonical
        cls.root = Path(__file__).resolve().parents[1]
        cls.canonical = load_app_canonical(cls.root)

    def test_quote_action_schedule_is_the_contract_the_save_writes(self):
        from nba_gm_data.app_actions import dispatch_app_action
        with TemporaryDirectory() as folder:
            path = Path(folder) / "screen.json"
            sv.create_league_save(self.root, self.canonical, "TOR", path, seed=17)
            saved = sv.load_save(path)
            sv.set_save_date_phase(saved, "2027-07-02")
            sv.write_save(path, saved)
            active = sv.canonical_with_save(self.canonical, saved)
            player = next(p for p in active["players"] if p["id"] in saved["free_agent_player_ids"]
                          and 6 <= float(p.get("minutes_projection") or 0) <= 20)

            def action(name, **payload):
                return dispatch_app_action(name, {"save_path": str(path), **payload}, root=self.root,
                                           save_dir=folder, canonical=self.canonical)
            terms = {"player_id": player["id"], "years": 3, "aav_millions": 4.0}
            quote = action("free_agent_offer_quote", **terms)["quote"]
            self.assertTrue(quote["ok"], quote)
            accept = {"terms": {"best_rival": None, "ask_millions": 3.0, "mode": "market", "bar": 50},
                      "context": {}, "interest": 99.0, "verdict": "accept", "floor_millions": 3.0}
            with patch("nba_gm_data.play.user_offer_decision", return_value=accept):
                result = action("submit_free_agent_offer", **terms, guaranteed=True, auto_apply=True, seed=17)
            self.assertEqual(result["apply_result"]["status"], "applied", result)
            written = sv.load_save(path)["contract_overrides"][player["id"]]
            self.assertEqual([round(r["salary"] / 1e6, 3) for r in written["seasons"]],
                             [row["salary_millions"] for row in quote["schedule"]])
            self.assertEqual(written["payment_route"], quote["route"])
            self.assertEqual(written["trade_eligible_date"], quote["trade_eligible_date"])
            room = action("free_agency_room", team="TOR", seed=17)
            used = room["cap_ledger"]["current"]["exceptions"].get(quote["route"], {}).get("used_millions")
            if quote["route"] in cl.EXCEPTION_ROUTES:
                self.assertAlmostEqual(used, quote["schedule"][0]["cap_charge_millions"], places=2)


if __name__ == "__main__":
    unittest.main()
