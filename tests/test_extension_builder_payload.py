"""Contract extension builder: the page shows the engine's own extension numbers.

The builder tells the user the salary a player extends for, the hard-cap limit for each term and what the deal does
to the cap and the luxury tax, before anything is sent. These tests keep those numbers equal to the rule
`submit_extension_offer` runs and to the tax rule the game charges (trade_tax).
"""
from __future__ import annotations

import json
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

from nba_gm_data import app_actions as aa
from nba_gm_data import trade_tax
from nba_gm_data.save import load_save

ROOT = Path(__file__).resolve().parents[1]
APP_JS = ROOT / "src/nba_gm_data/gui/app.js"


def old_submit_line(candidate: dict, player_id: str, seed: int, guaranteed: bool) -> float:
    """The acceptance line exactly as submit_extension_offer_action wrote it before the shared helper."""
    from nba_gm_data.contract_protection import security_penalty

    ask = float(candidate.get("projected_aav_millions") or 0.0)
    fit = float(candidate.get("team_fit_score") or 50.0)
    security = security_penalty(candidate, guaranteed)
    flexibility = round(max(8.0, min(92.0, 38.0 + fit * 0.18 + (sum(ord(c) for c in f"{seed}:{player_id}:extension") % 31) - 15)), 1)
    line = ask * (1.02 - flexibility / 260.0)
    line *= 1 + security / 100
    return line


class ExtensionPriceRuleTests(unittest.TestCase):
    def test_shared_rule_equals_the_original_submit_math(self):
        for ask in (2.1, 9.87, 21.55, 44.0):
            for minutes in (0.0, 11.0, 26.0, 34.5):
                for seed in (1, 7, 447):
                    for player_id in ("player_a", "player_bkn-michael-porter-jr"):
                        candidate = {"projected_aav_millions": ask, "minutes_projection": minutes}
                        terms = aa.extension_offer_terms(candidate, player_id, seed)
                        for key, guaranteed in (("guaranteed", True), ("non_guaranteed", False)):
                            with self.subTest(ask=ask, minutes=minutes, seed=seed, player=player_id, key=key):
                                self.assertEqual(terms["accept_line_millions"][key], old_submit_line(candidate, player_id, seed, guaranteed))

    def test_shown_price_is_the_smallest_accepted_offer(self):
        for line in (1.0, 5.0, 5.0005, 5.001, 5.0011, 12.3456, 19.245807692307693, 23.09496923076923, 40.0):
            with self.subTest(line=line):
                offer = aa.smallest_extension_offer_accepted(line)
                self.assertTrue(aa.extension_offer_accepted(offer, line))
                self.assertFalse(aa.extension_offer_accepted(round(offer - 0.1, 1), line))
                self.assertAlmostEqual(offer * 10, round(offer * 10), places=9)

    def test_eligibility_reasons_are_plain_words(self):
        self.assertIn("closed", aa.extension_eligibility_reason({"eligible": True}, False, 3))
        self.assertIn("last two seasons", aa.extension_eligibility_reason({"eligible": False, "eligibility_status": "not_in_extension_window"}, True, 3))
        self.assertIn("retire", aa.extension_eligibility_reason({"eligible": True}, True, 0))
        self.assertIsNone(aa.extension_eligibility_reason({"eligible": True}, True, 2))


class ExtensionRoomIntegrationTests(unittest.TestCase):
    """A real save (Brooklyn, preseason 2026): the price shown is where submit flips from no to yes."""

    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        cls.save_dir = Path(cls.tmp.name)
        cls.canonical = aa.load_app_canonical(ROOT)
        created = aa.dispatch_app_action("create_save", {"team": "BKN", "name": "ext", "seed": 7}, root=ROOT, save_dir=cls.save_dir, canonical=cls.canonical)
        cls.save_path = created["save_path"]
        room = cls.call("extension_room", {"team": "BKN"})
        eligible = [c for c in room["candidates"] if c["eligible"]]
        if not eligible:
            raise unittest.SkipTest("no extension-eligible player on this roster in the current data")
        cls.room = cls.call("extension_room", {"team": "BKN", "player_id": eligible[0]["player_id"]})
        cls.candidate = cls.room["candidates"][0]

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    @classmethod
    def call(cls, action: str, payload: dict) -> dict:
        return aa.dispatch_app_action(action, {"save_path": cls.save_path, **payload}, root=ROOT, save_dir=cls.save_dir, canonical=cls.canonical)

    def test_cap_table_uses_the_tax_rule_the_game_charges(self):
        save = load_save(Path(self.save_path))
        from nba_gm_data.save import canonical_with_save, ensure_league_save_defaults

        active = canonical_with_save(self.canonical, ensure_league_save_defaults(save, self.canonical))
        team_id = self.room["team"]["id"]
        table = self.candidate["cap_table"]
        start = int(self.candidate["start_season"][:4])
        self.assertGreaterEqual(int(table[-1]["season"][:4]), start + self.candidate["safe_years"] - 1, "the table reaches the end of the longest deal")
        for row in table:
            with self.subTest(season=row["season"]):
                rule = row["tax_rule"]
                for payroll in (150.0, 214.7, 230.33, 260.0):
                    expected = trade_tax.luxury_tax_bill(payroll * 1e6, row["season"], rule["repeater"]) / 1e6
                    self.assertAlmostEqual(js_tax(payroll, rule), expected, places=6)
                self.assertAlmostEqual(row["payout_share_if_under_millions"], round(trade_tax.pool_share_if_under(active, team_id, row["season"]) / 1e6, 2), places=6)

    def test_price_shown_is_where_submit_flips(self):
        c = self.candidate
        years = min(c["safe_years"], c["preferred_years"])
        price = c["accept_offer_millions"]["guaranteed"]
        self.assertLessEqual(price, c["max_aav_by_years"][str(years)], "this player's price fits under the hard cap")
        below = self.call("submit_extension_offer", {"player_id": c["player_id"], "years": years, "aav_millions": round(price - 0.1, 1), "guaranteed": True})
        self.assertEqual(below["status"], "rejected")
        self.assertEqual(below["needed_millions"], price)
        signed = self.call("submit_extension_offer", {"player_id": c["player_id"], "years": years, "aav_millions": price, "guaranteed": True})
        self.assertEqual(signed["status"], "applied")
        contract = load_save(Path(self.save_path))["contract_overrides"][c["player_id"]]
        added = [row for row in contract["seasons"] if row.get("season") >= c["start_season"]]
        self.assertEqual(len(added), years)
        self.assertTrue(all(abs(float(row["salary"]) - price * 1e6) < 1 for row in added))

    @unittest.skipUnless(shutil.which("node"), "node is needed to run the browser preview")
    def test_browser_verdict_matches_submit_rule(self):
        c = self.candidate
        cases = []
        for years in range(1, 6):
            for guaranteed in (True, False):
                price = c["accept_offer_millions"]["guaranteed" if guaranteed else "non_guaranteed"]
                ceiling = int(float(c["max_aav_by_years"].get(str(years)) or 0) * 10 + 1e-6) / 10
                for aav in sorted({1.8, round(price - 0.1, 1), price, round(price + 0.1, 1), 60.0, max(1.8, ceiling), round(ceiling + 0.1, 1)}):
                    cases.append({"years": years, "aav": aav, "guaranteed": guaranteed})
        results = js_previews({"offer_rules": self.room["offer_rules"]}, c, cases)
        for case, result in zip(cases, results):
            with self.subTest(**case):
                key = "guaranteed" if case["guaranteed"] else "non_guaranteed"
                maximum = float(c["max_aav_by_years"].get(str(case["years"])) or 0.0)
                legal = case["years"] <= c["safe_years"] and 1.8 <= case["aav"] <= maximum + 0.001
                accepted = aa.extension_offer_accepted(case["aav"], c["accept_line_millions"][key])
                self.assertEqual(result["canSubmit"], legal)
                self.assertEqual(result["tone"] == "yes", legal and accepted)
                start = int(c["start_season"][:4])
                for row in result["seasons"]:
                    year = int(row["season"][:4])
                    self.assertEqual(row["salary"], case["aav"] if start <= year < start + case["years"] else 0)


def js_source(start_marker: str, end_marker: str) -> str:
    source = APP_JS.read_text()
    start = source.index(start_marker)
    return source[start:source.index(end_marker, start)]


JS_HELPERS = (
    "const money=v=>`$${Number(v).toFixed(1)}M`;\nconst signedMoney=v=>`$${Number(v)>=0?'+':''}${Number(v).toFixed(1)}M`;\n"
    "const clampNumber=(v,a,b)=>Math.max(a,Math.min(b,v));\nconst roundOfferTenth=v=>Math.round(Number(v||0)*10)/10;\n"
    "const shortSeasonLabel=s=>String(s).slice(2,4)+'-'+String(s).slice(-2);\nconst escapeHtml=s=>String(s);\nconst escapeAttr=s=>String(s);\n"
)


def js_tax(payroll: float, rule: dict) -> float:
    script = JS_HELPERS + js_source("function extensionLuxuryTax(", "// The decision submit_extension_offer makes") + (
        "\nconst c=JSON.parse(require('fs').readFileSync(0,'utf8'));process.stdout.write(JSON.stringify(extensionLuxuryTax(c.payroll,c.rule)));"
    )
    result = subprocess.run(["node", "-e", script], input=json.dumps({"payroll": payroll, "rule": rule}), capture_output=True, text=True, check=True)
    return float(json.loads(result.stdout))


def js_previews(room: dict, candidate: dict, cases: list[dict]) -> list[dict]:
    script = JS_HELPERS + js_source("function extensionCandidate(", "function extensionVerdictMarkup(") + (
        "\nconst input=JSON.parse(require('fs').readFileSync(0,'utf8'));"
        "process.stdout.write(JSON.stringify(input.cases.map(d=>{const p=extensionOfferPreview(input.candidate,input.room,d);"
        "return {tone:p.verdict.tone,canSubmit:p.canSubmit,seasons:p.seasons.map(r=>({season:r.season,salary:r.salary}))};})));"
    )
    payload = json.dumps({"room": room, "candidate": {k: v for k, v in candidate.items() if k != "analysis"}, "cases": cases})
    result = subprocess.run(["node", "-e", script], input=payload, capture_output=True, text=True, check=True)
    return json.loads(result.stdout)


if __name__ == "__main__":
    unittest.main()
