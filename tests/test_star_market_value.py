"""Superstar trade-market shape under the new (input-based) ratings, 2026-11-17.

The playoff-translation recipe is fitted to real playoff production (scripts/fit_playoff_translation.py) and the
superstar value floor ramps in instead of switching on at hard cutoffs. The older benchmark tests in
test_foundation / test_fantasy_draft pin the legacy ratings, which undervalue Luka (on-court 72).
"""
from pathlib import Path
import unittest

from nba_gm_data.app_actions import load_app_canonical
from nba_gm_data.ratings_model import install_inputs_model
from nba_gm_data.transactions import goat_exception_player, market_trade_target_value, market_value_after_star_and_surplus_shape, with_transaction_context

ROOT = Path(__file__).resolve().parents[1]


class StarMarketValueTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        canonical = load_app_canonical(ROOT)
        install_inputs_model(canonical, ROOT)
        cls.active = with_transaction_context(canonical)
        values = {v["player_id"]: v for v in cls.active["player_asset_valuations"]}
        cls.market = {p["name"]: market_trade_target_value(p, values[p["id"]])
                      for p in cls.active["players"] if p["id"] in values}
        # LeBron's fixed one-of-one value (AGENTS.md rule 11) is a deliberate exception, so rank the rest of the market.
        regular = [name for name in cls.market if not goat_exception_player({"name": name})]
        cls.rank = {name: n + 1 for n, name in enumerate(sorted(regular, key=lambda n: -cls.market[n]))}

    def test_consensus_superstars_lead_the_market(self):
        for name in ("Nikola Jokić", "Luka Dončić", "Shai Gilgeous-Alexander", "Giannis Antetokounmpo"):
            self.assertLessEqual(self.rank[name], 6, (name, self.rank[name], self.market[name]))
        giannis = self.market["Giannis Antetokounmpo"]
        # 2026-11-19: the playoff blend (half Basketball Index playoff grades) moved Giannis 94.0 -> 90.4; still far
        # above good starters.
        self.assertGreater(giannis - self.market["LaMelo Ball"], 20)
        self.assertGreater(giannis, self.market["Tyler Herro"] + 6)
        self.assertGreater(giannis, self.market["Jrue Holiday"] + 10)

    def test_superstar_floor_has_no_cliff(self):
        player = {"id": "probe", "age": 27, "minutes_projection": 34}
        values = []
        for tenth in range(740, 821):
            on_court = tenth / 10
            values.append(market_value_after_star_and_surplus_shape(
                player, {"on_court_value": on_court, "playoff_value": 84.0, "contract_surplus": 0.0, "player_value": 84.0,
                         "development_upside": 0.0}, 84.0))
        steps = [b - a for a, b in zip(values, values[1:])]
        self.assertTrue(all(step >= -1e-9 for step in steps))   # never lower for a better player
        self.assertLess(max(steps), 1.5)                         # no jump between neighbouring 0.1 steps


if __name__ == "__main__":
    unittest.main()
