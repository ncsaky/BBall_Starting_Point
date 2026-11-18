"""Generated draft classes look and develop like real ones (docs/agents/tasks/prospect-realism.md).

Fast checks run on generated classes only. The development check drives four seasons of monthly development in the
new ratings for a few classes (about a minute). The full 15-class evidence check is opt-in:
PROSPECT_REALISM_FULL=1.
"""
import json
import os
import statistics as st
import sys
import unittest
from collections import Counter
from pathlib import Path

from nba_gm_data import draft
from nba_gm_data.schema import to_plain

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts" / "research"))
UNIVERSE = ROOT / "data/canonical/universe_2026_27_offseason.json"
INPUTS = ROOT / "data/canonical/player_inputs_2026_27.json"
HAVE_LEAGUE = UNIVERSE.exists() and (INPUTS.exists() or INPUTS.with_name(INPUTS.name + ".gz").exists())


def pick_range(rank):
    return "1-3" if rank <= 3 else "4-10" if rank <= 10 else "11-20" if rank <= 20 else "21-30" if rank <= 30 else "31-60"


def classes(years=range(2027, 2037), seeds=(1, 2)):
    for year in years:
        for seed in seeds:
            yield year, seed, to_plain(draft.generate_draft_class_records(str(year), seed, talent_model=True))


class GeneratedClassShapeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.records = list(classes())
        cls.prospects = [p for _, _, r in cls.records for p in r["draft_prospects"]]

    def test_same_seed_same_class_and_seeds_differ(self):
        a = to_plain(draft.generate_draft_class_records("2029", 7, talent_model=True))
        b = to_plain(draft.generate_draft_class_records("2029", 7, talent_model=True))
        c = to_plain(draft.generate_draft_class_records("2029", 8, talent_model=True))
        self.assertEqual(json.dumps(a, sort_keys=True), json.dumps(b, sort_keys=True))
        self.assertNotEqual([p["name"] for p in a["draft_prospects"]], [p["name"] for p in c["draft_prospects"]])

    def test_ages_by_pick_follow_real_draftees(self):
        # Real rookie-season ages, 2015-2022 classes: 19 for picks 1-3, 20 for 4-20, 21 for 21-30, 22 later.
        ages = {}
        for p in self.prospects:
            ages.setdefault(pick_range(p["rank"]), []).append(p["age"])
        self.assertLessEqual(st.median(ages["1-3"]), 19.5)
        self.assertGreaterEqual(st.median(ages["31-60"]), 21.5)
        self.assertLess(st.mean(ages["1-3"]), st.mean(ages["11-20"]))
        self.assertLess(st.mean(ages["11-20"]), st.mean(ages["31-60"]))
        self.assertTrue(all(18 <= a <= 25 for a in ages["1-3"] + ages["31-60"]))

    def test_position_mix_matches_real_draftees(self):
        # Real draftees 2022-26 still in the league: PG 18%, SG 22%, SF 26%, PF 18%, C 16%.
        mix = Counter(draft.primary_position_label(p["position"]) for p in self.prospects)
        n = sum(mix.values())
        bands = {"PG": (0.12, 0.26), "SG": (0.15, 0.29), "SF": (0.17, 0.33), "PF": (0.12, 0.26), "C": (0.11, 0.23)}
        for pos, (low, high) in bands.items():
            self.assertTrue(low <= mix[pos] / n <= high, (pos, mix[pos] / n))

    def test_level_and_upside_fall_with_pick_but_overlap(self):
        by = {}
        for p in self.prospects:
            by.setdefault(pick_range(p["rank"]), []).append(p)
        order = ["1-3", "4-10", "11-20", "21-30", "31-60"]
        current = [st.median(p["current_ability"] for p in by[k]) for k in order]
        public = [st.median((p.get("scouting_prior") or {}).get("potential", p["potential"]) for p in by[k]) for k in order]
        self.assertEqual(current, sorted(current, reverse=True))
        self.assertEqual(public, sorted(public, reverse=True))
        # Real 2026 class as the game rates it: picks 1-3 current ~58 / potential ~88, second round ~46 / ~50.
        self.assertTrue(55 <= current[0] <= 63, current)
        self.assertTrue(42 <= current[-1] <= 49, current)
        self.assertTrue(84 <= public[0] <= 93, public)
        self.assertTrue(45 <= public[-1] <= 56, public)
        # Scouting misses both ways: some second-rounders have more true upside than some lottery picks.
        best_late = max(p["potential"] for p in by["31-60"])
        worst_lottery = min(p["potential"] for p in by["1-3"] + by["4-10"])
        self.assertGreater(best_late, worst_lottery)

    def test_true_upside_differs_from_the_public_board(self):
        misses = [p["potential"] - p["scouting_prior"]["potential"] for p in self.prospects if p.get("scouting_prior")]
        self.assertGreater(len(misses), 0.9 * len(self.prospects))
        self.assertTrue(abs(st.mean(misses)) < 2.5, st.mean(misses))
        self.assertTrue(3.5 < st.pstdev(misses) < 10, st.pstdev(misses))

    def test_strong_and_weak_drafts(self):
        lottery = [st.mean(p["potential"] + p["current_ability"] for p in r["draft_prospects"] if p["rank"] <= 14)
                   for _, _, r in self.records]
        self.assertGreater(max(lottery) - min(lottery), 6.0)


@unittest.skipUnless(HAVE_LEAGUE, "canonical league or player inputs not available")
class GeneratedDevelopmentTests(unittest.TestCase):
    """Four seasons of monthly development in the new ratings, compared with real classes by pick range."""

    @classmethod
    def setUpClass(cls):
        import prospect_realism as pr
        cls.pr = pr
        full = os.environ.get("PROSPECT_REALISM_FULL") == "1"
        years = [2027, 2028, 2029, 2030, 2031] if full else [2028, 2030]
        seeds = [1, 2, 3] if full else [1, 2]
        thresholds = pr.league_thresholds(pr.load_league("inputs"))
        league, rows = pr.build_generated("inputs", years, seeds)
        for row in rows:
            row["entry_rank"] = pr.rank_in_league(thresholds["overall_sorted"], pr.card(league, row["id"])["overall"])
        histories = {}
        for seed in seeds:
            histories.update(pr.develop(league, [r for r in rows if r["seed"] == seed], thresholds, 4, seed)["history"])
        for row in rows:
            row["final_rank"] = pr.rank_in_league(thresholds["overall_sorted"], histories[row["id"]][4]["overall"])
            row["history"] = histories[row["id"]]
        cls.rows = rows
        cls.full = full

    def share(self, picks, test):
        group = [r for r in self.rows if r["range"] in picks]
        return sum(1 for r in group if test(r)) / len(group)

    def test_year4_tiers_follow_pick_order(self):
        starter = lambda r: r["final_rank"] <= 150
        out = lambda r: r["final_rank"] > 450
        self.assertGreater(self.share({"1-3", "4-10"}, starter), self.share({"11-20", "21-30"}, starter))
        self.assertGreater(self.share({"11-20", "21-30"}, starter), self.share({"31-60"}, starter))
        self.assertLess(self.share({"1-3", "4-10"}, out), self.share({"31-60"}, out))

    def test_year4_tiers_within_real_evidence_bands(self):
        # Evidence: real 2019-2023 top-10 picks in the game's ratings (3-7 seasons in), Basketball Index year-4
        # roles for 2015-2021 classes. Bands are wide for the small fast sample; the full run is tighter.
        wide = 0.0 if self.full else 0.08
        star = lambda r: r["final_rank"] <= 25
        starter = lambda r: r["final_rank"] <= 150
        out = lambda r: r["final_rank"] > 450
        checks = [
            ({"1-3", "4-10"}, starter, 0.30, 0.70),
            ({"11-20", "21-30"}, starter, 0.10, 0.40),
            ({"31-60"}, starter, 0.0, 0.08),
            ({"1-3", "4-10"}, out, 0.0, 0.25),
            ({"11-20", "21-30"}, out, 0.25, 0.55),
            ({"31-60"}, out, 0.55, 0.85),
            ({"1-3", "4-10"}, star, 0.01, 0.20),
            ({"21-30", "31-60"}, star, 0.0, 0.02),
        ]
        for picks, test, low, high in checks:
            value = self.share(picks, test)
            self.assertTrue(low - wide <= value <= high + wide, (sorted(picks), round(value, 3), low, high))

    def test_some_prospects_regress_and_some_break_out(self):
        changes = [r["entry_rank"] - r["final_rank"] for r in self.rows if r["final_rank"] <= 450]
        self.assertTrue(any(c < -60 for c in changes))   # clear regressions happen
        self.assertTrue(any(c > 250 for c in changes))   # and big jumps

    def test_development_is_deterministic(self):
        pr = self.pr
        thresholds = pr.league_thresholds(pr.load_league("inputs"))
        league, rows = pr.build_generated("inputs", [2029], [5])
        subset = rows[:12]
        a = pr.develop(league, subset, thresholds, 2, 5)["history"]
        b = pr.develop(league, subset, thresholds, 2, 5)["history"]
        self.assertEqual(a, b)


if __name__ == "__main__":
    unittest.main()
