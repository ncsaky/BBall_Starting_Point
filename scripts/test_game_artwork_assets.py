"""Approved subjects, lossless dot preservation, and installed-package coverage."""
import json
import tomllib
import unittest

from PIL import Image

from build_game_artwork import APPROVED, OUTPUT, ROOT, source_folder


class GameArtworkTests(unittest.TestCase):
    def test_approved_subjects_only(self):
        manifest=json.loads((OUTPUT/'manifest.json').read_text())
        self.assertEqual({row['category']:row['subject'] for row in manifest}, APPROVED)
        self.assertEqual(len(list(OUTPUT.glob('*.webp'))), 2*len(APPROVED))

    def test_packaged_images_preserve_approved_pixels(self):
        for row in json.loads((OUTPUT/'manifest.json').read_text()):
            for surface in ['silver', 'ink']:
                with self.subTest(category=row['category'],surface=surface):
                    with Image.open(source_folder(row['category'])/f"{row['subject']}-press-{surface}.png") as source:
                        expected=source.crop(row['crop'])
                    with Image.open(OUTPUT/f"{row['category']}-{surface}.webp") as output:
                        self.assertEqual(output.mode, 'RGBA')
                        self.assertEqual(list(output.size), row['size'])
                        # Transparent RGB is immaterial; compare composited pixels on
                        # both backgrounds to include antialiasing and alpha coverage.
                        for color in ['white', 'black']:
                            a=Image.new('RGBA',output.size,color)
                            b=a.copy()
                            a.alpha_composite(expected)
                            b.alpha_composite(output)
                            self.assertEqual(a.tobytes(),b.tobytes())

    def test_installed_package_contains_art_and_credits(self):
        config=tomllib.loads((ROOT/'pyproject.toml').read_text())
        globs=config['tool']['setuptools']['package-data']['nba_gm_data']
        files=[*OUTPUT.iterdir(),ROOT/'src/nba_gm_data/gui/assets/dot-press/ATTRIBUTION.md']
        for path in files:
            with self.subTest(file=path.name):
                relative=path.relative_to(ROOT/'src/nba_gm_data')
                self.assertTrue(any(relative.match(pattern) for pattern in globs))


if __name__=='__main__':
    unittest.main()
