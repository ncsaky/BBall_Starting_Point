"""Future classes have a sparse upper tail, not uniformly promoted rookies."""
from dataclasses import replace
import random
import unittest
from unittest.mock import patch

from nba_gm_data import draft
from nba_gm_data.schema import to_plain


def legacy_traits(prospect, rng):
    base = {key: draft.clamp(prospect.current_ability + rng.gauss(0, 8), 25, 94) for key in draft.DRAFT_TRAITS}
    inferred = draft.infer_trait_values(prospect.position, prospect.archetype, {}, prospect.height_inches)
    return {key: round((base[key] + inferred[key]) / 2, 2) for key in draft.DRAFT_TRAITS}


class GeneratedUpsideTests(unittest.TestCase):
    # 689933a makes public ranks depend on upside/medicals; isolate the underlying generator here.
    @patch("nba_gm_data.draft.apply_public_ranks", new=lambda prospects: prospects)
    def test_tail_preserves_identity_readiness_medicals_and_ordinary_traits(self):
        for seed in (17, 29, 47, 83):
            actual = to_plain(draft.generate_draft_class_records("2032", seed))
            with patch.object(draft, "generated_prospect_upside", side_effect=lambda value, *args: value), \
                 patch.object(draft, "generated_trait_values", side_effect=legacy_traits):
                original = to_plain(draft.generate_draft_class_records("2032", seed))
            self.assertEqual(actual["draft_classes"], original["draft_classes"])
            original_traits = {(t["prospect_id"], t["trait_key"]): t for t in original["draft_prospect_traits"]}
            unchanged = set()
            for player, old in zip(actual["draft_prospects"], original["draft_prospects"], strict=True):
                self.assertEqual({k: v for k, v in player.items() if k not in {"potential", "ceiling", "rookie_contract_value"}},
                                 {k: v for k, v in old.items() if k not in {"potential", "ceiling", "rookie_contract_value"}})
                self.assertGreaterEqual(player["potential"], old["potential"])
                self.assertLessEqual(player["potential"], 97)
                self.assertGreaterEqual(player["ceiling"], player["potential"])
                self.assertLessEqual(player["ceiling"], 99)
                if player["potential"] <= 80:
                    unchanged.add(player["id"])
                    self.assertEqual(player, old)
            self.assertGreater(len(unchanged), 45)
            for trait in actual["draft_prospect_traits"]:
                if trait["prospect_id"] in unchanged:
                    self.assertEqual(trait, original_traits[(trait["prospect_id"], trait["trait_key"])])
                self.assertGreaterEqual(trait["value"], 25)
                self.assertLessEqual(trait["value"], 95)

    def test_class_quality_changes_frequency_without_requiring_exceptional_players(self):
        weak, strong, late = 0, 0, 0
        strong_counts = []
        for seed in range(100):
            count = 0
            for rank in range(1, 61):
                weak += draft.generated_prospect_upside(70, rank, 53, "2030", seed) > 70
                exceptional = draft.generated_prospect_upside(70, rank, 74, "2030", seed) > 70
                strong += exceptional
                count += exceptional
                late += exceptional and rank > 30
            strong_counts.append(count)
        self.assertGreater(strong, weak)
        self.assertLess(strong, 600)
        self.assertGreater(late, 0)
        self.assertIn(0, strong_counts)
        self.assertGreater(max(strong_counts), 4)

    def test_repeating_generation_and_unrelated_random_calls_do_not_reroll_it(self):
        first = to_plain(draft.generate_draft_class_records("2035", 913))
        for _ in range(100):
            random.random()
        self.assertEqual(first, to_plain(draft.generate_draft_class_records("2035", 913)))

    def test_upside_tools_preserve_profile_shape(self):
        prospect = draft.generate_draft_class_records("2032", 17)["draft_prospects"][0]
        ordinary = replace(prospect, potential=70)
        exceptional = replace(prospect, potential=92)
        before = draft.generated_trait_values(ordinary, random.Random(19))
        after = draft.generated_trait_values(exceptional, random.Random(19))
        for key in draft.DRAFT_TRAITS:
            self.assertAlmostEqual(after[key] - before[key], 4.0, places=2)
        self.assertEqual(sorted(before, key=before.get), sorted(after, key=after.get))


if __name__ == "__main__":
    unittest.main()
