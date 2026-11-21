"""TRADE-VOLUME: one shared tax line for every part of the game, AI payroll discipline (re-signing, free agency, waiver
claims), and the user's free-agent offers judged by the AI bids' rule (docs/agents/tasks/trade-volume.md)."""
import unittest
from pathlib import Path
from unittest.mock import patch

from nba_gm_data import cap_rules
from nba_gm_data import narrative
from nba_gm_data import payroll_plan as pp
from nba_gm_data import play
from nba_gm_data import save as sv
from nba_gm_data import trade_tax as tax
from nba_gm_data import transactions as tx
from nba_gm_data import waivers

SEASON = "2026-27"
NEXT = "2027-28"
LINE = cap_rules.cap_lines_for_season(SEASON)["tax_line"]


def league(payroll_a: float = 197_000_000, players_a: int = 14, minutes_free: float = 30.0):
    """Team A: ``players_a`` players paid ``payroll_a`` in total this season and next; team B: a cheap roster;
    one free agent / waived player ``x`` (no team) on a one-year minimum contract."""
    data = {"meta": {"active_season": SEASON}, "teams": [{"id": "a", "abbrev": "A"}, {"id": "b", "abbrev": "B"}],
            "players": [], "contracts": [], "front_office_profiles": [{"team_id": "a", "financial_discipline": 58},
                                                                      {"team_id": "b", "financial_discipline": 58}]}
    for tid, count, total in (("a", players_a, payroll_a), ("b", 14, 120_000_000)):
        for i in range(count):
            pid = f"{tid}{i}"
            data["players"].append({"id": pid, "name": pid, "team_id": tid, "age": 27, "position": "SF",
                                    "minutes_projection": 20})
            data["contracts"].append({"player_id": pid, "team_id": tid, "seasons": [
                {"season": s, "salary": total / count} for s in (SEASON, NEXT)]})
    data["players"].append({"id": "x", "name": "Chris Veteran", "team_id": None, "age": 30, "position": "PG",
                            "minutes_projection": minutes_free})
    data["contracts"].append({"player_id": "x", "team_id": None, "seasons": [{"season": SEASON, "salary": 2_250_000}]})
    return data


def save_for(today: str, phase: str = "rebuilding", **extra):
    return {"meta": {"season": SEASON, "human_team_ids": [], "user_team_id": "b"},
            "state": {"current_date": today, "phase": "regular_season"},
            "team_plans": {"a": {"window_phase": phase}, "b": {"window_phase": "rebuilding"}}, **extra}


class SharedTaxLineTests(unittest.TestCase):
    def test_every_part_of_the_game_uses_the_same_real_lines(self):
        lines = cap_rules.cap_lines_for_season(SEASON)
        # FA-REAL: exact lines, no longer rounded to $0.1M.
        self.assertEqual(lines["tax_line"], 200_428_000)
        self.assertEqual(lines["first_apron"], 209_015_000)
        self.assertEqual(lines["hard_cap"], 221_686_000)      # second apron
        self.assertEqual(lines["salary_cap"], 164_961_000)
        for season in ("2026-27", "2027-28", "2028-29", "2030-31"):
            shared = cap_rules.cap_lines_for_season(season)
            for name, lookup in (("trade code", tx.cap_lines_for_season), ("screens", sv.cap_lines_for_season),
                                 ("news", narrative.cap_lines_for_narrative)):
                with self.subTest(season=season, part=name):
                    self.assertEqual(lookup(season)["tax_line"], shared["tax_line"])
                    self.assertEqual(lookup(season)["hard_cap"], shared["hard_cap"])
        # The trade code's tax bill starts at the same line the screens show (it used $207.4M for 2026-27).
        self.assertEqual(tax.luxury_tax_bill(LINE, SEASON), 0.0)
        self.assertGreater(tax.luxury_tax_bill(LINE + 1_000_000, SEASON), 0.0)


class PayrollPlanTests(unittest.TestCase):
    def test_projected_payroll_counts_the_minimum_contracts_still_needed(self):
        data = league(payroll_a=190_000_000, players_a=12)
        save = save_for("2027-01-10")
        self.assertEqual(pp.projected_end_payroll(data, save, "a", SEASON), 190_000_000 + 2 * pp.FILL_SALARY)
        # A signing that fills one of those spots replaces a minimum contract the team must sign anyway.
        check = pp.payroll_check(data, save, "a", SEASON, add_salary=pp.FILL_SALARY, minutes=0)
        self.assertEqual(check["after"], check["before"])
        self.assertTrue(check["ok"])

    def test_rebuilding_team_never_signs_into_the_tax_contender_pays_for_a_starter(self):
        data = league(payroll_a=197_000_000)
        crossing = dict(add_salary=6_000_000, minutes=30.0, kind="free_agency")
        rebuilding = pp.payroll_check(data, save_for("2027-07-02", "rebuilding"), "a", SEASON, **crossing)
        self.assertFalse(rebuilding["ok"])
        self.assertGreater(rebuilding["lost_payout"], 0, "crossing the line gives up the payout share")
        contender = pp.payroll_check(data, save_for("2027-07-02", "peak"), "a", SEASON, **crossing)
        self.assertTrue(contender["ok"], contender)
        bench = pp.payroll_check(data, save_for("2027-07-02", "peak"), "a", SEASON,
                                 add_salary=6_000_000, minutes=8.0, kind="free_agency")
        self.assertFalse(bench["ok"], "a bench player is not worth the tax even for a contender")

    def test_teams_that_are_not_contending_keep_room_below_the_line_for_veterans(self):
        data = league(payroll_a=180_000_000)
        veteran = dict(add_salary=8_000_000, minutes=24.0, kind="free_agency", age=30)
        rebuilding = pp.payroll_check(data, save_for("2027-07-02", "rebuilding"), "a", SEASON, **veteran)
        self.assertFalse(rebuilding["ok"])
        self.assertEqual(rebuilding["reason"], "keeps_room_below_the_line_for_its_phase")
        self.assertEqual(rebuilding["ceiling"], LINE - pp.PHASE_KEEP_ROOM["rebuilding"])
        self.assertIn("not contending", pp.plain_words(rebuilding))
        young = pp.payroll_check(data, save_for("2027-07-02", "rebuilding"), "a", SEASON, **{**veteran, "age": 23})
        self.assertTrue(young["ok"], "a rebuild invests in young players: half the room")
        self.assertEqual(young["ceiling"], LINE - pp.PHASE_KEEP_ROOM["rebuilding"] / 2)
        self.assertFalse(pp.payroll_check(data, save_for("2027-07-02", "rebuilding"), "a", SEASON,
                                          **{**veteran, "age": 23, "add_salary": 12_000_000})["ok"])
        self.assertTrue(pp.payroll_check(data, save_for("2027-07-02", "peak"), "a", SEASON, **veteran)["ok"])
        self.assertTrue(pp.payroll_check(data, save_for("2027-07-02", "rebuilding"), "a", SEASON,
                                         **{**veteran, "kind": "waiver_claim"})["ok"], "free agency and re-signing only")

    def test_payout_share_follows_the_last_recorded_season(self):
        save = save_for("2027-07-02", luxury_tax_payouts={SEASON: {"share_per_team": 11_500_000}})
        self.assertEqual(pp.expected_payout_share(save, NEXT), 11_500_000)
        self.assertEqual(pp.expected_payout_share(save_for("2027-07-02"), NEXT), pp.DEFAULT_PAYOUT_SHARE)

    def test_user_team_is_never_restricted(self):
        data = league(payroll_a=199_000_000)
        save = save_for("2027-02-10", human_team_ids=None)
        save["meta"]["human_team_ids"] = ["a"]
        self.assertTrue(pp.payroll_check(data, save, "a", SEASON, add_salary=30_000_000, kind="waiver_claim")["ok"])


class WaiverClaimTests(unittest.TestCase):
    def claim(self, today: str, phase: str, payroll: float = 199_000_000, minutes: float = 30.0):
        data = league(payroll_a=payroll, minutes_free=minutes)
        save = save_for(today, phase)
        entry = {"id": "w1", "player_id": "x", "team_id": "b", "date": today, "clearance_date": today,
                 "status": "pending", "claims": [], "contract": data["contracts"][-1]}
        with patch.object(waivers, "roster_signing_plan", return_value={"ok": True, "upgrade": 10, "cuts": []}), \
                patch.object(waivers, "claim_contract_cost", return_value={"worthwhile": True}):
            return waivers.claim_plan(data, save, entry, "a", ai=True)

    def test_a_team_under_the_line_never_claims_its_way_over_after_the_deadline(self):
        # Atlanta (Feb 2028) got under the line at the deadline, then claimed Chris Paul two days later and went over.
        after = self.claim("2027-02-07", "peak")
        self.assertFalse(after["ok"])
        self.assertIn("after the trade deadline", after["reason"])
        self.assertEqual(after["tax_plan"]["reason"], "would_cross_the_tax_line_after_the_deadline")

    def test_before_the_deadline_only_a_contender_claims_a_rotation_player_over_the_line(self):
        self.assertFalse(self.claim("2027-01-20", "rebuilding")["ok"])
        self.assertTrue(self.claim("2027-01-20", "peak")["ok"])
        self.assertFalse(self.claim("2027-01-20", "peak", minutes=6.0)["ok"], "not for a deep-bench player")

    def test_a_claim_that_stays_under_the_line_is_unaffected(self):
        self.assertTrue(self.claim("2027-02-07", "rebuilding", payroll=150_000_000)["ok"])


class ReSigningTaxTests(unittest.TestCase):
    def test_re_signing_checks_the_tax_as_well_as_the_hard_cap(self):
        data = league(payroll_a=195_000_000, players_a=13)
        player = {"id": "a_star", "name": "Expiring Starter", "team_id": "a", "age": 27, "minutes_projection": 30,
                  # FA-REAL: his own team re-signs him over the cap with his Bird rights (legal), so the owner's tax
                  # plan decides.
                  "_bird": {"level": "full", "limit": 60e6, "max_years": 5, "raise": 0.08, "previous_salary": 10e6}}
        save = save_for("2027-06-28", "rebuilding")
        terms = sv.ai_re_signing_contract_terms(save, player, NEXT)
        self.assertGreater(195_000_000 + terms["salary"], cap_rules.cap_lines_for_season(NEXT)["tax_line"])
        self.assertTrue(sv.ai_re_signing_fits_hard_cap(data, save, player, "a", NEXT, prepared_active=data))
        self.assertFalse(sv.ai_re_signing_fits_payroll_plan(data, save, player, "a", NEXT, prepared_active=data))
        self.assertFalse(sv.ai_re_signing_allowed(data, save, player, "a", NEXT, prepared_active=data))
        contender = save_for("2027-06-28", "peak")
        self.assertTrue(sv.ai_re_signing_allowed(data, contender, player, "a", NEXT, prepared_active=data))
        # Earlier re-signings in the same pass count against the owner's line (a rebuilding team says no); with Bird
        # rights a contender may still go past the aprons (FA-REAL: no blanket hard cap on Bird re-signings).
        crowded = {("a", NEXT): 20_000_000, ("a", sv.RE_SIGNING_PLAYER_COUNT_KEY): 1}
        self.assertFalse(sv.ai_re_signing_allowed(data, save, player, "a", NEXT, prepared_active=data,
                                                  committed_salary_by_team_season=crowded))
        self.assertTrue(sv.ai_re_signing_allowed(data, contender, player, "a", NEXT, prepared_active=data,
                                                 committed_salary_by_team_season=crowded))
        # A team with room keeps him.
        roomy = league(payroll_a=150_000_000, players_a=13)
        self.assertTrue(sv.ai_re_signing_allowed(roomy, save, player, "a", NEXT, prepared_active=roomy))


class UserOfferRuleTests(unittest.TestCase):
    """The user's offer competes under the AI bids' rule (Brandon Miller: ask $28.8M, a rival bid of $30.4M, signed with
    the user for $13.6M under the old minutes rule)."""

    def sign(self, save, aav, years=4, guaranteed=True):
        candidate = {"id": "p_miller", "name": "Brandon Miller", "age": 24, "position": "SF", "minutes_projection": 30.1,
                     "team_id": None}
        with patch.object(play, "load_save", return_value=save), patch.object(play, "write_save"), \
                patch.object(play, "resolve_team", return_value={"id": "team_cha", "abbrev": "CHA"}), \
                patch.object(play, "extension_retirement_blocked", return_value=False):
            return play.manual_save_pool_signing({}, Path("unused"), candidate, "CHA", years, aav, 7, guaranteed=guaranteed)

    def market(self, day, bids):
        return {"state": {"current_date": "2027-07-03", "phase": "free_agency"}, "meta": {"season": SEASON},
                "free_agency_state": {"season": SEASON, "day": day, "status": "active",
                                      "player_asks_millions": {"p_miller": 28.8}},
                "free_agent_offers": [{"id": f"bid{n}", "season": SEASON, "source": "ai", "player_id": "p_miller",
                                       "team_id": team, "years": 4, "aav_millions": aav, "interest_score": interest,
                                       "status": "active"} for n, (team, aav, interest) in enumerate(bids)],
                "team_records": {}}

    def test_the_user_loses_him_to_a_better_rival_bid(self):
        save = self.market(3, [("team_bkn", 30.4, 81.0)])
        old_price = self.sign(save, 13.6)
        self.assertFalse(old_price["accepted"])
        at_ask = self.sign(save, 28.8)
        self.assertFalse(at_ask["accepted"])
        self.assertEqual(at_ask["decision"]["decision"], "prefers_rival_bid")
        self.assertEqual(at_ask["decision"]["competing_offers"][0]["team_id"], "team_bkn")
        floor = at_ask["decision"]["ask_threshold_millions"]
        self.assertGreater(floor, 28.8, "beating the rival costs more than his ask")
        self.assertTrue(self.sign(save, floor)["accepted"])

    def test_without_rivals_he_still_needs_todays_bar(self):
        early = self.sign(self.market(1, []), 28.8)
        late = self.sign(self.market(5, []), 28.8)
        self.assertFalse(early["accepted"], "day 1: a star waits for better offers")
        self.assertEqual(early["decision"]["decision"], "reject_below_market")
        self.assertTrue(late["accepted"], "day 5: his ask is enough")
        self.assertLess(late["decision"]["ask_threshold_millions"], early["decision"]["ask_threshold_millions"] or 99)


if __name__ == "__main__":
    unittest.main()
