"""PICK-REFIT: undrawn picks are priced under the 3-2-1 lottery."""
from copy import deepcopy
import unittest

from nba_gm_data import pick_lottery_value as plv, transactions as tx
from nba_gm_data.draft import default_draft_model_config, draw_321_lottery, lottery_plan

TABLE_MEAN = sum(plv.first_round_slot_value(slot) for slot in range(1, 31)) / 30


def league(season="2026-27", years=(2026, 2027, 2029)):
    """Thirty teams, team 01 weakest, each holding its own picks."""
    teams = [{"id": f"t{n:02d}", "abbrev": f"T{n:02d}", "conference": "East" if n % 2 else "West"} for n in range(1, 31)]
    picks = [{"id": f"{team['id']}-{year}-{round_no}", "season": str(year), "round": round_no,
              "original_team_id": team["id"], "current_owner_team_id": team["id"], "status": "future"}
             for team in teams for year in years for round_no in (1, 2)]
    states = [{"team_id": team["id"], "phase": "balanced", "contention_ceiling": 20 + 2 * n}
              for n, team in enumerate(teams)]
    return {"meta": {"active_season": season}, "teams": teams, "draft_picks": picks, "team_strategic_states": states,
            "players": [], "player_asset_valuations": [], "pick_obligations": []}


def value(finish, distance=1, highest=1):
    return plv.first_round_slot_value(plv.lottery_pick_slot(float(finish), distance, 1, highest))


class PickLotteryValueTests(unittest.TestCase):
    def test_odds_table_is_the_lotterys_own_draw(self):
        config = default_draft_model_config()
        data = league()
        plan = lottery_plan(data, "2035", data["teams"], None, config)
        self.assertEqual(tuple(plan["teams"][team["id"]]["group"] for team in plan["field"]), plv.GROUP_BY_FINISH)
        draws = 20_000
        counts = {group: [0] * 16 for group in plv.SLOT_ODDS}
        for seed in range(draws):
            for slot, team in enumerate(draw_321_lottery(plan, seed, "2035", config)):
                counts[plan["teams"][team["id"]]["group"]][slot] += 1
        for group, row in counts.items():
            total = sum(row)
            for slot, count in enumerate(row):
                self.assertAlmostEqual(count / total, plv.SLOT_ODDS[group][slot], delta=0.007, msg=(group, slot + 1))

    def test_one_drafts_picks_are_still_worth_the_thirty_positions(self):
        for distance in (1, 3, 6):
            mean = sum(value(finish, distance) for finish in range(1, 31)) / 30
            self.assertAlmostEqual(mean, TABLE_MEAN, delta=0.5, msg=distance)

    def test_the_worst_record_no_longer_buys_a_far_better_pick(self):
        worst, seventh, ninth_seed, best = value(1), value(7), value(12), value(30)
        self.assertLess(worst, 100)                       # was 126 at the projected finish
        self.assertAlmostEqual(worst, seventh, delta=3)
        self.assertGreater(ninth_seed, plv.first_round_slot_value(12))
        self.assertLess(best, 40)
        self.assertGreater(worst, value(20) + 25)         # a bad team's pick is still clearly the better one

    def test_repeat_pick_limits_lower_a_barred_teams_pick(self):
        data = league()
        self.assertEqual(plv.highest_pick_allowed(data, "team_was", 2027), 2)
        self.assertEqual(plv.highest_pick_allowed(data, "team_uta", 2027), 6)
        self.assertEqual(plv.highest_pick_allowed(data, "team_uta", 2029), 1)
        self.assertLess(value(2, highest=6), value(2, highest=2))
        self.assertLess(value(2, highest=2), value(2))
        data["save_own_pick_history"] = {"2027": {"t01": 1}}
        self.assertEqual(plv.highest_pick_allowed(data, "t01", 2028), 2)

    def test_annotation_prices_2027_on_and_leaves_earlier_and_drawn_picks(self):
        data = league(season="2025-26")
        drawn = next(p for p in data["draft_picks"] if p["id"] == "t01-2027-1")
        drawn["overall_pick"] = 9
        tx.annotate_pick_value_context(data)
        picks = {p["id"]: p for p in data["draft_picks"]}
        old = picks["t01-2026-1"]
        self.assertIsInstance(old["projected_pick_slot"], int)
        self.assertNotIn("projected_finish_rank", old)
        self.assertEqual(drawn["projected_pick_slot"], 9)
        new = picks["t01-2029-1"]
        self.assertIn("projected_finish_rank", new)
        self.assertGreater(new["projected_pick_slot"], 4)
        # A weak team's second-rounder now falls behind the other lottery teams' seconds.
        late = picks["t01-2029-2"]
        self.assertGreater(late["projected_pick_slot"], late["projected_finish_rank"])

    def test_new_draft_history_refreshes_the_values(self):
        data = league()
        tx.ensure_pick_value_context(data)
        pick = next(p for p in data["draft_picks"] if p["id"] == "t01-2027-1")
        before = pick["projected_pick_slot"]
        data["save_own_pick_history"] = {"2025": {"t01": 2}, "2026": {"t01": 3}}
        tx.ensure_pick_value_context(data)
        self.assertGreater(pick["projected_pick_slot"], before)
        self.assertEqual(pick["_highest_allowed_pick"], 6)

    def test_better_of_two_picks_is_worth_more_than_the_worse_and_is_repeatable(self):
        data = league()
        tx.annotate_pick_value_context(data)
        leaves = [dict(p, _active_season="2026-27") for p in data["draft_picks"] if p["id"] in {"t01-2029-1", "t25-2029-1"}]
        import json
        first = tx.ranked_pool_expected_values(json.dumps(leaves, sort_keys=True), "neutral")
        self.assertEqual(first, tx.ranked_pool_expected_values.__wrapped__(json.dumps(leaves, sort_keys=True), "neutral"))
        singles = [tx.pick_asset_value({**leaf, "_ranked_scenario": True}, "neutral") for leaf in leaves]
        self.assertGreater(first[0], max(singles))
        self.assertLess(first[1], min(singles) + 8)
        self.assertGreater(first[0], first[1])

    def test_sampled_positions_follow_the_second_round_order(self):
        self.assertEqual(plv.sample_draft_position(30.0, 0.0, 0.5, 1), 30)
        self.assertEqual(plv.sample_draft_position(30.0, 0.0, 0.5, 2), 30)
        first = plv.sample_draft_position(1.0, 0.0, 0.5, 1)
        self.assertEqual(plv.sample_draft_position(1.0, 0.0, 0.5, 2), 17 - first)
        self.assertGreaterEqual(plv.sample_draft_position(1.0, 0.0, 0.0, 1, 6), 6)


if __name__ == "__main__":
    unittest.main()
