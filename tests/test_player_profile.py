"""Player card profile for the inputs ratings model: layers, evidence counts, scale, development."""
import json
import unittest
from copy import deepcopy
from pathlib import Path
from tempfile import TemporaryDirectory

from nba_gm_data import player_profile as pp
from nba_gm_data import ratings_model as rm

ROOT = Path(__file__).resolve().parents[1]
INPUTS = ROOT / rm.INPUTS_FILE
UNIVERSE = ROOT / "data/canonical/universe_2026_27_offseason.json"


def technique_values(profile):
    out = {}
    for group in profile["layers"][0]["groups"]:
        for entry in group.get("entries", []):
            out[entry["id"]] = entry["value"]
        for pair in group.get("pairs", []):
            out[pair["read"]["id"]] = pair["read"]["value"]
            out[pair["delivery"]["id"]] = pair["delivery"]["value"]
    return out


def all_entries(profile):
    for layer in profile["layers"]:
        for group in layer["groups"]:
            yield from group.get("entries", [])
            for pair in group.get("pairs", []):
                yield pair["read"]
                yield pair["delivery"]


@unittest.skipUnless((INPUTS.exists() or INPUTS.with_name(INPUTS.name + ".gz").exists()) and UNIVERSE.exists(), "player inputs file not built yet")
class PlayerProfileTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.active = json.loads(UNIVERSE.read_text())
        rm.install_inputs_model(cls.active, ROOT)
        cls.pid = next(p["id"] for p in cls.active["players"] if p["name"] == "Stephen Curry")
        cls.profile = pp.player_profile(cls.active, cls.pid)

    def test_all_94_inputs_sit_in_exactly_one_layer(self):
        ids = [e["id"] for e in all_entries(self.profile)]
        self.assertEqual(len(ids), 94)
        self.assertEqual(len(set(ids)), 94)
        self.assertEqual([l["total"] for l in self.profile["layers"]], [64, 12, 18])

    def test_header_values_are_on_the_open_ended_scale(self):
        for key in ("ovr", "off", "def"):
            self.assertTrue(0 < self.profile["header"][key] < 100, key)
        league = pp.league_reference(self.active[rm.MODEL_KEY]["inputs_key"])["league"]
        for key in ("max_ovr", "max_off", "max_def"):
            self.assertLess(league[key], 100)
        self.assertGreater(league["max_ovr"], 90)

    def test_evidence_counts_match_record_reasons(self):
        records = rm.effective_inputs(self.active, self.pid)
        for layer in self.profile["layers"]:
            ids = {e["id"] for g in layer["groups"] for e in
                   [*g.get("entries", []), *[x for p in g.get("pairs", []) for x in (p["read"], p["delivery"])]]}
            expected = sum(1 for i in ids if records[i]["reason"] != "prior")
            self.assertEqual(layer["from_player_data"], expected, layer["key"])
        for entry in all_entries(self.profile):
            self.assertEqual(entry["evidence"] == "prior", records[entry["id"]]["reason"] == "prior", entry["id"])

    def test_baseline_header_matches_league_table(self):
        ref = pp.league_reference(self.active[rm.MODEL_KEY]["inputs_key"])
        table = ref["display"][self.pid]
        for key in ("ovr", "off", "def"):
            self.assertAlmostEqual(self.profile["header"][key], table[key], delta=0.06)

    def test_development_changes_technique_values_and_header(self):
        ref = pp.league_reference(self.active[rm.MODEL_KEY]["inputs_key"])
        pid = min(ref["pids"], key=lambda p: abs(ref["display"][p]["off"] - 50))  # mid-table: no saturated percentiles
        before = pp.player_profile(self.active, pid)
        developed = deepcopy(self.active)
        rm.apply_development(developed, None, [{"player_id": pid, "trait_deltas": {"release_speed": 25.0}}])
        after = pp.player_profile(developed, pid)
        before_values, after_values = technique_values(before), technique_values(after)
        changed = [i for i in before_values if after_values[i] != before_values[i]]
        self.assertTrue(changed)
        self.assertTrue(all(i.startswith("S") for i in changed), changed)
        self.assertGreater(after["header"]["off"], before["header"]["off"])
        # the shared baseline tables are untouched by development
        self.assertEqual(pp.player_profile(self.active, pid)["header"], before["header"])

    def test_players_without_inputs_get_no_profile(self):
        self.assertIsNone(pp.player_profile(self.active, "player_does-not-exist"))


@unittest.skipUnless((INPUTS.exists() or INPUTS.with_name(INPUTS.name + ".gz").exists()) and UNIVERSE.exists(), "player inputs file not built yet")
class PlayerCardPayloadTests(unittest.TestCase):
    def test_inputs_profile_only_for_inputs_model_saves(self):
        from nba_gm_data.app_actions import player_card_payload
        from nba_gm_data.save import create_league_save
        base = json.loads(UNIVERSE.read_text())
        pid = next(p["id"] for p in base["players"] if p["name"] == "Stephen Curry")
        with TemporaryDirectory() as tmp:
            new = Path(tmp) / "inputs.json"
            old = Path(tmp) / "legacy.json"
            create_league_save(ROOT, deepcopy(base), "GSW", new, seed=3, ratings_model=rm.INPUTS_V1)
            create_league_save(ROOT, deepcopy(base), "GSW", old, seed=3)
            payload = player_card_payload(deepcopy(base), new, pid)
            self.assertIn("inputs_profile", payload)
            self.assertEqual(payload["inputs_profile"]["player_id"], pid)
            self.assertIsNotNone(payload["inputs_profile"]["coach"]["minutes_projection"])
            self.assertNotIn("inputs_profile", player_card_payload(deepcopy(base), old, pid))


if __name__ == "__main__":
    unittest.main()
