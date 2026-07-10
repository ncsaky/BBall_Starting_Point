import base64
import json
import os
import random
import tempfile
import threading
import unittest
import zipfile
from contextlib import redirect_stdout
from io import StringIO
from pathlib import Path
from collections import Counter
from unittest.mock import patch
from urllib import request as urlrequest

import nba_gm_data.transactions as transactions_module
from nba_gm_data.app_actions import APP_ACTION_PROTOCOL_VERSION, dispatch_app_action, estimated_overall_delta
from nba_gm_data.app_server import make_gui_server
from nba_gm_data.assets import install_loading_assets
from nba_gm_data.animation import auto_frame_size, colorize_frame, default_video_path, load_animation_frames
from nba_gm_data.cli import load_or_build, main as cli_main
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
from nba_gm_data.narrative import (
    NARRATIVE_PROMPT_VERSION,
    NarrativeProviderError,
    OllamaNarrativeProvider,
    default_narrative_settings,
    narrative_status,
    press_cache_entry,
    social_context_packet,
    validate_press_payload,
    validate_social_payload,
)
from nba_gm_data.research import existing_game_boxscores
from nba_gm_data.save import (
    advance_save,
    add_league_event,
    add_news,
    annotate_lottery_odds_context,
    box_score_view,
    calendar_view,
    complete_offseason_and_rollover,
    create_league_save,
    ai_extension_due_date,
    ai_extension_team_pass_outlook,
    ensure_league_save_defaults,
    ensure_draft_processed,
    extension_headline_with_terms,
    hold_press_conference,
    league_events_view,
    league_leaders,
    league_standings,
    load_save,
    lottery_seed,
    morale_report,
    narrative_settings_view,
    offseason_status,
    pending_actions_view,
    apply_ai_staff_recommendations,
    age_staff_contracts,
    playoff_picture,
    playoff_leaders,
    cap_lines_for_season,
    process_ai_extensions,
    process_ai_actions,
    propose_trade_to_save,
    quick_sim_current_season,
    recent_rookie_protected_player_ids,
    run_draft_lottery,
    save_status,
    refresh_draft_order_from_save,
    simulate_playoff_round,
    simulate_next_playoff_game,
    social_subject,
    social_feed_view,
    start_playoffs,
    team_dashboard,
    write_save,
    update_narrative_settings,
    canonical_with_save,
    merge_health_results,
    maybe_queue_rare_drama,
    press_impact,
    prune_rotation_recommendations,
    queue_aggregated_press_event,
    generate_league_awards,
    resolve_pick_obligations_for_year,
    repair_protected_pick_fallback,
    starting_lineup_slots,
    team_rotation_projection,
    team_cap_summary,
    player_attribute_summary,
    press_conferences_enabled,
    process_inseason_released_free_agent_signings,
    record_game_result,
)
from nba_gm_data.play import (
    box_score_influence,
    choose_assets,
    choose_fallback_pick_for_protection,
    choose_save_path,
    contract_start_season_for_signing,
    contextual_press_answers,
    deterministic_random_team,
    draft_trade_offer_assets,
    extension_safe_year_limit,
    free_agent_durability_flag,
    free_agency_user_offer_limit,
    handle_forced_phase,
    initialize_free_agency_market,
    league_trait_rows,
    league_trait_rating_thresholds,
    maybe_run_ai_draft_trades_before_pick,
    ratings_guide,
    offer_interest_score,
    pick_slot_is_determined_for_trade,
    print_free_agency_day_recap,
    print_lottery,
    print_prospect_line,
    print_home,
    press_room,
    print_league_trait_table,
    print_trade_offer_details,
    social_timeline_lines,
    social_timeline_text,
    refresh_live_draft_state_ownership,
    signing_cap_check,
    sync_live_draft_state_to_saved_order,
    prospect_scout_display,
    accept_trade_finder_offer,
    attach_pick_terms_to_trade,
    apply_saved_draft_order_to_draft,
    best_ai_draft_trade_candidate,
    trade_finder_report_for_selection,
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
    normalize_minutes,
    no_vig_probabilities,
    player_feature_vector,
    player_star_power_score,
    recent_scoring_context_for_team,
    scheduled_game_for_context,
    assist_rate_for_player,
    assist_rate_from_features,
    plausible_point_cap,
    scoring_weight,
    sim_game,
    team_feature_vector,
    validate,
    validate_game_probabilities,
    validate_season_probabilities,
)
from nba_gm_data.storage import write_outputs
from nba_gm_data.staff import fire_staff_from_save, hire_staff_from_save, negotiate_staff_hire, simulate_ai_staff_changes, staff_budget_for_team, staff_budget_snapshot, staff_grade, staff_market_report, staff_team_report
from nba_gm_data.transactions import annotate_pick_obligation_context, apply_trade_to_save, buyer_offer_package_options, canonical_with_pending_pick_terms, current_salary, evaluate_trade, fallback_asset_valuation, find_trade, find_trade_for_assets, gm_report, market_trade_target_value, package_value_for_team, pick_asset_value, pick_label, pick_season_start, pick_swap_asset_value, pick_swap_display_label, player_health_risk, protected_pick_fallback_is_distinct, simulate_ai_trades, stepien_guardrail_issues, trade_apply_authorized, trade_block_report, trade_headline_from_payload, trade_result_with_pick_terms, tradeable_pick_swaps_for_team, tradeable_picks_for_team, validate_pick_obligation_term, with_transaction_context
from nba_gm_data.traits import LEAGUE_TRAIT_RATING_COLUMNS, LEAGUE_TRAIT_RATINGS_SOURCE_ID, load_league_trait_ratings, match_league_trait_ratings


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

    def test_playtest_player_data_overrides_apply_to_canonical(self):
        players = {player["name"]: player for player in self.plain["players"]}
        expected_heights = {
            "Gui Santos": 79,
            "Will Richard": 75,
            "Pat Spencer": 74,
            "Quinten Post": 84,
            "Malevy Leons": 81,
            "Yuki Kawamura": 67,
        }
        for name, inches in expected_heights.items():
            self.assertEqual(players[name]["height_inches"], inches)
        podz = players["Brandin Podziemski"]
        traits = {
            trait["trait_key"]: trait
            for trait in self.plain["traits"]
            if trait["player_id"] == podz["id"]
        }
        self.assertLessEqual(traits["handle_pressure"]["value"], 44)
        self.assertLessEqual(traits["passing_reads"]["value"], 50)
        self.assertLessEqual(traits["playoff_translation"]["value"], 50)
        self.assertGreaterEqual(traits["offensive_rebounding"]["value"], 66)

    def test_minutes_normalization_caps_regulation_minutes(self):
        pool = [
            {"player": {"id": f"p{idx}"}, "minutes": raw}
            for idx, raw in enumerate([42, 38, 31, 24, 18, 12, 10, 8, 6, 4], start=1)
        ]
        normalized = normalize_minutes(pool)
        self.assertLessEqual(max(item["minutes"] for item in normalized), 48.0)
        self.assertAlmostEqual(sum(item["minutes"] for item in normalized), 240.0, places=1)

    def test_animation_auto_size_color_and_cache_selection(self):
        self.assertEqual(auto_frame_size(os.terminal_size((208, 60))), (192, 54))
        self.assertEqual(auto_frame_size(os.terminal_size((120, 40))), (112, 32))
        colored = colorize_frame(
            base64.b64encode(bytes([0, 80, 160, 255])).decode("ascii"),
            {
                "profile": "neon_white",
                "frame_format": "gray_b64",
                "width": 2,
                "height": 2,
                "render_options": {
                    "foreground_a": "#ff00c3",
                    "foreground_b": "#00fff0",
                    "background": "#ffffff",
                    "bg_gradient": True,
                    "bg_saturation": 30,
                    "threshold": 0,
                },
            },
            truecolor=True,
        )
        self.assertIn("\033[38;2;", colored)
        self.assertIn("\033[48;2;", colored)
        with tempfile.TemporaryDirectory() as tmp:
            video_root = Path(tmp) / "Animation Videos"
            video_root.mkdir()
            short_video = video_root / "5minClip.mp4"
            full_video = video_root / "Full Season Highlights.mp4"
            short_video.write_bytes(b"short")
            full_video.write_bytes(b"full-video-source")
            self.assertEqual(default_video_path(tmp), full_video)
            cache_root = Path(tmp) / ".cache" / "ascii_animation"
            old_dir = cache_root / "old"
            new_dir = cache_root / "new"
            full_dir = cache_root / "full"
            old_dir.mkdir(parents=True)
            new_dir.mkdir(parents=True)
            full_dir.mkdir(parents=True)
            (old_dir / "frames.json").write_text(json.dumps({"width": 88, "height": 30, "fps": 8, "frames": ["old"]}), encoding="utf-8")
            (new_dir / "frames.json").write_text(
                json.dumps({"profile": "neon_white", "render_version": 5, "video": str(short_video), "width": 112, "height": 32, "fps": 8, "frames": ["new"]}),
                encoding="utf-8",
            )
            (full_dir / "frames.json").write_text(
                json.dumps({"profile": "neon_white", "render_version": 5, "video": str(full_video), "width": 112, "height": 32, "fps": 8, "frames": ["full"]}),
                encoding="utf-8",
            )
            frames, fps, metadata = load_animation_frames(tmp, terminal_size=os.terminal_size((120, 40)))
            self.assertEqual(frames, ["full"])
            self.assertEqual(fps, 8)
            self.assertEqual(metadata["profile"], "neon_white")
            self.assertTrue(metadata["preferred_video"])

    def test_install_loading_assets_from_zip(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "game"
            root.mkdir()
            good_zip = Path(tmp) / "loading-assets-v1.zip"
            with zipfile.ZipFile(good_zip, "w") as archive:
                archive.writestr(".cache/ascii_animation/demo/metadata.json", "{}")
                archive.writestr(".cache/ascii_animation/demo/frames.json", '{"frames":["demo"]}')
            result = install_loading_assets(root, zip_path=good_zip)
            self.assertEqual(result["status"], "installed")
            self.assertTrue((root / ".cache/ascii_animation/demo/frames.json").exists())

            unsafe_zip = Path(tmp) / "unsafe.zip"
            with zipfile.ZipFile(unsafe_zip, "w") as archive:
                archive.writestr("../outside.txt", "bad")
            unsafe_result = install_loading_assets(root, zip_path=unsafe_zip, force=True)
            self.assertEqual(unsafe_result["status"], "unsafe_zip")

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
        podz = players["brandin podziemski"]
        self.assertLessEqual(traits[(podz.id, "passing_reads")].value, 50)
        self.assertLessEqual(traits[(podz.id, "handle_pressure")].value, 44)
        self.assertGreaterEqual(traits[(podz.id, "offensive_rebounding")].value, 60)

    def test_league_trait_ratings_prior_import_audit_and_manual_precedence(self):
        rows = load_league_trait_ratings(ROOT / "data/overrides/league_trait_ratings_2026_06_20.csv")
        self.assertGreaterEqual(len(rows), 500)
        self.assertEqual(LEAGUE_TRAIT_RATING_COLUMNS["ShootingRange"], "shooting_range")
        matched, report = match_league_trait_ratings(self.universe.players, rows)
        self.assertGreaterEqual(len(matched), 370)
        alias_pairs = {(item["csv_player"], item["matched_player"]) for item in report["alias_matches"]}
        self.assertIn(("Ron Holland", "Ronald Holland II"), alias_pairs)
        self.assertIn(("Carlton Carrington", "Bub Carrington"), alias_pairs)

        meta_report = self.plain["meta"]["rating_calibration_report"]
        self.assertEqual(meta_report["matched_count"], report["matched_count"])
        self.assertGreaterEqual(meta_report["adjusted_trait_count"], 5000)
        self.assertGreater(meta_report["fringe_role_cap_adjusted_player_count"], 0)
        self.assertEqual(meta_report["source_id"], LEAGUE_TRAIT_RATINGS_SOURCE_ID)
        self.assertIn(LEAGUE_TRAIT_RATINGS_SOURCE_ID, {source.id for source in self.universe.sources})

        traits = {(trait.player_id, trait.trait_key): trait for trait in self.universe.traits}
        players = {player.normalized_name: player for player in self.universe.players}
        tatum = players["jayson tatum"]
        tatum_versatility = traits[(tatum.id, "shot_versatility")]
        self.assertIn(LEAGUE_TRAIT_RATINGS_SOURCE_ID, tatum_versatility.source_ids)
        self.assertIn("league_trait_rating_calibration", tatum_versatility.components)

        nurkic = players["jusuf nurkic"]
        nurkic_rim = traits[(nurkic.id, "rim_deterrence")]
        self.assertEqual(nurkic_rim.value, 62)
        self.assertIn("manual", nurkic_rim.source_kind)

    def test_league_trait_calibration_sanity_corrects_rank_shape(self):
        players = {player.normalized_name: player for player in self.universe.players}
        summaries = {
            normalized: player_attribute_summary(self.plain, player.id)
            for normalized, player in players.items()
        }
        top_overall = sorted(
            ((attrs["overall"], players[name].name) for name, attrs in summaries.items()),
            reverse=True,
        )[:25]
        top_names = {name for _, name in top_overall}
        self.assertIn("Shai Gilgeous-Alexander", top_names)
        self.assertIn("Nikola Jokić", top_names)
        self.assertNotIn("Collin Gillespie", top_names)

        self.assertGreaterEqual(summaries["shai gilgeous alexander"]["creation"], 80)
        self.assertGreaterEqual(summaries["nikola jokic"]["passing"], 94)
        self.assertGreaterEqual(summaries["victor wembanyama"]["rim_deterrence"], 96)
        self.assertGreaterEqual(summaries["jaren jackson jr"]["rim_deterrence"], 90)
        self.assertGreaterEqual(summaries["trae young"]["passing"], 82)
        self.assertGreaterEqual(summaries["jayson tatum"]["versatility"], 50)
        self.assertLess(summaries["collin gillespie"]["overall"], 62)
        self.assertLess(summaries["tyty washington jr"]["overall"], 56)
        self.assertLess(summaries["tyty washington jr"]["defense"], 62)
        self.assertLessEqual(summaries["javon small"]["passing"], 60)
        self.assertLessEqual(summaries["chucky hepburn"]["rim_pressure"], 54)
        self.assertGreater(summaries["matisse thybulle"]["defense"], 75)

    def test_manual_player_physical_overrides_apply(self):
        players = {player.normalized_name: player for player in self.universe.players}
        self.assertEqual(players["trey alexander"].height_inches, 77)
        self.assertEqual(players["karlo matkovic"].height_inches, 82)
        self.assertEqual(players["hunter dickinson"].height_inches, 85)
        self.assertEqual(players["dru smith"].height_inches, 74)
        self.assertEqual(players["keshad johnson"].height_inches, 78)
        self.assertEqual(players["jordan goodwin"].height_inches, 75)
        self.assertEqual(players["justin champagnie"].height_inches, 78)
        self.assertEqual(players["tristan vukcevic"].height_inches, 84)
        self.assertEqual(players["nfaly dante"].height_inches, 83)
        self.assertEqual(players["naeqwan tomlin"].height_inches, 80)
        self.assertEqual(players["gui santos"].height_inches, 79)
        self.assertEqual(players["will richard"].height_inches, 75)
        self.assertEqual(players["pat spencer"].height_inches, 74)
        self.assertEqual(players["quinten post"].height_inches, 84)
        self.assertEqual(players["malevy leons"].height_inches, 81)
        self.assertEqual(players["yuki kawamura"].height_inches, 67)
        self.assertGreaterEqual(players["trae young"].minutes_projection, 34.0)

    def test_rostered_players_have_dashboard_core_data(self):
        teams = {team.id: team.abbrev for team in self.universe.teams}
        contracts_by_player: dict[str, list] = {}
        for contract in self.universe.contracts:
            contracts_by_player.setdefault(contract.player_id, []).append(contract)
        missing = []
        for player in self.universe.players:
            if not player.team_id:
                continue
            if player.age is None or player.height_inches is None or not contracts_by_player.get(player.id):
                missing.append((teams.get(player.team_id), player.name, player.age, player.height_inches, bool(contracts_by_player.get(player.id))))
        self.assertEqual(missing, [])

        players = {player.normalized_name: player for player in self.universe.players}
        bub = contracts_by_player[players["bub carrington"].id]
        cam = contracts_by_player[players["cam whitmore"].id]
        bub_years = {item["season"]: float(item["salary"]) for contract in bub for item in contract.seasons}
        cam_years = {item["season"]: float(item["salary"]) for contract in cam for item in contract.seasons}
        self.assertAlmostEqual(sum(bub_years.values()) / len(bub_years), 4_750_000, delta=25_000)
        self.assertEqual(max(bub_years), "2026-27")
        self.assertAlmostEqual(sum(cam_years.values()) / len(cam_years), 5_500_000, delta=25_000)
        self.assertEqual(max(cam_years), "2026-27")

    def test_playtest_trait_adjustments_apply_after_league_calibration(self):
        players = {player.normalized_name: player for player in self.universe.players}
        summaries = {
            name: player_attribute_summary(self.plain, player.id)
            for name, player in players.items()
        }
        self.assertLess(summaries["shai gilgeous alexander"]["defense"], 70)
        self.assertLess(summaries["kyle anderson"]["defense"], 64)
        self.assertLess(summaries["kevin durant"]["defense"], 68)
        self.assertLess(summaries["draymond green"]["shooting"], summaries["jimmy butler iii"]["shooting"])
        self.assertLess(summaries["draymond green"]["range"], summaries["jimmy butler iii"]["range"])
        self.assertLess(summaries["dangelo russell"]["shooting"], 50)
        self.assertLess(summaries["dangelo russell"]["defense"], 36)
        self.assertGreater(summaries["daniss jenkins"]["defense"], 45)
        self.assertLess(summaries["derrick white"]["shooting"], 68)
        self.assertLess(summaries["derrick white"]["rim_deterrence"], 62)
        self.assertLess(summaries["desmond bane"]["rebounding"], 46)

    def test_ledger_gaps_are_explicit(self):
        summary = self.universe.coverage_report.summary
        future_second_scaffolds = [
            pick
            for pick in self.universe.draft_picks
            if pick.status == "inferred_future_second_round_scaffold"
        ]
        self.assertEqual(summary["research_pending"]["contracts"], 0)
        self.assertEqual(summary["contract_manual_review_count"], 0)
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
        self.assertGreaterEqual(len(future_picks), 150)
        underlying_future_pick_keys = {
            (pick.season, pick.round, pick.original_team_id)
            for pick in future_picks
            if pick.original_team_id
        }
        self.assertEqual(len(future_picks), len(underlying_future_pick_keys))
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
        traits_by_prospect: dict[str, dict[str, float]] = {}
        for trait in self.universe.draft_prospect_traits:
            traits_by_prospect.setdefault(trait.prospect_id, {})[trait.trait_key] = float(trait.value)
        aj_traits = traits_by_prospect[prospects["aj dybantsa"].id]
        peterson_traits = traits_by_prospect[prospects["darryn peterson"].id]
        boozer_traits = traits_by_prospect[prospects["cameron boozer"].id]
        athleticism_values = [traits["athleticism"] for traits in traits_by_prospect.values()]
        self.assertGreaterEqual(aj_traits["shot_creation"], 65)
        self.assertGreaterEqual(peterson_traits["rim_pressure"], 62)
        self.assertGreaterEqual(boozer_traits["rebounding"], 74)
        self.assertGreaterEqual(max(athleticism_values), 70)
        self.assertGreater(max(athleticism_values) - min(athleticism_values), 10)

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
        trait_rows = first["draft_prospect_traits"]
        athleticism_values = [float(trait["value"]) for trait in trait_rows if trait["trait_key"] == "athleticism"]
        self.assertGreaterEqual(max(athleticism_values), 62)
        self.assertGreater(max(athleticism_values) - min(athleticism_values), 12)

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

    def test_new_save_seeds_startup_free_agents_and_event_collections(self):
        with tempfile.TemporaryDirectory() as tmp:
            save_path = Path(tmp) / "startup_save.json"
            save = create_league_save(ROOT, self.plain, "GSW", save_path, seed=404)
            self.assertGreaterEqual(len(save.get("free_agent_player_ids", [])), 30)
            self.assertGreaterEqual(len(save.get("startup_free_agents", [])), 30)
            self.assertIn("released_free_agents", save)
            self.assertIn("league_events", save)
            self.assertIn("user_trade_offers", save)
            self.assertIn("pick_obligations", save)
            active = canonical_with_save(self.plain, save)
            startup_players = [player for player in active["players"] if player["id"] in set(save["startup_free_agents"])]
            self.assertGreaterEqual(len(startup_players), 30)
            self.assertTrue(all(not player.get("team_id") for player in startup_players))
            generated_startup = [player for player in startup_players if player.get("source_ids") == ["src_startup_free_agent_scaffold_v1"]]
            if len(generated_startup) >= 20:
                last_names = [player["name"].split()[-1] for player in generated_startup]
                self.assertGreaterEqual(len(set(last_names)), min(len(last_names), 20))

    def test_inseason_released_good_free_agent_gets_ai_signing_next_pass(self):
        with tempfile.TemporaryDirectory() as tmp:
            save_path = Path(tmp) / "released_fa_save.json"
            save = create_league_save(ROOT, self.plain, "GSW", save_path, seed=405)
            active = canonical_with_save(self.plain, save)
            curry = next(player for player in active["players"] if player["name"] == "Stephen Curry")
            was = next(team for team in active["teams"] if team["abbrev"] == "WAS")
            for player in active["players"]:
                if player.get("team_id") == was["id"]:
                    save.setdefault("roster_overrides", {})[player["id"]] = None
            save["roster_overrides"][curry["id"]] = None
            save.setdefault("free_agent_player_ids", []).append(curry["id"])
            save["free_agent_player_ids"] = sorted(set(save["free_agent_player_ids"]))
            save.setdefault("released_free_agents", {})[curry["id"]] = {
                "player_id": curry["id"],
                "player_name": curry["name"],
                "waived_by_team_id": "team_gsw",
                "waived_by_team_abbrev": "GSW",
                "release_date": "2025-10-20",
                "status": "available",
            }
            signed = process_inseason_released_free_agent_signings(self.plain, save, seed=405, date_value="2025-10-22")
            self.assertIn(curry["id"], signed)
            self.assertNotIn(curry["id"], save["free_agent_player_ids"])
            self.assertNotEqual(save["roster_overrides"][curry["id"]], "team_gsw")
            self.assertNotEqual(save["roster_overrides"][curry["id"]], save["released_free_agents"][curry["id"]]["waived_by_team_id"])
            self.assertEqual(save["released_free_agents"][curry["id"]]["status"], "signed")
            self.assertEqual(save["contract_overrides"][curry["id"]]["status"], "ai_inseason_released_free_agent_signing")

    def test_inseason_released_fringe_free_agent_is_not_forced_signed(self):
        with tempfile.TemporaryDirectory() as tmp:
            save_path = Path(tmp) / "released_depth_save.json"
            save = create_league_save(ROOT, self.plain, "GSW", save_path, seed=406)
            player_id = save["startup_free_agents"][0]
            player = next(player for player in canonical_with_save(self.plain, save)["players"] if player["id"] == player_id)
            save.setdefault("released_free_agents", {})[player_id] = {
                "player_id": player_id,
                "player_name": player["name"],
                "waived_by_team_id": "team_gsw",
                "release_date": "2025-10-20",
                "status": "available",
            }
            signed = process_inseason_released_free_agent_signings(self.plain, save, seed=406, date_value="2025-10-22")
            self.assertNotIn(player_id, signed)
            self.assertIn(player_id, save["free_agent_player_ids"])
            self.assertEqual(save["released_free_agents"][player_id]["status"], "available")

    def test_free_agent_player_lines_do_not_create_ghost_stats(self):
        with tempfile.TemporaryDirectory() as tmp:
            save_path = Path(tmp) / "ghost_stats_save.json"
            save = create_league_save(ROOT, self.plain, "GSW", save_path, seed=407)
            active = canonical_with_save(self.plain, save)
            curry = next(player for player in active["players"] if player["name"] == "Stephen Curry")
            gsw = next(team for team in active["teams"] if team["abbrev"] == "GSW")
            bos = next(team for team in active["teams"] if team["abbrev"] == "BOS")
            save.setdefault("roster_overrides", {})[curry["id"]] = None
            save.setdefault("free_agent_player_ids", []).append(curry["id"])
            save["player_season_stats"][curry["id"]] = {
                "player_id": curry["id"],
                "player_name": curry["name"],
                "team_id": gsw["id"],
                "team_abbrev": "GSW",
                "games": 1,
                "game_ids": ["old_game"],
                "points": 30.0,
                "rebounds": 5.0,
                "assists": 8.0,
            }
            result = {
                "game_id": "ghost_game",
                "home_team_id": gsw["id"],
                "away_team_id": bos["id"],
                "home_score": 110,
                "away_score": 100,
                "team_lines": [
                    {"team_id": bos["id"], "team_abbrev": "BOS", "points": 100},
                    {"team_id": gsw["id"], "team_abbrev": "GSW", "points": 110},
                ],
                "player_lines": [
                    {"player_id": curry["id"], "player_name": curry["name"], "team_id": gsw["id"], "team_abbrev": "GSW", "minutes": 34, "points": 40, "rebounds": 4, "assists": 9},
                ],
            }
            record_game_result(save, self.plain, {"externalGameId": "ghost_game", "gameDate": "2025-10-22"}, result)
            self.assertEqual(save["player_season_stats"][curry["id"]]["games"], 1)
            self.assertEqual(save["player_season_stats"][curry["id"]]["game_ids"], ["old_game"])
            self.assertFalse(any(log.get("player_id") == curry["id"] and log.get("game_id") == "ghost_game" for log in save.get("player_game_logs", [])))
            saved_result = next(item for item in save["game_results"] if item["game_id"] == "ghost_game")
            self.assertEqual(saved_result["player_lines"], [])

    def test_locked_pick_obligations_block_trade_legality_and_value(self):
        with tempfile.TemporaryDirectory() as tmp:
            save_path = Path(tmp) / "pick_lock_save.json"
            save = create_league_save(ROOT, self.plain, "GSW", save_path, seed=405)
            active = canonical_with_save(self.plain, save)
            gsw = next(team for team in active["teams"] if team["abbrev"] == "GSW")
            pick = next(pick for pick in tradeable_picks_for_team(with_transaction_context(active), gsw["id"]) if int(pick.get("round") or 0) == 2 and str(pick.get("season")) >= "2027")
            save["locked_pick_assets"] = [pick["id"]]
            write_save(save_path, save)
            locked_active = with_transaction_context(canonical_with_save(self.plain, load_save(save_path)))
            locked_pick = next(item for item in locked_active["draft_picks"] if item["id"] == pick["id"])
            self.assertEqual(pick_asset_value(locked_pick, "balanced"), 0.0)
            report = evaluate_trade(locked_active, "GSW", "BOS", [{"kind": "pick", "value": pick["id"]}], [], seed=1)
            self.assertEqual(report["legality"]["status"], "illegal")
            self.assertTrue(any("locked" in issue.lower() for issue in report["legality"]["issues"]))

    def test_home_pending_line_only_shows_user_offers(self):
        with tempfile.TemporaryDirectory() as tmp:
            save_path = Path(tmp) / "home_pending_save.json"
            save = create_league_save(ROOT, self.plain, "GSW", save_path, seed=410)
            save["pending_ai_actions"] = [{"id": "ai_action_test"}]
            save["news_items"].append({"id": "news_home_test", "date": "2025-10-01", "kind": "trade", "headline": "GSW made a factual league move.", "status": "unread"})
            add_league_event(save, "trade", "GSW made a factual league move.", date_value="2025-10-01")
            save["social_feed"].append(
                {
                    "id": "social_home_test",
                    "date": "2025-10-01",
                    "kind": "trade",
                    "text": "GSW timeline item should stay off the home dashboard.",
                    "author": "Test",
                    "handle": "@test",
                    "persona": "test",
                    "subject": "GSW timeline item",
                    "team_ids": ["team_gsw"],
                    "sentiment": 0,
                    "importance": 99,
                }
            )
            write_save(save_path, save)
            with redirect_stdout(StringIO()) as output:
                print_home(ROOT, self.plain, save_path)
            text = output.getvalue()
            self.assertIn("Pending: user offers 0", text)
            self.assertIn("11. Review AI trade offers to you", text)
            self.assertIn("Recent league events", text)
            self.assertNotIn("Recent league news", text)
            self.assertNotIn("Top of the timeline", text)
            self.assertNotIn("@test", text)
            self.assertNotIn("Pending AI / league actions", text)
            self.assertNotIn("AI 1", text)
            self.assertNotIn("staff decisions", text)

    def test_user_trade_offers_expire_after_trade_deadline(self):
        with tempfile.TemporaryDirectory() as tmp:
            save_path = Path(tmp) / "deadline_offer_save.json"
            save = create_league_save(ROOT, self.plain, "GSW", save_path, seed=417)
            save["state"] = {"current_date": "2026-02-04", "phase": "regular_season", "legal_actions": ["trades", "advance"]}
            save["user_trade_offers"] = [
                {
                    "id": "deadline_offer",
                    "proposal": {"id": "deadline_offer", "from_team_id": "team_gsw", "to_team_id": "team_bos"},
                    "offer_context": {"status": "pending_user_review", "created_date": "2026-02-04"},
                }
            ]
            write_save(save_path, save)
            before = pending_actions_view(self.plain, save_path)
            self.assertEqual(before["pending_counts"]["user_trade_offers"], 1)
            advance_save(ROOT, self.plain, save_path, to_date="2026-02-06", seed=417)
            saved = load_save(save_path)
            self.assertEqual(saved["user_trade_offers"][0]["offer_context"]["status"], "expired_trade_deadline")
            after = pending_actions_view(self.plain, save_path)
            self.assertEqual(after["pending_counts"]["user_trade_offers"], 0)

    def test_app_action_layer_creates_local_save_and_serves_core_payloads(self):
        with tempfile.TemporaryDirectory() as tmp:
            save_dir = Path(tmp) / "app_saves"
            runtime = dispatch_app_action("runtime_status", root=ROOT, save_dir=save_dir, canonical=self.plain)
            self.assertEqual(runtime["protocol_version"], APP_ACTION_PROTOCOL_VERSION)
            self.assertTrue(runtime["runtime"]["ios_standalone_target"])
            self.assertFalse(runtime["runtime"]["requires_remote_backend"])

            created = dispatch_app_action(
                "create_save",
                {"team": "GSW", "seed": 501, "save_name": "gui_smoke"},
                root=ROOT,
                save_dir=save_dir,
                canonical=self.plain,
            )
            save_path = created["save_path"]
            self.assertEqual(created["status"], "created")
            self.assertFalse(created["game_settings"]["press_conferences_enabled"])

            listed = dispatch_app_action("list_saves", root=ROOT, save_dir=save_dir, canonical=self.plain)
            self.assertEqual(listed["save_count"], 1)
            home = dispatch_app_action("home", {"save_path": save_path}, root=ROOT, save_dir=save_dir, canonical=self.plain)
            self.assertEqual(home["save"]["user_team"]["abbrev"], "GSW")
            self.assertIn("league_events", home)
            dashboard = dispatch_app_action("team_dashboard", {"save_path": save_path, "team": "GSW"}, root=ROOT, save_dir=save_dir, canonical=self.plain)
            self.assertEqual(dashboard["team"]["abbrev"], "GSW")
            self.assertIn("rotation", dashboard)
            self.assertIn("cap_by_year", dashboard)

            league_stats = dispatch_app_action("league_leaders", {"save_path": save_path, "stat": "points"}, root=ROOT, save_dir=save_dir, canonical=self.plain)
            self.assertEqual(league_stats["stat"], "points")
            league_traits = dispatch_app_action("league_traits", {"save_path": save_path, "trait": "overall"}, root=ROOT, save_dir=save_dir, canonical=self.plain)
            self.assertEqual(league_traits["rating_scale"], "dashboard_display")

            starter_slots = {str(idx): row["id"] for idx, row in enumerate(dashboard["rotation"][:5], start=1)}
            lineup = dispatch_app_action(
                "set_starting_five",
                {"save_path": save_path, "team": "GSW", "slots": starter_slots},
                root=ROOT,
                save_dir=save_dir,
                canonical=self.plain,
            )
            self.assertEqual(lineup["status"], "updated")
            self.assertEqual(len(lineup["dashboard"]["starting_five"]), 5)

            minutes = {row["id"]: 0 for row in dashboard["rotation"]}
            for row in dashboard["rotation"][:5]:
                minutes[row["id"]] = 48
            rotation = dispatch_app_action(
                "set_rotation_minutes",
                {"save_path": save_path, "team": "GSW", "minutes": minutes},
                root=ROOT,
                save_dir=save_dir,
                canonical=self.plain,
            )
            self.assertEqual(rotation["status"], "updated")
            self.assertEqual(rotation["total_minutes"], 240)

            assets = dispatch_app_action("team_assets", {"save_path": save_path, "team": "GSW"}, root=ROOT, save_dir=save_dir, canonical=self.plain)
            self.assertEqual(assets["team"]["abbrev"], "GSW")
            self.assertTrue(assets["players"])
            self.assertIn("hard_cap_space_millions", assets["cap"])

            staff_room = dispatch_app_action("staff_room", {"save_path": save_path, "team": "GSW", "limit": 5}, root=ROOT, save_dir=save_dir, canonical=self.plain)
            self.assertEqual(staff_room["team_report"]["team"]["abbrev"], "GSW")
            self.assertLessEqual(len(staff_room["market"]["candidates"]), 5)

            free_agency_room = dispatch_app_action("free_agency_room", {"save_path": save_path, "team": "GSW"}, root=ROOT, save_dir=save_dir, canonical=self.plain)
            self.assertEqual(free_agency_room["team"]["abbrev"], "GSW")
            self.assertIn("candidates", free_agency_room)

            draft_room = dispatch_app_action("draft_room", {"save_path": save_path, "team": "GSW", "seed": 501}, root=ROOT, save_dir=save_dir, canonical=self.plain)
            self.assertEqual(draft_room["state"]["status"], "locked_until_draft")
            self.assertIsNone(draft_room["current_selection"])
            self.assertTrue(draft_room["draft_board"]["entries"])

            playoff_room = dispatch_app_action("playoff_room", {"save_path": save_path}, root=ROOT, save_dir=save_dir, canonical=self.plain)
            self.assertIn("picture", playoff_room)
            self.assertIn("East", playoff_room["picture"])
            self.assertIn("West", playoff_room["picture"])
            self.assertIn("series", playoff_room)

            advanced = dispatch_app_action(
                "advance_save",
                {"save_path": save_path, "days": 1, "seed": 501, "process_ai": False},
                root=ROOT,
                save_dir=save_dir,
                canonical=self.plain,
            )
            self.assertEqual(advanced["status"], "advanced")
            reloaded = load_save(save_path)
            self.assertEqual(reloaded["state"]["current_date"], "2025-10-02")
            self.assertFalse(press_conferences_enabled(reloaded))

            updated = dispatch_app_action(
                "update_game_settings",
                {"save_path": save_path, "settings": {"press_conferences_enabled": True}},
                root=ROOT,
                save_dir=save_dir,
                canonical=self.plain,
            )
            self.assertTrue(updated["press_conferences_enabled"])
            self.assertIn("press_conferences", load_save(save_path)["state"]["legal_actions"])

    def test_local_gui_server_serves_static_assets_and_json_actions(self):
        with tempfile.TemporaryDirectory() as tmp:
            save_dir = Path(tmp) / "gui_saves"
            server = make_gui_server(root=ROOT, save_dir=save_dir, host="127.0.0.1", port=0)
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()
            base_url = f"http://127.0.0.1:{server.server_address[1]}"

            def post_action(action: str, payload: dict | None = None) -> dict:
                body = json.dumps({"action": action, "payload": payload or {}}).encode("utf-8")
                req = urlrequest.Request(
                    f"{base_url}/api/action",
                    data=body,
                    headers={"Content-Type": "application/json"},
                    method="POST",
                )
                with urlrequest.urlopen(req, timeout=30) as response:
                    data = json.loads(response.read().decode("utf-8"))
                self.assertTrue(data["ok"], data)
                return data["result"]

            try:
                with urlrequest.urlopen(f"{base_url}/", timeout=30) as response:
                    index = response.read().decode("utf-8")
                self.assertIn("NBA GM Sandbox", index)
                teams = post_action("teams")
                self.assertIn("GSW", {team["abbrev"] for team in teams["teams"]})
                created = post_action("create_save", {"team": "GSW", "seed": 511, "save_name": "server_gui_smoke"})
                save_path = created["save_path"]
                home = post_action("home", {"save_path": save_path})
                self.assertEqual(home["save"]["user_team"]["abbrev"], "GSW")
            finally:
                server.shutdown()
                server.server_close()
                thread.join(timeout=30)

    def test_press_conferences_are_disabled_as_forced_interruptions_by_default(self):
        with tempfile.TemporaryDirectory() as tmp:
            save_path = Path(tmp) / "press_disabled_save.json"
            save = create_league_save(ROOT, self.plain, "GSW", save_path, seed=418)
            save["state"] = {"current_date": "2025-10-21", "phase": "regular_season", "legal_actions": ["trades", "advance"]}
            save["pending_press_events"] = [
                {
                    "id": "pending_press_disabled",
                    "kind": "trade",
                    "date": "2025-10-21",
                    "headline": "GSW makes a test move.",
                    "team_ids": ["team_gsw"],
                }
            ]
            write_save(save_path, save)
            result = handle_forced_phase(ROOT, self.plain, save_path, seed=418)
            self.assertIsNone(result)
            saved = ensure_league_save_defaults(load_save(save_path), self.plain)
            self.assertFalse(press_conferences_enabled(saved))
            self.assertEqual(len(saved["pending_press_events"]), 1)
            self.assertNotIn("press_conferences", saved["state"]["legal_actions"])

    def test_press_and_game_news_do_not_create_league_events(self):
        save = {"state": {"current_date": "2025-11-01"}, "news_items": [], "league_events": [], "social_feed": []}
        add_news(save, "press_conference", "GSW GM press conference: staff moves (accountable).")
        add_news(save, "game_result", "GSW 120, LAL 118.")
        add_news(save, "extension", "GSW extends Stephen Curry to $40.0M x 1.")
        headlines = [event.get("headline") for event in save.get("league_events", [])]
        self.assertEqual(headlines, ["GSW extends Stephen Curry to $40.0M x 1."])

    def test_narrative_social_generation_is_lazy_cached_and_optional(self):
        class FakeProvider:
            name = "fake"

            def __init__(self):
                self.calls = 0

            def generate_json(self, prompt, settings):
                self.calls += 1
                return {"text": "GSW trade math is spicy, but the rotation fit has to prove it quickly."}

        with tempfile.TemporaryDirectory() as tmp:
            save_path = Path(tmp) / "narrative_social.json"
            save = create_league_save(ROOT, self.plain, "GSW", save_path, seed=411)
            save["social_feed"].append(
                {
                    "id": "social_gsw_trade",
                    "date": "2025-10-01",
                    "kind": "trade",
                    "text": "GSW completes a trade.",
                    "author": "System",
                    "handle": "@system",
                    "persona": "template",
                    "subject": "GSW completes a trade",
                    "team_ids": ["team_gsw"],
                    "sentiment": 0,
                    "importance": 90,
                }
            )
            write_save(save_path, save)
            provider = FakeProvider()
            update_narrative_settings(save_path, enabled=True, provider="ollama", max_posts_per_view=4)
            first = social_feed_view(self.plain, save_path, "GSW", limit=3, narrative_provider=provider)
            saved_after_first = load_save(save_path)
            saved_after_first["team_records"]["team_gsw"]["wins"] += 3
            saved_after_first["social_feed"][0]["narrative"] = {"source": "stale_hydrated_copy_should_not_affect_cache"}
            write_save(save_path, saved_after_first)
            second = social_feed_view(self.plain, save_path, "GSW", limit=3, narrative_provider=provider)
            self.assertEqual(provider.calls, 1)
            self.assertIn("rotation fit", first["items"][0]["text"])
            self.assertEqual(first["items"][0]["text"], second["items"][0]["text"])
            status = narrative_settings_view(save_path)
            self.assertEqual(status["cache_counts"]["social"], 1)

    def test_narrative_model_switch_retries_cached_fallback_and_qwen_thinking_json(self):
        class FakeHTTPResponse:
            def __enter__(self):
                return self

            def __exit__(self, exc_type, exc, tb):
                return False

            def read(self):
                return json.dumps(
                    {
                        "response": "",
                        "thinking": json.dumps(
                            {"text": "qwen works", "author": "A", "handle": "@a", "persona": "test"}
                        ),
                    }
                ).encode("utf-8")

        class FailingProvider:
            name = "ollama"

            def generate_json(self, prompt, settings):
                raise NarrativeProviderError("old model failed")

        class WorkingProvider:
            name = "ollama"

            def __init__(self):
                self.calls = 0

            def generate_json(self, prompt, settings):
                self.calls += 1
                return {"text": "New model writes this with real rotation context."}

        with patch("nba_gm_data.narrative.urllib.request.urlopen", return_value=FakeHTTPResponse()):
            parsed = OllamaNarrativeProvider().generate_json(
                "Return JSON.",
                {**default_narrative_settings(), "ollama_model": "qwen3.5:4b"},
            )
        self.assertEqual(parsed["text"], "qwen works")

        with tempfile.TemporaryDirectory() as tmp:
            save_path = Path(tmp) / "narrative_model_switch.json"
            save = create_league_save(ROOT, self.plain, "GSW", save_path, seed=422)
            save["social_feed"].append(
                {
                    "id": "social_model_switch_trade",
                    "date": "2025-10-01",
                    "kind": "trade",
                    "text": "GSW completes a trade.",
                    "author": "System",
                    "handle": "@system",
                    "persona": "template",
                    "subject": "GSW completes a trade",
                    "team_ids": ["team_gsw"],
                    "sentiment": 0,
                    "importance": 90,
                }
            )
            write_save(save_path, save)
            update_narrative_settings(save_path, enabled=True, provider="ollama", ollama_model="llama3.1")
            fallback_view = social_feed_view(self.plain, save_path, "GSW", limit=1, narrative_provider=FailingProvider())
            self.assertEqual(fallback_view["items"][0]["narrative"]["source"], "fallback")
            update_narrative_settings(save_path, provider="ollama", ollama_model="qwen3.5:4b")
            provider = WorkingProvider()
            qwen_view = social_feed_view(self.plain, save_path, "GSW", limit=1, narrative_provider=provider)
            self.assertEqual(provider.calls, 1)
            self.assertEqual(qwen_view["items"][0]["narrative"]["source"], "ollama")
            self.assertIn("New model writes", qwen_view["items"][0]["text"])

    def test_extension_social_subject_includes_contract_terms(self):
        with tempfile.TemporaryDirectory() as tmp:
            save_path = Path(tmp) / "extension_social_terms.json"
            save = create_league_save(ROOT, self.plain, "GSW", save_path, seed=418)
            contract = {"annual_salary": 25_000_000, "years": 4, "original_contract_years": 4}
            save["league_events"].append(
                {
                    "id": "extension_terms_event",
                    "date": "2025-12-02",
                    "kind": "extension",
                    "headline": "UTA extends Keyonte George.",
                    "team_ids": ["team_uta"],
                    "player_ids": [],
                    "importance": 0.7,
                    "details": {"contract": contract, "annual_salary": 25_000_000, "years": 4},
                }
            )
            save["social_feed"].append(
                {
                    "id": "extension_terms_social",
                    "date": "2025-12-02",
                    "kind": "extension",
                    "text": "UTA extends Keyonte George. The extension table got serious.",
                    "author": "System",
                    "handle": "@system",
                    "persona": "template",
                    "subject": "UTA extends Keyonte George.",
                    "team_ids": ["team_uta"],
                    "sentiment": 0,
                    "importance": 76,
                }
            )
            write_save(save_path, save)
            update_narrative_settings(save_path, enabled=True, provider="fallback")
            view = social_feed_view(self.plain, save_path, "UTA", limit=1)
            self.assertIn("UTA extends Keyonte George to $25M x 4", view["items"][0]["narrative"]["display_subject"])
            self.assertNotIn("UTA extends Keyonte George to $25M x 4", view["items"][0]["text"])

    def test_extension_social_requires_sim_evidence_for_health_money_position_and_conference_claims(self):
        with tempfile.TemporaryDirectory() as tmp:
            save_path = Path(tmp) / "extension_social_context.json"
            save = create_league_save(ROOT, self.plain, "GSW", save_path, seed=421)
            for team_id, wins, losses in [
                ("team_nyk", 50, 20),
                ("team_bos", 45, 25),
                ("team_tor", 38, 32),
                ("team_okc", 52, 18),
                ("team_lac", 47, 23),
                ("team_sac", 1, 5),
            ]:
                save["team_records"][team_id]["wins"] = wins
                save["team_records"][team_id]["losses"] = losses
            players = {player["name"]: player for player in self.plain["players"]}
            persona = {"author": "Test", "handle": "@test", "persona": "tester"}

            def context_for(player_name, team_abbrev, annual, years, extra_events=None):
                player = players[player_name]
                team_id = player["team_id"]
                event = {
                    "id": f"extension_context_{player['id']}",
                    "date": "2025-11-01",
                    "kind": "extension",
                    "headline": f"{team_abbrev} extends {player_name} to ${annual / 1_000_000:.1f}M x {years}.",
                    "team_ids": [team_id],
                    "player_ids": [player["id"]],
                    "importance": 0.8,
                    "details": {
                        "player_id": player["id"],
                        "team_id": team_id,
                        "annual_salary": annual,
                        "years": years,
                        "contract": {"annual_salary": annual, "years": years, "original_contract_years": years},
                    },
                }
                item = {
                    "id": f"social_{player['id']}",
                    "date": "2025-11-01",
                    "kind": "extension",
                    "text": event["headline"],
                    "subject": event["headline"],
                    "team_ids": [team_id],
                    "player_ids": [player["id"]],
                }
                local_save = {**save, "league_events": [event, *(extra_events or [])]}
                return social_context_packet(self.plain, local_save, item, team_id=team_id)

            def context_with_cap(context, evidence, rows, posture):
                adjusted = json.loads(json.dumps(context))
                cap_context = {"rows": rows, "posture": posture, "evidence": evidence}
                adjusted["analysis"]["team_metrics"]["cap_context"] = cap_context
                adjusted["analysis"]["evidence_snippets"] = [
                    snippet
                    for snippet in adjusted["analysis"]["evidence_snippets"]
                    if not str(snippet).startswith("[Cap:")
                ] + [evidence]
                return adjusted

            zion_context = context_for("Zion Williamson", "NOP", 48_100_000, 4)
            self.assertEqual(zion_context["analysis"]["kind"], "extension")
            self.assertTrue(any("injury risk" in snippet for snippet in zion_context["analysis"]["evidence_snippets"]))
            zion_repaired = validate_social_payload(
                {"text": "Zion's extension got serious. Can he stay healthy and live up to the hype?"},
                zion_context,
                self.plain,
                persona,
            )
            self.assertIsNotNone(zion_repaired)
            self.assertIn("injury risk", zion_repaired["text"])
            cap_repaired = validate_social_payload(
                {"text": "This puts NOP in apron pain territory unless the room holds up."},
                zion_context,
                self.plain,
                persona,
            )
            self.assertIsNotNone(cap_repaired)
            self.assertIn("hard-cap pressure", cap_repaired["text"])
            self.assertIn("[Cap:", cap_repaired["text"])
            self.assertIsNone(
                validate_social_payload(
                    {"text": "Zion has only played 6 games, so the health bet is scary."},
                    zion_context,
                    self.plain,
                    persona,
                )
            )
            health_snippet = next(snippet for snippet in zion_context["analysis"]["evidence_snippets"] if "injury risk" in snippet)
            self.assertIsNotNone(
                validate_social_payload(
                    {"text": f"Big swing, but the health variable has to be real {health_snippet}."},
                    zion_context,
                    self.plain,
                    persona,
                )
            )

            save["team_records"]["team_tor"]["wins"] = 6
            save["team_records"]["team_tor"]["losses"] = 0
            ingram_id = players["Brandon Ingram"]["id"]
            save["player_season_stats"][ingram_id] = {"games": 6, "points": 120, "rebounds": 30, "assists": 24, "minutes": 204}
            early_ingram_context = context_for("Brandon Ingram", "TOR", 27_300_000, 3)
            self.assertFalse(any("6/6 GP" in snippet for snippet in early_ingram_context["analysis"]["evidence_snippets"]))
            self.assertIsNone(
                validate_social_payload(
                    {"text": "Only 6 games played makes this a durability bet."},
                    early_ingram_context,
                    self.plain,
                    persona,
                )
            )
            save["team_records"]["team_tor"]["wins"] = 38
            save["team_records"]["team_tor"]["losses"] = 32
            save["player_season_stats"].pop(ingram_id, None)

            jrue_context = context_for("Jrue Holiday", "POR", 25_300_000, 2)
            self.assertIsNone(
                validate_social_payload(
                    {"text": f"POR found its PG of the future {jrue_context['analysis']['evidence_snippets'][1]}."},
                    jrue_context,
                    self.plain,
                    persona,
                )
            )

            wemby_context = context_for("Victor Wembanyama", "SAS", 53_500_000, 5)
            self.assertIsNone(
                validate_social_payload(
                    {"text": f"Five years at $53.5M is roughly $10M AAV, which is a bargain {wemby_context['analysis']['evidence_snippets'][1]}."},
                    wemby_context,
                    self.plain,
                    persona,
                )
            )

            deni_context = context_for("Deni Avdija", "POR", 25_300_000, 4)
            self.assertIsNone(
                validate_social_payload(
                    {"text": "This is a cap-sheet debate, full stop. [West top: OKC 6-0 #1, UTA 5-0 #2] [Contract: $25.3M x 4 AAV, total $101.2M]"},
                    deni_context,
                    self.plain,
                    persona,
                )
            )
            self.assertIsNone(
                validate_social_payload(
                    {"text": "They're locking in Avdija on an annual avg of $63M, but the fit is real. [Contract: $25.3M x 4 AAV, total $101.2M]"},
                    deni_context,
                    self.plain,
                    persona,
                )
            )
            cleaned_deni = validate_social_payload(
                {"text": "[This is a real cap opinion with actual numbers.] [Contract: $25.3M x 4 AAV, total $101.2M][1]"},
                deni_context,
                self.plain,
                persona,
            )
            self.assertIsNotNone(cleaned_deni)
            self.assertNotIn("[1]", cleaned_deni["text"])
            self.assertFalse(cleaned_deni["text"].startswith("[This"))

            ingram_context = context_for("Brandon Ingram", "TOR", 27_300_000, 3)
            self.assertIsNone(
                validate_social_payload(
                    {"text": f"TOR has to chase the East's top teams; LAC and OKC are holding strong spots {ingram_context['analysis']['evidence_snippets'][1]}."},
                    ingram_context,
                    self.plain,
                    persona,
                )
            )
            east_snippet = next(snippet for snippet in ingram_context["analysis"]["optional_context_snippets"] if "East top" in snippet)
            ingram_rating_snippet = next(snippet for snippet in ingram_context["analysis"]["evidence_snippets"] if "Ratings:" in snippet)
            self.assertIsNotNone(
                validate_social_payload(
                    {"text": f"TOR's next question is the actual East ladder {east_snippet}, and the player case is real {ingram_rating_snippet}."},
                    ingram_context,
                    self.plain,
                    persona,
                )
            )

            bilal_context = context_for("Bilal Coulibaly", "WAS", 21_900_000, 4)
            self.assertEqual(bilal_context["analysis"]["player"]["position"], "SF")
            self.assertIsNone(
                validate_social_payload(
                    {"text": f"Solid move, but how does it fix the backcourt {bilal_context['analysis']['evidence_snippets'][1]}?"},
                    bilal_context,
                    self.plain,
                    persona,
                )
            )

            sabonis_context = context_for("Domantas Sabonis", "SAC", 25_700_000, 3)
            self.assertIsNone(
                validate_social_payload(
                    {"text": f"Next question is how this impacts SAC's playoff push {sabonis_context['analysis']['evidence_snippets'][1]}."},
                    sabonis_context,
                    self.plain,
                    persona,
                )
            )
            healthy_cap = "[Cap: 2026-27 payroll $148.7M, cap room $+45.8M, hard-cap room $+66.4M; 2027-28 payroll $109.5M, cap room $+91.8M, hard-cap room $+113.1M]"
            ja_context = context_with_cap(
                context_for("Ja Morant", "MEM", 47_300_000, 5),
                healthy_cap,
                [
                    {"season": "2026-27", "cap_space_millions": 45.8, "hard_cap_space_millions": 66.4},
                    {"season": "2027-28", "cap_space_millions": 91.8, "hard_cap_space_millions": 113.1},
                ],
                "healthy_space",
            )
            self.assertIsNone(
                validate_social_payload(
                    {"text": f"Ja Morant's deal puts MEM in a tough cap spot next year. {healthy_cap}"},
                    ja_context,
                    self.plain,
                    persona,
                )
            )
            self.assertIsNotNone(
                validate_social_payload(
                    {"text": f"Expensive deal, but MEM still has room to maneuver. {healthy_cap}"},
                    ja_context,
                    self.plain,
                    persona,
                )
            )
            tight_cap = "[Cap: 2026-27 payroll $217.0M, cap room $-22.5M, hard-cap room $-1.9M; 2027-28 payroll $221.7M, cap room $-20.4M, hard-cap room $+0.8M]"
            black_context = context_with_cap(
                context_for("Anthony Black", "ORL", 21_900_000, 4),
                tight_cap,
                [
                    {"season": "2026-27", "cap_space_millions": -22.5, "hard_cap_space_millions": -1.9},
                    {"season": "2027-28", "cap_space_millions": -20.4, "hard_cap_space_millions": 0.8},
                ],
                "tight",
            )
            self.assertIsNotNone(
                validate_social_payload(
                    {"text": f"That is real cap pressure unless the roster math changes. {tight_cap}"},
                    black_context,
                    self.plain,
                    persona,
                )
            )
            bilal = players["Bilal Coulibaly"]
            trae = players["Trae Young"]
            unresolved_event = {
                "id": "extension_context_trae_unresolved",
                "date": "2025-11-01",
                "kind": "extension",
                "headline": "WAS and Trae Young leave extension talks unresolved: extension talks remain unresolved.",
                "team_ids": [bilal["team_id"]],
                "player_ids": [trae["id"]],
                "details": {
                    "player_id": trae["id"],
                    "team_id": bilal["team_id"],
                    "reason": "extension talks remain unresolved",
                },
            }
            bilal_board_context = context_for("Bilal Coulibaly", "WAS", 21_900_000, 4, extra_events=[unresolved_event])
            board_snippet = next(
                snippet for snippet in bilal_board_context["analysis"]["optional_context_snippets"]
                if "extension board:" in snippet
            )
            self.assertIn("Trae Young unresolved", board_snippet)
            self.assertIn("backcourt money still undecided", board_snippet)
            bilal_rating_snippet = next(snippet for snippet in bilal_board_context["analysis"]["evidence_snippets"] if "Ratings:" in snippet)
            self.assertIsNotNone(
                validate_social_payload(
                    {"text": f"This reads like WAS paid the wing first while the backcourt money stays unresolved. {board_snippet} {bilal_rating_snippet}"},
                    bilal_board_context,
                    self.plain,
                    persona,
                )
            )
            wemby_rank_context = context_for("Victor Wembanyama", "SAS", 53_500_000, 5)
            team_rank_snippet = next(
                snippet for snippet in wemby_rank_context["analysis"]["optional_context_snippets"]
                if "team playmaking rank" in snippet
            )
            rank = wemby_rank_context["analysis"]["team_metrics"]["playmaking_rank"]["rank"]
            self.assertIn("team playmaking rank", team_rank_snippet)
            self.assertIn("player PLY", team_rank_snippet)
            wemby_rating_snippet = next(snippet for snippet in wemby_rank_context["analysis"]["evidence_snippets"] if "Ratings:" in snippet)
            self.assertIsNone(
                validate_social_payload(
                    {"text": f"Wembanyama is PLY rank #{rank}, which makes this deal a playmaking bet. {wemby_rating_snippet}"},
                    wemby_rank_context,
                    self.plain,
                    persona,
                )
            )
            self.assertIsNotNone(
                validate_social_payload(
                    {"text": f"SAS has a team playmaking rank #{rank}, while Wembanyama is the player bet here. {team_rank_snippet} {wemby_rating_snippet}"},
                    wemby_rank_context,
                    self.plain,
                    persona,
                )
            )

    def test_social_timeline_marks_fallback_posts_red_when_terminal_supports_color(self):
        item = {
            "subject": "WAS extends Bilal Coulibaly to $21.3M x 4.",
            "text": "Good teams keep the right guys before the market gets weird.",
            "persona": "template",
            "narrative": {
                "source": "fallback",
                "display_subject": "WAS extends Bilal Coulibaly to $21.3M x 4.",
            },
        }
        with patch("nba_gm_data.play.sys.stdout.isatty", return_value=True), patch.dict(os.environ, {"NO_COLOR": ""}):
            rendered = social_timeline_text(item)
            lines = social_timeline_lines(item, width=58)
        self.assertIn("\033[1;31mGood teams keep the right guys", rendered)
        self.assertTrue(any("\033[1;31mGood teams keep" in line for line in lines[1:]))

    def test_social_timeline_wraps_long_generated_posts_without_truncating_evidence(self):
        cap_snippet = "[Cap: 2026-27 payroll $174.5M, cap room $+20.0M, hard-cap room $+40.6M; 2027-28 payroll $122.1M, cap room $+79.2M, hard-cap room $+99.8M]"
        body = (
            "The cap implications here are real, but the story is not a crisis. WAS can still move carefully around the "
            f"next Trae decision. {cap_snippet}"
        )
        item = {
            "date": "2025-10-21",
            "handle": "@jules_on_hoops",
            "sentiment": 0.0,
            "subject": "WAS and Trae Young leave extension talks unresolved: extension talks remain unresolved.",
            "text": body,
            "narrative": {
                "source": "ollama",
                "display_subject": "WAS and Trae Young leave extension talks unresolved: extension talks remain unresolved.",
            },
        }
        lines = social_timeline_lines(item, width=92)
        joined = " ".join(line.strip() for line in lines)
        self.assertGreater(len(lines), 3)
        self.assertIn(cap_snippet, joined)
        self.assertTrue(joined.endswith("]"))
        self.assertNotIn(" har", joined[-8:])

    def test_narrative_provider_failure_falls_back_without_breaking_social(self):
        class FailingProvider:
            name = "fake"

            def generate_json(self, prompt, settings):
                raise NarrativeProviderError("offline")

        with tempfile.TemporaryDirectory() as tmp:
            save_path = Path(tmp) / "narrative_fallback.json"
            save = create_league_save(ROOT, self.plain, "GSW", save_path, seed=412)
            save["social_feed"].append(
                {
                    "id": "social_gsw_injury",
                    "date": "2025-10-01",
                    "kind": "injury",
                    "text": "Stephen Curry expected to miss 12 games for GSW.",
                    "author": "System",
                    "handle": "@system",
                    "persona": "template",
                    "subject": "Stephen Curry expected to miss 12 games",
                    "team_ids": ["team_gsw"],
                    "player_ids": ["player_stephen-curry"],
                    "sentiment": -0.2,
                    "importance": 95,
                }
            )
            write_save(save_path, save)
            update_narrative_settings(save_path, enabled=True, provider="ollama")
            view = social_feed_view(self.plain, save_path, "GSW", limit=1, narrative_provider=FailingProvider())
            self.assertEqual(view["item_count"], 1)
            self.assertIn("Depth", view["items"][0]["text"])
            saved = load_save(save_path)
            cached = next(iter(saved["narrative_cache"]["social"].values()))
            self.assertEqual(cached["source"], "fallback")

            save["social_feed"] = [
                {
                    "id": "social_gsw_player_high",
                    "date": "2025-10-02",
                    "kind": "player_high",
                    "text": "Stephen Curry posted a season-high watch line: 51 points for GSW.",
                    "author": "System",
                    "handle": "@system",
                    "persona": "template",
                    "subject": "Stephen Curry posted a season-high watch line: 51 points for GSW",
                    "team_ids": ["team_gsw"],
                    "player_ids": ["player_stephen-curry"],
                    "sentiment": 0.1,
                    "importance": 95,
                }
            ]
            save["league_events"] = [
                {
                    "id": "player_high_event",
                    "date": "2025-10-02",
                    "kind": "major_stat_line",
                    "headline": "Stephen Curry recorded 51 points for GSW.",
                    "team_ids": ["team_gsw"],
                    "player_ids": ["player_stephen-curry"],
                    "details": {"player_id": "player_stephen-curry", "stat": "points", "value": 51},
                }
            ]
            save["narrative_cache"] = {"version": NARRATIVE_PROMPT_VERSION, "social": {}, "press": {}}
            write_save(save_path, save)
            high_view = social_feed_view(self.plain, save_path, "GSW", limit=1, narrative_provider=FailingProvider())
            self.assertNotIn("React to the actual game", high_view["items"][0]["text"])
            self.assertNotIn("folklore", high_view["items"][0]["text"])

    def test_narrative_validators_reject_unsafe_or_malformed_output(self):
        save = {"version": "league_save_v1", "state": {"current_date": "2025-10-01", "phase": "regular_season"}, "team_records": {}}
        item = {"id": "social_test", "date": "2025-10-01", "kind": "trade", "text": "GSW completed a trade.", "subject": "GSW completed a trade", "team_ids": ["team_gsw"]}
        context = social_context_packet(self.plain, save, item, team_id="team_gsw")
        persona = {"author": "Test", "handle": "@test", "persona": "tester"}
        core_names = {
            player["name"]
            for team in context.get("team_context", [])
            for player in team.get("core_players", [])
        }
        self.assertIn("Stephen Curry", core_names)
        self.assertIsNotNone(
            validate_social_payload(
                {"text": "GSW can still make this work next to Stephen Curry if the spacing math holds."},
                context,
                self.plain,
                persona,
            )
        )
        self.assertIsNone(validate_social_payload({"text": "LAL is involved even though the context only says GSW made this move."}, context, self.plain, persona))
        self.assertIsNone(validate_social_payload({"text": "According to ESPN, this real life locker room has always hated the coach."}, context, self.plain, persona))
        self.assertIsNone(validate_social_payload({"text": "The trade significantly alters roster construction implications. Watching closely."}, context, self.plain, persona))
        self.assertIsNone(validate_social_payload({"text": "GSW needs a new OG to space the floor for DeMar after this."}, context, self.plain, persona))
        self.assertIsNone(validate_social_payload({"text": "Tom Thibodeau is going to love this second-unit wrinkle."}, context, self.plain, persona))
        press_context = {
            "topic": "trade",
            "team": {"abbrev": "GSW"},
            "event": {"headline": "GSW completed a trade"},
            "involved_teams": [{"abbrev": "GSW"}],
        }
        bad_press = {
            "reporter": {"name": "Dana Price", "beat": "accountability", "question": "GSW completed a trade. What is the plan now?"},
            "answers": [
                {"line": "This is the correct answer for the room.", "tone": "accountable", "quality": "good", "rationale": "too obvious"},
                {"line": "We believe in the upside but have to show it.", "tone": "optimistic", "quality": "mixed", "rationale": "ok"},
                {"line": "No details today, the work stays internal.", "tone": "deflect", "quality": "bad", "rationale": "evasive"},
                {"line": "The standard has to rise immediately.", "tone": "challenge", "quality": "mixed", "rationale": "ok"},
            ],
        }
        self.assertIsNone(validate_press_payload(bad_press, press_context, self.plain))

    def test_narrative_trade_context_uses_actual_teams_and_pick_facts(self):
        gsw_player = next(player for player in self.plain["players"] if player["name"] == "Stephen Curry")
        bos_player = next(player for player in self.plain["players"] if player["team_id"] == "team_bos" and float(player.get("minutes_projection") or 0.0) >= 20)
        save = {
            "version": "league_save_v1",
            "state": {"current_date": "2025-10-01", "phase": "regular_season"},
            "team_records": {},
            "league_events": [
                {
                    "id": "trade_context_test",
                    "date": "2025-10-01",
                    "kind": "trade",
                    "headline": f"Trade completed: {gsw_player['name']} for {bos_player['name']}.",
                    "team_ids": ["team_gsw", "team_bos"],
                    "player_ids": [gsw_player["id"], bos_player["id"]],
                    "importance": 0.7,
                    "details": {
                        "from_team_id": "team_gsw",
                        "to_team_id": "team_bos",
                        "from_assets": [{"kind": "player", "id": gsw_player["id"], "label": gsw_player["name"]}],
                        "to_assets": [{"kind": "player", "id": bos_player["id"], "label": bos_player["name"]}],
                    },
                }
            ],
        }
        item = {
            "id": "social_trade_context_test",
            "date": "2025-10-01",
            "kind": "trade",
            "text": f"Trade completed: {gsw_player['name']} for {bos_player['name']}.",
            "subject": f"Trade completed: {gsw_player['name']} for {bos_player['name']}",
            "team_ids": [],
        }
        context = social_context_packet(self.plain, save, item, team_id="team_orl")
        teams = {team["abbrev"] for team in context.get("involved_teams", [])}
        self.assertEqual(teams, {"BOS", "GSW"})
        self.assertIn("GSW sends", context["source"]["display_subject"])
        persona = {"author": "Test", "handle": "@test", "persona": "tester"}
        self.assertIsNone(validate_social_payload({"text": "What does this mean for ORL's playoff push?"}, context, self.plain, persona))
        self.assertIsNone(validate_social_payload({"text": "The pick math makes this whole trade hilarious."}, context, self.plain, persona))
        self.assertIsNone(validate_social_payload({"text": f"BOS sent {gsw_player['name']} away for cleaner role math."}, context, self.plain, persona))
        self.assertIsNone(validate_social_payload({"text": f"The Celtics did not overpay for {bos_player['name']} here."}, context, self.plain, persona))
        self.assertIsNone(validate_social_payload({"text": f"{gsw_player['name']}'s salary is $999M, so the cap sheet is cooked."}, context, self.plain, persona))
        self.assertIsNotNone(validate_social_payload({"text": "GSW got cleaner role math, but BOS has to justify the roster swing fast."}, context, self.plain, persona))

    def test_narrative_rejects_protected_pick_claim_without_protected_pick_context(self):
        gsw_player = next(player for player in self.plain["players"] if player["name"] == "Stephen Curry")
        pick = next(pick for pick in self.plain["draft_picks"] if pick.get("current_owner_team_id") == "team_bos" and int(pick.get("round") or 0) == 2)
        save = {
            "version": "league_save_v1",
            "state": {"current_date": "2025-10-01", "phase": "regular_season"},
            "team_records": {},
            "league_events": [
                {
                    "id": "unprotected_pick_trade_test",
                    "date": "2025-10-01",
                    "kind": "trade",
                    "headline": f"Trade completed: {gsw_player['name']} for {pick['season']} R2 BOS.",
                    "team_ids": ["team_gsw", "team_bos"],
                    "player_ids": [gsw_player["id"]],
                    "importance": 0.7,
                    "details": {
                        "from_team_id": "team_gsw",
                        "to_team_id": "team_bos",
                        "from_assets": [{"kind": "player", "id": gsw_player["id"], "label": gsw_player["name"]}],
                        "to_assets": [{"kind": "pick", "id": pick["id"], "label": f"{pick['season']} R2 BOS (own pick)", "round": 2, "season": pick["season"]}],
                    },
                }
            ],
        }
        item = {
            "id": "social_unprotected_pick_trade_test",
            "date": "2025-10-01",
            "kind": "trade",
            "text": f"Trade completed: {gsw_player['name']} for {pick['season']} R2 BOS.",
            "subject": f"Trade completed: {gsw_player['name']} for {pick['season']} R2 BOS",
            "team_ids": [],
        }
        context = social_context_packet(self.plain, save, item)
        self.assertTrue(context["analysis"]["asset_mix"]["has_picks"])
        self.assertEqual(context["analysis"]["asset_mix"]["protected_picks"], 0)
        persona = {"author": "Test", "handle": "@test", "persona": "tester"}
        self.assertIsNone(validate_social_payload({"text": "That protected second-round pick is sneakier than people think."}, context, self.plain, persona))
        self.assertIsNotNone(validate_social_payload({"text": "One R2 is not premium capital, so the player fit has to carry the argument."}, context, self.plain, persona))

    def test_narrative_defaults_timeout_ceiling_and_social_subject_prefix(self):
        defaults = default_narrative_settings()
        self.assertTrue(defaults["enabled"])
        self.assertEqual(defaults["timeout_seconds"], 45.0)
        self.assertEqual(defaults["max_posts_per_view"], 12)
        with tempfile.TemporaryDirectory() as tmp:
            save_path = Path(tmp) / "narrative_defaults.json"
            save = create_league_save(ROOT, self.plain, "GSW", save_path, seed=419)
            write_save(save_path, save)
            update_narrative_settings(save_path, timeout_seconds=90.0, max_posts_per_view=40)
            status = narrative_settings_view(save_path)
            self.assertEqual(status["timeout_seconds"], 90.0)
            self.assertEqual(status["max_posts_per_view"], 40)
        item = {
            "subject": "UTA extends Keyonte George to $25M x 4.",
            "text": "Fine if the role is real. Ugly if this is just paying for comfort.",
            "narrative": {"display_subject": "UTA extends Keyonte George to $25M x 4."},
        }
        rendered = social_timeline_text(item)
        self.assertTrue(rendered.startswith("UTA extends Keyonte George to $25M x 4."))
        self.assertIn("\n  Fine if the role is real", rendered)
        self.assertIn("Fine if the role is real", rendered)

    def test_narrative_press_generation_is_cached_and_bounded(self):
        class FakePressProvider:
            name = "fake"

            def __init__(self):
                self.calls = 0

            def generate_json(self, prompt, settings):
                self.calls += 1
                return {
                    "reporter": {
                        "name": "Miles Kwon",
                        "beat": "transactions and cap pressure",
                        "question": "GSW completed a trade. What basketball problem did this move have to solve?",
                    },
                    "answers": [
                        {"line": "We paid a real price because standing still had a price too.", "tone": "accountable", "quality": "good", "rationale": "owns the cost"},
                        {"line": "The fit gives us a cleaner way to play, but it has to show quickly.", "tone": "optimistic", "quality": "good", "rationale": "positive but grounded"},
                        {"line": "This should sharpen everyone because roles are not guaranteed.", "tone": "challenge", "quality": "mixed", "rationale": "useful but risky"},
                        {"line": "We are not going to explain the asset math from the podium.", "tone": "deflect", "quality": "bad", "rationale": "too evasive"},
                    ],
                }

        with tempfile.TemporaryDirectory() as tmp:
            save_path = Path(tmp) / "narrative_press.json"
            save = create_league_save(ROOT, self.plain, "GSW", save_path, seed=413)
            update_narrative_settings(save_path, enabled=True, provider="ollama")
            save = load_save(save_path)
            event = {"id": "press_trade_test", "kind": "trades", "headline": "GSW completed a trade.", "question": "How do you defend the move?"}
            base_prompt = {"topic": "trade", "reporters": [{"name": "Dana Price", "question": "GSW completed a trade. What now?"}]}
            provider = FakePressProvider()
            first = press_cache_entry(self.plain, save, "team_gsw", event, base_prompt, provider=provider)
            second = press_cache_entry(self.plain, save, "team_gsw", event, base_prompt, provider=provider)
            self.assertEqual(provider.calls, 1)
            self.assertEqual(first["id"], second["id"])
            self.assertEqual(len(first["answers"]), 4)
            self.assertTrue({answer["tone"] for answer in first["answers"]}.issubset({"accountable", "optimistic", "deflect", "challenge"}))

    def test_narrative_generation_does_not_run_during_save_advancement(self):
        with tempfile.TemporaryDirectory() as tmp:
            save_path = Path(tmp) / "narrative_advance.json"
            create_league_save(ROOT, self.plain, "GSW", save_path, seed=414)
            update_narrative_settings(save_path, enabled=True, provider="ollama")
            before = narrative_settings_view(save_path)
            advance_save(ROOT, self.plain, save_path, to_date="2025-10-21", seed=414)
            after = narrative_settings_view(save_path)
            self.assertEqual(before["cache_counts"], after["cache_counts"])

    def test_narrative_settings_cli_updates_save_without_requiring_ollama(self):
        with tempfile.TemporaryDirectory() as tmp:
            save_path = Path(tmp) / "narrative_cli.json"
            create_league_save(ROOT, self.plain, "GSW", save_path, seed=415)
            stdout = StringIO()
            with redirect_stdout(stdout):
                code = cli_main([
                    "--root",
                    str(ROOT),
                    "narrative-settings",
                    "--save",
                    str(save_path),
                    "--enable",
                    "--provider",
                    "ollama",
                    "--model",
                    "llama3.1",
                    "--max-posts",
                    "3",
                ])
            self.assertEqual(code, 0)
            payload = json.loads(stdout.getvalue())
            self.assertTrue(payload["enabled"])
            self.assertEqual(payload["max_posts_per_view"], 3)
            saved = load_save(save_path)
            self.assertTrue(saved["narrative_settings"]["enabled"])

    def test_narrative_status_explains_missing_ollama_model(self):
        class MissingModelProvider:
            name = "fake"

            def generate_json(self, prompt, settings):
                raise NarrativeProviderError("model 'llama3.1' not found")

        save = {
            "version": "league_save_v1",
            "narrative_settings": {"enabled": True, "provider": "ollama", "ollama_model": "llama3.1"},
            "narrative_cache": {"version": "narrative_v1", "social": {}, "press": {}},
        }
        with patch("nba_gm_data.narrative.ollama_available_models", return_value=["gemma4:e4b"]):
            status = narrative_status(save, provider=MissingModelProvider())
        self.assertIn("model 'llama3.1' not found", status["connection"])
        self.assertIn("Available local models: gemma4:e4b", status["connection"])
        self.assertIn("ollama pull llama3.1", status["connection"])

    def test_single_generated_press_reporter_skips_reporter_selection_prompt(self):
        with tempfile.TemporaryDirectory() as tmp:
            save_path = Path(tmp) / "narrative_press_room.json"
            create_league_save(ROOT, self.plain, "GSW", save_path, seed=416)
            update_narrative_settings(save_path, enabled=True, provider="fallback")
            event = {
                "id": "press_staff_test",
                "date": "2025-10-01",
                "kind": "staff_moves",
                "headline": "GSW hires a new head coach.",
                "question": "What should change because of the hire?",
            }
            with patch("builtins.input", side_effect=["1", ""]), redirect_stdout(StringIO()) as output:
                press_room(self.plain, save_path, "GSW", seed=416, event=event)
            text = output.getvalue()
            self.assertNotIn("Choose a reporter.", text)
            self.assertIn("Dana Price:", text)
            saved = load_save(save_path)
            self.assertEqual(saved["press_conferences"][-1]["narrative"]["source"], "fallback")

    def test_aggregated_press_fallback_asks_about_move_pattern(self):
        with tempfile.TemporaryDirectory() as tmp:
            save = create_league_save(ROOT, self.plain, "GSW", Path(tmp) / "aggregate_press.json", seed=419)
            save["narrative_settings"] = {**default_narrative_settings(), "enabled": True, "provider": "fallback"}
            event = {
                "id": "press_aggregate_test",
                "date": "2025-12-02",
                "kind": "staff_moves",
                "headline": "2 staff moves require GM availability.",
                "headlines": ["GSW fires an offensive coordinator.", "GSW hires a new offensive coordinator."],
                "question": "How do these moves connect?",
            }
            base_prompt = {"topic": "staff moves", "reporters": [{"name": "Dana Price", "question": "How do these moves connect?"}]}
            entry = press_cache_entry(self.plain, save, "team_gsw", event, base_prompt)
            self.assertIn("2 related moves", entry["reporter"]["question"])
            self.assertIn("through-line", entry["reporter"]["question"])

    def test_pick_labels_and_protection_fallbacks_stay_readable_and_chronological(self):
        synthetic = {
            "teams": [
                {"id": "team_bkn", "abbrev": "BKN"},
                {"id": "team_nyk", "abbrev": "NYK"},
                {"id": "team_phi", "abbrev": "PHI"},
                {"id": "team_was", "abbrev": "WAS"},
            ]
        }
        provenance_pick = {"season": "2026", "round": 2, "original_team_id": "team_was", "current_owner_team_id": "team_nyk", "protections": "from WSH via OKC and HOU"}
        conditional_pick = {
            "season": "2028",
            "round": 1,
            "original_team_id": "team_bkn",
            "current_owner_team_id": "team_phi",
            "protections": "BKN If 9-30 and if PHI conveys 1st to OKC by 2026",
        }
        missing_team_pick = {"season": "2030", "round": 2, "original_team_id": None, "current_owner_team_id": "team_nyk"}
        raw_own_conditional_pick = {**conditional_pick, "current_owner_team_id": "team_bkn"}
        self.assertEqual(pick_label(synthetic, provenance_pick), "2026 R2 WAS (owned by NYK)")
        self.assertEqual(pick_label(synthetic, raw_own_conditional_pick), "2028 R1 BKN (own pick)")
        conditional_label = pick_label(synthetic, conditional_pick)
        self.assertNotIn("conveys", conditional_label.lower())
        self.assertNotIn("and if", conditional_label)
        self.assertNotIn("via", conditional_label)
        self.assertNotIn("...", conditional_label)
        swap_pick = {**conditional_pick, "protections": "BKN Or swap with BKN"}
        self.assertNotIn("swap", pick_label(synthetic, swap_pick).lower())
        single_if_pick = {**conditional_pick, "protections": "If 1"}
        self.assertNotIn("If 1", pick_label(synthetic, single_if_pick))
        frozen_pick = {**conditional_pick, "protections": "FROZEN PICK"}
        self.assertNotIn("FROZEN PICK", pick_label(synthetic, frozen_pick))
        self.assertNotIn("UNK", pick_label(synthetic, missing_team_pick))
        prompted = trade_result_with_pick_terms({"proposal": {"id": "unprotected_prompt"}}, [{"type": "unprotected", "primary_pick_id": "pick_test"}])
        self.assertTrue(prompted["pick_obligation_terms_prompted"])
        self.assertNotIn("pick_obligation_terms", prompted)

        with tempfile.TemporaryDirectory() as tmp:
            save_path = Path(tmp) / "fallback_year_save.json"
            save = create_league_save(ROOT, self.plain, "GSW", save_path, seed=409)
            active = with_transaction_context(canonical_with_save(self.plain, save))
            gsw = next(team for team in active["teams"] if team["abbrev"] == "GSW")
            firsts = sorted(
                [
                    pick for pick in tradeable_picks_for_team(active, gsw["id"])
                    if int(pick.get("round") or 0) == 1 and (pick_season_start(pick) or 0) >= 2028
                ],
                key=lambda pick: (pick_season_start(pick) or 0, pick["id"]),
            )
            self.assertTrue(firsts)
            primary = firsts[0]
            with patch("builtins.input", return_value="1"), redirect_stdout(StringIO()):
                fallback_id = choose_fallback_pick_for_protection(active, save, gsw["id"], primary["id"])
            fallback = next(pick for pick in active["draft_picks"] if pick["id"] == fallback_id)
            self.assertEqual(int(fallback.get("round") or 0), int(primary.get("round") or 0))
            self.assertGreaterEqual(pick_season_start(fallback), pick_season_start(primary))

    def test_startup_protected_pick_labels_have_gameplay_fallback_context(self):
        with tempfile.TemporaryDirectory() as tmp:
            save_path = Path(tmp) / "startup_pick_obligation_save.json"
            save = create_league_save(ROOT, self.plain, "GSW", save_path, seed=412)
            self.assertGreaterEqual(len(save.get("pick_obligations", [])), 12)
            active = with_transaction_context(canonical_with_save(self.plain, save))
            gsw_dal_pick = next(pick for pick in active["draft_picks"] if pick["id"] == "pick_future-gsw-2030-1-2")
            label = pick_label(active, gsw_dal_pick)
            self.assertIn("top-20 protected", label)
            self.assertIn("DAL keeps this pick if it lands in the protected range", label)
            self.assertIn("GSW instead receives", label)
            self.assertNotIn("Transfers to", label)
            obligation = next(item for item in save.get("pick_obligations", []) if item.get("primary_pick_id") == gsw_dal_pick["id"])
            fallback = next(pick for pick in active["draft_picks"] if pick["id"] == obligation["fallback_pick_ids"][0])
            self.assertEqual(int(fallback.get("round") or 0), 1)
            self.assertTrue(protected_pick_fallback_is_distinct(gsw_dal_pick, fallback))
            self.assertFalse(any(pick["id"] == fallback["id"] for pick in tradeable_picks_for_team(active, "team_dal")))

    def test_startup_pick_ledger_and_fallbacks_never_duplicate_an_underlying_pick(self):
        future_keys = [
            (str(pick.get("season")), int(pick.get("round") or 0), pick.get("original_team_id"))
            for pick in self.plain["draft_picks"]
            if pick.get("status") == "verified_future_pick_reference" and pick.get("original_team_id")
        ]
        self.assertEqual(len(future_keys), len(set(future_keys)))
        with tempfile.TemporaryDirectory() as tmp:
            save_path = Path(tmp) / "startup_pick_ledger.json"
            save = create_league_save(ROOT, self.plain, "POR", save_path, seed=413)
            active = with_transaction_context(canonical_with_save(self.plain, save))
            picks = {pick["id"]: pick for pick in active["draft_picks"]}
            for obligation in save.get("pick_obligations", []):
                if obligation.get("type") != "protected_pick":
                    continue
                primary = picks[obligation["primary_pick_id"]]
                fallback = picks[obligation["fallback_pick_ids"][0]]
                self.assertTrue(protected_pick_fallback_is_distinct(primary, fallback))
                label = pick_label(active, primary)
                self.assertIn("keeps this pick if it lands in the protected range", label)
                self.assertIn("instead receives", label)
                self.assertNotIn("Transfers to", label)

    def test_loading_an_old_duplicate_fallback_repairs_and_persists_the_new_collateral(self):
        with tempfile.TemporaryDirectory() as tmp:
            save_path = Path(tmp) / "old_duplicate_fallback.json"
            save = create_league_save(ROOT, self.plain, "POR", save_path, seed=416)
            active = canonical_with_save(self.plain, save)
            obligation = next(item for item in save["pick_obligations"] if item.get("type") == "protected_pick")
            primary = next(pick for pick in active["draft_picks"] if pick["id"] == obligation["primary_pick_id"])
            duplicate_id = "legacy_duplicate_fallback"
            legacy_canonical = json.loads(json.dumps(self.plain))
            legacy_canonical["draft_picks"].append(
                {
                    **primary,
                    "id": duplicate_id,
                    "current_owner_team_id": obligation["sender_team_id"],
                }
            )
            obligation["fallback_pick_ids"] = [duplicate_id]
            save["locked_pick_assets"] = [duplicate_id]
            ensure_league_save_defaults(save, legacy_canonical)
            repaired = next(item for item in save["pick_obligations"] if item["primary_pick_id"] == primary["id"])
            self.assertNotEqual(repaired["fallback_pick_ids"], [duplicate_id])
            self.assertNotIn(duplicate_id, save["locked_pick_assets"])
            repaired_canonical = canonical_with_save(legacy_canonical, save)
            fallback = next(pick for pick in repaired_canonical["draft_picks"] if pick["id"] == repaired["fallback_pick_ids"][0])
            self.assertTrue(protected_pick_fallback_is_distinct(primary, fallback))

    def test_trade_finder_offer_is_authorized_after_the_counterparty_approves(self):
        with tempfile.TemporaryDirectory() as tmp:
            save_path = Path(tmp) / "finder_offer.json"
            save = create_league_save(ROOT, self.plain, "POR", save_path, seed=414)
            active = canonical_with_save(self.plain, save)
            report = trade_finder_report_for_selection(
                active,
                save,
                "POR",
                "POR",
                [{"kind": "player", "value": "Jerami Grant"}],
                seed=1,
            )
            self.assertTrue(report["candidates"])
            candidate = next(
                item for item in report["candidates"]
                if item["proposal"].get("to_team_id") == "team_det"
            )
            self.assertFalse(candidate["accepted_by_all"])
            self.assertEqual(candidate["offer_context"]["status"], "finder_offer_pending_user_acceptance")
            self.assertTrue(trade_apply_authorized(candidate))
            candidate = accept_trade_finder_offer(candidate, report["for_team"]["id"])
            self.assertIsNotNone(candidate)
            self.assertTrue(candidate["accepted_by_all"])
            self.assertEqual(candidate["offer_context"]["status"], "finder_offer_user_accepted")
            save["pending_trade_proposals"] = [candidate]
            write_save(save_path, save)
            result = apply_trade_to_save(save_path, candidate["proposal"]["id"], date="2025-10-01")
            self.assertEqual(result["status"], "applied")

    def test_trade_finder_does_not_reprompt_pick_terms_after_acceptance(self):
        with tempfile.TemporaryDirectory() as tmp:
            save_path = Path(tmp) / "finder_terms.json"
            create_league_save(ROOT, self.plain, "UTA", save_path, seed=432)
            pick = next(
                item for item in self.plain["draft_picks"]
                if item.get("current_owner_team_id") == "team_uta" and int(item.get("round") or 0) == 1 and str(item.get("season") or "") >= "2030"
            )
            candidate = {
                "proposal": {
                    "id": "finder_terms_offer",
                    "from_team_id": "team_uta",
                    "to_team_id": "team_tor",
                    "from_assets": [{"kind": "pick", "id": pick["id"], "value": pick["id"]}],
                    "to_assets": [],
                },
                "offer_context": {"source": "trade_finder", "status": "finder_offer_pending_user_acceptance"},
                "pick_trade_terms": [{"type": "unprotected", "primary_pick_id": pick["id"]}],
                "legality": {"status": "legal"},
                "evaluations": [{"perspective_team_id": "team_tor", "accepted": True}],
            }
            with patch("nba_gm_data.play.prompt_pick_trade_terms", side_effect=AssertionError("duplicate prompt")):
                finalized = attach_pick_terms_to_trade(self.plain, save_path, candidate)
            self.assertTrue(finalized["pick_obligation_terms_prompted"])
            self.assertEqual(finalized["pick_trade_terms"][0]["type"], "unprotected")
            self.assertNotIn("pick_obligation_terms", finalized)

    def test_draft_pick_transfer_refreshes_live_queue_and_slot_picks_do_not_prompt_for_protection(self):
        with tempfile.TemporaryDirectory() as tmp:
            save_path = Path(tmp) / "draft_trade_refresh.json"
            save = create_league_save(ROOT, self.plain, "GSW", save_path, seed=411)
            pick = next(pick for pick in self.plain["draft_picks"] if pick["id"] == "pick_2026-1-1-was")
            save["state"] = {"current_date": "2026-06-26", "phase": "draft", "legal_actions": ["trades", "draft_picks"]}
            save["draft_orders"] = {
                "2026": {
                    "draft_order": [
                        {
                            "id": pick["id"],
                            "draft_year": "2026",
                            "round": 1,
                            "overall_pick": 1,
                            "original_team_id": "team_was",
                            "current_owner_team_id": "team_was",
                        }
                    ]
                }
            }
            self.assertTrue(pick_slot_is_determined_for_trade(save, pick))
            save["draft_pick_overrides"][pick["id"]] = "team_chi"
            save["draft_state"] = {
                "year": "2026",
                "status": "in_progress",
                "current_index": 0,
                "draft": {
                    "pending_draft_selections": [
                        {
                            "id": "selection_refresh_test",
                            "selection": {
                                "id": "selection_refresh_test",
                                "pick_id": pick["id"],
                                "team_id": "team_was",
                                "prospect_id": "draft_prospect_test",
                                "draft_year": "2026",
                                "overall_pick": 1,
                            },
                            "pick": dict(pick),
                            "team": {"id": "team_was", "abbrev": "WAS"},
                            "prospect": {"id": "draft_prospect_test", "name": "Test Prospect"},
                        }
                    ]
                },
            }
            changed = refresh_live_draft_state_ownership(self.plain, save, "2026")
            self.assertTrue(changed)
            current = save["draft_state"]["draft"]["pending_draft_selections"][0]
            self.assertEqual(current["selection"]["team_id"], "team_chi")
            self.assertEqual(current["pick"]["current_owner_team_id"], "team_chi")
            self.assertEqual(current["team"]["abbrev"], "CHI")

    def test_ai_draft_trade_hook_applies_once_and_queues_breaking_news(self):
        with tempfile.TemporaryDirectory() as tmp:
            save_path = Path(tmp) / "ai_draft_trade_save.json"
            save = create_league_save(ROOT, self.plain, "GSW", save_path, seed=413)
            firsts = [
                pick for pick in self.plain["draft_picks"]
                if pick.get("season") == "2026"
                and int(pick.get("round") or 0) == 1
                and pick.get("current_owner_team_id") != "team_gsw"
            ]
            pick_a = firsts[0]
            pick_b = next(pick for pick in firsts[1:] if pick.get("current_owner_team_id") != pick_a.get("current_owner_team_id"))
            save["state"] = {"current_date": "2026-06-26", "phase": "draft", "legal_actions": ["trades", "draft_picks"]}
            save["draft_state"] = {
                "year": "2026",
                "status": "in_progress",
                "current_index": 0,
                "draft": {
                    "pending_draft_selections": [
                        {
                            "id": "selection_ai_trade_a",
                            "selection": {"id": "selection_ai_trade_a", "pick_id": pick_a["id"], "team_id": pick_a["current_owner_team_id"], "prospect_id": "draft_prospect_a", "draft_year": "2026", "overall_pick": 7},
                            "pick": dict(pick_a),
                            "team": {"id": pick_a["current_owner_team_id"], "abbrev": "AAA"},
                            "prospect": {"id": "draft_prospect_a", "name": "Prospect A"},
                        },
                        {
                            "id": "selection_ai_trade_b",
                            "selection": {"id": "selection_ai_trade_b", "pick_id": pick_b["id"], "team_id": pick_b["current_owner_team_id"], "prospect_id": "draft_prospect_b", "draft_year": "2026", "overall_pick": 12},
                            "pick": dict(pick_b),
                            "team": {"id": pick_b["current_owner_team_id"], "abbrev": "BBB"},
                            "prospect": {"id": "draft_prospect_b", "name": "Prospect B"},
                        },
                    ]
                },
            }
            candidate = {
                "proposal": {
                    "id": "ai_draft_trade_test",
                    "date": "2026-06-26",
                    "from_team_id": pick_a["current_owner_team_id"],
                    "to_team_id": pick_b["current_owner_team_id"],
                    "from_assets": [{"kind": "pick", "id": pick_a["id"], "label": pick_a["id"], "round": 1}],
                    "to_assets": [{"kind": "pick", "id": pick_b["id"], "label": pick_b["id"], "round": 1}],
                },
                "legality": {"status": "legal", "issues": [], "manual_review": []},
                "evaluations": [],
                "accepted_by_all": True,
                "summary": "AI draft trade test",
            }
            write_save(save_path, save)
            with patch("nba_gm_data.play.best_ai_draft_trade_candidate", return_value=candidate):
                result = maybe_run_ai_draft_trades_before_pick(self.plain, save_path, "GSW", seed=1, force=True)
                self.assertEqual(result["applied_count"], 1)
                second = maybe_run_ai_draft_trades_before_pick(self.plain, save_path, "GSW", seed=1, force=True)
                self.assertEqual(second["applied_count"], 0)
            saved = load_save(save_path)
            self.assertEqual(saved["draft_pick_overrides"][pick_a["id"]], pick_b["current_owner_team_id"])
            self.assertEqual(saved["draft_pick_overrides"][pick_b["id"]], pick_a["current_owner_team_id"])
            self.assertIn(pick_a["id"], saved["draft_state"]["ai_draft_traded_pick_ids"])
            self.assertIn(pick_b["id"], saved["draft_state"]["ai_draft_traded_pick_ids"])
            self.assertEqual(len(saved["draft_state"]["ai_draft_trade_news_queue"]), 1)
            headline = saved["draft_state"]["ai_draft_trade_news_queue"][0]["headline"]
            self.assertIn("Pick #7", headline)
            self.assertIn("Pick #12", headline)
            self.assertNotIn(pick_a["id"], headline)

    def test_mid_first_ai_draft_trade_market_finds_value_when_quiet(self):
        with tempfile.TemporaryDirectory() as tmp:
            save_path = Path(tmp) / "ai_draft_trade_market.json"
            save = create_league_save(ROOT, self.plain, "GSW", save_path, seed=77)
            active = with_transaction_context(canonical_with_save(self.plain, save))
            draft = simulate_draft(active, "2026", seed=77)
            state = {
                "year": "2026",
                "status": "in_progress",
                "current_index": 10,
                "draft": draft,
                "ai_draft_traded_pick_ids": [],
                "ai_draft_trade_budget": {"top_10": 0, "picks_11_25": 0, "total": 0},
                "used_pick_ids": [],
            }
            current = state["draft"]["pending_draft_selections"][10]
            candidate = best_ai_draft_trade_candidate(active, save, state, current, save["meta"]["user_team_id"], seed=77)
            self.assertIsNotNone(candidate)
            self.assertEqual(candidate["legality"]["status"], "legal")
            self.assertTrue(candidate["accepted_by_all"])
            to_assets = (candidate["proposal"] or {}).get("to_assets") or []
            self.assertTrue(
                any(
                    asset.get("kind") == "pick"
                    and int((next((pick for pick in active["draft_picks"] if pick["id"] == (asset.get("id") or asset.get("value"))), {}) or {}).get("round") or 0) == 1
                    for asset in to_assets
                )
            )

    def test_lottery_reveal_shows_final_owner_only(self):
        order = {
            "lottery": {"seed": 1, "method": "test", "odds_by_team": {}},
            "draft_order": [
                {
                    "id": "pick_test",
                    "round": 1,
                    "overall_pick": 1,
                    "original_team_id": "team_por",
                    "current_owner_team_id": "team_chi",
                    "team_abbrev": "CHI",
                }
            ],
        }
        with redirect_stdout(StringIO()) as output:
            print_lottery(order)
        text = output.getvalue()
        self.assertIn("1. CHI  #1", text)
        self.assertNotIn("POR  #1 [owned by CHI]", text)

    def test_lottery_odds_context_does_not_copy_protection_to_receiver_pick(self):
        with tempfile.TemporaryDirectory() as tmp:
            save_path = Path(tmp) / "lottery_context.json"
            save = create_league_save(ROOT, self.plain, "GSW", save_path, seed=431)
            dal_pick = next(
                pick for pick in self.plain["draft_picks"]
                if pick.get("season") == "2027" and pick.get("original_team_id") == "team_dal" and int(pick.get("round") or 0) == 1
            )
            cha_pick = next(
                pick for pick in self.plain["draft_picks"]
                if pick.get("season") == "2027" and pick.get("original_team_id") == "team_cha" and int(pick.get("round") or 0) == 1
            )
            fallback = next(
                pick for pick in self.plain["draft_picks"]
                if str(pick.get("season") or "") > "2027" and pick.get("original_team_id") == "team_dal" and int(pick.get("round") or 0) == 1
            )
            save["draft_pick_overrides"][dal_pick["id"]] = "team_cha"
            save["pick_obligations"] = [
                {
                    "id": "test_dal_to_cha_top2",
                    "type": "protected_pick",
                    "status": "active",
                    "season": "2027",
                    "round": 1,
                    "primary_pick_id": dal_pick["id"],
                    "sender_team_id": "team_dal",
                    "receiver_team_id": "team_cha",
                    "protected_range": {"from": 1, "through": 2},
                    "protected_top_n": 2,
                    "fallback_pick_ids": [fallback["id"]],
                }
            ]
            order = {
                "lottery": {"seed": 1, "method": "test", "odds_by_team": {"team_dal": 10.5, "team_cha": 3.0}},
                "draft_order": [
                    {**dal_pick, "overall_pick": 5, "current_owner_team_id": "team_cha"},
                    {**cha_pick, "overall_pick": 11, "current_owner_team_id": "team_cha"},
                ],
            }
            annotate_lottery_odds_context(self.plain, save, order)
            context = order["lottery"]["odds_context_by_team"]
            self.assertIn("owned by CHA", context["team_dal"])
            self.assertIn("top-2 protected", context["team_dal"])
            self.assertNotIn("top-2 protected", context.get("team_cha", ""))

    def test_protected_pick_visibility_locking_resolution_and_retrade(self):
        def build_protected_trade_save(save_path: Path) -> tuple[dict, dict, dict, dict]:
            save = create_league_save(ROOT, self.plain, "GSW", save_path, seed=408)
            active = with_transaction_context(canonical_with_save(self.plain, save))
            gsw = next(team for team in active["teams"] if team["abbrev"] == "GSW")
            bos = next(team for team in active["teams"] if team["abbrev"] == "BOS")
            primary = next(
                pick for pick in tradeable_picks_for_team(active, gsw["id"])
                if int(pick.get("round") or 0) == 1 and str(pick.get("season")) >= "2027"
            )
            fallback = next(
                pick for pick in tradeable_picks_for_team(active, gsw["id"])
                if int(pick.get("round") or 0) == 1 and str(pick.get("season")) >= str(primary.get("season")) and pick["id"] != primary["id"]
            )
            term = {
                "type": "protected_pick",
                "primary_pick_id": primary["id"],
                "sender_team_id": gsw["id"],
                "receiver_team_id": bos["id"],
                "season": primary["season"],
                "protected_range": {"from": 1, "through": 9},
                "protected_top_n": 9,
                "fallback_pick_ids": [fallback["id"]],
                "label": "top-9 protected",
            }
            protected_active = canonical_with_pending_pick_terms(active, [term])
            protected_primary = next(pick for pick in protected_active["draft_picks"] if pick["id"] == primary["id"])
            self.assertLess(pick_asset_value(protected_primary, "balanced"), pick_asset_value(primary, "balanced"))
            self.assertIn("top-9 protected", pick_label(protected_active, protected_primary))
            save["pending_trade_proposals"] = [
                {
                    "proposal": {
                        "id": "protected_pick_trade",
                        "date": save["state"]["current_date"],
                        "from_team_id": gsw["id"],
                        "to_team_id": bos["id"],
                        "from_assets": [
                            {
                                "kind": "pick",
                                "id": primary["id"],
                                "label": pick_label(protected_active, protected_primary),
                                "round": primary.get("round"),
                                "season": primary.get("season"),
                                "original_team_id": primary.get("original_team_id"),
                                "protection_summary": "top-9 protected",
                            }
                        ],
                        "to_assets": [],
                    },
                    "legality": {"status": "legal"},
                    "evaluations": [],
                    "accepted_by_all": True,
                    "pick_obligation_terms": [term],
                }
            ]
            write_save(save_path, save)
            applied = apply_trade_to_save(save_path, "protected_pick_trade", date=save["state"]["current_date"])
            self.assertEqual(applied["status"], "applied")
            saved = load_save(save_path)
            return saved, primary, fallback, term

        with tempfile.TemporaryDirectory() as tmp:
            save_path = Path(tmp) / "primary_conveys.json"
            saved, primary, fallback, _ = build_protected_trade_save(save_path)
            self.assertEqual(saved["draft_pick_overrides"][primary["id"]], "team_bos")
            self.assertIn(fallback["id"], saved["locked_pick_assets"])
            active = with_transaction_context(canonical_with_save(self.plain, saved))
            bos_picks = tradeable_picks_for_team(active, "team_bos")
            protected_label = next(pick_label(active, pick) for pick in bos_picks if pick["id"] == primary["id"])
            self.assertIn("top-9 protected", protected_label)
            self.assertIn("GSW keeps this pick if it lands in the protected range", protected_label)
            self.assertIn(f"BOS instead receives {fallback['season']} R1 GSW", protected_label)
            self.assertFalse(any(pick["id"] == fallback["id"] for pick in tradeable_picks_for_team(active, "team_gsw")))
            self.assertTrue(any("top-9 protected" in event.get("headline", "") for event in saved.get("league_events", [])))
            order = {
                "draft_order": [
                    {
                        "id": primary["id"],
                        "round": 1,
                        "overall_pick": 11,
                        "original_team_id": primary.get("original_team_id"),
                        "current_owner_team_id": "team_bos",
                    }
                ]
            }
            resolve_pick_obligations_for_year(saved, order, str(primary["season"]))
            self.assertEqual(saved["draft_pick_overrides"][primary["id"]], "team_bos")
            self.assertNotIn(fallback["id"], saved["locked_pick_assets"])
            self.assertNotEqual(saved.get("draft_pick_overrides", {}).get(fallback["id"]), "team_bos")

        with tempfile.TemporaryDirectory() as tmp:
            save_path = Path(tmp) / "fallback_conveys.json"
            saved, primary, fallback, _ = build_protected_trade_save(save_path)
            order = {
                "lottery": {"odds_by_team": {"team_gsw": 0.14}},
                "draft_order": [
                    {
                        "id": primary["id"],
                        "round": 1,
                        "overall_pick": 5,
                        "original_team_id": primary.get("original_team_id"),
                        "current_owner_team_id": "team_bos",
                    }
                ]
            }
            annotate_lottery_odds_context(self.plain, saved, order)
            lottery_context = order["lottery"]["odds_context_by_team"]["team_gsw"]
            self.assertIn("[owned by BOS]", lottery_context)
            self.assertIn("top-9 protected", lottery_context)
            self.assertIn("BOS instead receives", lottery_context)
            resolve_pick_obligations_for_year(saved, order, str(primary["season"]))
            refresh_draft_order_from_save(order, saved)
            self.assertEqual(saved["draft_pick_overrides"][primary["id"]], "team_gsw")
            self.assertEqual(order["draft_order"][0]["current_owner_team_id"], "team_gsw")
            self.assertEqual(saved["draft_pick_overrides"][fallback["id"]], "team_bos")
            self.assertNotIn(fallback["id"], saved["locked_pick_assets"])

        with tempfile.TemporaryDirectory() as tmp:
            save_path = Path(tmp) / "retrade_conveys.json"
            saved, primary, fallback, _ = build_protected_trade_save(save_path)
            saved["pending_trade_proposals"] = [
                {
                    "proposal": {
                        "id": "protected_pick_retrade",
                        "date": saved["state"]["current_date"],
                        "from_team_id": "team_bos",
                        "to_team_id": "team_nyk",
                        "from_assets": [{"kind": "pick", "id": primary["id"], "label": "2027 R1 GSW (top-9 protected)", "round": 1}],
                        "to_assets": [],
                    },
                    "legality": {"status": "legal"},
                    "evaluations": [],
                    "accepted_by_all": True,
                }
            ]
            write_save(save_path, saved)
            self.assertEqual(apply_trade_to_save(save_path, "protected_pick_retrade")["status"], "applied")
            retraded = load_save(save_path)
            obligation = next(item for item in retraded["pick_obligations"] if item["primary_pick_id"] == primary["id"])
            self.assertEqual(obligation["receiver_team_id"], "team_nyk")
            order = {
                "draft_order": [
                    {
                        "id": primary["id"],
                        "round": 1,
                        "overall_pick": 11,
                        "original_team_id": primary.get("original_team_id"),
                        "current_owner_team_id": "team_nyk",
                    }
                ]
            }
            resolve_pick_obligations_for_year(retraded, order, str(primary["season"]))
            self.assertEqual(retraded["draft_pick_overrides"][primary["id"]], "team_nyk")

        with tempfile.TemporaryDirectory() as tmp:
            save_path = Path(tmp) / "sender_reacquires.json"
            saved, primary, fallback, _ = build_protected_trade_save(save_path)
            saved["pending_trade_proposals"] = [
                {
                    "proposal": {
                        "id": "protected_pick_back_to_sender",
                        "date": saved["state"]["current_date"],
                        "from_team_id": "team_bos",
                        "to_team_id": "team_gsw",
                        "from_assets": [{"kind": "pick", "id": primary["id"], "label": "2027 R1 GSW (top-9 protected)", "round": 1}],
                        "to_assets": [],
                    },
                    "legality": {"status": "legal"},
                    "evaluations": [],
                    "accepted_by_all": True,
                }
            ]
            write_save(save_path, saved)
            self.assertEqual(apply_trade_to_save(save_path, "protected_pick_back_to_sender")["status"], "applied")
            reacquired = load_save(save_path)
            obligation = next(item for item in reacquired["pick_obligations"] if item["primary_pick_id"] == primary["id"])
            self.assertEqual(obligation["status"], "resolved_reacquired_by_sender")
            self.assertNotIn(fallback["id"], reacquired["locked_pick_assets"])

    def test_pick_obligation_validator_repairs_self_fallback_and_pick_swaps_resolve(self):
        with tempfile.TemporaryDirectory() as tmp:
            save_path = Path(tmp) / "swap_save.json"
            save = create_league_save(ROOT, self.plain, "GSW", save_path, seed=421)
            active = with_transaction_context(canonical_with_save(self.plain, save))
            gsw_firsts = sorted(
                [pick for pick in tradeable_picks_for_team(active, "team_gsw") if int(pick.get("round") or 0) == 1],
                key=lambda pick: (pick_season_start(pick) or 0, pick["id"]),
            )
            gsw_pick = next(
                pick for pick in gsw_firsts
                if any(other["id"] != pick["id"] and (pick_season_start(other) or 0) >= (pick_season_start(pick) or 0) for other in gsw_firsts)
            )
            self_fallback = {
                "id": "bad_self_fallback",
                "type": "protected_pick",
                "primary_pick_id": gsw_pick["id"],
                "sender_team_id": "team_gsw",
                "receiver_team_id": "team_bos",
                "season": gsw_pick["season"],
                "primary_round": 1,
                "protected_range": {"from": 1, "through": 9},
                "fallback_pick_ids": [gsw_pick["id"]],
            }
            self.assertFalse(validate_pick_obligation_term(active, None, self_fallback))
            repaired_obligation = repair_protected_pick_fallback(self_fallback, active, set())
            self.assertIsNotNone(repaired_obligation)
            self.assertNotEqual(repaired_obligation.get("fallback_pick_ids", [None])[0], gsw_pick["id"])
            self.assertTrue(validate_pick_obligation_term(active, None, repaired_obligation))

            duplicate_id = "duplicate_underlying_gsw_pick"
            duplicate = {**gsw_pick, "id": duplicate_id, "current_owner_team_id": "team_gsw"}
            active["draft_picks"].append(duplicate)
            duplicate_fallback = {**self_fallback, "id": "bad_duplicate_fallback", "fallback_pick_ids": [duplicate_id]}
            self.assertFalse(validate_pick_obligation_term(active, None, duplicate_fallback))
            repaired_duplicate = repair_protected_pick_fallback(duplicate_fallback, active, set())
            self.assertIsNotNone(repaired_duplicate)
            repaired_fallback = next(
                pick for pick in active["draft_picks"]
                if pick["id"] == repaired_duplicate["fallback_pick_ids"][0]
            )
            self.assertTrue(protected_pick_fallback_is_distinct(gsw_pick, repaired_fallback))

        with tempfile.TemporaryDirectory() as tmp:
            save_path = Path(tmp) / "swap_lifecycle.json"
            save = create_league_save(ROOT, self.plain, "GSW", save_path, seed=423)
            active = with_transaction_context(canonical_with_save(self.plain, save))
            gsw_pick = next(pick for pick in tradeable_picks_for_team(active, "team_gsw") if int(pick.get("round") or 0) == 1 and str(pick.get("season")) == "2028")
            bos_pick = next(pick for pick in tradeable_picks_for_team(active, "team_bos") if int(pick.get("round") or 0) == 1 and str(pick.get("season")) == str(gsw_pick.get("season")))
            swap = {
                "id": "test_swap_right",
                "type": "pick_swap",
                "season": gsw_pick["season"],
                "round": 1,
                "team_a_pick_id": gsw_pick["id"],
                "team_b_pick_id": bos_pick["id"],
                "original_rights_holder_team_id": "team_bos",
                "current_rights_holder_team_id": "team_bos",
                "counterparty_team_id": "team_gsw",
                "status": "active",
            }
            self.assertTrue(validate_pick_obligation_term(active, None, swap))
            save["pick_obligations"].append(swap)
            write_save(save_path, save)
            active = with_transaction_context(canonical_with_save(self.plain, load_save(save_path)))
            self.assertIn("swap right", pick_swap_display_label(active, swap))
            self.assertGreater(pick_swap_asset_value(active, swap), 0)
            self.assertTrue(any(item["id"] == "test_swap_right" for item in tradeable_pick_swaps_for_team(active, "team_bos")))
            self.assertIn("Subject to", pick_label(active, next(pick for pick in active["draft_picks"] if pick["id"] == gsw_pick["id"])))
            saved = load_save(save_path)
            saved["pending_trade_proposals"] = [
                {
                    "proposal": {
                        "id": "swap_retrade",
                        "from_team_id": "team_bos",
                        "to_team_id": "team_nyk",
                        "from_assets": [{"kind": "pick_swap", "id": "test_swap_right", "label": pick_swap_display_label(active, swap)}],
                        "to_assets": [],
                    },
                    "legality": {"status": "legal"},
                    "accepted_by_all": True,
                    "evaluations": [],
                }
            ]
            write_save(save_path, saved)
            self.assertEqual(apply_trade_to_save(save_path, "swap_retrade")["status"], "applied")
            retraded = load_save(save_path)
            obligation = next(item for item in retraded["pick_obligations"] if item["id"] == "test_swap_right")
            self.assertEqual(obligation["current_rights_holder_team_id"], "team_nyk")
            order = {
                "draft_order": [
                    {"id": gsw_pick["id"], "round": 1, "overall_pick": 4, "current_owner_team_id": "team_gsw", "original_team_id": "team_gsw"},
                    {"id": bos_pick["id"], "round": 1, "overall_pick": 18, "current_owner_team_id": "team_bos", "original_team_id": "team_bos"},
                ]
            }
            resolve_pick_obligations_for_year(retraded, order, str(gsw_pick["season"]))
            self.assertEqual(retraded["draft_pick_overrides"][gsw_pick["id"]], "team_nyk")
            self.assertEqual(retraded["draft_pick_overrides"][bos_pick["id"]], "team_gsw")
            self.assertEqual(next(item for item in retraded["pick_obligations"] if item["id"] == "test_swap_right")["status"], "resolved_swap_exercised")

    def test_ai_offer_packages_can_create_pick_swap_sweeteners(self):
        active = with_transaction_context(self.plain)
        buyer = next(team for team in active["teams"] if team["abbrev"] == "CLE")
        seller = next(team for team in active["teams"] if team["abbrev"] == "NOP")
        target = next(player for player in active["players"] if player["normalized_name"] == "deandre jordan")
        self.assertEqual(target["team_id"], seller["id"])
        packages = buyer_offer_package_options(
            active,
            buyer,
            seller,
            target,
            seed=5,
            max_results=12,
            max_player_options=6,
            allow_new_pick_swaps=True,
        )
        swap_package = next((package for package in packages if package.get("pick_obligation_terms")), None)
        self.assertIsNotNone(swap_package)
        term = swap_package["pick_obligation_terms"][0]
        self.assertEqual(term["type"], "pick_swap")
        self.assertEqual(term["sender_team_id"], buyer["id"])
        self.assertEqual(term["receiver_team_id"], seller["id"])
        self.assertTrue(validate_pick_obligation_term(active, None, term))
        preview = canonical_with_pending_pick_terms(active, [term])
        report = evaluate_trade(
            preview,
            seller["abbrev"],
            buyer["abbrev"],
            [{"kind": "player", "value": target["name"]}],
            swap_package["assets"],
            seed=5,
            context_ready=True,
        )
        report = trade_result_with_pick_terms(report, [term])
        self.assertTrue(any(asset["kind"] == "pick_swap" for asset in report["proposal"]["to_assets"]))
        self.assertIn("pick_obligation_terms", report)
        self.assertIn("swap right", trade_headline_from_payload(report["proposal"]))

    def test_pick_obligation_repair_creates_fallback_and_swap_direction_can_be_negative(self):
        synthetic = {
            "teams": [{"id": "team_den", "abbrev": "DEN"}, {"id": "team_okc", "abbrev": "OKC"}],
            "draft_picks": [
                {
                    "id": "pick_den_2028_r1_primary",
                    "season": "2028",
                    "round": 1,
                    "original_team_id": "team_den",
                    "current_owner_team_id": "team_okc",
                    "protection_summary": "top-5 protected",
                }
            ],
        }
        bad = {
            "id": "bad_self",
            "type": "protected_pick",
            "primary_pick_id": "pick_den_2028_r1_primary",
            "sender_team_id": "team_den",
            "receiver_team_id": "team_okc",
            "season": "2028",
            "primary_round": 1,
            "protected_range": {"from": 1, "through": 5},
            "fallback_pick_ids": ["pick_den_2028_r1_primary"],
        }
        repaired = repair_protected_pick_fallback(bad, synthetic, set())
        self.assertIsNotNone(repaired)
        fallback_id = repaired["fallback_pick_ids"][0]
        self.assertNotEqual(fallback_id, bad["primary_pick_id"])
        fallback = next(pick for pick in synthetic["draft_picks"] if pick["id"] == fallback_id)
        self.assertEqual(fallback["round"], 1)
        self.assertGreaterEqual(pick_season_start(fallback), 2028)
        self.assertTrue(validate_pick_obligation_term(synthetic, None, repaired))

        with tempfile.TemporaryDirectory() as tmp:
            save_path = Path(tmp) / "swap_worse.json"
            save = create_league_save(ROOT, self.plain, "GSW", save_path, seed=427)
            active = with_transaction_context(canonical_with_save(self.plain, save))
            gsw_pick = next(pick for pick in tradeable_picks_for_team(active, "team_gsw") if int(pick.get("round") or 0) == 1 and str(pick.get("season")) == "2028")
            bos_pick = next(pick for pick in tradeable_picks_for_team(active, "team_bos") if int(pick.get("round") or 0) == 1 and str(pick.get("season")) == str(gsw_pick.get("season")))
            swap = {
                "id": "test_less_favorable_swap",
                "type": "pick_swap",
                "season": gsw_pick["season"],
                "round": 1,
                "team_a_pick_id": gsw_pick["id"],
                "team_b_pick_id": bos_pick["id"],
                "original_rights_holder_team_id": "team_bos",
                "current_rights_holder_team_id": "team_bos",
                "counterparty_team_id": "team_gsw",
                "benefit": "worse",
                "status": "active",
            }
            self.assertTrue(validate_pick_obligation_term(active, None, swap))
            labelled = canonical_with_pending_pick_terms(active, [swap])
            self.assertIn("less favorable", pick_swap_display_label(labelled, swap))
            self.assertLess(pick_swap_asset_value(labelled, swap), 0)
            save["pick_obligations"].append(swap)
            order = {
                "draft_order": [
                    {"id": gsw_pick["id"], "round": 1, "overall_pick": 18, "current_owner_team_id": "team_gsw", "original_team_id": "team_gsw"},
                    {"id": bos_pick["id"], "round": 1, "overall_pick": 4, "current_owner_team_id": "team_bos", "original_team_id": "team_bos"},
                ]
            }
            resolve_pick_obligations_for_year(save, order, str(gsw_pick["season"]))
            self.assertEqual(save["draft_pick_overrides"][gsw_pick["id"]], "team_bos")
            self.assertEqual(save["draft_pick_overrides"][bos_pick["id"]], "team_gsw")
            self.assertEqual(next(item for item in save["pick_obligations"] if item["id"] == "test_less_favorable_swap")["status"], "resolved_less_favorable_assigned")

    def test_league_events_and_playoff_leaders_views_are_save_backed(self):
        with tempfile.TemporaryDirectory() as tmp:
            save_path = Path(tmp) / "events_save.json"
            save = create_league_save(ROOT, self.plain, "GSW", save_path, seed=406)
            curry = next(player for player in self.plain["players"] if player["normalized_name"] == "stephen curry")
            save["league_events"].append(
                {
                    "id": "league_event_test",
                    "date": "2026-06-20",
                    "kind": "playoff_result",
                    "headline": "GSW wins a test Finals game.",
                    "team_ids": ["team_gsw"],
                    "player_ids": [],
                    "importance": 0.9,
                    "details": {},
                }
            )
            save["playoff_player_stats"][curry["id"]] = {
                "player_id": curry["id"],
                "player_name": curry["name"],
                "team_id": curry["team_id"],
                "team_abbrev": "GSW",
                "games": 6,
                "points": 192,
                "rebounds": 30,
                "assists": 48,
                "steals": 9,
                "blocks": 2,
                "fg3m": 31,
            }
            save["finals_mvp"] = {"player_id": curry["id"], "player_name": curry["name"], "team_abbrev": "GSW"}
            write_save(save_path, save)
            events = league_events_view(self.plain, save_path, limit=5)
            self.assertEqual(events["events"][0]["headline"], "GSW wins a test Finals game.")
            leaders = playoff_leaders(self.plain, save_path, stat="points", limit=3)
            self.assertEqual(leaders["leaders"][0]["player"]["name"], "Stephen Curry")
            self.assertEqual(leaders["finals_mvp"]["player_name"], "Stephen Curry")

    def test_dashboard_starting_five_and_playoff_stat_context_are_save_backed(self):
        with tempfile.TemporaryDirectory() as tmp:
            save_path = Path(tmp) / "dashboard_playoff_save.json"
            save = create_league_save(ROOT, self.plain, "GSW", save_path, seed=424)
            curry = next(player for player in self.plain["players"] if player["normalized_name"] == "stephen curry")
            save["state"] = {"current_date": "2026-05-10", "phase": "playoffs", "legal_actions": ["advance"]}
            save["player_season_stats"][curry["id"]] = {"games": 10, "minutes": 320, "points": 200, "rebounds": 40, "assists": 80}
            save["playoff_player_stats"][curry["id"]] = {
                "player_id": curry["id"],
                "player_name": curry["name"],
                "team_id": curry["team_id"],
                "team_abbrev": "GSW",
                "games": 2,
                "minutes": 72,
                "points": 60,
                "rebounds": 12,
                "assists": 14,
            }
            save["starting_lineups"] = {"team_gsw": {"source": "user", "slots": {"1": "missing_player", "2": curry["id"]}}}
            write_save(save_path, save)
            payload = team_dashboard(ROOT, self.plain, save_path, "GSW")
            self.assertEqual(payload["stats_context"]["label"], "Playoffs")
            curry_row = next(row for row in payload["rotation"] if row["id"] == curry["id"])
            self.assertEqual(curry_row["points_per_game"], 30.0)
            self.assertTrue(curry_row["is_starting_five"])
            self.assertFalse(any(row["player_id"] == "missing_player" for row in payload["starting_five"]))
            saved = load_save(save_path)
            self.assertNotIn("missing_player", (saved.get("starting_lineups", {}).get("team_gsw", {}).get("slots") or {}).values())
            saved["state"] = {"current_date": "2026-10-21", "phase": "regular_season", "legal_actions": ["advance"]}
            write_save(save_path, saved)
            regular = team_dashboard(ROOT, self.plain, save_path, "GSW")
            self.assertEqual(regular["stats_context"]["label"], "Regular season")

    def test_starting_five_optimizer_respects_lineup_shape_for_okc_and_sas(self):
        with tempfile.TemporaryDirectory() as tmp:
            save_path = Path(tmp) / "lineups.json"
            save = create_league_save(ROOT, self.plain, "OKC", save_path, seed=428)
            active = canonical_with_save(self.plain, save)
            players = {player["id"]: player for player in active["players"]}
            okc = starting_lineup_slots(active, save, "team_okc", persist=False)
            okc_names = [players[player_id]["name"] for _, player_id in sorted(okc.items())]
            self.assertEqual(okc_names[:5], ["Shai Gilgeous-Alexander", "Cason Wallace", "Jalen Williams", "Chet Holmgren", "Isaiah Hartenstein"])
            self.assertGreaterEqual(float(players[okc["4"]]["height_inches"]), 80.0)
            self.assertGreaterEqual(float(players[okc["5"]]["height_inches"]), 80.0)

            save = create_league_save(ROOT, self.plain, "SAS", save_path, seed=429)
            active = canonical_with_save(self.plain, save)
            players = {player["id"]: player for player in active["players"]}
            sas = starting_lineup_slots(active, save, "team_sas", persist=False)
            sas_names = [players[player_id]["name"] for _, player_id in sorted(sas.items())]
            self.assertEqual(sas_names[0], "De'Aaron Fox")
            self.assertIn("Victor Wembanyama", sas_names[3:5])
            self.assertGreaterEqual(float(players[sas["5"]]["height_inches"]), 80.0)

    def test_manual_starting_five_temporarily_autofills_around_injuries(self):
        with tempfile.TemporaryDirectory() as tmp:
            save_path = Path(tmp) / "lineup_injury.json"
            save = create_league_save(ROOT, self.plain, "GSW", save_path, seed=430)
            active = canonical_with_save(self.plain, save)
            curry = next(player for player in active["players"] if player["normalized_name"] == "stephen curry")
            save["starting_lineups"] = {"team_gsw": {"source": "user", "slots": {"1": curry["id"]}}}
            for state in save["health_states"]:
                if state.get("player_id") == curry["id"]:
                    state.update({"availability_status": "out", "current_injury_id": "test_injury", "return_date": "2025-11-15"})
            injured_slots = starting_lineup_slots(active, save, "team_gsw", persist=True)
            self.assertNotIn(curry["id"], injured_slots.values())
            self.assertEqual(save["starting_lineups"]["team_gsw"]["slots"]["1"], curry["id"])
            for state in save["health_states"]:
                if state.get("player_id") == curry["id"]:
                    state.update({"availability_status": "active", "current_injury_id": None, "return_date": None, "days_left": 0})
            healthy_slots = starting_lineup_slots(active, save, "team_gsw", persist=True)
            self.assertEqual(healthy_slots["1"], curry["id"])

    def test_starting_five_autofill_uses_next_unused_auto_starter_for_open_manual_slot(self):
        with tempfile.TemporaryDirectory() as tmp:
            save_path = Path(tmp) / "lineup_injury_collision.json"
            save = create_league_save(ROOT, self.plain, "MIA", save_path, seed=432)
            active = canonical_with_save(self.plain, save)
            players_by_name = {player["normalized_name"]: player for player in active["players"] if player.get("team_id") == "team_mia"}
            herro = players_by_name["tyler herro"]
            powell = players_by_name["norman powell"]
            wiggins = players_by_name["andrew wiggins"]
            adebayo = players_by_name["bam adebayo"]
            ware = players_by_name["kelel ware"]
            save["starting_lineups"] = {
                "team_mia": {
                    "source": "user",
                    "slots": {
                        "1": herro["id"],
                        "2": powell["id"],
                        "3": wiggins["id"],
                        "4": adebayo["id"],
                        "5": ware["id"],
                    },
                }
            }
            save.setdefault("health_states", []).append(
                {
                    "player_id": powell["id"],
                    "availability_status": "out",
                    "current_injury_id": "test_powell_injury",
                    "return_date": "2025-11-15",
                }
            )
            injured_slots = starting_lineup_slots(active, save, "team_mia", persist=True)
            self.assertEqual(len(injured_slots), 5)
            self.assertNotIn(powell["id"], injured_slots.values())
            self.assertEqual(injured_slots["1"], herro["id"])

    def test_gui_starting_five_auto_saves_real_slots_and_blocks_empty_manual_lineup(self):
        with tempfile.TemporaryDirectory() as tmp:
            save_dir = Path(tmp)
            created = dispatch_app_action(
                "create_save",
                {"team": "GSW", "seed": 431, "save_name": "lineup_auto"},
                root=ROOT,
                save_dir=save_dir,
                canonical=self.plain,
            )
            save_path = created["save_path"]
            blocked = dispatch_app_action(
                "set_starting_five",
                {"save_path": save_path, "team": "GSW", "slots": {}},
                root=ROOT,
                save_dir=save_dir,
                canonical=self.plain,
            )
            self.assertEqual(blocked["status"], "blocked")

            auto = dispatch_app_action(
                "set_starting_five",
                {"save_path": save_path, "team": "GSW", "auto": True},
                root=ROOT,
                save_dir=save_dir,
                canonical=self.plain,
            )
            self.assertEqual(auto["status"], "updated")
            self.assertEqual(len(auto["dashboard"]["starting_five"]), 5)
            saved = load_save(save_path)
            stored = saved.get("starting_lineups", {}).get("team_gsw", {})
            self.assertEqual(stored.get("source"), "auto")
            self.assertEqual(len(stored.get("slots") or {}), 5)

    def test_league_events_transactions_filters_are_not_major_only(self):
        with tempfile.TemporaryDirectory() as tmp:
            save_path = Path(tmp) / "events_transactions.json"
            save = create_league_save(ROOT, self.plain, "GSW", save_path, seed=425)
            save["state"]["current_date"] = "2026-02-15"
            save["league_events"] = [
                {"id": "t1", "date": "2026-02-10", "kind": "trade", "headline": "Trade happened.", "team_ids": [], "player_ids": [], "importance": 0.3, "details": {}},
                {"id": "e1", "date": "2026-02-11", "kind": "extension", "headline": "Extension happened.", "team_ids": [], "player_ids": [], "importance": 0.3, "details": {"annual_salary": 10_000_000}},
                {"id": "s1", "date": "2026-02-11", "kind": "free_agent_signing", "headline": "Signing happened.", "team_ids": [], "player_ids": [], "importance": 0.3, "details": {"annual_salary": 8_000_000}},
                {"id": "h1", "date": "2026-02-12", "kind": "staff_hire", "headline": "Staff hire happened.", "team_ids": [], "player_ids": [], "importance": 0.3, "details": {"staff_grade": 70}},
                {"id": "f1", "date": "2026-02-13", "kind": "staff_fire", "headline": "Staff fire happened.", "team_ids": [], "player_ids": [], "importance": 0.3, "details": {"staff_grade": 70}},
                {"id": "d1", "date": "2026-02-13", "kind": "trade_demand", "headline": "Trade demand happened.", "team_ids": [], "player_ids": [], "importance": 0.7, "details": {}},
                {"id": "p1", "date": "2026-02-14", "kind": "playoff_result", "headline": "Game happened.", "team_ids": [], "player_ids": [], "importance": 0.9, "details": {}},
                {"id": "old", "date": "2025-12-01", "kind": "trade", "headline": "Old trade happened.", "team_ids": [], "player_ids": [], "importance": 0.3, "details": {}},
            ]
            write_save(save_path, save)
            transactions = league_events_view(self.plain, save_path, kind="transactions", limit=20)
            headlines = {event["headline"] for event in transactions["events"]}
            self.assertIn("Trade happened.", headlines)
            self.assertIn("Extension happened.", headlines)
            self.assertIn("Signing happened.", headlines)
            self.assertIn("Staff hire happened.", headlines)
            self.assertIn("Staff fire happened.", headlines)
            self.assertIn("Trade demand happened.", headlines)
            self.assertNotIn("Game happened.", headlines)
            trades = league_events_view(self.plain, save_path, kind="trades", limit=20)
            self.assertEqual({event["kind"] for event in trades["events"]}, {"trade"})
            recent = league_events_view(self.plain, save_path, kind="transactions", recent_days=30, limit=20)
            self.assertNotIn("Old trade happened.", {event["headline"] for event in recent["events"]})

    def test_league_events_major_filter_uses_strict_business_rules(self):
        with tempfile.TemporaryDirectory() as tmp:
            save_path = Path(tmp) / "major_events_save.json"
            save = create_league_save(ROOT, self.plain, "GSW", save_path, seed=407)
            save["state"]["current_date"] = "2026-02-15"
            save["league_events"] = [
                {
                    "id": "score",
                    "date": "2026-02-14",
                    "kind": "game_result",
                    "headline": "GSW 120, LAL 118",
                    "team_ids": ["team_gsw", "team_lal"],
                    "player_ids": [],
                    "importance": 1.0,
                    "details": {},
                },
                {
                    "id": "r1_trade",
                    "date": "2026-02-14",
                    "kind": "trade",
                    "headline": "R1 pick moved.",
                    "team_ids": ["team_gsw", "team_bos"],
                    "player_ids": [],
                    "importance": 0.4,
                    "details": {"from_assets": [{"kind": "pick", "id": "pick_test", "round": 1}], "to_assets": []},
                },
                {
                    "id": "r1_trade_duplicate",
                    "date": "2026-02-13",
                    "kind": "trade",
                    "headline": "R1 pick moved again.",
                    "team_ids": ["team_gsw", "team_bos"],
                    "player_ids": [],
                    "importance": 0.4,
                    "details": {"from_assets": [{"kind": "pick", "id": "pick_test", "round": 1}], "to_assets": []},
                },
                {
                    "id": "exact_contract",
                    "date": "2026-02-14",
                    "kind": "extension",
                    "headline": "Exact threshold extension.",
                    "team_ids": ["team_gsw"],
                    "player_ids": ["player_exact"],
                    "importance": 0.9,
                    "details": {"annual_salary": 25_000_000},
                },
                {
                    "id": "big_contract",
                    "date": "2026-02-13",
                    "kind": "free_agent_signing",
                    "headline": "Big contract signing.",
                    "team_ids": ["team_gsw"],
                    "player_ids": ["player_big"],
                    "importance": 0.3,
                    "details": {"annual_salary": 25_100_000},
                },
                {
                    "id": "major_injury",
                    "date": "2026-02-13",
                    "kind": "injury",
                    "headline": "Major injury.",
                    "team_ids": ["team_gsw"],
                    "player_ids": ["player_hurt"],
                    "importance": 0.3,
                    "details": {"expected_games_missed": 42, "player_minutes_projection": 30.0},
                },
                {
                    "id": "exact_stat",
                    "date": "2026-02-12",
                    "kind": "major_stat_line",
                    "headline": "Exactly 20 rebounds.",
                    "team_ids": ["team_gsw"],
                    "player_ids": ["player_reb"],
                    "importance": 0.9,
                    "details": {"stat": "rebounds", "value": 20},
                },
                {
                    "id": "major_stat",
                    "date": "2026-02-12",
                    "kind": "major_stat_line",
                    "headline": "50 points.",
                    "team_ids": ["team_gsw"],
                    "player_ids": ["player_pts"],
                    "importance": 0.3,
                    "details": {"stat": "points", "value": 50},
                },
                {
                    "id": "old_major",
                    "date": "2025-12-01",
                    "kind": "staff_hire",
                    "headline": "Old elite hire.",
                    "team_ids": ["team_gsw"],
                    "player_ids": [],
                    "importance": 0.3,
                    "details": {"staff_grade": 95.0},
                },
            ]
            write_save(save_path, save)
            major = league_events_view(self.plain, save_path, major_only=True, limit=20)
            headlines = {event["headline"] for event in major["events"]}
            self.assertIn("R1 pick moved.", headlines)
            self.assertEqual(
                sum(1 for event in major["events"] if (event.get("details") or {}).get("from_assets") == [{"kind": "pick", "id": "pick_test", "round": 1}]),
                1,
            )
            self.assertIn("Big contract signing.", headlines)
            self.assertIn("Major injury.", headlines)
            self.assertIn("50 points.", headlines)
            self.assertIn("Old elite hire.", headlines)
            self.assertNotIn("GSW 120, LAL 118", headlines)
            self.assertNotIn("Exact threshold extension.", headlines)
            self.assertNotIn("Exactly 20 rebounds.", headlines)
            recent = league_events_view(self.plain, save_path, major_only=True, recent_days=30, limit=20)
            self.assertNotIn("Old elite hire.", {event["headline"] for event in recent["events"]})

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
        draft_repeat = simulate_draft(self.plain, "2026", seed=2)
        draft_other = simulate_draft(self.plain, "2026", seed=9)
        self.assertEqual(draft["selections"], draft_repeat["selections"])
        prospects = {prospect["id"]: prospect["name"] for prospect in self.plain["draft_prospects"]}
        self.assertEqual(prospects[draft["selections"][0]["prospect_id"]], "AJ Dybantsa")
        self.assertEqual(prospects[draft_other["selections"][0]["prospect_id"]], "AJ Dybantsa")
        mid_board = [selection["prospect_id"] for selection in draft["selections"][10:30]]
        mid_board_other = [selection["prospect_id"] for selection in draft_other["selections"][10:30]]
        self.assertNotEqual(mid_board, mid_board_other)
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

    def test_draft_assets_and_goat_exception_use_playtest_value_floors(self):
        top_pick_value = pick_asset_value(
            {
                "id": "pick_value_test",
                "season": "2026",
                "round": 1,
                "overall_pick": 1,
                "original_team_id": "team_was",
                "current_owner_team_id": "team_was",
            },
            "neutral",
        )
        self.assertGreaterEqual(top_pick_value, 84)
        sixth_pick_value = pick_asset_value(
            {
                "id": "pick_value_test_6",
                "season": "2026",
                "round": 1,
                "overall_pick": 6,
                "original_team_id": "team_was",
                "current_owner_team_id": "team_was",
            },
            "neutral",
        )
        tenth_pick_value = pick_asset_value(
            {
                "id": "pick_value_test_10",
                "season": "2026",
                "round": 1,
                "overall_pick": 10,
                "original_team_id": "team_was",
                "current_owner_team_id": "team_was",
            },
            "neutral",
        )
        thirtieth_pick_value = pick_asset_value(
            {
                "id": "pick_value_test_30",
                "season": "2026",
                "round": 1,
                "overall_pick": 30,
                "original_team_id": "team_was",
                "current_owner_team_id": "team_was",
            },
            "neutral",
        )
        self.assertGreater(top_pick_value - sixth_pick_value, 25.0)
        self.assertGreater(top_pick_value - tenth_pick_value, 15.0)
        self.assertGreater(tenth_pick_value - thirtieth_pick_value, 35.0)
        rookie = {
            "name": "Test Rookie",
            "draft_pick": 1,
            "current_ability": 58,
            "potential": 83,
            "age": 19,
            "minutes_projection": 6,
            "position": "SF",
        }
        rookie_value = fallback_asset_valuation(rookie)
        self.assertGreaterEqual(rookie_value["player_value"], 84)
        self.assertGreaterEqual(market_trade_target_value(rookie, rookie_value), 84)
        active = with_transaction_context(self.plain)
        report = evaluate_trade(active, "LAL", "BOS", [{"kind": "player", "value": "LeBron James"}], [], seed=5)
        self.assertEqual(report["legality"]["status"], "illegal")
        self.assertTrue(any("GOAT exception" in issue for issue in report["legality"]["issues"]))

    def test_superstar_and_swap_values_have_benchmark_shape(self):
        active = with_transaction_context(self.plain)
        players = {player["normalized_name"]: player for player in active["players"]}
        values = {row["player_id"]: row for row in active["player_asset_valuations"]}
        giannis = players["giannis antetokounmpo"]
        lamelo = players["lamelo ball"]
        naz = players["naz reid"]
        giannis_value = market_trade_target_value(giannis, values[giannis["id"]])
        lamelo_value = market_trade_target_value(lamelo, values[lamelo["id"]])
        naz_value = market_trade_target_value(naz, values[naz["id"]])
        self.assertGreater(giannis_value, 105.0)
        self.assertGreater(giannis_value - lamelo_value, 25.0)
        self.assertLess(abs(lamelo_value - naz_value), 18.0)
        first_a = {"id": "swap_a", "season": "2030", "round": 1, "overall_pick": 8, "original_team_id": "team_mia", "current_owner_team_id": "team_mia", "_active_season": "2025-26"}
        first_b = {"id": "swap_b", "season": "2030", "round": 1, "overall_pick": 24, "original_team_id": "team_mil", "current_owner_team_id": "team_mil", "_active_season": "2025-26"}
        swap_context = {**active, "draft_picks": [*active["draft_picks"], first_a, first_b]}
        swap = {"id": "benchmark_swap", "type": "pick_swap", "team_a_pick_id": "swap_a", "team_b_pick_id": "swap_b", "current_rights_holder_team_id": "team_mia", "benefit": "better", "status": "active"}
        self.assertGreater(pick_swap_asset_value(swap_context, swap), 8.0)
        self.assertLess(pick_swap_asset_value(swap_context, swap), pick_asset_value(first_a, "neutral"))

    def test_draft_trade_up_packages_need_real_first_round_value(self):
        active = with_transaction_context(self.plain)
        state = {
            "ai_draft_traded_pick_ids": [],
            "used_pick_ids": [],
        }
        buyer = next(team for team in active["teams"] if team["abbrev"] == "BOS")
        target = {
            "id": "draft_pick_target_12",
            "season": "2026",
            "round": 1,
            "overall_pick": 12,
            "original_team_id": "team_was",
            "current_owner_team_id": "team_was",
        }
        lower = {
            "id": "draft_pick_lower_18",
            "season": "2026",
            "round": 1,
            "overall_pick": 18,
            "original_team_id": buyer["id"],
            "current_owner_team_id": buyer["id"],
        }
        active["draft_picks"].extend([target, lower])
        assets = draft_trade_offer_assets(active, state, buyer["id"], target["id"], lower, 12)
        self.assertTrue(any(asset["kind"] == "pick" and int(next(pick for pick in active["draft_picks"] if pick["id"] == asset["value"]).get("round") or 0) == 1 and asset["value"] != lower["id"] for asset in assets))

        target_one = {**target, "id": "draft_pick_target_1", "overall_pick": 1}
        lower_six = {**lower, "id": "draft_pick_lower_6", "overall_pick": 6}
        second_only = {"id": "draft_pick_second_only", "season": "2028", "round": 2, "projected_pick_slot": 34, "original_team_id": buyer["id"], "current_owner_team_id": buyer["id"]}
        controlled = {
            **active,
            "draft_picks": [
                pick
                for pick in active["draft_picks"]
                if pick.get("current_owner_team_id") != buyer["id"]
            ],
        }
        controlled["draft_picks"].extend([target_one, lower_six, second_only])
        self.assertEqual(draft_trade_offer_assets(controlled, state, buyer["id"], target_one["id"], lower_six, 1), [])

        future_first = {"id": "draft_pick_future_first", "season": "2028", "round": 1, "projected_pick_slot": 8, "original_team_id": buyer["id"], "current_owner_team_id": buyer["id"]}
        extra_future_first = {"id": "draft_pick_extra_future_first", "season": "2029", "round": 1, "projected_pick_slot": 15, "original_team_id": buyer["id"], "current_owner_team_id": buyer["id"]}
        controlled["draft_picks"].extend([future_first, extra_future_first])
        stronger = draft_trade_offer_assets(controlled, state, buyer["id"], target_one["id"], lower_six, 1)
        self.assertTrue(
            any(
                int(next(pick for pick in controlled["draft_picks"] if pick["id"] == asset["value"]).get("round") or 0) == 1
                and asset["value"] != lower_six["id"]
                for asset in stronger
            )
        )
        self.assertGreaterEqual(len(stronger), 2)

    def test_prospect_picker_board_and_report_share_scout_display_values(self):
        report = next(item for item in self.plain.get("scouting_reports", []) if item.get("prospect_id") and item.get("team_id"))
        prospect = next(item for item in self.plain.get("draft_prospects", []) if item.get("id") == report["prospect_id"])
        scout = prospect_scout_display(self.plain, prospect, report["team_id"])
        with StringIO() as buffer, redirect_stdout(buffer):
            print_prospect_line(prospect, prefix="1", team_id=report["team_id"], canonical=self.plain)
            text = buffer.getvalue()
        self.assertIn(f"now {scout['now']:.0f}", text)
        self.assertIn(f"pot {scout['potential']:.0f}", text)
        self.assertIn(f"floor {scout['floor']:.0f}", text)
        self.assertIn(f"ceil {scout['ceiling']:.0f}", text)

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
            rookie_id = applied["incoming_rookie"]["player_id"]
            rookie = next(player for player in saved["generated_players"] if player["id"] == rookie_id)
            self.assertGreaterEqual(float(saved.get("rotation_baselines", {}).get(rookie_id) or 0.0), 17.0)
            self.assertIn(rookie_id, recent_rookie_protected_player_ids(saved))
            saved["meta"]["season"] = "2027-28"
            saved["state"] = {"current_date": "2027-10-01", "phase": "preseason", "legal_actions": []}
            active = canonical_with_save(self.plain, saved)
            active_rookie = next(player for player in active["players"] if player["id"] == rookie["id"])
            self.assertEqual(float(active_rookie["display_age"]), float(rookie["age"]))
            projection = team_rotation_projection(active, saved, active_rookie["team_id"], integer=False)
            self.assertGreaterEqual(float(projection.get(rookie_id) or 0.0), 17.0)

    def test_automated_draft_processing_unblocks_free_agency_advance(self):
        with tempfile.TemporaryDirectory() as tmp:
            save_path = Path(tmp) / "automated_draft_save.json"
            save = create_league_save(ROOT, self.plain, "ATL", save_path, seed=12)
            save["state"] = {"current_date": "2026-06-27", "phase": "draft", "legal_actions": ["trades", "draft_picks"]}
            result = ensure_draft_processed(self.plain, save, "2026", seed=12)
            self.assertEqual(result["status"], "processed_ai_draft")
            self.assertEqual(save.get("pending_draft_selections"), [])
            self.assertEqual(save.get("draft_state", {}).get("status"), "completed")
            self.assertGreater(result["rookies_signed"], 0)
            write_save(save_path, save)
            advanced = advance_save(ROOT, self.plain, save_path, to_date="2026-07-01", seed=12)
            self.assertEqual(advanced["status"], "advanced")
            self.assertEqual(load_save(save_path)["state"]["phase"], "free_agency")

    def test_awards_generate_from_saved_stats(self):
        with tempfile.TemporaryDirectory() as tmp:
            save_path = Path(tmp) / "awards_save.json"
            save = create_league_save(ROOT, self.plain, "GSW", save_path, seed=31)
            players = {player["normalized_name"]: player for player in self.plain["players"]}
            curry = players["stephen curry"]
            wemby = players["victor wembanyama"]
            nurkic = players["jusuf nurkic"]
            save["team_records"][curry["team_id"]]["wins"] = 58
            save["team_records"][curry["team_id"]]["losses"] = 24
            save["team_records"][wemby["team_id"]]["wins"] = 47
            save["team_records"][wemby["team_id"]]["losses"] = 35
            save["team_records"][nurkic["team_id"]]["wins"] = 50
            save["team_records"][nurkic["team_id"]]["losses"] = 32
            save["player_season_stats"][curry["id"]] = {"games": 74, "minutes": 2450, "points": 2300, "rebounds": 330, "assists": 610, "steals": 95, "blocks": 25}
            save["player_season_stats"][wemby["id"]] = {"games": 72, "minutes": 2520, "points": 1900, "rebounds": 920, "assists": 310, "steals": 95, "blocks": 265}
            save["player_season_stats"][nurkic["id"]] = {"games": 72, "minutes": 2200, "points": 1050, "rebounds": 850, "assists": 280, "steals": 80, "blocks": 190}
            awards = generate_league_awards(self.plain, save, "2025-26", seed=31)
            self.assertTrue(any(award["award"] == "MVP" for award in awards))
            self.assertTrue(any(award["award"] == "DPOY" for award in awards))
            dpoy = next(award for award in awards if award["award"] == "DPOY")
            self.assertEqual(dpoy["player_name"], "Victor Wembanyama")
            self.assertTrue(any(item.get("kind") == "award" for item in save.get("news_items", [])))

    def test_rookie_of_year_only_counts_first_season(self):
        with tempfile.TemporaryDirectory() as tmp:
            save_path = Path(tmp) / "roty_save.json"
            save = create_league_save(ROOT, self.plain, "GSW", save_path, seed=433)
            rookie = {
                "id": "rookie_test_repeat",
                "name": "Repeat Rookie",
                "normalized_name": "repeat rookie",
                "team_id": "team_gsw",
                "team_abbrev": "GSW",
                "position": "PG",
                "age": 20.0,
                "display_age": 20.0,
                "height_inches": 76,
                "minutes_projection": 30.0,
                "source_kind": "generated_rookie",
                "draft_year": 2026,
            }
            save["generated_players"].append(rookie)
            save["incoming_rookies"].append({"id": "incoming_repeat", "player_id": rookie["id"], "draft_year": 2026, "team_id": "team_gsw", "overall_pick": 4})
            save["team_records"]["team_gsw"] = {"team_id": "team_gsw", "team_abbrev": "GSW", "wins": 45, "losses": 37}
            save["player_season_stats"] = {
                rookie["id"]: {"games": 74, "minutes": 2200, "points": 1500, "rebounds": 350, "assists": 520, "steals": 80, "blocks": 20}
            }
            first = generate_league_awards(self.plain, save, "2026-27", seed=433)
            self.assertEqual(next(award for award in first if award["award"] == "ROTY")["player_id"], rookie["id"])
            second = generate_league_awards(self.plain, save, "2027-28", seed=434)
            self.assertFalse(any(award["award"] == "ROTY" and award["player_id"] == rookie["id"] for award in second))

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

    def test_elite_staff_hire_and_fire_create_major_league_events(self):
        with tempfile.TemporaryDirectory() as tmp:
            save_path = Path(tmp) / "elite_staff_save.json"
            save = create_league_save(ROOT, self.plain, "GSW", save_path, seed=25)
            elite_traits = {"rotation_management": 82.0, "locker_room": 82.0, "scheme_balance": 82.0}
            candidate = {
                "id": "elite_staff_candidate",
                "team_id": None,
                "slot": "head_coach",
                "name": "Andre Whitaker",
                "skill_traits": elite_traits,
                "personality_traits": {"communication": 82.0, "adaptability": 82.0},
                "market_status": "free_agent",
            }
            save["pending_staff_negotiations"].append(
                {
                    "id": "elite_staff_negotiation",
                    "accepted": True,
                    "budget_legal": True,
                    "team_id": "team_gsw",
                    "slot": "head_coach",
                    "candidate": candidate,
                    "team_offer": {"annual_salary_millions": 9.5, "years": 3},
                }
            )
            hire_staff_from_save(save, "elite_staff_negotiation")
            fire_staff_from_save(save, "team_gsw", "head_coach")
            write_save(save_path, save)
            major = league_events_view(self.plain, save_path, major_only=True, limit=20)
            staff_events = [event for event in major["events"] if event.get("kind") in {"staff_hire", "staff_fire"}]
            self.assertGreaterEqual(len(staff_events), 2)
            self.assertTrue(all(float((event.get("details") or {}).get("staff_grade") or 0.0) > 89 for event in staff_events))

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
            advanced = advance_save(ROOT, self.plain, save_path, to_date="2026-01-16", seed=6)
            self.assertGreaterEqual(advanced["ai_applied_count"], 1)
            saved = load_save(save_path)
            trade_actions = [action for action in saved["pending_ai_actions"] if action["action_type"] == "trade_recommendations"]
            self.assertTrue(trade_actions)
            self.assertTrue(all(action["status"] == "executed" for action in trade_actions))
            self.assertTrue(any(log.get("transaction_type") == "trade" and log.get("date") == "2026-01-16" for log in saved.get("transaction_logs", [])))
            processed = process_ai_actions(self.plain, save_path, seed=6, execute=False)
            self.assertEqual(processed["processed_count"], 0)

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
            active_series_count = len([series for series in bracket["series"] if series.get("round") == bracket["round"] and series.get("status") != "completed"])
            one_game = simulate_next_playoff_game(self.plain, save_path, seed=7)
            self.assertEqual(one_game["status"], "simulated_game")
            self.assertEqual(len(one_game["games"]), active_series_count)
            self.assertEqual(len(load_save(save_path)["playoff_state"]["games"]), active_series_count)
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
        newly_confirmed = {
            "mason plumlee": {"2025-26": 3_634_153},
            "mike conley": {"2025-26": 10_774_038},
            "svi mykhailiuk": {"2025-26": 3_675_000, "2026-27": 3_850_000, "2027-28": 4_025_000},
        }
        for name, expected_salaries in newly_confirmed.items():
            contract = contracts[players[name].id]
            self.assertEqual(contract.status, "manual_gameplay_confirmed")
            self.assertIn("src_manual_overrides_2025_26", contract.source_ids)
            salaries = {row["season"]: row.get("salary") for row in contract.seasons}
            for season, salary in expected_salaries.items():
                self.assertEqual(salaries.get(season), salary)
        confirmed = {
            "bub carrington": 4_750_000,
            "cam whitmore": 5_500_000,
        }
        for name, salary in confirmed.items():
            contract = contracts[players[name].id]
            self.assertEqual(contract.status, "manual_gameplay_confirmed")
            salaries = {row["season"]: row.get("salary") for row in contract.seasons}
            self.assertEqual(salaries.get("2025-26"), salary)
            self.assertEqual(salaries.get("2026-27"), salary)
            self.assertNotIn("2027-28", salaries)

    def test_playable_canonical_uses_fresh_contract_overrides(self):
        data = load_or_build(ROOT, ROOT / "data/canonical")
        players = {player["normalized_name"]: player for player in data["players"]}
        contracts = {contract["player_id"]: contract for contract in data["contracts"]}
        for name, salary in {"bub carrington": 4_750_000, "cam whitmore": 5_500_000}.items():
            contract = contracts[players[name]["id"]]
            salaries = {row["season"]: row.get("salary") for row in contract.get("seasons", [])}
            self.assertEqual(contract.get("status"), "manual_gameplay_confirmed")
            self.assertEqual(salaries.get("2026-27"), salary)
            self.assertNotIn("2027-28", salaries)

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

    def test_development_dashboard_uses_visible_estimated_ovr_scale(self):
        event = {"trait_deltas": {"shooting_range": 0.18, "rim_pressure": 0.14, "scheme_iq": 0.12}}
        self.assertGreaterEqual(estimated_overall_delta(event), 0.3)
        self.assertLessEqual(estimated_overall_delta({"trait_deltas": {"a": 2.0}}), 0.65)
        self.assertGreaterEqual(estimated_overall_delta({"trait_deltas": {"a": -2.0}}), -0.65)

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
        jrue = find_trade(self.plain, "Jrue Holiday", "POR", limit=6, seed=2)
        for candidate in jrue["candidates"]:
            self.assertEqual(candidate["legality"]["status"], "legal")
            user_eval = next(item for item in candidate["evaluations"] if item["perspective_team_id"] == "team_por")
            partner_eval = next(item for item in candidate["evaluations"] if item["perspective_team_id"] != "team_por")
            self.assertGreaterEqual(float(user_eval["net_value"]), -18.0)
            self.assertTrue(partner_eval["accepted"])

    def test_superstar_trade_value_benchmark_rejects_light_giannis_packages(self):
        active = with_transaction_context(self.plain)
        values = {value["player_id"]: value for value in active["player_asset_valuations"]}
        players = {player["normalized_name"]: player for player in active["players"]}
        giannis = players["giannis antetokounmpo"]
        herro = players["tyler herro"]
        jrue = players["jrue holiday"]
        self.assertGreater(market_trade_target_value(giannis, values[giannis["id"]]), market_trade_target_value(herro, values[herro["id"]]) + 6)
        self.assertGreater(market_trade_target_value(giannis, values[giannis["id"]]), market_trade_target_value(jrue, values[jrue["id"]]) + 10)
        light = evaluate_trade(
            active,
            "MIL",
            "HOU",
            [{"kind": "player", "value": "Giannis Antetokounmpo"}, {"kind": "player", "value": "Bobby Portis"}],
            [{"kind": "player", "value": "Fred VanVleet"}],
            seed=2,
        )
        mil_eval = next(item for item in light["evaluations"] if item["perspective_team_id"] == "team_mil")
        self.assertFalse(mil_eval["accepted"])
        self.assertLess(float(mil_eval["net_value"]), -40.0)

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
        self.assertEqual(decisions["team_sac"], "accept")
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

    def test_transaction_context_reuses_pick_annotation_until_inputs_change(self):
        with tempfile.TemporaryDirectory() as tmp:
            save_path = Path(tmp) / "context_cache_save.json"
            save = create_league_save(ROOT, self.plain, "GSW", save_path, seed=509)
            active = with_transaction_context(canonical_with_save(self.plain, save))
            self.assertIn("_transaction_pick_context_signature", active)
            with patch("nba_gm_data.transactions.annotate_pick_value_context", wraps=transactions_module.annotate_pick_value_context) as annotated:
                evaluate_trade(active, "GSW", "BOS", [{"kind": "player", "value": "Seth Curry"}], [], seed=1)
                evaluate_trade(active, "GSW", "BOS", [{"kind": "player", "value": "Seth Curry"}], [], seed=1)
                self.assertEqual(annotated.call_count, 0)
            original_signature = active["_transaction_pick_context_signature"]
            active.setdefault("save_team_records", {}).setdefault("team_bos", {})["wins"] = 8
            with patch("nba_gm_data.transactions.annotate_pick_value_context", wraps=transactions_module.annotate_pick_value_context) as annotated:
                refreshed = with_transaction_context(active)
                self.assertEqual(annotated.call_count, 1)
            self.assertNotEqual(original_signature, refreshed["_transaction_pick_context_signature"])
            record_signature = refreshed["_transaction_pick_context_signature"]
            movable_pick = next(pick for pick in refreshed["draft_picks"] if pick.get("current_owner_team_id") and pick.get("status") not in {"used_draft_pick", "expired_draft_pick"})
            movable_pick["current_owner_team_id"] = "team_bos" if movable_pick["current_owner_team_id"] != "team_bos" else "team_gsw"
            with patch("nba_gm_data.transactions.annotate_pick_value_context", wraps=transactions_module.annotate_pick_value_context) as annotated:
                pick_refreshed = with_transaction_context(refreshed)
                self.assertEqual(annotated.call_count, 1)
            self.assertNotEqual(record_signature, pick_refreshed["_transaction_pick_context_signature"])

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
            self.assertEqual(saved["transaction_logs"][0]["date"], "2026-01-20")
            self.assertEqual(saved["pending_ai_actions"][0]["status"], "executed")
            self.assertIn(saved["roster_overrides"][seth["id"]], {"team_was", "team_bkn"})
            again = process_ai_actions(self.plain, save_path, seed=6, execute=True, limit=1)
            self.assertEqual(again["processed_count"], 0)
            self.assertEqual(len(load_save(save_path)["transaction_logs"]), 1)

    def test_trade_application_prunes_stale_offers_and_blocks_recently_traded_players(self):
        seth = next(player for player in self.plain["players"] if player["name"] == "Seth Curry")

        def player_trade(proposal_id: str, to_team_id: str) -> dict:
            return {
                "proposal": {
                    "id": proposal_id,
                    "date": "2026-01-20",
                    "from_team_id": "team_gsw",
                    "to_team_id": to_team_id,
                    "from_assets": [{"kind": "player", "id": seth["id"], "label": "Seth Curry"}],
                    "to_assets": [],
                },
                "legality": {"status": "legal", "issues": []},
                "accepted_by_all": True,
                "evaluations": [],
            }

        with tempfile.TemporaryDirectory() as tmp:
            save_path = Path(tmp) / "stale_offer_save.json"
            save = create_league_save(ROOT, self.plain, "GSW", save_path, seed=61)
            first = player_trade("seth_to_was", "team_was")
            second = player_trade("seth_to_bkn", "team_bkn")
            save["pending_trade_proposals"] = [first, second]
            save["user_trade_offers"] = [{**second, "offer_context": {"status": "pending_user_review"}}]
            write_save(save_path, save)

            applied = apply_trade_to_save(save_path, "seth_to_was", date="2026-01-20")
            self.assertEqual(applied["status"], "applied")
            saved = load_save(save_path)
            self.assertFalse(any((item.get("proposal") or {}).get("id") == "seth_to_bkn" for item in saved.get("pending_trade_proposals", [])))
            self.assertEqual(saved["user_trade_offers"][0]["offer_context"]["status"], "stale_asset_moved")

        with tempfile.TemporaryDirectory() as tmp:
            save_path = Path(tmp) / "stale_live_apply_save.json"
            save = create_league_save(ROOT, self.plain, "GSW", save_path, seed=62)
            save.setdefault("roster_overrides", {})[seth["id"]] = "team_was"
            save["pending_trade_proposals"] = [player_trade("stale_seth", "team_bkn")]
            write_save(save_path, save)
            skipped = apply_trade_to_save(save_path, "stale_seth", date="2026-01-20")
            self.assertEqual(skipped["status"], "not_applied_stale_assets")
            self.assertTrue(any("no longer on" in issue for issue in skipped["issues"]))

        with tempfile.TemporaryDirectory() as tmp:
            save_path = Path(tmp) / "recent_trade_save.json"
            save = create_league_save(ROOT, self.plain, "GSW", save_path, seed=63)
            save["state"] = {"current_date": "2026-01-20", "phase": "regular_season", "legal_actions": ["trades"]}
            save["transaction_logs"] = [
                {
                    "id": "recent_seth_trade",
                    "date": "2026-01-01",
                    "transaction_type": "trade",
                    "status": "applied_to_save_ledger",
                    "assets": {"from_assets": [{"kind": "player", "id": seth["id"], "label": "Seth Curry"}], "to_assets": []},
                }
            ]
            write_save(save_path, save)
            active = canonical_with_save(self.plain, load_save(save_path))
            report = evaluate_trade(active, "GSW", "WAS", [{"kind": "player", "value": "Seth Curry"}], [], seed=1, date="2026-01-20")
            self.assertEqual(report["legality"]["status"], "illegal")
            self.assertTrue(any("last 60 days" in issue for issue in report["legality"]["issues"]))

        with tempfile.TemporaryDirectory() as tmp:
            save_path = Path(tmp) / "recent_signing_save.json"
            save = create_league_save(ROOT, self.plain, "GSW", save_path, seed=64)
            save["state"] = {"current_date": "2026-07-02", "phase": "free_agency", "legal_actions": ["contracts", "trades"]}
            save.setdefault("roster_overrides", {})[seth["id"]] = "team_gsw"
            save["transaction_logs"] = [
                {
                    "id": "same_day_seth_signing",
                    "date": "2026-07-02",
                    "transaction_type": "free_agent_signing",
                    "status": "applied_to_save_ledger",
                    "assets": {"player_id": seth["id"], "contract": {"annual_salary": 4_000_000}},
                }
            ]
            write_save(save_path, save)
            active = canonical_with_save(self.plain, load_save(save_path))
            locked = evaluate_trade(active, "GSW", "WAS", [{"kind": "player", "value": "Seth Curry"}], [], seed=1, date="2026-07-02")
            self.assertEqual(locked["legality"]["status"], "illegal")
            self.assertTrue(any("cannot be traded until Dec. 1" in issue for issue in locked["legality"]["issues"]))
            unlocked = evaluate_trade(active, "GSW", "WAS", [{"kind": "player", "value": "Seth Curry"}], [], seed=1, date="2026-12-01")
            self.assertFalse(any("cannot be traded until Dec. 1" in issue for issue in unlocked["legality"]["issues"]))

        with tempfile.TemporaryDirectory() as tmp:
            save_path = Path(tmp) / "rejected_apply_save.json"
            save = create_league_save(ROOT, self.plain, "GSW", save_path, seed=65)
            rejected = player_trade("rejected_seth", "team_was")
            rejected["accepted_by_all"] = False
            rejected["evaluations"] = [
                {"perspective_team_id": "team_gsw", "team_abbrev": "GSW", "decision": "reject", "accepted": False, "net_value": -1.0},
                {"perspective_team_id": "team_was", "team_abbrev": "WAS", "decision": "reject", "accepted": False, "net_value": -1.0},
            ]
            save["pending_trade_proposals"] = [rejected]
            write_save(save_path, save)
            blocked = apply_trade_to_save(save_path, "rejected_seth", date="2026-01-20")
            self.assertEqual(blocked["status"], "not_applied_rejected")
            self.assertEqual(len(load_save(save_path).get("transaction_logs", [])), 0)

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

    def test_free_agent_investigation_shows_real_durability_flag(self):
        players = {player["name"]: player for player in self.plain["players"]}
        ayo = players["Ayo Dosunmu"]
        flag = free_agent_durability_flag(self.plain, ayo)
        self.assertNotIn("Unknown", flag)
        self.assertIn("/10", flag)
        self.assertIn("GP/yr", flag)

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
        self.assertIn(cj["negotiation"]["status"], {"original_contract_shorter_than_three_years", "not_in_extension_window"})
        phx_offer = evaluate_signing(self.plain, "LeBron James", "PHX", 2, 35, seed=3)
        was_offer = evaluate_signing(self.plain, "LeBron James", "WAS", 2, 35, seed=3)
        self.assertTrue(phx_offer["accepted_by_all"])
        self.assertEqual(was_offer["legality"]["status"], "legal")

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

    def test_extension_override_preserves_current_contract_season(self):
        with tempfile.TemporaryDirectory() as tmp:
            save_path = Path(tmp) / "extension_save.json"
            save = create_league_save(ROOT, self.plain, "GSW", save_path, seed=41)
            active = canonical_with_save(self.plain, save)
            curry = next(player for player in active["players"] if player["normalized_name"] == "stephen curry")
            current_contract = next(contract for contract in active["contracts"] if contract["player_id"] == curry["id"])
            negotiation_id = "test_curry_extension"
            accepted_offer = {
                "id": "test_curry_extension_offer",
                "negotiation_id": negotiation_id,
                "team_id": curry["team_id"],
                "player_id": curry["id"],
                "offer_type": "extension",
                "round": 1,
                "years": 1,
                "start_season": "2026-27",
                "annual_salary": 42_500_000,
                "total_value": 42_500_000,
                "status": "accepted",
            }
            save["pending_contract_negotiations"].append(
                {
                    "negotiation": {
                        "id": negotiation_id,
                        "negotiation_type": "extension",
                        "player_id": curry["id"],
                        "player_name": curry["name"],
                        "team_id": curry["team_id"],
                        "date": "2026-01-10",
                        "current_contract_seasons": current_contract["seasons"],
                    },
                    "decision": {"accepted": True, "accepted_offer": accepted_offer},
                    "accepted": True,
                }
            )
            write_save(save_path, save)
            self.assertEqual(apply_contract_to_save(save_path, negotiation_id, date="2026-01-10")["status"], "applied")
            updated = canonical_with_save(self.plain, load_save(save_path))
            contract = next(contract for contract in updated["contracts"] if contract["player_id"] == curry["id"])
            salaries = {row["season"]: row.get("salary") for row in contract["seasons"]}
            self.assertIsNotNone(salaries.get("2025-26"))
            self.assertEqual(salaries.get("2026-27"), 62_587_158)
            self.assertEqual(salaries.get("2027-28"), 42_500_000)
        with tempfile.TemporaryDirectory() as tmp:
            save_path = Path(tmp) / "midseason_extension_save.json"
            save = create_league_save(ROOT, self.plain, "GSW", save_path, seed=42)
            active = canonical_with_save(self.plain, save)
            curry = next(player for player in active["players"] if player["normalized_name"] == "stephen curry")
            negotiation_id = "test_curry_midseason_extension"
            existing_salary = 59_606_817
            accepted_offer = {
                "id": "test_curry_midseason_extension_offer",
                "negotiation_id": negotiation_id,
                "team_id": curry["team_id"],
                "player_id": curry["id"],
                "offer_type": "extension",
                "round": 1,
                "years": 1,
                "start_season": "2026-27",
                "annual_salary": 42_500_000,
                "total_value": 42_500_000,
                "status": "accepted",
            }
            save["pending_contract_negotiations"].append(
                {
                    "negotiation": {
                        "id": negotiation_id,
                        "negotiation_type": "extension",
                        "player_id": curry["id"],
                        "player_name": curry["name"],
                        "team_id": curry["team_id"],
                        "date": "2027-01-10",
                        "current_contract_seasons": [{"season": "2026-27", "salary": existing_salary}],
                    },
                    "decision": {"accepted": True, "accepted_offer": accepted_offer},
                    "accepted": True,
                }
            )
            write_save(save_path, save)
            self.assertEqual(apply_contract_to_save(save_path, negotiation_id, date="2027-01-10")["status"], "applied")
            updated = canonical_with_save(self.plain, load_save(save_path))
            contract = next(contract for contract in updated["contracts"] if contract["player_id"] == curry["id"])
            salaries = {row["season"]: row.get("salary") for row in contract["seasons"]}
            self.assertEqual(salaries.get("2026-27"), existing_salary)
            self.assertEqual(salaries.get("2027-28"), 42_500_000)
            dashboard = team_dashboard(ROOT, self.plain, save_path, "GSW")
            dashboard_curry = next(player for player in dashboard["rotation"] if player["name"] == "Stephen Curry")
            self.assertEqual(dashboard_curry["salary_by_year"].get("2026-27"), 59.6)
            self.assertEqual(dashboard_curry["salary_by_year"].get("2027-28"), 42.5)
        self.assertEqual(extension_safe_year_limit({"id": "retiring_test_player", "age": 42, "minutes_projection": 8}, "2026-27", 5), 1)
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
                pick.get("protection_summary") or pick.get("protections") or "",
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

    def test_team_asset_lists_show_cap_context(self):
        with tempfile.TemporaryDirectory() as tmp:
            save_path = Path(tmp) / "asset_cap_save.json"
            save = create_league_save(ROOT, self.plain, "GSW", save_path, seed=66)
            active = canonical_with_save(self.plain, save)
            with patch("builtins.input", return_value="0"), redirect_stdout(StringIO()) as output:
                selected = choose_assets(active, save, "GSW", "Assets from GSW", save_path=save_path)
            self.assertIsNone(selected)
            text = output.getvalue()
            self.assertIn("Cap: payroll", text)
            self.assertIn("tax room", text)
            self.assertIn("hard-cap room", text)

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

    def test_staff_contract_expiry_creates_user_retention_window(self):
        with tempfile.TemporaryDirectory() as tmp:
            save_path = Path(tmp) / "league_save.json"
            save = create_league_save(ROOT, self.plain, "GSW", save_path, seed=22)
            head = next(slot for slot in save["staff_slots"] if slot["team_id"] == "team_gsw" and slot["slot"] == "head_coach")
            old_name = head["name"]
            head["contract"]["years_remaining"] = 1
            save["state"]["current_date"] = "2026-10-01"
            age_staff_contracts(save)
            new_head = next(slot for slot in save["staff_slots"] if slot["team_id"] == "team_gsw" and slot["slot"] == "head_coach")
            self.assertEqual(new_head["name"], old_name)
            self.assertEqual(new_head["market_status"], "contract_expired_pending_user_decision")
            self.assertTrue(any(window.get("staff_name") == old_name and window.get("status") == "pending_user_decision" for window in save.get("staff_retention_windows", [])))

    def test_ai_staff_expiry_retains_elite_staff_within_budget(self):
        with tempfile.TemporaryDirectory() as tmp:
            save_path = Path(tmp) / "ai_staff_retention.json"
            save = create_league_save(ROOT, self.plain, "GSW", save_path, seed=434)
            staff = next(slot for slot in save["staff_slots"] if slot["team_id"] == "team_bos" and slot["slot"] == "development_lead")
            staff["name"] = "Elite Development Lead"
            staff["skill_traits"] = {key: 88.0 for key in staff["skill_traits"]}
            staff["personality_traits"] = {key: 86.0 for key in staff["personality_traits"]}
            staff["contract"]["annual_salary_millions"] = 3.0
            staff["contract"]["years_remaining"] = 1
            save["team_records"]["team_bos"] = {"team_id": "team_bos", "team_abbrev": "BOS", "wins": 52, "losses": 30}
            save["state"]["current_date"] = "2026-10-01"
            age_staff_contracts(save, self.plain, seed=434)
            retained = next(slot for slot in save["staff_slots"] if slot["team_id"] == "team_bos" and slot["slot"] == "development_lead")
            self.assertEqual(retained["name"], "Elite Development Lead")
            self.assertEqual(retained["market_status"], "employed")
            self.assertGreaterEqual(int(retained["contract"]["years_remaining"]), 2)
            self.assertFalse(any(item.get("name") == "Elite Development Lead" for item in save.get("former_staff", [])))
            spent = sum(float(slot.get("contract", {}).get("annual_salary_millions") or 0.0) for slot in save["staff_slots"] if slot.get("team_id") == "team_bos")
            self.assertLessEqual(spent, staff_budget_for_team(self.plain, "team_bos") + 0.01)

    def test_support_staff_can_be_fired_for_role_specific_failures(self):
        with tempfile.TemporaryDirectory() as tmp:
            save_path = Path(tmp) / "support_staff_fire.json"
            save = create_league_save(ROOT, self.plain, "GSW", save_path, seed=435)
            staff = next(slot for slot in save["staff_slots"] if slot["team_id"] == "team_bos" and slot["slot"] == "development_lead")
            staff["skill_traits"] = {key: 48.0 for key in staff["skill_traits"]}
            staff["personality_traits"] = {key: 50.0 for key in staff["personality_traits"]}
            save["team_records"]["team_bos"] = {"team_id": "team_bos", "team_abbrev": "BOS", "wins": 42, "losses": 40}
            save["development_events"] = [
                {
                    "id": f"poor_dev_{idx}",
                    "team_id": "team_bos",
                    "player_id": f"player_{idx}",
                    "trait_deltas": {"release_speed": -0.02, "scheme_iq": 0.0},
                }
                for idx in range(18)
            ]
            payload = simulate_ai_staff_changes(self.plain, save, "2026-06-30", "2026-09-01", seed=435, limit=10)
            rec = next((item for item in payload["recommendations"] if item["team_id"] == "team_bos" and item["slot"] == "development_lead"), None)
            self.assertIsNotNone(rec)
            self.assertIn("development", rec["firing_reason"])

    def test_box_score_influence_sort_key_values_all_around_lines(self):
        scorer = {"points": 28, "rebounds": 2, "assists": 1, "steals": 0, "blocks": 0, "turnovers": 4}
        all_around = {"points": 17, "rebounds": 10, "assists": 9, "steals": 2, "blocks": 1, "turnovers": 1}
        self.assertGreater(box_score_influence(all_around), box_score_influence(scorer))

    def test_extension_eligibility_uses_original_term_and_active_save_season(self):
        extensions = {candidate["name"]: candidate for candidate in extension_candidates_report(self.plain, "GSW")["candidates"]}
        self.assertTrue(extensions["Stephen Curry"]["eligible"])
        self.assertEqual(extensions["Stephen Curry"]["eligibility_status"], "eligible_extension_window")
        self.assertFalse(extensions["Jimmy Butler III"]["eligible"])
        contract = {"_active_season": "2026-27", "seasons": [{"season": "2025-26", "salary": 10}, {"season": "2026-27", "salary": 20}]}
        self.assertEqual(current_salary(contract), 20)
        rookie_projection = {"status": "save_state_contract_override", "_active_season": "2025-26", "seasons": [{"season": "2026-27", "salary": 3_100_000}]}
        self.assertEqual(current_salary(rookie_projection), 3_100_000)
        expired_contract = {"_active_season": "2026-27", "seasons": [{"season": "2025-26", "salary": 5_000_000}]}
        self.assertIsNone(current_salary(expired_contract))

    def test_ai_extensions_have_leaguewide_volume_and_trade_demand_pressure(self):
        with tempfile.TemporaryDirectory() as tmp:
            save_path = Path(tmp) / "ai_extensions.json"
            save = create_league_save(ROOT, self.plain, "GSW", save_path, seed=123)
            good_teams = {"team_phi", "team_lac", "team_phx", "team_mil", "team_bos", "team_nyk", "team_okc", "team_cle"}
            for team in self.plain["teams"]:
                if team["id"] == save["meta"]["user_team_id"]:
                    continue
                good = team["id"] in good_teams
                save["team_records"][team["id"]] = {
                    "team_id": team["id"],
                    "team_abbrev": team["abbrev"],
                    "wins": 24 if good else 9,
                    "losses": 10 if good else 25,
                }
            result = process_ai_extensions(self.plain, save, "2026-01-10", seed=123, limit=24)
            self.assertGreaterEqual(result["applied_count"], 18)
            self.assertGreaterEqual(result["refusal_count"], 1)
            self.assertGreaterEqual(
                len([log for log in save.get("transaction_logs", []) if log.get("transaction_type") == "extension"]),
                18,
            )
            self.assertTrue(save.get("ai_trade_pressure_player_ids"))
            self.assertTrue(any(event.get("kind") == "trade_demand" for event in save.get("league_events", [])))

    def test_ai_extension_timing_and_older_player_caution(self):
        save = {
            "version": "league_save_v1",
            "state": {"current_date": "2025-10-01", "phase": "regular_season"},
            "team_records": {"team_test": {"wins": 8, "losses": 18}},
            "player_season_stats": {
                "old_player": {"games": 14, "points": 110},
                "young_star": {"games": 14, "points": 350},
            },
        }
        young = {"id": "young_star", "display_age": 23, "minutes_projection": 33}
        older = {"id": "old_player", "display_age": 32, "minutes_projection": 26}
        high_due = ai_extension_due_date(save, {"team_id": "team_test"}, young, 85.0, seed=9)
        lower_due = ai_extension_due_date(save, {"team_id": "team_test"}, older, 58.0, seed=9)
        self.assertLess(high_due, lower_due)
        pass_outlook = ai_extension_team_pass_outlook(
            save,
            {"team_id": "team_test", "projected_aav_millions": 22.0},
            older,
            "team_test",
            priority=60.0,
        )
        self.assertIsNotNone(pass_outlook)
        self.assertTrue(pass_outlook["team_passed_on_extension"])

    def test_ai_staff_can_fire_weak_coordinator_before_secure_head_coach(self):
        with tempfile.TemporaryDirectory() as tmp:
            save_path = Path(tmp) / "coordinator_weak_link.json"
            save = create_league_save(ROOT, self.plain, "GSW", save_path, seed=420)
            team_id = "team_atl"
            save["state"] = {"current_date": "2026-01-20", "phase": "regular_season", "legal_actions": ["staff_changes"]}
            save["team_records"][team_id] = {"team_id": team_id, "team_abbrev": "ATL", "wins": 10, "losses": 30}
            save["team_game_logs"] = [
                {"team_id": team_id, "date": f"2026-01-{idx + 1:02d}", "result": "W" if idx < 2 else "L"}
                for idx in range(17)
            ]
            for staff in save["staff_slots"]:
                if staff.get("team_id") == team_id and staff.get("slot") == "head_coach":
                    for key in staff.get("skill_traits", {}):
                        staff["skill_traits"][key] = 90.0
                    staff["job_security"] = 84.0
                if staff.get("team_id") == team_id and staff.get("slot") == "offensive_coordinator":
                    for key in staff.get("skill_traits", {}):
                        staff["skill_traits"][key] = 45.0
                    staff["job_security"] = 35.0
            payload = simulate_ai_staff_changes(self.plain, save, "2026-01-01", "2026-01-20", seed=99, limit=10)
            atl_recs = [item for item in payload["recommendations"] if item["team_id"] == team_id]
            self.assertTrue(any(item["slot"] == "offensive_coordinator" for item in atl_recs))
            self.assertFalse(any(item["slot"] == "head_coach" for item in atl_recs))

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

    def test_stale_rotation_recommendations_are_pruned_when_player_leaves(self):
        curry = next(player for player in self.plain["players"] if player["name"] == "Stephen Curry")
        with tempfile.TemporaryDirectory() as tmp:
            save_path = Path(tmp) / "stale_rotation_rec.json"
            save = create_league_save(ROOT, self.plain, "GSW", save_path, seed=414)
            save["rotation_recommendations"][curry["id"]] = {
                "player_id": curry["id"],
                "team_id": "team_gsw",
                "target_minutes": 24.0,
                "coach_commitment": 0.68,
                "status": "active",
            }
            save["roster_overrides"][curry["id"]] = "team_bos"
            self.assertEqual(prune_rotation_recommendations(save, self.plain), 1)
            self.assertNotIn(curry["id"], save["rotation_recommendations"])
            write_save(save_path, save)
            team_dashboard(ROOT, self.plain, save_path, "GSW")
            self.assertNotIn(curry["id"], load_save(save_path)["rotation_recommendations"])

    def test_free_agency_day_recap_surfaces_ai_trade_news(self):
        with tempfile.TemporaryDirectory() as tmp:
            save_path = Path(tmp) / "fa_trade_news.json"
            create_league_save(ROOT, self.plain, "GSW", save_path, seed=415)
            result = {"accepted_count": 0, "ask_adjusted_count": 0, "accepted_offers": [], "ai_trade_news": [{"headline": "Trade completed: Team A pick for Team B player."}]}
            with redirect_stdout(StringIO()) as output:
                print_free_agency_day_recap(self.plain, save_path, 1, result)
            text = output.getvalue()
            self.assertIn("League trades", text)
            self.assertIn("Team A pick", text)

    def test_head_coach_firing_reason_is_major_league_event(self):
        with tempfile.TemporaryDirectory() as tmp:
            save_path = Path(tmp) / "staff_firing_reason.json"
            save = create_league_save(ROOT, self.plain, "GSW", save_path, seed=416)
            result = fire_staff_from_save(save, "team_bos", "head_coach", reason="on 2-15 skid")
            self.assertEqual(result["status"], "applied")
            write_save(save_path, save)
            view = league_events_view(self.plain, save_path, major_only=True, limit=10)
            headlines = [event.get("headline", "") for event in view.get("events", [])]
            self.assertTrue(any("on 2-15 skid" in headline for headline in headlines))

    def test_ai_head_coach_firings_reach_realistic_bad_season_volume(self):
        with tempfile.TemporaryDirectory() as tmp:
            save_path = Path(tmp) / "staff_firing_volume.json"
            save = create_league_save(ROOT, self.plain, "GSW", save_path, seed=417)
            save["state"] = {"current_date": "2026-06-20", "phase": "offseason", "legal_actions": ["staff_changes"]}
            for idx, team in enumerate(self.plain["teams"]):
                if team["id"] == save["meta"]["user_team_id"]:
                    continue
                wins = 18 + (idx % 10)
                save["team_records"][team["id"]] = {
                    "team_id": team["id"],
                    "team_abbrev": team["abbrev"],
                    "wins": wins,
                    "losses": 82 - wins,
                }
            payload = simulate_ai_staff_changes(self.plain, save, "2026-04-15", "2026-06-20", seed=417, limit=10)
            head_coach_moves = [item for item in payload["recommendations"] if item["slot"] == "head_coach"]
            self.assertGreaterEqual(len(head_coach_moves), 4)
            self.assertTrue(all(item.get("firing_reason") for item in head_coach_moves))

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
        fourth = queue_aggregated_press_event(save, "staff_hire", "GSW hires Dana Price as Head Coach.", ["team_gsw"], "2026-01-10")
        self.assertEqual(first["id"], second["id"])
        self.assertIsNone(third)
        self.assertNotEqual(first["id"], fourth["id"])
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
        trae = player_feature_vector(plain, players["trae young"])
        sga = player_feature_vector(plain, players["shai gilgeous alexander"])
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
        self.assertLessEqual(plausible_point_cap({"minutes": 34, "player": players["stephen curry"]}, curry.features), 30)
        self.assertLessEqual(assist_rate_for_player(players["stephen curry"], curry.features) * 34, 8.5)
        self.assertLess(luka.features["defensive_events"], 55)
        self.assertGreater(luka.features["defensive_weak_link"], 55)
        self.assertGreaterEqual(assist_rate_for_player(players["luka doncic"], luka.features) * 36, 9.0)
        self.assertLess(clowney.features["usage"], 68)
        self.assertGreaterEqual(wemby.features["rim_deterrence"], 75)
        self.assertGreaterEqual(draymond.features["passing"], 85)
        self.assertGreaterEqual(assist_rate_from_features(trae.features), 0.27)
        self.assertGreaterEqual(assist_rate_for_player(players["trae young"], trae.features), 0.31)
        self.assertLessEqual(
            plausible_point_cap({"minutes": 33.5, "player": players["shai gilgeous alexander"]}, sga.features),
            34,
        )
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

    def test_random_team_default_creates_seeded_team_filename(self):
        with tempfile.TemporaryDirectory() as tmp:
            expected = deterministic_random_team(self.plain, seed=17)
            with patch("builtins.input", side_effect=["", "", "", ""]), redirect_stdout(StringIO()):
                path = choose_save_path(Path(tmp), self.plain, None, None, seed=17)
            self.assertEqual(path.name, f"{expected.lower()}_test.json")
            self.assertTrue(path.exists())
            self.assertEqual(load_save(path)["meta"]["user_team_abbrev"], expected)

        with tempfile.TemporaryDirectory() as tmp:
            rng = patch("nba_gm_data.play.random.SystemRandom")
            with rng as system_random:
                system_random.return_value.randrange.side_effect = [1, 2, 3]
                paths = []
                for idx in range(3):
                    with patch("builtins.input", side_effect=["", ""]), redirect_stdout(StringIO()):
                        paths.append(choose_save_path(Path(tmp), self.plain, Path(tmp) / f"save{idx}.json", "random", seed=None))
            teams = [load_save(path)["meta"]["user_team_abbrev"] for path in paths]
            self.assertEqual(teams, [deterministic_random_team(self.plain, seed) for seed in [1, 2, 3]])
            self.assertGreater(len(set(teams)), 1)

    def test_unseeded_lottery_uses_fresh_entropy_but_seeded_lottery_stays_deterministic(self):
        self.assertEqual(lottery_seed(17), 17)
        draws = {lottery_seed(None) for _ in range(5)}
        self.assertGreater(len(draws), 1)

    def test_league_leaders_are_stats_only_and_traits_are_separate(self):
        with tempfile.TemporaryDirectory() as tmp:
            save_path = Path(tmp) / "save.json"
            create_league_save(ROOT, self.plain, "GSW", save_path, seed=4)
            with self.assertRaises(ValueError):
                league_leaders(self.plain, save_path, stat="overall", limit=5)
            rows = league_trait_rows(self.plain, save_path, "overall")
            self.assertGreater(len(rows), 20)
            self.assertGreaterEqual(rows[0]["attrs"]["overall"], rows[1]["attrs"]["overall"])
            self.assertNotIn("raw_attrs", rows[0])
            raw_attrs = player_attribute_summary(self.plain, rows[0]["player"]["id"])
            self.assertAlmostEqual(rows[0]["attrs"]["overall"], raw_attrs["overall"], delta=0.5)
            self.assertIn("contract", rows[0])
            self.assertIn("minutes", rows[0])
            thresholds = league_trait_rating_thresholds(rows)
            class TtyStringIO(StringIO):
                def isatty(self):
                    return True

            stdout = TtyStringIO()
            with patch.dict(os.environ, {"NO_COLOR": ""}, clear=False), redirect_stdout(stdout):
                print_league_trait_table(rows[:3], thresholds=thresholds)
            self.assertIn("\033[", stdout.getvalue())
            guide = ratings_guide(self.plain)
            self.assertGreaterEqual(len(guide["rows"]), 15)
            self.assertIn("engine calculations use the same underlying raw trait values", guide["display_scale"])
            self.assertIn("full-health 2026 league ratings prior", guide["calibration_stack"])

    def test_social_subject_preserves_initials_and_avoids_truncation_dots(self):
        text = "Trade completed: T.J. McConnell, 2027 R1 HOU (own pick) for Norman Powell, 2028 R2 DEN (own pick)."
        subject = social_subject(text)
        self.assertIn("T.J. McConnell", subject)
        self.assertNotEqual(subject, "Trade completed: T.J")
        self.assertNotIn("...", subject)
        headline = trade_headline_from_payload({"from_assets": [{"kind": "player", "name": "T.J. McConnell"}], "to_assets": []})
        self.assertEqual(headline, "Trade completed: T.J. McConnell for future considerations.")
        self.assertNotIn("for assets", headline)

    def test_trade_inspection_includes_player_height(self):
        players = {player["normalized_name"]: player for player in self.plain["players"]}
        dlo = players["dangelo russell"]
        daniss = players["daniss jenkins"]
        candidate = {
            "summary": {"headline": "Inspection test"},
            "proposal": {
                "id": "proposal_height_test",
                "from_team_id": dlo["team_id"],
                "to_team_id": daniss["team_id"],
                "from_assets": [{"kind": "player", "id": dlo["id"], "label": dlo["name"]}],
                "to_assets": [{"kind": "player", "id": daniss["id"], "label": daniss["name"]}],
            },
            "evaluations": [],
            "legality": {"status": "legal", "issues": []},
        }
        stdout = StringIO()
        with redirect_stdout(stdout):
            print_trade_offer_details(self.plain, candidate)
        output = stdout.getvalue()
        self.assertIn("Daniss Jenkins", output)
        self.assertIn("D'Angelo Russell", output)
        self.assertIn("age 24 ht 6'4\"", output)
        self.assertIn("age 29 ht 6'3\"", output)

    def test_late_first_and_early_second_pick_values_are_neighbors(self):
        base = {"season": "2026", "current_owner_team_id": "team_gsw", "original_team_id": "team_gsw", "_active_season": "2025-26"}
        pick_23 = pick_asset_value({**base, "id": "pick_2026_23_gsw", "round": 1, "overall_pick": 23}, "neutral")
        late_first = pick_asset_value({**base, "id": "pick_2026_30_gsw", "round": 1, "overall_pick": 30}, "neutral")
        early_second = pick_asset_value({**base, "id": "pick_2026_31_gsw", "round": 2, "overall_pick": 31}, "neutral")
        pick_33 = pick_asset_value({**base, "id": "pick_2026_33_gsw", "round": 2, "overall_pick": 33}, "neutral")
        top_first = pick_asset_value({**base, "id": "pick_2026_1_gsw", "round": 1, "overall_pick": 1}, "neutral")
        lottery_first = pick_asset_value({**base, "id": "pick_2026_10_gsw", "round": 1, "overall_pick": 10}, "neutral")
        self.assertGreater(pick_23, late_first)
        self.assertGreater(late_first, pick_33)
        self.assertGreater(late_first, early_second)
        self.assertLess(late_first - early_second, 8.0)
        self.assertGreater(top_first - lottery_first, 15.0)
        self.assertGreater(lottery_first - late_first, 35.0)
        stale = {"draft_picks": [{**base, "id": "stale_pick", "round": 1, "overall_pick": 23, "_protection_value_factor": 0.42}], "pick_obligations": [], "locked_pick_assets": []}
        annotate_pick_obligation_context(stale)
        self.assertNotIn("_protection_value_factor", stale["draft_picks"][0])

    def test_current_injury_is_modest_value_risk_but_history_still_matters(self):
        active = player_health_risk({"durability": 62}, {"availability_status": "active"})
        temporarily_out = player_health_risk({"durability": 62}, {"availability_status": "out", "current_injury_id": "injury_test"})
        recurring = player_health_risk(
            {"durability": 50, "injury_prone": True, "major_prior_injuries": [{"body_area": "leg"}, {"body_area": "back"}]},
            {"availability_status": "active"},
        )
        self.assertLessEqual(temporarily_out - active, 2.0)
        self.assertGreater(recurring - active, 10.0)

    def test_startup_injured_stars_keep_long_term_trade_value(self):
        with tempfile.TemporaryDirectory() as tmp:
            save_path = Path(tmp) / "startup_injured_star_value.json"
            save = create_league_save(ROOT, self.plain, "GSW", save_path, seed=701)
            active = canonical_with_save(self.plain, save)
            enriched = with_transaction_context(active)
            valuations = {value["player_id"]: value for value in enriched["player_asset_valuations"]}
            players = {player["name"]: player for player in enriched["players"]}
            for name in ["Tyrese Haliburton", "Jayson Tatum"]:
                player = players[name]
                self.assertEqual(float(player.get("minutes_projection") or 0.0), 0.0)
                self.assertTrue(player.get("_trade_value_unavailable"))
                self.assertGreaterEqual(float(player.get("_trade_value_minutes_projection") or 0.0), 27.0)
                self.assertGreater(market_trade_target_value(player, valuations[player["id"]]), 70.0)

    def test_live_draft_state_syncs_pick_ids_to_saved_lottery_order(self):
        save = {
            "draft_orders": {
                "2026": {
                    "draft_order": [
                        {"id": "pick_2026_1_chi", "pick_id": "pick_2026_1_chi", "overall_pick": 1, "round": 1, "season": "2026", "original_team_id": "team_chi", "current_owner_team_id": "team_chi"},
                        {"id": "pick_2026_2_lac", "pick_id": "pick_2026_2_lac", "overall_pick": 2, "round": 1, "season": "2026", "original_team_id": "team_lac", "current_owner_team_id": "team_lac"},
                    ]
                }
            },
            "draft_state": {
                "year": "2026",
                "current_index": 0,
                "draft": {
                    "pending_draft_selections": [
                        {"selection": {"overall_pick": 1, "pick_id": "pick_2026_1_chi", "team_id": "team_chi"}, "pick": {"id": "pick_2026_1_chi"}},
                        {"selection": {"overall_pick": 2, "pick_id": "pick_2026_2_uta", "team_id": "team_uta"}, "pick": {"id": "pick_2026_2_uta"}},
                    ]
                },
            },
        }
        self.assertTrue(sync_live_draft_state_to_saved_order(self.plain, save, "2026"))
        second = save["draft_state"]["draft"]["pending_draft_selections"][1]
        self.assertEqual(second["selection"]["pick_id"], "pick_2026_2_lac")
        self.assertEqual(second["selection"]["team_id"], "team_lac")

        duplicate = {
            "draft_pick_overrides": {"pick_2026_1_chi": "team_gsw"},
            "draft_orders": {
                "2026": {
                    "draft_order": [
                        {"id": "pick_2026_1_chi", "pick_id": "pick_2026_1_chi", "overall_pick": 1, "round": 1, "season": "2026", "original_team_id": "team_chi", "current_owner_team_id": "team_chi"},
                        {"id": "pick_2026_1_chi", "pick_id": "pick_2026_1_chi", "overall_pick": 2, "round": 1, "season": "2026", "original_team_id": "team_lac", "current_owner_team_id": "team_lac"},
                    ]
                }
            },
            "draft_state": {
                "year": "2026",
                "current_index": 0,
                "draft": {
                    "pending_draft_selections": [
                        {"selection": {"overall_pick": 1, "pick_id": "pick_2026_1_chi", "team_id": "team_chi"}, "pick": {"id": "pick_2026_1_chi"}},
                        {"selection": {"overall_pick": 2, "pick_id": "pick_2026_2_lac", "team_id": "team_lac"}, "pick": {"id": "pick_2026_2_lac"}},
                    ]
                },
            },
        }
        self.assertTrue(sync_live_draft_state_to_saved_order(self.plain, duplicate, "2026"))
        self.assertTrue(refresh_live_draft_state_ownership(self.plain, duplicate, "2026"))
        first_dup, second_dup = duplicate["draft_state"]["draft"]["pending_draft_selections"]
        self.assertEqual(first_dup["selection"]["team_id"], "team_gsw")
        self.assertEqual(second_dup["selection"]["pick_id"], "pick_2026_2_lac")
        self.assertEqual(second_dup["selection"]["team_id"], "team_lac")

    def test_saved_lottery_order_replaces_draft_payload_order_before_persist(self):
        save = {
            "draft_orders": {
                "2026": {
                    "lottery": {"seed": 99, "method": "test_reveal"},
                    "draft_order": [
                        {"id": "pick_2026_1_chi", "pick_id": "pick_2026_1_chi", "overall_pick": 1, "round": 1, "season": "2026", "original_team_id": "team_chi", "current_owner_team_id": "team_chi"},
                        {"id": "pick_2026_2_lac", "pick_id": "pick_2026_2_lac", "overall_pick": 2, "round": 1, "season": "2026", "original_team_id": "team_lac", "current_owner_team_id": "team_lac"},
                    ],
                }
            }
        }
        draft = {
            "lottery": {"seed": 1, "method": "stale"},
            "draft_order": [
                {"id": "pick_stale_1", "pick_id": "pick_stale_1", "overall_pick": 1, "round": 1, "season": "2026", "original_team_id": "team_nyk", "current_owner_team_id": "team_nyk"},
                {"id": "pick_stale_2", "pick_id": "pick_stale_2", "overall_pick": 2, "round": 1, "season": "2026", "original_team_id": "team_lal", "current_owner_team_id": "team_lal"},
            ],
            "pending_draft_selections": [
                {"selection": {"overall_pick": 1, "pick_id": "pick_stale_1", "team_id": "team_nyk"}, "pick": {"id": "pick_stale_1"}, "team": {"id": "team_nyk", "abbrev": "NYK"}},
                {"selection": {"overall_pick": 2, "pick_id": "pick_stale_2", "team_id": "team_lal"}, "pick": {"id": "pick_stale_2"}, "team": {"id": "team_lal", "abbrev": "LAL"}},
            ],
        }
        updated = apply_saved_draft_order_to_draft(self.plain, save, "2026", draft)
        self.assertEqual(updated["lottery"]["seed"], 99)
        self.assertEqual(updated["draft_order"][0]["pick_id"], "pick_2026_1_chi")
        self.assertEqual(updated["draft_order"][1]["current_owner_team_id"], "team_lac")
        self.assertEqual(updated["pending_draft_selections"][1]["selection"]["pick_id"], "pick_2026_2_lac")
        self.assertEqual(updated["pending_draft_selections"][1]["team"]["abbrev"], "LAC")

    def test_current_year_pick_assets_keep_slot_identity(self):
        canonical = {
            "meta": {"active_season": "2025-26"},
            "draft_picks": [
                {"id": "pick_a", "season": "2026", "round": 1, "overall_pick": 11, "original_team_id": "team_lac", "current_owner_team_id": "team_gsw"},
                {"id": "pick_b", "season": "2026", "round": 1, "overall_pick": 19, "original_team_id": "team_lac", "current_owner_team_id": "team_gsw"},
            ],
        }
        picks = tradeable_picks_for_team(canonical, "team_gsw")
        self.assertEqual([pick["id"] for pick in picks], ["pick_a", "pick_b"])

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
