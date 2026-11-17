"""Verify and optionally publish four researched player corrections, preserving saves."""
import argparse
import gzip
import hashlib
import json
from pathlib import Path

from audit_roster_floor import decompose
from nba_gm_data.ingest import build_universe
from nba_gm_data.roster_alignment import STARTING_DATA_VERSION
from nba_gm_data.save import player_display_attribute_summary
from nba_gm_data.schema import to_plain
from nba_gm_data.storage import write_outputs
from verify_roster_alignment import archive_candidate, protection

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "output/player-tuning-2026-10-23"


def hashes(paths):
    return {str(path): hashlib.sha256(path.read_bytes()).hexdigest() for path in paths}


def verify(publish=False):
    protected = protection()
    archives = hashes((ROOT / "data/canonical/baselines").glob("*.json.gz"))
    universe = build_universe(ROOT)
    new = to_plain(universe)
    with gzip.open(ROOT / "data/canonical/baselines/2026-10-23-roster-v2.json.gz", "rt") as handle:
        old = json.load(handle)
    overrides = json.loads((ROOT / "data/overrides/trait_overrides.json").read_text())["post_alignment_players"]
    players = {p["name"]: p for p in new["players"]}
    allowed = {(players[row["player_name"]]["id"], key): value["value"]
               for row in overrides for key, value in row["traits"].items()}
    old_traits = {(t["player_id"], t["trait_key"]): t for t in old["traits"]}
    for trait in new["traits"]:
        key = trait["player_id"], trait["trait_key"]
        if key in allowed:
            assert trait["value"] == allowed[key], key
            assert trait["components"]["manual_calibration"]["evidence_urls"], key
        else:
            assert trait == old_traits[key], key
    for key in ("players", "contracts", "draft_picks", "roster_slots", "player_health_profiles",
                "player_health_states", "injury_events", "draft_classes", "draft_prospects", "draft_prospect_traits"):
        assert new[key] == old[key], key
    contexts = [{"players": [{**p, "minutes_projection": 24} for p in data["players"]],
                 "traits": data["traits"], "_allow_internal_caches": True} for data in (old, new)]
    grades = {row["player_name"]: {
        label: player_display_attribute_summary(context, players[row["player_name"]]["id"])
        for label, context in zip(("before", "after"), contexts)} for row in overrides}
    floor = {}
    for directory in ("roster-alignment-2026-10-23", "talent-supply-performance-2026-10-23"):
        for seed in (17, 29):
            files = sorted((ROOT / "output" / directory / f"career-{seed}").glob("census-*.json"))
            if len(files) < 2:
                continue
            snapshots = [json.loads(path.read_text()) for path in files]
            floor[f"{directory}:{seed}"] = {
                "endpoints": decompose(snapshots[0], snapshots[-1]),
                "intervals": [decompose(a, b) for a, b in zip(snapshots, snapshots[1:])],
                "source_files": [str(path.relative_to(ROOT)) for path in files]}
    assert protection() == protected, "Playable saves changed during verification"
    assert hashes(Path(path) for path in archives) == archives, "Published archives changed"
    OUT.mkdir(parents=True, exist_ok=True)
    if publish:
        assert new["meta"]["starting_data_version"] == STARTING_DATA_VERSION
        archive_candidate(new)
        write_outputs(universe, ROOT / "data/canonical")
        with gzip.open(ROOT / "data/canonical/baselines" / f"{STARTING_DATA_VERSION}.json.gz", "rt") as handle:
            assert json.load(handle) == new
        assert json.loads((ROOT / "data/canonical/universe_2026_27_offseason.json").read_text()) == new
    assert protection() == protected
    assert hashes(Path(path) for path in archives) == archives
    report = {"status": "passed", "published": publish, "version": STARTING_DATA_VERSION,
              "player_grades_fixed24": grades, "floor_decomposition": floor,
              "protected_save_hashes": protected, "prior_archive_hashes": archives,
              "scope": "Only the listed trait overrides change; derived rating-dependent markets are rebuilt. No growth, generator, overall, medical or save migration change."}
    (OUT / "verification.json").write_text(json.dumps(report, indent=2, sort_keys=True) + "\n")
    print(json.dumps({key: report[key] for key in ("status", "published", "version", "player_grades_fixed24")}, indent=2))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--publish", action="store_true")
    verify(parser.parse_args().publish)
