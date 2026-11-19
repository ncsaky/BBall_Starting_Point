from copy import deepcopy
import unittest
from unittest.mock import patch
from pathlib import Path
from contextlib import ExitStack

from nba_gm_data.dashboard_metrics import build_award_baselines, award_watch_payload
from nba_gm_data.play import save_focused_scouted_pct, prospect_scout_display
from nba_gm_data.app_actions import prospect_card_ratings, set_rotation_minutes_action, enrich_draft_board_scouting


class DashboardMetricsTests(unittest.TestCase):
    def test_prospect_card_hides_ratings_until_their_scout_traits_are_revealed(self):
        prospect = {"position": "SG", "archetype": "lead_creator"}
        report = {"trait_estimates": {key: {"mid": 70} for key in (
            "shooting", "shot_creation", "defense", "athleticism", "passing", "rim_pressure",
            "rebounding", "rim_protection", "feel", "size", "motor", "nba_readiness",
        )}}

        unscouted = prospect_card_ratings(prospect, {"scouted_pct": 0, "now": 60, "potential": 82}, report)
        self.assertEqual(unscouted["ratings"], {})
        self.assertEqual(unscouted["ratings_revealed"], 0)

        partial = prospect_card_ratings(prospect, {"scouted_pct": 50, "now": 60, "potential": 82}, report)
        self.assertGreater(partial["ratings_revealed"], 0)
        self.assertLess(partial["ratings_revealed"], partial["ratings_total"])
        self.assertIn("shooting", partial["ratings"])
        self.assertIn("creation", partial["ratings"])
        self.assertNotIn("release", partial["ratings"])
        self.assertNotIn("stamina", partial["ratings"])
        self.assertNotIn("playoff", partial["ratings"])

        complete = prospect_card_ratings(prospect, {"scouted_pct": 100, "now": 60, "potential": 82}, report)
        self.assertEqual(complete["ratings_revealed"], complete["ratings_total"])
        self.assertIn("release", complete["ratings"])
        self.assertIn("playoff", complete["ratings"])

    def test_scouting_advances_with_calendar_and_staff_strength(self):
        canonical = {"gameplay_staff_slots": [{"team_id": "was", "slot": "scouting_lead", "skill_traits": {"talent_eval": 60, "risk_modeling": 60, "international_coverage": 60}}]}
        save = {"meta": {"season": "2029-30", "seed": 1}, "state": {"current_date": "2029-10-01"}}
        prospect = {"id": "generated", "rank": 20, "current_ability": 50, "potential": 70}
        start = save_focused_scouted_pct(canonical, save, "generated", "was", prospect=prospect)
        save["state"]["current_date"] = "2030-03-01"
        later = save_focused_scouted_pct(canonical, save, "generated", "was", prospect=prospect)
        self.assertGreater(later, start + 5)
        stronger = deepcopy(canonical)
        stronger["gameplay_staff_slots"][0]["skill_traits"] = dict.fromkeys(("talent_eval", "risk_modeling", "international_coverage"), 85)
        self.assertGreater(save_focused_scouted_pct(stronger, save, "generated", "was", prospect=prospect), later)
        with patch("nba_gm_data.play.scouting_report_for", return_value={}):
            self.assertEqual(prospect_scout_display(canonical, prospect, "was", save)["scouted_pct"], later)
        self.assertLessEqual(later, 100)
        # A class beyond next June is barely scouted yet.
        future = {**prospect, "draft_year": "2031"}
        self.assertLess(save_focused_scouted_pct(canonical, save, "generated", "was", prospect=future), start)

    def test_prospect_movement_uses_saved_team_board_baseline(self):
        save = {"prospect_preseason_ranks": {"was:2030": {"p": 5}}}
        board = {"year": "2030", "entries": [{"board_rank": 2, "prospect": {"id": "p", "rank": 20}}]}
        with patch("nba_gm_data.play.prospect_scout_display", return_value={"scouted_pct": 70}):
            result = enrich_draft_board_scouting({}, save, "was", board)
        self.assertEqual(result["entries"][0]["rank_change"], 3)
        self.assertEqual(result["entries"][0]["season_start_rank"], 5)

    def test_explicit_minutes_markers_are_saved_separately_from_autofill(self):
        save = {"meta": {"user_team_id": "was"}}
        active = {"players": [{"id": str(i), "team_id": "was"} for i in range(6)]}
        with ExitStack() as stack:
            for name, value in (("load_save", save), ("ensure_league_save_defaults", save), ("canonical_with_save", active), ("resolve_team", {"id": "was", "abbrev": "WAS"}), ("team_dashboard", {})):
                stack.enter_context(patch(f"nba_gm_data.app_actions.{name}", return_value=value))
            write = stack.enter_context(patch("nba_gm_data.app_actions.write_save"))
            result = set_rotation_minutes_action(Path("."), {}, Path("unused.json"), {"team": "WAS", "minutes": {str(i): 40 for i in range(6)}, "locked_player_ids": ["0"]})
        self.assertEqual(result["status"], "updated")
        self.assertEqual(save["rotation_locked_player_ids"]["was"], ["0"])
        self.assertEqual(sum(save["rotation_overrides"]["was"].values()), 240)
        write.assert_called_once()

    def test_award_changes_use_frozen_rank_not_display_position(self):
        save = {"meta": {"season": "2029-30"}, "award_preseason_baselines": {"2029-30": {"MVP": {"a": {"rank": 1, "score": 100}, "b": {"rank": 2, "score": 90}}}}, "player_season_stats": {"a": {"games": 10, "points": 100}, "b": {"games": 10, "points": 400}}}
        rows = [{"player_id": pid, "player_name": pid, "team_id": "was", "team_abbrev": "WAS", "headshot_url": None, "rookie": False, "values": {"overall": 80}} for pid in ("a", "b")]
        ranks = award_watch_payload(rows, save)["MVP"]
        self.assertEqual([(row["player_id"], row["rank_change"]) for row in ranks], [("b", 1), ("a", -1)])
        save["player_season_stats"] = {}
        self.assertEqual([row["rank_change"] for row in award_watch_payload(rows, save)["MVP"]], [0, 0])

    def test_preseason_projection_uses_prior_performance_and_growth(self):
        active = {"players": [{"id": "young", "age": 22, "team_id": "was"}, {"id": "old", "age": 35, "team_id": "was"}]}
        save = {"meta": {"season": "2029-30"}, "season_history": [{"season": "2028-29", "player_season_stats": {pid: {"games": 60, "points": 1500} for pid in ("young", "old")}}]}
        with patch("nba_gm_data.save.player_attribute_summary", return_value={"overall": 80}), patch("nba_gm_data.save.is_rookie_for_awards", return_value=False):
            baseline = build_award_baselines(active, save)
        self.assertLess(baseline["MVP"]["young"]["rank"], baseline["MVP"]["old"]["rank"])
        self.assertEqual(baseline["ROTY"], {})
