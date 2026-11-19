"""Trade step 1: how AI teams value their own players (docs/agents/tasks/trade-step1-own-value.md).

Direction and monotonicity of the attachment / tenure / investment premium, the tenure ledger (seeding from real data
and folding transaction logs), the own-player role correction, and that none of it touches the human team.
"""
from copy import deepcopy
from pathlib import Path
import unittest

from nba_gm_data import trade_ownership as own
from nba_gm_data.app_actions import load_app_canonical
from nba_gm_data.transactions import (destination_role_multipliers, package_value_breakdown, package_value_for_team,
                                      player_asset_values_by_id, player_by_id, trade_value_role_minutes,
                                      with_transaction_context)

ROOT = Path(__file__).resolve().parents[1]
TODAY = "2026-10-20"


def find(canonical, name):
    return next(p for p in canonical["players"] if p["name"] == name)


class OwnershipLedgerSeedTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.canonical = load_app_canonical(ROOT)
        cls.ledger = own.seed_player_tenure(cls.canonical, root=ROOT)

    def entry(self, name):
        return self.ledger["players"][find(self.canonical, name)["id"]]

    def test_franchise_player_is_homegrown_with_long_tenure(self):
        jokic = self.entry("Nikola Jokić")
        self.assertTrue(jokic["homegrown"])
        self.assertEqual(jokic["how"], "draft")
        self.assertLessEqual(jokic["since"], "2015-10-01")

    def test_real_draft_trade_up_is_remembered(self):
        clifford = self.entry("Nique Clifford")
        self.assertTrue(clifford["homegrown"])
        self.assertTrue(clifford["draft"]["traded_up"])
        self.assertEqual(clifford["draft"]["pick"], 24)

    def test_injured_season_does_not_reset_tenure(self):
        # Haliburton missed 2025-26; his latest season is still with Indiana.
        self.assertLess(self.entry("Tyrese Haliburton")["since"], "2023-01-01")

    def test_real_offseason_trade_is_an_investment(self):
        giannis = self.entry("Giannis Antetokounmpo")
        self.assertEqual(giannis["how"], "trade")
        self.assertTrue(any(row["kind"] == "trade" for row in giannis["investments"]))

    def test_fantasy_draft_has_no_tenure(self):
        self.assertEqual(own.seed_player_tenure(self.canonical, game_mode="fantasy_draft", root=ROOT)["players"], {})

    def test_seeding_is_deterministic(self):
        self.assertEqual(own.seed_player_tenure(self.canonical, root=ROOT), self.ledger)


class LedgerFoldTests(unittest.TestCase):
    def base(self):
        return {"version": 1, "players": {"p1": {"team_id": "team_a", "since": "2020-10-01", "how": "draft",
                                                  "homegrown": True, "draft": None, "investments": []}},
                "folded_log_ids": [], "folded_since": ""}

    def logs(self):
        return [
            {"id": "t1", "date": "2026-12-01", "transaction_type": "trade", "status": "applied_to_save_ledger",
             "teams": ["team_a", "team_b"],
             "assets": {"from_assets": [{"kind": "player", "id": "p1"}], "to_assets": [{"kind": "pick", "id": "pick_x"}]},
             "evaluations": [{"perspective_team_id": "team_a", "outgoing_value": 50.0},
                             {"perspective_team_id": "team_b", "outgoing_value": 42.0}]},
            {"id": "t2", "date": "2027-06-24", "transaction_type": "trade", "status": "applied_to_save_ledger",
             "teams": ["team_c", "team_d"],
             "assets": {"from_assets": [{"kind": "pick", "id": "pick_c1"}], "to_assets": [{"kind": "pick", "id": "pick_d1"}]},
             "evaluations": []},
            {"id": "d1", "date": "2027-06-25", "transaction_type": "draft_selection", "teams": ["team_d"],
             "assets": {"pick_id": "pick_c1", "prospect_id": "prospect_1"}},
            {"id": "s1", "date": "2027-07-03", "transaction_type": "free_agent_signing", "teams": ["team_e"],
             "assets": {"player_id": "p2", "contract": {"team_id": "team_e", "annual_salary": 30_000_000, "years": 4}}},
            {"id": "w1", "date": "2027-10-03", "transaction_type": "waiver_claim", "teams": ["team_e", "team_f"],
             "assets": {"player_id": "p3"}},
        ]

    def rookies(self):
        return [{"prospect_id": "prospect_1", "player_id": "rookie_1", "team_id": "team_d", "overall_pick": 5, "draft_year": "2027"}]

    def test_logs_record_team_changes_and_investments(self):
        ledger = own.fold_transaction_logs(self.base(), self.logs(), self.rookies())
        p1 = ledger["players"]["p1"]
        self.assertEqual((p1["team_id"], p1["how"], p1["since"], p1["homegrown"]), ("team_b", "trade", "2026-12-01", False))
        self.assertEqual(p1["investments"][0]["package_value"], 42.0)
        rookie = ledger["players"]["rookie_1"]
        self.assertTrue(rookie["homegrown"])
        self.assertEqual(rookie["draft"]["pick"], 5)
        self.assertTrue(rookie["draft"]["traded_up"])  # team_d received pick_c1 the day before
        self.assertEqual(ledger["players"]["p2"]["investments"][0]["kind"], "signing")
        self.assertEqual(ledger["players"]["p3"]["team_id"], "team_f")

    def test_fold_is_idempotent_and_does_not_mutate_input(self):
        base = self.base()
        before = deepcopy(base)
        once = own.fold_transaction_logs(base, self.logs(), self.rookies())
        twice = own.fold_transaction_logs(once, self.logs(), self.rookies())
        self.assertEqual(base, before)
        self.assertEqual(once["players"], twice["players"])

    def test_folding_in_pieces_matches_folding_at_once(self):
        logs = self.logs()
        at_once = own.fold_transaction_logs(self.base(), logs, self.rookies())
        piecewise = self.base()
        for end in range(1, len(logs) + 1):
            piecewise = own.fold_transaction_logs(piecewise, logs[:end], self.rookies())
        self.assertEqual(at_once["players"], piecewise["players"])

    def test_release_ends_the_stint(self):
        logs = [{"id": "c1", "date": "2027-01-02", "transaction_type": "roster_cut", "teams": ["team_a"],
                 "assets": {"player_id": "p1"}}]
        self.assertIsNone(own.fold_transaction_logs(self.base(), logs)["players"]["p1"]["team_id"])


class PremiumDirectionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        canonical = load_app_canonical(ROOT)
        canonical["meta"]["current_date"] = TODAY
        canonical[own.LEDGER_KEY] = own.seed_player_tenure(canonical, root=ROOT)
        cls.active = with_transaction_context(canonical)
        cls.active["meta"]["current_date"] = TODAY
        cls.player = next(p for p in cls.active["players"] if p["name"] == "Nikola Jokić")
        cls.team = cls.player["team_id"]

    def premium(self, entry=None, *, human=False, base=100.0):
        active = dict(self.active)
        ledger = deepcopy(active[own.LEDGER_KEY])
        if entry is not None:
            ledger["players"][self.player["id"]] = {**ledger["players"][self.player["id"]], **entry}
        active[own.LEDGER_KEY] = ledger
        active["_human_team_ids"] = [self.team] if human else []
        return own.own_player_premium(active, self.player, self.team, base)

    def test_more_tenure_never_lowers_the_premium(self):
        totals = [self.premium({"since": f"{year}-10-01", "homegrown": False})["total"] for year in range(2026, 2010, -1)]
        self.assertTrue(all(b >= a - 1e-9 for a, b in zip(totals, totals[1:])), totals)
        self.assertGreater(totals[-1], totals[0])

    def test_more_or_newer_investment_never_lowers_the_premium(self):
        base = {"since": "2020-10-01", "homegrown": False, "draft": None, "investments": []}
        none = self.premium(base)["total"]
        signing = {"kind": "signing", "date": "2026-07-06", "annual_salary": 40_000_000, "years": 4}
        one = self.premium({**base, "investments": [signing]})["total"]
        two = self.premium({**base, "investments": [signing, {"kind": "trade", "date": "2026-02-01", "package_value": 90.0,
                                                               "package_player_ids": [self.player["id"]]}]})["total"]
        old = self.premium({**base, "investments": [{**signing, "date": "2025-03-01"}]})["total"]
        self.assertLessEqual(none, one)
        self.assertLessEqual(one, two)
        self.assertLessEqual(old, one)
        fades = [own.investment_fade(days) for days in range(0, 900, 15)]
        self.assertTrue(all(b <= a for a, b in zip(fades, fades[1:])))
        self.assertEqual(own.investment_fade(800), 0.0)

    def test_better_pick_and_trading_up_never_lower_draft_investment(self):
        rates = [own.draft_slot_rate(pick) for pick in range(1, 61)]
        self.assertTrue(all(b <= a for a, b in zip(rates, rates[1:])))
        base = {"since": "2026-06-24", "homegrown": True, "investments": []}
        plain = self.premium({**base, "draft": {"year": 2026, "pick": 12, "date": "2026-06-24", "traded_up": False}})
        up = self.premium({**base, "draft": {"year": 2026, "pick": 12, "date": "2026-06-24", "traded_up": True}})
        self.assertGreater(up["investment"], plain["investment"])

    def test_never_applies_to_the_human_team_or_other_teams_players(self):
        self.assertEqual(self.premium(human=True)["total"], 0.0)
        other = next(t["id"] for t in self.active["teams"] if t["id"] != self.team)
        self.assertEqual(own.own_player_premium(self.active, self.player, other, 100.0)["total"], 0.0)

    def test_premium_is_modest_and_deterministic(self):
        first, second = self.premium(), self.premium()
        self.assertEqual(first["total"], second["total"])
        self.assertGreater(first["total"], 0.0)
        self.assertLessEqual(first["total"], 100.0 * own.TOTAL_RATE_CAP)

    def test_a_reason_to_move_scales_the_premium_down(self):
        reasons_active = dict(self.active)
        reasons_active["team_trade_blocks"] = {self.team: [self.player["id"]]}
        listed = own.own_player_premium(reasons_active, self.player, self.team, 100.0)
        self.assertIn("gm_listed", listed["detail"]["move_reasons"])
        self.assertLess(listed["total"], self.premium()["total"])


class OwnPlayerValueTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        canonical = load_app_canonical(ROOT)
        canonical["meta"]["current_date"] = TODAY
        canonical[own.LEDGER_KEY] = own.seed_player_tenure(canonical, root=ROOT)
        cls.active = with_transaction_context(canonical)
        cls.active["meta"]["current_date"] = TODAY

    def test_own_role_is_at_least_the_minutes_he_plays(self):
        # A rotation player whose on-court rank on his own team is low still costs his team the role he plays.
        values = player_asset_values_by_id(self.active)
        for player in sorted(self.active["players"], key=lambda p: p["id"]):
            if not player.get("team_id") or player["id"] not in values or float(player.get("minutes_projection") or 0) < 24:
                continue
            asset = [{"kind": "player", "id": player["id"]}]
            ai_view = destination_role_multipliers(self.active, asset, player["team_id"])[player["id"]]
            minutes = trade_value_role_minutes(player, values[player["id"]])
            self.assertGreaterEqual(ai_view, round(min(1.22, (min(36.0, minutes) / 28.0) ** 1.8), 3) - 1e-9,
                                    player["name"])

    def test_human_team_valuations_are_unchanged(self):
        player = find(self.active, "Stephen Curry")
        team = player["team_id"]
        asset = [{"kind": "player", "id": player["id"]}]
        human = {**self.active, "_human_team_ids": [team]}
        no_ledger = {**human, own.LEDGER_KEY: {}}
        self.assertEqual(package_value_for_team(human, asset, team), package_value_for_team(no_ledger, asset, team))
        ai = {**self.active, "_human_team_ids": []}
        self.assertGreater(package_value_for_team(ai, asset, team), 0)

    def test_breakdown_explains_the_own_player_price(self):
        player = find(self.active, "Nikola Jokić")
        team = player["team_id"]
        breakdown = package_value_breakdown({**self.active, "_human_team_ids": []}, [{"kind": "player", "id": player["id"]}], team)
        detail = breakdown["asset_details"][0]
        self.assertIn("own_player_view", detail)
        self.assertGreater(detail["components"].get("tenure", 0), 0)
        self.assertAlmostEqual(breakdown["total"], package_value_for_team({**self.active, "_human_team_ids": []},
                                                                          [{"kind": "player", "id": player["id"]}], team), places=1)
        self.assertEqual(player_by_id(self.active, player["id"])["team_id"], team)


if __name__ == "__main__":
    unittest.main()
