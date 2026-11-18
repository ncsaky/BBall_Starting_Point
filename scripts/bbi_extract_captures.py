#!/usr/bin/env python3
"""Convert the five BBX-2 captures to offline research tables."""
import argparse
import csv
import gzip
import io
import json
from collections import defaultdict
from datetime import datetime
from pathlib import Path

from bbi_extract_tools import CANONICAL, DATA, ROOT, REVIEWED_NAMES, Export, name_key

ROSTERS = [
    ROOT / "data/research/nba_official_rosters_2026_07_28.json",
    ROOT / "data/research/nba_official_rosters_2026_10_13.json",
]
CAPTURES = {
    "progression": "fanspo_tools/progression/bbi_progression_all.json.gz",
    "playoff_talent": "fanspo_tools/playoff_talent/bbi_playoff_talent_3yr.json.gz",
    "lineup_explorer": "fanspo_tools/lineup_explorer/bbi_lineup_explorer_2013_2026.json.gz",
    "xpoints_lineups": "fanspo_tools/xpoints/bbi_xpoints_lineups_2025_26.json.gz",
    "role_labs": "tools/role_labs/bbi_role_labs.json.gz",
}
ALIASES = {name_key(alias): name_key(name) for alias, name in REVIEWED_NAMES.items()}


def identity_key(name):
    key = name_key(name)
    return ALIASES.get(key, key)


def load_capture(root, name, inventory):
    relative = CAPTURES[name]
    with gzip.open(root / relative, "rt", encoding="utf-8") as handle:
        capture = json.load(handle)
    inventory["captures"][name] = {
        "file": relative, "source": capture["source"], "retrieved_at": capture["retrieved_at"],
    }
    return capture


class PlayerCrosswalk:
    def __init__(self, canonical, rosters):
        canonical_names = defaultdict(list)
        for player in json.loads(canonical.read_text(encoding="utf-8"))["players"]:
            canonical_names[identity_key(player["name"])].append(player)
        nba_to_game = defaultdict(set)
        game_to_nba = defaultdict(set)
        for path in rosters:
            for team in json.loads(path.read_text(encoding="utf-8"))["teams"]:
                for row in team["roster"]:
                    if not row.get("nba_player_id") or not row.get("birthdate"):
                        continue
                    birthdate = datetime.strptime(row["birthdate"], "%b %d, %Y").date().isoformat()
                    for player in canonical_names[identity_key(row["name"])]:
                        if player.get("birthdate") == birthdate:
                            nba_to_game[row["nba_player_id"]].add(player["id"])
                            game_to_nba[player["id"]].add(row["nba_player_id"])
        self.game_ids = {
            nba_id: game_id
            for nba_id, games in nba_to_game.items()
            if len(games) == 1
            for game_id in games
            if len(game_to_nba[game_id]) == 1
        }
        self.by_season_name = defaultdict(set)

    def observe(self, season, name, nba_id):
        self.by_season_name[season, identity_key(name)].add(nba_id)

    def season_id(self, season, name):
        candidates = self.by_season_name.get((season, identity_key(name)), ())
        return next(iter(candidates)) if len(candidates) == 1 else None

    def fields(self, nba_id, name):
        return {"nba_player_id": nba_id, "player": name, "player_id": self.game_ids.get(nba_id)}


class MatchCoverage:
    def __init__(self):
        self.players = {}
        self.references = 0
        self.matched_references = 0
        self.unresolved_names = set()
        self.unresolved_references = 0

    def add(self, player):
        nba_id, game_id = player["nba_player_id"], player["player_id"]
        if nba_id is None:
            self.unresolved_names.add(identity_key(player["player"]))
            self.unresolved_references += 1
        else:
            self.players[nba_id] = game_id
        self.references += 1
        self.matched_references += game_id is not None

    def summary(self):
        matched = sum(game_id is not None for game_id in self.players.values())
        return {
            "unique_nba_ids": len(self.players),
            "matched_nba_ids": matched,
            "nba_id_match_rate": matched / len(self.players) if self.players else None,
            "player_references": self.references,
            "matched_references": self.matched_references,
            "reference_match_rate": self.matched_references / self.references if self.references else None,
            "unresolved_name_keys": len(self.unresolved_names),
            "unresolved_nba_id_references": self.unresolved_references,
        }


def csv_table(export, name, columns, rows):
    out = io.StringIO(newline="")
    writer = csv.DictWriter(out, columns, lineterminator="\n")
    writer.writeheader()
    count = 0
    for row in rows:
        writer.writerow(row)
        count += 1
    export.write(name + ".csv", out.getvalue().encode("utf-8"), count)


def progression(capture, export, crosswalk, coverage):
    league = capture["league"]
    players = capture["players"]
    measure_keys = [metric["column"] for metric in league["grade_columns"]]
    metadata = ["season", "team", "minutes", "age", "offensive_role", "defensive_role",
                "rotation_role", "position", "advanced_position"]
    key = ["nba_player_id", "player", "player_id", "season"]
    export.json("progression_metrics", league["grade_columns"])
    export.json("progression_league_distributions", league["league_distributions"])
    export.json("progression_players", [
        {**crosswalk.fields(player["player_id"], player["player_name"]),
         **{k: player[k] for k in ("headshot", "all_seasons", "active_filters", "peer_population_size")}}
        for player in players.values()
    ])

    def rows(kind):
        for raw_id, player in players.items():
            nba_id, name = player["player_id"], player["player_name"]
            if str(nba_id) != raw_id or player["grade_columns"] != league["grade_columns"]:
                raise ValueError(f"Unexpected progression metadata for {name}")
            identity = crosswalk.fields(nba_id, name)
            for row in player["seasons_data"]:
                if kind == "grades":
                    coverage.add(identity)
                    crosswalk.observe(row["season"], name, nba_id)
                    bio = {k: v for k, v in row.items() if k not in ("grades", "percentiles", "ranks")}
                    bio["minutes"] = bio.pop("mins")
                    bio["advanced_position"] = bio.pop("advancedPosition")
                else:
                    bio = {"season": row["season"]}
                yield {**identity, **bio, **row[kind]}

    csv_table(export, "progression_player_seasons", key[:-1] + metadata + measure_keys, rows("grades"))
    for kind in ("percentiles", "ranks"):
        csv_table(export, f"progression_{kind}", key + measure_keys, rows(kind))


def playoff_talent(capture, export, crosswalk, coverage):
    meta, table = capture["meta"], capture["table"]
    if table["count"] != len(table["rows"]) or meta["row_count"] != table["count"]:
        raise ValueError("Playoff Talent row count disagrees with metadata")
    rename = {"player_id": "nba_player_id", "player_name": "player", "Season": "window"}
    keys = ["nba_player_id", "player", "player_id", "window", "offensive_role", "off_role"]
    export.json("playoff_talent_reference", meta)

    def rows():
        for raw in table["rows"]:
            row = {rename.get(k, k): v for k, v in raw.items()}
            identity = crosswalk.fields(row["nba_player_id"], row["player"])
            coverage.add(identity)
            yield {**row, **identity}

    csv_table(export, "playoff_talent_windows",
              keys + [k for k in meta["col_meta"] if rename.get(k, k) not in keys], rows())


def lineup_players(players, crosswalk, coverage):
    if len(players) != 5:
        raise ValueError("Expected five source members per lineup")
    fields = {}
    for slot, (nba_id, name) in enumerate(players, start=1):
        identity = crosswalk.fields(nba_id, name)
        coverage.add(identity)
        fields.update({f"{key}_{slot}": value for key, value in identity.items()})
    return fields


def lineups(capture, export, crosswalk, coverage, *, xpoints=False):
    prefix = "xpoints_lineups" if xpoints else "lineup_explorer"
    columns = {"season": None, "team": None}
    rows = []
    reference = {}
    if xpoints:
        for team, groups in capture["teams"].items():
            reference[team] = {group: len(entries) for group, entries in groups.items()}
            for group, entries in groups.items():
                for row in entries:
                    players = list(zip(map(int, row["lineup_ids"]), row["lineup_names"], strict=True))
                    values = {k: v for k, v in row.items() if k not in ("lineup_ids", "lineup_names")}
                    rows.append({"season": "2025-26", "team": team, "group": group,
                                 **lineup_players(players, crosswalk, coverage), **values})
    else:
        for season, block in capture["seasons"].items():
            reference[season] = {k: v for k, v in block.items() if k != "data"}
            for row in block["data"]:
                players = [(p["id"], p["name"]) for p in row["players"]]
                for nba_id, name in players:
                    crosswalk.observe(season, name, nba_id)
                values = {k: v for k, v in row.items() if k not in ("team", "players", "roles")}
                roles = {f"role_{k}": v for k, v in row["roles"].items()}
                rows.append({"season": season, "team": row["team"],
                             **lineup_players(players, crosswalk, coverage), **values, **roles})
    for row in rows:
        columns.update(dict.fromkeys(row))
    export.json(prefix + "_reference", reference)
    if xpoints:
        csv_table(export, prefix, columns, rows)
    else:
        # The full explorer exceeds 5 MB even as gzip. Both parts use one header.
        csv_table(export, prefix + "_2013_2019", columns,
                  (row for row in rows if row["season"] < "2019-20"))
        csv_table(export, prefix + "_2019_2026", columns,
                  (row for row in rows if row["season"] >= "2019-20"))


def role_labs(capture, export, crosswalk, coverages):
    for side in ("offensive", "defensive"):
        lab = capture[f"{side}_role_lab"]
        prefix = f"role_lab_{side}"
        if side == "defensive" and len(lab["sh"]) != len(lab["players"]):
            raise ValueError("Defensive Role Lab history blend is not aligned with player rows")
        rows = []
        for index, entry in enumerate(lab["players"]):
            nba_id = crosswalk.season_id(entry["s"], entry["n"])
            identity = crosswalk.fields(nba_id, entry["n"])
            coverages[prefix].add(identity)
            row = {**identity, **entry}
            if side == "defensive":
                row["sh"] = lab["sh"][index]
            rows.append(row)
        export.json(prefix + "_player_seasons", rows)
        export.json(prefix + "_reference", {k: v for k, v in lab.items() if k not in ("players", "sh")})


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--captures", type=Path, default=DATA / "captures")
    parser.add_argument("--output", type=Path, default=DATA / "tools")
    parser.add_argument("--canonical", type=Path, default=CANONICAL)
    parser.add_argument("--rosters", type=Path, nargs="+", default=ROSTERS)
    args = parser.parse_args()
    export = Export(args.output)
    crosswalk = PlayerCrosswalk(args.canonical, args.rosters)
    coverage = defaultdict(MatchCoverage)
    inventory = {
        "captures": {},
        "canonical": args.canonical.name,
        "official_rosters": [path.name for path in args.rosters],
        "crosswalk_players": len(crosswalk.game_ids),
    }
    progression(load_capture(args.captures, "progression", inventory), export, crosswalk,
                coverage["progression"])
    playoff_talent(load_capture(args.captures, "playoff_talent", inventory), export, crosswalk,
                   coverage["playoff_talent"])
    for dataset in ("lineup_explorer", "xpoints_lineups"):
        lineups(load_capture(args.captures, dataset, inventory), export, crosswalk,
                coverage[dataset], xpoints=dataset == "xpoints_lineups")
    role_labs(load_capture(args.captures, "role_labs", inventory), export, crosswalk, coverage)
    inventory["files"] = [
        {"file": item["file"], "rows": item["rows"],
         "bytes": (args.output / item["file"]).stat().st_size}
        for item in export.inventory
    ]
    inventory["match_coverage"] = {key: counts.summary() for key, counts in coverage.items()}
    export.json("bbx2_inventory", inventory)


if __name__ == "__main__":
    main()
