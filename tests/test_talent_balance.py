from copy import deepcopy
import gzip
import json
from pathlib import Path
import random
from tempfile import TemporaryDirectory
import unittest

from nba_gm_data import draft, health
from nba_gm_data.save import (apply_development_events_to_traits, canonical_with_save,
                              create_league_save, load_save, player_display_attribute_summary)
from nba_gm_data.schema import to_plain
from nba_gm_data.sim import player_feature_vector
from nba_gm_data.talent import SOURCE_ID, trait_ceiling

ROOT = Path(__file__).resolve().parents[1]


def converted(seed=17, year="2030", new=True):
    generated = to_plain(draft.generate_draft_class_records(year, seed, talent_model=new))
    by_prospect = {}
    for trait in generated["draft_prospect_traits"]:
        by_prospect.setdefault(trait["prospect_id"], []).append(trait)
    players, traits = [], []
    team = {"id": "team_gsw", "abbrev": "GSW"}
    for prospect in generated["draft_prospects"]:
        selection = {"id": prospect["id"], "prospect_id": prospect["id"], "draft_year": year,
                     "overall_pick": prospect["rank"], "team_id": team["id"]}
        contract = draft.rookie_contract_projection(selection, prospect, team, {}, draft.default_draft_model_config(), signed=True)
        onboarding = draft.rookie_onboarding_record(selection, prospect, team, contract, signed=True)
        player = draft.rookie_player_record(onboarding, prospect, team, contract)
        player["minutes_projection"] = 24
        players.append(player)
        traits.extend(draft.rookie_trait_records(player, prospect, by_prospect[prospect["id"]]))
    return generated, {"meta": {"talent_model_version": 2} if new else {}, "players": players,
                       "traits": traits, "_allow_internal_caches": True}


class TalentBalanceTests(unittest.TestCase):
    def test_new_shape_preserves_class_quality_identity_readiness_and_medicals(self):
        for seed in (17, 29, 913):
            old = to_plain(draft.generate_draft_class_records("2030", seed))
            new = to_plain(draft.generate_draft_class_records("2030", seed, talent_model=True))
            self.assertEqual(old["draft_classes"], new["draft_classes"])
            for before, after in zip(old["draft_prospects"], new["draft_prospects"], strict=True):
                allowed = {"source_ids", "potential", "ceiling", "rookie_contract_value", "scouting_prior"}
                self.assertEqual({k: v for k, v in before.items() if k not in allowed},
                                 {k: v for k, v in after.items() if k not in allowed})
                # The public board is unchanged; the true potential adds the hidden tail and a scouting miss
                # either way (prospect realism), so it can sit below the board.
                self.assertEqual(draft.prospect_evaluation_value(after, "potential"),
                                 draft.prospect_evaluation_value(before, "potential"))
                self.assertIn(SOURCE_ID, after["source_ids"])
            self.assertEqual(new, to_plain(draft.generate_draft_class_records("2030", seed, talent_model=True)))

    def test_potential_does_not_buy_current_traits_or_minutes(self):
        prospect = draft.generate_draft_class_records("2030", 17, talent_model=True)["draft_prospects"][0]
        from dataclasses import replace
        low, high = replace(prospect, potential=65), replace(prospect, potential=95)
        self.assertEqual(draft.generated_trait_values(low, random.Random(7)),
                         draft.generated_trait_values(high, random.Random(7)))
        values = draft.generated_trait_values(low, random.Random(7))
        first = draft.nba_trait_values_from_prospect(values, 55, 65, "PG", "lead_creator", talent_model=True)
        second = draft.nba_trait_values_from_prospect(values, 55, 95, "PG", "lead_creator", talent_model=True)
        self.assertEqual(first, second)
        team = {"id": "team_gsw", "abbrev": "GSW"}
        minutes = []
        for potential in (65, 95):
            body = {**to_plain(prospect), "potential": potential}
            selection = {"id": "pick", "prospect_id": body["id"], "draft_year": "2030", "overall_pick": 25, "team_id": team["id"]}
            contract = draft.rookie_contract_projection(selection, body, team, {}, draft.default_draft_model_config(), signed=True)
            onboard = draft.rookie_onboarding_record(selection, body, team, contract, signed=True)
            minutes.append(draft.rookie_player_record(onboard, body, team, contract)["minutes_projection"])
        self.assertEqual(*minutes)

    def test_weaknesses_survive_conversion_without_a_uniform_nerf(self):
        _, old = converted(new=False)
        _, new = converted()
        profiles = [[t["value"] for t in new["traits"] if t["player_id"] == p["id"]] for p in new["players"]]
        self.assertGreater(sum(min(profile) < 25 for profile in profiles), 10)
        self.assertGreater(sum(max(profile) - min(profile) > 25 for profile in profiles), 35)
        before = {(t["player_id"], t["trait_key"]): t["value"] for t in old["traits"]}
        self.assertTrue(any(t["value"] > before[t["player_id"], t["trait_key"]] for t in new["traits"]))
        self.assertTrue(any(t["value"] < before[t["player_id"], t["trait_key"]] for t in new["traits"]))
        self.assertTrue(all(5 <= t["value"] <= 95 for t in new["traits"]))

    def test_role_value_rewards_real_big_man_strengths_not_position_alone(self):
        from nba_gm_data.draft import NBA_TRAIT_LABELS
        values = {key: 30 for key in NBA_TRAIT_LABELS}
        values.update(rim_deterrence=85, offensive_rebounding=85, defensive_effort=75,
                      scheme_iq=70, stamina_cardio=65, rim_pressure=80)
        player = {"id": "specialist", "position": "C", "minutes_projection": 24}
        old = {"players": [player], "traits": [{"player_id": player["id"], "trait_key": k, "value": v} for k, v in values.items()]}
        new = {**old, "meta": {"talent_model_version": 2}}
        self.assertGreater(player_display_attribute_summary(new, player["id"])["overall"],
                           player_display_attribute_summary(old, player["id"])["overall"])
        self.assertGreater(player_feature_vector(new, player).features["impact"], player_feature_vector(old, player).features["impact"])
        uniform = {"players": [player], "traits": [{"player_id": player["id"], "trait_key": k, "value": 50} for k in values]}
        self.assertEqual(player_display_attribute_summary(uniform, player["id"])["overall"],
                         player_display_attribute_summary({**uniform, "meta": new["meta"]}, player["id"])["overall"])

    def test_capacity_is_trait_specific_seeded_and_low_realization_can_plateau(self):
        _, context = converted()
        player = context["players"][0]
        traits = [t for t in context["traits"] if t["player_id"] == player["id"]]
        capacities = [trait_ceiling(player, t["trait_key"], t["components"]["career_capacity"], .55, 17) - t["value"] for t in traits]
        self.assertGreater(max(capacities) - min(capacities), .5)
        trait = traits[0]
        profile = trait["components"]["career_capacity"]
        ceiling = trait_ceiling(player, trait["trait_key"], profile, health.prospect_development_realization(player, 17), 17)
        for month in range(1, 13):
            delta = health.monthly_trait_delta(player, trait["trait_key"], ceiling, 20, 32, {}, 0, 17, f"2031-{month:02}", 1, profile)
            self.assertLessEqual(delta, 0)
        self.assertEqual(ceiling, trait_ceiling(json.loads(json.dumps(player)), trait["trait_key"], profile,
                                               health.prospect_development_realization(player, 17), 17))

    def test_role_value_reaches_trade_market_and_retention_consumers(self):
        from nba_gm_data.transactions import build_player_asset_valuations
        from nba_gm_data.save import ai_roster_retention_score
        with gzip.open(ROOT / "data/canonical/baselines/2026-10-23-player-tuning-v3.json.gz", "rt") as handle:
            old = json.load(handle)
        new = deepcopy(old)
        new["meta"]["talent_model_version"] = 2
        player = next(p for p in old["players"] if p["name"] == "Dereck Lively II")
        before = {v.player_id: v for v in build_player_asset_valuations(old)}[player["id"]]
        after = {v.player_id: v for v in build_player_asset_valuations(new)}[player["id"]]
        self.assertGreater(after.on_court_value, before.on_court_value)
        saved = {"meta": {"season": "2026-27"}, "state": {"current_date": "2026-10-01"}}
        self.assertGreater(ai_roster_retention_score(new, saved, player), ai_roster_retention_score(old, saved, player))
        self.assertEqual(old["contracts"], new["contracts"])
        from nba_gm_data.play import trade_finder_report_for_selection, trade_apply_authorized
        with gzip.open(ROOT / "data/canonical/baselines/2026-10-23-talent-v4.json.gz", "rt") as handle:
            current = json.load(handle)
        with TemporaryDirectory() as directory:
            saved = create_league_save(ROOT, current, "POR", Path(directory) / "market.json", seed=414)
            active = canonical_with_save(current, saved)
            self.assertEqual(active["meta"]["talent_model_version"], 2)
            offers = trade_finder_report_for_selection(active, saved, "POR", "POR",
                                                       [{"kind": "player", "value": "Donovan Clingan"}], 1)
            self.assertTrue(offers["candidates"])
            self.assertTrue(any(trade_apply_authorized(offer) for offer in offers["candidates"]))

    def test_capacity_and_model_survive_development_and_serialized_reload(self):
        _, context = converted()
        ids = {p["id"] for p in context["players"][:3]}
        context["players"] = [p for p in context["players"] if p["id"] in ids]
        context["traits"] = [t for t in context["traits"] if t["player_id"] in ids]
        reloaded = deepcopy(context)
        unchanged = deepcopy(context)
        health.advance_development(context, "2031-01", 17)
        self.assertEqual(context, unchanged)
        for index in range(36):
            for probe in (context, reloaded):
                for p in probe["players"]:
                    p["age"] = 20 + index // 12
                events = health.advance_development(probe, f"{2031 + index // 12}-{index % 12 + 1:02}", 17)
                apply_development_events_to_traits(probe, events["events"])
            reloaded = json.loads(json.dumps(reloaded))
        self.assertEqual(context["traits"], reloaded["traits"])
        self.assertTrue(all(t["components"].get("career_capacity") for t in reloaded["traits"]))

    def test_v3_save_does_not_adopt_new_model(self):
        with gzip.open(ROOT / "data/canonical/baselines/2026-10-23-player-tuning-v3.json.gz", "rt") as handle:
            old = json.load(handle)
        with TemporaryDirectory() as directory:
            path = Path(directory) / "career.json"
            create_league_save(ROOT, deepcopy(old), "GSW", path, seed=17)
            candidate = deepcopy(old)
            candidate["meta"].update(starting_data_version="hypothetical-v4", talent_model_version=2)
            actual = canonical_with_save(candidate, load_save(path))
            self.assertNotIn("talent_model_version", actual["meta"])
            self.assertEqual(actual["traits"], old["traits"])
