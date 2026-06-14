import json
import random
import tempfile
import unittest
from contextlib import redirect_stdout
from io import StringIO
from pathlib import Path
from collections import Counter

from nba_gm_data.cli import main as cli_main
from nba_gm_data.contract_ai import (
    apply_contract_to_save,
    contract_market_report,
    evaluate_signing,
    extension_candidates_report,
    free_agents_report,
    negotiate_extension,
    simulate_free_agency,
)
from nba_gm_data.draft import (
    apply_draft_selection_to_save,
    draft_board_report,
    draft_class_payload,
    evaluate_draft_pick,
    find_draft_trade,
    generate_draft_order,
    generate_draft_class_records,
    pick_recommendations,
    project_rookie_contract,
    simulate_draft,
)
from nba_gm_data.health import (
    advance_development,
    health_player_report,
    health_team_report,
    load_injury_model_config,
    performance_staff_modifiers,
    simulate_health,
)
from nba_gm_data.ingest import build_universe
from nba_gm_data.research import existing_game_boxscores
from nba_gm_data.save import (
    advance_save,
    box_score_view,
    calendar_view,
    complete_offseason_and_rollover,
    create_league_save,
    hold_press_conference,
    league_leaders,
    league_standings,
    load_save,
    morale_report,
    offseason_status,
    pending_actions_view,
    apply_ai_staff_recommendations,
    age_staff_contracts,
    playoff_picture,
    cap_lines_for_season,
    process_ai_actions,
    propose_trade_to_save,
    quick_sim_current_season,
    run_draft_lottery,
    save_status,
    simulate_playoff_round,
    social_feed_view,
    start_playoffs,
    team_dashboard,
    write_save,
    canonical_with_save,
    merge_health_results,
    maybe_queue_rare_drama,
    press_impact,
    queue_aggregated_press_event,
    generate_league_awards,
    team_rotation_projection,
    team_cap_summary,
)
from nba_gm_data.play import (
    box_score_influence,
    contract_start_season_for_signing,
    contextual_press_answers,
    free_agency_user_offer_limit,
    initialize_free_agency_market,
    offer_interest_score,
    signing_cap_check,
)
from nba_gm_data.schema import TradeProposal, to_plain
from nba_gm_data.sim import (
    american_to_implied_probability,
    age_fatigue_effect,
    apply_manifesto_expectation_adjustments,
    availability_gap_effect,
    calibrate_market,
    calibrated_win_probability,
    coach_ratings,
    explain_game_probability,
    game_player_pool,
    game_environment_effect,
    lineup_quality_effect,
    load_sim_context,
    matchup_total_environment_effect,
    normalize_game_team_abbrev,
    no_vig_probabilities,
    player_feature_vector,
    player_star_power_score,
    recent_scoring_context_for_team,
    scheduled_game_for_context,
    scoring_weight,
    sim_game,
    team_feature_vector,
    validate,
    validate_game_probabilities,
    validate_season_probabilities,
)
from nba_gm_data.storage import write_outputs
from nba_gm_data.staff import fire_staff_from_save, hire_staff_from_save, negotiate_staff_hire, simulate_ai_staff_changes, staff_budget_for_team, staff_budget_snapshot, staff_grade, staff_market_report, staff_team_report
from nba_gm_data.transactions import apply_trade_to_save, current_salary, evaluate_trade, find_trade, find_trade_for_assets, gm_report, package_value_for_team, pick_asset_value, simulate_ai_trades, stepien_guardrail_issues, trade_block_report, tradeable_picks_for_team, with_transaction_context


ROOT = Path(__file__).resolve().parents[1]


class DataFoundationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.universe = build_universe(ROOT)
        cls.plain = to_plain(cls.universe)

    def test_builds_expected_core_counts(self):
        self.assertEqual(len(self.universe.teams), 30)
        self.assertGreaterEqual(len(self.universe.players), 500)
        self.assertEqual(len(self.universe.traits), len(self.universe.players) * 15)
        self.assertGreaterEqual(len(self.universe.sources), 8)

    def test_rotation_players_have_canonical_traits(self):
        rotation = [player for player in self.universe.players if player.rotation_priority in {"core_rotation", "rotation", "development_priority"}]
        traits_by_player = {}
        for trait in self.universe.traits:
            traits_by_player.setdefault(trait.player_id, set()).add(trait.trait_key)
        for player in rotation[:50]:
            self.assertIn("shooting_range", traits_by_player[player.id])
            self.assertIn("rim_deterrence", traits_by_player[player.id])
            self.assertIn("portability", traits_by_player[player.id])

    def test_known_archetypes_survive_trait_ingestion(self):
        traits = {(trait.player_id, trait.trait_key): trait for trait in self.universe.traits}
        players = {player.normalized_name: player for player in self.universe.players}
        curry = players["stephen curry"]
        jokic = players["nikola jokic"]
        luka = players["luka doncic"]
        draymond = players["draymond green"]
        wemby = players["victor wembanyama"]
        giannis = players["giannis antetokounmpo"]
        caruso = players["alex caruso"]
        adams = players["steven adams"]
        jaren = players["jaren jackson jr"]
        self.assertGreaterEqual(traits[(curry.id, "shooting_range")].value, 80)
        self.assertGreaterEqual(traits[(wemby.id, "rim_deterrence")].value, 75)
        self.assertGreaterEqual(traits[(giannis.id, "rim_pressure")].value, 90)
        self.assertLess(traits[(jokic.id, "rim_deterrence")].value, traits[(wemby.id, "rim_deterrence")].value - 20)
        self.assertLess(traits[(luka.id, "foot_speed_lateral_agility")].value, 45)
        self.assertGreaterEqual(traits[(draymond.id, "scheme_iq")].value, 90)
        self.assertGreaterEqual(traits[(caruso.id, "defensive_effort")].value, 70)
        self.assertGreaterEqual(traits[(adams.id, "offensive_rebounding")].value, 70)
        self.assertGreaterEqual(traits[(jaren.id, "rim_deterrence")].value, 90)
        self.assertGreaterEqual(traits[(jaren.id, "scheme_iq")].value, 80)
        zion = players["zion williamson"]
        self.assertGreaterEqual(traits[(zion.id, "rim_pressure")].value, 90)

    def test_manual_player_physical_overrides_apply(self):
        players = {player.normalized_name: player for player in self.universe.players}
        self.assertEqual(players["trey alexander"].height_inches, 77)
        self.assertEqual(players["karlo matkovic"].height_inches, 82)
        self.assertEqual(players["hunter dickinson"].height_inches, 85)

    def test_ledger_gaps_are_explicit(self):
        summary = self.universe.coverage_report.summary
        future_second_scaffolds = [
            pick
            for pick in self.universe.draft_picks
            if pick.status == "inferred_future_second_round_scaffold"
        ]
        self.assertEqual(summary["research_pending"]["contracts"], 0)
        self.assertEqual(summary["contract_manual_review_count"], 5)
        self.assertGreaterEqual(summary["research_pending"]["draft_picks"] + len(future_second_scaffolds), 1)
        self.assertEqual(summary["research_pending"]["staff_profiles"], 0)
        self.assertEqual(summary["missing_gameplay_staff_slots"], 0)
        self.assertEqual(summary["rotation_missing_without_fallback"], 0)

    def test_public_contract_and_draft_sources_populate_ledger(self):
        verified_contracts = [contract for contract in self.universe.contracts if contract.status == "verified_public_salary_table"]
        verified_picks = [pick for pick in self.universe.draft_picks if pick.status == "verified_2026_draft_board"]
        future_picks = [pick for pick in self.universe.draft_picks if pick.status == "verified_future_pick_reference"]
        self.assertGreaterEqual(len(verified_contracts), 300)
        self.assertEqual(len(verified_picks), 60)
        self.assertGreaterEqual(len(future_picks), 180)
        self.assertTrue(any("src_spotrac_future_picks" in pick.source_ids for pick in future_picks))
        curry = next(player for player in self.universe.players if player.normalized_name == "stephen curry")
        curry_contract = next(contract for contract in self.universe.contracts if contract.player_id == curry.id)
        self.assertEqual(curry_contract.seasons[0]["season"], "2025-26")
        self.assertGreater(curry_contract.seasons[0]["salary"], 50_000_000)

    def test_2026_draft_prospects_preserve_pick_ledger_separation(self):
        self.assertEqual(len([pick for pick in self.universe.draft_picks if pick.season == "2026"]), 60)
        self.assertEqual(len(self.universe.draft_classes), 1)
        self.assertEqual(len(self.universe.draft_prospects), 60)
        self.assertEqual(len(self.universe.draft_prospect_traits), 60 * 12)
        self.assertEqual(len(self.universe.scouting_reports), len(self.universe.teams) * 60)
        self.assertEqual(len(self.universe.draft_board_entries), len(self.universe.teams) * 60)
        prospects = {prospect.normalized_name: prospect for prospect in self.universe.draft_prospects}
        self.assertIn("aj dybantsa", prospects)
        self.assertIn("src_tankathon_2026_mock_draft", prospects["aj dybantsa"].source_ids)
        self.assertLessEqual(prospects["aj dybantsa"].rank_range["low"], prospects["aj dybantsa"].rank_range["high"])
        self.assertGreater(prospects["aj dybantsa"].height_inches, 78)

    def test_generated_draft_classes_are_deterministic_and_variable(self):
        first = to_plain(generate_draft_class_records("2028", seed=7))
        second = to_plain(generate_draft_class_records("2028", seed=7))
        other = to_plain(generate_draft_class_records("2028", seed=8))
        self.assertEqual(first, second)
        self.assertNotEqual(first["draft_classes"][0]["class_strength"], other["draft_classes"][0]["class_strength"])
        self.assertEqual(len(first["draft_prospects"]), 60)
        self.assertEqual(len(first["draft_prospect_traits"]), 60 * 12)
        self.assertLessEqual(max(float(prospect["current_ability"]) for prospect in first["draft_prospects"]), 69)
        self.assertTrue(all(prospect["source_ids"] == ["src_draft_model_config_v1"] for prospect in first["draft_prospects"]))
        names = [prospect["name"] for prospect in first["draft_prospects"]]
        self.assertEqual(len(names), len(set(names)))
        self.assertFalse(any(any(char.isdigit() for char in name) for name in names))
        self.assertGreaterEqual(len({name.split()[-1] for name in names}), 35)

    def test_cap_growth_contract_metadata_and_old_pick_expiry(self):
        self.assertGreater(cap_lines_for_season("2028-29")["tax_line"], cap_lines_for_season("2025-26")["tax_line"])
        with tempfile.TemporaryDirectory() as tmp:
            save_path = Path(tmp) / "league_save.json"
            save = create_league_save(ROOT, self.plain, "GSW", save_path, seed=21)
            active = canonical_with_save(self.plain, save)
            self.assertTrue(all(contract.get("original_contract_years") for contract in active.get("contracts", []) if contract.get("seasons")))
            save["meta"]["season"] = "2027-28"
            save["state"] = {"current_date": "2028-02-01", "phase": "regular_season", "legal_actions": ["trades"]}
            write_save(save_path, save)
            future_active = canonical_with_save(self.plain, load_save(save_path))
            expired_2027 = [pick for pick in future_active.get("draft_picks", []) if str(pick.get("season")) == "2027"]
            self.assertTrue(expired_2027)
            self.assertTrue(all(pick.get("current_owner_team_id") is None for pick in expired_2027))

    def test_future_draft_order_lottery_is_deterministic_and_pick_aware(self):
        first = generate_draft_order(self.plain, "2027", seed=4)
        second = generate_draft_order(self.plain, "2027", seed=4)
        other = generate_draft_order(self.plain, "2027", seed=5)
        self.assertEqual(first, second)
        self.assertEqual(first["pick_count"], 60)
        self.assertEqual(len(first["lottery"]["lottery_draw"]), 4)
        self.assertEqual(len(set(first["lottery"]["lottery_draw"])), 4)
        self.assertNotEqual(first["lottery"]["lottery_draw"], other["lottery"]["lottery_draw"])
        first_round = [pick for pick in first["draft_order"] if pick["round"] == 1]
        second_round = [pick for pick in first["draft_order"] if pick["round"] == 2]
        self.assertEqual([pick["overall_pick"] for pick in first_round], list(range(1, 31)))
        self.assertEqual([pick["overall_pick"] for pick in second_round], list(range(31, 61)))

    def test_scouting_reports_and_boards_have_fog_and_staff_context(self):
        payload = draft_class_payload(self.plain, "2026", scouted_for="WAS")
        self.assertEqual(payload["prospect_count"], 60)
        self.assertEqual(len(payload["scouting_reports"]), 60)
        report = payload["scouting_reports"][0]
        self.assertLessEqual(report["estimated_current"]["low"], report["estimated_current"]["mid"])
        self.assertLessEqual(report["estimated_current"]["mid"], report["estimated_current"]["high"])
        self.assertGreaterEqual(report["confidence"], 0.38)
        self.assertLessEqual(report["confidence"], 0.88)
        board = draft_board_report(self.plain, "WAS", "2026", limit=5)
        self.assertEqual(board["team"]["abbrev"], "WAS")
        self.assertEqual(board["entry_count"], 5)
        self.assertEqual(board["entries"][0]["prospect"]["name"], "AJ Dybantsa")

    def test_ai_draft_decisions_recommendations_trades_and_save_ledger(self):
        recommendations = pick_recommendations(self.plain, "WAS", "pick_2026-1-1-was", limit=3, seed=3)
        self.assertEqual(recommendations["recommendations"][0]["entry"]["prospect"]["name"], "AJ Dybantsa")
        decision = evaluate_draft_pick(self.plain, "WAS", "pick_2026-1-1-was", "AJ Dybantsa", seed=3)
        self.assertEqual(decision["decision"]["decision"], "select")
        self.assertIn("best_player_available", decision["decision"]["reasons"])
        trades = find_draft_trade(self.plain, "SAC", "pick_2026-1-7-sac", limit=2, seed=2)
        self.assertEqual(trades["candidate_count"], 2)
        self.assertIn("proposal", trades["candidates"][0])
        draft = simulate_draft(self.plain, "2026", seed=2)
        self.assertEqual(draft["selection_count"], 60)
        self.assertEqual(len(draft["draft_rights"]), 60)
        self.assertEqual(len(draft["rookie_contracts"]), 60)
        self.assertEqual(draft["rookie_contracts"][0]["contract_type"], "first_round_rookie_scale")
        pending = draft["pending_draft_selections"][0]
        with tempfile.TemporaryDirectory() as tmp:
            save_path = Path(tmp) / "save.json"
            save_path.write_text(json.dumps({"version": "league_save_v1", "pending_draft_selections": draft["pending_draft_selections"][:2], "transaction_logs": []}), encoding="utf-8")
            result = apply_draft_selection_to_save(save_path, draft["selections"][0]["id"])
            self.assertEqual(result["status"], "applied")
            signed_result = apply_draft_selection_to_save(save_path, draft["selections"][1]["id"], sign_rookie=True)
            self.assertEqual(signed_result["status"], "applied")
            saved = json.loads(save_path.read_text(encoding="utf-8"))
            self.assertEqual(len(saved["transaction_logs"]), 2)
            self.assertEqual(len(saved["draft_rights"]), 2)
            self.assertEqual(len(saved["rookie_contracts"]), 2)
            self.assertEqual(len(saved["incoming_rookies"]), 2)
            self.assertEqual(saved["incoming_rookies"][0]["name"], "AJ Dybantsa")
            self.assertEqual(len(saved["generated_players"]), 1)
            self.assertEqual(len(saved["generated_traits"]), 15)
            self.assertIn(draft["selections"][1]["pick_id"], saved["draft_pick_overrides"])
            self.assertEqual(saved["incoming_rookies"][1]["roster_status"], "signed_rookie")
        filtered = pick_recommendations(
            self.plain,
            "WAS",
            "pick_2026-1-1-was",
            limit=3,
            seed=3,
            unavailable_prospect_ids={recommendations["recommendations"][0]["entry"]["prospect"]["prospect_id"]},
        )
        self.assertNotEqual(filtered["recommendations"][0]["entry"]["prospect"]["name"], "AJ Dybantsa")

    def test_rookie_contract_projection_and_future_simulated_draft_onboarding(self):
        contract = project_rookie_contract(self.plain, "WAS", "pick_2026-1-1-was", "AJ Dybantsa")
        self.assertEqual(contract["rookie_contract"]["contract_type"], "first_round_rookie_scale")
        self.assertEqual(len(contract["rookie_contract"]["seasons"]), 4)
        self.assertEqual(contract["rookie_contract"]["seasons"][0]["season"], "2026-27")
        self.assertTrue(contract["rookie_contract"]["seasons"][0]["guaranteed"])
        second_round = project_rookie_contract(self.plain, "WAS", "pick_2026-2-60-was", "Milos Uzan")
        self.assertEqual(second_round["rookie_contract"]["contract_type"], "second_round_minimum_framework")
        self.assertEqual(len(second_round["rookie_contract"]["seasons"]), 2)
        future = simulate_draft(self.plain, "2027", seed=4)
        self.assertEqual(future["selection_count"], 60)
        self.assertIn("lottery", future)
        self.assertEqual(len(future["draft_order"]), 60)
        self.assertEqual(len(future["pending_draft_selections"]), 60)
        self.assertEqual(len(future["incoming_rookies"]), 60)
        with tempfile.TemporaryDirectory() as tmp:
            save_path = Path(tmp) / "rookie_age_save.json"
            save = create_league_save(ROOT, self.plain, "GSW", save_path, seed=4)
            save["meta"]["season"] = "2026-27"
            save["state"] = {"current_date": "2027-06-27", "phase": "draft", "legal_actions": ["trades", "draft_picks"]}
            save["pending_draft_selections"] = future["pending_draft_selections"][:1]
            write_save(save_path, save)
            applied = apply_draft_selection_to_save(save_path, future["selections"][0]["id"], date="2027-06-27", sign_rookie=True)
            self.assertEqual(applied["status"], "applied")
            saved = load_save(save_path)
            rookie = saved["generated_players"][0]
            saved["meta"]["season"] = "2027-28"
            saved["state"] = {"current_date": "2027-10-01", "phase": "preseason", "legal_actions": []}
            active = canonical_with_save(self.plain, saved)
            active_rookie = next(player for player in active["players"] if player["id"] == rookie["id"])
            self.assertEqual(float(active_rookie["display_age"]), float(rookie["age"]))

    def test_awards_generate_from_saved_stats(self):
        with tempfile.TemporaryDirectory() as tmp:
            save_path = Path(tmp) / "awards_save.json"
            save = create_league_save(ROOT, self.plain, "GSW", save_path, seed=31)
            players = {player["normalized_name"]: player for player in self.plain["players"]}
            curry = players["stephen curry"]
            wemby = players["victor wembanyama"]
            save["team_records"][curry["team_id"]]["wins"] = 58
            save["team_records"][curry["team_id"]]["losses"] = 24
            save["team_records"][wemby["team_id"]]["wins"] = 47
            save["team_records"][wemby["team_id"]]["losses"] = 35
            save["player_season_stats"][curry["id"]] = {"games": 74, "minutes": 2450, "points": 2300, "rebounds": 330, "assists": 610, "steals": 95, "blocks": 25}
            save["player_season_stats"][wemby["id"]] = {"games": 72, "minutes": 2520, "points": 1900, "rebounds": 920, "assists": 310, "steals": 95, "blocks": 265}
            awards = generate_league_awards(self.plain, save, "2025-26", seed=31)
            self.assertTrue(any(award["award"] == "MVP" for award in awards))
            self.assertTrue(any(award["award"] == "DPOY" for award in awards))
            self.assertTrue(any(item.get("kind") == "award" for item in save.get("news_items", [])))

    def test_public_staff_sources_populate_key_roles(self):
        verified_staff = [staff for staff in self.universe.staff_profiles if staff.status != "research_pending"]
        self.assertGreaterEqual(len(verified_staff), 90)
        okc_head = next(staff for staff in self.universe.staff_profiles if staff.team_id == "team_okc" and staff.role == "head_coach")
        okc_front_office = next(staff for staff in self.universe.staff_profiles if staff.team_id == "team_okc" and staff.role == "front_office_identity")
        self.assertEqual(okc_head.name, "Mark Daigneault")
        self.assertEqual(okc_front_office.name, "Sam Presti")

    def test_manual_staff_overrides_preserve_preseason_snapshot(self):
        chi_head = next(staff for staff in self.universe.staff_profiles if staff.team_id == "team_chi" and staff.role == "head_coach")
        orl_head = next(staff for staff in self.universe.staff_profiles if staff.team_id == "team_orl" and staff.role == "head_coach")
        self.assertEqual(chi_head.name, "Billy Donovan")
        self.assertEqual(chi_head.status, "manual_snapshot_override")
        self.assertEqual(orl_head.name, "Jamahl Mosley")
        self.assertEqual(orl_head.status, "manual_snapshot_override")
        self.assertFalse(any(staff.role == "head_scout" for staff in self.universe.staff_profiles))
        self.assertFalse(any(staff.role == "lead_offense_assistant" for staff in self.universe.staff_profiles))

    def test_gameplay_staff_slots_are_complete_and_fictional(self):
        expected_slots = {"head_coach", "offensive_coordinator", "defensive_coordinator", "development_lead", "scouting_lead", "performance_lead"}
        slots_by_team = {}
        for slot in self.universe.gameplay_staff_slots:
            slots_by_team.setdefault(slot.team_id, set()).add(slot.slot)
            self.assertEqual(slot.status, "fictional_gameplay_scaffold")
            self.assertIn("src_gameplay_staff_seed_v1", slot.source_ids)
        self.assertEqual(len(self.universe.gameplay_staff_slots), len(self.universe.teams) * len(expected_slots))
        for team in self.universe.teams:
            self.assertEqual(slots_by_team[team.id], expected_slots)

    def test_league_save_creation_advancement_and_views(self):
        with tempfile.TemporaryDirectory() as tmp:
            save_path = Path(tmp) / "league_save.json"
            save = create_league_save(ROOT, self.plain, "GSW", save_path, seed=9)
            self.assertEqual(save["version"], "league_save_v1")
            self.assertEqual(save["state"]["current_date"], "2025-10-01")
            self.assertEqual(save["state"]["phase"], "preseason")
            self.assertEqual(len(save["staff_slots"]), len(self.universe.teams) * 6)
            self.assertEqual(save["schedule_state"]["simulated_game_ids"], [])

            first = advance_save(ROOT, self.plain, save_path, to_date="2025-10-21", seed=9)
            second = advance_save(ROOT, self.plain, save_path, to_date="2025-10-21", seed=9)
            self.assertEqual(first["games_simulated"], 2)
            self.assertEqual(second["games_simulated"], 0)
            saved = load_save(save_path)
            self.assertEqual(saved["state"]["phase"], "regular_season")
            self.assertEqual(len(saved["game_results"]), 2)
            self.assertTrue(all(result["home_score"] != result["away_score"] for result in saved["game_results"]))
            self.assertLess(max(line["minutes"] for result in saved["game_results"] for line in result["player_lines"]), 43)
            self.assertEqual(len(saved["schedule_state"]["simulated_game_ids"]), 2)
            self.assertEqual(sum(record["wins"] + record["losses"] for record in saved["team_records"].values()), 4)
            self.assertEqual(
                sum(stats["points"] for stats in saved["player_season_stats"].values()),
                sum(line["points"] for result in saved["game_results"] for line in result["player_lines"]),
            )

            status = save_status(ROOT, self.plain, save_path)
            self.assertEqual(status["phase"], "regular_season")
            self.assertIn("staff_changes", status["legal_actions"])
            standings = league_standings(self.plain, save_path)
            leaders = league_leaders(self.plain, save_path, stat="points", limit=5)
            calendar = calendar_view(ROOT, self.plain, save_path, from_date="2025-10-21", through_date="2025-10-21")
            box_score = box_score_view(self.plain, save_path, saved["game_results"][0]["game_id"])
            dashboard = team_dashboard(ROOT, self.plain, save_path, "GSW")
            self.assertEqual(standings["team_count"], 30)
            self.assertGreater(len(leaders["leaders"]), 0)
            self.assertEqual(calendar["game_count"], 2)
            self.assertIsNotNone(calendar["games"][0]["home_score"])
            self.assertGreater(len(box_score["player_lines"]), 10)
            self.assertEqual(dashboard["team"]["abbrev"], "GSW")
            self.assertIn("health_summary", dashboard)
            self.assertIn("team_identity", dashboard)
            self.assertIn("overall", dashboard["team_identity"]["metrics"])
            self.assertIn("offense", dashboard["team_identity"]["ranks"])
            self.assertTrue(all("age" in row for row in dashboard["rotation"]))
            head = next(slot for slot in saved["staff_slots"] if slot["team_id"] == "team_gsw" and slot["slot"] == "head_coach")
            self.assertEqual(head["name"], "Steve Kerr")

    def test_staff_market_negotiation_hire_and_effects_are_save_state_only(self):
        with tempfile.TemporaryDirectory() as tmp:
            save_path = Path(tmp) / "league_save.json"
            save = create_league_save(ROOT, self.plain, "GSW", save_path, seed=5)
            original_canonical_staff = list(self.plain["gameplay_staff_slots"])
            market = staff_market_report(self.plain, save, slot="performance_lead", limit=1)
            candidate = market["candidates"][0]
            negotiation = negotiate_staff_hire(self.plain, save, candidate["id"], "GSW", "performance_lead", seed=5)
            self.assertTrue(negotiation["accepted"])
            result = hire_staff_from_save(save, negotiation["id"])
            self.assertEqual(result["status"], "applied")
            write_save(save_path, save)

            saved = load_save(save_path)
            report = staff_team_report(self.plain, saved, "GSW")
            hired = next(slot for slot in report["gameplay_staff_slots"] if slot["slot"] == "performance_lead")
            self.assertEqual(hired["name"], candidate["name"])
            self.assertIn("effect_summary", hired)
            self.assertIn("effect_rows", hired)
            self.assertTrue(any(row["label"] == "Availability" for row in hired["effect_rows"]))
            self.assertEqual(self.plain["gameplay_staff_slots"], original_canonical_staff)
            self.assertEqual(len([slot for slot in saved["staff_slots"] if slot["team_id"] == "team_gsw"]), 6)

    def test_staff_market_is_grade_sorted_and_staff_pending_count_hidden(self):
        with tempfile.TemporaryDirectory() as tmp:
            save_path = Path(tmp) / "league_save.json"
            save = create_league_save(ROOT, self.plain, "GSW", save_path, seed=12)
            market = staff_market_report(self.plain, save, slot=None, limit=25)
            grades = [float(candidate["grade"]) for candidate in market["candidates"]]
            self.assertEqual(grades, sorted(grades, reverse=True))
            save.setdefault("pending_staff_negotiations", []).append({"id": "old_staff_offer", "accepted": True})
            write_save(save_path, save)
            status = save_status(ROOT, self.plain, save_path)
            self.assertEqual(status["pending_counts"]["staff"], 0)

    def test_interest_score_rewards_better_money_and_years(self):
        weak = offer_interest_score(4.0, 8.0, 1, 3, 45.0)
        strong = offer_interest_score(8.5, 8.0, 3, 3, 60.0)
        self.assertLess(weak, strong)
        self.assertGreaterEqual(strong, 75)

    def test_staff_fire_interim_budget_and_market_depth(self):
        with tempfile.TemporaryDirectory() as tmp:
            save_path = Path(tmp) / "league_save.json"
            save = create_league_save(ROOT, self.plain, "GSW", save_path, seed=8)
            budgets = [staff_budget_for_team(self.plain, team["id"]) for team in self.plain["teams"]]
            self.assertGreater(max(budgets) - min(budgets), 8)
            self.assertLess(sum(budgets) / len(budgets), 38)
            original = next(slot for slot in save["staff_slots"] if slot["team_id"] == "team_gsw" and slot["slot"] == "head_coach")
            first_fire = fire_staff_from_save(save, "team_gsw", "head_coach")
            interim = first_fire["interim_staff"]
            self.assertEqual(first_fire["status"], "applied")
            self.assertEqual(interim["status"], "interim_staff_vacancy")
            self.assertNotEqual(interim["name"], original["name"])
            self.assertEqual(len([staff for staff in save["staff_slots"] if staff["team_id"] == "team_gsw" and staff["slot"] == "head_coach"]), 1)

            snapshot = staff_budget_snapshot(self.plain, save, "team_gsw", "head_coach", 0)
            self.assertTrue(snapshot["current_slot_is_interim"])
            self.assertGreater(snapshot["interim_replacement_credit_millions"], 0)
            capped_snapshot = staff_budget_snapshot(self.plain, save, "team_gsw", "head_coach", snapshot["max_offer_millions"])
            self.assertAlmostEqual(capped_snapshot["available_after_offer_millions"], 0.0, places=2)
            ai_staff = simulate_ai_staff_changes(self.plain, save, "2025-10-01", "2025-10-31", seed=8, limit=8)
            self.assertTrue(any(item["team_id"] == "team_gsw" and item["slot"] == "head_coach" for item in ai_staff["recommendations"]))
            candidate_ids = [item["candidate_id"] for item in ai_staff["recommendations"]]
            self.assertEqual(len(candidate_ids), len(set(candidate_ids)))

            market = staff_market_report(self.plain, save, slot="head_coach", limit=20)
            grades = [float(candidate["grade"]) for candidate in market["candidates"]]
            self.assertEqual(len(market["candidates"]), 20)
            employed_grades = [staff_grade(staff) for staff in save["staff_slots"] if staff["team_id"] != "team_gsw" and staff["slot"] == "head_coach"]
            self.assertLess(sum(grades) / len(grades), sum(employed_grades) / len(employed_grades))
            self.assertTrue(any(candidate["name"] == original["name"] for candidate in market["candidates"]))
            generated_grades = [
                float(candidate["grade"])
                for candidate in market["candidates"]
                if str(candidate.get("id", "")).startswith("staff_market_")
                and not str(candidate.get("id", "")).startswith("staff_market_former")
            ]
            self.assertTrue(generated_grades)
            self.assertLessEqual(max(generated_grades), 84)

            negotiation = negotiate_staff_hire(self.plain, save, market["candidates"][0]["id"], "GSW", "head_coach", seed=8, offer_salary_millions=999)
            self.assertTrue(negotiation["offer_capped_by_budget"])
            self.assertLessEqual(negotiation["team_offer"]["annual_salary_millions"], negotiation["max_offer_millions"])
            self.assertNotEqual(negotiation["decision"], "reject_budget")

            second_fire = fire_staff_from_save(save, "team_gsw", "head_coach")
            self.assertEqual(second_fire["status"], "applied")
            self.assertNotEqual(second_fire["interim_staff"]["id"], interim["id"])
            self.assertNotEqual(second_fire["interim_staff"]["name"], interim["name"])

    def test_ai_staff_hire_logs_one_event_without_duplicate_news(self):
        with tempfile.TemporaryDirectory() as tmp:
            save_path = Path(tmp) / "league_save.json"
            save = create_league_save(ROOT, self.plain, "GSW", save_path, seed=24)
            candidate = staff_market_report(self.plain, save, slot="defensive_coordinator", limit=1)["candidates"][0]
            payload = {
                "through_date": "2026-02-05",
                "recommendations": [
                    {
                        "id": "staff_rec_det",
                        "team_id": "team_det",
                        "team_abbrev": "DET",
                        "slot": "defensive_coordinator",
                        "candidate_id": candidate["id"],
                        "candidate": candidate,
                        "recommended_offer": {
                            "annual_salary_millions": candidate["asking_salary_millions"],
                            "years": candidate["asking_years"],
                        },
                    }
                ],
            }
            result = apply_ai_staff_recommendations(self.plain, save, payload, seed=24)
            self.assertEqual(result["applied_count"], 1)
            headlines = [item["headline"] for item in save.get("news_items", []) if "DET hires" in item.get("headline", "")]
            self.assertEqual(len(headlines), 1)

    def test_save_user_actions_ai_processing_morale_and_social(self):
        with tempfile.TemporaryDirectory() as tmp:
            save_path = Path(tmp) / "league_save.json"
            create_league_save(ROOT, self.plain, "GSW", save_path, seed=6)
            preview = propose_trade_to_save(self.plain, save_path, "GSW", "WAS", ["FROM:player:Seth Curry"], seed=2, store=False)
            self.assertEqual(preview["status"], "evaluated")
            self.assertEqual(len(load_save(save_path).get("pending_trade_proposals", [])), 0)
            proposal = propose_trade_to_save(self.plain, save_path, "GSW", "WAS", ["FROM:player:Seth Curry"], seed=2)
            self.assertEqual(proposal["status"], "stored")
            actions = pending_actions_view(self.plain, save_path)
            self.assertEqual(actions["pending_counts"]["trades"], 1)

            press = hold_press_conference(self.plain, save_path, "GSW", "early losing streak", "accountable", seed=2)
            self.assertEqual(press["tone"], "accountable")
            self.assertIn("before", press["confidence_metrics"])
            self.assertIn("after", press["confidence_metrics"])
            self.assertGreater(press["confidence_metrics"]["after"]["team_morale"], press["confidence_metrics"]["before"]["team_morale"])
            self.assertGreaterEqual(press["confidence_metrics"]["after"]["team_morale"] - press["confidence_metrics"]["before"]["team_morale"], 3.0)
            morale = morale_report(self.plain, save_path, "GSW")
            self.assertGreater(morale["team_morale"]["overall"], 57.5)
            social = social_feed_view(self.plain, save_path, "GSW", limit=5)
            self.assertGreaterEqual(social["item_count"], 1)

            saved = load_save(save_path)
            saved["state"] = {"current_date": "2026-01-15", "phase": "regular_season", "legal_actions": ["trades", "advance"]}
            write_save(save_path, saved)
            advance_save(ROOT, self.plain, save_path, to_date="2026-01-16", seed=6)
            processed = process_ai_actions(self.plain, save_path, seed=6, execute=False)
            self.assertGreaterEqual(processed["processed_count"], 1)
            saved = load_save(save_path)
            self.assertTrue(any(action["action_type"] == "trade_recommendations" for action in saved["pending_ai_actions"]))

    def test_press_answers_are_question_specific(self):
        answers = contextual_press_answers(
            "rotation controversy",
            "SAC",
            "Keegan Murray",
            random.Random("press-role-test"),
            question="Whose role gets squeezed if this rotation change sticks?",
        )
        self.assertEqual(len(answers), 4)
        self.assertEqual(len({answer["line"] for answer in answers}), 4)
        text = " ".join(answer["line"].lower() for answer in answers)
        self.assertTrue(any(word in text for word in ["minutes", "role", "rotation"]))
        impact = press_impact("trade pressure", "accountable", seed=44)
        self.assertTrue(any(abs(value) >= 3.0 for value in impact.values()))

    def test_playoff_and_offseason_scaffolds_use_save_state(self):
        with tempfile.TemporaryDirectory() as tmp:
            save_path = Path(tmp) / "league_save.json"
            create_league_save(ROOT, self.plain, "PHX", save_path, seed=7)
            advance_save(ROOT, self.plain, save_path, to_date="2025-10-25", seed=7)
            picture = playoff_picture(self.plain, save_path)
            self.assertIn("East", picture["picture"])
            self.assertIn("West", picture["picture"])
            bracket = start_playoffs(self.plain, save_path, seed=7)
            self.assertEqual(bracket["round"], "first_round")
            self.assertGreaterEqual(len(bracket["series"]), 4)
            completed = simulate_playoff_round(self.plain, save_path, seed=7)
            self.assertGreater(len(completed["completed_series"]), 0)
            order = run_draft_lottery(self.plain, save_path, year="2027", seed=7)
            self.assertEqual(order["pick_count"], 60)
            status = offseason_status(self.plain, save_path)
            self.assertIn("2027", status["draft_orders"])

    def test_rollover_generates_future_schedule_and_future_games_simulate(self):
        with tempfile.TemporaryDirectory() as tmp:
            save_path = Path(tmp) / "league_save.json"
            create_league_save(ROOT, self.plain, "GSW", save_path, seed=8)
            rollover = complete_offseason_and_rollover(ROOT, self.plain, save_path, seed=8)
            self.assertEqual(rollover["to_season"], "2026-27")
            self.assertEqual(rollover["generated_game_count"], 1235)
            self.assertEqual(rollover["offseason_changes"]["expired_free_agents"] > 0, True)
            result = advance_save(ROOT, self.plain, save_path, to_date="2026-10-21", seed=8)
            self.assertEqual(result["games_simulated"], 2)
            saved = load_save(save_path)
            self.assertEqual(saved["meta"]["season"], "2026-27")
            self.assertEqual(saved["state"]["phase"], "regular_season")
            self.assertGreaterEqual(len(saved["incoming_rookies"]), 60)
            self.assertGreaterEqual(len(saved["generated_players"]), 60)
            self.assertGreater(len(saved.get("free_agent_player_ids", [])), 0)
            self.assertTrue(saved.get("year_reviews"))
            self.assertTrue(saved["year_reviews"][-1].get("players"))
            self.assertIn("retirement_reports", saved)
            active = canonical_with_save(self.plain, saved)
            roster_counts = Counter(player.get("team_id") for player in active["players"] if player.get("team_id"))
            self.assertGreaterEqual(min(roster_counts.values()), 14)
            self.assertTrue(all(game["game_id"].startswith("sim_game_2026-27") for game in saved["game_results"]))

    def test_manual_contract_overrides_classify_uncertainty(self):
        players = {player.normalized_name: player for player in self.universe.players}
        contracts = {contract.player_id: contract for contract in self.universe.contracts}
        for name in ["mason plumlee", "mike conley", "svi mykhailiuk", "bub carrington", "cam whitmore"]:
            contract = contracts[players[name].id]
            self.assertEqual(contract.status, "manual_research_pending")
            self.assertIn("src_manual_overrides_2025_26", contract.source_ids)

    def test_health_profiles_states_and_startup_injuries_are_exported(self):
        self.assertEqual(len(self.universe.player_health_profiles), len(self.universe.players))
        self.assertEqual(len(self.universe.player_health_states), len(self.universe.players))
        players = {player.normalized_name: player for player in self.universe.players}
        states = {state.player_id: state for state in self.universe.player_health_states}
        self.assertEqual(len(self.universe.injury_events), 3)
        for name in ["jayson tatum", "tyrese haliburton", "damian lillard"]:
            state = states[players[name].id]
            self.assertEqual(state.availability_status, "out")
            self.assertEqual(state.return_date, "2026-07-01")
            self.assertIsNotNone(state.current_injury_id)
        report = health_player_report(self.plain, "Jayson Tatum")
        self.assertEqual(report["state"]["availability_status"], "out")

    def test_health_team_report_includes_performance_staff_context(self):
        report = health_team_report(self.plain, "GSW")
        self.assertEqual(report["team"]["abbrev"], "GSW")
        self.assertIn("injury_risk_multiplier", report["performance_staff"])
        self.assertGreater(len(report["players"]), 5)
        modifiers = performance_staff_modifiers(self.plain, "team_gsw")
        self.assertLessEqual(modifiers["injury_risk_multiplier"], 1.08)
        self.assertGreaterEqual(modifiers["injury_risk_multiplier"], 0.88)

    def test_health_simulation_is_deterministic_and_quota_guided(self):
        first = simulate_health(ROOT, self.plain, "2025-10-21", "2026-04-12", seed=1)
        second = simulate_health(ROOT, self.plain, "2025-10-21", "2026-04-12", seed=1)
        self.assertEqual(first, second)
        config = load_injury_model_config(ROOT)
        self.assertGreaterEqual(config["severity_bands"]["day_to_day"]["min_per_season"], 350)
        self.assertGreater(config["severity_bands"]["day_to_day"]["weight"], config["severity_bands"]["medium"]["weight"])
        self.assertGreaterEqual(config["tuning"]["base_player_game_injury_rate"], 0.02)
        for severity, band in config["severity_bands"].items():
            self.assertGreaterEqual(first["severity_counts"][severity], band["min_per_season"])
            self.assertLessEqual(first["severity_counts"][severity], band["max_per_season"])
        for body_area, quota in config["body_area_quota_ranges"].items():
            self.assertGreaterEqual(first["body_area_counts"][body_area], quota["min_per_season"])
            self.assertLessEqual(first["body_area_counts"][body_area], quota["max_per_season"])

    def test_monthly_development_is_trait_level_and_deterministic(self):
        first = advance_development(self.plain, "2025-11", seed=4)
        second = advance_development(self.plain, "2025-11", seed=4)
        self.assertEqual(first, second)
        players = {player["normalized_name"]: player for player in self.plain["players"]}
        kon = players["kon knueppel"]
        lebron = players["lebron james"]
        kon_event = next(event for event in first["events"] if event["player_id"] == kon["id"])
        lebron_event = next(event for event in first["events"] if event["player_id"] == lebron["id"])
        self.assertGreater(sum(kon_event["trait_deltas"].values()), 0)
        self.assertTrue(all(abs(delta) <= 0.12 for delta in lebron_event["trait_deltas"].values()))
        self.assertIn("stamina_cardio", kon_event["trait_deltas"])

    def test_gm_transaction_context_exports_core_records(self):
        self.assertEqual(len(self.universe.front_office_profiles), len(self.universe.teams))
        self.assertEqual(len(self.universe.team_strategic_states), len(self.universe.teams))
        self.assertEqual(len(self.universe.player_asset_valuations), len(self.universe.players))
        self.assertEqual(len(self.universe.player_contract_market_profiles), len(self.universe.players))
        self.assertEqual(len(self.universe.player_contract_preferences), len(self.universe.players))
        self.assertEqual(len(self.universe.extension_candidates), len(self.universe.players))
        self.assertGreaterEqual(len(self.universe.free_agent_candidates), 150)
        self.assertGreaterEqual(len(self.universe.trade_block_entries), 40)

    def test_team_strategy_reflects_phase_pressure_and_personality(self):
        states = {team.abbrev: next(state for state in self.universe.team_strategic_states if state.team_id == team.id) for team in self.universe.teams}
        front_offices = {profile.team_id: profile for profile in self.universe.front_office_profiles}
        teams = {team.abbrev: team for team in self.universe.teams}
        self.assertIn("contending", states["GSW"].phase)
        self.assertIn("contending", states["PHX"].phase)
        self.assertEqual(states["OKC"].phase, "contending_with_future_upside")
        self.assertIn(states["WAS"].phase, {"developing", "rebuilding"})
        self.assertGreater(states["GSW"].pressure, states["WAS"].pressure)
        self.assertGreater(front_offices[teams["OKC"].id].asset_discipline, front_offices[teams["GSW"].id].asset_discipline)

    def test_player_asset_valuation_rewards_portability_and_flags_contract_risk(self):
        players = {player.normalized_name: player for player in self.universe.players}
        values = {valuation.player_id: valuation for valuation in self.universe.player_asset_valuations}
        caruso = values[players["alex caruso"].id]
        giddey = values[players["josh giddey"].id]
        davis = values[players["anthony davis"].id]
        kon = values[players["kon knueppel"].id]
        jaren = values[players["jaren jackson jr"].id]
        self.assertGreater(caruso.player_value, giddey.player_value)
        self.assertGreater(caruso.portability, giddey.portability + 25)
        self.assertLess(davis.contract_surplus, 0)
        self.assertGreater(davis.health_risk, 8)
        self.assertGreater(kon.development_upside, 8)
        self.assertGreater(kon.contract_surplus, 20)
        self.assertGreater(jaren.player_value, 58)
        self.assertGreater(jaren.portability, 70)

    def test_trade_block_and_find_trade_are_explainable(self):
        block = trade_block_report(self.plain, "WAS")
        self.assertGreater(block["entry_count"], 0)
        self.assertTrue(any(entry["name"] == "Anthony Davis" for entry in block["entries"]))
        report = find_trade(self.plain, "Anthony Davis", "WAS", limit=2, seed=2)
        self.assertGreater(report["candidate_count"], 0)
        self.assertIn("summary", report["candidates"][0])
        self.assertEqual(len(report["candidates"][0]["evaluations"]), 2)

    def test_trade_finder_preserves_untouchables_and_bounded_multi_asset_packages(self):
        self.assertEqual(find_trade(self.plain, "Stephen Curry", "GSW", limit=4, seed=2)["candidate_count"], 0)
        self.assertEqual(find_trade(self.plain, "Victor Wembanyama", "SAS", limit=4, seed=2)["candidate_count"], 0)
        movable = find_trade(self.plain, "Tidjane Salaun", "PHX", limit=8, seed=9)
        self.assertGreater(movable["candidate_count"], 0)
        self.assertTrue(
            any(
                asset.get("kind") == "pick" and "R2" in str(asset.get("label"))
                for candidate in movable["candidates"]
                for asset in candidate["proposal"]["from_assets"]
            )
        )
        barnes = find_trade(self.plain, "Scottie Barnes", "TOR", limit=8, seed=2)
        self.assertTrue(barnes["candidates"])
        incoming_packages = [candidate["proposal"]["to_assets"] for candidate in barnes["candidates"]]
        self.assertTrue(any(len(assets) > 1 for assets in incoming_packages))
        self.assertTrue(all(len(assets) <= 4 for assets in incoming_packages))
        self.assertTrue(all(candidate["legality"]["status"] == "legal" for candidate in barnes["candidates"]))
        gsw_pick = next(pick for pick in self.plain["draft_picks"] if pick["current_owner_team_id"] == "team_gsw")
        package = find_trade_for_assets(
            self.plain,
            "GSW",
            [{"kind": "player", "value": "Seth Curry"}, {"kind": "pick", "value": gsw_pick["id"]}],
            "GSW",
            limit=4,
            seed=2,
        )
        self.assertEqual(package["mode"], "shop_package")
        self.assertGreater(package["candidate_count"], 0)
        self.assertTrue(all(candidate["legality"]["status"] == "legal" for candidate in package["candidates"]))

    def test_trade_evaluation_uses_team_context_and_legality(self):
        legal = evaluate_trade(
            self.plain,
            "WAS",
            "SAC",
            [{"kind": "player", "value": "Anthony Davis"}],
            [{"kind": "player", "value": "Zach LaVine"}, {"kind": "pick", "value": "pick_2026-1-7-sac"}],
            seed=2,
        )
        self.assertEqual(legal["legality"]["status"], "legal")
        decisions = {evaluation["perspective_team_id"]: evaluation["decision"] for evaluation in legal["evaluations"]}
        self.assertEqual(decisions["team_was"], "accept")
        self.assertEqual(decisions["team_sac"], "reject")
        self.assertTrue(all("acceptance_score" in evaluation for evaluation in legal["evaluations"]))
        self.assertIn("asset_details", legal["value_breakdown"]["to_team_receives"])
        illegal = evaluate_trade(
            self.plain,
            "WAS",
            "GSW",
            [{"kind": "player", "value": "Anthony Davis"}],
            [{"kind": "player", "value": "Seth Curry"}],
            seed=2,
        )
        self.assertEqual(illegal["legality"]["status"], "illegal")
        self.assertTrue(any("salary" in issue for issue in illegal["legality"]["issues"]))

    def test_trade_package_value_discounts_depth_without_destination_minutes(self):
        active = with_transaction_context(self.plain)
        values = {item["player_id"]: item for item in active["player_asset_valuations"]}
        gsw_players = sorted(
            [player for player in active["players"] if player.get("team_id") == "team_gsw"],
            key=lambda player: float(values[player["id"]]["player_value"]),
        )[:3]
        self.assertGreaterEqual(len(gsw_players), 2)
        assets = [{"kind": "player", "id": player["id"], "label": player["name"]} for player in gsw_players[:3]]
        raw_value = sum(float(values[player["id"]]["player_value"]) for player in gsw_players[:3])
        destination_value = package_value_for_team(active, assets, "team_bos")
        self.assertLess(destination_value, raw_value)

    def test_stepien_guardrail_only_counts_own_firsts(self):
        synthetic = {
            "teams": [
                {"id": "team_a", "abbrev": "AAA"},
                {"id": "team_b", "abbrev": "BBB"},
            ],
            "draft_picks": [
                {"id": "own_2026", "season": "2026", "round": 1, "original_team_id": "team_a", "current_owner_team_id": "team_a"},
                {"id": "acquired_2027", "season": "2027", "round": 1, "original_team_id": "team_b", "current_owner_team_id": "team_a"},
                {"id": "own_2027", "season": "2027", "round": 1, "original_team_id": "team_a", "current_owner_team_id": "team_a"},
            ],
        }
        acquired_pair = TradeProposal(
            id="proposal_acquired_pair",
            date="2026-06-25",
            from_team_id="team_a",
            to_team_id="team_b",
            from_assets=[{"kind": "pick", "id": "own_2026"}, {"kind": "pick", "id": "acquired_2027"}],
            to_assets=[],
            status="test",
            source_ids=[],
            notes="test",
        )
        own_pair = TradeProposal(
            id="proposal_own_pair",
            date="2026-06-25",
            from_team_id="team_a",
            to_team_id="team_b",
            from_assets=[{"kind": "pick", "id": "own_2026"}, {"kind": "pick", "id": "own_2027"}],
            to_assets=[],
            status="test",
            source_ids=[],
            notes="test",
        )
        self.assertEqual(stepien_guardrail_issues(synthetic, acquired_pair), [])
        self.assertTrue(stepien_guardrail_issues(synthetic, own_pair))

    def test_ai_trade_simulation_and_save_ledger_are_deterministic(self):
        first = simulate_ai_trades(self.plain, "2025-12-01", "2026-02-01", seed=5, limit=3)
        second = simulate_ai_trades(self.plain, "2025-12-01", "2026-02-01", seed=5, limit=3)
        self.assertEqual(first, second)
        self.assertGreater(first["proposal_count"], 0)
        proposal = first["proposals"][0]
        with tempfile.TemporaryDirectory() as tmp:
            save_path = Path(tmp) / "save.json"
            save_path.write_text(json.dumps({"pending_trade_proposals": [proposal], "transaction_logs": []}), encoding="utf-8")
            result = apply_trade_to_save(save_path, proposal["proposal"]["id"])
            self.assertEqual(result["status"], "applied")
            saved = json.loads(save_path.read_text(encoding="utf-8"))
            self.assertEqual(len(saved["transaction_logs"]), 1)

    def test_ai_trade_processing_skips_overlapping_bundle_assets(self):
        with tempfile.TemporaryDirectory() as tmp:
            save_path = Path(tmp) / "league_save.json"
            save = create_league_save(ROOT, self.plain, "GSW", save_path, seed=6)
            seth = next(player for player in self.plain["players"] if player["name"] == "Seth Curry")
            proposals = []
            for idx, team_id in enumerate(["team_was", "team_bkn"], start=1):
                proposal = {
                    "proposal": {
                        "id": f"overlap_trade_{idx}",
                        "from_team_id": "team_gsw",
                        "to_team_id": team_id,
                        "from_assets": [{"kind": "player", "id": seth["id"], "label": "Seth Curry"}],
                        "to_assets": [],
                    },
                    "legality": {"status": "legal", "issues": []},
                    "accepted_by_all": True,
                    "evaluations": [],
                }
                proposals.append(proposal)
            save["pending_ai_actions"] = [
                {
                    "id": "overlap_bundle",
                    "date": "2026-01-20",
                    "action_type": "trade_recommendations",
                    "status": "recommendation_pending_review",
                    "payload": {"proposals": proposals},
                }
            ]
            write_save(save_path, save)
            result = process_ai_actions(self.plain, save_path, seed=6, execute=True, limit=1)
            applied_outcome = result["processed"][0]
            self.assertEqual(applied_outcome["applied_candidate_count"], 1)
            saved = load_save(save_path)
            self.assertEqual(len(saved["transaction_logs"]), 1)
            self.assertIn(saved["roster_overrides"][seth["id"]], {"team_was", "team_bkn"})

    def test_contract_market_profiles_price_roles_without_low_minute_star_leakage(self):
        sga = contract_market_report(self.plain, "Shai Gilgeous-Alexander")
        caruso = contract_market_report(self.plain, "Alex Caruso")
        tyty = contract_market_report(self.plain, "TyTy Washington Jr.")
        lebron = contract_market_report(self.plain, "LeBron James")
        self.assertEqual(sga["market_profile"]["role_tier"], "franchise_anchor")
        self.assertGreaterEqual(sga["market_profile"]["asking_aav"], 45_000_000)
        self.assertEqual(caruso["market_profile"]["role_tier"], "elite_specialist")
        self.assertLess(caruso["market_profile"]["asking_aav"], sga["market_profile"]["asking_aav"])
        self.assertNotEqual(tyty["market_profile"]["role_tier"], "franchise_anchor")
        self.assertLessEqual(tyty["market_profile"]["asking_aav"], 16_000_000)
        self.assertLessEqual(lebron["market_profile"]["preferred_years"], 2)

    def test_extension_and_free_agency_negotiations_are_deterministic_and_explainable(self):
        first = negotiate_extension(self.plain, "Stephen Curry", "GSW", seed=4, max_rounds=4)
        second = negotiate_extension(self.plain, "Stephen Curry", "GSW", seed=4, max_rounds=4)
        self.assertEqual(first, second)
        self.assertTrue(first["accepted"])
        self.assertEqual(first["decision"]["decision"], "accept")
        self.assertGreater(len(first["negotiation"]["offers"]), 0)
        cj = negotiate_extension(self.plain, "CJ McCollum", "ATL", seed=4, max_rounds=4)
        self.assertFalse(cj["accepted"])
        self.assertIsNone(cj["decision"])
        self.assertIn(cj["negotiation"]["status"], {"original_contract_shorter_than_three_years", "not_in_final_two_contract_seasons"})
        phx_offer = evaluate_signing(self.plain, "LeBron James", "PHX", 2, 35, seed=3)
        was_offer = evaluate_signing(self.plain, "LeBron James", "WAS", 2, 35, seed=3)
        self.assertTrue(phx_offer["accepted_by_all"])
        self.assertEqual(was_offer["legality"]["status"], "manual_review_required")

    def test_free_agency_reports_simulation_and_contract_save_ledger(self):
        free_agents = free_agents_report(self.plain, "PHX", position="PG")
        self.assertGreater(free_agents["candidate_count"], 0)
        free_agent_active = json.loads(json.dumps(self.plain))
        for key in ["player_contract_market_profiles", "player_contract_preferences", "extension_candidates", "free_agent_candidates"]:
            free_agent_active.pop(key, None)
        next(player for player in free_agent_active["players"] if player["name"] == "Seth Curry")["team_id"] = None
        self.assertGreater(free_agents_report(free_agent_active, "GSW")["candidate_count"], 0)
        extensions = extension_candidates_report(self.plain, "GSW")
        self.assertTrue(any(candidate["name"] == "Stephen Curry" for candidate in extensions["candidates"]))
        first = simulate_free_agency(self.plain, "2026-07-01", "2026-07-08", seed=2, limit=2)
        second = simulate_free_agency(self.plain, "2026-07-01", "2026-07-08", seed=2, limit=2)
        self.assertEqual(first, second)
        self.assertEqual(first["negotiation_count"], 2)
        pending = first["negotiations"][0]
        with tempfile.TemporaryDirectory() as tmp:
            save_path = Path(tmp) / "save.json"
            save = create_league_save(ROOT, self.plain, "GSW", save_path, seed=19)
            save["pending_contract_negotiations"] = [pending]
            write_save(save_path, save)
            result = apply_contract_to_save(save_path, pending["negotiation"]["id"])
            self.assertEqual(result["status"], "applied")
            saved = json.loads(save_path.read_text(encoding="utf-8"))
            self.assertEqual(len(saved["transaction_logs"]), 1)
            self.assertTrue(any(item.get("kind") == "free_agent_signing" for item in saved.get("news_items", [])))
            self.assertGreaterEqual(len(saved.get("social_feed", [])), 1)

    def test_free_agency_day_market_initializes_ai_offers_and_limits(self):
        self.assertEqual(free_agency_user_offer_limit(1), 3)
        self.assertEqual(free_agency_user_offer_limit(2), 6)
        self.assertIsNone(free_agency_user_offer_limit(3))
        with tempfile.TemporaryDirectory() as tmp:
            save_path = Path(tmp) / "league_save.json"
            save = create_league_save(ROOT, self.plain, "GSW", save_path, seed=17)
            save["state"]["phase"] = "free_agency"
            save["state"]["current_date"] = "2026-07-01"
            save["free_agent_player_ids"] = [
                candidate["player_id"] for candidate in self.plain["free_agent_candidates"][:12]
            ]
            for player_id in save["free_agent_player_ids"]:
                save.setdefault("roster_overrides", {})[player_id] = None
            write_save(save_path, save)
            initialized = initialize_free_agency_market(self.plain, save_path, "GSW", seed=17)
            state = initialized["free_agency_state"]
            self.assertEqual(state["day"], 1)
            self.assertEqual(state["re_signing_status"], "active")
            self.assertEqual(state["ai_days_processed"], [])
            state["re_signing_status"] = "completed"
            initialized["free_agency_state"] = state
            write_save(save_path, initialized)
            initialized = initialize_free_agency_market(self.plain, save_path, "GSW", seed=17)
            state = initialized["free_agency_state"]
            self.assertIn(f"{state['season']}:1", state["ai_days_processed"])
            self.assertGreater(len(initialized.get("free_agent_offers", [])), 0)
            self.assertTrue(all(offer["source"] == "ai" for offer in initialized["free_agent_offers"]))

    def test_future_second_round_picks_are_tradeable_scaffold_assets(self):
        active = with_transaction_context(self.plain)
        future_seconds = [
            pick for team in active["teams"]
            for pick in tradeable_picks_for_team(active, team["id"])
            if str(pick.get("season")) > "2026"
            and int(pick.get("round") or 0) == 2
        ]
        self.assertGreaterEqual(len(future_seconds), 30)
        self.assertTrue(any(pick.get("status") == "inferred_future_second_round_scaffold" for pick in future_seconds))

    def test_future_pick_values_reflect_timeline_uncertainty_and_dedupe_display_assets(self):
        active = with_transaction_context(self.plain)
        sac = next(team for team in active["teams"] if team["abbrev"] == "SAC")
        picks = tradeable_picks_for_team(active, sac["id"])
        future_seconds = [pick for pick in picks if str(pick.get("season")) > "2026" and int(pick.get("round") or 0) == 2]
        self.assertGreaterEqual(len(future_seconds), 6)
        label_keys = [
            (
                pick.get("season"),
                pick.get("round"),
                pick.get("original_team_id"),
                pick.get("current_owner_team_id"),
                pick.get("protections") or pick.get("protection_summary") or "",
            )
            for pick in picks
        ]
        self.assertEqual(len(label_keys), len(set(label_keys)))
        own_first_values = {
            str(pick.get("season")): pick_asset_value(pick, "neutral")
            for pick in picks
            if int(pick.get("round") or 0) == 1
            and pick.get("original_team_id") == sac["id"]
            and str(pick.get("season")) >= "2027"
        }
        self.assertGreater(own_first_values["2027"], own_first_values["2032"])
        self.assertGreater(len(set(own_first_values.values())), 3)

    def test_rare_drama_deadline_window_does_not_crash(self):
        with tempfile.TemporaryDirectory() as tmp:
            save_path = Path(tmp) / "league_save.json"
            save = create_league_save(ROOT, self.plain, "SAC", save_path, seed=1)
            maybe_queue_rare_drama(save, self.plain, "2025-11-01", "2026-02-05", seed=1)
            self.assertTrue(save.get("rare_drama_triggered"))
            self.assertTrue(any(item.get("kind") == "rare_drama" for item in save.get("pending_press_events", [])))

    def test_effective_age_is_idempotent_for_save_aware_canonical(self):
        with tempfile.TemporaryDirectory() as tmp:
            save_path = Path(tmp) / "league_save.json"
            save = create_league_save(ROOT, self.plain, "GSW", save_path, seed=18)
            save["meta"]["season"] = "2027-28"
            save["meta"]["season_start_year"] = 2027
            active_once = canonical_with_save(self.plain, save)
            curry_once = next(player for player in active_once["players"] if player["name"] == "Stephen Curry")
            active_twice = canonical_with_save(active_once, save)
            curry_twice = next(player for player in active_twice["players"] if player["name"] == "Stephen Curry")
            self.assertEqual(curry_once["age"], curry_twice["age"])

    def test_free_agency_cap_checks_use_upcoming_contract_season(self):
        with tempfile.TemporaryDirectory() as tmp:
            save_path = Path(tmp) / "league_save.json"
            save = create_league_save(ROOT, self.plain, "GSW", save_path, seed=20)
            save["state"]["phase"] = "free_agency"
            save["state"]["current_date"] = "2026-07-01"
            save.setdefault("generated_players", []).append(
                {
                    "id": "generated_cap_anchor",
                    "name": "Cap Anchor",
                    "normalized_name": "cap anchor",
                    "team_id": "team_gsw",
                    "team_abbrev": "GSW",
                    "position": "C",
                    "age": 25,
                    "minutes_projection": 1,
                }
            )
            save.setdefault("roster_overrides", {})["generated_cap_anchor"] = "team_gsw"
            save.setdefault("contract_overrides", {})["generated_cap_anchor"] = {
                "team_id": "team_gsw",
                "seasons": [{"season": "2026-27", "salary": 240_000_000}],
                "status": "test_future_contract",
                "original_contract_years": 1,
                "signed_season": "2026-27",
            }
            active = canonical_with_save(self.plain, save)
            self.assertEqual(contract_start_season_for_signing(save), "2026-27")
            cap = team_cap_summary(active, save, "team_gsw", season="2026-27")
            self.assertLess(cap["hard_cap_space_millions"], 0)
            self.assertFalse(signing_cap_check(active, save, "GSW", 10.0)["ok"])
            self.assertTrue(signing_cap_check(active, save, "GSW", 1.9)["ok"])

    def test_staff_contract_expiry_creates_interim_and_market_candidate(self):
        with tempfile.TemporaryDirectory() as tmp:
            save_path = Path(tmp) / "league_save.json"
            save = create_league_save(ROOT, self.plain, "GSW", save_path, seed=22)
            head = next(slot for slot in save["staff_slots"] if slot["team_id"] == "team_gsw" and slot["slot"] == "head_coach")
            old_name = head["name"]
            head["contract"]["years_remaining"] = 1
            save["state"]["current_date"] = "2026-10-01"
            age_staff_contracts(save)
            new_head = next(slot for slot in save["staff_slots"] if slot["team_id"] == "team_gsw" and slot["slot"] == "head_coach")
            self.assertEqual(new_head["status"], "interim_staff_vacancy")
            self.assertNotEqual(new_head["name"], old_name)
            self.assertTrue(any(staff.get("name") == old_name and staff.get("market_status") == "expired_contract" for staff in save.get("former_staff", [])))

    def test_box_score_influence_sort_key_values_all_around_lines(self):
        scorer = {"points": 28, "rebounds": 2, "assists": 1, "steals": 0, "blocks": 0, "turnovers": 4}
        all_around = {"points": 17, "rebounds": 10, "assists": 9, "steals": 2, "blocks": 1, "turnovers": 1}
        self.assertGreater(box_score_influence(all_around), box_score_influence(scorer))

    def test_extension_eligibility_uses_original_term_and_active_save_season(self):
        extensions = {candidate["name"]: candidate for candidate in extension_candidates_report(self.plain, "GSW")["candidates"]}
        self.assertTrue(extensions["Stephen Curry"]["eligible"])
        self.assertEqual(extensions["Stephen Curry"]["eligibility_status"], "eligible_final_two_seasons")
        self.assertFalse(extensions["Jimmy Butler III"]["eligible"])
        contract = {"_active_season": "2026-27", "seasons": [{"season": "2025-26", "salary": 10}, {"season": "2026-27", "salary": 20}]}
        self.assertEqual(current_salary(contract), 20)
        rookie_projection = {"status": "save_state_contract_override", "_active_season": "2025-26", "seasons": [{"season": "2026-27", "salary": 3_100_000}]}
        self.assertEqual(current_salary(rookie_projection), 3_100_000)
        expired_contract = {"_active_season": "2026-27", "seasons": [{"season": "2025-26", "salary": 5_000_000}]}
        self.assertIsNone(current_salary(expired_contract))

    def test_rotation_recommendation_anchors_coach_adjusted_minutes(self):
        curry = next(player for player in self.plain["players"] if player["name"] == "Stephen Curry")
        with tempfile.TemporaryDirectory() as tmp:
            save_path = Path(tmp) / "league_save.json"
            save = create_league_save(ROOT, self.plain, "GSW", save_path, seed=5)
            save["rotation_recommendations"][curry["id"]] = {
                "player_id": curry["id"],
                "team_id": curry["team_id"],
                "target_minutes": 24.0,
                "coach_commitment": 0.68,
            }
            active = canonical_with_save(self.plain, save)
            roster = [player for player in active["players"] if player["team_id"] == "team_gsw"]
            adjusted = next(player for player in roster if player["id"] == curry["id"])
            self.assertGreaterEqual(adjusted["minutes_projection"], 24.0)
            self.assertLessEqual(adjusted["minutes_projection"], 27.0)
            self.assertAlmostEqual(sum(float(player.get("minutes_projection") or 0) for player in roster), 240.0, delta=0.3)

    def test_save_rotation_projection_sums_to_240_and_zeros_injured_players(self):
        curry = next(player for player in self.plain["players"] if player["name"] == "Stephen Curry")
        with tempfile.TemporaryDirectory() as tmp:
            save_path = Path(tmp) / "league_save.json"
            save = create_league_save(ROOT, self.plain, "GSW", save_path, seed=7)
            projected = team_rotation_projection(self.plain, save, "team_gsw", integer=True)
            self.assertEqual(sum(projected.values()), 240)
            self.assertTrue(all(float(value).is_integer() for value in projected.values()))
            for state in save["health_states"]:
                if state["player_id"] == curry["id"]:
                    state.update({"availability_status": "out", "current_injury_id": "test_injury", "return_date": "2025-11-15"})
            injured = team_rotation_projection(self.plain, save, "team_gsw", integer=True)
            self.assertEqual(injured[curry["id"]], 0)
            self.assertEqual(sum(injured.values()), 240)

    def test_mandatory_press_events_aggregate_by_day_and_topic(self):
        save = {"state": {"user_team_id": "team_gsw"}, "pending_press_events": []}
        first = queue_aggregated_press_event(save, "trade", "GSW trades Player A for Player B.", ["team_gsw"], "2026-01-10")
        second = queue_aggregated_press_event(save, "trade", "GSW adds a second-round pick in a follow-up move.", ["team_gsw"], "2026-01-10")
        third = queue_aggregated_press_event(save, "staff_hire", "GSW hires a new scouting lead.", ["team_gsw"], "2026-01-10")
        self.assertEqual(first["id"], second["id"])
        self.assertNotEqual(first["id"], third["id"])
        self.assertEqual(len(save["pending_press_events"]), 2)
        trade_event = next(item for item in save["pending_press_events"] if item["kind"] == "trades")
        self.assertEqual(len(trade_event["headlines"]), 2)
        self.assertIn("question", trade_event)

    def test_injury_social_only_posts_substantial_events_once(self):
        with tempfile.TemporaryDirectory() as tmp:
            save_path = Path(tmp) / "league_save.json"
            save = create_league_save(ROOT, self.plain, "GSW", save_path, seed=5)
            curry = next(player for player in self.plain["players"] if player["name"] == "Stephen Curry")
            minor = {"id": "injury_minor", "player_id": curry["id"], "team_id": curry["team_id"], "start_date": "2025-11-01", "body_area": "ankle_foot", "expected_games_missed": 3}
            major = {"id": "injury_major", "player_id": curry["id"], "team_id": curry["team_id"], "start_date": "2025-12-01", "body_area": "ankle_foot", "expected_games_missed": 12}
            health = {"events": [minor, major], "final_states": save["health_states"]}
            merge_health_results(save, health, self.plain)
            merge_health_results(save, health, self.plain)
            injury_news = [item for item in save["news_items"] if item["kind"] == "injury"]
            self.assertEqual(len(injury_news), 1)
            self.assertIn("12 games", injury_news[0]["headline"])
            depth_player = next(player for player in self.plain["players"] if player["team_id"] == "team_gsw" and float(player.get("minutes_projection") or 0) < 20)
            depth_major = {"id": "injury_depth_major", "player_id": depth_player["id"], "team_id": depth_player["team_id"], "start_date": "2025-12-02", "body_area": "ankle_foot", "expected_games_missed": 18}
            merge_health_results(save, {"events": [depth_major], "final_states": save["health_states"]}, self.plain)
            injury_news = [item for item in save["news_items"] if item["kind"] == "injury"]
            self.assertEqual(len(injury_news), 1)
            injured_states = [
                {**state, "availability_status": "out", "current_injury_id": "injury_major"}
                if state.get("player_id") == curry["id"]
                else state
                for state in save["health_states"]
            ]
            merge_health_results(save, {"events": [major], "final_states": injured_states}, self.plain)
            replacement = next(player for player in self.plain["players"] if player["team_id"] == "team_gsw" and player["id"] != curry["id"])
            save.setdefault("player_season_stats", {})[replacement["id"]] = {"games": 5, "minutes": 100}
            active_states = [
                {**state, "availability_status": "active", "current_injury_id": None}
                if state.get("player_id") == curry["id"]
                else state
                for state in save["health_states"]
            ]
            merge_health_results(save, {"events": [], "final_states": active_states}, self.plain)
            self.assertFalse(any(item["kind"] == "injury_return" for item in save["news_items"]))
            self.assertTrue(any(item["kind"] == "injury_return" for item in save["social_feed"]))

    def test_transaction_cli_smoke(self):
        with tempfile.TemporaryDirectory() as tmp:
            stdout = StringIO()
            with redirect_stdout(stdout):
                code = cli_main(["--root", str(ROOT), "--out", tmp, "trade-block", "--team", "WAS"])
            self.assertEqual(code, 0)
            payload = json.loads(stdout.getvalue())
            self.assertEqual(payload["team"]["abbrev"], "WAS")
            self.assertGreater(payload["entry_count"], 0)
            stdout = StringIO()
            with redirect_stdout(stdout):
                code = cli_main(["--root", str(ROOT), "--out", tmp, "contract-market", "player", "Stephen Curry"])
            self.assertEqual(code, 0)
            payload = json.loads(stdout.getvalue())
            self.assertEqual(payload["player"]["name"], "Stephen Curry")
            stdout = StringIO()
            with redirect_stdout(stdout):
                code = cli_main(["--root", str(ROOT), "--out", tmp, "evaluate-signing", "LeBron James", "--team", "PHX", "--years", "2", "--aav", "35"])
            self.assertEqual(code, 0)
            payload = json.loads(stdout.getvalue())
            self.assertTrue(payload["accepted_by_all"])
            stdout = StringIO()
            with redirect_stdout(stdout):
                code = cli_main(["--root", str(ROOT), "--out", tmp, "pick-recommendations", "--team", "WAS", "--pick", "pick_2026-1-1-was", "--limit", "2"])
            self.assertEqual(code, 0)
            payload = json.loads(stdout.getvalue())
            self.assertEqual(payload["recommendations"][0]["entry"]["prospect"]["name"], "AJ Dybantsa")
            stdout = StringIO()
            with redirect_stdout(stdout):
                code = cli_main(["--root", str(ROOT), "--out", tmp, "generate-draft-order", "2027", "--seed", "4"])
            self.assertEqual(code, 0)
            payload = json.loads(stdout.getvalue())
            self.assertEqual(payload["pick_count"], 60)
            stdout = StringIO()
            with redirect_stdout(stdout):
                code = cli_main(["--root", str(ROOT), "--out", tmp, "rookie-contract", "--team", "WAS", "--pick", "pick_2026-1-1-was", "--prospect", "AJ Dybantsa"])
            self.assertEqual(code, 0)
            payload = json.loads(stdout.getvalue())
            self.assertEqual(payload["rookie_contract"]["contract_type"], "first_round_rookie_scale")

    def test_sim_feature_vectors_preserve_basketball_sanity(self):
        players = {player.normalized_name: to_plain(player) for player in self.universe.players}
        teams = {team.abbrev: to_plain(team) for team in self.universe.teams}
        plain = to_plain(self.universe)
        curry = player_feature_vector(plain, players["stephen curry"])
        luka = player_feature_vector(plain, players["luka doncic"])
        tatum = player_feature_vector(plain, players["jayson tatum"])
        giannis = player_feature_vector(plain, players["giannis antetokounmpo"])
        clowney = player_feature_vector(plain, players["noah clowney"])
        wemby = player_feature_vector(plain, players["victor wembanyama"])
        draymond = player_feature_vector(plain, players["draymond green"])
        okc = team_feature_vector(plain, teams["OKC"])
        self.assertGreaterEqual(curry.features["spacing"], 90)
        self.assertGreaterEqual(luka.features["usage"], 80)
        self.assertGreater(curry.features["scoring_usage"], draymond.features["scoring_usage"])
        self.assertGreater(curry.features["shot_creation"], draymond.features["shot_creation"])
        self.assertGreaterEqual(tatum.features["usage"], 78)
        self.assertGreaterEqual(giannis.features["impact"], 78)
        self.assertGreaterEqual(giannis.features["rim_pressure"], 90)
        self.assertGreater(player_star_power_score(curry.features), player_star_power_score(draymond.features))
        self.assertGreater(
            scoring_weight({"minutes": 32}, curry.features),
            scoring_weight({"minutes": 32}, draymond.features) * 1.6,
        )
        self.assertLess(luka.features["defensive_events"], 55)
        self.assertGreater(luka.features["defensive_weak_link"], 55)
        self.assertLess(clowney.features["usage"], 68)
        self.assertGreaterEqual(wemby.features["rim_deterrence"], 75)
        self.assertGreaterEqual(draymond.features["passing"], 85)
        self.assertIn("primary_creator", okc.features)
        self.assertIn("defensive_anchor", okc.features)
        self.assertGreater(okc.features["defensive_events"], 55)
        gsw = team_feature_vector(plain, teams["GSW"])
        self.assertGreater(gsw.features["old_core_share"], 0.25)
        self.assertLess(age_fatigue_effect(gsw.features, {"rest_days": 0})["offense"], age_fatigue_effect(gsw.features, {"rest_days": 3})["offense"])
        missing_creator = {"availability_dependency_penalty": 3.0, "availability_creation_gap": 18.0, "availability_spacing_gap": 6.0}
        missing_defender = {"availability_dependency_penalty": 3.0, "availability_defensive_event_gap": 18.0}
        self.assertLess(availability_gap_effect(missing_creator)["offense"], availability_gap_effect(missing_defender)["offense"])
        self.assertGreater(availability_gap_effect(missing_defender)["defense_leak"], availability_gap_effect(missing_creator)["defense_leak"])

    def test_coach_ratings_use_star_scale_and_overrides(self):
        ratings = coach_ratings(to_plain(self.universe))
        by_name = {rating.coach_name: rating for rating in ratings}
        self.assertGreaterEqual(by_name["Mark Daigneault"].ratings["development"], 4.5)
        for rating in ratings:
            for value in rating.ratings.values():
                self.assertGreaterEqual(value, 0)
                self.assertLessEqual(value, 5)

    def test_replay_real_minutes_sim_is_deterministic(self):
        first = to_plain(sim_game(ROOT, "401809243", mode="replay-real-minutes", seed=9))
        second = to_plain(sim_game(ROOT, "401809243", mode="replay-real-minutes", seed=9))
        self.assertEqual(first, second)
        self.assertAlmostEqual(sum(line["minutes"] for line in first["player_lines"] if line["team_id"] == first["home_team_id"]), 240, places=1)
        self.assertTrue(all(line["points"] >= 0 for line in first["player_lines"]))

    def test_replay_real_minutes_normalizes_game_team_abbreviations(self):
        context = load_sim_context(ROOT, to_plain(self.universe))
        teams = {team["abbrev"]: team for team in context["canonical"]["teams"]}
        self.assertEqual(normalize_game_team_abbrev("WSH"), "WAS")
        self.assertEqual(normalize_game_team_abbrev("UTAH"), "UTA")
        was_pool = game_player_pool(context, "401810740", teams["WAS"], "replay-real-minutes")
        uta_pool = game_player_pool(context, "401810736", teams["UTA"], "replay-real-minutes")
        self.assertAlmostEqual(sum(item["minutes"] for item in was_pool), 240, places=1)
        self.assertAlmostEqual(sum(item["minutes"] for item in uta_pool), 240, places=1)
        self.assertGreaterEqual(len(was_pool), 8)
        self.assertGreaterEqual(len(uta_pool), 8)

    def test_sandbox_health_excludes_unavailable_startup_players(self):
        context = load_sim_context(ROOT, self.plain)
        game = scheduled_game_for_context(context, "401810729")
        teams = {team["abbrev"]: team for team in context["canonical"]["teams"]}
        pool = game_player_pool(context, "401810729", teams["BOS"], "sandbox-sim", game_date=game["gameDate"])
        names = {item["player"]["name"] for item in pool}
        self.assertNotIn("Jayson Tatum", names)
        self.assertAlmostEqual(sum(item["minutes"] for item in pool), 240, places=1)

    def test_validation_report_runs_with_available_minutes(self):
        report = validate(ROOT, through_date="2025-10-22", seed=3)
        self.assertGreater(report.game_count, 0)
        self.assertIn("available_games", report.summary)

    def test_odds_math_removes_vig(self):
        self.assertAlmostEqual(american_to_implied_probability(-150), 0.6)
        self.assertAlmostEqual(american_to_implied_probability(200), 1 / 3, places=5)
        no_vig = no_vig_probabilities(0.6, 0.45)
        self.assertAlmostEqual(no_vig["home"] + no_vig["away"], 1.0)

    def test_win_probability_trusts_margin_distribution_for_clear_edges(self):
        self.assertGreater(calibrated_win_probability(4, 4, [12, 14, 16, 18]), 0.85)
        self.assertLess(calibrated_win_probability(0, 4, [-12, -14, -16, -18]), 0.15)

    def test_game_probability_report_is_deterministic_and_market_aware(self):
        first = validate_game_probabilities(ROOT, "401810728", runs=8, seed=11)
        second = validate_game_probabilities(ROOT, "401810728", runs=8, seed=11)
        self.assertEqual(first, second)
        self.assertIn("home_win_probability", first["sim"])
        self.assertIn("raw_home_win_probability", first["sim"])
        self.assertIn("beta_home_win_probability", first["sim"])
        self.assertIn("margin_home_win_probability", first["sim"])
        self.assertNotEqual(first["sim"]["probability_calibration"], "beta_shrink_to_50_50_alpha_6")
        self.assertIn("market_vs_sim_home_prob_delta", first["calibration"])
        self.assertIn("player_stats", first["sim"])
        self.assertIn("player_props", first["calibration"])

    def test_game_probability_report_uses_actuals_when_available(self):
        report = validate_game_probabilities(ROOT, "401810728", runs=8, seed=11)
        self.assertIsNotNone(report["actual"])
        self.assertIn("brier_score", report["calibration"])
        self.assertIn("market_brier_score", report["calibration"])
        self.assertIn("sim_minus_market_log_loss", report["calibration"])
        self.assertIn("actual_margin_percentile", report["calibration"])

    def test_season_probability_report_runs_without_full_market_data(self):
        report = validate_season_probabilities(ROOT, through_date="2026-03-02", runs=4, seed=5, limit=2)
        self.assertEqual(report["game_count"], 2)
        self.assertIn("mean_brier_score", report["summary"])

    def test_market_calibration_report_is_holdout_aware(self):
        report = calibrate_market(ROOT, through_date="2026-03-15", holdout_start="2026-02-01", runs=4, seed=7, limit=6)
        self.assertIn("tuning", report)
        self.assertIn("holdout", report)
        self.assertIn("edge_candidates", report)
        self.assertEqual(report["tuning"]["game_count"] + report["holdout"]["game_count"], report["game_count"])
        self.assertTrue(all(candidate["diagnostic_only"] for candidate in report["edge_candidates"]))

    def test_market_calibration_can_limit_to_scored_games(self):
        report = calibrate_market(ROOT, through_date="2026-05-22", runs=4, seed=7, limit=3, scored_only=True)
        self.assertTrue(report["scored_only"])
        self.assertEqual(report["summary"]["games_with_actuals"], report["game_count"])
        self.assertIn("probability_buckets", report["summary"])

    def test_existing_boxscores_load_for_incremental_refresh(self):
        boxscores = existing_game_boxscores(ROOT)
        self.assertGreaterEqual(len(boxscores), 1000)
        self.assertIn("401810749", boxscores)
        self.assertEqual(len(boxscores), len(set(boxscores)))

    def test_lineup_quality_effect_moves_clear_talent_edges(self):
        strong_offense = {"impact": 66, "star_power": 72, "primary_creator": 76, "offense_creation": 71, "offense_balance": 65}
        weak_offense = {"impact": 48, "star_power": 45, "primary_creator": 43, "offense_creation": 44, "offense_balance": 46}
        strong_defense = {"impact": 66, "star_power": 72, "defense_total": 71, "defensive_anchor": 70}
        weak_defense = {"impact": 48, "star_power": 45, "defense_total": 47, "defensive_anchor": 44}
        self.assertGreater(lineup_quality_effect(strong_offense, weak_defense), 6.0)
        self.assertLess(lineup_quality_effect(weak_offense, strong_defense), -6.0)

    def test_explain_game_probabilities_includes_feature_breakdowns(self):
        report = explain_game_probability(ROOT, "401809243", runs=4, seed=2)
        self.assertIn("offensive_feature_deltas_home_minus_away", report)
        self.assertIn("defensive_feature_deltas_home_minus_away", report)
        self.assertIn("market_vs_sim_vs_actual", report)
        self.assertIn("usage_star_load", report["teams"]["home"])
        self.assertIn("offense_fit", report["teams"]["home"]["coach"]["effects"])
        self.assertIsNotNone(report["teams"]["home"]["manifesto_context"])

    def test_availability_dependency_is_generic_not_manifesto_triggered(self):
        bos_report = explain_game_probability(ROOT, "401810729", runs=4, seed=2)
        gsw_report = explain_game_probability(ROOT, "401810775", runs=4, seed=2)
        self.assertGreater(bos_report["teams"]["home"]["availability_dependency"]["penalty"], 0)
        self.assertIsNone(bos_report["teams"]["home"]["manifesto_context"])
        self.assertGreater(gsw_report["teams"]["away"]["availability_dependency"]["penalty"], 0)
        self.assertEqual(gsw_report["teams"]["away"]["manifesto_feature_adjustments"]["dependency_penalty"], 0)

    def test_recent_scoring_context_uses_only_prior_games(self):
        context = load_sim_context(ROOT, self.plain)
        game = scheduled_game_for_context(context, "401811023")
        home_team = next(team for team in context["canonical"]["teams"] if team["abbrev"] == "BOS")
        baseline = recent_scoring_context_for_team(context, game, home_team)
        self.assertGreaterEqual(baseline["recent_game_count"], 3)
        future_context = {
            **context,
            "boxscores": [
                *context["boxscores"],
                {
                    "game_id": "future_leak_guard",
                    "date": "2026-06-30",
                    "status": "STATUS_FINAL",
                    "home_team_id": game["homeTeamId"],
                    "away_team_id": game["awayTeamId"],
                    "home_score": 180,
                    "away_score": 170,
                },
            ],
        }
        self.assertEqual(baseline, recent_scoring_context_for_team(future_context, game, home_team))

    def test_matchup_total_environment_is_pace_only(self):
        open_matchup = {
            "defense_total": 44,
            "defense_rim": 45,
            "offense_pressure": 67,
            "offense_balance": 62,
            "offense_creation": 62,
            "defense_integrity": 46,
        }
        grind_matchup = {
            "defense_total": 66,
            "defense_rim": 65,
            "offense_pressure": 48,
            "offense_balance": 51,
            "offense_creation": 52,
            "defense_integrity": 66,
        }
        self.assertGreater(matchup_total_environment_effect(open_matchup, open_matchup)["pace"], 0)
        self.assertLess(matchup_total_environment_effect(grind_matchup, grind_matchup)["pace"], 0)
        self.assertEqual(matchup_total_environment_effect(open_matchup, grind_matchup)["offense"], 0.0)

    def test_recent_scoring_environment_compresses_low_totals(self):
        neutral_low = {
            "recent_scoring": {
                "recent_game_count": 5,
                "total": 218,
                "pace_delta": 0,
                "offense_delta": 0,
                "defense_allowed_delta": 0,
            }
        }
        neutral_high = {
            "recent_scoring": {
                "recent_game_count": 5,
                "total": 242,
                "pace_delta": 0,
                "offense_delta": 0,
                "defense_allowed_delta": 0,
            }
        }
        self.assertLess(game_environment_effect(neutral_low, neutral_low)["offense"], 0)
        self.assertLess(game_environment_effect(neutral_low, neutral_low)["pace"], 0)
        self.assertGreater(game_environment_effect(neutral_high, neutral_high)["offense"], 0)
        self.assertGreater(game_environment_effect(neutral_high, neutral_high)["pace"], 0)

    def test_manifesto_expectation_phrases_adjust_current_team_context(self):
        contender = {"impact": 50, "spacing": 50, "top_creation": 50, "defensive_events": 50, "rim_deterrence": 50, "defensive_anchor": 50, "star_power": 50}
        rebuild = {"impact": 50, "star_power": 50, "primary_creator": 50, "top_creation": 50, "passing": 50, "defensive_events": 50, "rim_deterrence": 50, "defensive_anchor": 50}
        contender_notes: list[str] = []
        rebuild_notes: list[str] = []
        apply_manifesto_expectation_adjustments("they fixed the offense and are clear favorites with the best defensive teams we've ever seen", contender, contender_notes)
        apply_manifesto_expectation_adjustments("clear tanking effort, dead last, shocked if they win more than 20", rebuild, rebuild_notes)
        self.assertGreater(contender["impact"], 51)
        self.assertGreater(contender["defensive_events"], 51)
        self.assertLess(rebuild["impact"], 48)
        self.assertLess(rebuild["top_creation"], 49)

    def test_outputs_are_written(self):
        with tempfile.TemporaryDirectory() as tmp:
            paths = write_outputs(self.universe, tmp)
            for path in paths.values():
                self.assertTrue(path.exists())
            data = json.loads(paths["json"].read_text())
            self.assertEqual(data["meta"]["id"], "universe_2025_26_preseason")

    def test_rebuild_is_deterministic(self):
        second = to_plain(build_universe(ROOT))
        self.assertEqual(json.dumps(self.plain, sort_keys=True), json.dumps(second, sort_keys=True))


if __name__ == "__main__":
    unittest.main()
