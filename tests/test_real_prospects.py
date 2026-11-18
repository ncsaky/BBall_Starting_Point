"""Real players in the first future drafts (docs/agents/tasks/real-prospects.md).

Bundle: data/canonical/real_prospects.json (derived; rebuilt by scripts/research/real_prospects.py from the local
Barttorvik tables and data/research/prospect_scouting/).
"""
import datetime as dt
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
YEARS = ("2027", "2028", "2029")


def pick_range(rank):
    return "1-3" if rank <= 3 else "4-10" if rank <= 10 else "11-20" if rank <= 20 else "21-30" if rank <= 30 else "31-60"


def real_class(year, seed=1, talent_model=True):
    return to_plain(draft.generate_draft_class_records(str(year), seed, talent_model=talent_model, real_prospects=True))


def generated_class(year, seed=1, talent_model=True):
    return to_plain(draft.generate_draft_class_records(str(year), seed, talent_model=talent_model))


def is_real(prospect):
    return prospect["league"] != "generated"


def pool():
    return rp.bundle()["prospects"]


def by_name(name):
    return next(p for p in pool() if p["name"] == name)


class BundleTests(unittest.TestCase):
    def test_pool_holds_college_high_school_and_international_players(self):
        self.assertEqual(rp.draft_years(), set(YEARS))
        ids = [p["id"] for p in pool()]
        self.assertEqual(len(ids), len(set(ids)))
        kinds = Counter(p["kind"] for p in pool())
        self.assertGreater(kinds["college"], 200)
        self.assertGreaterEqual(kinds["high_school"], 80)
        self.assertGreaterEqual(kinds["international"], 20)
        for p in pool():
            chances = p["chance_by_year"]
            self.assertTrue(set(chances) <= set(YEARS), p["name"])
            self.assertLessEqual(sum(chances.values()), 1.0 + 1e-9, p["name"])
            self.assertEqual(set(chances), set(p["years"]), p["name"])
            for year, view in p["years"].items():
                self.assertTrue(1 <= view["expected_pick"] <= 200, p["name"])
                self.assertGreater(view["age_at_draft"], 18.0, p["name"])
            if p["kind"] == "college":
                self.assertTrue(all(v.get("projected_profile") for v in p["years"].values()), p["name"])
            else:
                self.assertEqual(set(p["skill_base"]), set(draft.DRAFT_TRAITS), p["name"])

    def test_bundle_records_out_of_sample_check_and_evidence_fits(self):
        bundle = rp.bundle()
        same_year = bundle["projection"]["out_of_sample"]["0"]["direct"]
        self.assertGreater(same_year["auc"], 0.95)
        self.assertGreater(same_year["spearman_rank_vs_pick"], 0.4)
        fits = bundle["input_mapping"]["targets"]
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


class ScoutBlendTests(unittest.TestCase):
    """2027: the scouts' consensus board leads; the college model gains weight as games are played."""

    def test_consensus_board_leads_the_2027_order(self):
        board = sorted((p for p in pool() if (p.get("scouting") or {}).get("consensus_rank")),
                       key=lambda p: p["scouting"]["consensus_rank"])
        self.assertEqual([p["name"] for p in board[:2]], ["Tyran Stokes", "Stefan Joksimovic"])
        top = sorted((p for p in pool() if "2027" in p["years"]), key=lambda p: p["years"]["2027"]["expected_pick"])[:10]
        ranks = [p["scouting"].get("consensus_rank") for p in top]
        self.assertTrue(all(r is not None and r <= 15 for r in ranks), ranks)
        # Recent boards count more than stale ones; mocks a little less than big boards.
        weights = rp.bundle()["scouting_sources"]["boards"]
        self.assertGreater(weights["espn_2027_bigboard"], weights["br_2027_bigboard"])
        self.assertGreater(weights["br_2027_bigboard"], weights["si_2027_bigboard_june"])
        self.assertGreater(weights["espn_2027_bigboard"], weights["clutchpoints_2027_mock"])

    def test_model_weight_follows_games_played(self):
        for p in pool():
            if p["kind"] != "college":
                continue
            games = p["games_this_season"]
            self.assertAlmostEqual(p["model_weight"], games / (games + 20), places=3)
            listed = bool((p.get("scouting") or {}).get("consensus_rank"))
            self.assertAlmostEqual(p["scout_share"], round(1 - p["model_weight"], 3) if listed else 0.0, places=3)
            if not listed and "2027" in p["chance_by_year"]:
                # Not on any board: scouts never raise his 2027 chance above the model's.
                self.assertLessEqual(p["chance_by_year"]["2027"], p["model"]["chance_by_year"]["2027"] + 1e-4, p["name"])
        stokes = by_name("Tyran Stokes")
        self.assertGreater(stokes["chance_by_year"]["2027"], 0.75)
        self.assertLess(stokes["years"]["2027"]["expected_pick"], 3)

    def test_players_on_the_boards_without_college_data_are_real_prospects(self):
        joksimovic = by_name("Stefan Joksimovic")
        self.assertEqual(joksimovic["kind"], "international")
        self.assertEqual(joksimovic["scouting"]["team"], "Baskonia")
        mccoy = by_name("Brandon McCoy Jr.")
        self.assertEqual(mccoy["kind"], "college_no_stats")
        # Out for the season: less likely to go this spring than his board rank alone says.
        listed = [p for p in pool() if (p.get("scouting") or {}).get("consensus_rank") and p["kind"] != "college_no_stats"]
        near = [p["chance_by_year"].get("2027", 0) for p in listed if abs(p["scouting"]["consensus_rank"] - mccoy["scouting"]["consensus_rank"]) <= 3]
        self.assertLess(mccoy["chance_by_year"]["2027"], min(near))
        self.assertTrue(by_name("Najai Hines")["kind"] == "college")  # matched across the apostrophe spelling


@unittest.skipUnless((ROOT / "scripts/research/barttorvik.py").exists(), "builder not available")
class NameMatchingTests(unittest.TestCase):
    def test_names_and_teams_normalize_across_sources(self):
        import real_prospects as builder
        self.assertEqual(builder.name_key("Na'jai Hines"), builder.name_key("Najai Hines"))
        self.assertEqual(builder.name_key("Paul McNeil, Jr."), builder.name_key("Paul McNeil Jr."))
        self.assertEqual(builder.name_key("Patrick Ngongba II"), builder.name_key("Patrick Ngongba"))
        self.assertEqual(builder.name_key("Hugo Yimga-Moukouri"), builder.name_key("Hugo Yimga Moukouri"))
        self.assertEqual(builder.name_key("JoJo Tugler"), builder.name_key("Joseph Tugler"))
        self.assertEqual(builder.name_key("Rubén Prey"), builder.name_key("Rueben Prey"))
        self.assertNotEqual(builder.name_key("Dylan Mingo"), builder.name_key("Kayden Mingo"))
        self.assertEqual(builder.team_key("UConn"), builder.team_key("Connecticut"))
        self.assertEqual(builder.team_key("Ohio State"), builder.team_key("Ohio St."))
        self.assertEqual(builder.team_key("Miami (FL)"), builder.team_key("Miami FL"))

    def test_consensus_imputes_missing_ranks_past_the_list(self):
        import real_prospects as builder
        boards = {"sources": [{"id": "a", "kind": "big_board", "published": "2026-11-05", "ranked_count": 10},
                              {"id": "b", "kind": "big_board", "published": "2026-11-05", "ranked_count": 10}],
                  "players": [{"name": "X", "ranks": {"a": 1, "b": 2}}, {"name": "Y", "ranks": {"a": 2}},
                              {"name": "Z", "ranks": {"b": 1}}]}
        rows, _ = builder.consensus_board(boards)
        # Y (2nd on one list, missing from the other) and Z (1st on one, missing from the other) trail X.
        self.assertEqual([r["name"] for r in rows], ["X", "Z", "Y"])
        self.assertAlmostEqual(builder.imputed_rank({"ranked_count": 100}), 130.0)

    def test_scouting_tags_map_to_skills(self):
        import real_prospects as builder
        self.assertEqual(builder.tag_skills("elite shot blocking"), ["rim_protection"])
        self.assertEqual(builder.tag_skills("catch-and-shoot threes"), ["shooting"])
        self.assertIn("passing", builder.tag_skills("creative passing"))
        self.assertEqual(builder.tag_skills("very young"), [])
        self.assertEqual(builder.tag_skills("long-range shooting potential"), ["shooting"])
        scores = builder.tag_scores(["rim protection", "rebounding"], ["3-point shooting"])
        self.assertGreater(scores["rim_protection"], 0.8)  # one tag: about one standard deviation (eased)
        self.assertLess(scores["shooting"], -0.8)
        many = builder.tag_scores(["passing", "vision", "playmaking", "passing iq", "creative passing"], [])
        self.assertLess(many["passing"], builder.TAG_MAX_SD)

    def test_age_notes_and_the_age_rule(self):
        import real_prospects as builder
        self.assertEqual(builder.birth_from_note("Born June 11 2010 per SI"), dt.date(2010, 6, 11))
        self.assertEqual(builder.birth_from_note("Born Jan 2009 per a snippet"), dt.date(2009, 1, 15))
        self.assertEqual(builder.birth_from_note("Born 2008 (age 17)"), dt.date(2008, 7, 1))
        self.assertEqual(builder.birth_from_note("Turns 18 on Sept 30 2026 per SI (so born 2008-09-30, derived)"), dt.date(2008, 9, 30))
        born = builder.birth_from_note("19.1 (ESPN, Nov 5)")
        self.assertAlmostEqual(builder.age_on_draft_day(born, 2027), 19.73, delta=0.05)
        self.assertIsNone(builder.birth_from_note(None))


class RecruitTimingTests(unittest.TestCase):
    def test_recruit_timing_table_from_history(self):
        bands = rp.bundle()["declaration"]["recruit_timing"]["bands"]
        one_and_done = [b["drafted_after_years"]["1"] for b in bands]
        self.assertEqual(one_and_done, sorted(one_and_done, reverse=True))
        self.assertGreater(bands[0]["drafted_after_years"]["1"], 0.75, "top-5 recruits are usually one-and-done")
        self.assertLess(bands[0]["typical_pick"]["1"], 10)
        self.assertGreater(bands[0]["players"], 50)
        for band in bands:
            self.assertLessEqual(sum(band["drafted_after_years"].values()) + band["not_drafted_within_4"], 1.0 + 0.005)  # rounded shares
        ratings = rp.bundle()["declaration"]["recruit_timing"]["rating_by_rank"]
        self.assertEqual(ratings, sorted(ratings, reverse=True))

    def test_recruits_enter_after_a_college_year_and_follow_the_table(self):
        bands = rp.bundle()["declaration"]["recruit_timing"]["bands"]
        black = by_name("Beckham Black")  # 247 No. 1, class of 2027
        self.assertEqual(black["kind"], "high_school")
        self.assertNotIn("2027", black["years"])
        self.assertAlmostEqual(black["chance_by_year"]["2028"], bands[0]["drafted_after_years"]["1"])
        self.assertEqual(black["years"]["2028"]["class_year_at_draft"], "Fr")
        hiller = by_name("Colton Hiller")  # class of 2028
        self.assertEqual(set(hiller["years"]), {"2029"})
        # Reclassified freshmen take the college path with their scouting notes; too young for 2027.
        boumtje = by_name("Joaquim Boumtje Boumtje")
        self.assertEqual(boumtje["kind"], "college")
        self.assertNotIn("2027", boumtje["years"])
        self.assertTrue(boumtje["scouting"]["strengths"])

    def test_internationals_respect_the_age_rule(self):
        for p in pool():
            if p["kind"] != "international":
                continue
            born = dt.date.fromisoformat(p["birth_date"])
            for year in p["years"]:
                self.assertLessEqual(born.year, int(year) - 19, p["name"])


class DeclarationTests(unittest.TestCase):
    def test_declaration_draw_is_deterministic_and_varies_across_saves(self):
        entry = by_name("Colben Landrew")
        draws = [rp.declaration_year(entry, seed) for seed in range(1, 41)]
        self.assertEqual(draws, [rp.declaration_year(entry, seed) for seed in range(1, 41)])
        self.assertGreater(len(set(draws)), 1)
        share = draws.count("2027") / len(draws)
        self.assertLess(abs(share - entry["chance_by_year"]["2027"]), 0.25)
        stokes = by_name("Tyran Stokes")
        self.assertGreater(sum(rp.declaration_year(stokes, s) == "2027" for s in range(1, 101)), 65)

    def test_each_player_enters_at_most_one_class_per_save(self):
        for seed in (1, 2, 3):
            names = [e["name"] for year in YEARS for e in rp.class_entries(year, seed)]
            self.assertEqual(len(names), len(set(names)), seed)
            a = [e["name"] for e in rp.class_entries("2027", seed)]
            self.assertEqual(a, [e["name"] for e in rp.class_entries("2027", seed)])
        self.assertNotEqual([e["name"] for e in rp.class_entries("2027", 1)], [e["name"] for e in rp.class_entries("2027", 2)])

    def test_returners_come_back_a_year_older_and_developed(self):
        entry = next(p for p in pool() if p["kind"] == "college" and {"2027", "2028"} <= set(p["years"])
                     and p.get("scouting", {}).get("consensus_rank"))
        now, later = rp.class_entry(entry, "2027"), rp.class_entry(entry, "2028")
        self.assertAlmostEqual(later["age_at_draft"] - now["age_at_draft"], 1.0, delta=0.02)
        self.assertNotEqual(later["class_year_at_draft"], now["class_year_at_draft"])
        self.assertNotEqual(later["projected_profile"], now["projected_profile"])
        self.assertGreaterEqual(later["effective_minutes"], now["effective_minutes"] * 0.5)
        # A save where he returned has him in the 2028 class, not in 2027.
        seed = next(s for s in range(1, 500) if rp.declaration_year(entry, s) == "2028")
        self.assertNotIn(entry["name"], [e["name"] for e in rp.class_entries("2027", seed)])
        names_2028 = [e["name"] for e in rp.class_entries("2028", seed)]
        self.assertTrue(entry["name"] in names_2028 or len(names_2028) >= 58, (entry["name"], len(names_2028)))


class ClassAssemblyTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.classes = {year: real_class(year) for year in YEARS}

    def test_real_players_sit_at_their_slots_and_other_slots_keep_generated_prospects(self):
        for year, records in self.classes.items():
            prospects = records["draft_prospects"]
            self.assertEqual(len(prospects), 60)
            self.assertEqual(sorted(p["rank"] for p in prospects), list(range(1, 61)))
            real = [p for p in prospects if is_real(p)]
            self.assertEqual({p["name"] for p in real}, {e["name"] for e in rp.class_entries(year, 1)})
            generated = generated_class(year)["draft_prospects"]
            kept = {p["id"]: p for p in prospects if not is_real(p)}
            ignore = {"rank", "rank_range", "rookie_contract_value", "scouting_prior"}
            for original in generated:
                if original["id"] in kept:
                    self.assertEqual({k: v for k, v in kept[original["id"]].items() if k not in ignore},
                                     {k: v for k, v in original.items() if k not in ignore})
            self.assertEqual(len(kept) + len(real), 60)
            self.assertEqual(records["draft_classes"][0]["class_type"], "real_college_plus_generated")
            traits = Counter(t["prospect_id"] for t in records["draft_prospect_traits"])
            self.assertTrue(all(traits[p["id"]] == len(draft.DRAFT_TRAITS) for p in prospects))
            self.assertTrue(all(0 <= t["value"] <= 100 for t in records["draft_prospect_traits"]))
        leagues = Counter(p["league"] for r in self.classes.values() for p in r["draft_prospects"])
        self.assertGreater(leagues["High School"], 0)
        self.assertGreater(leagues["NCAA"], 40)

    def test_2027_order_follows_the_scouts(self):
        prospects = sorted(self.classes["2027"]["draft_prospects"], key=lambda p: p["rank"])
        ranks = [(p.get("public_stats", {}).get("scouting") or {}).get("consensus_rank") for p in prospects[:15]]
        listed = [r for r in ranks if r]
        self.assertGreaterEqual(len(listed), 13)
        self.assertGreater(st.correlation(range(len(listed)), listed), 0.8)

    def test_same_seed_same_class_and_saves_differ(self):
        a, b, c = real_class(2027, 7), real_class(2027, 7), real_class(2027, 8)
        self.assertEqual(json.dumps(a, sort_keys=True), json.dumps(b, sort_keys=True))
        self.assertNotEqual({p["name"] for p in a["draft_prospects"] if is_real(p)},
                            {p["name"] for p in c["draft_prospects"] if is_real(p)})

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
        records = [real_class(y, s) for y in YEARS for s in (1, 2)]
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
            real = [p["current_ability"] for r in records[:6] for p in r["draft_prospects"] if is_real(p) and pick_range(p["rank"]) == key]
            gen = [p["current_ability"] for r in records[6:] for p in r["draft_prospects"] if pick_range(p["rank"]) == key]
            if len(real) >= 5:
                self.assertLess(abs(st.median(real) - st.median(gen)), 3.0, key)
        misses = [p["potential"] - p["scouting_prior"]["potential"] for r in records[:6] for p in r["draft_prospects"]
                  if is_real(p) and p.get("scouting_prior")]
        self.assertGreater(len(misses), 40)
        self.assertTrue(3.0 < st.pstdev(misses) < 10, st.pstdev(misses))

    def test_college_profile_and_scouting_tags_shape_draft_traits(self):
        real = [p for r in self.classes.values() for p in r["draft_prospects"] if p.get("public_stats", {}).get("college")]
        traits = {}
        for r in self.classes.values():
            for t in r["draft_prospect_traits"]:
                traits.setdefault(t["prospect_id"], {})[t["trait_key"]] = t["value"]

        def r(stat, trait):
            xs = [p["public_stats"]["college"]["profile"][stat] for p in real]
            ys = [traits[p["id"]][trait] for p in real]
            return st.correlation(xs, ys)

        self.assertGreater(r("ft_pct", "shooting"), 0.4)
        self.assertGreater(r("blk_pct", "rim_protection"), 0.5)
        self.assertGreater(r("ast_pct", "passing"), 0.5)
        self.assertGreater(r("usg", "shot_creation"), 0.4)
        self.assertGreater(r("drb_pct", "rebounding"), 0.5)
        # Without college numbers, the scouts' tags and position carry the shape.
        entry = rp.class_entry(by_name("Cherif Millogo"), "2028")  # 7-4 centre: "rim protection", "rebounding"
        guard = rp.class_entry(by_name("Beckham Black"), "2028")  # point guard: "passing vision", "floor general"
        self.assertGreater(entry["skill_scores"]["rim_protection"], guard["skill_scores"]["rim_protection"] + 1.5)
        self.assertGreater(guard["skill_scores"]["passing"], entry["skill_scores"]["passing"] + 1.5)
        self.assertGreater(entry["skill_scores"]["size"], 2.0)
        self.assertEqual(entry["input_parts"], {})

    def test_real_prospects_carry_scouting_and_no_invented_medical_history(self):
        for records in self.classes.values():
            for p in records["draft_prospects"]:
                if not is_real(p):
                    continue
                stats = p["public_stats"]
                self.assertIn(rp.SOURCE_ID, p["source_ids"])
                self.assertFalse(p["medical_profile"]["major_prior_injuries"])
                if p["league"] == "NCAA" and stats.get("college"):
                    self.assertEqual(p["source_team"], stats["college"]["team"])
                    self.assertTrue(stats["college"]["seasons"])
                else:
                    self.assertTrue(stats.get("scouting"), p["name"])
                    self.assertIn(rp.SCOUTING_SOURCE_ID, p["source_ids"])


@unittest.skipUnless(HAVE_LEAGUE, "canonical league or player inputs not available")
class EntryInputTests(unittest.TestCase):
    """Drafted real prospects: their college strengths show in the 94 inputs."""

    @classmethod
    def setUpClass(cls):
        from nba_gm_data.input_estimator import _generated_player_inputs, scalar_value
        cls.rows = []
        records = [real_class(2027, 3), real_class(2029, 3)]
        traits = {}
        for t in (t for r in records for t in r["draft_prospect_traits"]):
            traits.setdefault(t["prospect_id"], []).append(t)
        for prospect in (p for r in records for p in r["draft_prospects"]):
            onboarding = {"draft_year": prospect["draft_year"], "name": prospect["name"], "overall_pick": prospect["rank"]}
            player = draft.rookie_player_record(onboarding, prospect, {"id": "team_t", "abbrev": "TST"}, SimpleNamespace(id="c"))
            nba = {t["trait_key"]: t["value"] for t in draft.rookie_trait_records(player, prospect, traits[prospect["id"]])}
            inputs = _generated_player_inputs(player, nba).to_dict()["inputs"]
            cls.rows.append((prospect, player, nba, {iid: scalar_value(rec) for iid, rec in inputs.items()}))
        cls.real = [row for row in cls.rows if row[0].get("public_stats", {}).get("college")]

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
        international = next((row for row in self.rows if row[0]["league"] == "International"), None)
        if international:
            self.assertNotIn("college_profile", international[1])
            self.assertIn(rp.SCOUTING_SOURCE_ID, international[1]["source_ids"])

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
        real = [row for row in self.rows if is_real(row[0])]
        groups = ("S07", "S01", "S37", "S16")
        self.assertGreater(len(gen), 10)
        real_mean = st.mean(st.mean(v[i] for i in groups) for _, _, _, v in real)
        gen_mean = st.mean(st.mean(v[i] for i in groups) for _, _, _, v in gen)
        self.assertLess(abs(real_mean - gen_mean), 5.0)


class CardTests(unittest.TestCase):
    def test_card_blocks_show_real_seasons_profile_and_scouting(self):
        entry = rp.class_entry(by_name("Tyran Stokes"), "2027", slot=1)
        college = rp.college_block(entry)
        card = rp.college_card(college)
        self.assertEqual(card["team"], entry["college_team"])
        self.assertEqual(card["seasons"][0]["college_team"], entry["seasons"][0]["team"])
        self.assertEqual([s[0] for s in card["stats"]][:3], ["USG%", "AST%", "TOV%"])
        scouting = rp.scouting_card(rp.scouting_block(entry))
        self.assertTrue(scouting["rank_label"].startswith("Consensus #1"))
        self.assertIn("ESPN #1", scouting["rank_hint"])
        self.assertTrue(scouting["strengths"] and scouting["weaknesses"])
        recruit = rp.scouting_card(rp.scouting_block(rp.class_entry(by_name("Beckham Black"), "2028")))
        self.assertIn("247Sports #1", recruit["rank_label"])
        self.assertIn("Southeastern Prep", recruit["where"])
        # Lookup by id works for slim board payloads (no public_stats).
        slim = {"id": rp.prospect_id("2027", entry["name"]), "draft_year": "2027"}
        self.assertEqual(rp.college_entry_for(slim)["team"], entry["college_team"])
        self.assertIsNone(rp.college_entry_for({"id": "draft_prospect_2027-nobody", "draft_year": "2027"}))
        intl = {"id": rp.prospect_id("2027", "Stefan Joksimovic"), "draft_year": "2027"}
        self.assertIsNone(rp.real_entry_for(intl)["college"])
        self.assertEqual(rp.real_entry_for(intl)["scouting"]["team"], "Baskonia")

    def test_prospect_card_payload_uses_real_college_seasons_and_scouting(self):
        from nba_gm_data import app_actions as aa
        from nba_gm_data import play
        records = real_class(2028, 5)
        prospect = next(p for p in records["draft_prospects"] if p.get("public_stats", {}).get("college"))
        recruit = next(p for p in records["draft_prospects"] if p["league"] == "High School")
        generated = next(p for p in records["draft_prospects"] if p["league"] == "generated")
        active = {"meta": {"talent_model_version": 2, "draft_class_seed": 5}, "teams": [{"id": "team_test", "abbrev": "TST"}],
                  "draft_prospects": records["draft_prospects"], "draft_prospect_traits": records["draft_prospect_traits"]}
        context = {"save": {"meta": {"user_team_abbrev": "TST"}}, "active": active}
        with patch.object(aa, "dashboard_read_context", return_value=context), \
                patch.object(aa, "transaction_read_active", return_value=active), \
                patch.object(aa, "user_team_abbrev", return_value="TST"), \
                patch.object(play, "prospect_scouted_pct", return_value=100), \
                patch("nba_gm_data.spatial.prospect_spatial_profile", return_value={}):
            card = aa.prospect_card_payload(active, Path("unused.json"), prospect["id"], "2028")
            hs = aa.prospect_card_payload(active, Path("unused.json"), recruit["id"], "2028")
            other = aa.prospect_card_payload(active, Path("unused.json"), generated["id"], "2028")
        self.assertEqual(card["college_profile"]["team"], prospect["source_team"])
        self.assertEqual(card["season"]["college_team"], prospect["source_team"])
        self.assertEqual(card["recent_games"], [])
        self.assertIsNone(hs["college_profile"])
        self.assertEqual(hs["recent_games"], [])
        self.assertTrue(hs["scouting_profile"]["rank_label"])
        self.assertIsNone(other["college_profile"])
        self.assertIsNone(other["scouting_profile"])
        self.assertTrue(other["recent_games"])


@unittest.skipUnless(UNIVERSE.exists(), "canonical universe not available")
class CanonicalClassTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from nba_gm_data.storage import load_universe_json
        cls.universe = load_universe_json(UNIVERSE)

    def test_stored_2027_class_is_the_seed_2027_draw_with_sources(self):
        prospects = [p for p in self.universe["draft_prospects"] if p["draft_year"] == "2027"]
        self.assertEqual(len(prospects), 60)
        self.assertEqual({p["name"] for p in prospects if is_real(p)}, {e["name"] for e in rp.class_entries("2027", 2027)})
        self.assertEqual(self.universe["draft_classes"][0]["seed"], 2027)
        ids = {s["id"] for s in self.universe["sources"]}
        self.assertTrue({rp.SOURCE_ID, rp.SCOUTING_SOURCE_ID} <= ids)
        prospect_ids = {p["id"] for p in prospects}
        self.assertTrue(all(e["prospect_id"] in prospect_ids for e in self.universe["draft_board_entries"]))

    def test_a_save_gets_its_own_2027_draw(self):
        same = draft.draft_class_for_save(self.universe, 2027)
        self.assertIs(same, self.universe)
        mine = draft.draft_class_for_save(self.universe, 11)
        self.assertIs(mine, draft.draft_class_for_save(self.universe, 11), "built once per seed")
        names = {p["name"] for p in mine["draft_prospects"] if is_real(p)}
        self.assertEqual(names, {e["name"] for e in rp.class_entries("2027", 11)})
        self.assertNotEqual(names, {p["name"] for p in self.universe["draft_prospects"] if is_real(p)})
        ids = {p["id"] for p in mine["draft_prospects"]}
        self.assertEqual(len(mine["draft_prospects"]), 60)
        self.assertTrue(all(e["prospect_id"] in ids for e in mine["draft_board_entries"]))
        self.assertTrue(all(r["prospect_id"] in ids for r in mine["scouting_reports"]))
        self.assertEqual(len(mine["draft_board_entries"]), len(self.universe["draft_board_entries"]))
        self.assertEqual(mine["players"], self.universe["players"])
        self.assertEqual(mine["draft_classes"][0]["seed"], 11)


@unittest.skipUnless(RAW.exists(), "local Barttorvik tables not available")
class ProjectionModelTests(unittest.TestCase):
    def test_logistic_fit_recovers_direction_and_eligibility_passes_chance_on(self):
        import real_prospects as model
        xs = [[i / 50 - 1] for i in range(101)]
        ys = [1 if x[0] + 0.3 * math.sin(i) > 0 else 0 for i, x in enumerate(xs)]
        beta = model.logistic_fit(xs, ys, [1.0] * len(xs), ridge=0.1)
        self.assertGreater(beta[1], 1.0)
        young = {"born": dt.date(2009, 4, 8), "cls": 0, "season": 2027}
        self.assertFalse(model.eligible(young, 2027))
        self.assertTrue(model.eligible(young, 2028))
        self.assertTrue(model.eligible({"born": None}, 2027))


if __name__ == "__main__":
    unittest.main()
