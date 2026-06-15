from __future__ import annotations

import argparse
import base64
import hashlib
import json
import os
import random
import shutil
import subprocess
import sys
import time
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator


ASCII_CHARS = " .:-=+*#%@"
ASCII_GRADIENT = "    ``..--^^~~<>??123456789%%&&@@"
DEFAULT_WIDTH = 160
DEFAULT_HEIGHT = 45
DEFAULT_FPS = 30
DEFAULT_PROFILE = "neon_white"
DEFAULT_FOREGROUND_A = "#ff00c3"
DEFAULT_FOREGROUND_B = "#00fff0"
DEFAULT_BACKGROUND = "#ffffff"
DEFAULT_TEXT_INPUT = "`1234567890-=~!@#$%^&*()_+qwertyuiop[]\\QWERTYUIOP{}|asdfghjkl;'ASDFGHJKL:zxcvbnm,./ZXCVBNM<>?"
DEFAULT_CELL_ASPECT = 2.0
DEFAULT_BG_SATURATION = 30.0
DEFAULT_RANDOMNESS = 0.0
DEFAULT_SEGMENT_SECONDS = 180
DEFAULT_VIDEO_ASPECT = 16 / 9
RENDER_VERSION = 5


def _clamp(value: float, low: float, high: float) -> float:
    return max(low, min(high, value))


def parse_hex_color(value: str, fallback: tuple[int, int, int]) -> tuple[int, int, int]:
    text = str(value or "").strip()
    if text.startswith("#"):
        text = text[1:]
    if len(text) != 6:
        return fallback
    try:
        return tuple(int(text[index : index + 2], 16) for index in (0, 2, 4))  # type: ignore[return-value]
    except ValueError:
        return fallback


def _blend_rgb(a: tuple[int, int, int], b: tuple[int, int, int], amount: float) -> tuple[int, int, int]:
    amount = _clamp(amount, 0.0, 1.0)
    return tuple(int(round(a[channel] + (b[channel] - a[channel]) * amount)) for channel in range(3))  # type: ignore[return-value]


def _rgb_to_hue(rgb: tuple[int, int, int]) -> float:
    r, g, b = (channel / 255.0 for channel in rgb)
    high = max(r, g, b)
    low = min(r, g, b)
    delta = high - low
    if delta == 0:
        return 0.0
    if high == r:
        hue = ((g - b) / delta) % 6
    elif high == g:
        hue = ((b - r) / delta) + 2
    else:
        hue = ((r - g) / delta) + 4
    return hue * 60.0


def _hsl_to_rgb(hue: float, saturation_percent: float, lightness_percent: float) -> tuple[int, int, int]:
    hue = hue % 360.0
    saturation = _clamp(saturation_percent / 100.0, 0.0, 1.0)
    lightness = _clamp(lightness_percent / 100.0, 0.0, 1.0)
    chroma = (1 - abs(2 * lightness - 1)) * saturation
    x = chroma * (1 - abs((hue / 60.0) % 2 - 1))
    match = lightness - chroma / 2
    if hue < 60:
        r1, g1, b1 = chroma, x, 0
    elif hue < 120:
        r1, g1, b1 = x, chroma, 0
    elif hue < 180:
        r1, g1, b1 = 0, chroma, x
    elif hue < 240:
        r1, g1, b1 = 0, x, chroma
    elif hue < 300:
        r1, g1, b1 = x, 0, chroma
    else:
        r1, g1, b1 = chroma, 0, x
    return (int(round((r1 + match) * 255)), int(round((g1 + match) * 255)), int(round((b1 + match) * 255)))


def _ansi_fg(rgb: tuple[int, int, int]) -> str:
    return f"\033[38;2;{rgb[0]};{rgb[1]};{rgb[2]}m"


def _ansi_bg(rgb: tuple[int, int, int]) -> str:
    return f"\033[48;2;{rgb[0]};{rgb[1]};{rgb[2]}m"


def _supports_truecolor() -> bool:
    if os.environ.get("NO_COLOR"):
        return False
    term = os.environ.get("TERM", "")
    if term == "dumb":
        return False
    return sys.stdout.isatty()


def auto_frame_size(
    terminal_size: os.terminal_size | None = None,
    *,
    target_cols: int | None = None,
    target_rows: int | None = None,
    cell_aspect: float = DEFAULT_CELL_ASPECT,
    video_aspect: float = DEFAULT_VIDEO_ASPECT,
) -> tuple[int, int]:
    """Choose a landscape terminal frame that respects character-cell shape."""
    terminal_size = terminal_size or shutil.get_terminal_size((120, 40))
    term_cols = max(40, int(terminal_size.columns))
    term_rows = max(16, int(terminal_size.lines))
    usable_cols = max(40, term_cols - 4)
    usable_rows = max(12, term_rows - 6)
    cell_aspect = max(1.0, float(cell_aspect or DEFAULT_CELL_ASPECT))
    video_aspect = max(1.0, float(video_aspect or DEFAULT_VIDEO_ASPECT))

    if target_cols:
        width = min(max(40, int(target_cols)), usable_cols)
    elif term_cols >= 180:
        width = min(192, usable_cols)
    elif term_cols >= 120:
        width = min(112, usable_cols)
    else:
        width = min(usable_cols, max(72, int(usable_cols * 0.92)))

    if target_rows:
        height = min(max(12, int(target_rows)), usable_rows)
        width = min(width, max(40, int(round(height * video_aspect * cell_aspect))))
    else:
        height = max(12, int(round(width / (video_aspect * cell_aspect))))
        if height > usable_rows:
            height = usable_rows
            width = max(40, min(usable_cols, int(round(height * video_aspect * cell_aspect))))

    width = max(40, min(width, usable_cols))
    height = max(12, min(height, usable_rows))
    return width, height


def default_video_path(root: str | Path) -> Path | None:
    root = Path(root)
    videos = sorted((root / "Animation Videos").glob("*.mp4"))
    if not videos:
        return None
    return max(videos, key=lambda item: item.stat().st_size)


def _resolve_video_identity(root: str | Path, video_value: object) -> Path | None:
    if not video_value:
        return None
    path = Path(str(video_value))
    if not path.is_absolute():
        path = Path(root) / path
    try:
        return path.resolve()
    except OSError:
        return None


def _preferred_video_identity(root: str | Path) -> Path | None:
    video = default_video_path(root)
    if not video:
        return None
    try:
        return video.resolve()
    except OSError:
        return None


def _profile_payload(
    *,
    profile: str = DEFAULT_PROFILE,
    foreground_a: str = DEFAULT_FOREGROUND_A,
    foreground_b: str = DEFAULT_FOREGROUND_B,
    background: str = DEFAULT_BACKGROUND,
    bg_gradient: bool = True,
    bg_saturation: float = DEFAULT_BG_SATURATION,
    text_type: str = "random-text",
    text_input: str = DEFAULT_TEXT_INPUT,
    threshold: int = 0,
    invert: bool = False,
    cell_aspect: float = DEFAULT_CELL_ASPECT,
    randomness: float = DEFAULT_RANDOMNESS,
) -> dict[str, object]:
    return {
        "profile": profile,
        "foreground_a": foreground_a,
        "foreground_b": foreground_b,
        "background": background,
        "bg_gradient": bool(bg_gradient),
        "bg_saturation": float(bg_saturation),
        "text_type": text_type,
        "text_input": text_input or DEFAULT_TEXT_INPUT,
        "threshold": int(threshold),
        "invert": bool(invert),
        "cell_aspect": float(cell_aspect),
        "randomness": float(randomness),
        "render_version": RENDER_VERSION,
        "sample_mode": "browser_canvas_cells",
    }


def cache_dir_for(
    root: str | Path,
    video_path: str | Path | None = None,
    width: int = DEFAULT_WIDTH,
    height: int = DEFAULT_HEIGHT,
    fps: int = DEFAULT_FPS,
    *,
    seconds: int = 45,
    start_seconds: int = 0,
    profile_options: dict[str, object] | None = None,
) -> Path:
    root = Path(root)
    video = Path(video_path) if video_path else default_video_path(root)
    key = "spinner"
    if video:
        stat = video.stat()
        payload = json.dumps(
            {
                "video": str(video.resolve()),
                "size": stat.st_size,
                "mtime": int(stat.st_mtime),
                "width": width,
                "height": height,
                "fps": fps,
                "seconds": seconds,
                "start_seconds": start_seconds,
                "profile_options": profile_options or {},
            },
            sort_keys=True,
        ).encode("utf-8")
        key = hashlib.sha1(payload).hexdigest()[:14]
    return root / ".cache" / "ascii_animation" / key


def clear_animation_cache(root: str | Path) -> dict[str, object]:
    path = Path(root) / ".cache" / "ascii_animation"
    existed = path.exists()
    shutil.rmtree(path, ignore_errors=True)
    return {"status": "cleared" if existed else "empty", "path": str(path)}


def video_duration_seconds(video_path: str | Path) -> float | None:
    ffprobe = shutil.which("ffprobe")
    if not ffprobe:
        return None
    proc = subprocess.run(
        [
            ffprobe,
            "-v",
            "error",
            "-show_entries",
            "format=duration",
            "-of",
            "default=noprint_wrappers=1:nokey=1",
            str(video_path),
        ],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
        text=True,
    )
    if proc.returncode != 0:
        return None
    try:
        return max(0.0, float(proc.stdout.strip()))
    except ValueError:
        return None


def segment_start_seconds(video_path: str | Path, *, segment_count: int, seconds: int) -> list[int]:
    segment_count = max(1, int(segment_count))
    duration = video_duration_seconds(video_path)
    if segment_count == 1 or not duration or duration <= seconds + 1:
        return [0]
    max_start = max(0, int(duration - max(1, seconds)))
    if segment_count == 2:
        return [0, max_start]
    return sorted({int(round(index * max_start / (segment_count - 1))) for index in range(segment_count)})


def _resolve_render_size(
    width: int | None,
    height: int | None,
    *,
    auto_size: bool,
    target_cols: int | None,
    target_rows: int | None,
    cell_aspect: float,
    terminal_size: os.terminal_size | None = None,
) -> tuple[int, int]:
    if width and height:
        return max(40, int(width)), max(12, int(height))
    if width:
        resolved_height = max(12, int(round(int(width) / (DEFAULT_VIDEO_ASPECT * max(1.0, cell_aspect)))))
        return max(40, int(width)), resolved_height
    if height:
        resolved_width = max(40, int(round(int(height) * DEFAULT_VIDEO_ASPECT * max(1.0, cell_aspect))))
        return resolved_width, max(12, int(height))
    if auto_size:
        return auto_frame_size(terminal_size, target_cols=target_cols, target_rows=target_rows, cell_aspect=cell_aspect)
    return DEFAULT_WIDTH, DEFAULT_HEIGHT


def _deterministic_random_unit(frame_index: int, x: int, y: int, pixel: int) -> float:
    value = (frame_index * 1315423911 + x * 2654435761 + y * 97531 + pixel * 17) & 0xFFFFFFFF
    value ^= value >> 16
    value = (value * 0x7FEB352D) & 0xFFFFFFFF
    value ^= value >> 15
    return (value & 0xFFFFFF) / float(0x1000000)


def _random_text_char(text: str, frame_index: int, x: int, y: int, pixel: int) -> str:
    source = text or DEFAULT_TEXT_INPUT
    index = (frame_index * 1315423911 + x * 2654435761 + y * 97531 + pixel * 17) % len(source)
    return source[index]


def _gradient_char(pixel: int) -> str:
    index = min(len(ASCII_GRADIENT) - 1, max(0, int(pixel) * len(ASCII_GRADIENT) // 256))
    return ASCII_GRADIENT[index]


def _char_for_pixel(
    pixel: int,
    *,
    frame_index: int,
    x: int,
    y: int,
    text_type: str,
    text_input: str,
    threshold: int,
    invert: bool,
    randomness: float = DEFAULT_RANDOMNESS,
) -> str:
    value = 255 - pixel if invert else pixel
    if value <= max(0, threshold):
        return " "
    randomness = _clamp(randomness, 0.0, 100.0) / 100.0
    if randomness and _deterministic_random_unit(frame_index, x, y, value) < 0.005 * randomness:
        return ASCII_GRADIENT[int(_deterministic_random_unit(frame_index + 37, y, x, value) * len(ASCII_GRADIENT)) % len(ASCII_GRADIENT)]
    if text_type.replace("_", "-") in {"user-text", "user"}:
        return _random_text_char(text_input, frame_index, x, y, value)
    return _gradient_char(value)


def render_ascii_cache(
    root: str | Path,
    video_path: str | Path | None = None,
    seconds: int = 45,
    fps: int = DEFAULT_FPS,
    width: int | None = None,
    height: int | None = None,
    start_seconds: int = 0,
    *,
    profile: str = DEFAULT_PROFILE,
    auto_size: bool = True,
    target_cols: int | None = None,
    target_rows: int | None = None,
    cell_aspect: float = DEFAULT_CELL_ASPECT,
    foreground_a: str = DEFAULT_FOREGROUND_A,
    foreground_b: str = DEFAULT_FOREGROUND_B,
    background: str = DEFAULT_BACKGROUND,
    bg_gradient: bool = True,
    bg_saturation: float = DEFAULT_BG_SATURATION,
    text_type: str = "random-text",
    text_input: str = DEFAULT_TEXT_INPUT,
    threshold: int = 0,
    invert: bool = False,
    randomness: float = DEFAULT_RANDOMNESS,
) -> dict[str, object]:
    root = Path(root)
    video = Path(video_path) if video_path else default_video_path(root)
    if video is None or not video.exists():
        return {"status": "no_video", "frames": 0, "path": None}
    ffmpeg = shutil.which("ffmpeg")
    if not ffmpeg:
        return {"status": "missing_ffmpeg", "frames": 0, "path": None}
    render_width, render_height = _resolve_render_size(
        width,
        height,
        auto_size=auto_size,
        target_cols=target_cols,
        target_rows=target_rows,
        cell_aspect=cell_aspect,
    )
    options = _profile_payload(
        profile=profile,
        foreground_a=foreground_a,
        foreground_b=foreground_b,
        background=background,
        bg_gradient=bg_gradient,
        bg_saturation=bg_saturation,
        text_type=text_type,
        text_input=text_input,
        threshold=threshold,
        invert=invert,
        cell_aspect=cell_aspect,
        randomness=randomness,
    )
    out_dir = cache_dir_for(
        root,
        video,
        width=render_width,
        height=render_height,
        fps=fps,
        seconds=seconds,
        start_seconds=start_seconds,
        profile_options=options,
    )
    out_dir.mkdir(parents=True, exist_ok=True)
    frame_path = out_dir / "frames.json"
    if frame_path.exists():
        with frame_path.open("r", encoding="utf-8") as handle:
            cached = json.load(handle)
        metadata_path = out_dir / "metadata.json"
        if not metadata_path.exists():
            metadata_payload = dict(cached)
            metadata_payload.pop("frames", None)
            metadata_payload["frame_count"] = len(cached.get("frames", []))
            with metadata_path.open("w", encoding="utf-8") as handle:
                json.dump(metadata_payload, handle)
        return {"status": "cached", "frames": len(cached.get("frames", [])), "path": str(frame_path), "width": cached.get("width"), "height": cached.get("height"), "profile": cached.get("profile")}
    # The grid is intentionally wider than a normal pixel frame because terminal
    # character cells are taller than they are wide. Fill the character grid and
    # let the terminal cell shape restore the visual 16:9 aspect.
    vf = f"scale={render_width}:{render_height}:flags=lanczos,setsar=1"
    cmd = [
        ffmpeg,
        "-hide_banner",
        "-loglevel",
        "error",
        "-ss",
        str(max(0, start_seconds)),
        "-i",
        str(video),
        "-t",
        str(max(1, seconds)),
        "-vf",
        vf,
        "-r",
        str(max(1, fps)),
        "-f",
        "rawvideo",
        "-pix_fmt",
        "gray",
        "-",
    ]
    proc = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False)
    if proc.returncode != 0 or not proc.stdout:
        return {"status": "ffmpeg_failed", "frames": 0, "path": None, "stderr": proc.stderr.decode("utf-8", errors="ignore")[-300:]}
    frame_size = render_width * render_height
    frames: list[str] = []
    for offset in range(0, len(proc.stdout) - frame_size + 1, frame_size):
        raw = proc.stdout[offset : offset + frame_size]
        frames.append(base64.b64encode(raw).decode("ascii"))
    payload = {
        "version": 2,
        "render_version": RENDER_VERSION,
        "frame_format": "gray_b64",
        "profile": profile,
        "video": str(video),
        "width": render_width,
        "height": render_height,
        "fps": fps,
        "seconds": seconds,
        "start_seconds": start_seconds,
        "render_options": options,
        "frames": frames,
    }
    with frame_path.open("w", encoding="utf-8") as handle:
        json.dump(payload, handle)
    metadata_payload = dict(payload)
    metadata_payload.pop("frames", None)
    metadata_payload["frame_count"] = len(frames)
    with (out_dir / "metadata.json").open("w", encoding="utf-8") as handle:
        json.dump(metadata_payload, handle)
    return {"status": "rendered", "frames": len(frames), "path": str(frame_path), "width": render_width, "height": render_height, "profile": profile}


def _frame_score(payload: dict[str, object], path: Path, terminal_size: os.terminal_size, root: str | Path) -> float:
    width = int(payload.get("width") or 0)
    height = int(payload.get("height") or 0)
    if width <= 0 or height <= 0:
        return -1_000_000.0
    target_width, target_height = auto_frame_size(terminal_size)
    fits = width <= max(40, terminal_size.columns - 2) and height <= max(12, terminal_size.lines - 4)
    preferred_video = _preferred_video_identity(root)
    payload_video = _resolve_video_identity(root, payload.get("video"))
    preferred_source_bonus = 500_000.0 if preferred_video and payload_video == preferred_video else 0.0
    profile_bonus = 200_000.0 if payload.get("profile") == DEFAULT_PROFILE else 0.0
    version_bonus = 50_000.0 if int(payload.get("render_version") or 0) >= RENDER_VERSION else 0.0
    fit_bonus = 100_000.0 if fits else -100_000.0
    size_ratio = min(width / max(1, target_width), height / max(1, target_height), 1.0)
    closeness = 10_000.0 * size_ratio - abs(width - target_width) * 10.0 - abs(height - target_height) * 20.0
    recency = path.stat().st_mtime / 1_000_000_000.0
    return preferred_source_bonus + profile_bonus + version_bonus + fit_bonus + closeness + recency


def _read_cache_metadata(path: Path) -> dict[str, object] | None:
    metadata_path = path.with_name("metadata.json")
    try:
        with (metadata_path if metadata_path.exists() else path).open("r", encoding="utf-8") as handle:
            payload = json.load(handle)
    except (OSError, ValueError, TypeError):
        return None
    if "frames" in payload:
        payload = dict(payload)
        payload["frame_count"] = len(payload.get("frames") or [])
        payload.pop("frames", None)
    return dict(payload)


def _read_cache_frames(path: Path) -> tuple[list[str], int, dict[str, object]] | None:
    try:
        with path.open("r", encoding="utf-8") as handle:
            payload = json.load(handle)
    except (OSError, ValueError, TypeError):
        return None
    frames = payload.get("frames") or []
    if not frames:
        return None
    metadata = dict(payload)
    metadata["frame_count"] = len(frames)
    metadata["cache_path"] = str(path)
    return [str(frame) for frame in frames], int(payload.get("fps") or DEFAULT_FPS), metadata


def _animation_cache_candidates(root: str | Path, terminal_size: os.terminal_size | None = None) -> list[tuple[float, Path, dict[str, object]]]:
    cache_root = Path(root) / ".cache" / "ascii_animation"
    terminal_size = terminal_size or shutil.get_terminal_size((120, 40))
    if not cache_root.exists():
        return []
    frame_files = sorted(cache_root.glob("*/frames.json"), key=lambda item: item.stat().st_mtime, reverse=True)
    candidates: list[tuple[float, Path, dict[str, object]]] = []
    for path in frame_files:
        metadata = _read_cache_metadata(path)
        if not metadata or int(metadata.get("frame_count") or 0) <= 0:
            continue
        metadata["cache_path"] = str(path)
        payload_video = _resolve_video_identity(root, metadata.get("video"))
        metadata["preferred_video"] = bool(payload_video and payload_video == _preferred_video_identity(root))
        metadata["fits_terminal"] = int(metadata.get("width") or 0) <= max(40, terminal_size.columns - 2) and int(metadata.get("height") or 0) <= max(12, terminal_size.lines - 4)
        candidates.append((_frame_score(metadata, path, terminal_size, root), path, metadata))
    candidates.sort(key=lambda item: item[0], reverse=True)
    return candidates


def load_animation_frame_sets(root: str | Path, terminal_size: os.terminal_size | None = None) -> list[tuple[list[str], int, dict[str, object]]]:
    frame_sets: list[tuple[list[str], int, dict[str, object]]] = []
    for _, path, metadata in _animation_cache_candidates(root, terminal_size):
        loaded = _read_cache_frames(path)
        if loaded:
            frames, fps, loaded_metadata = loaded
            loaded_metadata.update({key: value for key, value in metadata.items() if key not in loaded_metadata})
            frame_sets.append((frames, fps, loaded_metadata))
    return frame_sets


def load_animation_frames(root: str | Path, terminal_size: os.terminal_size | None = None) -> tuple[list[str], int, dict[str, object]]:
    candidates = load_animation_frame_sets(root, terminal_size)
    if not candidates:
        return [], DEFAULT_FPS, {}
    frames, fps, metadata = candidates[0]
    return frames, fps, metadata


def load_frames(root: str | Path) -> tuple[list[str], int]:
    frames, fps, _ = load_animation_frames(root)
    return frames, fps


def colorize_frame(frame: str, metadata: dict[str, object] | None = None, *, truecolor: bool = True) -> str:
    metadata = metadata or {}
    options = metadata.get("render_options") if isinstance(metadata.get("render_options"), dict) else {}
    options = options if isinstance(options, dict) else {}
    if metadata.get("frame_format") != "gray_b64":
        if not truecolor:
            return frame
        return _colorize_text_frame(frame, options)
    width = int(metadata.get("width") or 0)
    height = int(metadata.get("height") or 0)
    if width <= 0 or height <= 0:
        return ""
    try:
        pixels = base64.b64decode(frame.encode("ascii"), validate=True)
    except (ValueError, TypeError):
        return ""
    if len(pixels) < width * height:
        return ""
    return _render_gray_frame(pixels, width, height, options, truecolor=truecolor)


def _colorize_text_frame(frame: str, options: dict[str, object]) -> str:
    foreground_a = parse_hex_color(str(options.get("foreground_a") or DEFAULT_FOREGROUND_A), (255, 0, 195))
    foreground_b = parse_hex_color(str(options.get("foreground_b") or DEFAULT_FOREGROUND_B), (0, 255, 240))
    background = parse_hex_color(str(options.get("background") or DEFAULT_BACKGROUND), (255, 255, 255))
    bg_gradient = bool(options.get("bg_gradient", True))
    bg_saturation = float(options.get("bg_saturation", DEFAULT_BG_SATURATION))
    lines = frame.splitlines()
    width = max((len(line) for line in lines), default=0)
    height = max(1, len(lines))
    rendered: list[str] = []
    for y, line in enumerate(lines):
        row_ratio = y / max(1, height - 1)
        row_tint = _blend_rgb(foreground_a, foreground_b, row_ratio)
        row_bg = _blend_rgb(background, row_tint, (bg_saturation / 100.0) * 0.35) if bg_gradient else background
        current_fg: tuple[int, int, int] | None = None
        chunks = [_ansi_bg(row_bg)]
        padded = line.ljust(width)
        for x, char in enumerate(padded):
            if char == " ":
                chunks.append(" ")
                continue
            fg = foreground_a if ((x * 17 + y * 31 + ord(char)) % 9) < 5 else foreground_b
            if fg != current_fg:
                chunks.append(_ansi_fg(fg))
                current_fg = fg
            chunks.append(char)
        chunks.append("\033[0m")
        rendered.append("".join(chunks))
    return "\n".join(rendered)


def _render_gray_frame(pixels: bytes, width: int, height: int, options: dict[str, object], *, truecolor: bool) -> str:
    foreground_a = parse_hex_color(str(options.get("foreground_a") or DEFAULT_FOREGROUND_A), (255, 0, 195))
    foreground_b = parse_hex_color(str(options.get("foreground_b") or DEFAULT_FOREGROUND_B), (0, 255, 240))
    background = parse_hex_color(str(options.get("background") or DEFAULT_BACKGROUND), (255, 255, 255))
    background_hue = _rgb_to_hue(background)
    bg_gradient = bool(options.get("bg_gradient", True))
    bg_saturation = float(options.get("bg_saturation", DEFAULT_BG_SATURATION))
    threshold = _clamp(float(options.get("threshold") or 0) / 100.0, 0.0, 0.95)
    invert = bool(options.get("invert", False))
    text_type = str(options.get("text_type") or "random-text")
    text_input = str(options.get("text_input") or DEFAULT_TEXT_INPUT)
    randomness = _clamp(float(options.get("randomness") or DEFAULT_RANDOMNESS), 0.0, 100.0)
    frame_index = int(options.get("_frame_index") or 0)
    rows: list[str] = []
    for y in range(height):
        current_fg: tuple[int, int, int] | None = None
        current_bg: tuple[int, int, int] | None = None
        chunks: list[str] = []
        for x in range(width):
            gray = pixels[y * width + x]
            norm = gray / 255.0
            if bg_gradient:
                if not invert:
                    lightness = (norm**2) * 100.0 if norm > threshold else threshold / 4.0 * 100.0
                else:
                    lightness = (1.0 - norm**2) * 100.0 if norm < 1.0 - threshold else threshold / 4.0 * 100.0
                bg = _hsl_to_rgb(background_hue, bg_saturation, lightness)
            else:
                bg = background

            visible = norm > threshold if not invert else norm < 1.0 - threshold
            if visible:
                char = _char_for_pixel(
                    gray,
                    frame_index=frame_index,
                    x=x,
                    y=y,
                    text_type=text_type,
                    text_input=text_input,
                    threshold=int(threshold * 255),
                    invert=invert,
                    randomness=randomness,
                )
                if not char:
                    char = " "
                if not invert:
                    fg_factor = (norm - threshold) / max(0.001, 1.0 - threshold)
                    fg = _blend_rgb(foreground_a, foreground_b, fg_factor)
                else:
                    fg_factor = norm / max(0.001, 1.0 - threshold)
                    fg = _blend_rgb(foreground_b, foreground_a, fg_factor)
            else:
                char = " "
                fg = foreground_a

            if truecolor:
                if bg != current_bg:
                    chunks.append(_ansi_bg(bg))
                    current_bg = bg
                    current_fg = None
                if visible and fg != current_fg:
                    chunks.append(_ansi_fg(fg))
                    current_fg = fg
                chunks.append(char)
            else:
                chunks.append(char)
        if truecolor:
            chunks.append("\033[0m")
        rows.append("".join(chunks))
    return "\n".join(rows)


def _center_text(text: str, width: int) -> str:
    if len(text) >= width:
        return text[:width]
    return " " * max(0, (width - len(text)) // 2) + text


def _render_screen(label: str, frame: str | None, metadata: dict[str, object], *, tick: int = 0, clear_screen: bool = True) -> str:
    terminal_size = shutil.get_terminal_size((120, 40))
    truecolor = bool(frame and metadata.get("profile") == DEFAULT_PROFILE and _supports_truecolor())
    foreground_a = parse_hex_color(str((metadata.get("render_options") or {}).get("foreground_a") if isinstance(metadata.get("render_options"), dict) else DEFAULT_FOREGROUND_A), (255, 0, 195))
    clear = "\033[?25l\033[0m"
    clear += "\033[2J\033[H" if clear_screen else "\033[H"
    if truecolor:
        title = _ansi_fg(foreground_a) + _center_text(label, terminal_size.columns) + "\033[0m"
    else:
        title = _center_text(label, terminal_size.columns)
    if not frame:
        spinner = ["|", "/", "-", "\\"]
        return f"{clear}{title}\n\n{_center_text('Working ' + spinner[tick % len(spinner)], terminal_size.columns)}\n"

    if metadata.get("frame_format") == "gray_b64":
        frame_width = int(metadata.get("width") or 0)
        frame_height = int(metadata.get("height") or 0)
    else:
        lines = frame.splitlines()
        frame_width = max((len(line) for line in lines), default=0)
        frame_height = len(lines)
    left_pad = max(0, (terminal_size.columns - frame_width) // 2)
    vertical_pad = max(1, (terminal_size.lines - frame_height - 3) // 2)
    centered_rows = []
    render_metadata = dict(metadata)
    render_options = dict(render_metadata.get("render_options") or {}) if isinstance(render_metadata.get("render_options"), dict) else {}
    render_options["_frame_index"] = tick
    render_metadata["render_options"] = render_options
    rendered_frame = colorize_frame(frame, render_metadata, truecolor=truecolor)
    for row in rendered_frame.splitlines():
        centered_rows.append(" " * left_pad + row)
    body = "\n" * vertical_pad + "\n".join(centered_rows)
    return f"{clear}{title}{body}\n\033[0m"


def play_loop(root: str | Path, label: str, seed: int = 1, duration_seconds: float | None = None) -> None:
    rng = random.Random(f"{seed}:{label}:{os.getpid()}:{time.time_ns()}:ascii_loading")
    metadata_candidates = _animation_cache_candidates(root)
    preferred_metadata = [candidate for candidate in metadata_candidates if candidate[2].get("preferred_video") and candidate[2].get("fits_terminal")]
    if not preferred_metadata:
        preferred_metadata = [candidate for candidate in metadata_candidates if candidate[2].get("fits_terminal")]
    if not preferred_metadata:
        preferred_metadata = metadata_candidates
    if preferred_metadata:
        top_width = int(preferred_metadata[0][2].get("width") or 0)
        top_height = int(preferred_metadata[0][2].get("height") or 0)
        best_size_metadata = [candidate for candidate in preferred_metadata if int(candidate[2].get("width") or 0) == top_width and int(candidate[2].get("height") or 0) == top_height]
        if best_size_metadata:
            top_seconds = max(int(candidate[2].get("seconds") or 0) for candidate in best_size_metadata)
            best_size_metadata = [candidate for candidate in best_size_metadata if int(candidate[2].get("seconds") or 0) == top_seconds]
        _, chosen_path, chosen_metadata = rng.choice(best_size_metadata or preferred_metadata)
        loaded = _read_cache_frames(chosen_path)
        if loaded:
            frames, fps, metadata = loaded
            metadata.update({key: value for key, value in chosen_metadata.items() if key not in metadata})
        else:
            frames, fps, metadata = [], DEFAULT_FPS, {}
    else:
        frames, fps, metadata = [], DEFAULT_FPS, {}
    start_index = rng.randrange(max(1, len(frames))) if frames else 0
    tick = 0
    delay = 1.0 / max(1, fps)
    started = time.monotonic()
    first_render = True
    try:
        while True:
            now = time.monotonic()
            if frames:
                frame_offset = int(max(0.0, now - started) * max(1, fps))
                frame_index = (start_index + frame_offset) % len(frames)
                sys.stdout.write(_render_screen(label, frames[frame_index], metadata, tick=frame_offset, clear_screen=first_render))
                tick = frame_offset + 1
            else:
                sys.stdout.write(_render_screen(label, None, metadata, tick=tick, clear_screen=first_render))
                tick += 1
            sys.stdout.flush()
            first_render = False
            if duration_seconds is not None and time.monotonic() - started >= duration_seconds:
                break
            if frames:
                next_frame_time = started + (tick / max(1, fps))
                time.sleep(max(0.0, min(delay, next_frame_time - time.monotonic())))
            else:
                time.sleep(0.12)
    except KeyboardInterrupt:
        return
    finally:
        sys.stdout.write("\033[0m\033[?25h")
        sys.stdout.flush()


@contextmanager
def loading_screen(root: str | Path, label: str, seed: int = 1, enabled: bool = True) -> Iterator[None]:
    if not enabled or not sys.stdout.isatty():
        yield
        return
    cmd = [sys.executable, "-m", "nba_gm_data.animation", "play", "--root", str(root), "--label", label, "--seed", str(seed)]
    proc = subprocess.Popen(cmd, stdout=sys.stdout, stderr=subprocess.DEVNULL)
    try:
        yield
    finally:
        proc.terminate()
        try:
            proc.wait(timeout=0.5)
        except subprocess.TimeoutExpired:
            proc.kill()
        sys.stdout.write("\033[0m\033[?25h\033[2J\033[H")
        sys.stdout.flush()


def preview_animation(root: str | Path, label: str = "Previewing loading animation...", seed: int = 1, seconds: float = 5.0) -> None:
    play_loop(root, label, seed=seed, duration_seconds=max(0.5, seconds))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Render or play terminal ASCII loading animations.")
    sub = parser.add_subparsers(dest="command", required=True)
    cache = sub.add_parser("cache")
    cache.add_argument("--root", default=".")
    cache.add_argument("--video", default=None)
    cache.add_argument("--seconds", type=int, default=DEFAULT_SEGMENT_SECONDS)
    cache.add_argument("--segments", type=int, default=1)
    cache.add_argument("--fps", type=int, default=DEFAULT_FPS)
    cache.add_argument("--width", type=int, default=None)
    cache.add_argument("--height", type=int, default=None)
    cache.add_argument("--start", type=int, default=0)
    cache.add_argument("--profile", default=DEFAULT_PROFILE)
    cache.add_argument("--auto-size", action="store_true")
    cache.add_argument("--target-cols", type=int, default=None)
    cache.add_argument("--target-rows", type=int, default=None)
    cache.add_argument("--cell-aspect", type=float, default=DEFAULT_CELL_ASPECT)
    cache.add_argument("--foreground-a", default=DEFAULT_FOREGROUND_A)
    cache.add_argument("--foreground-b", default=DEFAULT_FOREGROUND_B)
    cache.add_argument("--background", default=DEFAULT_BACKGROUND)
    cache.add_argument("--bg-gradient", action="store_true", default=True)
    cache.add_argument("--no-bg-gradient", action="store_false", dest="bg_gradient")
    cache.add_argument("--bg-saturation", type=float, default=DEFAULT_BG_SATURATION)
    cache.add_argument("--text-type", default="random-text")
    cache.add_argument("--text-input", default=DEFAULT_TEXT_INPUT)
    cache.add_argument("--threshold", type=int, default=0)
    cache.add_argument("--invert", action="store_true")
    cache.add_argument("--randomness", type=float, default=DEFAULT_RANDOMNESS)
    cache.add_argument("--clear-cache", action="store_true")
    play = sub.add_parser("play")
    play.add_argument("--root", default=".")
    play.add_argument("--label", default="Working...")
    play.add_argument("--seed", type=int, default=1)
    play.add_argument("--duration", type=float, default=None)
    preview = sub.add_parser("preview")
    preview.add_argument("--root", default=".")
    preview.add_argument("--label", default="Previewing loading animation...")
    preview.add_argument("--seed", type=int, default=1)
    preview.add_argument("--seconds", type=float, default=5.0)
    args = parser.parse_args(argv)
    if args.command == "cache":
        if args.clear_cache:
            clear_animation_cache(args.root)
        video = Path(args.video) if args.video else default_video_path(args.root)
        starts = segment_start_seconds(video, segment_count=args.segments, seconds=args.seconds) if video else [args.start]
        results = [
            render_ascii_cache(
                args.root,
                args.video,
                args.seconds,
                args.fps,
                args.width,
                args.height,
                start,
                profile=args.profile,
                auto_size=args.auto_size or (args.width is None and args.height is None),
                target_cols=args.target_cols,
                target_rows=args.target_rows,
                cell_aspect=args.cell_aspect,
                foreground_a=args.foreground_a,
                foreground_b=args.foreground_b,
                background=args.background,
                bg_gradient=args.bg_gradient,
                bg_saturation=args.bg_saturation,
                text_type=args.text_type,
                text_input=args.text_input,
                threshold=args.threshold,
                invert=args.invert,
                randomness=args.randomness,
            )
            for start in starts
        ]
        print(
            json.dumps(
                results[0] if args.segments <= 1 else {"status": "rendered_segments", "segments": len(results), "starts": starts, "results": results},
                indent=2,
                sort_keys=True,
            )
        )
        return 0
    if args.command == "play":
        play_loop(args.root, args.label, seed=args.seed, duration_seconds=args.duration)
        return 0
    if args.command == "preview":
        preview_animation(args.root, args.label, seed=args.seed, seconds=args.seconds)
        return 0
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
