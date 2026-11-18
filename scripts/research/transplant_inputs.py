#!/usr/bin/env python3
"""Copy named inputs from a fresh build into the tracked player-inputs file, leaving every other input untouched.

A full rebuild of data/canonical/player_inputs_2026_27.json also picks up unrelated drift in the local evidence (for
example newly listed heights for a few players). When a change is meant to affect only some inputs (a mapping fix for
one input), build to a scratch path, then transplant just those inputs so the diff stays attributable:

    PYTHONPATH=src .venv/bin/python scripts/build_player_inputs.py --no-report --output /tmp/build/player_inputs_2026_27.json
    PYTHONPATH=src .venv/bin/python scripts/research/transplant_inputs.py /tmp/build/player_inputs_2026_27.json S20

Writes data/canonical/player_inputs_2026_27.json (local, git-ignored) and its tracked .json.gz copy, byte-reproducibly
(the same canonical JSON and gzip settings as build_player_inputs.py). Replaces a symlinked json with a real file.
"""
from __future__ import annotations

import gzip
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from nba_gm_data.input_estimator import canonical_json  # noqa: E402

TRACKED = ROOT / "data/canonical/player_inputs_2026_27.json"


def load(path: Path) -> dict:
    if path.suffix == ".gz":
        with gzip.open(path, "rt", encoding="utf-8") as handle:
            return json.load(handle)
    return json.loads(path.read_text())


def main() -> int:
    source = load(Path(sys.argv[1]))
    ids = sys.argv[2:]
    if not ids:
        raise SystemExit("name at least one input id to transplant")
    target = load(TRACKED.with_name(TRACKED.name + ".gz"))
    changed = 0
    for pid, doc in target["players"].items():
        fresh = source["players"].get(pid)
        if not fresh:
            continue
        for iid in ids:
            if doc["inputs"].get(iid) != fresh["inputs"].get(iid):
                doc["inputs"][iid] = fresh["inputs"][iid]
                changed += 1
    payload = canonical_json(target)
    if TRACKED.is_symlink():
        TRACKED.unlink()
    TRACKED.write_text(payload, encoding="utf-8")
    with open(str(TRACKED) + ".gz", "wb") as raw, gzip.GzipFile(fileobj=raw, mode="wb", compresslevel=9, mtime=0, filename="") as gz:
        gz.write(payload.encode("utf-8"))
    print(f"transplanted {', '.join(ids)}: {changed} player records changed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
