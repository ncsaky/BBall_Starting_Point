import io
import json
from contextlib import redirect_stdout
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import cleanup_disposable_saves as cleanup


class DisposableSaveCleanupTests(unittest.TestCase):
    def test_live_save_ancestors_and_outside_paths_are_protected(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder); output = root / "output"; output.mkdir()
            live = output / "preview/saves"
            with patch.object(cleanup, "OUTPUT", output):
                self.assertTrue(cleanup.protected(root / "personal", [live]))
                self.assertTrue(cleanup.protected(live, [live]))
                self.assertTrue(cleanup.protected(live.parent, [live]))
                self.assertTrue(cleanup.protected(live / "game.json", [live]))
                self.assertFalse(cleanup.protected(output / "old/saves", [live]))

    def test_apply_removes_old_saves_but_not_assets_reports_or_live_saves(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder); output = root / "output"; output.mkdir()
            old = output / "old/saves"; old.mkdir(parents=True)
            (old / "career.json").write_text('{"version":"league_save_v1"}')
            live = output / "preview/saves"; live.mkdir(parents=True)
            (live / "game.json").write_text('{"version":"league_save_v1"}')
            assets = output / "old/assets"; assets.mkdir()
            (assets / "video.mp4").write_bytes(b"asset")
            report = output / "old/report.json"; report.write_text('{"status":"passed"}')
            history = output / "old/disposable.history.sqlite3"; history.write_bytes(b"old history")
            fixture = output / "original.nbagm.zip"; fixture.write_bytes(b"kept fixture")
            manifest = output / "cleanup/manifest.json"
            with patch.object(cleanup, "ROOT", root), patch.object(cleanup, "OUTPUT", output), \
                 patch.object(cleanup, "REPORT", manifest), patch.object(cleanup, "PRESERVED_FIXTURE", fixture), \
                 patch.object(cleanup, "live_save_directories", return_value=[live]), \
                 patch.object(sys, "argv", ["cleanup", "--apply"]), redirect_stdout(io.StringIO()):
                cleanup.main()
            self.assertFalse(old.exists()); self.assertFalse(history.exists())
            self.assertTrue((live / "game.json").exists())
            self.assertEqual((assets / "video.mp4").read_bytes(), b"asset")
            self.assertTrue(report.exists()); self.assertTrue(fixture.exists())
            self.assertTrue(all(row["removed"] for row in json.loads(manifest.read_text())["targets"]))

    def test_symlink_to_an_active_save_is_not_a_cleanup_target(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder); output = root / "output"; output.mkdir()
            external = root / "live"; external.mkdir()
            link = output / "saves"; link.symlink_to(external, target_is_directory=True)
            with patch.object(cleanup, "OUTPUT", output):
                self.assertTrue(cleanup.protected(link, []))


if __name__ == "__main__":
    unittest.main()
