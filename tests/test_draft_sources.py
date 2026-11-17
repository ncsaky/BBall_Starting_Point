import unittest
from collections import Counter

from nba_gm_data.draft import GENERATED_SOURCE_TEAMS, generate_draft_class_records
from nba_gm_data.schema import to_plain


class GeneratedProspectSourceTests(unittest.TestCase):
    def test_generated_class_keeps_origin_groups_small(self):
        self.assertGreaterEqual(len(GENERATED_SOURCE_TEAMS), 60)
        prospects = to_plain(generate_draft_class_records("2028", seed=7))["draft_prospects"]
        sources = [prospect["source_team"] for prospect in prospects]
        self.assertEqual(len(sources), 60)
        self.assertGreaterEqual(len(set(sources)), 30)
        self.assertLessEqual(max(Counter(sources).values()), 2)


if __name__ == "__main__":
    unittest.main()
