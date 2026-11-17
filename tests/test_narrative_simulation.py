"""Historical prose must never substitute for current basketball inputs."""
from copy import deepcopy
import json
from pathlib import Path
import unittest

from nba_gm_data import sim
from nba_gm_data.schema import to_plain

ROOT = Path(__file__).resolve().parents[1]
PROSE = {
    "positive": "An excellent lead creator. Top 10 defense and best offense. Added shooting.",
    "negative": "Lack shot creation, lack passing, lack floor spacing. Clear tanking effort, dead last.",
    "negated": "They do not lack shot creation or lack floor spacing. They are not clear favorites.",
    "hypothetical": "If they acquired a lead creator and added shooting, they could have a top 10 defense.",
}


class NarrativeSimulationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.canonical = json.loads((ROOT / "data/canonical/universe_2026_27_offseason.json").read_text())
        cls.base = sim.load_sim_context(ROOT, cls.canonical)
        cls.team = next(t for t in cls.canonical["teams"] if t["abbrev"] == "TOR")
        cls.game = next(g for g in cls.base["schedule"]
                        if cls.base["indices"]["teams_by_espn_id"].get(str(g["homeTeamId"]), {}).get("id") == cls.team["id"])
        cls.game_id = str(cls.game["externalGameId"])

    def context(self, text, canonical=None, later=False):
        canonical = canonical or self.canonical
        if later:
            canonical = {**canonical, "meta": {**canonical.get("meta", {}),
                         "season": "2028-29", "active_season": "2028-29", "current_date": "2029-01-02"}}
        context = {**self.base, "canonical": canonical,
                   "manifestos": {"TOR": text}, "sim_cache": {}}
        if later:
            context["schedule"] = [{**self.game, "gameDate": "2029-01-02"}]
        context["indices"] = sim.build_sim_indices(context)
        return context

    def test_prose_cannot_change_features_or_seeded_games_in_either_mode(self):
        for mode in sorted(sim.SIM_MODES):
            baseline = self.context("")
            pool = sim.game_player_pool(baseline, self.game_id, self.team, mode)
            expected = sim.game_team_features(baseline, self.canonical, self.team, pool, mode)
            result = to_plain(sim.sim_game_with_context(baseline, self.game_id, mode, 17))
            for label, text in {**PROSE, "shipped": self.base["manifestos"]["TOR"]}.items():
                with self.subTest(mode=mode, prose=label):
                    context = self.context(text)
                    actual = sim.game_team_features(context, self.canonical, self.team, pool, mode)
                    self.assertEqual(actual, expected)
                    self.assertEqual(to_plain(sim.sim_game_with_context(context, self.game_id, mode, 17)), result)

    def test_changed_roster_and_later_season_are_not_bound_to_old_prose(self):
        canonical = deepcopy(self.canonical)
        # Exchange complete rosters; retain the TOR identity and historical text.
        other = next(t for t in canonical["teams"] if t["abbrev"] == "BOS")
        for player in canonical["players"]:
            if player["team_id"] == self.team["id"]:
                player["team_id"] = other["id"]
            elif player["team_id"] == other["id"]:
                player["team_id"] = self.team["id"]
            if player.get("age"):
                player["age"] += 3
        for later in (False, True):
            baseline = to_plain(sim.sim_game_with_context(self.context("", canonical, later), self.game_id, "sandbox-sim", 29))
            original = to_plain(sim.sim_game_with_context(self.context(""), self.game_id, "sandbox-sim", 29))
            self.assertNotEqual(baseline, original)
            for text in PROSE.values():
                self.assertEqual(to_plain(sim.sim_game_with_context(self.context(text, canonical, later), self.game_id, "sandbox-sim", 29)), baseline)

    def test_live_health_creator_spacing_and_roster_still_matter(self):
        context = self.context(PROSE["negative"])
        pool = sim.game_player_pool(context, self.game_id, self.team, "sandbox-sim")
        baseline = sim.game_team_features(None, self.canonical, self.team, pool, "sandbox-sim")
        unhealthy = [{**row, "health_fatigue": 100, "health_rust": 25} for row in pool]
        health = sim.game_team_features(None, self.canonical, self.team, unhealthy, "sandbox-sim")
        self.assertLess(health["impact"], baseline["impact"])
        self.assertLess(health["primary_creator"], baseline["primary_creator"])
        stronger = deepcopy(self.canonical)
        ids = {row["player"]["id"] for row in pool}
        for trait in stronger["traits"]:
            if trait["player_id"] in ids and trait["trait_key"] in {"shooting_range", "shot_versatility", "handle_pressure", "passing_reads", "release_speed"}:
                trait["value"] = 99
        upgraded = sim.game_team_features(None, stronger, self.team, pool, "sandbox-sim")
        self.assertGreater(upgraded["spacing"], baseline["spacing"])
        self.assertGreater(upgraded["primary_creator"], baseline["primary_creator"])
        star = max(pool, key=lambda row: sim.primary_creator_score(sim.player_feature_vector(self.canonical, row["player"]).features))
        without = [row for row in pool if row is not star]
        depleted = sim.game_team_features(None, self.canonical, self.team, without, "sandbox-sim")
        self.assertLess(depleted["primary_creator"], baseline["primary_creator"])
        normal_game = to_plain(sim.sim_game_with_context(self.context(""), self.game_id, "sandbox-sim", 17))
        upgraded_game = to_plain(sim.sim_game_with_context(self.context("", stronger), self.game_id, "sandbox-sim", 17))
        self.assertNotEqual((normal_game["home_score"], normal_game["away_score"]),
                            (upgraded_game["home_score"], upgraded_game["away_score"]))

    def test_prose_hook_does_not_mutate_features_pool_or_personnel(self):
        context = self.context(PROSE["positive"])
        pool = sim.game_player_pool(context, self.game_id, self.team, "sandbox-sim")
        features = sim.lineup_feature_vector(self.canonical, pool)
        before = deepcopy((features, pool, self.canonical))
        self.assertEqual(sim.apply_manifesto_feature_adjustments(context, self.canonical, self.team, pool, features), features)
        self.assertEqual((features, pool, self.canonical), before)

    def test_empty_pool_and_legacy_helpers_do_not_apply_prose(self):
        expected = sim.game_team_features(self.context(""), self.canonical, self.team, [], "sandbox-sim")
        for text in PROSE.values():
            self.assertEqual(sim.game_team_features(self.context(text), self.canonical, self.team, [], "sandbox-sim"), expected)
        features = {"impact": 50.0, "spacing": 50.0}
        notes = []
        sim.apply_manifesto_expectation_adjustments("clear favorites, added shooting, dead last", features, notes)
        self.assertEqual(features, {"impact": 50.0, "spacing": 50.0})
        self.assertEqual(notes, [])


if __name__ == "__main__":
    unittest.main()
