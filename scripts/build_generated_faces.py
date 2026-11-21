#!/usr/bin/env python3
"""Copy the AI-generated fictional faces into the game (gui/assets/headshots/generated/) with their manifest.

The faces are made by Codex (task HEADSHOT-GEN-LIBRARY): photoreal portraits of fictional adults, made with OpenAI's
image tool, several images per person by age ("stages": rookie, prime, veteran, late career for players; three ages
for staff). Codex keeps the library manifest in data/research/headshot_gen_library_manifest.json and the 320 x 320
game JPEGs in its ignored output folder (output/headshots-gen-library/game/<group>/<NNNN>-s<K>.jpg).

This script turns every listed person whose images are all present into a game face:
  - images: 260 px AVIF (about 4-6 KB, against about 28 KB for the JPEG, with no visible loss at game size), made with
    macOS `sips` like the stock library (scripts/build_stock_faces.py); `--format jpg` copies the JPEGs instead;
  - manifest: gui/assets/headshots/generated/manifest.json, in the format faces.py reads: `groups` (gender, count,
    use) and `faces` (gender, stages with min_age and file). Game face ids carry a "gen-" group prefix
    ("gen-staff-m/0001") so they never collide with the stock library's ids ("staff-m/0001").

Later batches keep continuing ids in the same manifest: re-run the script and only new or changed images are
converted; images no longer listed are removed.

  python3 scripts/build_generated_faces.py [--source DIR] [--manifest FILE] [--format avif|jpg] [--width 260]
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_MANIFEST = ROOT / "data" / "research" / "headshot_gen_library_manifest.json"
DEFAULT_SOURCE = ROOT / "output" / "headshots-gen-library" / "game"
OUT = ROOT / "src" / "nba_gm_data" / "gui" / "assets" / "headshots" / "generated"
URL_ROOT = "/assets/headshots/generated"
GROUP_PREFIX = "gen-"
USE = {
    "staff-m": "Made-up coaches and staff (men)",
    "staff-f": "Made-up coaches and staff (women)",
    "player-m": "Made-up draft prospects and the players they become",
}
GENDER = {"staff-m": "male", "staff-f": "female", "player-m": "male"}
ABOUT = ("AI-generated portraits of fictional people (no real person is depicted), made with OpenAI's image tool "
         "(HEADSHOT-GEN-LIBRARY). Each face is one fictional person with images at several ages; the game shows the "
         "last stage whose min_age is at or below the person's age (faces.py).")


def convert(source: Path, target: Path, fmt: str, width: int, quality: int) -> None:
    target.parent.mkdir(parents=True, exist_ok=True)
    if fmt == "jpg":
        shutil.copyfile(source, target)
        return
    subprocess.run(["sips", "-s", "format", "avif", "-s", "formatOptions", str(quality), "--resampleWidth", str(width),
                    str(source), "--out", str(target)], check=True, capture_output=True)


def build(source_dir: Path, manifest_path: Path, fmt: str, width: int, quality: int) -> dict:
    library = json.loads(manifest_path.read_text(encoding="utf-8"))
    groups: dict[str, dict] = {}
    faces: dict[str, dict] = {}
    skipped: list[str] = []
    written: set[Path] = set()
    converted = 0
    for person in sorted(library.get("people") or [], key=lambda row: row["id"]):
        base, _, number = person["id"].partition("/")
        if base not in GENDER or not number.isdigit():
            skipped.append(f"{person['id']}: unknown group")
            continue
        if person.get("gender") != GENDER[base]:
            skipped.append(f"{person['id']}: gender {person.get('gender')} does not match group {base}")
            continue
        stages = sorted(person.get("stages") or [], key=lambda stage: float(stage.get("min_age") or 0))
        missing = [stage["file"] for stage in stages if not (source_dir / stage["file"]).exists()]
        if not stages or missing or float(stages[0].get("min_age") or 0) != 0:
            skipped.append(f"{person['id']}: " + (f"missing {', '.join(missing)}" if missing else "no stage from age 0"))
            continue
        face_id = f"{GROUP_PREFIX}{base}/{number}"
        entry = {"gender": GENDER[base], "source_id": person["id"], "stages": []}
        for stage in stages:
            source = source_dir / stage["file"]
            target = OUT / Path(stage["file"]).with_suffix(f".{fmt}")
            if not target.exists() or target.stat().st_mtime < source.stat().st_mtime:
                convert(source, target, fmt, width, quality)
                converted += 1
            written.add(target)
            entry["stages"].append({"min_age": stage["min_age"], "age": stage.get("age"),
                                    "file": f"{URL_ROOT}/{target.relative_to(OUT).as_posix()}"})
        faces[face_id] = entry
        group = groups.setdefault(f"{GROUP_PREFIX}{base}", {"gender": GENDER[base], "count": 0, "use": USE[base]})
        group["count"] += 1
    removed = 0
    for old in OUT.rglob("*"):
        if old.is_file() and old.suffix in (".avif", ".jpg") and old not in written:
            old.unlink()
            removed += 1
    manifest = {
        "library": "generated", "ext": fmt, "built_by": "scripts/build_generated_faces.py",
        "built": dt.date.today().isoformat(), "source_manifest": "data/research/headshot_gen_library_manifest.json",
        "about": ABOUT, "made_with": "OpenAI image generation (Codex built-in image tool)",
        "fictional": True, "groups": dict(sorted(groups.items())), "faces": faces,
    }
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "manifest.json").write_text(json.dumps(manifest, indent=1) + "\n", encoding="utf-8")
    return {"faces": len(faces), "images": len(written), "converted": converted, "removed": removed,
            "groups": {name: info["count"] for name, info in groups.items()}, "skipped": skipped}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--source", type=Path, default=DEFAULT_SOURCE, help="folder with <group>/<NNNN>-s<K>.jpg")
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    parser.add_argument("--format", choices=("avif", "jpg"), default="avif")
    parser.add_argument("--width", type=int, default=260)
    parser.add_argument("--quality", type=int, default=65, help="AVIF quality for sips (0-100)")
    args = parser.parse_args(argv)
    if not args.source.is_dir():
        print(f"No image folder at {args.source} (pass --source)", file=sys.stderr)
        return 2
    report = build(args.source, args.manifest, args.format, args.width, args.quality)
    print(json.dumps(report, indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
