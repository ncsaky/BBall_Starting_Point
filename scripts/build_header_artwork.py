"""Offline photo matting and original object art for compact game headers.

No generated people or generative image models. BiRefNet predicts foreground
masks only; closed-form matting follows the actual photographic boundaries.
"""
from pathlib import Path
import argparse
import hashlib
import subprocess

import numpy as np
from PIL import Image, ImageDraw, ImageFont

from build_dot_press import press

ROOT = Path(__file__).resolve().parents[1]
ART = ROOT / 'src/nba_gm_data/gui/assets/header-art'
WORK = ROOT / 'artifacts/header-art'


def commons_url(name):
    digest = hashlib.md5(name.encode()).hexdigest()
    return f'https://upload.wikimedia.org/wikipedia/commons/thumb/{digest[0]}/{digest[:2]}/{name}/960px-{name}'


PHOTOS = {
    'kawhi': 'https://a.espncdn.com/photo/2021/1004/r918170_1296x729_16-9.jpg',
    'kobe-portrait': 'https://www.highsnobiety.com/static-assets/dato/1673438017-kobe-hip-hop-lyrics.jpg',
    'popovich-arms': commons_url('Popovich_cross_armed.JPG'),
    'draft-night': 'https://www.basketshop.ru/files/photo_library/37652632/tild3333-3565-4730-a533-656533363266__2023-06-24_003824.jpg',
}

FRAMING = {'popovich-arms': (264, 74, 552, 563)}


def segment():
    from rembg import new_session
    from scipy.ndimage import binary_dilation, binary_erosion, label
    from pymatting import estimate_alpha_cf, estimate_foreground_ml
    session = new_session('birefnet-general-lite', providers=['CPUExecutionProvider'])
    for key in PHOTOS:
        photo = Image.open(ART / 'sources' / f'{key}.jpg').convert('RGB')
        if key in FRAMING:
            photo = photo.crop(FRAMING[key])
        prediction = session.predict(photo)[0].resize(photo.size, Image.Resampling.LANCZOS)
        selected = np.asarray(prediction) > 127
        # Discard only isolated background fragments, never the main silhouette.
        components, _ = label(selected)
        sizes = np.bincount(components.ravel())
        sizes[0] = 0
        selected &= sizes[components] > max(32, selected.sum()*.002)
        radius = max(1, round(photo.width/700))
        trimap = np.full(selected.shape, .5)
        trimap[~binary_dilation(selected, iterations=radius)] = 0
        trimap[binary_erosion(selected, iterations=radius)] = 1
        pixels = np.asarray(photo)/255.
        alpha = estimate_alpha_cf(pixels, trimap)
        alpha[alpha < .02] = 0
        alpha[alpha > .98] = 1
        foreground = estimate_foreground_ml(pixels, alpha)
        foreground[alpha == 1] = pixels[alpha == 1]
        foreground[alpha == 0] = 0
        result = Image.fromarray(np.uint8(np.clip(np.dstack([foreground, alpha])*255, 0, 255)))
        result.save(ART / 'cutouts' / f'{key}.png')
        print('Matted', key, flush=True)
    proof('cutouts')


def objects():
    ink, paper, shade = '#273540', '#d8e0e4', '#8b9aa4'
    image = Image.new('RGBA', (1024, 1024))
    pen = ImageDraw.Draw(image)
    pen.rounded_rectangle((233, 125, 791, 927), 28, fill=ink)
    pen.rounded_rectangle((263, 161, 761, 894), 12, fill=paper)
    pen.rounded_rectangle((376, 92, 648, 218), 22, fill=shade, outline=ink, width=15)
    pen.rounded_rectangle((448, 66, 576, 132), 18, fill=ink)
    pen.rectangle((297, 304, 727, 854), outline=shade, width=10)
    pen.rectangle((411, 304, 613, 475), outline=shade, width=9)
    pen.arc((326, 245, 698, 701), 0, 180, fill=shade, width=9)
    pen.arc((418, 741, 606, 931), 180, 360, fill=shade, width=9)
    for x, y in [(348, 438), (657, 545), (447, 751)]:
        pen.ellipse((x-23, y-23, x+23, y+23), outline=ink, width=12)
    for x, y in [(462, 554), (578, 687), (628, 376)]:
        pen.line((x-20, y-20, x+20, y+20), fill=ink, width=12)
        pen.line((x+20, y-20, x-20, y+20), fill=ink, width=12)
    pen.line([(372, 470), (389, 566), (351, 652)], fill=ink, width=12)
    pen.polygon([(351, 652), (344, 613), (377, 625)], fill=ink)
    pen.line([(476, 724), (507, 650), (548, 584)], fill=ink, width=12)
    pen.polygon([(548, 584), (516, 605), (550, 620)], fill=ink)
    image.save(ART / 'cutouts' / 'clipboard.png')

    image = Image.new('RGBA', (1024, 1024)); pen = ImageDraw.Draw(image)
    # Basketball trophy: broad metal stem, ball seams and a tiered plinth.
    pen.polygon([(444, 394), (574, 409), (590, 714), (702, 791), (326, 791), (435, 714)], fill=shade, outline=ink, width=16)
    pen.polygon([(483, 448), (534, 455), (553, 719), (483, 747)], fill=paper)
    pen.ellipse((282, 102, 740, 553), fill=paper, outline=ink, width=18)
    pen.arc((278, 170, 744, 502), 4, 172, fill=ink, width=16)
    pen.arc((252, 100, 705, 559), 287, 86, fill=ink, width=16)
    pen.arc((371, 98, 836, 558), 103, 246, fill=ink, width=16)
    pen.line((317, 447, 672, 166), fill=ink, width=14)
    pen.polygon([(304, 772), (720, 772), (759, 832), (265, 832)], fill=paper, outline=ink, width=16)
    pen.rectangle((264, 832, 760, 914), fill=shade, outline=ink, width=16)
    pen.rectangle((420, 850, 604, 894), fill=paper)
    image.save(ART / 'cutouts' / 'trophy.png')

    image = Image.new('RGBA', (1024, 1024)); pen = ImageDraw.Draw(image)
    def bundle(x, y):
        pen.polygon([(x,y), (x+312,y-77), (x+522,y+34), (x+208,y+115)], fill=paper, outline=ink, width=12)
        pen.polygon([(x,y), (x+208,y+115), (x+208,y+207), (x,y+88)], fill=shade, outline=ink, width=12)
        pen.polygon([(x+208,y+115), (x+522,y+34), (x+522,y+126), (x+208,y+207)], fill=paper, outline=ink, width=12)
        for dy in [29, 51, 72]:
            pen.line([(x+8,y+dy), (x+208,y+115+dy), (x+515,y+36+dy)], fill=shade, width=6)
        pen.polygon([(x+152,y-37), (x+228,y-55), (x+435,y+56), (x+360,y+76)], fill=shade, outline=ink, width=7)
        pen.polygon([(x+360,y+76), (x+435,y+56), (x+435,y+146), (x+360,y+167)], fill=shade, outline=ink, width=7)
        pen.ellipse((x+88,y-13,x+144,y+27), outline=ink, width=7)
    bundle(200, 631); bundle(371, 428); bundle(124, 347)
    image.save(ART / 'cutouts' / 'cash.png')

    image = Image.new('RGBA', (1024, 1024)); pen = ImageDraw.Draw(image)
    pen.ellipse((60, 143, 640, 723), outline=ink, width=42)
    pen.rounded_rectangle((267, 62, 441, 181), radius=28, fill=ink)
    pen.rounded_rectangle((499, 135, 598, 256), radius=20, fill=ink)
    pen.line((350, 433, 350, 250), fill=ink, width=36)
    pen.line((350, 433, 494, 520), fill=ink, width=36)
    pen.ellipse((313, 396, 387, 470), fill=ink)
    pen.ellipse((569, 449, 966, 846), fill=paper, outline=ink, width=28)
    pen.line((768, 520, 768, 775), fill=ink, width=80)
    pen.line((640, 647, 896, 647), fill=ink, width=80)
    image.save(ART / 'cutouts' / 'availability.png')


def export():
    subjects = [*PHOTOS, 'clipboard', 'trophy', 'cash', 'availability']
    sheet = Image.new('RGB', (250*len(subjects), 580), '#edf0f2')
    for i, key in enumerate(subjects):
        image = Image.open(ART / 'cutouts' / f'{key}.png').convert('RGBA')
        image = image.crop(image.getbbox())
        scale = min(880/image.width, 880/image.height)
        image = image.resize((round(image.width*scale), round(image.height*scale)), Image.Resampling.LANCZOS)
        photo = Image.new('RGBA', (1024, 1024))
        photo.alpha_composite(image, ((1024-image.width)//2, (1024-image.height)//2))
        for light, surface in [(True, 'silver'), (False, 'ink')]:
            if key == 'draft-night':
                artwork = press(photo, 3.2, light, dot_scale=0.36)
            else:
                artwork = press(photo, 5.2, light)
            artwork.save(ART / 'exports' / f'{key}-press-{surface}.png')
            preview = artwork.crop(artwork.getbbox())
            preview.thumbnail((224, 245), Image.Resampling.LANCZOS)
            row = 0 if light else 1
            panel = Image.new('RGB', (250, 290), '#edf0f2' if light else '#151b20')
            panel.paste(preview, ((250-preview.width)//2, (260-preview.height)//2), preview)
            ImageDraw.Draw(panel).text((12, 270), key, fill='#8294a0')
            sheet.paste(panel, (i*250, row*290))
    sheet.save(WORK / 'dot-press-proof.jpg', quality=96)


def fetch():
    for key, url in PHOTOS.items():
        target = ART / 'sources' / f'{key}.jpg'
        if not target.exists():
            subprocess.run(['curl', '-fL', '--max-time', '40', '-o', str(target), url], check=True)
        with Image.open(target) as image:
            print(key, image.size, flush=True)
    proof('sources', False)


def proof(folder, transparent=True):
    sheet = Image.new('RGB', (1600, 1000 if transparent else 520), '#edf0f2')
    font = ImageFont.truetype('/System/Library/Fonts/Supplemental/Arial.ttf', 18)
    for i, key in enumerate(PHOTOS):
        path = ART / folder / f'{key}.{"png" if transparent else "jpg"}'
        image = Image.open(path)
        if transparent:
            image = image.crop(image.getbbox())
        image.thumbnail((376, 452), Image.Resampling.LANCZOS)
        for row, color in enumerate(['#edf0f2', '#151b20'] if transparent else ['#edf0f2']):
            panel = Image.new('RGB', (400, 500), color)
            panel.paste(image, ((400-image.width)//2, (470-image.height)//2), image if transparent else None)
            ImageDraw.Draw(panel).text((16, 476), key, font=font, fill='#8294a0')
            sheet.paste(panel, (i*400, row*500))
    sheet.save(WORK / f'{folder}-proof.jpg', quality=96)


def main():
    for folder in ['sources', 'cutouts', 'exports']:
        (ART / folder).mkdir(parents=True, exist_ok=True)
    WORK.mkdir(parents=True, exist_ok=True)
    parser = argparse.ArgumentParser()
    parser.add_argument('--fetch', action='store_true')
    parser.add_argument('--segment', action='store_true')
    args = parser.parse_args()
    if args.fetch:
        fetch()
    elif args.segment:
        segment()
    else:
        objects()
        export()


if __name__ == '__main__':
    main()
