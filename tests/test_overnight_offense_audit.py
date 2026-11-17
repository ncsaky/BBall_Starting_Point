from copy import deepcopy
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from overnight_offense_audit import SEEDS, TARGET, career_progress, season_metrics, valid_run, write


class OvernightOffenseAuditTests(unittest.TestCase):
    def test_only_two_seeds_and_one_completed_season_are_approved(self):
        self.assertEqual(SEEDS, (29, 913))
        self.assertEqual(TARGET, '2027-10-01')
        valid_run({'target': TARGET, 'target_seasons': 1, 'endpoint': '2026-11-01', 'complete_seasons': 0, 'status': 'running'})
        valid_run({'target': TARGET, 'target_seasons': 1, 'endpoint': TARGET, 'complete_seasons': 1, 'status': 'completed'})
        for update in ({'target': '2036-10-01'}, {'target_seasons': 10}, {'complete_seasons': 2},
                       {'endpoint': '2027-10-02'}, {'endpoint': '2027-06-01', 'status': 'completed'},
                       {'complete_seasons': 0, 'status': 'completed'}):
            run = {'target': TARGET, 'target_seasons': 1, 'endpoint': TARGET, 'complete_seasons': 1, 'status': 'running'}
            run.update(update)
            with self.assertRaises(RuntimeError):
                valid_run(run)

    def test_metrics_use_weighted_totals_not_averages_of_percentages(self):
        records = {str(i): {'wins': 41, 'losses': 41} for i in range(30)}
        stats = {'p': {'games': 60, 'minutes': 900, 'points': 600, 'fgm': 200, 'fga': 400, 'fg3a': 0},
                 'q': {'games': 60, 'minutes': 1800, 'points': 300, 'fgm': 100, 'fga': 400, 'fg3a': 20}}
        before = deepcopy(stats)
        result = season_metrics(stats, records, {'p': {'name': 'P'}, 'q': {'name': 'Q'}}, {'p': 'bigs', 'q': 'bigs'})
        self.assertEqual(result['league_games'], 1230)
        self.assertEqual(result['fg_pct'], .375)
        self.assertEqual(result['groups']['bigs']['per36']['points'], 12)
        self.assertEqual(result['groups']['bigs']['players_300_minutes'], 2)
        self.assertEqual(stats, before)

    def test_tiny_minute_samples_stay_visible_but_do_not_define_cohort_rates(self):
        records = {str(i): {'wins': 41, 'losses': 41} for i in range(30)}
        stats = {'p': {'games': 1, 'minutes': 2, 'points': 10, 'fgm': 4, 'fga': 4}}
        result = season_metrics(stats, records, {'p': {'name': 'Small sample'}}, {'p': 'bigs'})
        self.assertEqual(len(result['players']), 1)
        self.assertEqual(result['groups']['bigs']['players_300_minutes'], 0)
        self.assertIsNone(result['groups']['bigs']['per36']['points'])

    def test_incomplete_seasons_cannot_produce_final_comparison(self):
        for records in ({'one': {'wins': 41, 'losses': 41}},
                        {str(i): {'wins': 40, 'losses': 41} for i in range(30)}):
            with self.assertRaises(ValueError):
                season_metrics({}, records, {}, {})

    def test_progress_reads_actual_checkpoint_and_missing_jobs_are_queued(self):
        with TemporaryDirectory() as tmp:
            batch = Path(tmp)
            self.assertEqual(career_progress(batch, 29)['status'], 'queued')
            path = batch/'runtime/output/offense-season/career-29/run.json'
            write(path, {'endpoint': '2027-02-05', 'complete_seasons': 0, 'status': 'running', 'actions': [{}, {}]})
            result = career_progress(batch, 29)
            self.assertEqual(result['date'], '2027-02-05')
            self.assertEqual(result['actions'], 2)
            self.assertEqual(result['complete_seasons'], 0)
            self.assertFalse(path.with_name(path.name+'.tmp').exists())


if __name__ == '__main__':
    unittest.main()
