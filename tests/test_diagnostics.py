import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from nba_gm_data import app_actions, diagnostics


class DiagnosticsTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory(prefix="nba-diagnostics-")
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)

    def test_developer_version_is_allowlisted_without_paths_or_save_reads(self):
        (self.root / "pyproject.toml").write_text('[project]\nversion = "0.1.0"\n')
        saves = self.root / "saves"
        with patch.object(app_actions, "load_app_canonical", side_effect=AssertionError("must not load canonical")):
            report = app_actions.dispatch_app_action("diagnostic_runtime", {"save_path": "/private/secret.json", "session_token": "secret-token"}, root=self.root, save_dir=saves)
        self.assertFalse(saves.exists())
        self.assertEqual(report["version"], "0.1.0")
        self.assertEqual(set(report), {"version", "packaged", "os", "os_release", "architecture", "python", "protocol"})
        self.assertNotIn(str(self.root), json.dumps(report))
        self.assertNotIn("secret", json.dumps(report))

    def test_frozen_reports_exact_bundled_build_version_not_generic_bundle_number(self):
        (self.root / "build-manifest.json").write_text(json.dumps({"version": "0.1.0-beta.8", "input_sha256": {"/Users/secret": "secret-hash"}}))
        with patch.object(diagnostics.sys, "frozen", True, create=True):
            report = diagnostics.diagnostic_runtime(self.root)
        self.assertTrue(report["packaged"])
        self.assertEqual(report["version"], "0.1.0-beta.8")
        self.assertNotIn("secret", json.dumps(report))

    def test_missing_or_malformed_metadata_has_safe_fallback(self):
        for content in (None, "not toml [", '[project]\nversion = "/Users/private/secret"\n'):
            with self.subTest(content=content):
                if content is not None:
                    (self.root / "pyproject.toml").write_text(content)
                self.assertEqual(diagnostics.diagnostic_runtime(self.root)["version"], "unknown")

    def test_corrupt_or_missing_build_metadata_has_safe_fallback(self):
        with patch.object(diagnostics.sys, "frozen", True, create=True):
            for contents in (None, "corrupt", "[]"):
                with self.subTest(contents=contents):
                    if contents is not None:
                        (self.root / "build-manifest.json").write_text(contents)
                    self.assertEqual(diagnostics.diagnostic_runtime(self.root)["version"], "unknown")
