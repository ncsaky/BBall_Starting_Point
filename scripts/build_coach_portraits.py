"""Split and recolor the original fictional coach-portrait sheet."""
from pathlib import Path
import json

import numpy as np
from PIL import Image


ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "src/nba_gm_data/gui/assets/header-art/sources/coach-portraits-sheet.png"
OUTPUT = ROOT / "src/nba_gm_data/gui/assets/game-art/coaches"
SIZE = 512
COACHES = [f"coach-{index:02d}" for index in range(1, 7)]
SURFACES = {
    "silver": ((28, 41, 50), (218, 228, 234)),
    "ink": ((218, 228, 234), (28, 41, 50)),
}


def recolor(image: Image.Image, shadow: tuple[int, ...], highlight: tuple[int, ...]) -> Image.Image:
    rgba = np.asarray(image.convert("RGBA")).copy()
    alpha = rgba[:, :, 3]
    alpha[alpha < 14] = 0
    luminance = np.asarray(image.convert("L"), dtype=np.float32) / 255.0
    tones = np.clip((luminance - 0.06) / 0.9, 0, 1)[:, :, None]
    dark = np.asarray(shadow, dtype=np.float32)
    light = np.asarray(highlight, dtype=np.float32)
    rgb = dark + (light - dark) * tones
    rgba[:, :, :3] = np.uint8(np.round(rgb))
    rgba[:, :, 3] = alpha
    return Image.fromarray(rgba)


def main() -> None:
    sheet = Image.open(SOURCE).convert("RGBA")
    if sheet.width % 3 or sheet.height % 2:
        raise ValueError(f"Portrait sheet must divide evenly into 3x2 cells: {sheet.size}")
    cell_width, cell_height = sheet.width // 3, sheet.height // 2
    OUTPUT.mkdir(parents=True, exist_ok=True)
    manifest = []
    for index, coach_id in enumerate(COACHES):
        column, row = index % 3, index // 3
        cell = sheet.crop((column * cell_width, row * cell_height, (column + 1) * cell_width, (row + 1) * cell_height))
        alpha = cell.getchannel("A").point(lambda value: 0 if value < 14 else value)
        bounds = alpha.getbbox()
        if not bounds:
            raise ValueError(f"No portrait found in sprite cell {index + 1}")
        figure = cell.crop(bounds)
        fit = min((SIZE - 28) / figure.width, (SIZE - 36) / figure.height)
        figure = figure.resize((round(figure.width * fit), round(figure.height * fit)), Image.Resampling.LANCZOS)
        normalized = Image.new("RGBA", (SIZE, SIZE))
        normalized.alpha_composite(figure, ((SIZE - figure.width) // 2, SIZE - figure.height - 14))
        for surface, (shadow, highlight) in SURFACES.items():
            recolor(normalized, shadow, highlight).save(OUTPUT / f"{coach_id}-{surface}.webp", lossless=True)
        manifest.append({"id": coach_id, "source_cell": index + 1, "size": [SIZE, SIZE]})
    (OUTPUT / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")


if __name__ == "__main__":
    main()
