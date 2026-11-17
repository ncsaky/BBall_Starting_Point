import argparse
import ast
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

from scripts import overnight_balance_comparison as audit


class OvernightBalanceComparisonTests(unittest.TestCase):
    def test_control_replaces_only_monthly_function_and_rejects_helper_drift(self):
        original = 'import math\n\ndef helper(x):\n    return x\n\ndef monthly_trait_delta(x):\n    return x + 1\n'
        current = original.replace('return x + 1','return x + 2')
        self.assertEqual(ast.dump(ast.parse(audit.control_health(current,original))),ast.dump(ast.parse(original)))
        with self.assertRaises(AssertionError):
            audit.control_health(current.replace('return x\n','return x * 2\n'),original)

    def test_progress_reads_only_small_atomic_checkpoint_report(self):
        with TemporaryDirectory() as directory:
            root = Path(directory)
            self.assertEqual(audit.progress(root,'control',29)['actions'],0)
            path = root/'control/runtime/output/balance/career-29/run.json'
            audit.write(path,{'endpoint':'2028-10-01','complete_seasons':2,'actions':[{},{}],
                              'target':'2034-10-01','status':'running'})
            self.assertEqual(audit.progress(root,'control',29)['complete_seasons'],2)
            self.assertEqual(audit.progress(root,'control',29)['actions'],2)
            self.assertFalse(path.with_name(path.name+'.tmp').exists())

    def test_worker_command_points_inside_the_selected_frozen_arm(self):
        runtime,command = audit.worker_command(Path('/isolated/batch'),'tuned',913,1)
        self.assertEqual(runtime,Path('/isolated/batch/tuned/runtime'))
        self.assertIn(str(runtime/'scripts/overnight_balance_comparison.py'),command)
        self.assertEqual(command[-4:],['--seed','913','--short-days','1'])

    def test_worker_refuses_source_workspace(self):
        with patch.object(audit,'ROOT',Path('/workspace')):
            with self.assertRaises(RuntimeError):
                audit.step(argparse.Namespace(batch=Path('/isolated'),seed=29,short_days=1))


if __name__ == '__main__':
    unittest.main()
