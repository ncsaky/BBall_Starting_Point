"""Build the save-screen's real-photo, dot-press player cutouts.

Requires Pillow, NumPy, OpenCV, and ONNX Runtime. The BiRefNet model is cached
outside the repository; only the processed, attributed artwork is shipped.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
from urllib.request import urlretrieve

import cv2
import numpy as np
import onnxruntime as ort
from PIL import Image, ImageDraw, ImageFilter

from build_dot_press import press

ROOT = Path(__file__).resolve().parents[1]
ASSETS = ROOT / "src/nba_gm_data/gui/assets/startup"
SOURCES = ASSETS / "sources"
OUTPUT = ASSETS / "press"
MODEL = Path.home() / ".cache/nba-gm-artwork/birefnet-general-lite.onnx"
MODEL_URL = (
    "https://github.com/danielgatis/rembg/releases/download/v0.0.0/"
    "BiRefNet-general-bb_swin_v1_tiny-epoch_232.onnx"
)
MODEL_MD5 = "4fab47adc4ff364be1713e97b7e66334"
SIZE = 1024

# Keep the complete on-court action group, not only one selected athlete.
PHOTOS = [
    {"id": "iguodala", "file": "iguodala-dunk.jpg", "path": ASSETS / "iguodala-dunk.jpg"},
    {"id": "carmelo-anthony", "file": "carmelo-anthony-jump-shot.jpg"},
    {"id": "james-worthy", "file": "james-worthy-layup.jpg"},
    {"id": "kobe-bryant", "file": "kobe-bryant-dunk.jpg"},
    {"id": "kobe-bryant-layup", "file": "kobe-bryant-layup.jpg"},
    {
        "id": "larry-sanders",
        "file": "larry-sanders-dunk.jpg",
        # The ball touches the jersey and is merged into the background by
        # automatic segmentation; preserve its photographed circular outline.
        "balls": [(488, 1228, 109, 108)],
    },
    {"id": "lebron-james", "file": "lebron-james-dunk.jpg"},
    {"id": "pau-gasol", "file": "pau-gasol-dunk.jpg"},
    {"id": "giannis-antetokounmpo", "file": "giannis-dunk.jpg"},
    {"id": "bradley-beal", "file": "bradley-beal-dunk.jpg"},
    {
        "id": "curry-thunder-wide",
        "file": "mixcollage-11-aug-2024-03-42-pm-9270.jpg",
        "path": SOURCES / "supplied/mixcollage-11-aug-2024-03-42-pm-9270.jpg",
        "details": [((0.103, 0.26), (0.151, 0.26), (0.155, 0.37), (0.132, 0.40), (0.11, 0.37))],
    },
    {"id": "thunder-team-celebration", "file": "images.jpg", "path": SOURCES / "supplied/images.jpg"},
    {
        "id": "shai-vs-rockets",
        "file": "1-GettyImages-2036341157.webp",
        "path": SOURCES / "supplied/1-GettyImages-2036341157.webp",
        "details": [((0.245, 0.08), (0.355, 0.08), (0.36, 0.245), (0.30, 0.28), (0.25, 0.24))],
    },
    {
        "id": "thunder-bucks-action",
        "file": "6-241217_JIMMYDO_OKCMIL_0137.webp",
        "path": SOURCES / "supplied/6-241217_JIMMYDO_OKCMIL_0137.webp",
        "details": [((0.45, 0.20), (0.57, 0.20), (0.59, 0.35), (0.51, 0.39), (0.46, 0.35))],
    },
    {
        "id": "thunder-paint-action", "file": "images-1.jpg", "path": SOURCES / "supplied/images-1.jpg",
        "details": [((0.53, 0.16), (0.65, 0.16), (0.66, 0.33), (0.59, 0.37), (0.54, 0.33))],
    },
    {
        "id": "curry-team-moment",
        "file": "merlin_195945042_866c81c5-2517-4be5-b104-393f742442be-superJumbo.webp",
        "path": SOURCES / "supplied/merlin_195945042_866c81c5-2517-4be5-b104-393f742442be-superJumbo.webp",
        "details": [((0.42, 0.015), (0.54, 0.015), (0.55, 0.13), (0.48, 0.17), (0.43, 0.13))],
    },
    {"id": "lebron-edwards-postgame", "file": "17331906740012.jpg", "path": SOURCES / "supplied/17331906740012.jpg"},
    {
        "id": "lebron-edwards-drive",
        "file": "ee0a010d226d2f144f3f620fd5440e1c7e10766afe1fa2b40297f8c8f5f42b8e.jpg",
        "path": SOURCES / "supplied/ee0a010d226d2f144f3f620fd5440e1c7e10766afe1fa2b40297f8c8f5f42b8e.jpg",
    },
    {
        "id": "lebron-edwards-matchup",
        "file": "LeBron-James-Anthony-Edwards-2.jpg",
        "path": SOURCES / "supplied/LeBron-James-Anthony-Edwards-2.jpg",
    },
    {
        "id": "lebron-wade-team-usa", "file": "images-3.jpg", "path": SOURCES / "supplied/images-3.jpg",
        "details": [((0.90, 0.27), (0.999, 0.27), (0.999, 0.42), (0.91, 0.42))],
    },
]


def ensure_model() -> Path:
    if not MODEL.exists():
        MODEL.parent.mkdir(parents=True, exist_ok=True)
        urlretrieve(MODEL_URL, MODEL)
    digest = hashlib.md5(MODEL.read_bytes()).hexdigest()
    if digest != MODEL_MD5:
        raise ValueError(f"Unexpected BiRefNet model checksum: {digest}")
    return MODEL


def make_mask(
    photo: Image.Image,
    session: ort.InferenceSession,
    balls: tuple[tuple[int, int, int, int], ...] = (),
    details: tuple[tuple[tuple[float, float], ...], ...] = (),
) -> Image.Image:
    input_image = photo.resize((SIZE, SIZE), Image.Resampling.LANCZOS)
    pixels = np.asarray(input_image, dtype=np.float32) / 255
    pixels = (pixels - np.array([0.485, 0.456, 0.406], np.float32)) / np.array(
        [0.229, 0.224, 0.225], np.float32
    )
    tensor = np.transpose(pixels, (2, 0, 1))[None]
    logits = session.run(None, {"input_image": tensor})[0][0, 0]
    probability = 1 / (1 + np.exp(-np.clip(logits, -40, 40)))
    probability = np.asarray(
        Image.fromarray(probability.astype(np.float32), mode="F").resize(
            photo.size, Image.Resampling.BILINEAR
        ),
        dtype=np.float32,
    )

    binary = (probability > 0.5).astype(np.uint8)
    count, labels, stats, _ = cv2.connectedComponentsWithStats(binary, connectivity=8)
    # Retain complete foreground players and salient ball components, while
    # dropping tiny specks from the crowd and arena lights.
    min_area = max(80, round(photo.width * photo.height * 0.00025))
    subject = np.zeros(binary.shape, dtype=bool)
    for component in range(1, count):
        if int(stats[component, cv2.CC_STAT_AREA]) >= min_area:
            subject |= labels == component

    soft = Image.fromarray((probability * 255).clip(0, 255).astype(np.uint8))
    kept = np.where(subject, np.asarray(soft), 0).astype(np.uint8)
    if details:
        detail_regions = Image.new("L", photo.size)
        detail_draw = ImageDraw.Draw(detail_regions)
        for points in details:
            detail_draw.polygon(
                [(round(x * (photo.width - 1)), round(y * (photo.height - 1))) for x, y in points],
                fill=255,
            )
        luminance = np.asarray(photo.convert("L"))
        preserved = (np.asarray(detail_regions) > 0) & (luminance > 105)
        kept = np.maximum(kept, preserved.astype(np.uint8) * 255)
    if balls:
        ball_mask = Image.new("L", photo.size)
        draw = ImageDraw.Draw(ball_mask)
        for center_x, center_y, radius_x, radius_y in balls:
            draw.ellipse(
                (
                    center_x - radius_x,
                    center_y - radius_y,
                    center_x + radius_x,
                    center_y + radius_y,
                ),
                fill=255,
            )
        ball_mask = ball_mask.filter(ImageFilter.GaussianBlur(0.7))
        kept = np.maximum(kept, np.asarray(ball_mask))
    mask = Image.fromarray(kept).filter(ImageFilter.GaussianBlur(0.65))
    return mask


def normalize(photo: Image.Image, mask: Image.Image) -> Image.Image:
    rgba = photo.convert("RGBA")
    rgba.putalpha(mask)
    bounds = mask.getbbox()
    if not bounds:
        raise ValueError("Foreground segmentation returned an empty cutout")
    left, top, right, bottom = bounds
    margin = max(10, round(max(photo.size) * 0.012))
    bounds = (
        max(0, left - margin), max(0, top - margin),
        min(photo.width, right + margin), min(photo.height, bottom + margin),
    )
    cutout = rgba.crop(bounds)
    # Match visual player height across solo and group shots. Let team scenes
    # widen instead of shrinking the people to fit a square canvas.
    scale = 0.86 * SIZE / cutout.height
    cutout = cutout.resize(
        (round(cutout.width * scale), round(cutout.height * scale)), Image.Resampling.LANCZOS
    )
    canvas = Image.new("RGBA", (cutout.width + 24, SIZE))
    canvas.alpha_composite(cutout, (12, (SIZE - cutout.height) // 2))
    return canvas


def main() -> None:
    model = ensure_model()
    session = ort.InferenceSession(str(model), providers=["CPUExecutionProvider"])
    OUTPUT.mkdir(parents=True, exist_ok=True)
    manifest = []
    for item in PHOTOS:
        source = item.get("path", SOURCES / item["file"])
        photo = Image.open(source).convert("RGB")
        mask = make_mask(
            photo,
            session,
            tuple(item.get("balls", ())),
            tuple(item.get("details", ())),
        )
        silhouette = normalize(photo, mask)
        result = press(silhouette, pitch=3.6, light_surface=False, dot_scale=0.36)
        target = OUTPUT / f"{item['id']}.png"
        result.save(target, optimize=True)
        manifest.append({"id": item["id"], "file": target.name, "size": list(result.size)})
        print(f"built {target.relative_to(ROOT)}")
    (OUTPUT / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")


if __name__ == "__main__":
    main()
