"""Draft boards (docs/agents/tasks/draft-boards-plan.md): consensus big board, each team's scouts' board (talent
only), a deterministic GM layer, and no hidden true ratings on screen before a prospect is signed."""
import statistics
import unittest
from copy import deepcopy
from pathlib import Path

from nba_gm_data import draft as D
from nba_gm_data import draft_scouting as S
from nba_gm_data.app_actions import load_app_canonical
from nba_gm_data.prospect_cards import prospect_rating_projection
from nba_gm_data.save import presentation_rating_value

ROOT = Path(__file__).resolve().parents[1]


class DraftBoardTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.canonical = D.with_draft_context(load_app_canonical(ROOT))
        cls.team = cls.canonical["teams"][0]

    def test_board_payload_carries_no_hidden_ratings(self):
        for year in ("2027", "2030"):
            board = D.draft_board_report(self.canonical, self.team["abbrev"], year)
            scouting = S.class_scouting(self.canonical, year)
            truth = {pid: p for pid, p in scouting["prospects"].items()}
            hidden = 0
            for entry in board["entries"]:
                shown = entry["prospect"]
                true = truth[shown["id"]]
                consensus = scouting["consensus"][shown["id"]]
                self.assertEqual(shown["potential"], round(consensus["potential"], 2))
                self.assertEqual(shown["current_ability"], round(consensus["current"], 2))
                if abs(true["potential"] - D.prospect_evaluation_value(true, "potential")) > 1:
                    hidden += 1
                    self.assertNotEqual(shown["potential"], true["potential"])
            self.assertGreater(hidden, 20, year)

    def test_card_uses_the_scouting_report_even_at_full_coverage(self):
        prospect = next(p for p in self.canonical["draft_prospects"] if p.get("scouting_prior"))
        report = S.report_for(self.canonical, prospect, self.team["id"])
        projection = prospect_rating_projection(self.canonical, prospect, report, 100)
        self.assertEqual(projection["potential"], presentation_rating_value(report["estimated_potential"]["mid"]))
        self.assertNotEqual(projection["potential"], presentation_rating_value(prospect["potential"]))

    def test_scouts_board_is_talent_only(self):
        # Changing a team's phase and needs changes its GM's order, never its scouts' board.
        changed = deepcopy(self.canonical)
        for state in changed["team_strategic_states"]:
            state["phase"] = "contending" if state["phase"] != "contending" else "rebuilding"
            state["needs"] = ["shooting"]
        S.clear_cache()
        before = S.class_scouting(self.canonical, "2027", 4)["boards"]
        S.clear_cache()
        after = S.class_scouting(changed, "2027", 4)["boards"]
        self.assertEqual(before, after)

    def test_need_fit_never_reads_true_potential(self):
        prospect = next(p for p in self.canonical["draft_prospects"] if p.get("scouting_prior"))
        team = self.team["id"]
        moved = {**prospect, "id": prospect["id"] + "-copy", "potential": prospect["potential"] + 15}
        same = {**prospect, "id": prospect["id"] + "-same"}
        self.assertEqual(D.gm_need_fit(self.canonical, team, moved), D.gm_need_fit(self.canonical, team, same))

    def test_hidden_upside_tail_stays_hidden(self):
        prospect = next(p for p in S.class_scouting(self.canonical, "2030")["prospects"].values() if p.get("scouting_prior"))
        staff = S.staff_profile(self.canonical, self.team["id"])
        traits = {"shooting": 60.0, "athleticism": 55.0}
        tailed = {**prospect, "potential": prospect["potential"] + 12,
                  "scouting_prior": {**prospect["scouting_prior"], "latent_tail": prospect["scouting_prior"].get("latent_tail", 0) + 12}}
        for month in (0, 4, 8):
            a = S.team_report(prospect, traits, staff, self.team["id"], month, 7)
            b = S.team_report(tailed, traits, staff, self.team["id"], month, 7)
            self.assertEqual(a["estimated_potential"], b["estimated_potential"])

    def test_boards_move_more_early_than_late(self):
        early, late = [], []
        for team in self.canonical["teams"][:10]:
            ranks = [S.class_scouting(self.canonical, "2027", m)["ranks"][team["id"]] for m in range(9)]
            top = [pid for pid, rank in ranks[8].items() if rank <= 30]
            early += [abs(ranks[1][pid] - ranks[0][pid]) for pid in top]
            late += [abs(ranks[8][pid] - ranks[7][pid]) for pid in top]
        self.assertGreater(statistics.mean(early), statistics.mean(late))

    def test_coverage_grows_and_ranges_narrow_through_the_season(self):
        prospect = sorted(self.canonical["draft_prospects"], key=lambda p: p["rank"])[20]
        october = S.report_for(self.canonical, prospect, self.team["id"], month=0)
        june = S.report_for(self.canonical, prospect, self.team["id"], month=8)
        self.assertGreater(june["coverage"], october["coverage"])
        width = lambda r: r["estimated_potential"]["high"] - r["estimated_potential"]["low"]
        self.assertLess(width(june), width(october))

    def test_better_scouting_lead_sees_more_of_the_truth(self):
        def error(talent):
            canonical = deepcopy(self.canonical)
            for slot in canonical["gameplay_staff_slots"]:
                if slot["slot"] == "scouting_lead":
                    slot["skill_traits"] = dict.fromkeys(("talent_eval", "risk_modeling", "international_coverage"), talent)
            S.clear_cache()
            scouting = S.class_scouting(canonical, "2027", 8)
            misses = []
            for team_reports in scouting["reports"].values():
                for pid, report in team_reports.items():
                    p = scouting["prospects"][pid]
                    knowable = p["potential"] - (p.get("scouting_prior") or {}).get("latent_tail", 0.0)
                    misses.append(abs(report["estimated_potential"]["mid"] - knowable))
            return statistics.mean(misses)
        self.assertLess(error(85), error(50))

    def test_draft_is_deterministic_and_explained(self):
        first = D.simulate_draft(self.canonical, "2030", seed=11)
        second = D.simulate_draft(self.canonical, "2030", seed=11)
        self.assertEqual([s["prospect_id"] for s in first["selections"]], [s["prospect_id"] for s in second["selections"]])
        note = first["decisions"][0]["notes"]
        self.assertRegex(note, r"^[A-Z]{3} took .+ \(consensus #\d+, their board #\d+\): .+\.$")


if __name__ == "__main__":
    unittest.main()
