from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]
APP = (ROOT / "src/nba_gm_data/gui/app.js").read_text(encoding="utf-8")
CSS = (ROOT / "src/nba_gm_data/gui/styles.css").read_text(encoding="utf-8")


class Concept74GuiTests(unittest.TestCase):
    def test_dashboard_uses_authored_two_row_composition(self):
        dashboard = APP[
            APP.index("function seasonCommandDashboardMarkup"):
            APP.index("function seasonPanelHeader")
        ]
        for class_name in (
            "season-diagnostics-row",
            "season-operations-row",
            "season-matchup-stack",
            "season-intelligence-grid",
        ):
            self.assertIn(class_name, dashboard)
        self.assertIn("seasonIdentityCard", dashboard)
        self.assertIn("seasonTeamSignalsCard", dashboard)
        self.assertIn("seasonTeamRadarsCard", dashboard)
        self.assertIn("seasonOpponentCard", dashboard)
        self.assertNotIn("seasonPreviousGamesCard", dashboard)
        self.assertIn("seasonEfficiencyCard", dashboard)
        self.assertIn("seasonProspectsCard", dashboard)
        self.assertIn("seasonAwardsCard", dashboard)

    def test_rating_and_scouting_bars_use_solid_sampled_color(self):
        mini_rating = APP[
            APP.index("function seasonMiniRating"):
            APP.index("function seasonFatigueCell")
        ]
        prospects = APP[
            APP.index("function seasonProspectsCard"):
            APP.index("function regularSeasonProgressSlot")
        ]
        self.assertIn("performanceBarStyle(score)", mini_rating)
        self.assertIn("performanceBarStyle(confidence)", prospects)
        self.assertIn("grid-template-columns: 18px minmax(0, 1fr)", CSS)
        self.assertIn("background: var(--bar-color", CSS)
        self.assertNotIn("linear-gradient", mini_rating)
        self.assertNotIn("linear-gradient", prospects)

    def test_minutes_and_opponent_share_row_height(self):
        specification = CSS[CSS.rindex("Regular-season command surface") :]
        self.assertIn(
            ".season-opponent-table { display: grid; grid-template-rows: 15px repeat(6, minmax(0, 1fr))",
            specification,
        )
        self.assertIn("grid-template-rows: 18px repeat(var(--roster-count), minmax(0, 1fr));", specification)
        self.assertIn(".season-minutes-table {", specification)

    def test_outer_rows_share_exact_width_and_header_treatment(self):
        specification = CSS[CSS.rindex("Regular-season command surface") :]
        self.assertIn(".season-diagnostics-row,\n.season-operations-row", specification)
        self.assertIn("width: 100%;", specification)
        self.assertIn("--season-card-header-height", specification)
        self.assertIn("white-space: nowrap;", specification)
        self.assertIn("--season-text: #edf2f4", specification)
        self.assertIn("--season-muted: #8e9ba1", specification)

    def test_dense_tables_reserve_status_and_mpg_width_without_card_overflow(self):
        specification = CSS[CSS.rindex("Regular-season command surface") :]
        minutes = specification[
            specification.index(".season-minutes-head,"):
            specification.index(".season-minutes-head {")
        ]
        prospects = specification[
            specification.index(".season-prospects-head,"):
            specification.index(".season-prospects-head {")
        ]
        # Minutes table was reduced to Player / Pos / Height / Minutes / Fatigue columns.
        self.assertIn("minmax(112px,1.25fr) minmax(88px,1fr) minmax(52px,.7fr)", minutes)
        self.assertIn("minmax(0, 1.6fr)", prospects)
        self.assertNotIn("minmax(100px", prospects)

    def test_minutes_add_age_and_preserve_authored_group_gaps(self):
        minutes = APP[
            APP.index("function seasonMinutesCard"):
            APP.index("function seasonMiniRating")
        ]
        specification = CSS[CSS.rindex("Regular-season command surface") :]
        # The Age column was removed from the minutes card (and its nth-child group-gap CSS with it).
        # The Player cell also holds the "Coach rests players" toggle (FATIGUE-REST); the five columns are unchanged.
        self.assertIn('<span class="season-minutes-player-head"><span>Player</span>', minutes)
        self.assertIn("</span><span>Pos</span><span>Height</span><span>Minutes</span><span>Fatigue</span>", minutes)

    def test_team_radars_are_stacked_between_signals_and_standings(self):
        dashboard = APP[
            APP.index("function seasonCommandDashboardMarkup"):
            APP.index("function seasonPanelHeader")
        ]
        signals_at = dashboard.index("season-signals-panel")
        radars_at = dashboard.index("season-radars-panel")
        standings_at = dashboard.index("season-standings-panel")
        self.assertLess(signals_at, radars_at)
        self.assertLess(radars_at, standings_at)
        self.assertIn("grid-template-rows: repeat(2, minmax(0, 1fr))", CSS)

    def test_trend_charts_keep_fixed_season_horizons(self):
        efficiency = APP[
            APP.index("function seasonEfficiencyCard"):
            APP.index("function seasonProspectsCard")
        ]
        development = APP[
            APP.index("function developmentLineChart"):
            APP.index("function normalizeDevelopmentSeries")
        ]
        self.assertIn("Math.max(26, source.length", efficiency)
        self.assertIn("seasonSlots - 1", efficiency)
        # The prospect-stock chart was removed; its season-progress helper remains.
        self.assertIn("function regularSeasonProgressSlot(totalSlots = 26)", APP)
        self.assertIn("months.length", development)
        self.assertNotIn("season-horizon-guide", efficiency)
        self.assertIn("season-horizon-guide", development)
        self.assertIn('x1="${padX}" y1="${height / 2}"', development)

    def test_dashboard_includes_four_factors_and_real_rookie_candidates(self):
        signals = APP[
            APP.index("function seasonTeamSignalsCard"):
            APP.index("function performanceBarColor")
        ]
        awards = APP[
            APP.index("function seasonAwardsCard"):
            APP.index("function seasonStaffCard")
        ]
        self.assertIn("four_factors", signals)
        self.assertIn("Four Factors", signals)
        self.assertIn("dashboardSummaryLeaders?.rookies", awards)

    def test_weekly_efficiency_uses_dense_fixed_grid_and_three_series(self):
        efficiency = APP[
            APP.index("function seasonEfficiencyCard"):
            APP.index("function seasonProspectsCard")
        ]
        # Dense fixed grid is now built from seasonSlots (>= 26 weekly slots) rather than 13/7 literals.
        self.assertIn("Array.from({length: seasonSlots}", efficiency)
        self.assertIn("gridRows", efficiency)
        self.assertIn('class="net ', efficiency)
        self.assertIn('class="offense secondary', efficiency)
        self.assertIn('class="defense secondary', efficiency)

    def test_weekly_efficiency_footer_clarifies_average_without_axis_overlap(self):
        efficiency = APP[
            APP.index("function seasonEfficiencyCard"):
            APP.index("function seasonProspectsCard")
        ]
        self.assertIn("chartHeight - 42", efficiency)
        self.assertNotIn('class="axis-caption"', efficiency)
        # The league-average context caption was replaced by series plotted relative to the league average,
        # with a legend row; the card-board panel now has two grid rows.
        self.assertIn("league_average", efficiency)
        self.assertIn('class="season-efficiency-legend"', efficiency)
        board_css = (ROOT / "src/nba_gm_data/gui/card-board.css").read_text(encoding="utf-8")
        self.assertIn("season-efficiency-panel.card-board-headerless { grid-template-rows:minmax(0,1fr) auto; }", board_css)

    def test_minutes_use_visible_fill_rail(self):
        minutes = APP[
            APP.index("function seasonMinutesCard"):
            APP.index("function seasonMiniRating")
        ]
        self.assertIn("season-minute-slider", minutes)
        self.assertIn("season-minute-fill", minutes)
        self.assertIn("minuteValue / 48", minutes)


if __name__ == "__main__":
    unittest.main()
