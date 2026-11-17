import unittest

from nba_gm_data.app_actions import block_contract_terms


class BlockContractTermsTests(unittest.TestCase):
    def test_annual_changes_are_one_remaining_contract(self):
        rows = [{"season": season, "salary": salary} for season, salary in
                [("2026-27", 32_400_000), ("2027-28", 29_600_000),
                 ("2028-29", 26_800_000), ("2029-30", 26_700_000)]]
        self.assertEqual(block_contract_terms({"seasons": rows}, "2028-29"),
                         [{"salary": 26_800_000, "years": 2, "start_season": "2028-29"}])

    def test_actual_extension_stays_separate_even_at_same_salary(self):
        rows = [{"season": "2029-30", "salary": 12_000_000},
                {"season": "2030-31", "salary": 12_000_000, "guarantee_status": "extension"},
                {"season": "2031-32", "salary": 12_000_000, "guarantee_status": "extension"}]
        terms = block_contract_terms({"seasons": rows, "signed_season": "2030-31"}, "2029-30")
        self.assertEqual([term["years"] for term in terms], [1, 2])


if __name__ == "__main__":
    unittest.main()
