"""S2-SEAM-SHOOTING: the league input bridge (every player's 94 inputs -> the physics pieces' typed profiles) and the
shooting spot-check helpers."""
import copy
import json
import unittest
from pathlib import Path

from nba_gm_data.experimental_inputs import InputInterpretation, LeagueInterpretedInputs
from nba_gm_data.interior_defense import compile_profile
from nba_gm_data.offense_response import OffenseCoefficients, compile_offense, finishing_response, shooting_response
from nba_gm_data.player_model import PlayerInputs
from nba_gm_data.stage2 import league_inputs as L
from nba_gm_data.stage2 import shooting_check as S

ROOT = Path(__file__).resolve().parents[1]
HAVE_INPUTS = (ROOT / L.INPUTS_FILE).exists() or (ROOT / (L.INPUTS_FILE + ".gz")).exists()


@unittest.skipUnless(HAVE_INPUTS, "league inputs file not present")
class LeagueBridgeTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.data = L.compile_league(ROOT)
        cls.documents = L.load_league_documents(ROOT)

    def test_every_player_compiles_for_offense_and_interior(self):
        players = self.data["players"]
        self.assertEqual(len(players), len(self.documents))
        self.assertEqual(len(players), 691)
        self.assertTrue(all(r["offense"] and r["interior"] and not r["errors"] for r in players.values()))
        report = L.coverage_report(ROOT)
        self.assertEqual((report["offense_compiled"], report["interior_compiled"], report["errors"]), (691, 691, {}))
        self.assertEqual(set(report["offense_inputs"]), set(L.OFFENSE_READS))

    def test_cached_profile_matches_full_compile(self):
        pid = "player_den-nikola-jokic" if "player_den-nikola-jokic" in self.documents else sorted(self.documents)[0]
        full = compile_offense(L.interpreted_inputs(ROOT, pid))
        cached = L.offense_profile(self.data["players"][pid], player_id=pid)
        self.assertEqual(full.skills, cached.skills)
        for mode in ("catch", "pull_up"):
            self.assertAlmostEqual(shooting_response(full, mode=mode)["make_probability"],
                                   shooting_response(cached, mode=mode)["make_probability"], places=12)
        self.assertAlmostEqual(finishing_response(full, "dunk")["make_probability"],
                               finishing_response(cached, "dunk")["make_probability"], places=12)
        interior = compile_profile(L.interpreted_inputs(ROOT, pid))
        self.assertAlmostEqual(interior.acceleration_m_s2, L.interior_profile(self.data["players"][pid]).acceleration_m_s2)

    def test_unknown_cell_gets_the_group_prior_with_its_uncertainty(self):
        pid = sorted(self.documents)[0]
        doc = copy.deepcopy(self.documents[pid])
        doc["inputs"]["S01"] = {"status": "unknown", "value": None, "evidence": [], "reason": "not measured",
                                "uncertainty": {"confidence": "unknown", "notes": "test"}}
        doc["inputs"]["T03"] = {"status": "unknown", "value": None, "evidence": [], "reason": "not measured",
                                "uncertainty": {"confidence": "unknown", "notes": "test"}}
        directory = L.player_directory(ROOT)
        group = directory.get(pid, {}).get("group", "wing")
        priors = L._league_priors(ROOT)
        bridged, notes = L.bridge_document(doc, priors, group, L._league_p05(ROOT), L.sprint_reference(ROOT))
        self.assertEqual(sorted(notes["filled_unknown"]), ["S01", "T03"])
        record = bridged["inputs"]["S01"]
        self.assertEqual((record["status"], record["reason"], record["uncertainty"]["confidence"]), ("estimated", "prior", "low"))
        same_group = sorted(d["inputs"]["S01"]["value"]["grade"] for p, d in self.documents.items()
                            if directory.get(p, {}).get("group", "wing") == group)
        self.assertAlmostEqual(record["value"]["grade"], same_group[len(same_group) // 2], delta=1.0)
        lo, hi = json.loads(record["uncertainty"]["notes"])["interval"]
        self.assertLess(lo, record["value"]["grade"])
        self.assertGreater(hi, record["value"]["grade"])
        self.assertIn("group prior", record["evidence"][0]["method"])
        # The bridged document is a valid snapshot the physics pieces compile.
        profile = compile_offense(LeagueInterpretedInputs(PlayerInputs(bridged), InputInterpretation()))
        self.assertAlmostEqual(profile.skill(1), record["value"]["grade"] / 100)
        self.assertAlmostEqual(sum(profile.modes), 1.0, places=9)
        # The source document is untouched.
        self.assertEqual(self.documents[pid]["inputs"]["S01"]["status"], "estimated")

    def test_rounding_repair_is_bounded(self):
        pid = sorted(self.documents)[0]
        doc = copy.deepcopy(self.documents[pid])
        probs = doc["inputs"]["T01"]["value"]["rows"][0]["probabilities"]
        key = max(probs, key=probs.get)
        probs[key] += 1 + 1e-6 - sum(probs.values())  # storage rounding (sum off by 1e-6): repaired
        args = (L._league_priors(ROOT), "wing", L._league_p05(ROOT), L.sprint_reference(ROOT))
        bridged, notes = L.bridge_document(doc, *args)
        self.assertIn("T01", notes["rounding_repaired"])
        PlayerInputs(bridged)
        probs[key] += 1e-3  # a real error: still rejected by the player model
        bridged, _ = L.bridge_document(doc, *args)
        with self.assertRaises(ValueError):
            PlayerInputs(bridged)

    def test_acceleration_follows_the_grade_and_stays_in_human_range(self):
        grades, sprint = L._league_p05(ROOT), L.sprint_reference(ROOT)
        values = [L.acceleration_from_grade(g, grades, sprint) for g in (grades[0], grades[len(grades) // 2], grades[-1])]
        self.assertLess(values[0], values[1])
        self.assertLess(values[1], values[2])
        self.assertTrue(all(2.8 < v < 6.0 for v in values), values)


class ShootingCheckHelpersTest(unittest.TestCase):
    def test_kernel_conversion_reproduces_the_kernel(self):
        from nba_gm_data.offense_response import OffensiveProfile
        p = OffensiveProfile(None, "x", tuple([.6] * 15), .3, (.3, .3, .4), (.6, .3, .1), 265.0, 75.0, .5, .5,
                             OffenseCoefficients(), "r", .8, "test")
        context = {"dunk_share_rim": .3, "pullup_share_mid": .4, "pullup_share_three": .25, "corner_share": .2}
        plain = S.kernel_rates(p, context)
        converted = S.kernel_rates(p, context, conv=S.kernel_conversion())
        for key in plain:
            self.assertAlmostEqual(plain[key], converted[key], places=12)

    def test_weighted_errors(self):
        result = S.weighted_errors([(.40, .35, 100), (.30, .35, 100), (.35, .35, 200)])
        self.assertAlmostEqual(result["bias"], 0.0)
        self.assertAlmostEqual(result["mae"], .025)
        self.assertIsNone(S.weighted_errors([(.4, .35, 10)]))

    def test_short_mid_split(self):
        self.assertEqual(S._short_share(10, 4, .45, 0.0, .5), 1.0)  # empty long zone
        self.assertEqual(S._short_share(10, 4, .45, .44, .3), .3)  # ill-conditioned -> observed split
        self.assertAlmostEqual(S._short_share(10, 4.0, .50, .30, .5), .5)  # 4 made of 10 = .5*.5+.5*.3


if __name__ == "__main__":
    unittest.main()
