"""Playmaking and on-ball / help defense court charts (2026-11-19)."""
import unittest

from nba_gm_data import court_influence as ci
from nba_gm_data.spatial import league_playmaking_mean, player_spatial_profile, team_spatial_profile


def getter(**values):
    return lambda key: float(values.get(key, 55.0))


def league(passer_reads=90.0, n=10):
    players, traits = [], []
    for i in range(n):
        pid = f"p{i}"
        team = "A" if i < n // 2 else "B"
        players.append({"id": pid, "name": f"Player {i}", "team_id": team, "position": "G", "height_inches": 77,
                        "minutes_projection": 30.0, "age": 26})
        reads = passer_reads if pid == "p0" else 50.0
        for key, value in {"passing_reads": reads, "handle_pressure": 55.0, "rim_pressure": 55.0, "shooting_range": 55.0,
                           "shot_versatility": 50.0, "rim_deterrence": 50.0, "scheme_iq": 55.0, "defensive_effort": 60.0,
                           "foot_speed_lateral_agility": 60.0, "screen_navigation": 60.0}.items():
            traits.append({"player_id": pid, "trait_key": key, "value": value})
    return {"meta": {"current_date": "2026-11-01"}, "players": players, "traits": traits,
            "teams": [{"id": "A"}, {"id": "B"}]}


class CourtInfluenceTests(unittest.TestCase):
    def test_passers_lift_teammates_most_at_the_rim_and_corners(self):
        great = ci.playmaking_by_group(getter(passing_reads=92), 78)
        poor = ci.playmaking_by_group(getter(passing_reads=25), 78)
        self.assertGreater(ci.overall_playmaking(great), ci.overall_playmaking(poor) + 0.8)
        self.assertGreater(great["corner_three"], great["above_break_three"])
        self.assertGreater(great["corner_three"], great["midrange"])

    def test_shooting_gravity_opens_the_paint(self):
        shooter = ci.playmaking_by_group(getter(shooting_range=95), 78)
        self.assertGreater(shooter["rim"], shooter["corner_three"])

    def test_on_ball_and_help_add_up_to_the_engine_defense(self):
        canonical = league()
        chart = player_spatial_profile(canonical, canonical["players"][0], include_chart=True)["shot_chart"]
        self.assertIn("playmaking", chart["views"])
        for region in chart["regions"]:
            self.assertAlmostEqual(region["onball_delta_pp"] + region["help_delta_pp"], region["suppression_delta_pp"], places=1)
        for layer in (6, 7, 8):
            self.assertAlmostEqual(sum(cell[layer] for cell in chart["cells"]), 1.0, places=3)

    def test_rim_protector_help_is_mostly_at_the_rim(self):
        help_delta = ci.help_suppression_delta(getter(rim_deterrence=95, scheme_iq=80))
        self.assertGreater(help_delta["rim"], help_delta["perimeter"])
        self.assertGreater(help_delta["rim"], 2.0)

    def test_team_with_the_great_passer_shoots_better_and_league_is_centered(self):
        canonical = league()
        zero = league_playmaking_mean(canonical)
        profiles = [player_spatial_profile(canonical, p)["playmaking"] for p in canonical["players"]]
        mean_corner = sum(p["corner_three"] for p in profiles) / len(profiles)
        self.assertAlmostEqual(mean_corner, 0.0, places=2)       # measured against the league's own players
        self.assertGreater(zero["corner_three"], -10)
        a = team_spatial_profile(canonical, "A")["offense"]["corner_three_left"]["efficiency"]
        b = team_spatial_profile(canonical, "B")["offense"]["corner_three_left"]["efficiency"]
        self.assertGreater(a, b)


if __name__ == "__main__":
    unittest.main()
