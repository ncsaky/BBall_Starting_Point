"""Real college players in the first future drafts (docs/agents/tasks/real-prospects.md).

Bundle: data/canonical/real_prospects.json (derived; rebuilt by scripts/research/real_prospects.py).
"""
import json
import math
import statistics as st
import sys
import unittest
from collections import Counter
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from nba_gm_data import draft
from nba_gm_data import real_prospects as rp
from nba_gm_data.schema import to_plain

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts" / "research"))
UNIVERSE = ROOT / "data/canonical/universe_2026_27_offseason.json"
INPUTS = ROOT / "data/canonical/player_inputs_2026_27.json"
HAVE_LEAGUE = UNIVERSE.exists() and (INPUTS.exists() or INPUTS.with_name(INPUTS.name + ".gz").exists())
RAW = ROOT / "data/research/barttorvik/raw/players_2026.csv"


def pick_range(rank):
    return "1-3" if rank <= 3 else "4-10" if rank <= 10 else "11-20" if rank <= 20 else "21-30" if rank <= 30 else "31-60"


def real_class(year, seed=1, talent_model=True):
    return to_plain(draft.generate_draft_class_records(str(year), seed, talent_model=talent_model, real_prospects=True))


def generated_class(year, seed=1, talent_model=True):
    return to_plain(draft.generate_draft_class_records(str(year), seed, talent_model=talent_model))


class BundleTests(unittest.TestCase):
    def test_bundle_lists_three_classes_with_one_class_per_player(self):
        bundle = rp.bundle()
        self.assertEqual(rp.draft_years(), {"2027", "2028", "2029"})
        ids = [p["id"] for p in bundle["prospects"]]
        self.assertEqual(len(ids), len(set(ids)), "a real player belongs to at most one class")
        for year in rp.draft_years():
            rows = rp.prospects_for_year(year)
            self.assertTrue(rows, year)
            picks = [p["projected_pick"] for p in rows]
            self.assertEqual(len(picks), len(set(picks)), year)
            self.assertTrue(all(1 <= pick <= 60 for pick in picks), year)
        self.assertGreaterEqual(len(rp.prospects_for_year("2027")), 35)
        required = {"name", "draft_year", "projected_pick", "college_team", "conference", "class_year_now", "age_at_draft",
                    "height_inches", "role", "projected_profile", "skill_scores", "input_parts", "seasons"}
        for prospect in bundle["prospects"]:
            self.assertFalse(required - set(prospect), prospect["name"])
            self.assertEqual(set(prospect["skill_scores"]), set(draft.DRAFT_TRAITS))

    def test_bundle_records_out_of_sample_check_and_evidence_fits(self):
        bundle = rp.bundle()
        same_year = bundle["projection"]["out_of_sample"]["0"]["direct"]
        self.assertGreater(same_year["auc"], 0.95)
        self.assertGreater(same_year["spearman_rank_vs_pick"], 0.4)
        fits = bundle["input_mapping"]["targets"]
        # College -> NBA direction: every fitted college part predicts its input positively.
        for iid in ("S07", "S01", "S37", "S29", "S42", "F01.recognition", "S16"):
            self.assertGreater(fits[iid]["r_college"], 0.25, iid)
        self.assertLess(fits["S17"]["coef"][0], 0, "college turnovers lower ball security")
        self.assertGreater(fits["S37"]["coef"][0], 0, "college blocks raise contests")

    def test_soft_bounds_rescale_without_clipping(self):
        values = [rp.soft_bounded(x) for x in (-50, 0, 20, 50, 80, 100, 150)]
        self.assertEqual(values, sorted(values))
        self.assertTrue(all(5 < v < 95 for v in values))
        self.assertNotEqual(rp.soft_bounded(100), rp.soft_bounded(150))
        self.assertAlmostEqual(rp.soft_bounded(50), 50.0)


class ClassAssemblyTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.classes = {year: real_class(year) for year in (2027, 2028, 2029)}

    def test_real_players_sit_at_projected_picks_and_other_slots_keep_generated_prospects(self):
        for year, records in self.classes.items():
            prospects = records["draft_prospects"]
            self.assertEqual(len(prospects), 60)
            self.assertEqual(sorted(p["rank"] for p in prospects), list(range(1, 61)))
            real = [p for p in prospects if p["league"] == "NCAA"]
            names = {e["name"] for e in rp.prospects_for_year(year)}
            self.assertEqual({p["name"] for p in real}, names)
            generated = generated_class(year)["draft_prospects"]
            kept = {p["id"]: p for p in prospects if p["league"] == "generated"}
            for slot, original in enumerate(generated, start=1):
                if original["id"] in kept:
                    self.assertEqual({k: v for k, v in kept[original["id"]].items() if k not in {"rank", "rank_range", "rookie_contract_value", "scouting_prior"}},
                                     {k: v for k, v in original.items() if k not in {"rank", "rank_range", "rookie_contract_value", "scouting_prior"}})
            self.assertEqual(len(kept) + len(real), 60)
            self.assertEqual(records["draft_classes"][0]["class_type"], "real_college_plus_generated")
            traits = Counter(t["prospect_id"] for t in records["draft_prospect_traits"])
            self.assertTrue(all(traits[p["id"]] == len(draft.DRAFT_TRAITS) for p in prospects))
            self.assertTrue(all(0 <= t["value"] <= 100 for t in records["draft_prospect_traits"]))

    def test_same_seed_same_class_and_real_board_is_shared_across_saves(self):
        a = real_class(2027, 7)
        b = real_class(2027, 7)
        c = real_class(2027, 8)
        self.assertEqual(json.dumps(a, sort_keys=True), json.dumps(b, sort_keys=True))
        real_a = {p["name"]: p for p in a["draft_prospects"] if p["league"] == "NCAA"}
        real_c = {p["name"]: p for p in c["draft_prospects"] if p["league"] == "NCAA"}
        self.assertEqual(set(real_a), set(real_c))
        # What scouts see is the same in every save; the hidden upside differs by save seed.
        name = next(iter(real_a))
        self.assertEqual(real_a[name]["current_ability"], real_c[name]["current_ability"])
        gen_a = [p["name"] for p in a["draft_prospects"] if p["league"] == "generated"]
        gen_c = [p["name"] for p in c["draft_prospects"] if p["league"] == "generated"]
        self.assertNotEqual(gen_a, gen_c)

    def test_classes_after_2029_are_unchanged(self):
        for year, seed in ((2030, 1), (2031, 7), (2036, 2)):
            for talent_model in (True, False):
                self.assertEqual(json.dumps(generated_class(year, seed, talent_model), sort_keys=True),
                                 json.dumps(real_class(year, seed, talent_model), sort_keys=True), (year, seed))

    def test_disabled_config_keeps_classes_generated(self):
        config = draft.default_draft_model_config()
        config["real_prospects"] = {"enabled": False}
        self.assertFalse(rp.enabled(config))
        self.assertTrue(rp.enabled(draft.default_draft_model_config()))
        self.assertTrue(rp.enabled({}))

    def test_mixed_classes_keep_prospect_realism_shape(self):
        # The classes a new save drafts from: real-plus-generated 2027-2029, generated later (two save seeds).
        records = [real_class(y, s) for y in (2027, 2028, 2029) for s in (1, 2)]
        records += [generated_class(y, s) for y in range(2030, 2037) for s in (1, 2)]
        prospects = [p for r in records for p in r["draft_prospects"]]
        ages = {}
        for p in prospects:
            ages.setdefault(pick_range(p["rank"]), []).append(p["age"])
        self.assertLessEqual(st.median(ages["1-3"]), 20)
        self.assertGreaterEqual(st.median(ages["31-60"]), 21)
        self.assertLess(st.mean(ages["1-3"]), st.mean(ages["31-60"]))
        mix = Counter(draft.primary_position_label(p["position"]) for p in prospects)
        n = sum(mix.values())
        bands = {"PG": (0.12, 0.26), "SG": (0.15, 0.29), "SF": (0.15, 0.33), "PF": (0.12, 0.28), "C": (0.11, 0.25)}
        for pos, (low, high) in bands.items():
            self.assertTrue(low <= mix[pos] / n <= high, (pos, mix[pos] / n))
        by = {}
        for p in prospects:
            by.setdefault(pick_range(p["rank"]), []).append(p)
        order = ["1-3", "4-10", "11-20", "21-30", "31-60"]
        current = [st.median(p["current_ability"] for p in by[k]) for k in order]
        public = [st.median((p.get("scouting_prior") or {}).get("potential", p["potential"]) for p in by[k]) for k in order]
        self.assertEqual(public, sorted(public, reverse=True))
        self.assertGreater(current[0], current[-1] + 6)
        self.assertTrue(55 <= current[0] <= 63, current)
        self.assertTrue(42 <= current[-1] <= 49, current)
        self.assertTrue(84 <= public[0] <= 93, public)
        self.assertTrue(45 <= public[-1] <= 56, public)
        # Real and generated prospects sit on the same scale at the same picks.
        for key in ("4-10", "11-20", "31-60"):
            real = [p["current_ability"] for r in records[:6] for p in r["draft_prospects"] if p["league"] == "NCAA" and pick_range(p["rank"]) == key]
            gen = [p["current_ability"] for r in records[6:] for p in r["draft_prospects"] if pick_range(p["rank"]) == key]
            if len(real) >= 5:
                self.assertLess(abs(st.median(real) - st.median(gen)), 3.0, key)
        misses = [p["potential"] - p["scouting_prior"]["potential"] for r in records[:6] for p in r["draft_prospects"]
                  if p["league"] == "NCAA" and p.get("scouting_prior")]
        self.assertGreater(len(misses), 40)
        self.assertTrue(3.0 < st.pstdev(misses) < 10, st.pstdev(misses))

    def test_college_profile_shapes_draft_traits(self):
        real = [p for r in self.classes.values() for p in r["draft_prospects"] if p["league"] == "NCAA"]
        traits = {}
        for r in self.classes.values():
            for t in r["draft_prospect_traits"]:
                traits.setdefault(t["prospect_id"], {})[t["trait_key"]] = t["value"]

        def r(stat, trait):
            xs = [p["public_stats"]["college"]["profile"][stat] for p in real]
            ys = [traits[p["id"]][trait] for p in real]
            return st.correlation(xs, ys)

        self.assertGreater(r("ft_pct", "shooting"), 0.4)
        self.assertGreater(r("three_pct", "shooting"), 0.3)
        self.assertGreater(r("blk_pct", "rim_protection"), 0.6)
        self.assertGreater(r("ast_pct", "passing"), 0.6)
        self.assertGreater(r("usg", "shot_creation"), 0.4)
        self.assertGreater(r("stl_pct", "defense"), 0.4)
        self.assertGreater(r("drb_pct", "rebounding"), 0.5)
        guards = [p for p in real if p["position"].startswith("PG")]
        bigs = [p for p in real if p["position"].startswith("C")]
        self.assertGreater(st.mean(traits[p["id"]]["passing"] for p in guards), st.mean(traits[p["id"]]["passing"] for p in bigs))
        self.assertGreater(st.mean(traits[p["id"]]["rim_protection"] for p in bigs), st.mean(traits[p["id"]]["rim_protection"] for p in guards))

    def test_real_prospects_have_college_block_and_no_invented_medical_history(self):
        for p in self.classes[2027]["draft_prospects"]:
            if p["league"] != "NCAA":
                continue
            college = p["public_stats"]["college"]
            self.assertTrue(college["team"])
            self.assertTrue(college["seasons"])
            self.assertEqual(p["source_team"], college["team"])
            self.assertIn(rp.SOURCE_ID, p["source_ids"])
            self.assertFalse(p["medical_profile"]["major_prior_injuries"])
            self.assertIsNone(p["medical_profile"]["current_injury"])


@unittest.skipUnless(HAVE_LEAGUE, "canonical league or player inputs not available")
class EntryInputTests(unittest.TestCase):
    """Drafted real prospects: their college strengths show in the 94 inputs."""

    @classmethod
    def setUpClass(cls):
        from nba_gm_data.input_estimator import _generated_player_inputs, scalar_value
        cls.rows = []
        records = real_class(2027, 3)
        traits = {}
        for t in records["draft_prospect_traits"]:
            traits.setdefault(t["prospect_id"], []).append(t)
        for prospect in records["draft_prospects"]:
            onboarding = {"draft_year": "2027", "name": prospect["name"], "overall_pick": prospect["rank"]}
            player = draft.rookie_player_record(onboarding, prospect, {"id": "team_t", "abbrev": "TST"}, SimpleNamespace(id="c"))
            nba = {t["trait_key"]: t["value"] for t in draft.rookie_trait_records(player, prospect, traits[prospect["id"]])}
            inputs = _generated_player_inputs(player, nba).to_dict()["inputs"]
            cls.rows.append((prospect, player, nba, {iid: scalar_value(rec) for iid, rec in inputs.items()}))
        cls.real = [row for row in cls.rows if row[0]["league"] == "NCAA"]

    def corr(self, stat, ids):
        xs = [p["public_stats"]["college"]["profile"][stat] for p, _, _, _ in self.real]
        ys = [st.mean(v[i] for i in ids) for _, _, _, v in self.real]
        return st.correlation(xs, ys)

    def test_rookie_record_carries_college_estimates(self):
        prospect, player, _, _ = self.real[0]
        profile = player["college_profile"]
        self.assertEqual(profile["team"], prospect["source_team"])
        self.assertIn("S07", profile["inputs"])
        value, weight = profile["inputs"]["S07"]
        self.assertTrue(0 < weight <= rp.INPUT_WEIGHT_MAX)
        self.assertIn(rp.SOURCE_ID, player["source_ids"])
        generated = next(row for row in self.rows if row[0]["league"] == "generated")
        self.assertNotIn("college_profile", generated[1])

    def test_shooters_rim_protectors_creators_and_passers_come_out_right(self):
        self.assertGreater(self.corr("ft_pct", ("S07",)), 0.6)
        self.assertGreater(self.corr("three_pct", ("S01", "S03")), 0.4)
        self.assertGreater(self.corr("blk_pct", ("S37", "S36")), 0.6)
        self.assertGreater(self.corr("usg", ("S16", "S18", "S19")), 0.3)
        self.assertGreater(self.corr("ast_pct", tuple(f"F0{i}.{p}" for i in range(1, 10) for p in ("recognition", "execution"))), 0.5)
        self.assertGreater(self.corr("orb_pct", ("S29",)), 0.6)
        self.assertGreater(self.corr("stl_pct", ("S42", "S43")), 0.6)
        self.assertLess(self.corr("tov_pct", ("S17",)), 0)

    def test_college_evidence_moves_inputs_toward_the_fitted_estimate(self):
        from nba_gm_data.input_estimator import _generated_player_inputs, scalar_value
        prospect, player, nba, with_college = self.real[0]
        without = {k: v for k, v in player.items() if k != "college_profile"}
        plain = {iid: scalar_value(rec) for iid, rec in _generated_player_inputs(without, nba).to_dict()["inputs"].items()}
        moved = 0
        for iid, (target, weight) in player["college_profile"]["inputs"].items():
            if iid == "T08":
                continue
            if abs(target - plain[iid]) > 1:
                self.assertLess(abs(with_college[iid] - target), abs(plain[iid] - target), iid)
                moved += 1
        self.assertGreater(moved, 5)
        untouched = [iid for iid in plain if iid.startswith("S") and iid not in player["college_profile"]["inputs"]]
        self.assertTrue(all(plain[iid] == with_college[iid] for iid in untouched))

    def test_entry_level_matches_generated_prospects_at_the_same_slots(self):
        gen = [row for row in self.rows if row[0]["league"] == "generated"]
        groups = ("S07", "S01", "S37", "S16")
        real_mean = st.mean(st.mean(v[i] for i in groups) for _, _, _, v in self.real)
        gen_mean = st.mean(st.mean(v[i] for i in groups) for _, _, _, v in gen)
        self.assertLess(abs(real_mean - gen_mean), 5.0)


class CardTests(unittest.TestCase):
    def test_card_block_shows_real_seasons_and_profile(self):
        entry = rp.prospects_for_year("2027")[0]
        college = rp.college_block(entry)
        card = rp.college_card(college)
        self.assertEqual(card["team"], entry["college_team"])
        self.assertEqual(card["seasons"][0]["college_team"], entry["seasons"][0]["team"])
        self.assertEqual(card["seasons"][0]["games"], entry["seasons"][0]["games"])
        self.assertEqual([s[0] for s in card["stats"]][:3], ["USG%", "AST%", "TOV%"])
        # Lookup by id works for slim board payloads (no public_stats).
        slim = {"id": rp.prospect_id("2027", entry["name"]), "draft_year": "2027"}
        self.assertEqual(rp.college_entry_for(slim)["team"], entry["college_team"])
        self.assertIsNone(rp.college_entry_for({"id": "draft_prospect_2027-nobody", "draft_year": "2027"}))

    def test_prospect_card_payload_uses_real_college_seasons(self):
        from nba_gm_data import app_actions as aa
        from nba_gm_data import play
        records = real_class(2027, 5)
        prospect = next(p for p in records["draft_prospects"] if p["league"] == "NCAA")
        generated = next(p for p in records["draft_prospects"] if p["league"] == "generated")
        active = {"meta": {"talent_model_version": 2, "draft_class_seed": 5}, "teams": [{"id": "team_test", "abbrev": "TST"}],
                  "draft_prospects": records["draft_prospects"], "draft_prospect_traits": records["draft_prospect_traits"]}
        context = {"save": {"meta": {"user_team_abbrev": "TST"}}, "active": active}
        with patch.object(aa, "dashboard_read_context", return_value=context), \
                patch.object(aa, "transaction_read_active", return_value=active), \
                patch.object(aa, "user_team_abbrev", return_value="TST"), \
                patch.object(play, "prospect_scouted_pct", return_value=100), \
                patch("nba_gm_data.spatial.prospect_spatial_profile", return_value={}):
            card = aa.prospect_card_payload(active, Path("unused.json"), prospect["id"], "2027")
            other = aa.prospect_card_payload(active, Path("unused.json"), generated["id"], "2027")
        self.assertEqual(card["college_profile"]["team"], prospect["source_team"])
        self.assertEqual(card["season"]["college_team"], prospect["source_team"])
        self.assertEqual(card["recent_games"], [])
        self.assertIsNone(other["college_profile"])
        self.assertTrue(other["recent_games"])


@unittest.skipUnless(UNIVERSE.exists(), "canonical universe not available")
class CanonicalClassTests(unittest.TestCase):
    def test_stored_2027_class_has_real_prospects_and_registered_source(self):
        universe = json.loads(UNIVERSE.read_text(encoding="utf-8"))
        prospects = [p for p in universe["draft_prospects"] if p["draft_year"] == "2027"]
        self.assertEqual(len(prospects), 60)
        real = [p for p in prospects if p["league"] == "NCAA"]
        self.assertEqual({p["name"] for p in real}, {e["name"] for e in rp.prospects_for_year("2027")})
        self.assertTrue(any(s["id"] == rp.SOURCE_ID for s in universe["sources"]))
        self.assertEqual(universe["meta"]["counts"]["sources"], len(universe["sources"]))
        ids = {p["id"] for p in prospects}
        self.assertTrue(all(e["prospect_id"] in ids for e in universe["draft_board_entries"]))


@unittest.skipUnless(RAW.exists(), "local Barttorvik tables not available")
class ProjectionModelTests(unittest.TestCase):
    def test_logistic_fit_recovers_direction_and_eligibility_passes_chance_on(self):
        import real_prospects as model
        xs = [[i / 50 - 1] for i in range(101)]
        ys = [1 if x[0] + 0.3 * math.sin(i) > 0 else 0 for i, x in enumerate(xs)]
        beta = model.logistic_fit(xs, ys, [1.0] * len(xs), ridge=0.1)
        self.assertGreater(beta[1], 1.0)
        young = {"born": __import__("datetime").date(2009, 4, 8), "cls": 0, "season": 2027}
        self.assertFalse(model.eligible(young, 2027))
        self.assertTrue(model.eligible(young, 2028))
        self.assertTrue(model.eligible({"born": None}, 2027))


if __name__ == "__main__":
    unittest.main()
