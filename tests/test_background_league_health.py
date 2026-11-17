import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))

from background_league_health import descendants_rss, stop_reason


class BackgroundHealthTests(unittest.TestCase):
    def test_memory_includes_worker_descendants_but_not_other_apps(self):
        rows = [(1, 0, 999999), (20, 1, 1024), (21, 20, 2048), (22, 21, 3072), (30, 1, 999999)]
        self.assertEqual(descendants_rss(rows, [20]), 6)
        self.assertEqual(descendants_rss(rows, [20, 21]), 6)
        self.assertEqual(descendants_rss(rows, []), 0)

    def test_bounded_time_disk_and_memory_without_tuning(self):
        plenty = 20 * 1024 ** 3
        self.assertIsNone(stop_reason(30, 12, plenty, 3000))
        self.assertEqual(stop_reason(12 * 3600, 12, plenty, 3000), "time_limit")
        self.assertEqual(stop_reason(30, 12, 4 * 1024 ** 3, 3000), "disk_below_5_gib")
        self.assertEqual(stop_reason(30, 12, plenty, 6145), "workers_above_6_gib")


if __name__ == "__main__":
    unittest.main()
