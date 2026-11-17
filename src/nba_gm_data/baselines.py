"""Keep established saves on the starting universe they were created against."""
from functools import lru_cache
import gzip
import json
from pathlib import Path
from typing import Any

DIRECTORY = Path(__file__).resolve().parents[2] / "data/canonical/baselines"

@lru_cache(maxsize=8)
def _read_baseline(path: str) -> dict[str, Any]:
    with gzip.open(path, "rt", encoding="utf-8") as handle:
        return json.load(handle)

def baseline_for_save(canonical: dict[str, Any], save: dict[str, Any]) -> dict[str, Any]:
    if save.get("version") != "league_save_v1":
        return canonical
    current = (canonical.get("meta") or {}).get("starting_data_version")
    if not current:
        return canonical
    version = (save.get("meta") or {}).get("starting_data_version")
    if version == current:
        return canonical
    directory = Path(canonical.get("_baseline_directory") or DIRECTORY)
    with (directory / "registry.json").open(encoding="utf-8") as handle:
        registry = json.load(handle)
    version = version or registry.get("hashes", {}).get((save.get("meta") or {}).get("canonical_hash")) or registry["legacy_version"]
    filename = registry.get("versions", {}).get(version)
    if not filename or Path(filename).name != filename:
        raise ValueError(f"Starting data {version} is unavailable for this save.")
    baseline = _read_baseline(str(directory / filename))
    # Some startup repair helpers can add fallback scaffolds. Keep that work
    # off the shared archive object so one save cannot change another's input.
    from copy import deepcopy
    return {**baseline, "meta": dict(baseline.get("meta") or {}),
            "_baseline_identity": (str(directory / filename), (directory / filename).stat().st_mtime_ns),
            "draft_picks": deepcopy(baseline.get("draft_picks") or [])}
