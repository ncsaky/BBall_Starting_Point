"""Verify and optionally publish the two-forward correction against immutable V4."""
import argparse
import gzip
import hashlib
import json
from pathlib import Path

from nba_gm_data.ingest import build_universe
from nba_gm_data.roster_alignment import STARTING_DATA_VERSION
from nba_gm_data.save import player_display_attribute_summary
from nba_gm_data.schema import to_plain
from nba_gm_data.sim import player_feature_vector
from nba_gm_data.storage import write_outputs
from verify_roster_alignment import archive_candidate

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "output/forward-tuning-2026-10-23"
PREVIOUS = "2026-10-23-talent-v4"
VERSION = "2026-10-23-forward-tuning-v5"
NAMES = {"Aaron Gordon", "Julius Randle"}
DERIVED_TABLES = {
    "draft_board_entries", "team_strategic_states", "player_asset_valuations",
    "player_contract_market_profiles", "player_contract_preferences",
    "extension_candidates", "free_agent_candidates",
}


def hashes(paths):
    return {str(path): hashlib.sha256(path.read_bytes()).hexdigest() for path in paths}


def protected_saves():
    return hashes(path for path in (ROOT / "saves").rglob("*")
                  if path.is_file() and path.suffix in {".json", ".sqlite", ".sqlite3"})


def previous():
    with gzip.open(ROOT / "data/canonical/baselines" / f"{PREVIOUS}.json.gz", "rt") as handle:
        return json.load(handle)


def overrides():
    rows = json.loads((ROOT / "data/overrides/trait_overrides.json").read_text())["post_alignment_players"]
    return [row for row in rows if row["player_name"] in NAMES]


def verify_scope(old, new):
    assert set(old) == set(new)
    assert new["meta"]["starting_data_version"] == VERSION
    assert {k: v for k, v in old["meta"].items() if k != "starting_data_version"} == {
        k: v for k, v in new["meta"].items() if k != "starting_data_version"}
    players = {p["name"]: p["id"] for p in new["players"]}
    allowed = {(players[row["player_name"]], key): (value, row["evidence_urls"])
               for row in overrides() for key, value in row["traits"].items()}
    before = {(t["player_id"], t["trait_key"]): t for t in old["traits"]}
    after = {(t["player_id"], t["trait_key"]): t for t in new["traits"]}
    assert len(before) == len(old["traits"]) == len(after) == len(new["traits"])
    assert set(before) == set(after)
    changed = {key for key in before if before[key] != after[key]}
    assert changed == set(allowed), changed.symmetric_difference(allowed)
    for key, (value, urls) in allowed.items():
        trait = after[key]
        assert trait["value"] == value["value"], key
        assert trait["components"]["manual_calibration"]["evidence_urls"] == urls, key
    for key in old.keys() - DERIVED_TABLES - {"meta", "traits"}:
        assert old[key] == new[key], key
    # Rating-dependent team needs and markets can move, but unrelated players'
    # direct ability and health valuation must not change with the environment.
    old_assets = {v["player_id"]: v for v in old["player_asset_valuations"]}
    for asset in new["player_asset_valuations"]:
        prior = old_assets[asset["player_id"]]
        assert asset["health_risk"] == prior["health_risk"]
        if asset["player_id"] not in {players[name] for name in NAMES}:
            assert asset["on_court_value"] == prior["on_court_value"], asset["player_id"]
    return len(changed)


def measurements(canonical):
    fixed = {"meta": canonical["meta"], "players": [
        {**p, "minutes_projection": 24} for p in canonical["players"]], "traits": canonical["traits"]}
    assets = {v["player_id"]: v for v in canonical["player_asset_valuations"]}
    output = {}
    for player in canonical["players"]:
        if player["name"] not in NAMES:
            continue
        features = player_feature_vector(canonical, player).features
        output[player["name"]] = {
            "display": player_display_attribute_summary(canonical, player["id"]),
            "fixed24_display": player_display_attribute_summary(fixed, player["id"]),
            "sim": {k: features[k] for k in (
                "impact", "shot_creation", "scoring_usage", "spacing", "rim_pressure",
                "passing", "defensive_events", "rim_deterrence", "defensive_weak_link")},
            "asset": assets[player["id"]],
        }
    return output


def verify(publish=False):
    protected = protected_saves()
    archives = hashes((ROOT / "data/canonical/baselines").glob("*.json.gz"))
    universe = build_universe(ROOT)
    new = to_plain(universe)
    old = previous()
    changed = verify_scope(old, new)
    assert new == to_plain(build_universe(ROOT)), "Rebuild is not deterministic"
    before, after = measurements(old), measurements(new)
    assert protected_saves() == protected, "Playable files changed"
    assert hashes(Path(path) for path in archives) == archives, "Prior archive changed"
    if publish:
        assert STARTING_DATA_VERSION == VERSION
        archive_candidate(new)
        write_outputs(universe, ROOT / "data/canonical")
        with gzip.open(ROOT / "data/canonical/baselines" / f"{VERSION}.json.gz", "rt") as handle:
            assert json.load(handle) == new
        assert json.loads((ROOT / "data/canonical/universe_2026_27_offseason.json").read_text()) == new
    assert protected_saves() == protected
    assert hashes(Path(path) for path in archives) == archives
    report = {"status": "passed", "published": publish, "version": VERSION,
              "changed_trait_count": changed, "before": before, "after": after,
              "protected_save_hashes": protected, "prior_archive_hashes": archives,
              "scope": "Two player profiles only; derived markets/needs rebuilt. No rating-formula, growth, prospect, contract, pick, medical or existing-save migration change."}
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "verification.json").write_text(json.dumps(report, indent=2, sort_keys=True) + "\n")
    print(json.dumps({"status": report["status"], "published": publish, "changed_traits": changed,
                      "overall": {name: {"before": before[name]["display"]["overall"],
                                          "after": after[name]["display"]["overall"]} for name in sorted(NAMES)}}, indent=2))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--publish", action="store_true")
    verify(parser.parse_args().publish)
