"""COACHES-FREE-AGENTS: coaches judged against expectations; loyal free agents and stated reasons for leaving."""
import unittest
from unittest.mock import patch

from nba_gm_data import coach_review, franchise_ties, play
from nba_gm_data.contract_ai import apply_contract_to_save_state
from nba_gm_data.save import add_re_signing_right, should_ai_retain_expiring_player
from nba_gm_data.staff import offseason_coaching_recommendations, remember_opening_coaching_staff
from nba_gm_data.staff_lifecycle import staff_win_expectations
from tests.test_staff_lifecycle import make_staff


LILLARD = {"id": "p-lillard", "espn_player_id": "6606", "name": "Damian Lillard", "age": 37.0}
LEBRON = {"id": "p-lebron", "espn_player_id": "1966", "name": "LeBron James", "age": 42.0}


def standing(seasons=1, here=0, total=None, since=None, legend=False):
    return {"seasons_with_team": seasons, "titles_with_team": here, "titles": here if total is None else total,
            "seasons_since_title": since, "legend": legend}


def coach(name, team="team_gsw", person="c1"):
    staff = make_staff(person, 61, "head_coach", team)
    staff["name"] = name
    return staff


class CoachReviewTests(unittest.TestCase):
    def test_legend_with_expected_results_cannot_be_fired(self):
        kerr = standing(13, 4, since=5, legend=True)
        self.assertEqual(coach_review.head_coach_firing_chance(-2.8, offseason=True, standing=kerr), 0.0)
        self.assertEqual(coach_review.head_coach_firing_chance(-9.9, offseason=True, standing=kerr), 0.0)
        self.assertEqual(coach_review.head_coach_firing_chance(-12.0, offseason=False, standing=kerr), 0.0)
        collapse = coach_review.head_coach_firing_chance(-20.0, offseason=True, standing=kerr)
        self.assertTrue(0 < collapse < 0.15)

    def test_firings_follow_the_miss_tenure_and_titles(self):
        chance = lambda gap, **kw: coach_review.head_coach_firing_chance(gap, offseason=True, **kw)
        plain = standing(4)
        self.assertGreater(chance(-14, standing=plain), chance(-8, standing=plain))
        self.assertGreater(chance(-8, standing=plain), chance(-5, standing=plain))
        self.assertGreater(chance(-8, standing=plain), chance(0, standing=plain))
        self.assertGreater(chance(0, standing=plain), chance(8, standing=plain))
        self.assertGreater(chance(-8, standing=standing(2)), chance(-8, standing=standing(1)))
        self.assertLess(chance(-8, standing=standing(4, 1, since=1)), chance(-8, standing=plain))
        self.assertEqual(chance(-8, standing=standing(4, 1, since=0)), 0.0)
        self.assertGreater(chance(-8, standing=plain, previous_gap=-9), chance(-8, standing=plain))
        self.assertGreater(chance(-1, standing=plain, new_direction=True), chance(-1, standing=plain))

    def test_real_standing_and_a_simulated_title(self):
        save = {"meta": {"season": "2026-27"}}
        kerr = coach_review.coach_standing(save, coach("Steve Kerr"))
        self.assertEqual((kerr["seasons_with_team"], kerr["titles_with_team"], kerr["legend"]), (13, 4, True))
        moved = coach_review.coach_standing(save, {**coach("Steve Kerr", "team_chi"), "staff_hired_on": "2026-07-01"})
        self.assertEqual((moved["seasons_with_team"], moved["titles_with_team"], moved["titles"]), (1, 0, 4))
        new = coach("New Coach", "team_bos", "c2")
        save.update(staff_slots=[new], playoff_state={"champion_team_id": "team_bos"})
        coach_review.record_coach_titles(save)
        coach_review.record_coach_titles(save)
        won = coach_review.coach_standing(save, new)
        self.assertEqual((won["titles_with_team"], won["seasons_since_title"]), (1, 0))

    def test_expectations_spread_like_preseason_win_totals(self):
        rows = [{"team_id": t, "contention_ceiling": c} for t, c in (("a", 76.0), ("b", 68.0), ("c", 62.0))]
        wins = {t: 82 * p for t, p in staff_win_expectations(rows).items()}
        self.assertGreater(wins["a"], 58)
        self.assertLess(wins["c"], 30)

    def test_injuries_and_departures_lower_the_expectation(self):
        save = {"meta": {"season": "2026-27"},
                "team_records": {"team_gsw": {"wins": 38, "losses": 44}, "team_bos": {"wins": 50, "losses": 32}},
                "health_states": [{"player_id": "star", "games_missed": 41}],
                "staff_season_expectations": {"2026-27": {
                    "team_gsw": {"key_players": {"star": 10.0, "traded": 8.0}},
                    "team_bos": {"key_players": {"healthy": 9.0}}}}}
        canonical = {"players": [{"id": "star", "team_id": "team_gsw"}, {"id": "traded", "team_id": "team_bos"},
                                 {"id": "healthy", "team_id": "team_bos"}]}
        coach_review.note_departures(canonical, save, "2027-02-01")
        review = coach_review.team_review(canonical, save, "team_gsw", 50 / 82)
        lost = 5.0 + 8.0 * 71 / 173
        self.assertAlmostEqual(review["lost_wins"], lost, delta=0.15)
        # Only the loss above the league's typical one (here half of it) moves the expectation, in both directions.
        self.assertAlmostEqual(review["expected_wins"], 50 - lost / 2, delta=0.15)
        self.assertGreater(review["gap"], -8)
        healthy = coach_review.team_review(canonical, save, "team_bos", 45 / 82)
        self.assertAlmostEqual(healthy["expected_wins"], 45 + lost / 2, delta=0.15)

    def test_summer_review_keeps_a_legend_and_explains_a_firing(self):
        teams = ("team_gsw", "team_bos")
        canonical = {"teams": [{"id": t, "abbrev": t[5:].upper(), "name": t} for t in teams]}
        kerr, other = coach("Steve Kerr"), coach("Some Coach", "team_bos", "c2")
        save = {"meta": {"seed": 1, "season": "2026-27", "user_team_id": "team_tor"},
                "state": {"current_date": "2027-09-30", "phase": "training_camp"},
                "team_records": {"team_gsw": {"wins": 38, "losses": 44}, "team_bos": {"wins": 25, "losses": 57}},
                "staff_slots": [kerr, other],
                "staff_preseason_expectations": {"2026-27": {"team_gsw": 41 / 82, "team_bos": 45 / 82}}}
        remember_opening_coaching_staff(save)
        with patch("nba_gm_data.staff.staff_turnover_draw", return_value=0.0):
            recs = offseason_coaching_recommendations(canonical, save)
        heads = [r for r in recs if r["slot"] == "head_coach"]
        self.assertEqual([r["team_id"] for r in heads], ["team_bos"])
        self.assertIn("20 wins per 82 games short of the 45 expected", heads[0]["firing_reason"])
        self.assertEqual(save["staff_season_review"]["2026-27"]["team_gsw"]["wins"], 38)


def market_save(**extra):
    """The 2027 offseason: Portland's veteran icon, Cleveland the defending champion."""
    save = {"version": "league_save_v1", "meta": {"season": "2026-27", "user_team_id": "team_bkn"},
            "state": {"current_date": "2027-07-01", "phase": "free_agency"},
            "playoff_state": {"champion_team_id": "team_cle"},
            "team_records": {"team_por": {"wins": 45, "losses": 37}, "team_cle": {"wins": 59, "losses": 23},
                             "team_sac": {"wins": 20, "losses": 62}},
            "team_plans": {"team_por": {"window_phase": "entering"}, "team_sac": {"window_phase": "rebuilding"}},
            "free_agency_state": {"season": "2026-27", "status": "active", "day": 3},
            "free_agent_offers": [], "free_agent_player_ids": [LILLARD["id"]]}
    add_re_signing_right(save, "2026-27", LILLARD["id"], "team_por")
    save.update(extra)
    return save


def offer(team, aav, interest, minutes=30.0, years=1):
    return {"id": f"{team}-{aav}", "player_id": LILLARD["id"], "team_id": team, "aav_millions": aav, "years": years,
            "interest_score": interest, "status": "active", "season": "2026-27",
            "interest_context": {"projected_minutes": minutes}}


class FreeAgentLoyaltyTests(unittest.TestCase):
    def test_icons_rings_and_chasers_come_from_real_careers(self):
        save = market_save()
        tie = franchise_ties.franchise_tie(save, LILLARD, "team_por")
        self.assertTrue(tie["icon"] and tie["drafted"] and tie["seasons"] >= 11)
        self.assertFalse(franchise_ties.franchise_tie(save, LILLARD, "team_cle")["loyal"])
        self.assertEqual(franchise_ties.championship_rings(save, LILLARD), 0)
        self.assertEqual(franchise_ties.championship_rings(save, LEBRON), 4)
        self.assertEqual(franchise_ties.chase_profile(save, LILLARD), "ringless_star_late")

    def test_season_ledger_counts_seasons_and_simulated_rings(self):
        rookie = {"id": "gen", "name": "Generated Star", "age": 33.0}
        save = market_save(player_season_stats={"gen": {"games": 70, "points": 1400, "team_abbrevs": ["CLE"]}})
        franchise_ties.record_season(save)
        franchise_ties.record_season(save)
        self.assertEqual(franchise_ties.championship_rings(save, rookie), 1)
        self.assertEqual(franchise_ties.franchise_tie(save, rookie, "team_cle")["seasons"], 1)
        self.assertTrue(franchise_ties.has_been_a_star(save, rookie))

    def test_loyalty_and_title_chase_points(self):
        save = market_save()
        loyal = franchise_ties.loyalty_points(None, save, LILLARD, "team_por", 11.0)
        self.assertGreaterEqual(loyal, 11 + 9 + 14)
        save["team_plans"]["team_por"]["window_phase"] = "rebuilding"
        self.assertEqual(franchise_ties.loyalty_points(None, save, LILLARD, "team_por", 11.0), loyal / 2)
        self.assertEqual(franchise_ties.chase_points(None, save, LILLARD, "team_cle"), 30.0)
        self.assertEqual(franchise_ties.chase_points(None, save, LILLARD, "team_sac"), 0.0)
        self.assertEqual(franchise_ties.chase_points(None, save, LILLARD, "team_por"), 0.0)

    def test_departure_reasons(self):
        save = market_save()
        why = lambda team, aav, minutes=30.0, **kw: franchise_ties.departure(
            None, save, kw.get("player", LILLARD), team, aav_millions=aav, years=1, new_minutes=minutes)
        self.assertIsNone(why("team_por", 16.0))
        chase = why("team_cle", 15.5)
        self.assertEqual((chase["key"], chase["reason"]), ("ring_chase", "chasing his first championship"))
        self.assertIn("leaving POR after", franchise_ties.departure_clause(chase))
        self.assertEqual(why("team_sac", 15.0)["key"], "no_offer")
        save["free_agent_offers"] = [offer("team_por", 12.0, 60, minutes=24.0)]
        self.assertEqual(why("team_sac", 18.0)["key"], "bigger_contract")
        self.assertEqual(why("team_sac", 12.5, minutes=33.0)["key"], "bigger_role")
        weak = why("team_sac", 12.5, minutes=25.0)
        self.assertEqual((weak["key"], weak["clear"]), ("more_money", False))
        self.assertIsNone(franchise_ties.departure(None, {"meta": {"season": "2026-27"}}, LILLARD, "team_cle",
                                                   aav_millions=15, years=1))

    def test_icon_stays_unless_the_motive_is_clear(self):
        save = market_save()
        own, plain = offer("team_por", 14.0, 66), offer("team_sac", 14.5, 75)
        self.assertIs(play.loyal_offer({}, save, LILLARD, [own, plain], plain, 72), own)
        title = offer("team_cle", 14.5, 75)
        self.assertIsNone(play.loyal_offer({}, save, LILLARD, [own, title], title, 72))
        richer = offer("team_sac", 19.0, 75)
        self.assertIsNone(play.loyal_offer({}, save, LILLARD, [own, richer], richer, 72))
        low = offer("team_por", 9.0, 40)
        self.assertIsNone(play.loyal_offer({}, save, LILLARD, [low, plain], plain, 72))
        # Your own team's offer is judged only as the offer screen shows it.
        save["meta"]["user_team_id"] = "team_por"
        self.assertIsNone(play.loyal_offer({}, save, LILLARD, [own, plain], plain, 72))

    def test_signing_news_and_transaction_say_why(self):
        save = market_save()
        why = franchise_ties.departure(None, save, LILLARD, "team_cle", aav_millions=15.5, years=1, new_minutes=30)
        accepted = {"player_id": LILLARD["id"], "team_id": "team_cle", "annual_salary": 15_500_000, "years": 1,
                    "start_season": "2027-28"}
        save["pending_contract_negotiations"] = [{
            "negotiation": {"id": "n1", "negotiation_type": "free_agent_signing", "player_id": LILLARD["id"],
                            "player_name": "Damian Lillard", "team_id": "team_cle", "departure": why},
            "decision": {"accepted": True, "accepted_offer": accepted}}]
        result = apply_contract_to_save_state(save, "n1", date="2027-07-03")
        self.assertEqual(result["status"], "applied", result)
        headline = save["league_events"][-1]["headline"]
        self.assertTrue(headline.startswith("CLE signs Damian Lillard, leaving POR after "), headline)
        self.assertIn("chasing his first championship", headline)
        self.assertIn(headline, [row["headline"] for row in save["news_items"]])
        log = save["transaction_logs"][-1]
        self.assertEqual(log["assets"]["departure"]["key"], "ring_chase")
        self.assertIn("chasing his first championship", log["notes"])
        self.assertIn("chasing his first championship",
                      franchise_ties.departure_text(save, LILLARD["id"], "team_por"))
        self.assertIsNone(franchise_ties.departure_text(save, LILLARD["id"], "team_sac"))

    def test_june_keeps_an_icon_unless_he_tests_the_market_for_a_ring(self):
        player = {**LILLARD, "team_id": "team_por", "minutes_projection": 28}
        save = market_save(free_agency_state={}, playoff_state={"champion_team_id": "team_cle"})
        kept = {should_ai_retain_expiring_player(save, player, "2026-27", seed) for seed in range(24)}
        self.assertEqual(kept, {True, False})
        save["playoff_state"] = {"champion_team_id": "team_por"}   # nowhere better to look
        self.assertTrue(all(should_ai_retain_expiring_player(save, player, "2026-27", seed) for seed in range(24)))
        young = {**player, "age": 29.0}
        save["playoff_state"] = {"champion_team_id": "team_cle"}
        self.assertTrue(all(should_ai_retain_expiring_player(save, young, "2026-27", seed) for seed in range(24)))


if __name__ == "__main__":
    unittest.main()
