"""Builder-only tests, run with the pinned packaging environment."""

import importlib.util
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("macos_build", ROOT / "packaging/macos/build.py")
build = importlib.util.module_from_spec(spec)
try:
    spec.loader.exec_module(build)
except ModuleNotFoundError as exc:
    raise unittest.SkipTest("Requires the packaging build environment") from exc


class MacArchitecturesTests(unittest.TestCase):
    def binary(self, cpu, minimum=0x000b0000, dependency="/usr/lib/libSystem.B.dylib"):
        header = SimpleNamespace(header=SimpleNamespace(cputype=cpu),
                                 commands=[(SimpleNamespace(cmd=build.LC_BUILD_VERSION),
                                            SimpleNamespace(minos=minimum), b"")],
                                 walkRelocatables=lambda: [(0, 0, dependency)])
        return SimpleNamespace(headers=[header])

    def audit(self, architecture, binary):
        with tempfile.TemporaryDirectory() as directory:
            app = Path(directory)
            (app / "executable").write_bytes(b"\xcf\xfa\xed\xfe")
            with patch.object(build, "MachO", return_value=binary):
                return build.audit_binaries(app, architecture)

    def test_each_architecture_is_accepted_with_matching_binaries(self):
        for architecture, cpu in build.ARCHITECTURES.items():
            with self.subTest(architecture=architecture):
                result = self.audit(architecture, self.binary(cpu))
                self.assertEqual(result["architecture"], architecture)
                self.assertEqual(result["mach_o_count"], 1)
                self.assertEqual(result["maximum_binary_minimum_macos"], "11.0.0")

    def test_mixed_architecture_fails_in_both_directions(self):
        for architecture, wrong in [("arm64", "x86_64"), ("x86_64", "arm64")]:
            with self.subTest(architecture=architecture), self.assertRaisesRegex(RuntimeError, "Unexpected non-"):
                self.audit(architecture, self.binary(build.ARCHITECTURES[wrong]))

    def test_unsupported_os_and_external_dependencies_are_rejected(self):
        cpu = build.ARCHITECTURES["x86_64"]
        with self.assertRaisesRegex(RuntimeError, "requires macOS"):
            self.audit("x86_64", self.binary(cpu, minimum=0x000c0000))
        with self.assertRaisesRegex(RuntimeError, "Unbundled binary dependency"):
            self.audit("x86_64", self.binary(cpu, dependency="/opt/homebrew/lib/something.dylib"))

    def test_empty_application_fails(self):
        with tempfile.TemporaryDirectory() as directory, self.assertRaisesRegex(RuntimeError, "no Mach-O"):
            build.audit_binaries(Path(directory), "x86_64")


if __name__ == "__main__":
    unittest.main()
