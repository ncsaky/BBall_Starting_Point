"""Offline asset regression checks. Run after build_dot_press.py."""
import unittest
import zipfile

import numpy as np
from PIL import Image

from build_dot_press import ASSETS, MASKS, ROOT


class CutoutTests(unittest.TestCase):
    def test_source_resolution_and_transparency(self):
        for key, spec in MASKS.items():
            with self.subTest(subject=key):
                image = Image.open(ASSETS/'cutouts'/f'{key}.png')
                self.assertEqual(image.mode, 'RGBA')
                with Image.open(ASSETS/'sources'/spec['file']) as source:
                    self.assertEqual(image.size, source.size)
                rgba = np.asarray(image)
                alpha = rgba[:, :, 3]
                self.assertEqual(int(alpha[0].max()), 0)
                self.assertEqual(int(alpha[-1].max()), 0)
                self.assertEqual(int(alpha[:, 0].max()), 0)
                self.assertEqual(int(alpha[:, -1].max()), 0)
                self.assertFalse(np.any(rgba[:, :, :3][alpha == 0]))
                self.assertGreater(np.sum((alpha > 0) & (alpha < 255)), 100)

    def test_overlap_cleanup_preserves_subject(self):
        landmarks = {
            'curry': {
                'foreground': [(235, 500), (220, 85), (266, 343), (228, 638)],
                'background': [(205, 180), (251, 534), (302, 547), (245, 227)],
            },
            'rodman-detroit': {
                'foreground': [(545, 167), (319, 605), (435, 467), (679, 465), (663, 484)],
                'background': [(405, 470), (492, 420), (639, 430), (324, 584)],
            },
            'rodman-chicago': {
                'foreground': [(355, 482), (384, 425), (500, 210), (350, 558)],
                'background': [(392, 448), (358, 390), (381, 489), (420, 367), (373, 480), (371, 490)],
            },
            'allen': {
                'foreground': [(648, 440), (690, 1570), (620, 550), (640, 880)],
                'background': [(648, 1575), (622, 1360), (714, 1602)],
            },
        }
        for key, checks in landmarks.items():
            alpha = Image.open(ASSETS/'cutouts'/f'{key}.png').getchannel('A')
            sx, sy = alpha.width/MASKS[key]['ref'][0], alpha.height/MASKS[key]['ref'][1]
            for kind, points in checks.items():
                for x, y in points:
                    with self.subTest(subject=key, kind=kind, point=(x, y)):
                        value = alpha.getpixel((round(x*sx), round(y*sy)))
                        if kind == 'foreground':
                            self.assertGreater(value, 240)
                        else:
                            self.assertLess(value, 8)

    def test_exports_and_preserved_tools(self):
        exports = list((ASSETS/'exports').glob('*.png'))
        self.assertEqual(len(exports), 42)
        for path in exports:
            with self.subTest(asset=path.name):
                image = Image.open(path)
                self.assertEqual((image.mode, image.size), ('RGBA', (1024, 1024)))
                self.assertEqual(image.getchannel('A').getextrema(), (0, 255))
                if path.stem.startswith(('builder-', 'finder-')):
                    before = ROOT/'artifacts/dot-press/edge-refinement/before'/path.name
                    if before.exists():
                        self.assertEqual(path.read_bytes(), before.read_bytes())
        with zipfile.ZipFile(ASSETS/'dot-press-review.zip') as archive:
            for path in exports:
                self.assertEqual(archive.read('exports/'+path.name), path.read_bytes())


if __name__ == '__main__':
    unittest.main()
