from __future__ import annotations

import argparse
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
DEFAULT_WIDTH = 88
DEFAULT_HEIGHT = 30
DEFAULT_FPS = 8


def default_video_path(root: str | Path) -> Path | None:
    root = Path(root)
    preferred = root / "Animation Videos" / "5minClip.mp4"
    if preferred.exists():
        return preferred
    videos = sorted((root / "Animation Videos").glob("*.mp4"))
    return videos[0] if videos else None


def cache_dir_for(root: str | Path, video_path: str | Path | None = None, width: int = DEFAULT_WIDTH, height: int = DEFAULT_HEIGHT, fps: int = DEFAULT_FPS) -> Path:
    root = Path(root)
    video = Path(video_path) if video_path else default_video_path(root)
    key = "spinner"
    if video:
        stat = video.stat()
        payload = f"{video.resolve()}:{stat.st_size}:{int(stat.st_mtime)}:{width}:{height}:{fps}".encode("utf-8")
        key = hashlib.sha1(payload).hexdigest()[:14]
    return root / ".cache" / "ascii_animation" / key


def render_ascii_cache(
    root: str | Path,
    video_path: str | Path | None = None,
    seconds: int = 45,
    fps: int = DEFAULT_FPS,
    width: int = DEFAULT_WIDTH,
    height: int = DEFAULT_HEIGHT,
    start_seconds: int = 0,
) -> dict[str, object]:
    root = Path(root)
    video = Path(video_path) if video_path else default_video_path(root)
    if video is None or not video.exists():
        return {"status": "no_video", "frames": 0, "path": None}
    ffmpeg = shutil.which("ffmpeg")
    if not ffmpeg:
        return {"status": "missing_ffmpeg", "frames": 0, "path": None}
    out_dir = cache_dir_for(root, video, width=width, height=height, fps=fps)
    out_dir.mkdir(parents=True, exist_ok=True)
    frame_path = out_dir / "frames.json"
    if frame_path.exists():
        with frame_path.open("r", encoding="utf-8") as handle:
            cached = json.load(handle)
        return {"status": "cached", "frames": len(cached.get("frames", [])), "path": str(frame_path)}
    vf = f"scale={width}:{height}:force_original_aspect_ratio=decrease,pad={width}:{height}:(ow-iw)/2:(oh-ih)/2"
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
    frame_size = width * height
    frames: list[str] = []
    for offset in range(0, len(proc.stdout) - frame_size + 1, frame_size):
        raw = proc.stdout[offset : offset + frame_size]
        rows = []
        for y in range(height):
            row = raw[y * width : (y + 1) * width]
            rows.append("".join(ASCII_CHARS[min(len(ASCII_CHARS) - 1, pixel * len(ASCII_CHARS) // 256)] for pixel in row))
        frames.append("\n".join(rows))
    payload = {"video": str(video), "width": width, "height": height, "fps": fps, "frames": frames}
    with frame_path.open("w", encoding="utf-8") as handle:
        json.dump(payload, handle)
    return {"status": "rendered", "frames": len(frames), "path": str(frame_path)}


def load_frames(root: str | Path) -> tuple[list[str], int]:
    cache_root = Path(root) / ".cache" / "ascii_animation"
    if not cache_root.exists():
        return [], DEFAULT_FPS
    frame_files = sorted(cache_root.glob("*/frames.json"), key=lambda item: item.stat().st_mtime, reverse=True)
    for path in frame_files:
        try:
            with path.open("r", encoding="utf-8") as handle:
                payload = json.load(handle)
            frames = payload.get("frames") or []
            if frames:
                return [str(frame) for frame in frames], int(payload.get("fps") or DEFAULT_FPS)
        except (OSError, ValueError, TypeError):
            continue
    return [], DEFAULT_FPS


def play_loop(root: str | Path, label: str, seed: int = 1) -> None:
    frames, fps = load_frames(root)
    rng = random.Random(f"{seed}:{label}:ascii_loading")
    spinner = ["|", "/", "-", "\\"]
    index = rng.randrange(max(1, len(frames))) if frames else 0
    tick = 0
    delay = 1.0 / max(1, fps)
    try:
        while True:
            sys.stdout.write("\033[2J\033[H")
            sys.stdout.write(f"{label}\n\n")
            if frames:
                sys.stdout.write(frames[index % len(frames)])
                index += 1
            else:
                sys.stdout.write(f"Working {spinner[tick % len(spinner)]}")
                tick += 1
            sys.stdout.write("\n")
            sys.stdout.flush()
            time.sleep(delay if frames else 0.12)
    except KeyboardInterrupt:
        return


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
        sys.stdout.write("\033[2J\033[H")
        sys.stdout.flush()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Render or play terminal ASCII loading animations.")
    sub = parser.add_subparsers(dest="command", required=True)
    cache = sub.add_parser("cache")
    cache.add_argument("--root", default=".")
    cache.add_argument("--video", default=None)
    cache.add_argument("--seconds", type=int, default=45)
    cache.add_argument("--fps", type=int, default=DEFAULT_FPS)
    cache.add_argument("--width", type=int, default=DEFAULT_WIDTH)
    cache.add_argument("--height", type=int, default=DEFAULT_HEIGHT)
    cache.add_argument("--start", type=int, default=0)
    play = sub.add_parser("play")
    play.add_argument("--root", default=".")
    play.add_argument("--label", default="Working...")
    play.add_argument("--seed", type=int, default=1)
    args = parser.parse_args(argv)
    if args.command == "cache":
        print(json.dumps(render_ascii_cache(args.root, args.video, args.seconds, args.fps, args.width, args.height, args.start), indent=2, sort_keys=True))
        return 0
    if args.command == "play":
        play_loop(args.root, args.label, seed=args.seed)
        return 0
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
