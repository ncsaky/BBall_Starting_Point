"""TRADE-CORE: a team fresh off a playoff run does not sell one of its best players for tax savings or as a "close
call" (docs/agents/tasks/trade-core.md)."""
import unittest

from nba_gm_data import team_planning as tp
from nba_gm_data import trade_tax as tax
from nba_gm_data import transactions as tx

from test_trade_step4 import P, SEASON, league, set_contract

SUMMER = "2027-07-01"


def run_team(rounds=1, date=SUMMER, window="exiting", games=0, **plan):
    """Team A over the tax line (a0 on $230M), having won ``rounds`` playoff series in 2027 with its top three still there."""
    data = league()
    set_contract(data, "a0", [(SEASON, 230_000_000), ("2027-28", 230_000_000), ("2028-29", 230_000_000)])
    data["meta"]["current_date"] = date
    core = [pid for _, pid in tax._depth_chart(data, "a")[:3]]
    data["team_plans"] = {"a": {"postseason_outcomes": [{"year": "2027", "rounds_won": rounds, "core_ids": core}], **plan}}
    data["save_team_records"] = {"a": {"wins": games, "losses": 0}}
    for state in data["team_strategic_states"]:
        if state["team_id"] == "a":
            state["window_phase"] = window
    return data


def top(data, place=0):
    return tax._depth_chart(data, "a")[place][1]


class FreshOffARunTests(unittest.TestCase):
    def test_one_series_win_counts_through_the_summer_and_the_first_25_games(self):
        self.assertTrue(tp.fresh_off_playoff_run(run_team(), "a"))
        self.assertTrue(tp.fresh_off_playoff_run(run_team(date="2027-11-20", games=24), "a"))
        self.assertFalse(tp.fresh_off_playoff_run(run_team(date="2027-12-20", games=25), "a"))

    def test_a_first_round_exit_or_a_broken_up_core_does_not_count(self):
        self.assertFalse(tp.fresh_off_playoff_run(run_team(rounds=0), "a"))
        data = run_team()
        gone = set(data["team_plans"]["a"]["postseason_outcomes"][0]["core_ids"][:2])
        for player in data["players"]:
            if player["id"] in gone:
                player["team_id"] = "b"
        self.assertFalse(tp.fresh_off_playoff_run(data, "a"))


class TaxCreditTests(unittest.TestCase):
    def test_no_tax_credit_for_a_core_player_after_one_series_win(self):
        data = run_team()
        self.assertGreater(tax.tax_value(run_team(rounds=0), "a", [], [P("a0")]), 0)
        for place in range(3):
            self.assertTrue(tax.contender_core_outgoing(data, "a", [P(top(data, place))]))
        self.assertFalse(tax.contender_core_outgoing(data, "a", [P(top(data, 3))]))
        self.assertEqual(tax.tax_value(data, "a", [], [P(top(data))]), 0.0)

    def test_the_clubs_own_retool_candidate_can_still_be_moved_for_savings(self):
        data = run_team()
        marked = top(data, 1)
        data["team_plans"]["a"]["retool_candidate_id"] = marked
        self.assertFalse(tax.contender_core_outgoing(data, "a", [P(marked)]))
        self.assertTrue(tax.contender_core_outgoing(data, "a", [P(marked), P(top(data))]))
        # A contender proper keeps the whole top three, marked or not.
        peak = run_team(window="peak", retool_candidate_id=marked)
        self.assertTrue(tax.contender_core_outgoing(peak, "a", [P(marked)]))


class CloseCallTests(unittest.TestCase):
    def candidate(self, sent, net=-2.0, accepted=False):
        return {"legality": {"status": "legal"}, "accepted_by_all": False,
                "proposal": {"from_team_id": "a", "to_team_id": "b", "from_assets": [P(sent)], "to_assets": []},
                "evaluations": [
                    {"perspective_team_id": "a", "net_value": net, "outgoing_value": 100.0, "accepted": accepted},
                    {"perspective_team_id": "b", "net_value": 20.0, "outgoing_value": 20.0, "accepted": True,
                     "incoming_asset_value": 0.0}]}

    def refused(self, data, candidate):
        return tx.short_changed_core_sale(data, candidate)

    def test_a_core_player_is_not_given_up_as_a_close_call(self):
        data = run_team()
        self.assertTrue(self.refused(data, self.candidate(top(data))))
        self.assertTrue(self.refused(run_team(window="peak", rounds=0), self.candidate(top(data))))

    def test_bench_players_willing_sellers_other_teams_and_the_user_are_untouched(self):
        data = run_team()
        self.assertFalse(self.refused(data, self.candidate(top(data, 3))))
        self.assertFalse(self.refused(data, self.candidate(top(data), net=4.0, accepted=True)))
        self.assertFalse(self.refused(run_team(rounds=0), self.candidate(top(data))))
        self.assertFalse(self.refused(dict(data, _human_team_ids=["a"]), self.candidate(top(data))))

    def test_the_acceptance_check_uses_it(self):
        from unittest.mock import patch
        candidate = self.candidate(top(run_team()))
        with patch.object(tx, "useful_player_for_nothing", return_value=False), \
                patch.object(tx, "max_player_value_from_assets", return_value=0.0):
            self.assertTrue(tx.ai_trade_candidate_accepted(run_team(rounds=0), candidate))
            self.assertFalse(tx.ai_trade_candidate_accepted(run_team(), candidate))


if __name__ == "__main__":
    unittest.main()
