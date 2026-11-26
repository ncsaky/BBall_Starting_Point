"""The NBA's "3-2-1" lottery, from the 2027 draft on: field, odds, the 12th-pick floor, repeat limits and order."""
from copy import deepcopy
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from nba_gm_data import save as engine
from nba_gm_data.app_actions import draft_lottery_view, load_app_canonical
from nba_gm_data.draft import (default_draft_model_config, draw_321_lottery, generate_draft_order, load_draft_model_config,
                               lottery_preview)
from nba_gm_data.season_slides import lottery_view

ROOT = Path(__file__).resolve().parents[1]
# Wins by conference seed (teams in abbreviation order). All 30 differ, so record order is unambiguous.
WINS = {"East": [62, 58, 54, 50, 48, 46, 44, 42, 38, 36, 30, 26, 22, 18, 14],
        "West": [61, 57, 53, 49, 47, 45, 43, 41, 37, 35, 29, 25, 21, 17, 13]}
# The league's published table (chance in percent of picks 1-16, per team of each group, no repeat limits), from the
# official 3-2-1 odds sheet, rounded there to whole points except pick 1.
OFFICIAL = {
    "relegated": [5.4, 5, 6, 6, 6, 6, 6, 6, 6, 8, 14, 25, 0, 0, 0, 0],
    "outside_play_in": [8.1, 8, 8, 8, 8, 7, 7, 7, 7, 6, 4, 2, 7, 6, 5, 3],
    "play_in_9_10": [5.4, 5, 6, 6, 6, 6, 6, 6, 6, 6, 5, 2, 9, 9, 9, 7],
    "seven_eight_loser": [2.7, 3, 3, 3, 3, 4, 4, 4, 4, 4, 4, 2, 8, 10, 15, 27],
}
NO_HISTORY = {"2025": {}, "2026": {}}


def no_history_config():
    config = default_draft_model_config()
    config["lottery_321"]["real_own_pick_slots"] = deepcopy(NO_HISTORY)
    return config


class Lottery321Tests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.canonical = load_app_canonical(ROOT)
        cls.ids = {team["abbrev"]: team["id"] for team in cls.canonical["teams"]}
        with TemporaryDirectory() as directory:
            cls.base_save = engine.create_league_save(ROOT, cls.canonical, "GSW", Path(directory) / "save.json", seed=17)

    def season(self, *, upsets=("East",), tenth_wins=("West",)):
        """A finished 2026-27 season after the play-in. In ``upsets`` the 8th seed beats the 7th; in ``tenth_wins`` the
        10th seed beats the 9th and then takes the last playoff place."""
        save = deepcopy(self.base_save)
        seeds = {conference: [team["id"] for team in sorted(self.canonical["teams"], key=lambda t: t["abbrev"])
                              if team["conference"] == conference] for conference in WINS}
        save["team_records"] = {team_id: {"wins": wins, "losses": 82 - wins}
                                for conference, ids in seeds.items() for team_id, wins in zip(ids, WINS[conference])}
        play_in = {}
        for c, ids in seeds.items():
            seven, eight = (ids[7], ids[6]) if c in upsets else (ids[6], ids[7])
            play_in[c] = {"status": "completed", "teams": {str(n): ids[n - 1] for n in range(7, 11)},
                          "seed_7_team_id": seven, "seed_8_team_id": ids[9] if c in tenth_wins else eight}
        save["playoff_state"] = {
            "year": "2027", "round": "first_round", "status": "in_progress", "games": [], "series": [],
            "locked_seeds": {c: {str(n): ids[n - 1] for n in range(1, 7)} for c, ids in seeds.items()},
            "play_in": play_in,
        }
        save["playoff_state"]["series"] = engine.first_round_series_from_play_in(self.canonical, save["playoff_state"])
        return save, seeds

    def standings(self, save):
        return engine.save_standings_for_draft(self.canonical, save)

    def order(self, save, year="2027", seed=4, config=None):
        return generate_draft_order(self.canonical, year, seed=seed, standings=self.standings(save), config=config)

    def by_record(self, save, team_ids):
        return sorted(team_ids, key=lambda team_id: save["team_records"][team_id]["wins"])

    def round_order(self, order, round_no):
        return [row["original_team_id"] for row in sorted(order["draft_order"], key=lambda r: r["overall_pick"])
                if row["round"] == round_no]

    def expected_groups(self, seeds, upsets):
        groups = {}
        outside = sorted((WINS[c][i], seeds[c][i]) for c in WINS for i in range(10, 15))
        for position, (_, team_id) in enumerate(outside):
            groups[team_id] = "relegated" if position < 3 else "outside_play_in"
        for c, ids in seeds.items():
            groups[ids[8]] = groups[ids[9]] = "play_in_9_10"
            groups[ids[6 if c in upsets else 7]] = "seven_eight_loser"
        return groups

    def test_the_config_file_and_the_built_in_default_agree(self):
        self.assertEqual(load_draft_model_config(ROOT)["lottery_321"], default_draft_model_config()["lottery_321"])

    def test_field_is_set_by_seeds_and_the_seven_eight_game_not_by_who_made_the_playoffs(self):
        save, seeds = self.season(upsets=("East",), tenth_wins=("West",))
        lottery = self.order(save)["lottery"]
        groups = {team_id: row["group"] for team_id, row in lottery["team_groups"].items()}
        self.assertEqual(groups, self.expected_groups(seeds, ("East",)))
        self.assertEqual(sum(row["balls"] for row in lottery["team_groups"].values()), 37)
        self.assertEqual(lottery["format"], "3-2-1")
        self.assertEqual(lottery["draw_count"], 16)
        self.assertEqual(lottery["pre_lottery_order"], self.by_record(save, groups))
        field = engine.playoff_field_team_ids(save)
        # The 10th seed that won its way in and the East's 7th seed that lost the 7-vs-8 game keep their balls.
        self.assertIn(seeds["West"][9], field)
        self.assertEqual(groups[seeds["West"][9]], "play_in_9_10")
        self.assertEqual(groups[seeds["East"][6]], "seven_eight_loser")
        self.assertNotIn(seeds["East"][7], groups)   # won the 7-vs-8 game

    def test_before_the_seven_eight_game_the_eighth_seed_stands_in_as_the_loser(self):
        save, seeds = self.season(upsets=(), tenth_wins=())
        save["playoff_state"].update(round="play_in", series=[])
        for payload in save["playoff_state"]["play_in"].values():
            payload.update(status="scheduled", seed_7_team_id=None, seed_8_team_id=None)
        for state in (save, {**save, "playoff_state": {}}):
            plan = lottery_preview(self.canonical, "2027", self.standings(state))
            groups = {team_id: row["group"] for team_id, row in plan["teams"].items()}
            self.assertEqual(groups, self.expected_groups(seeds, ()))

    def test_order_after_the_lottery(self):
        save, seeds = self.season()
        for seed in range(1, 31):
            order = self.order(save, seed=seed)
            lottery = order["lottery"]
            field = set(lottery["pre_lottery_order"])
            first, second = self.round_order(order, 1), self.round_order(order, 2)
            self.assertEqual(first[:16], lottery["final_lottery_order"])
            self.assertEqual(set(first[:16]), field)
            rest = self.by_record(save, set(save["team_records"]) - field)
            self.assertEqual(first[16:], rest)                       # picks 17-30 by record
            self.assertEqual(second[:16], first[:16][::-1])          # picks 31-46 run opposite to 1-16
            self.assertEqual(second[16:], rest)                      # picks 47-60 by record
            self.assertEqual([row["lottery_slot"] for row in order["draft_order"][:17]], [*range(1, 17), None])

    def test_the_same_seed_draws_the_same_order(self):
        save, _ = self.season()
        self.assertEqual(self.order(save, seed=9), self.order(save, seed=9))
        self.assertNotEqual(self.order(save, seed=9)["lottery"]["final_lottery_order"],
                            self.order(save, seed=10)["lottery"]["final_lottery_order"])

    def draws(self, config, count):
        save, _ = self.season()
        plan = lottery_preview(self.canonical, "2027", self.standings(save), config)
        picks = {team["id"]: [0] * 16 for team in plan["field"]}
        for seed in range(count):
            for slot, team in enumerate(draw_321_lottery(plan, seed, "2027", config)):
                picks[team["id"]][slot] += 1
        return plan, {team_id: [100 * n / count for n in row] for team_id, row in picks.items()}

    def test_odds_over_many_draws_match_the_leagues_published_table(self):
        plan, odds = self.draws(no_history_config(), 40_000)
        for group, official in OFFICIAL.items():
            members = [team_id for team_id, row in plan["teams"].items() if row["group"] == group]
            for slot, expected in enumerate(official):
                average = sum(odds[team_id][slot] for team_id in members) / len(members)
                self.assertAlmostEqual(average, expected, delta=0.8, msg=f"{group} pick {slot + 1}")
            for team_id in members:
                # The odds the screens show are the draw's own odds at No. 1.
                self.assertAlmostEqual(100 * plan["odds"][team_id], official[0], delta=0.05)
                self.assertAlmostEqual(odds[team_id][0], official[0], delta=0.6)
        for team_id, row in plan["teams"].items():
            if row["group"] == "relegated":
                self.assertEqual(sum(odds[team_id][12:]), 0.0)   # never below 12th

    def test_the_first_limits_look_back_at_the_real_2025_and_2026_drafts(self):
        save, _ = self.season()
        teams = self.order(save)["lottery"]["team_groups"]
        limits = {team_id: row["highest_pick"] for team_id, row in teams.items() if row["highest_pick"] > 1}
        # Washington picked first in 2026; Utah's own pick was 5th in 2025 and 2nd in 2026.
        expected = {self.ids[abbrev]: slot for abbrev, slot in (("WAS", 2), ("UTA", 6)) if self.ids[abbrev] in teams}
        self.assertEqual(limits, expected)

    def barred_season(self):
        """A season with a first-pick-barred and a top-five-barred team among the relegated and 9-10 seeds."""
        save, seeds = self.season()
        no_first, no_top_five = seeds["East"][14], seeds["West"][8]
        config = no_history_config()
        config["lottery_321"]["real_own_pick_slots"] = {"2025": {no_top_five: 5}, "2026": {no_first: 1, no_top_five: 2}}
        return save, config, no_first, no_top_five

    def test_repeat_limits_move_a_barred_team_down_and_pass_its_odds_on(self):
        save, config, no_first, no_top_five = self.barred_season()
        plan = lottery_preview(self.canonical, "2027", self.standings(save), config)
        self.assertEqual(plan["odds"][no_first], 0.0)
        self.assertEqual(plan["odds"][no_top_five], 0.0)
        self.assertAlmostEqual(sum(plan["odds"].values()), 1.0, places=2)
        picks = {team["id"]: [0] * 16 for team in plan["field"]}
        for seed in range(20_000):
            order = [team["id"] for team in draw_321_lottery(plan, seed, "2027", config)]
            self.assertEqual(len(set(order)), 16)
            for slot, team_id in enumerate(order):
                picks[team_id][slot] += 1
        self.assertEqual(picks[no_first][0], 0)
        self.assertEqual(sum(picks[no_top_five][:5]), 0)
        self.assertEqual(sum(picks[no_first][12:]), 0)          # relegated, so still never below 12th
        # Drawn too high, a team takes the first pick it may hold: far more often than an ordinary draw would.
        self.assertGreater(picks[no_first][1] / 20_000, 0.08)
        self.assertGreater(picks[no_top_five][5] / 20_000, 0.25)
        for team_id, chance in plan["odds"].items():
            self.assertAlmostEqual(picks[team_id][0] / 20_000, chance, delta=0.007)

    def test_a_save_s_own_draft_orders_set_the_next_limits(self):
        save, seeds = self.season()
        first = engine.run_draft_lottery_state(self.canonical, save, "2027", seed=4)
        winner = next(r["original_team_id"] for r in first["draft_order"] if r["overall_pick"] == 1)
        self.assertEqual(engine.own_first_round_slots(save)["2027"][winner], 1)
        for seed in range(60):
            order = self.order(save, year="2028", seed=seed)
            self.assertNotEqual(self.round_order(order, 1)[0], winner)
        teams = order["lottery"]["team_groups"]
        self.assertGreaterEqual(teams[winner]["highest_pick"], 2)
        self.assertEqual(order["lottery"]["odds_by_team"][winner], 0.0)
        # Two top-five picks in the save's last two drafts bar the third.
        save["draft_orders"]["2028"] = {"draft_order": [{"round": 1, "original_team_id": winner, "overall_pick": 4}]}
        self.assertEqual(self.order(save, year="2029")["lottery"]["team_groups"][winner]["highest_pick"], 6)

    def test_the_draft_room_shows_all_sixteen_with_the_draw_s_odds(self):
        save, _ = self.season()
        order = engine.run_draft_lottery_state(self.canonical, save, "2027", seed=4)
        view = draft_lottery_view(self.canonical, order, "2027", revealed=True)
        self.assertEqual(view["format"], "3-2-1")
        self.assertEqual(view["draw_count"], 16)
        self.assertEqual(len(view["odds"]), 16)
        self.assertEqual([row["pick"] for row in view["reveal"]], list(range(1, 17)))
        for row in view["odds"]:
            self.assertEqual(row["odds"], order["lottery"]["odds_by_team"][row["team"]["id"]])
            self.assertIn(row["balls"], {1, 2, 3})

    def test_the_year_end_slide_gives_a_playoff_team_in_the_lottery_its_odds(self):
        save, seeds = self.season()
        tenth, top = seeds["West"][9], seeds["East"][0]   # the East leader has the best record of all
        view = lottery_view(self.canonical, save, "2026-27", tenth)
        shown = self.order(save)["lottery"]["odds_by_team"][tenth]
        self.assertEqual((view["status"], view["lottery_teams"], view["odds_first_pick"]),
                         ("lottery", 16, round(100 * shown, 1)))
        self.assertGreater(shown, 0.054)   # more than 2 of 37: the barred teams' chance passes to the others
        self.assertEqual(lottery_view(self.canonical, save, "2026-27", top)["status"], "playoff_team")
        self.assertEqual(lottery_view(self.canonical, save, "2026-27", top)["projected_pick"], 30)

    def test_a_traded_protected_pick_resolves_on_its_lottery_slot(self):
        save, seeds = self.season()
        sender, receiver = seeds["East"][14], seeds["West"][0]
        pick_id = next(r["id"] for r in self.order(save)["draft_order"]
                       if r["round"] == 1 and r["original_team_id"] == sender)
        save["draft_pick_overrides"] = {pick_id: receiver}
        save["pick_obligations"] = [{
            "id": "sender_top8", "type": "protected_pick", "status": "active", "season": "2027", "round": 1,
            "primary_pick_id": pick_id, "sender_team_id": sender, "receiver_team_id": receiver,
            "protected_range": {"from": 1, "through": 8}, "protected_top_n": 8, "fallback_pick_ids": [],
        }]
        outcomes = set()
        for seed in range(12):
            trial = deepcopy(save)
            order = engine.run_draft_lottery_state(self.canonical, trial, "2027", seed=seed)
            row = next(r for r in order["draft_order"] if r["id"] == pick_id)
            protected = row["overall_pick"] <= 8
            self.assertEqual(row["current_owner_team_id"], sender if protected else receiver)
            self.assertEqual(trial["draft_orders"]["2027"], order)
            outcomes.add(protected)
        self.assertEqual(outcomes, {True, False})

    def test_2026_keeps_the_fourteen_team_lottery(self):
        save, _ = self.season()
        lottery = self.order(save, year="2026")["lottery"]
        self.assertEqual(lottery["format"], "weighted_14")
        self.assertEqual(len(lottery["pre_lottery_order"]), 14)
        self.assertEqual(lottery["draw_count"], 4)


if __name__ == "__main__":
    unittest.main()
