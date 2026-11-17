"""Check committed icon exports and the macOS packaging contract without graphics dependencies."""

import ast
from pathlib import Path
import struct
import unittest
import xml.etree.ElementTree as ET


ROOT = Path(__file__).resolve().parents[1]
ASSETS = ROOT / "packaging/assets"


class AppIconTests(unittest.TestCase):
    def test_editable_vector_has_accessible_name_and_master_dimensions(self):
        svg = ET.parse(ASSETS / "app-icon.svg").getroot()
        self.assertEqual(svg.attrib["viewBox"], "0 0 1024 1024")
        self.assertEqual(svg.find("{http://www.w3.org/2000/svg}title").text, "NBA GM Sandbox")

    def test_master_png_has_transparency_and_full_resolution(self):
        data = (ASSETS / "app-icon.png").read_bytes()
        self.assertEqual(data[:8], b"\x89PNG\r\n\x1a\n")
        width, height, depth, color = struct.unpack(">IIBB", data[16:26])
        self.assertEqual((width, height, depth, color), (1024, 1024, 8, 6))

    def test_mac_icon_container_has_retina_and_small_representations(self):
        data = (ASSETS / "app-icon.icns").read_bytes()
        self.assertEqual(data[:4], b"icns")
        self.assertEqual(struct.unpack(">I", data[4:8])[0], len(data))
        position = 8
        representations = set()
        while position < len(data):
            kind, length = struct.unpack(">4sI", data[position:position + 8])
            self.assertGreaterEqual(length, 8)
            self.assertLessEqual(position + length, len(data))
            representations.add(kind)
            position += length
        self.assertEqual(position, len(data))
        self.assertTrue({b"ic10", b"ic09", b"ic08", b"ic07", b"ic11", b"ic12"} <= representations)

    def test_bundle_uses_icon_and_manifest_tracks_it(self):
        spec = ast.parse((ROOT / "packaging/macos/NBA GM Sandbox.spec").read_text())
        bundle = next(node for node in ast.walk(spec)
                      if isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
                      and node.func.id == "BUNDLE")
        icon = next(keyword.value for keyword in bundle.keywords if keyword.arg == "icon")
        self.assertIn("packaging/assets/app-icon.icns", ast.unparse(icon))
        self.assertIn('REPO / "packaging/assets/app-icon.icns"',
                      (ROOT / "packaging/macos/build.py").read_text())


if __name__ == "__main__":
    unittest.main()
