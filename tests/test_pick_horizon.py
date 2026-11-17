import unittest

from nba_gm_data.transactions import ensure_future_second_round_scaffolds


class PickHorizonTests(unittest.TestCase):
    def test_extends_both_rounds_without_replacing_known_ownership(self):
        traded = {"id": "known", "season": "2033", "round": 1,
                  "original_team_id": "team_was", "current_owner_team_id": "team_bos",
                  "protection_summary": "top-5 protected"}
        canonical = {"meta": {"active_season": "2029-30"},
                     "teams": [{"id": "team_was", "abbrev": "WAS"},
                               {"id": "team_bos", "abbrev": "BOS"}],
                     "draft_picks": [traded.copy()]}
        ensure_future_second_round_scaffolds(canonical)
        self.assertEqual(canonical["draft_picks"][0], traded)
        for team in ("team_was", "team_bos"):
            for year in range(2034, 2037):
                for round_no in (1, 2):
                    rows = [p for p in canonical["draft_picks"] if p["original_team_id"] == team
                            and p["season"] == str(year) and p["round"] == round_no]
                    self.assertEqual(len(rows), 1)
                    self.assertEqual(rows[0]["current_owner_team_id"], team)
        before = list(canonical["draft_picks"])
        ensure_future_second_round_scaffolds(canonical)
        self.assertEqual(canonical["draft_picks"], before)


if __name__ == "__main__":
    unittest.main()
