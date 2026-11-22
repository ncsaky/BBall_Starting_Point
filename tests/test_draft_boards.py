"""Draft boards (docs/agents/tasks/draft-boards-plan.md): consensus big board, each team's scouts' board (talent
only), a deterministic GM layer, and no hidden true ratings on screen before a prospect is signed."""
import statistics
import unittest
from copy import deepcopy
from pathlib import Path
from unittest.mock import patch

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

    def test_late_lottery_gm_uses_the_league_as_a_second_opinion(self):
        scouting = S.class_scouting(self.canonical, "2031", S.DRAFT_MONTH)
        team_id = self.team["id"]
        pid = max(scouting["reports"][team_id], key=lambda pid: abs(
            scouting["consensus"][pid]["grade"] - scouting["reports"][team_id][pid]["scouted_grade"]))
        team_grade = scouting["reports"][team_id][pid]["scouted_grade"]
        consensus_grade = scouting["consensus"][pid]["grade"]
        for slot in (5, 6, 14, 15, 35):
            with self.subTest(slot=slot):
                row = D.gm_rows(self.canonical, scouting, team_id, slot, [pid])[0]
                with patch.object(D, "GM_LOTTERY_CONSENSUS_SHARE", 0):
                    old = D.gm_rows(self.canonical, scouting, team_id, slot, [pid])[0]
                expected = D.GM_LOTTERY_CONSENSUS_SHARE * (consensus_grade - team_grade) if 6 <= slot <= 14 else 0
                self.assertAlmostEqual(row["score"] - old["score"], expected, places=3)
                self.assertEqual(row["scout_grade"], old["scout_grade"])

    def test_archived_board_uses_the_late_season_evidence(self):
        team_id = self.team["id"]
        year, seed = "2026", 2026
        context = {**self.canonical, "draft_classes": [{"season": year, "seed": seed}],
                   "draft_prospect_traits": [], "draft_prospects": [
                       {"id": "archive_a", "name": "Prospect A", "draft_year": year, "rank": 2,
                        "current_ability": 51, "potential": 76, "ceiling": 83, "floor": 41},
                       {"id": "archive_b", "name": "Prospect B", "draft_year": year, "rank": 12,
                        "current_ability": 61, "potential": 78, "ceiling": 83, "floor": 52},
                   ]}
        original = S.class_scouting(context, year, S.DRAFT_MONTH)
        archive = {**context, "draft_classes": [
            {**context["draft_classes"][0], "class_type": D.ARCHIVED_PUBLIC_CLASS_TYPE}
        ]}
        adjusted = S.class_scouting(archive, year, S.DRAFT_MONTH)
        self.assertEqual(original["prospects"], adjusted["prospects"])
        self.assertEqual(original["boards"][team_id][0], "archive_b")
        self.assertEqual(adjusted["boards"][team_id][0], "archive_a")
        for p in context["draft_prospects"]:
            standard = S.public_view(p, S.DRAFT_MONTH, seed)
            sourced = S.public_view(p, S.DRAFT_MONTH, seed, archived_board=True)
            self.assertLess(abs(sourced["delta"]), abs(standard["delta"]))

    def test_user_board_uses_the_same_grades_as_pick_selection(self):
        year = "2031"
        team_id = self.team["id"]
        board = D.draft_board_report(self.canonical, self.team["abbrev"], year, month=S.DRAFT_MONTH)
        scouting = S.class_scouting(self.canonical, year, S.DRAFT_MONTH)
        ids = [entry["prospect_id"] for entry in board["entries"]]
        gm_rows = D.gm_rows(self.canonical, scouting, team_id, 14, ids)
        gm_by_prospect = {row["prospect_id"]: row for row in gm_rows}
        for rank, entry in enumerate(board["entries"], 1):
            gm = gm_by_prospect[entry["prospect_id"]]
            self.assertEqual(entry["scout_grade"], gm["scout_grade"])
            self.assertEqual(entry["scout_rank"], gm["scout_rank"])
            self.assertEqual(entry["scout_rank"], rank)
        best = D.preferred_prospect_for_pick(self.canonical, year, team_id, 14,
                                             [scouting["prospects"][pid] for pid in ids], seed=17)
        self.assertEqual(best["id"], gm_rows[0]["prospect_id"])

    def test_different_staff_skills_with_same_overall_refresh_the_report(self):
        team_id = self.team["id"]
        slot = next(slot for slot in self.canonical["gameplay_staff_slots"]
                    if slot["team_id"] == team_id and slot["slot"] == "scouting_lead")

        def with_skills(talent, risk):
            updated = {**slot, "skill_traits": {"talent_eval": talent, "risk_modeling": risk,
                                               "international_coverage": 65}}
            slots = [updated if row is slot else row for row in self.canonical["gameplay_staff_slots"]]
            return {**self.canonical, "gameplay_staff_slots": slots}

        first = S.class_scouting(with_skills(65, 65), "2031", S.DRAFT_MONTH)
        second = S.class_scouting(with_skills(78.5, 36), "2031", S.DRAFT_MONTH)
        self.assertAlmostEqual(first["staffs"][team_id]["score"], second["staffs"][team_id]["score"])
        self.assertNotEqual(first["reports"][team_id], second["reports"][team_id])

    def test_draft_is_deterministic_and_explained(self):
        first = D.simulate_draft(self.canonical, "2030", seed=11)
        second = D.simulate_draft(self.canonical, "2030", seed=11)
        self.assertEqual([s["prospect_id"] for s in first["selections"]], [s["prospect_id"] for s in second["selections"]])
        note = first["decisions"][0]["notes"]
        self.assertRegex(note, r"^[A-Z]{3} took .+ \(consensus #\d+, their board #\d+\): .+\.$")


if __name__ == "__main__":
    unittest.main()
