"""AI cuts use evolving saved talent, not draft-class immunity or injury minutes."""
from copy import deepcopy
import json
import unittest
from unittest.mock import patch

from nba_gm_data import health, save as sv


class RosterRetentionTests(unittest.TestCase):
    def fixture(self):
        canonical = {"teams": [{"id": "ai", "abbrev": "AI"}, {"id": "human", "abbrev": "HUM"}],
                     "players": [], "traits": [], "contracts": []}
        saved = {"version": sv.SAVE_VERSION, "meta": {"season": "2029-30", "user_team_id": "human"},
                 "state": {"current_date": "2029-11-01", "phase": "regular_season"},
                 "generated_players": [], "generated_traits": [], "incoming_rookies": [],
                 "roster_overrides": {}, "free_agent_player_ids": [], "rotation_baselines": {},
                 "development_events": []}
        for i in range(14):
            self.add(canonical, saved, f"core{i:02}", 70, minutes=24, age=27, priority="core_rotation")
        return canonical, saved

    def add(self, canonical, saved, pid, rating, *, minutes=0, age=20, draft_year=None,
            priority="fringe", generated=False, potential=None, ability=None, team="ai"):
        player = {"id": pid, "name": pid, "team_id": team, "position": "SG", "age": age,
                  "age_base_start_year": 2029, "minutes_projection": minutes, "rotation_priority": priority}
        if draft_year is not None:
            player["draft_year"] = str(draft_year)
        if potential is not None:
            player.update(potential=potential, current_ability=ability)
        traits = [{"player_id": pid, "trait_key": key, "value": rating} for key in health.DEVELOPMENT_TRAITS]
        canonical_or_save = saved if generated else canonical
        canonical_or_save["generated_players" if generated else "players"].append(player)
        canonical_or_save["generated_traits" if generated else "traits"].extend(traits)
        saved["rotation_baselines"][pid] = minutes
        return player

    def cuts(self, saved):
        return {pid for pid, team in saved["roster_overrides"].items() if team is None}

    def test_developed_prior_class_beats_weak_protected_new_pick(self):
        canonical, saved = self.fixture()
        self.add(canonical, saved, "developing", 84, minutes=22, draft_year=2027,
                 generated=True, potential=88, ability=58)
        self.add(canonical, saved, "new_pick", 32, draft_year=2029, generated=True)
        sv.refresh_roster_cutdowns(canonical, saved)
        self.assertEqual(self.cuts(saved), {"new_pick"})
        self.assertEqual(len(sv.active_players_for_roster_checks(canonical, saved)), 15)

    def test_saved_development_not_original_baseline_determines_cut(self):
        canonical, saved = self.fixture()
        self.add(canonical, saved, "improved", 32)
        self.add(canonical, saved, "depth", 54)
        saved["development_trait_totals"] = {"improved": {key: 50 for key in health.DEVELOPMENT_TRAITS}}
        sv.refresh_roster_cutdowns(canonical, saved)
        self.assertEqual(self.cuts(saved), {"depth"})

    def test_injury_does_not_change_cuts_even_with_zero_baseline_minutes(self):
        canonical, healthy = self.fixture()
        self.add(canonical, healthy, "star", 96, minutes=0, priority="starter")
        self.add(canonical, healthy, "depth", 54)
        injured = deepcopy(healthy)
        injured["health_states"] = [{**health.default_state_dict("star", "2029-11-01"),
                                    "availability_status": "out", "current_injury_id": "test",
                                    "return_date": "2030-02-01"}]
        original_health = deepcopy(injured["health_states"])
        sv.refresh_roster_cutdowns(canonical, healthy)
        sv.refresh_roster_cutdowns(canonical, injured)
        self.assertEqual(self.cuts(healthy), {"depth"})
        self.assertEqual(self.cuts(healthy), self.cuts(injured))
        self.assertEqual(injured["health_states"], original_health)

    def test_low_minutes_or_stale_starter_tag_do_not_overrule_large_talent_gap(self):
        canonical, saved = self.fixture()
        self.add(canonical, saved, "talent", 90, minutes=0)
        self.add(canonical, saved, "stale_starter", 45, minutes=34, priority="starter")
        sv.refresh_roster_cutdowns(canonical, saved)
        self.assertEqual(self.cuts(saved), {"stale_starter"})

    def test_promising_young_depth_wins_a_close_decision(self):
        canonical, saved = self.fixture()
        self.add(canonical, saved, "project", 54, draft_year=2028, generated=True, potential=95, ability=45)
        self.add(canonical, saved, "depth", 56, age=28)
        sv.refresh_roster_cutdowns(canonical, saved)
        self.assertEqual(self.cuts(saved), {"depth"})

    def test_high_potential_is_not_immunity_for_a_bad_player(self):
        canonical, saved = self.fixture()
        self.add(canonical, saved, "bad_project", 20, draft_year=2029, generated=True, potential=99, ability=20)
        self.add(canonical, saved, "contributor", 66, minutes=18)
        sv.refresh_roster_cutdowns(canonical, saved)
        self.assertEqual(self.cuts(saved), {"bad_project"})

    def test_late_pick_gem_is_not_discarded_for_a_weaker_lottery_pick(self):
        canonical, saved = self.fixture()
        gem = self.add(canonical, saved, "late_gem", 80, draft_year=2027,
                       generated=True, potential=95, ability=45)
        gem["overall_pick"] = 55
        lottery = self.add(canonical, saved, "lottery", 40, draft_year=2029,
                           generated=True, potential=85, ability=40)
        lottery["overall_pick"] = 1
        sv.refresh_roster_cutdowns(canonical, saved)
        self.assertEqual(self.cuts(saved), {"lottery"})

    def test_expensive_star_is_not_cut_as_if_waiving_cleared_its_salary(self):
        canonical, saved = self.fixture()
        self.add(canonical, saved, "star", 96, minutes=0, priority="starter")
        self.add(canonical, saved, "depth", 54)
        canonical["contracts"] = [{"id": "expensive", "player_id": "star", "team_id": "ai",
                                    "seasons": [{"season": "2029-30", "salary": 70_000_000, "guaranteed": True}]}]
        sv.refresh_roster_cutdowns(canonical, saved)
        self.assertEqual(self.cuts(saved), {"depth"})

    def test_old_source_age_does_not_hide_current_regression(self):
        canonical, saved = self.fixture()
        self.add(canonical, saved, "veteran", 70, age=25, minutes=24)
        canonical["players"][-1]["age_base_start_year"] = 2017
        saved["development_trait_totals"] = {"veteran": {key: -25 for key in health.DEVELOPMENT_TRAITS}}
        self.add(canonical, saved, "young_depth", 61, minutes=0)
        sv.refresh_roster_cutdowns(canonical, saved)
        self.assertEqual(self.cuts(saved), {"veteran"})

    def test_many_recent_rookies_still_obey_cap(self):
        canonical, saved = self.fixture()
        for i in range(4):
            self.add(canonical, saved, f"rookie{i}", 30 + i, draft_year=2029, generated=True)
        sv.refresh_roster_cutdowns(canonical, saved)
        self.assertEqual(len(self.cuts(saved)), 3)
        self.assertEqual(len(sv.active_players_for_roster_checks(canonical, saved)), 15)

    def test_repeat_and_serialized_reload_do_not_duplicate_cuts(self):
        canonical, saved = self.fixture()
        self.add(canonical, saved, "good", 86, generated=True)
        self.add(canonical, saved, "bad", 30, generated=True, draft_year=2029)
        sv.refresh_roster_cutdowns(canonical, saved)
        first = deepcopy(saved)
        sv.refresh_roster_cutdowns(canonical, saved)
        self.assertEqual(saved, first)
        saved = json.loads(json.dumps(saved))
        sv.refresh_roster_cutdowns(canonical, saved)
        self.assertEqual(saved, first)
        self.assertEqual(len([t for t in saved["transaction_logs"] if t["transaction_type"] == "roster_cut"]), 1)
        self.assertNotIn("bad", saved["free_agent_player_ids"])
        self.assertEqual([r['player_id'] for r in saved['waiver_wire'] if r['status'] == 'pending'], ['bad'])

    def test_deterministic_ties_do_not_depend_on_input_order(self):
        canonical, saved = self.fixture()
        for pid in ("tie_b", "tie_a"):
            self.add(canonical, saved, pid, 30, draft_year=2029, generated=True)
        reverse = deepcopy(saved)
        reverse["generated_players"].reverse()
        sv.refresh_roster_cutdowns(canonical, saved)
        sv.refresh_roster_cutdowns(canonical, reverse)
        self.assertEqual(self.cuts(saved), self.cuts(reverse))

    def test_human_overflow_is_a_decision_not_an_auto_waiver(self):
        canonical, saved = self.fixture()
        for i in range(16):
            self.add(canonical, saved, f"human{i}", 50, team="human")
        with patch.object(sv, "roster_retention_context", side_effect=AssertionError("No AI overflow")):
            sv.refresh_roster_cutdowns(canonical, saved)
        self.assertFalse(self.cuts(saved))
        self.assertEqual(saved["pending_roster_cutdowns"][0]["cut_required"], 1)
        with self.assertRaisesRegex(ValueError, "Cut to 15"):
            sv.guard_required_phase_actions(saved, "2029-11-01", "2029-11-02")

    def test_read_only_refresh_does_not_evaluate_or_cut_ai_players(self):
        canonical, saved = self.fixture()
        for i in range(2):
            self.add(canonical, saved, f"rookie{i}", 30, generated=True)
        with patch.object(sv, "roster_retention_context", side_effect=AssertionError("Read only")):
            sv.refresh_roster_cutdowns(canonical, saved, apply_ai=False)
        self.assertFalse(self.cuts(saved))

    def test_context_does_not_mutate_original_traits_health_or_rotations(self):
        canonical, saved = self.fixture()
        self.add(canonical, saved, "generated", 86, generated=True)
        original_canonical, original_save = deepcopy(canonical), deepcopy(saved)
        context = sv.roster_retention_context(canonical, saved)
        self.assertGreater(sv.player_attribute_summary(context, "generated")["overall"], 75)
        self.assertEqual(canonical, original_canonical)
        self.assertEqual(saved, original_save)

    def test_draft_grace_tapers_and_does_not_become_a_permanent_priority(self):
        canonical, saved = self.fixture()
        player = self.add(canonical, saved, "project", 50, draft_year=2029, generated=True)
        context = sv.roster_retention_context(canonical, saved)
        player = next(p for p in context["players"] if p["id"] == "project")
        scores = []
        for year in (2029, 2030, 2031):
            saved["meta"]["season"] = f"{year}-{str(year+1)[-2:]}"
            saved["state"]["current_date"] = f"{year}-11-01"
            scores.append(sv.ai_roster_retention_score(context, saved, player))
        self.assertEqual([round(scores[i] - scores[i+1], 3) for i in (0, 1)], [2, 2])

    def test_remaining_waiver_cost_offsets_the_cheap_current_year_bonus(self):
        canonical, saved = self.fixture()
        player = canonical["players"][0]
        canonical["contracts"] = [{"player_id": player["id"], "seasons": [
            {"season": "2027-28", "salary": 1_000_000}, {"season": "2029-30", "salary": 30_000_000}]}]
        expensive = sv.ai_roster_retention_score(canonical, saved, player)
        canonical["contracts"][0]["seasons"][1]["salary"] = 1_000_000
        cheap = sv.ai_roster_retention_score(canonical, saved, player)
        self.assertAlmostEqual(cheap - expensive, 1.0 - 29*.12)

    def destination(self, canonical, saved, incoming):
        active = sv.canonical_with_save(canonical, saved)
        incoming = next(p for p in active["players"] if p["id"] == incoming["id"])
        with patch.object(sv, "ai_team_can_absorb_released_free_agent", return_value=True), \
             patch.object(sv, "team_cap_summary", return_value={"tax_space_millions": 100}), \
             patch.object(sv, "free_agent_team_score", return_value=20):
            return sv.released_free_agent_destination(active, saved, incoming, {}, 3_000_000, 17, "2029-11-01")

    def test_average_released_veteran_cannot_displace_better_low_minute_talent(self):
        canonical, saved = self.fixture()
        self.add(canonical, saved, "project", 80, generated=True, draft_year=2027, potential=95, ability=50)
        incoming = self.add(canonical, saved, "veteran", 60, minutes=32, age=35, team=None)
        self.assertIsNone(self.destination(canonical, saved, incoming))

    def test_released_star_can_replace_a_weak_recent_lottery_pick(self):
        canonical, saved = self.fixture()
        self.add(canonical, saved, "weak_rookie", 25, generated=True, draft_year=2029, potential=90, ability=30)
        incoming = self.add(canonical, saved, "star", 96, minutes=32, team=None)
        destination = self.destination(canonical, saved, incoming)
        self.assertIsNotNone(destination)
        self.assertEqual(destination["cut_player"]["id"], "weak_rookie")

    def test_replacement_uses_healthy_depth_not_a_temporarily_out_starter(self):
        canonical, saved = self.fixture()
        self.add(canonical, saved, "injured_star", 96, minutes=32, priority="starter")
        incoming = self.add(canonical, saved, "incoming", 96, minutes=32, team=None)
        saved["health_states"] = [{**health.default_state_dict("injured_star", "2029-11-01"),
                                   "availability_status": "out", "current_injury_id": "injured",
                                   "return_date": "2030-01-01"}]
        destination = self.destination(canonical, saved, incoming)
        self.assertIsNotNone(destination)
        self.assertNotEqual(destination["cut_player"]["id"], "injured_star")

    def test_prepared_context_does_not_apply_development_twice(self):
        canonical, saved = self.fixture()
        saved["development_trait_totals"] = {"core00": {key: 5 for key in health.DEVELOPMENT_TRAITS}}
        active = sv.canonical_with_save(canonical, saved)
        context = sv.roster_retention_context(active, saved, prepared_active=True)
        self.assertEqual(sv.trait_values_by_player(context)["core00"]["shooting_range"], 75)
        self.assertIs(sv.trait_values_by_player(context), sv.trait_values_by_player(context))

    def test_open_roster_signing_does_not_build_replacement_context(self):
        canonical, saved = self.fixture()
        incoming = self.add(canonical, saved, "incoming", 80, minutes=25, team=None)
        with patch.object(sv, "roster_retention_context", side_effect=AssertionError("No replacement needed")):
            destination = self.destination(canonical, saved, incoming)
        self.assertIsNotNone(destination)
        self.assertIsNone(destination["cut_player"])

    def test_financial_ineligibility_precedes_any_replacement(self):
        canonical, saved = self.fixture()
        self.add(canonical, saved, "depth", 30)
        incoming = self.add(canonical, saved, "star", 96, team=None)
        active = sv.canonical_with_save(canonical, saved)
        with patch.object(sv, "ai_team_can_absorb_released_free_agent", return_value=False), \
             patch.object(sv, "roster_retention_context", side_effect=AssertionError("Cannot afford player")):
            self.assertIsNone(sv.released_free_agent_destination(active, saved, incoming, {}, 30_000_000, 17, "2029-11-01"))

    def test_prepared_healthy_view_matches_full_clone_without_mutating_inputs(self):
        canonical, saved = self.fixture()
        saved["health_states"] = [{"player_id": "core00", "availability_status": "out"}]
        saved["rotation_overrides"] = {"ai": {"core00": 32, "core01": 25}}
        active = sv.canonical_with_save(canonical, saved)
        original = deepcopy((active, saved))
        reference_save = deepcopy(saved)
        reference_save["health_states"] = []
        expected = deepcopy({key: value for key, value in active.items() if not key.startswith("_")})
        expected["_allow_internal_caches"] = True
        sv.apply_save_rotation_projection(expected, reference_save)
        actual = sv.roster_retention_context(active, saved, prepared_active=True)
        clean = lambda context: {key: value for key, value in context.items() if not key.startswith("_")}
        self.assertEqual(clean(actual), clean(expected))
        self.assertEqual((active, saved), original)
        self.assertIsNot(actual["players"][0], active["players"][0])

    def test_prepared_healthy_view_does_not_copy_unrelated_history(self):
        class NoHistoryCopy:
            def __deepcopy__(self, memo):
                raise AssertionError("Unrelated history was recursively copied")

        canonical, saved = self.fixture()
        history = [NoHistoryCopy()]
        saved["game_results"] = history
        canonical["player_game_logs"] = history
        context = sv.roster_retention_context(canonical, saved, prepared_active=True)
        self.assertIs(context["player_game_logs"], history)
        self.assertEqual(len(context["players"]), 14)

    def test_released_candidates_share_context_until_an_actual_signing(self):
        for sign_first in (False, True):
            with self.subTest(sign_first=sign_first):
                canonical, saved = self.fixture()
                for index in range(3):
                    pid = f"free{index}"
                    self.add(canonical, saved, pid, 80, minutes=24, team=None)
                    saved["free_agent_player_ids"].append(pid)
                    saved.setdefault("released_free_agents", {})[pid] = {"status": "available"}
                views = []

                def destination(active, state, player, *args, retention_context_factory=None):
                    views.append(retention_context_factory())
                    if sign_first and len(views) == 1:
                        return {"team": canonical["teams"][0], "cut_player": None, "score": 50}
                    return None

                def sign(state, player, team, *args):
                    state["roster_overrides"][player["id"]] = team["id"]
                    state["free_agent_player_ids"].remove(player["id"])

                with patch.object(sv, "released_free_agent_destination", side_effect=destination), \
                     patch.object(sv, "apply_inseason_released_free_agent_signing", side_effect=sign), \
                     patch.object(sv, "canonical_with_save", wraps=sv.canonical_with_save) as build, \
                     patch.object(sv, "roster_retention_context", wraps=sv.roster_retention_context) as healthy:
                    result = sv.process_inseason_released_free_agent_signings(canonical, saved, 17, "2029-11-01")
                self.assertEqual(len(views), 3)
                self.assertEqual(build.call_count, 2 if sign_first else 1)
                self.assertEqual(healthy.call_count, 2 if sign_first else 1)
                self.assertIs(views[1], views[2])
                self.assertEqual(views[0] is views[1], not sign_first)
                self.assertEqual(len(result), int(sign_first))


if __name__ == "__main__":
    unittest.main()
