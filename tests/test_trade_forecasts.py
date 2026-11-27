"""TRADE-FORECASTS: Four Factors for any roster, and the morale a trade stores (and shows beforehand)."""
from copy import deepcopy
from pathlib import Path
import math
import random
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]


def correlation(x, y):
    mx, my = sum(x) / len(x), sum(y) / len(y)
    sx = math.sqrt(sum((a - mx) ** 2 for a in x))
    sy = math.sqrt(sum((b - my) ** 2 for b in y))
    return sum((a - mx) * (b - my) for a, b in zip(x, y)) / (sx * sy)


class TradeForecastTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from nba_gm_data.save import canonical_with_save, create_league_save, ensure_league_save_defaults, load_save
        from nba_gm_data.storage import JSON_FILENAME, load_universe_json
        cls.tmp = tempfile.TemporaryDirectory()
        cls.canonical = load_universe_json(ROOT / "data" / "canonical" / JSON_FILENAME)
        cls.path = Path(cls.tmp.name) / "forecast.json"
        create_league_save(ROOT, cls.canonical, "MIN", cls.path, seed=17)
        cls.save = ensure_league_save_defaults(load_save(cls.path), cls.canonical)
        cls.active = canonical_with_save(cls.canonical, cls.save)

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def roster(self, team_id):
        return [p for p in self.active["players"] if p.get("team_id") == team_id]

    def top_player(self, team_id, rank=0):
        from nba_gm_data.save import team_rotation_projection
        minutes = team_rotation_projection(self.active, self.save, team_id)
        return sorted(self.roster(team_id), key=lambda p: (-minutes.get(p["id"], 0.0), p["id"]))[rank]

    # Four Factors ------------------------------------------------------------------------------------------------

    def test_projection_matches_the_engine_on_the_same_rosters(self):
        """The expected box score agrees with the engine playing the same pools (three home and three away games each)."""
        from nba_gm_data import four_factor_projection as ffp
        from nba_gm_data import sim
        from nba_gm_data.box_score import reconcile_box_score
        from nba_gm_data.box_variation import vary_box_score
        from nba_gm_data.save import save_coach_ratings
        sides = ffp.league_sides(self.active, self.save)
        coaches = save_coach_ratings(self.active, self.save)
        self.assertEqual(len(sides), 30)
        ids = sorted(sides)
        totals = {tid: {k: 0.0 for k in ("fgm", "fga", "fg3m", "fta", "turnovers", "oreb", "opp_dreb")} for tid in ids}
        for seed, home_id, away_id in ((seed, h, a) for seed in range(3) for h in ids for a in ids if h != a):
                home, away = sides[home_id], sides[away_id]
                rng = random.Random(f"forecast-test:{seed}:{home_id}:{away_id}")
                hs, as_ = sim.draw_both_scores(self.active, home["features"], away["features"], coaches.get(home_id),
                                               coaches.get(away_id), rng, None, None)
                hl, ht = sim.simulate_team_line(self.active, home["team"], away["team"], home["pool"], home["features"],
                                                away["features"], coaches.get(home_id), coaches.get(away_id), rng,
                                                is_home=True, score_state=hs)
                al, at = sim.simulate_team_line(self.active, away["team"], home["team"], away["pool"], away["features"],
                                                home["features"], coaches.get(away_id), coaches.get(home_id), rng,
                                                is_home=False, score_state=as_)
                vary_box_score(self.active, [hl, al], [ht, at], [home["features"], away["features"]],
                               f"forecast-test:{seed}:{home_id}:{away_id}:box")
                reconcile_box_score(hl + al, [ht, at])
                for me, line, other in ((home_id, ht, at), (away_id, at, ht)):
                    for key in ("fgm", "fga", "fg3m", "fta", "turnovers"):
                        totals[me][key] += line[key]
                    totals[me]["oreb"] += line["offensive_rebounds"]
                    totals[me]["opp_dreb"] += other["defensive_rebounds"]

        def engine(t):
            return {"efg": (t["fgm"] + .5 * t["fg3m"]) / t["fga"] * 100,
                    "tov": t["turnovers"] / (t["fga"] + .44 * t["fta"] + t["turnovers"]) * 100,
                    "oreb": t["oreb"] / (t["oreb"] + t["opp_dreb"]) * 100,
                    "ftr": t["fta"] / t["fga"] * 100}

        projected = {tid: ffp.season_projection(self.active, tid, sides, coaches) for tid in ids}
        for key, floor in (("efg", .85), ("tov", .85), ("oreb", .95), ("ftr", .95)):
            eng = [engine(totals[tid])[key] for tid in ids]
            proj = [projected[tid]["offense"][key] * 100 for tid in ids]
            self.assertGreater(correlation(proj, eng), floor, key)
            # The engine's league average itself moves ~0.2 between seed sets (shared shooting days).
            self.assertLess(abs(sum(proj) / 30 - sum(eng) / 30), 0.5, key)

    def test_project_four_factors_shape_and_roster_changes(self):
        from nba_gm_data.app_actions import project_four_factors, project_league_four_factors
        league = project_league_four_factors(self.active, self.save)
        self.assertEqual(len(league), 30)
        mine = project_four_factors(self.active, self.save, "team_min")
        self.assertEqual(mine["offense"], league["team_min"]["offense"])
        self.assertEqual(mine["defense"], league["team_min"]["defense"])
        for side in ("offense", "defense"):
            self.assertEqual(set(mine[side]), {"efg", "tov", "oreb", "ftr"})
        self.assertTrue(45 < mine["offense"]["efg"] < 65)
        self.assertTrue(8 < mine["offense"]["tov"] < 20)
        self.assertEqual(mine["games"], 58)
        self.assertAlmostEqual(sum(row["minutes"] for row in mine["minutes"]), 240.0, delta=0.5)
        star = self.top_player("team_min")
        without = project_four_factors(self.active, self.save, "team_min",
                                       [p for p in self.roster("team_min") if p["id"] != star["id"]])
        self.assertNotIn(star["id"], {row["player_id"] for row in without["minutes"]})
        self.assertNotEqual(without["offense"], mine["offense"])
        self.assertLess(without["net_rating"], mine["net_rating"])

    def test_preseason_profile_uses_the_projection(self):
        from nba_gm_data.app_actions import dashboard_four_factors, project_league_four_factors
        from nba_gm_data.save import team_identity_report
        league = project_league_four_factors(self.active, self.save)
        rows = dashboard_four_factors({**self.save, "team_game_logs": []}, self.active, "team_min",
                                      team_identity_report(self.active, self.save))
        values = {row["key"]: row["value"] for row in rows}
        self.assertEqual(values, league["team_min"]["offense"])

    # Morale ------------------------------------------------------------------------------------------------------

    def test_role_scale_matches_the_opening_morale_steps(self):
        from nba_gm_data.trade_morale import role_level
        self.assertEqual([role_level(m) for m in (10, 18, 28)], [51.0, 56.0, 60.0])
        self.assertLess(role_level(5), role_level(15))
        self.assertEqual(role_level(48), role_level(36))

    def test_trade_moves_reads_every_proposal_shape(self):
        from nba_gm_data.trade_morale import trade_moves
        a, b = self.top_player("team_min"), self.top_player("team_dal", 3)
        expected = {a["id"]: "team_dal", b["id"]: "team_min"}
        bilateral = {"from_team_id": "team_min", "to_team_id": "team_dal",
                     "from_assets": [{"kind": "player", "id": a["id"]}, {"kind": "pick", "id": "x"}],
                     "to_assets": [{"kind": "player", "id": b["id"]}]}
        multi = {"transfers": [{"from_team_id": "team_min", "to_team_id": "team_dal", "assets": [{"kind": "player", "id": a["id"]}]},
                               {"from_team_id": "team_dal", "to_team_id": "team_min", "assets": [{"kind": "player", "id": b["id"]}]}]}
        room = {"moves": [{"to_team": "DAL", "player_ids": [a["id"]]}, {"to_team": "MIN", "player_ids": [b["id"]]}]}
        for proposal in (bilateral, {"proposal": bilateral}, multi, room):
            self.assertEqual(trade_moves(self.active, proposal), expected)

    def test_star_trade_moves_roles_chemistry_and_confidence(self):
        from nba_gm_data.app_actions import project_trade_morale
        star, other = self.top_player("team_min"), self.top_player("team_dal", 3)
        effect = project_trade_morale(self.active, self.save, {"moves": [
            {"to_team": "DAL", "player_ids": [star["id"]]}, {"to_team": "MIN", "player_ids": [other["id"]]}]})
        teams = {row["team_id"]: row for row in effect["teams"]}
        self.assertEqual(set(teams), {"team_min", "team_dal"})
        minnesota, dallas = teams["team_min"], teams["team_dal"]
        self.assertLess(minnesota["after"]["chemistry"], minnesota["before"]["chemistry"])
        self.assertGreater(minnesota["before"]["chemistry"] - minnesota["after"]["chemistry"], 0.3)
        self.assertLess(minnesota["before"]["chemistry"] - minnesota["after"]["chemistry"], 4.0)
        self.assertLess(minnesota["after"]["confidence"], minnesota["before"]["confidence"])
        self.assertGreater(dallas["after"]["confidence"], dallas["before"]["confidence"])
        self.assertIn(f"{star['name']} leaves", minnesota["reasons"])
        players = {row["player_id"]: row for row in effect["players"]}
        self.assertIn("traded", players[star["id"]]["reasons"])
        self.assertLess(players[star["id"]]["after"]["overall"], players[star["id"]]["before"]["overall"] + 0.5)
        stayed = [row for row in effect["players"] if row["team_id_after"] == "team_min" and row["player_id"] != other["id"]]
        self.assertTrue(stayed)
        for row in stayed:
            self.assertLess(row["after"]["team_confidence"], row["before"]["team_confidence"])
        # Nothing is saved by the projection.
        self.assertEqual(self.save["team_morale"]["team_min"], minnesota["before"] | {
            k: v for k, v in self.save["team_morale"]["team_min"].items() if k not in minnesota["before"]})

    def test_applied_trade_stores_exactly_the_projected_morale(self):
        from nba_gm_data.save import canonical_with_save, ensure_league_save_defaults, load_save
        from nba_gm_data.trade_morale import project_trade_morale
        from nba_gm_data.transactions import apply_trade_to_state, contract_for_player, current_salary
        save = deepcopy(self.save)
        active = canonical_with_save(self.canonical, save)
        salary = {p["id"]: current_salary(contract_for_player(active, p["id"])) or 0.0 for p in active["players"]}
        # Two rotation players on near-equal salaries, so the swap stays legal under the salary rules.
        mine = [p for p in active["players"] if p.get("team_id") == "team_min" and salary[p["id"]] > 5e6]
        theirs = [p for p in active["players"] if p.get("team_id") == "team_dal" and salary[p["id"]] > 5e6]
        a, b = min(((x, y) for x in mine for y in theirs),
                   key=lambda pair: (abs(salary[pair[0]["id"]] - salary[pair[1]["id"]]) / salary[pair[0]["id"]], pair[0]["id"], pair[1]["id"]))
        proposal = {"id": "forecast_morale_trade", "from_team_id": "team_min", "to_team_id": "team_dal",
                    "from_assets": [{"kind": "player", "id": a["id"]}], "to_assets": [{"kind": "player", "id": b["id"]}]}
        projected = project_trade_morale(active, save, proposal)
        save.setdefault("pending_trade_proposals", []).append(
            {"proposal": proposal, "legality": {"status": "legal"}, "accepted_by_all": True, "evaluations": []})
        result = apply_trade_to_state(save, "forecast_morale_trade", date=save["state"]["current_date"],
                                      canonical=self.canonical)
        self.assertEqual(result["status"], "applied", result)
        self.assertTrue(projected["teams"])
        for row in projected["teams"]:
            for key, value in row["after"].items():
                self.assertEqual(save["team_morale"][row["team_id"]][key], value)
        for row in projected["players"]:
            for key, value in row["after"].items():
                self.assertEqual(save["player_morale"][row["player_id"]][key], value)
        self.assertNotEqual(save["team_morale"]["team_min"]["chemistry"], self.save["team_morale"]["team_min"]["chemistry"])


if __name__ == "__main__":
    unittest.main()
