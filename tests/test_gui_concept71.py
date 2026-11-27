from pathlib import Path
import re
import unittest


ROOT = Path(__file__).resolve().parents[1]
APP = (ROOT / "src/nba_gm_data/gui/app.js").read_text(encoding="utf-8")
CSS = (ROOT / "src/nba_gm_data/gui/styles.css").read_text(encoding="utf-8")


class Concept71GuiTests(unittest.TestCase):
    def test_appearance_customization_is_not_exposed(self):
        settings = APP[APP.index("function openSettingsModal"):APP.index("async function openExtensionNegotiation")]
        # The user approved two preset look choices in Settings: Font (taste deck round 4, bb56f037) and Buttons
        # (round 6). Free appearance customization (colours, palettes, other font controls) stays unexposed.
        # "motion" is the on/off switch for the arena background's slow drift. The user chose the movement itself
        # ("slow drift and cross-fade", UI polish pass Stage C checkpoint 3 answer `bg-motion`); the switch to turn
        # it off was built with it and reported at checkpoint 4 (176963b5). It is an off switch, not a new look.
        looks = APP[APP.index("const UI_LOOK_SETTINGS"):APP.index("const UI_LOOK_DATASET")]
        self.assertEqual(re.findall(r"^  (\w+): \{", looks, re.M), ["glass", "font", "buttons", "motion"])
        self.assertIn('options: [["off", "Off"], ["on", "On"]] }', looks)
        self.assertIn('options: [["clear", "Clear"]] }', looks)
        self.assertNotRegex(settings.lower(), r"""type=["']color["']""")
        remaining = settings.lower()
        for approved in ('uilookmenumarkup("font")', 'name === "font"', "ui-font-sample"):
            remaining = remaining.replace(approved, "")
        self.assertNotIn("primary color", settings.lower())
        self.assertNotIn("font", remaining)
        self.assertNotIn("palette", settings.lower())
        self.assertNotIn("--team-accent", CSS)

    def test_dashboard_uses_concept_71_structure(self):
        identity = APP[APP.index("function seasonIdentityCard"):APP.index("function seasonIdentityRadar")]
        week = APP[APP.index("function seasonWeekCard"):APP.index("function seasonGameOpponent")]
        dashboard = APP[APP.index("function seasonCommandDashboardMarkup"):APP.index("function seasonPanelHeader")]
        standings = APP[APP.index("function seasonStandingsCard"):APP.index("function seasonWeekCard")]
        self.assertIn("spatialHeatmapMarkup(dash.spatial_profile", identity)
        self.assertIn("season-identity-signals", identity)
        self.assertIn("season-signal-card", identity)
        self.assertIn("season-week-node", week)
        self.assertNotIn("season-week-opponent", week)
        self.assertNotIn("dashboardTeamSelect", dashboard)
        self.assertNotIn("standings-conference-toggle", standings)
        self.assertNotIn("standings-view-all", standings)

    def test_player_cards_show_spatial_maps_and_rating_averages(self):
        card = APP[APP.index("function playerCardRatingBar"):APP.index("async function dashboardPlayerCard")]
        self.assertIn("rating-average-marker", card)
        self.assertIn("rating_league_averages", card)
        self.assertIn("spatialHeatmapMarkup(detail.spatial_profile", card)
        self.assertIn("approved-player-identity-ratings", card)
        self.assertNotIn("approved-ratings-panel", card)

    def test_bars_sample_one_color_and_heatmap_uses_dense_hexes(self):
        self.assertNotIn("--performance-gradient", CSS)
        self.assertIn("background: var(--bar-color", CSS)
        self.assertIn("performanceBarStyle", APP)
        self.assertIn(".spatial-legend i", CSS)
        self.assertNotIn("radial-gradient(", CSS)
        self.assertNotIn("<radialGradient", APP)
        self.assertIn("function spatialHeatmapRegions", APP)
        self.assertIn("function spatialEfficiencyColor", APP)
        self.assertIn("profile?.shot_chart", APP)
        # Colors come straight from each region's stored delta, chosen per court view (2026-11-19 views).
        self.assertIn("region[view.delta]", APP)
        for field in ('delta: "delta_pp"', 'delta: "suppression_delta_pp"', 'delta: "playmaking_delta_pp"',
                      'delta: "onball_delta_pp"', 'delta: "help_delta_pp"'):
            self.assertIn(field, APP)
        self.assertIn("data-density-ratio", APP)
        self.assertNotIn("spatialInterpolatedSample", APP)
        self.assertNotIn("stableSpatialUnit", APP)
        self.assertIn("spatial-discrete-key", APP)
        self.assertIn("spatial-court-hex", APP)
        self.assertIn('viewBox="0 0 500 470"', APP)
        self.assertIn("function spatialRegionGeometry", APP)
        self.assertIn('class="spatial-region-hit"', APP)
        self.assertIn("A237.5 237.5", APP)

    def test_player_development_remains_a_card_without_team_growth_modal(self):
        development = APP[APP.index("function seasonDevelopmentCard"):APP.index("function seasonLeagueWire")]
        self.assertIn('class="season-development-list"', development)
        self.assertIn('class="season-development-row"', development)
        self.assertNotIn("data-team-development", development)
        self.assertNotIn("openTeamDevelopmentModal", APP)
        self.assertNotIn("team-development-modal", CSS)
        self.assertNotIn("data-dashboard-player-finder>All players", development)


if __name__ == "__main__":
    unittest.main()
