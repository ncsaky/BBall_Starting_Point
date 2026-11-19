import json
import unittest
from pathlib import Path

from nba_gm_data import analyst_evidence as ae

ROOT = Path(__file__).resolve().parents[1]
CLAIMS = ROOT / ae.CLAIMS_FILE


def _section(values, iid="S17", measured=True):
    players = {}
    for i, v in enumerate(values):
        players[f"p{i}"] = {"inputs": {iid: {"status": "estimated", "reason": "estimated" if measured else "prior",
                                             "value": {"grade": float(v)}, "evidence": []}}}
    return {"players": players}


def _claim(pid, level, support="both_hosts", inputs=("S17",), **extra):
    return {"id": "t1", "player_id": pid, "source": "Nerd Sesh", "episode": "Top 10 test", "video_id": "abc",
            "published": "2026-08-01", "timestamp": "00:01:00-00:02:00", "claim": "test claim",
            "inputs": list(inputs), "level": level, "support": support, "context": "general", **extra}


class AnalystEvidenceTests(unittest.TestCase):
    def test_contradicting_claim_leads_but_keeps_the_input_scale(self):
        section = _section(range(1, 101))
        before = sorted(d["inputs"]["S17"]["value"]["grade"] for d in section["players"].values())
        out = ae.apply_analyst_evidence(section, ROOT, [_claim("p9", "strong")])   # value 10: 10th percentile
        new = section["players"]["p9"]["inputs"]["S17"]["value"]["grade"]
        self.assertEqual(out["analyst_evidence"]["changed"], 1)
        self.assertGreater(new, 50.0)                 # past the middle: analysts lead (share 0.63)
        self.assertLess(new, 85.0)                    # but not all the way to the claim's target
        self.assertGreaterEqual(new, before[0])
        self.assertLessEqual(new, before[-1])         # stays inside the league's existing range, nothing clipped
        record = section["players"]["p9"]["inputs"]["S17"]
        sources = [e["source"] for e in record["evidence"]]
        self.assertTrue(any("Nerd Sesh" in s and "abc" in s and "2026-08-01" in s for s in sources))

    def test_agreeing_claim_changes_nothing(self):
        section = _section(range(1, 101))
        out = ae.apply_analyst_evidence(section, ROOT, [_claim("p89", "strong")])  # 90th percentile, inside band
        self.assertEqual(out["analyst_evidence"]["changed"], 0)
        self.assertEqual(section["players"]["p89"]["inputs"]["S17"]["value"]["grade"], 90.0)

    def test_weights_follow_support_context_and_specificity(self):
        both = ae.claim_weight(_claim("p", "weak"))
        one = ae.claim_weight(_claim("p", "weak", support="one_host"))
        disputed = ae.claim_weight(_claim("p", "weak", support="disputed"))
        broad = ae.claim_weight(_claim("p", "weak", inputs=("S10", "S15", "S19", "S24")))
        playoff = ae.claim_weight(_claim("p", "weak", context="playoffs"))
        week = ae.claim_weight(_claim("p", "weak", episode="Opening week"))
        self.assertGreater(both, one)
        self.assertGreater(one, disputed)
        self.assertAlmostEqual(broad, both / 2)
        self.assertLess(playoff, both)
        self.assertAlmostEqual(week, both * ae.SMALL_SAMPLE)

    def test_general_playmaking_claim_informs_the_general_passing_reads_as_one_input(self):
        claim = _claim("p", "strong", inputs=("F01.recognition", "S19"))
        self.assertEqual(set(ae.claim_inputs(claim)), {"S19", *ae.PASSING_READS})
        self.assertAlmostEqual(ae.claim_weight(claim), ae.claim_weight(_claim("p", "strong", inputs=("S19",))))
        post = _claim("p", "strong", inputs=("F08.recognition",))
        self.assertEqual(ae.claim_inputs(post), ["F08.recognition"])   # a specific read stays specific

    def test_prior_only_inputs_move_further_than_measured_ones(self):
        measured, prior = _section(range(1, 101)), _section(range(1, 101), measured=False)
        ae.apply_analyst_evidence(measured, ROOT, [_claim("p9", "strong", support="one_host")])
        ae.apply_analyst_evidence(prior, ROOT, [_claim("p9", "strong", support="one_host")])
        self.assertGreater(prior["players"]["p9"]["inputs"]["S17"]["value"]["grade"],
                           measured["players"]["p9"]["inputs"]["S17"]["value"]["grade"])

    def test_tendency_free_throw_and_unapplied_claims_are_recorded_only(self):
        section = _section(range(1, 101), iid="S07")
        out = ae.apply_analyst_evidence(section, ROOT, [
            _claim("p9", "elite", inputs=("S07",)),
            _claim("p9", "elite", not_applied="too vague"),
        ])
        self.assertEqual(out["analyst_evidence"]["changed"], 0)
        self.assertFalse(ae.applicable_input("T06"))
        self.assertFalse(ae.applicable_input("P01"))
        self.assertTrue(ae.applicable_input("P10"))


@unittest.skipUnless(CLAIMS.exists(), "analyst claims file not present")
class ClaimsFileTests(unittest.TestCase):
    def test_every_claim_is_attributed_and_valid(self):
        data = json.loads(CLAIMS.read_text())
        from nba_gm_data.player_model_registry import definition_registry
        ids = {row["id"] for row in definition_registry()["inputs"]}
        self.assertGreater(len(data["claims"]), 100)
        seen = set()
        for c in data["claims"]:
            self.assertNotIn(c["id"], seen)
            seen.add(c["id"])
            for key in ("source", "episode", "video_id", "published", "timestamp", "claim"):
                self.assertTrue(c.get(key), (c["id"], key))
            self.assertIn(c["level"], ae.LEVELS)
            self.assertIn(c["support"], ae.SUPPORT)
            self.assertTrue(set(c["inputs"]) <= ids, c["id"])
            self.assertTrue(c.get("player_id") or c.get("not_applied"), c["id"])
            self.assertLessEqual(len(c["claim"].split()), 25, c["id"])   # paraphrases, not long quotes


if __name__ == "__main__":
    unittest.main()
