import unittest
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from audit_roster_floor import decompose


def snapshot(rows):
    return {"date": "2026-01-01", "players": [
        {"id": pid, "fixed24_engine": score, "rostered": True, "age": 25}
        for pid, score in rows]}


class RosterFloorTests(unittest.TestCase):
    def test_turnover_and_growth_reconcile_with_unequal_roster_sizes(self):
        result = decompose(snapshot([("a", 40), ("b", 60), ("c", 50)]),
                           snapshot([("a", 42), ("b", 61), ("d", 55), ("e", 52)]))
        self.assertAlmostEqual(result["mean_change"], result["continuing_players_contribution"]
                               + result["turnover_contribution"])
        self.assertAlmostEqual(result["residual"], 0)
        self.assertEqual(result["below70_count_change"]["net"],
                         result["after"]["below70"] - result["before"]["below70"])

    def test_unchanged_population_has_no_turnover_contribution(self):
        result = decompose(snapshot([("a", 40), ("b", 60)]),
                           snapshot([("a", 41), ("b", 59)]))
        self.assertEqual(result["turnover_contribution"], 0)
        self.assertEqual(result["entrants_at_end"]["count"], 0)

    def test_no_incumbents_still_reconciles(self):
        result = decompose(snapshot([("a", 40)]), snapshot([("b", 60)]))
        self.assertEqual(result["continuing_players_contribution"], 0)
        self.assertEqual(result["mean_change"], result["turnover_contribution"])

    def test_duplicate_and_empty_populations_are_rejected(self):
        for rows in ([], [("a", 50), ("a", 50)]):
            with self.assertRaises(ValueError):
                decompose(snapshot(rows), snapshot([("b", 50)]))
