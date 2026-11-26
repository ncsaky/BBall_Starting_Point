"""The 14-team lottery (the 2026 draft) is for the teams that missed the playoffs after the play-in, whatever their
records say. From 2027 the 3-2-1 lottery applies (test_draft_lottery_321)."""
from copy import deepcopy
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from nba_gm_data import save as engine
from nba_gm_data.app_actions import load_app_canonical
from nba_gm_data.draft import generate_draft_order

ROOT = Path(__file__).resolve().parents[1]
# Wins by conference seed. East's 10th seed (40 wins) has a worse record than its 8th (42) and 9th (41).
WINS = {"East": [60, 58, 56, 54, 52, 50, 44, 42, 41, 40, 30, 28, 26, 24, 22],
        "West": [61, 59, 57, 55, 53, 51, 45, 43, 39, 38, 31, 29, 27, 25, 23]}


class DraftLotteryFieldTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.canonical = load_app_canonical(ROOT)
        with TemporaryDirectory() as directory:
            cls.base_save = engine.create_league_save(ROOT, cls.canonical, "GSW", Path(directory) / "save.json", seed=17)

    def season(self, east_eighth_seed=10):
        """A finished season: records, plus the first round built by the game's own play-in bracket code."""
        save = deepcopy(self.base_save)
        seeds = {conference: [team["id"] for team in sorted(self.canonical["teams"], key=lambda t: t["abbrev"])
                              if team["conference"] == conference] for conference in WINS}
        save["team_records"] = {team_id: {"wins": wins, "losses": 82 - wins}
                                for conference, ids in seeds.items() for team_id, wins in zip(ids, WINS[conference])}
        state = {
            "year": "2027", "round": "first_round", "status": "in_progress", "games": [], "series": [],
            "locked_seeds": {c: {str(n): ids[n - 1] for n in range(1, 7)} for c, ids in seeds.items()},
            "play_in": {c: {"status": "completed", "seed_7_team_id": ids[6],
                            "seed_8_team_id": ids[(east_eighth_seed if c == "East" else 8) - 1]}
                        for c, ids in seeds.items()},
        }
        state["series"] = engine.first_round_series_from_play_in(self.canonical, state)
        save["playoff_state"] = state
        return save, seeds

    def order(self, save, seed=4):
        return generate_draft_order(self.canonical, "2026", seed=seed,
                                    standings=engine.save_standings_for_draft(self.canonical, save))

    def by_record(self, save, team_ids):
        return sorted(team_ids, key=lambda team_id: save["team_records"][team_id]["wins"])

    def first_round(self, order):
        return [row["original_team_id"] for row in order["draft_order"] if row["round"] == 1]

    def test_play_in_winner_with_the_worse_record_is_not_in_the_lottery(self):
        save, seeds = self.season()
        winner, eliminated = seeds["East"][9], seeds["East"][7]
        field = engine.playoff_field_team_ids(save)
        self.assertEqual(len(field), 16)
        self.assertIn(winner, field)
        self.assertNotIn(eliminated, field)
        missed = set(save["team_records"]) - field

        for seed in range(1, 41):
            order = self.order(save, seed)
            lottery = order["lottery"]
            self.assertEqual(lottery["pre_lottery_order"], self.by_record(save, missed))
            self.assertEqual(set(lottery["odds_by_team"]), missed)
            self.assertEqual(set(self.first_round(order)[:14]), missed)
            self.assertEqual(self.first_round(order)[14:], self.by_record(save, field))
        # The worst playoff record picks 15th; the eliminated team with the better record holds a lottery slot.
        self.assertEqual(self.first_round(order)[14], winner)
        row = next(r for r in order["draft_order"] if r["round"] == 1 and r["original_team_id"] == winner)
        self.assertIsNone(row["lottery_slot"])
        self.assertIsNone(row["pre_lottery_rank"])
        # The second round stays in record order for all 30 teams.
        self.assertEqual([r["original_team_id"] for r in order["draft_order"] if r["round"] == 2],
                         self.by_record(save, save["team_records"]))

    def test_season_where_the_best_sixteen_records_qualify_is_unchanged(self):
        save, seeds = self.season(east_eighth_seed=8)
        # Make the East play-in follow the records, and give both conferences' qualifiers the 16 best records.
        for team_id, wins in zip(seeds["West"], WINS["East"]):
            save["team_records"][team_id] = {"wins": wins, "losses": 82 - wins}
        field = engine.playoff_field_team_ids(save)
        self.assertEqual(set(self.by_record(save, save["team_records"])[14:]), field)
        unplayed = {**save, "playoff_state": {}}
        self.assertEqual(self.order(save), self.order(unplayed))

    def test_records_alone_decide_until_the_play_in_is_over(self):
        save, _ = self.season()
        save["playoff_state"].update(round="play_in", series=[])
        rows = engine.save_standings_for_draft(self.canonical, save)
        self.assertEqual(engine.playoff_field_team_ids(save), set())
        self.assertFalse(any("made_playoffs" in row for row in rows))
        self.assertEqual(self.order(save)["lottery"]["pre_lottery_order"],
                         self.by_record(save, save["team_records"])[:14])

    def test_pick_ownership_and_protection_resolve_on_the_new_slot(self):
        save, seeds = self.season()
        winner, receiver = seeds["East"][9], seeds["West"][0]
        pick_id = next(r["id"] for r in self.order(save)["draft_order"]
                       if r["round"] == 1 and r["original_team_id"] == winner)
        save["draft_pick_overrides"] = {pick_id: receiver}
        save["pick_obligations"] = [{
            "id": "winner_top14", "type": "protected_pick", "status": "active", "season": "2026", "round": 1,
            "primary_pick_id": pick_id, "sender_team_id": winner, "receiver_team_id": receiver,
            "protected_range": {"from": 1, "through": 14}, "protected_top_n": 14, "fallback_pick_ids": [],
        }]
        order = engine.run_draft_lottery_state(self.canonical, save, "2026", seed=4)
        row = next(r for r in order["draft_order"] if r["id"] == pick_id)
        # A top-14 protected pick from a playoff team lands outside the protection and conveys.
        self.assertEqual(row["overall_pick"], 15)
        self.assertEqual(row["current_owner_team_id"], receiver)
        self.assertEqual(save["pick_obligations"][0]["status"], "resolved_primary_conveyed")
        self.assertEqual(save["draft_orders"]["2026"], order)


if __name__ == "__main__":
    unittest.main()
