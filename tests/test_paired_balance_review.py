from copy import deepcopy
import unittest

from scripts.review_paired_balance import compare


class PairedBalanceReviewTests(unittest.TestCase):
    def career(self, stars=17, generated=4, mean=79, floor=72):
        return {"annual":[
            {"date":"2026-10-01","fixed24_display_at_least":{"90":24},
             "generated_90_plus":0,"fixed24_display":{"mean":76,"p10":66}},
            {"date":"2034-10-01","fixed24_display_at_least":{"90":stars},
             "generated_90_plus":generated,"fixed24_display":{"mean":mean,"p10":floor}}],
            "floor_accounting_same_october_dates":{"departure_composition_component":2,"mean_change":2.5}}

    def test_generated_stars_are_not_confused_with_total_star_count(self):
        result = compare(self.career(),self.career(stars=18,generated=5))
        self.assertEqual(result["control_90_plus"],17)
        self.assertEqual(result["tuned_generated_90_plus"],5)
        self.assertEqual(result["starting_90_plus"],24)

    def test_equal_end_floor_is_not_reported_as_no_floor_rise(self):
        result = compare(self.career(),self.career(mean=79.2))
        self.assertEqual(result["tuned_minus_control_p10"],0)
        self.assertEqual(result["tuned_floor_p10_gain"],6)
        self.assertEqual(result["tuned_minus_control_mean"],.2)

    def test_different_initial_populations_are_rejected(self):
        control = self.career()
        tuned = deepcopy(control)
        tuned["annual"][0]["fixed24_display"]["p10"] += 1
        with self.assertRaises(AssertionError):
            compare(control,tuned)

    def test_mean_decomposition_is_labeled_as_a_share_not_percentage_points(self):
        result = compare(self.career(),self.career())
        self.assertEqual(result["control_departure_share_of_mean_rise"],.8)


if __name__ == "__main__":
    unittest.main()
