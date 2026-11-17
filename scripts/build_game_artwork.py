"""Losslessly package the approved and newly commissioned header artwork."""
from pathlib import Path
import json

from PIL import Image


ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / 'src/nba_gm_data/gui/assets/dot-press/exports'
OUTPUT = ROOT / 'src/nba_gm_data/gui/assets/game-art'
HEADER_SOURCE = ROOT / 'src/nba_gm_data/gui/assets/header-art/exports'
APPROVED = {'shooting': 'curry', 'rebounding': 'rodman-chicago',
            'trade-builder': 'builder', 'trade-finder': 'finder',
            'defense': 'kawhi', 'mentality': 'kobe-portrait',
            'coach': 'popovich-arms', 'prospects': 'draft-night',
            'staff': 'clipboard', 'awards': 'trophy', 'payroll': 'cash',
            'availability': 'availability'}


def source_folder(category):
    return SOURCE if category in {'shooting', 'rebounding', 'trade-builder', 'trade-finder'} else HEADER_SOURCE


def main():
    OUTPUT.mkdir(parents=True, exist_ok=True)
    manifest = []
    for category, subject in APPROVED.items():
        source = source_folder(category)
        # Crop transparent canvas only; preserve the approved dots and fine matte.
        with Image.open(source / f'{subject}-press-silver.png') as reference:
            x0, y0, x1, y1 = reference.getbbox()
            bounds = (max(0, x0-8), max(0, y0-8), min(1024, x1+8), min(1024, y1+8))
        for surface in ['silver', 'ink']:
            with Image.open(source / f'{subject}-press-{surface}.png') as image:
                image.crop(bounds).save(OUTPUT / f'{category}-{surface}.webp', lossless=True)
        manifest.append({'category': category, 'subject': subject,
                         'crop': bounds, 'size': [bounds[2]-bounds[0], bounds[3]-bounds[1]]})
    (OUTPUT / 'manifest.json').write_text(json.dumps(manifest, indent=2) + '\n')
    print(json.dumps(manifest))


if __name__ == '__main__':
    main()
