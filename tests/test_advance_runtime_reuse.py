"""Daily league reuse must preserve fresh-state behavior and its call boundary."""
from copy import deepcopy
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from nba_gm_data import save as sv
from nba_gm_data.cli import DEFAULT_OUT, load_or_build


class AdvanceRuntimeGuardTests(unittest.TestCase):
    def fixture(self):
        return {"version": sv.SAVE_VERSION,
                "meta": {"season": "2026-27", "seed": 55},
                "state": {"current_date": "2026-11-28", "phase": "regular_season"},
                "roster_overrides": {"p": "team"},
                "contract_overrides": {"p": {"seasons": [{"salary": 100}]}},
                "development_events": [], "free_agent_player_ids": ["fa"]}

    def test_hot_fields_can_change_but_nested_materialized_inputs_invalidate(self):
        for key in sv._AdvanceRuntimeState._INPUT_KEYS:
            with self.subTest(key=key):
                save = self.fixture()
                runtime = sv._AdvanceRuntimeState()
                runtime.remember({"players": [{"id": "p"}]}, save)
                if key == "contract_overrides":
                    save[key]["p"]["seasons"][0]["salary"] = 101
                else:
                    save[key] = {"changed": True}
                self.assertIsNone(runtime.take(save))
        save = self.fixture()
        runtime = sv._AdvanceRuntimeState()
        runtime.remember({"players": [{"id": "p"}]}, save)
        save["state"]["current_date"] = "2026-11-29"
        save.update(health_states=[{"player_id": "p", "rust": 8}],
                    team_records={"team": {"wins": 3}}, rotation_baselines={"p": 31},
                    staff_slots=[{"id": "coach"}], team_plans={"team": {"core_ids": ["p"]}})
        self.assertIsNotNone(runtime.take(save))
        self.assertIsNone(runtime.take(save))

    def test_copy_precedes_ai_mutations_and_discards_derived_caches(self):
        save = self.fixture()
        active = {"players": [{"id": "p", "team_id": "team"}],
                  "_allow_internal_caches": True, "_ratings_model": {"mode": "inputs_v1"},
                  "_transaction_pick_context_signature": "stale", "_sim_feature_cache": {"stale": True}}
        runtime = sv._AdvanceRuntimeState()
        runtime.remember(active, save)
        active["players"][0]["team_id"] = "mutated"
        active["_ratings_model"]["mode"] = "mutated"
        reused = runtime.take(save)
        self.assertEqual(reused["players"][0]["team_id"], "team")
        self.assertEqual(reused["_ratings_model"]["mode"], "inputs_v1")
        self.assertNotIn("_sim_feature_cache", reused)
        self.assertNotIn("_transaction_pick_context_signature", reused)
        self.assertNotIn("_advance_runtime_state", save)

    def test_phase_season_and_protection_date_boundaries_invalidate(self):
        for phase in ("free_agency", "playoffs", "training_camp"):
            save = self.fixture()
            save["state"]["phase"] = phase
            runtime = sv._AdvanceRuntimeState()
            runtime.remember({}, save)
            self.assertIsNone(runtime.take(save))
        for change in ("phase", "season", "protection_date"):
            with self.subTest(change=change):
                save = self.fixture()
                save["contract_protection"] = {"evidence_as_of": "2026-11-29"}
                runtime = sv._AdvanceRuntimeState()
                runtime.remember({}, save)
                if change == "phase":
                    save["state"]["phase"] = "playoffs"
                elif change == "season":
                    save["meta"]["season"] = "2027-28"
                else:
                    save["state"]["current_date"] = "2026-11-29"
                self.assertIsNone(runtime.take(save))
        save = self.fixture()
        save["contract_protection"] = {"evidence_as_of": "2026-11-29"}
        runtime = sv._AdvanceRuntimeState()
        runtime.remember({}, save)
        self.assertIsNone(runtime.take(save, "2026-11-29"))

    def test_call_context_restores_on_nested_call_and_exception(self):
        outer, inner = sv._AdvanceRuntimeState(), sv._AdvanceRuntimeState()
        seen = []
        def day(*args):
            seen.append(sv._ADVANCE_RUNTIME_STATE.get())
            if len(seen) == 1:
                with patch.object(sv, "advance_save_day", side_effect=ValueError("stop")):
                    with self.assertRaisesRegex(ValueError, "stop"):
                        inner.advance_day()
                self.assertIs(sv._ADVANCE_RUNTIME_STATE.get(), outer)
            return {}
        with patch.object(sv, "advance_save_day", side_effect=day):
            outer.advance_day()
        self.assertEqual(seen, [outer])
        self.assertIsNone(sv._ADVANCE_RUNTIME_STATE.get())


class AdvanceRuntimeParityTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.root = Path(__file__).resolve().parents[1]
        cls.canonical = sv.to_plain(load_or_build(cls.root, cls.root / DEFAULT_OUT))

    def test_reuse_matches_daily_fresh_builds_across_month_with_both_models(self):
        for model in ("legacy_traits", "inputs_v1"):
            with self.subTest(model=model), tempfile.TemporaryDirectory() as folder:
                path = Path(folder) / "career.json"
                sv.create_league_save(self.root, self.canonical, "BOS", path, seed=55, ratings_model=model)
                initial = sv.load_save(path)
                sv.set_save_date_phase(initial, "2026-11-29")
                initial.setdefault("lifecycle_state", {})["through_date"] = "2026-11-29"
                fresh, reused = deepcopy(initial), deepcopy(initial)
                dates = ["2026-11-30", "2026-12-01", "2026-12-02"]
                current = "2026-11-29"
                with patch.object(sv, "canonical_with_save", wraps=sv.canonical_with_save) as build:
                    for target in dates:
                        sv.advance_save_day(self.root, self.canonical, path, fresh, current, target, 55)
                        current = target
                    fresh_builds = build.call_count
                with patch.object(sv, "canonical_with_save", wraps=sv.canonical_with_save) as build:
                    sv.advance_save(self.root, self.canonical, path, to_date=dates[-1],
                                    prepared_save=reused, persist=False)
                    reused_builds = build.call_count
                self.assertEqual(fresh, reused)
                self.assertLess(reused_builds, fresh_builds)
                self.assertIsNone(sv._ADVANCE_RUNTIME_STATE.get())
                # Every rating dependency can change within an advance.
                # Cached answers must still equal a fresh formula evaluation.
                active = sv.canonical_with_save(self.canonical, initial)
                player = next(p for p in active["players"] if p.get("team_id") == "team_bos")
                pid = player["id"]
                runtime = sv._AdvanceRuntimeState()
                token = sv._ADVANCE_RUNTIME_STATE.set(runtime)
                try:
                    def check():
                        expected = sv._uncached_player_attribute_summary(active, pid)
                        actual = sv.player_attribute_summary(active, pid)
                        self.assertEqual(actual, expected)
                        actual["overall"] = -1  # Returned dicts cannot corrupt the memo.
                        self.assertEqual(sv.player_attribute_summary(active, pid), expected)
                    check()
                    for field, value in (("minutes_projection", 17), ("position", "C"),
                                         ("height_inches", 84), ("weight_lbs", 265)):
                        player[field] = value
                        check()
                    for field in ("talent_model_version", "offense_model_version"):
                        original = active["meta"].get(field)
                        active["meta"][field] = None
                        check()
                        active["meta"][field] = original
                    sv.apply_development_events(active, [{"player_id": pid,
                                                           "trait_deltas": {"passing_reads": 1.25}}])
                    check()
                    prior = active["meta"].get("offensive_profiles", {}).get(pid)
                    if prior and "three_per36" in prior:
                        prior["three_per36"] += 1
                        check()
                finally:
                    sv._ADVANCE_RUNTIME_STATE.reset(token)
                with patch.object(sv, "canonical_with_save", wraps=sv.canonical_with_save) as build:
                    sv.advance_save(self.root, self.canonical, path, to_date="2026-12-03",
                                    prepared_save=reused, persist=False)
                    self.assertGreaterEqual(build.call_count, 1)


if __name__ == "__main__":
    unittest.main()
