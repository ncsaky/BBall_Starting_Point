"""Local materialization must never publish partial or changed model inputs."""
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
sys.path.insert(0, str(SCRIPTS))
import local_market_audit as local
import overnight_market_health as audit


class LocalMarketAuditTests(unittest.TestCase):
    def test_copies_real_bytes_and_verifies_frozen_digest(self):
        with tempfile.TemporaryDirectory() as folder:
            source, target = Path(folder) / "source", Path(folder) / "local/input"
            data = b"verified local runtime\n" * 200
            source.write_bytes(data)
            expected = hashlib.sha256(data).hexdigest()
            report = local.materialize(source, target, expected)
            self.assertEqual(target.read_bytes(), data)
            self.assertEqual(report, {"sha256": expected, "bytes": len(data)})
            self.assertFalse(target.with_name(target.name + ".materializing").exists())

    def test_changed_input_is_not_published_or_silently_accepted(self):
        with tempfile.TemporaryDirectory() as folder:
            source, target = Path(folder) / "source", Path(folder) / "local/input"
            source.write_bytes(b"changed")
            with self.assertRaisesRegex(RuntimeError, "Frozen input mismatch"):
                local.materialize(source, target, "0" * 64)
            self.assertFalse(target.exists())

    def test_timeouts_are_bounded_and_do_not_publish_a_file(self):
        with tempfile.TemporaryDirectory() as folder:
            source, target = Path(folder) / "source", Path(folder) / "target"
            with patch.object(local.subprocess, "run", side_effect=subprocess.TimeoutExpired("copy", 1)) as run:
                with self.assertRaisesRegex(RuntimeError, "Cannot materialize required file"):
                    local.materialize(source, target, timeout=1, attempts=2)
            self.assertEqual(run.call_count, 2)
            self.assertFalse(target.exists())

    def test_strategy_text_is_part_of_the_frozen_inventory(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            path = root / "Pre-Season manifestos/UTA.txt"
            path.parent.mkdir()
            path.write_text("Strategy")
            with patch.object(audit, "ROOT", root):
                self.assertIn(path, audit.inputs())

    def test_cloud_read_guard_blocks_files_and_sqlite_but_allows_local_io(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            cloud, runtime = root / "cloud", root / "runtime"
            cloud.mkdir(); runtime.mkdir()
            (cloud / "input.txt").write_text("must not be read")
            (runtime / "local-runtime.json").write_text(json.dumps({"blocked_roots": [str(cloud)]}))
            code = '''
import pathlib,sqlite3,sys
from overnight_market_health import install_local_read_guard
runtime,cloud=map(pathlib.Path,sys.argv[1:3])
install_local_read_guard(runtime)
(runtime/'allowed.txt').write_text('local')
for action in (lambda:(cloud/'input.txt').read_text(),lambda:sqlite3.connect(str(cloud/'state.sqlite3'))):
    try:action()
    except PermissionError:pass
    else:raise AssertionError('Cloud read was not blocked')
assert (runtime/'allowed.txt').read_text()=='local'
'''
            result = subprocess.run([sys.executable, "-B", "-c", code, str(runtime), str(cloud)],
                                    env={**os.environ, "PYTHONPATH": f"{SCRIPTS}:{SCRIPTS.parent / 'src'}"},
                                    capture_output=True, text=True, timeout=20)
            self.assertEqual(result.returncode, 0, result.stderr)


if __name__ == "__main__":
    unittest.main()
