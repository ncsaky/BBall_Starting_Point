"""Prospect cards show the same public potential the AI drafts on, never the latent upside tail.

Q2 diagnosis (docs/agents/tasks/q2-draft-falling-prospects.md, finding 5): generated prospects with a hidden upside
tail showed their true 85+ potential on the board while every AI team saw the public number, so they appeared to
"fall" irrationally. Product rule 4: what the user sees must match what the engine uses.
"""
import unittest
from pathlib import Path

from nba_gm_data.app_actions import load_app_canonical
from nba_gm_data.draft import generated_class_for_context, prospect_evaluation_value
from nba_gm_data.prospect_cards import prospect_rating_projection
from nba_gm_data.save import presentation_rating_value

ROOT = Path(__file__).resolve().parents[1]


class PublicPotentialTests(unittest.TestCase):
    def test_hidden_tail_prospects_show_public_potential(self):
        canonical = load_app_canonical(ROOT)
        checked = 0
        for year in ("2028", "2029", "2030", "2031"):
            generated = generated_class_for_context(canonical, year)
            for prospect in generated["draft_prospects"]:
                prior = prospect.get("scouting_prior") or {}
                if prior.get("potential") is None or prior["potential"] == prospect["potential"]:
                    continue
                shown = prospect_rating_projection(canonical, {"id": prospect["id"], "league": "generated",
                                                               "draft_year": year}, {}, 0)
                self.assertEqual(shown["potential"], presentation_rating_value(prospect_evaluation_value(prospect, "potential")))
                # The true potential can sit above (hidden upside tail) or below (scouting miss) the public number.
                if abs(prospect["potential"] - prior["potential"]) >= 1.0:
                    self.assertNotEqual(shown["potential"], presentation_rating_value(prospect["potential"]))
                checked += 1
        self.assertGreater(checked, 0, "expected at least one hidden-tail prospect across four classes")


if __name__ == "__main__":
    unittest.main()
