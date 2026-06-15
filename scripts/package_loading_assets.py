from __future__ import annotations

import argparse
import json
import zipfile
from pathlib import Path


DEFAULT_OUTPUT = Path("dist/loading-assets-v1.zip")


def main() -> int:
    parser = argparse.ArgumentParser(description="Package pre-rendered loading-screen caches for GitHub Releases.")
    parser.add_argument("--root", default=".")
    parser.add_argument("--out", default=str(DEFAULT_OUTPUT))
    parser.add_argument("--seconds", type=int, default=180)
    parser.add_argument("--video-name", default="The Top Plays of the 2025-26 NBA Season _ Pt.1.mp4")
    args = parser.parse_args()

    root = Path(args.root).resolve()
    output = (root / args.out).resolve() if not Path(args.out).is_absolute() else Path(args.out).resolve()
    selected = selected_cache_files(root, video_name=args.video_name, seconds=args.seconds)
    if not selected:
        print("No matching loading-screen caches found. Run nba-gm-data animation-cache first.")
        return 1

    output.parent.mkdir(parents=True, exist_ok=True)
    manifest = {
        "asset": output.name,
        "video_name": args.video_name,
        "seconds": args.seconds,
        "cache_files": [str(path.relative_to(root)) for path in selected],
    }
    with zipfile.ZipFile(output, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=6) as archive:
        archive.writestr("loading-assets-manifest.json", json.dumps(manifest, indent=2, sort_keys=True))
        for path in selected:
            archive.write(path, path.relative_to(root).as_posix())

    size_mb = output.stat().st_size / (1024 * 1024)
    print(f"Wrote {output} ({size_mb:.1f} MB)")
    print(f"Packaged {len(selected)} cache files.")
    return 0


def selected_cache_files(root: Path, *, video_name: str, seconds: int) -> list[Path]:
    cache_root = root / ".cache" / "ascii_animation"
    files: list[Path] = []
    for frame_path in sorted(cache_root.glob("*/frames.json")):
        metadata = load_metadata(frame_path)
        if not metadata:
            continue
        if Path(str(metadata.get("video") or "")).name != video_name:
            continue
        if int(metadata.get("seconds") or 0) != seconds:
            continue
        files.append(frame_path)
        metadata_path = frame_path.with_name("metadata.json")
        if metadata_path.exists():
            files.append(metadata_path)
    return files


def load_metadata(frame_path: Path) -> dict[str, object] | None:
    metadata_path = frame_path.with_name("metadata.json")
    try:
        with (metadata_path if metadata_path.exists() else frame_path).open("r", encoding="utf-8") as handle:
            payload = json.load(handle)
    except (OSError, ValueError, TypeError):
        return None
    if "frames" in payload:
        payload = dict(payload)
        payload.pop("frames", None)
    return dict(payload)


if __name__ == "__main__":
    raise SystemExit(main())
