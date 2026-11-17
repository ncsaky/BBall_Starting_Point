"""Rare latent upside is not a current-rating boost or a guaranteed outcome."""
from copy import deepcopy
import json
import math
import random
import unittest
from unittest.mock import patch

from nba_gm_data import draft, health
from nba_gm_data.schema import to_plain
from tests.test_talent_balance import converted


def previous_upside(potential, rank, top_strength, year, seed, talent_model=False):
    quality = draft.clamp((top_strength - 53) / 21, 0, 1)
    probability = .004 + (.12 + .30 * quality) * math.exp(-(rank - 1) / 9)
    rng = random.Random(f"{year}:{seed}:{rank}:ceiling_tail")
    if rng.random() < probability:
        potential = max(potential, 85 + quality * 4 + rng.uniform(-3, 4))
    return draft.clamp(potential, 0, 97)


class HiddenUpsideTests(unittest.TestCase):
    def test_legacy_upside_is_exact_and_new_tail_remains_sparse_class_sensitive(self):
        totals = {key: 0 for key in ("weak", "strong", "old", "late")}
        late_counts = []
        for seed in range(100):
            count = 0
            for rank in range(1, 61):
                old = previous_upside(70, rank, 74, "2040", seed)
                self.assertEqual(old, draft.generated_prospect_upside(70, rank, 74, "2040", seed))
                weak = draft.generated_prospect_upside(70, rank, 53, "2040", seed, True)
                strong = draft.generated_prospect_upside(70, rank, 74, "2040", seed, True)
                self.assertGreaterEqual(strong, old)
                self.assertLessEqual(strong, 97)
                totals["weak"] += weak > 70
                totals["strong"] += strong > 70
                totals["old"] += old > 70
                totals["late"] += strong > 70 and rank > 30
                count += strong > 70 and rank > 30
            late_counts.append(count)
        self.assertGreater(totals["strong"], totals["weak"])
        self.assertGreater(totals["strong"], totals["old"])
        self.assertGreater(totals["late"], 20)
        self.assertLess(totals["late"], 120)
        self.assertLess(totals["strong"], 650)
        self.assertIn(0, late_counts)

    def test_future_generation_preserves_every_current_trait_and_unaffected_capacity(self):
        affected = 0
        for seed in range(100, 120):
            after, context = converted(seed, "2038")
            with patch.object(draft, "generated_prospect_upside", previous_upside):
                before, original = converted(seed, "2038")
            self.assertEqual(after["draft_classes"], before["draft_classes"])
            self.assertEqual(after["draft_prospect_traits"], before["draft_prospect_traits"])
            unchanged = set()
            for left, right in zip(before["draft_prospects"], after["draft_prospects"], strict=True):
                allowed = {"potential", "ceiling", "rookie_contract_value", "scouting_prior"}
                self.assertEqual({k:v for k,v in left.items() if k not in allowed},
                                 {k:v for k,v in right.items() if k not in allowed})
                if left["potential"] == right["potential"]:
                    unchanged.add(left["id"])
                else:
                    affected += 1
                    self.assertGreaterEqual(right["potential"], 80)
            ids = {p["id"] for p, prospect in zip(context["players"], after["draft_prospects"], strict=True)
                   if prospect["id"] in unchanged}
            for left, right in zip(original["traits"], context["traits"], strict=True):
                self.assertEqual(left["value"], right["value"])
                self.assertEqual(left["components"]["career_capacity"]["aptitude"],
                                 right["components"]["career_capacity"]["aptitude"])
                if right["player_id"] in ids:
                    self.assertEqual(left, right)
            self.assertEqual(original["traits"], json.loads(json.dumps(original))["traits"])
        self.assertGreater(affected, 0)

    def test_bust_realizations_and_saved_profiles_are_not_rerolled(self):
        _, context = converted(107, "2038")
        original = deepcopy(context)
        before = [health.prospect_development_realization(p, 107) for p in context["players"]]
        for p in context["players"]:
            p["team_id"] = "other_team"
            p["draft_pick"] = 1
        reloaded = json.loads(json.dumps(context))
        self.assertEqual(before, [health.prospect_development_realization(p, 107) for p in reloaded["players"]])
        self.assertTrue(any(value <= .8 for value in before))
        self.assertEqual(original["traits"], reloaded["traits"])
        # Generating unrelated future classes cannot rewrite saved entries.
        draft.generate_draft_class_records("2041", 107, talent_model=True)
        self.assertEqual(original["traits"], reloaded["traits"])

    def test_saved_old_class_signing_uses_saved_potential_not_new_generator(self):
        with patch.object(draft, "generated_prospect_upside", previous_upside):
            old = to_plain(draft.generate_draft_class_records("2038", 100, talent_model=True))
        new = to_plain(draft.generate_draft_class_records("2038", 100, talent_model=True))
        prospect = next(a for a,b in zip(old["draft_prospects"],new["draft_prospects"],strict=True)
                        if a["potential"] != b["potential"])
        selection = {"id":"saved-selection","pick_id":"saved-pick","overall_pick":39,
                     "team_id":"team_test","prospect_id":prospect["id"],"draft_year":"2038"}
        saved = {"version":"league_save_v1","draft_state":{"draft":old},
                 "pending_draft_selections":[{"id":selection["id"],"selection":selection,
                    "prospect":prospect,"team":{"id":"team_test","abbrev":"TST"}}],
                 "state":{"current_date":"2038-06-25"}}
        saved = json.loads(json.dumps(saved))
        with patch.object(draft,"generate_draft_class_records",side_effect=AssertionError("Saved class rerolled")):
            result = draft.apply_draft_selection_to_save_state(saved,selection["id"],date="2038-06-25",sign_rookie=True)
        self.assertEqual(result["status"],"applied")
        self.assertEqual(saved["generated_players"][0]["potential"],prospect["potential"])
        self.assertTrue(all(t["components"]["career_capacity"]["potential"] == prospect["potential"]
                            for t in saved["generated_traits"]))
        self.assertEqual(saved["draft_state"]["draft"]["draft_prospects"],old["draft_prospects"])

    def test_new_hidden_tail_is_not_leaked_through_draft_evaluations(self):
        for seed in range(100,120):
            with patch.object(draft,"generated_prospect_upside",previous_upside):
                before = to_plain(draft.generate_draft_class_records("2038",seed,talent_model=True))
            after = to_plain(draft.generate_draft_class_records("2038",seed,talent_model=True))
            canonical = {"players":[],"team_strategic_states":[{"team_id":"t","phase":"developing","salary_posture":"below_cap"}]}
            for left,right in zip(before["draft_prospects"],after["draft_prospects"],strict=True):
                with self.subTest(seed=seed,rank=right["rank"]):
                    self.assertEqual(draft.generated_bpa_grade(left),draft.generated_bpa_grade(right))
                    self.assertEqual(draft.prospect_cap_value(canonical,"t",left),draft.prospect_cap_value(canonical,"t",right))
                    with patch.object(draft,"prospect_spatial_fit_delta",return_value=0):
                        self.assertEqual(draft.prospect_team_fit(canonical,"t",left),draft.prospect_team_fit(canonical,"t",right))
                    self.assertEqual(right["scouting_prior"],json.loads(json.dumps(right))["scouting_prior"])
            self.assertEqual(draft.generated_board_report({**canonical,"teams":[{"id":"t","abbrev":"TST"}]},"TST","2038",seed,0,None)["entry_count"],60)

    def test_scouting_reports_retain_estimates_not_new_latent_truth(self):
        with patch.object(draft,"generated_prospect_upside",previous_upside):
            before = draft.generate_draft_class_records("2038",100,talent_model=True)
        after = draft.generate_draft_class_records("2038",100,talent_model=True)
        canonical = {"teams":[{"id":"t","abbrev":"TST"}]}
        config = draft.default_draft_model_config()
        old = draft.build_scouting_reports(canonical,before["draft_prospects"],before["draft_prospect_traits"],config)
        new = draft.build_scouting_reports(canonical,after["draft_prospects"],after["draft_prospect_traits"],config)
        self.assertEqual(to_plain(old),to_plain(new))
        self.assertTrue(any(p.potential > (p.scouting_prior or {}).get("potential",p.potential)
                            for p in after["draft_prospects"]))


if __name__ == "__main__":
    unittest.main()
