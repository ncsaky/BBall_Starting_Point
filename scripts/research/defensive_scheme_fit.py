#!/usr/bin/env python3
"""Build three-season Stage 2 scheme evidence from local Basketball Index data and NBA releases.

From the repository root, using the same isolated Parquet reader as the rotation study:
    uv run --no-project --python 3.12 --with duckdb==2.0.1 \
        python scripts/research/defensive_scheme_fit.py [--fetch]

--fetch retrieves missing public archive files sequentially. Basketball Index inputs
are local. Output is private research derived from the inputs.
"""
from __future__ import annotations

import argparse
import csv
import gzip
import hashlib
import json
import math
import statistics
import time
import unicodedata
from collections import Counter, defaultdict
from pathlib import Path
from urllib.request import urlopen

import duckdb

ROOT = Path(__file__).resolve().parents[2]
CACHE = ROOT / "output/defensive-scheme-evidence"
OUTPUT = ROOT / "data/research/defensive_scheme_evidence.json"
BBI = ROOT / "data/research/bbi"
ROTATION = ROOT / "data/research/rotation_evidence.json"
COMBINE = ROOT / "data/research/draft_combine_2000_2025.json"
SEASONS = {2024: "2023-24", 2025: "2024-25", 2026: "2025-26"}
TEAM_ALIASES = {"BRK": "BKN", "CHO": "CHA", "PHO": "PHX"}
RELEASE = "https://github.com/sportsdataverse/sportsdataverse-data/releases/download"
SYNERGY = {
    "handoff_offense": ("handoff", "offensive"),
    "off_screen_offense": ("offscreen", "offensive"),
    "isolation_offense": ("isolation", "offensive"),
    "post_up_defense": ("postup", "defensive"),
    "isolation_defense": ("isolation", "defensive"),
    "pick_roll_handler_defense": ("prballhandler", "defensive"),
    "pick_roll_roller_defense": ("prrollman", "defensive"),
}
BBI_METRICS = {
    "ball_screen_aggression_index": "P&R Coverage Aggression",
    "ball_screen_versatility_index": "P&R Coverage Versatility",
    "help_activity_index": "Help Defensive Activity",
    "rim_attempts_defended_per_75": "Stable Rim DFGA Per 75 Possessions",
    "rim_share_contested_pct": "Percentage of Shots at Rim Contested",
    "role_adjusted_defensive_feet_per_min": "Matchup Adjusted Defensive Feet Per Minute",
    "guard_assignments_vs_centers_pct": "% of Time Guarding Centers",
    "center_assignments_vs_point_guards_pct": "% of Time Guarding Point Guards",
}


def assets(year):
    files = {
        "teams": ("nba_stats_team_season_stats", f"team_season_stats_{year}.parquet"),
        "players": ("nba_stats_player_season_stats", f"player_season_stats_{year}.parquet"),
        "team_hustle": ("nba_stats_hustle", f"leaguehustlestatsteam_regular-season_totals_{year}.parquet"),
        "player_hustle": ("nba_stats_hustle", f"leaguehustlestatsplayer_regular-season_totals_{year}.parquet"),
        "matchups": ("nba_stats_matchups", f"leagueseasonmatchups_regular-season_totals_{year}.parquet"),
        "position_matchups": ("nba_stats_matchups", f"matchupsrollup_regular-season_totals_{year}.parquet"),
    }
    return files | {
        metric: ("nba_stats_synergy", f"regular-season_{action}_{side}_totals_{year}.parquet")
        for metric, (action, side) in SYNERGY.items()
    }


def file_checksum(path):
    with path.open("rb") as source:
        return hashlib.file_digest(source, "sha256").hexdigest()


def public_assets(cache, fetch):
    result, provenance = {}, {}
    if fetch:
        cache.mkdir(parents=True, exist_ok=True)
    for year in SEASONS:
        result[year] = {}
        for label, (release, filename) in assets(year).items():
            url = f"{RELEASE}/{release}/{filename}"
            path = cache / filename
            if not path.is_file() and fetch:
                with urlopen(url, timeout=30) as response:
                    content = response.read()
                if not content.startswith(b"PAR1") or not content.endswith(b"PAR1"):
                    raise ValueError(f"Invalid Parquet download from {url}")
                path.write_bytes(content)
                time.sleep(1)
            if not path.is_file():
                raise FileNotFoundError(f"Missing {path}. Fetch with --fetch or copy from {url}")
            result[year][label] = path
            provenance[filename] = {"url": url, "sha256": file_checksum(path)}
    return result, provenance


def parquet(path):
    return duckdb.read_parquet(str(path))


def rows(relation):
    names = relation.columns
    return [dict(zip(names, row, strict=True)) for row in relation.fetchall()]


def indexed(source, key):
    result = {row[key]: row for row in source}
    if len(result) != len(source):
        raise ValueError(f"Duplicate {key} in source")
    return result


def round_number(value, places=4):
    return round(value, places) if value is not None else None


def ratio(num, den, scale=1):
    return round_number(scale * num / den) if den else None


def average_weighted(samples):
    if not samples:
        return None
    return ratio(sum(value * weight for value, weight in samples), sum(weight for _, weight in samples))


def nba_season(files):
    regular_advanced_totals = "season_type = 'regular-season' AND measure_type = 'advanced' AND per_mode = 'totals'"
    teams = indexed(rows(parquet(files["teams"]).filter(regular_advanced_totals)
                         .project("team_id, team_name, gp, poss, min")), "team_id")
    if len(teams) != 30 or any(row["gp"] != 82 or row["poss"] <= 0 for row in teams.values()):
        raise ValueError("Expected 30 completed NBA regular-season team rows")
    players = indexed(rows(parquet(files["players"]).filter(regular_advanced_totals)
                           .project("player_id, team_id, team_abbreviation, min, gp, poss")), "player_id")
    codes = {row["team_id"]: row["team_abbreviation"] for row in players.values()}
    team_hustle = indexed(rows(parquet(files["team_hustle"])
                               .project("team_id, min, screen_assists, screen_ast_pts")), "team_id")
    player_hustle = indexed(rows(parquet(files["player_hustle"])
                                 .project("player_id, player_name, team_id, min, g, screen_assists, screen_ast_pts")),
                            "player_id")
    if teams.keys() != team_hustle.keys() or teams.keys() != codes.keys():
        raise ValueError("NBA team IDs differ across sources")
    if sum(p["screen_assists"] for p in player_hustle.values()) != sum(
        t["screen_assists"] for t in team_hustle.values()
    ):
        raise ValueError("Player and team NBA Screen Assist totals disagree")
    team_result = {}
    for team_id, team in teams.items():
        code = codes[team_id]
        hustle = team_hustle[team_id]
        team_result[code] = {
            "team_name": team["team_name"], "games": team["gp"], "possessions": team["poss"],
            "team_minutes": team["min"], "tracking_team_minutes": hustle["min"], "screen_assists": hustle["screen_assists"],
            "screen_assist_points": hustle["screen_ast_pts"],
            "screen_assists_per_100": ratio(hustle["screen_assists"], team["poss"], 100),
        }
    player_result = {}
    for player_id, player in player_hustle.items():
        season = players.get(player_id)
        if season is None or season["poss"] <= 0:
            raise ValueError(f"Missing player possessions for NBA ID {player_id}")
        player_result[player_id] = {
            "player": player["player_name"], "nba_player_id": player_id,
            "last_team": codes[player["team_id"]], "games": player["g"], "minutes": player["min"],
            "possessions_on_court": season["poss"], "screen_assists": player["screen_assists"],
            "screen_assist_points": player["screen_ast_pts"],
            "screen_assists_per_100": ratio(player["screen_assists"], season["poss"], 100),
        }
    for metric in SYNERGY:
        source = parquet(files[metric])
        stints = rows(source.project("player_id, team_id, poss, pts"))
        if len({(p["player_id"], p["team_id"]) for p in stints}) != len(stints):
            raise ValueError(f"Duplicate player/team rows in {metric}")
        counts = source.aggregate("team_id, count(*) AS rows, sum(poss) AS poss, sum(pts) AS pts")
        by_team = indexed(rows(counts), "team_id")
        if teams.keys() != by_team.keys():
            raise ValueError(f"Missing team slice in {metric}")
        for team_id, stats in by_team.items():
            team = team_result[codes[team_id]]
            team.setdefault("synergy_qualifying_player_stints", {})[metric] = {
                "stints": stats["rows"], "endings": stats["poss"], "points": stats["pts"],
                "endings_per_100_team_possessions": ratio(stats["poss"], team["possessions"], 100),
                "points_per_ending": ratio(stats["pts"], stats["poss"]),
            }
        if metric in {"handoff_offense", "off_screen_offense"}:
            for stats in stints:
                player = player_result.get(stats["player_id"])
                if player is not None:
                    entries = player.setdefault("synergy_qualifying_offensive_stints", {})
                    entries.setdefault(metric, []).append({
                        "team": codes[stats["team_id"]], "endings": stats["poss"],
                        "points_per_ending": ratio(stats["pts"], stats["poss"]),
                    })
    for player in player_result.values():
        for action, stints in player.get("synergy_qualifying_offensive_stints", {}).items():
            stints.sort(key=lambda stint: stint["team"])
            player.setdefault("synergy_qualifying_endings_per_100_on_court", {})[action] = ratio(
                sum(stint["endings"] for stint in stints), player["possessions_on_court"], 100)
    return team_result, player_result


def load_bbi():
    roles_file = BBI / "tools/role_lab_defensive_player_seasons.json.gz"
    positions_file = BBI / "tools/progression_player_seasons.csv.gz"
    metrics_file = BBI / "values_recent.json.gz"
    for path in (roles_file, positions_file, metrics_file):
        if not path.is_file():
            raise FileNotFoundError(f"Link the local Basketball Index input at {path}")
    with gzip.open(roles_file, "rt", encoding="utf-8") as source:
        roles = json.load(source)
    with gzip.open(positions_file, "rt", encoding="utf-8") as source:
        positions = {(r["season"], int(r["nba_player_id"])): r["position"]
                     for r in csv.DictReader(source) if r["season"] in SEASONS.values() and r["nba_player_id"]}
    with gzip.open(metrics_file, "rt", encoding="utf-8") as source:
        metrics = json.load(source)["table"]
    roles_by_year = {}
    for year, season in SEASONS.items():
        roles_by_year[year] = {}
        for role in roles:
            if role["s"] != season or role["m"] <= 0 or not role["nba_player_id"]:
                continue
            player_id = role["nba_player_id"]
            keys = (role["player_id"], f"name:{role['player']}")
            values = {}
            for key, label in BBI_METRICS.items():
                table = metrics[f"{season}|{label}"]
                hit = next((table[candidate] for candidate in keys if candidate in table), None)
                if hit and hit[0] is not None and math.isfinite(hit[0]):
                    values[key] = hit[0]
            role_teams = [TEAM_ALIASES.get(team, team) for team in role["tm"]]
            roles_by_year[year][player_id] = {
                "player": role["player"], "role": role["r"], "teams": role_teams,
                "minutes": role["m"], "height": role["h"],
                "position": positions.get((season, player_id)), "values": values,
            }
    return roles_by_year, {str(p.relative_to(ROOT)): file_checksum(p)
                           for p in (roles_file, positions_file, metrics_file)}


def position_group(position):
    return {"PG": "G", "SG": "G", "SF": "F", "PF": "F", "C": "C"}.get(position)


def name_key(name):
    return "".join(c for c in unicodedata.normalize("NFKD", name.casefold()) if c.isascii() and c.isalnum())


def lane_agility_data():
    records = defaultdict(list)
    for row in json.loads(COMBINE.read_text(encoding="utf-8"))["players"]:
        if row["lane_agility_s"] is not None:
            records[name_key(row["name"])].append((row["year"], row["lane_agility_s"]))
    return {key: values[0] for key, values in records.items() if len(values) == 1}


def add_bbi_team_profiles(teams, players, roles, lane_agility, year):
    assigned = defaultdict(list)
    for player_id, role in roles.items():
        if len(role["teams"]) == 1 and player_id in players and role["teams"][0] == players[player_id]["last_team"]:
            assigned[role["teams"][0]].append(role)
    for code, team in teams.items():
        covered = assigned[code]
        total = sum(role["minutes"] for role in covered)
        bigs = [r for r in covered if r["role"] in {"Mobile Big", "Anchor Big"}]
        big_minutes = sum(r["minutes"] for r in bigs)
        combine = []
        for role in bigs:
            match = lane_agility.get(name_key(role["player"]))
            if match and match[0] < year:
                combine.append((match[1], role["minutes"]))
        combine_minutes = sum(minutes for _, minutes in combine)
        team["bbi_proxy"] = {
            "attributed_player_minutes": total,
            "minute_coverage_pct": ratio(total, 5 * team["team_minutes"], 100),
            "rotation_height_inches": average_weighted([(r["height"], r["minutes"]) for r in covered if r["height"]]),
            "big_height_inches": average_weighted([(r["height"], r["minutes"]) for r in bigs if r["height"]]),
            "big_minutes_per_100_player_minutes": ratio(big_minutes, total, 100),
            "big_lane_agility_covered_minutes_pct": ratio(combine_minutes, big_minutes, 100),
            "big_lane_agility_seconds": average_weighted(combine) if combine_minutes >= 0.45 * big_minutes else None,
            "mobile_share_of_big_minutes_pct": ratio(sum(r["minutes"] for r in bigs if r["role"] == "Mobile Big"),
                                                    big_minutes, 100),
        }
        for key in BBI_METRICS:
            group = covered
            if key.startswith("ball_screen_") or key in {"role_adjusted_defensive_feet_per_min",
                                                          "rim_attempts_defended_per_75",
                                                          "rim_share_contested_pct"}:
                group = bigs
            elif key.startswith("guard_assignments"):
                group = [r for r in covered if position_group(r["position"]) == "G"]
            elif key.startswith("center_assignments"):
                group = [r for r in covered if position_group(r["position"]) == "C"]
            sample = [(r["values"][key], r["minutes"]) for r in group if key in r["values"]]
            team["bbi_proxy"][key] = average_weighted(sample)
            team["bbi_proxy"][f"{key}_minutes"] = sum(weight for _, weight in sample)


def matchup_summary(numerators):
    return {
        "partial_possessions": round_number(numerators["partial_poss"]),
        "matchup_seconds": round_number(numerators["matchup_time_sec"]),
        "field_goal_attempts": numerators["matchup_fga"],
        "effective_field_goal_pct": ratio(numerators["matchup_fgm"] + 0.5 * numerators["matchup_fg3_m"],
                                          numerators["matchup_fga"], 100),
        "shooter_points_per_100_partial_possessions": ratio(numerators["player_pts"],
                                                            numerators["partial_poss"], 100),
    }


def add_nba_matchups(files, teams, players, roles):
    # Use the NBA's own positional grouping for the opponent. The defender's
    # listed position comes from the season-specific Basketball Index metadata.
    data = parquet(files["position_matchups"])
    totals = rows(data.filter("position = 'TOTAL'").project("def_player_id, matchup_fga, partial_poss"))
    position_rows = rows(data.filter("position != 'TOTAL'").project(
        "position, def_player_id, matchup_fga, matchup_fgm, matchup_fg3_m, partial_poss, percent_of_time"))
    by_group = defaultdict(Counter)
    by_team = defaultdict(Counter)
    for row in position_rows:
        player_id = row["def_player_id"]
        entry = roles.get(player_id)
        if not entry or not (group := position_group(entry["position"])):
            continue
        opponent = row["position"]
        stats = {key: row[key] for key in ("matchup_fga", "matchup_fgm", "matchup_fg3_m", "partial_poss")}
        by_group[group, opponent].update(stats)
        if len(entry["teams"]) == 1 and players.get(player_id, {}).get("last_team") == entry["teams"][0]:
            by_team[entry["teams"][0], group, opponent].update(stats)
    for team, result in teams.items():
        result["nba_assignment_proxy"] = {
            f"{defense}_defending_{offense}_partial_possession_pct": ratio(
                by_team[team, defense, offense]["partial_poss"],
                sum(by_team[team, defense, other]["partial_poss"] for other in ("G", "F", "C")), 100)
            for defense, offense in (("G", "C"), ("C", "G"))
        }
    group_result = {}
    for defense, offense in sorted(by_group):
        stats = by_group[defense, offense]
        group_result[f"{defense}_defending_{offense}"] = {
            "partial_possessions": round_number(stats["partial_poss"]),
            "share_of_defender_group_partial_possessions_pct": ratio(
                stats["partial_poss"], sum(by_group[defense, other]["partial_poss"]
                                           for other in ("G", "F", "C")), 100),
            "field_goal_attempts": stats["matchup_fga"],
            "effective_field_goal_pct": ratio(stats["matchup_fgm"] + 0.5 * stats["matchup_fg3_m"],
                                              stats["matchup_fga"], 100),
        }
    # Show selected cross-position pairs in context with their small sample sizes.
    pairs = {
        ("Victor Wembanyama", "Jalen Brunson"),
        ("Nikola Jokić", "Alex Caruso"),
        ("Nikola Jokic", "Alex Caruso"),
        ("Shai Gilgeous-Alexander", "Rudy Gobert"),
        ("Jalen Brunson", "Bam Adebayo"),
        ("Luka Dončić", "Al Horford"),
        ("Luka Doncic", "Al Horford"),
        ("Karl-Anthony Towns", "Josh Hart"),
    }
    matchups = parquet(files["matchups"])
    subset = rows(matchups.filter("matchup_time_sec >= 30").project(
        "off_player_name, def_player_name, partial_poss, matchup_time_sec, matchup_fga, matchup_fgm, "
        "matchup_fg3_m, player_pts"))
    named = []
    for row in subset:
        pair = row["off_player_name"], row["def_player_name"]
        if pair in pairs:
            named.append({"offense": pair[0], "defense": pair[1]} | matchup_summary(row))
    quality = matchups.aggregate("count(*) AS rows, sum(help_fga) AS help_fga, sum(help_fgm) AS help_fgm,"
                                 " sum(help_blk) AS help_blk").fetchall()[0]
    return {
        "by_position": group_result,
        "named_regular_season_matchups": sorted(named, key=lambda r: (r["offense"], r["defense"])),
        "nba_defenders_in_rollup": len(totals),
        "position_rollup_partial_possession_coverage_pct": ratio(
            sum(r["partial_poss"] for r in position_rows if r["def_player_id"] in roles and
                position_group(roles[r["def_player_id"]]["position"])),
            sum(r["partial_poss"] for r in totals), 100),
        "source_pair_rows": quality[0],
        "source_help_field_totals": dict(zip(("attempts", "makes", "blocks"), quality[1:], strict=True)),
    }


SOURCES = {
    "nba_terms": "https://www.nba.com/termsofuse",
    "nba_robots": "https://www.nba.com/robots.txt",
    "nba_team_hustle": "https://www.nba.com/stats/teams/hustle",
    "nba_player_hustle": "https://www.nba.com/stats/players/hustle",
    "nba_team_advanced": "https://www.nba.com/stats/teams/advanced",
    "nba_player_advanced": "https://www.nba.com/stats/players/advanced",
    "nba_hand_off": "https://www.nba.com/stats/teams/hand-off",
    "nba_off_screen": "https://www.nba.com/stats/teams/off-screen",
    "nba_ball_handler": "https://www.nba.com/stats/teams/ball-handler",
    "nba_roll_man": "https://www.nba.com/stats/teams/roll-man",
    "nba_post_up": "https://www.nba.com/stats/teams/playtype-post-up",
    "nba_isolation": "https://www.nba.com/stats/teams/isolation",
    "nba_matchup_example": "https://www.nba.com/game/sas-vs-nyk-0042500404/box-score?type=matchups",
    "nba_matchup_definition": "https://www.nba.com/news/lu-dorts-defensive-excellence-is-pushing-okc-to-the-next-level",
    "nba_combine": "https://www.nba.com/stats/draft/combine-strength-agility",
    "nba_guide": "https://cdn.nba.com/manage/2026/10/2026-27-NBA-Guide_v2.pdf",
    "bbi": "https://www.bball-index.com/data-tools-package/",
    "bbi_defensive_roles": "https://www.bball-index.com/defensive-roles/",
    "bbi_terms": "https://www.bball-index.com/legal/terms-and-conditions/",
    "github_terms": "https://docs.github.com/en/site-policy/github-terms/github-terms-of-service",
    "league_switching": "https://alldlls.com/mavericks/nba-isolation-looks-different-10-years-stats-mid-range/",
    "boston_2024": "https://www.nba.com/news/nba-finals-film-study-how-will-the-celtics-defend-luka-doncic",
    "denver_2025": "https://www.nba.com/news/film-study-can-new-additions-help-nuggets-defense",
    "okc_2025": "https://www.nba.com/news/finals-film-study-thunder-pacers-game-2",
    "okc_memphis_2025": "https://www.si.com/nba/thunder/onsi/news/film-breakdown-okc-thunder-defense-suffocated-grizzlies-game-1",
    "spurs_2026": "https://www.nba.com/news/starting-5-as-finals-return-to-msg-knicks-staying-present-amid-history",
    "tracking_archive_article": "https://www.neilball.org/p/nba-released-player-tracking-data-for-2025-26-season",
    "tracking_archive_download": "https://downloads.neilball.org/NBA-2025-26-Available-Tracking.zip",
    "finals_game_2_book": "https://statsdmz.nba.com/pdfs/20260605/20260605_NYKSAS_book.pdf",
    "finals_game_3_book": "https://statsdmz.nba.com/pdfs/20260608/20260608_SASNYK_book.pdf",
    "miami_switch_december_2025": "https://www.nba.com/heat/news/coup-notebook-101-heat-deep-dive-tyler-herro-return-profile-121225",
    "knicks_2026": "https://www.nba.com/news/finals-film-study-game-3-2026-finals",
    "knicks_hawks_post_double": "https://www.nba.com/news/knicks-hawks-2026-playoffs-first-round-game-5-takeaways",
    "suns_thunder_post_double": "https://www.nba.com/news/3-things-to-watch-thunder-suns-game-4",
    "miami_zone_2024": "https://www.nba.com/news/power-rankings-2023-24-week-16",
    "miami_zone_2024_rate": "https://www.basketballpoetry.com/p/1-stat-explaining-every-first-round",
    "houston_zone_2026": "https://www.nba.com/news/4-takeaways-from-rockets-early-season-success",
    "kings_zone_2025": "https://www.sportscasting.com/?p=1614398",
    "miami_zone_2025": "https://www.nba.com/news/offseason-power-rankings-east-2025",
    "miami_zone_2026": "https://www.nba.com/news/offseason-power-rankings-east-2026",
    "miami_zone_changes_2026": "https://www.nba.com/news/power-rankings-2025-26-week-24",
    "miami_team_screening": "https://www.miamiherald.com/sports/nba/miami-heat/article314323490.html",
    "miami_team_handoffs": "https://www.miamiherald.com/sports/nba/miami-heat/article313344337.html",
    "miami_full_season_actions": "https://www.aol.co.uk/articles/heat-suddenly-threat-east-giannis-143148000.html",
    "ball_screens_2024": "https://www.thescore.com/nba/news/2883055/how-modern-offenses-blend-old-school-tactics-with-new-age-skills",
    "screen_assist_definition": "https://www.nba.com/stats/help/glossary",
    "sis_ball_screens": "https://www.sportsinfosolutions.com/2025/11/11/heat-check-a-different-offensive-approach-than-any-other-team/",
    "aggression_variation": "https://www.lastnightinbasketball.com/nba-defenses-are-different-too/",
    "thibodeau": "https://staging-aws.sports.yahoo.com/nba/article/is-the-knicks-curveball-affecting-boston-behind-the-celtics-3-point-shooting-woes-192439329.html",
}


# Film-selected moments near the screen. NBA Game Pulse supplies positions and
# clocks. Its clock can differ slightly from the official event clock.
DEPTH_SAMPLES = (
    ("0042500402", 4, 504902, -1, 1626157, 1641705, "Karl-Anthony Towns",
     "Victor Wembanyama", "blitz", 29.6, 32.1, -2.5),
    ("0042500403", 2, 204333, 1, 1641705, 1628384, "Victor Wembanyama",
     "OG Anunoby", "switch", 21.1, 13.2, 7.9),
    ("0042500403", 4, 346150, -1, 1641705, 1626157, "Victor Wembanyama",
     "Karl-Anthony Towns", "roll with weak-side help due", 30.8, 27.3, 3.5),
)


def coordinate_depth_examples(verify_dir):
    result = []
    for game, quarter, clock, basket, screener, defender, screener_name, defender_name, film, *distances in DEPTH_SAMPLES:
        if verify_dir is not None:
            file = verify_dir / f"{game}-tracking.jsonl.gz"
            with gzip.open(file, "rt", encoding="utf-8") as source:
                for frame in map(json.loads, source):
                    if (frame["period"] == quarter and frame["game_clock_ms"] == clock
                            and frame["quality"]["all_ten_and_ball_observed"]):
                        break
                else:
                    raise ValueError(f"Missing expected tracking frame in {file}: {quarter}, {clock}")
            players = {p["player_id"]: p["xyz"] for p in frame["home_players"] + frame["away_players"] if p["on_court"]}
            screen_depth, defender_depth = [math.dist(players[pid][:2], (basket * 41.75, 0))
                                             for pid in (screener, defender)]
            observed = [round(screen_depth, 1), round(defender_depth, 1), round(screen_depth - defender_depth, 1)]
            if observed != distances:
                raise ValueError(f"Tracking depth changed for {game}, quarter {quarter}, {clock}: {observed}")
        result.append({
            "game_id": game, "quarter": quarter, "tracking_clock_ms": clock, "screener": screener_name,
            "screen_defender": defender_name, "film_description": film, "screener_distance_ft": distances[0],
            "defender_distance_ft": distances[1], "defender_ft_closer_to_rim_than_screener": distances[2],
            "film_source": "spurs_2026" if game.endswith("02") else "knicks_2026",
            "game_book_source": "finals_game_2_book" if game.endswith("02") else "finals_game_3_book",
            "tracking_source": "tracking_archive_article",
        })
    return result


def public_samples(verify_tracking=None):
    return {
        "league_switch_pct_of_ball_screens": {
            "source": "league_switching",
            "2023-24": 22.5, "2024-25": 24.6, "2025-26": 25.9,
            "2025-26_sample": "April 7 publication, before the regular season ended. Underlying screen counts unavailable.",
        },
        "coverage_and_screen_geometry": [
            {"season": "2023-24", "defense": "BOS", "coach": "Joe Mazzulla", "source": "boston_2024",
             "sample": "Two regular-season Boston-Dallas games, only screens for Luka Dončić.",
             "blitz_count": 2, "screen_count": 89, "blitz_pct": ratio(2, 89, 100)},
            {"season": "2024-25", "defense": "DEN", "coach": None, "source": "denver_2025",
             "sample": "Regular season, only Nikola Jokić as screener's defender, split-coach season.",
             "film_coverage": "at level", "screens_defended_per_100_player_possessions": 45.8,
             "points_per_chance": 1.02, "prior_season_points_per_chance": 0.93},
            {"season": "2024-25", "defense": "OKC", "coach": "Mark Daigneault", "source": "okc_memphis_2025",
             "sample": "Playoff Game 1 vs. Memphis.",
             "film_coverage": "switching and drop with Isaiah Hartenstein"},
            {"season": "2024-25", "defense": "IND", "coach": "Rick Carlisle", "source": "okc_2025",
             "sample": "Finals Game 2, Indiana's Tyrese Haliburton as screener's defender on a Cason Wallace slip.",
             "film_coverage": "hedge", "defender_distance_from_rim_ft_approx": 30,
             "screen_distance_from_rim_ft_game_average_for_sga": 30.3},
            {"season": "2025-26", "defense": "SAS", "coach": "Mitch Johnson", "source": "spurs_2026",
             "sample": "Finals Game 2, Wembanyama and the point-of-attack defender pressure Brunson.",
             "film_coverage": "blitz"},
        ],
        "tracking_depth_film_examples": coordinate_depth_examples(verify_tracking),
        "direct_switching_team_examples": [
            {"season": "2025-26", "team": "MIA", "coach": "Erik Spoelstra",
             "sample": "Dec. 12 team article; switched picks per 100 possessions, as reported; not a percent of screens.",
             "switches_per_100_possessions": 24.5, "points_per_switched_screen": 0.84, "source": "miami_switch_december_2025"},
        ],
        "screen_targeting": [
            {"season": "2023-24", "offense": "OKC", "ball_handler": "Shai Gilgeous-Alexander",
             "sample": "Regular season, screens received from guards", "screens": 941,
             "screens_per_100_player_possessions": 17.6, "points_per_direct_ending": 1.15, "source": "okc_2025"},
            {"season": "2024-25", "offense": "OKC", "ball_handler": "Shai Gilgeous-Alexander",
             "sample": "Regular season, screens received from guards", "screens": 1106,
             "screens_per_100_player_possessions": 20.4, "points_per_direct_ending": 1.14, "source": "okc_2025"},
            {"season": "2024-25", "offense": "OKC", "ball_handler": "Shai Gilgeous-Alexander",
             "sample": "Finals Games 1-2 with Haliburton as screener's defender",
             "screens": 22, "points_per_chance": 0.73, "source": "okc_2025"},
            {"season": "2024-25", "offense": "OKC", "ball_handler": "Shai Gilgeous-Alexander",
             "sample": "Finals Games 1-2 with Turner or Bryant as screener's defender",
             "direct_endings": 25, "points": 35, "points_per_direct_ending": 1.40, "source": "okc_2025"},
            {"season": "2025-26", "offense": "SAS", "screener": "Victor Wembanyama",
             "sample": "Finals Game 3. Ball screens with two teammates on the weak side, a spacing observation.",
             "screens": 35, "screens_with_two_weak_side_teammates": 16, "source": "knicks_2026"},
        ],
        "post_doubles": [
            {"season": "2023-24", "defense": "BOS", "coach": "Joe Mazzulla", "target": "Pascal Siakam",
             "sample": "Eastern Conference finals, Boston occasionally sent a second defender; count unpublished.",
             "source": "boston_2024"},
            {"season": "2025-26", "defense": "ATL", "coach": "Quin Snyder", "target": "Karl-Anthony Towns",
             "sample": "Playoff Game 5, Atlanta doubled in the second half and New York found open shots.",
             "source": "knicks_hawks_post_double"},
            {"season": "2025-26", "defense": "PHX", "coach": "Jordan Ott", "target": "Shai Gilgeous-Alexander",
             "sample": "Playoff Game 3, Oso Ighodaro came to double in the second quarter.",
             "source": "suns_thunder_post_double"},
        ],
        "zone": [
            {"season": "2023-24", "team": "MIA", "coach": "Erik Spoelstra", "rank": 1,
             "sample": "Full-season share rank stated retrospectively. In early February Utah ranked first in count.",
             "zone_pct": 13.4, "points_per_zone_possession": 1.02,
             "source": "miami_zone_2024_rate", "midseason_source": "miami_zone_2024"},
            {"season": "2024-25", "team": "MIA", "coach": "Erik Spoelstra", "rank": 1,
             "sample": "Full season, zone possession count about 50% higher than the next team.",
             "source": "miami_zone_2025"},
            {"season": "2025-26", "team": "MIA", "coach": "Erik Spoelstra", "rank": 1,
             "sample": "Full-season Synergy share of defensive possessions.", "zone_pct": 16.3,
             "source": "miami_zone_2026"},
            {"season": "2025-26", "team": "HOU", "coach": "Ime Udoka",
             "sample": "Nov. 7 snapshot. Synergy share of defensive possessions; Miami was second at 9.7%.",
             "zone_pct": 18.6, "source": "houston_zone_2026"},
            {"season": "2024-25", "team": "SAC", "coach": "Mike Brown",
             "sample": "First 31 games, Synergy zone possessions per game.",
             "zone_possessions_per_game": 2.29, "source": "kings_zone_2025"},
            {"season": "2024-25", "team": "SAC", "coach": "Doug Christie",
             "sample": "First eight games after taking over, Synergy zone possessions per game.",
             "zone_possessions_per_game": 3.25, "source": "kings_zone_2025"},
            {"season": "2025-26", "team": "MIA", "coach": "Erik Spoelstra",
             "sample": "First 55 games vs. next 20 in the April Power Rankings.",
             "zone_possessions_per_game_first_55": 8.7, "zone_possessions_per_game_next_20": 28.7,
             "source": "miami_zone_changes_2026"},
        ],
        "offensive_screen_counts": [
            {"season": "2024-25", "team": "MIA", "coach": "Erik Spoelstra", "source": "miami_team_screening",
             "sample": "Genius Sports, prior full season as reported by Miami Herald.", "screens_per_100": 68.9,
             "handoffs_per_100": 22.3, "handoff_source": "miami_team_handoffs"},
            {"season": "2025-26", "team": "MIA", "coach": "Erik Spoelstra", "source": "miami_team_screening",
             "sample": "Genius Sports, first 40 games, same story as the prior full season.", "screens_per_100": 18},
            {"season": "2025-26", "team": "MIA", "coach": "Erik Spoelstra", "source": "sis_ball_screens",
             "sample": "Sports Info Solutions, first 10 games, provider's ball-screen definition.",
             "ball_screens_per_100": 27.8},
            {"season": "2024-25", "team": "MIA", "coach": "Erik Spoelstra", "source": "sis_ball_screens",
             "sample": "Full season, Sports Info Solutions ball-screen definition.", "ball_screens_per_100": 99.9},
            {"season": "2024-25", "team": "MEM", "coach": None, "source": "sis_ball_screens",
             "sample": "Full season, Sports Info Solutions ball-screen definition.", "ball_screens_per_100": 63.4},
            {"season": "2024-25", "team": "DEN", "coach": None, "source": "sis_ball_screens",
             "sample": "Full season, Sports Info Solutions ball-screen definition.", "ball_screens_per_100": 77.1},
            {"season": "2024-25", "team": "GSW", "coach": "Steve Kerr", "source": "sis_ball_screens",
             "sample": "Full season, Sports Info Solutions ball-screen definition.", "ball_screens_per_100": 81.4},
            {"season": "2023-24", "team": None, "source": "ball_screens_2024",
             "sample": "League snapshot, Second Spectrum as reported by theScore.", "ball_screens_per_100": 68.8},
            {"season": "2025-26", "team": "MIA", "coach": "Erik Spoelstra", "source": "miami_full_season_actions",
             "sample": "Prior-season reference, Second Spectrum as reported by Nekias Duncan.",
             "ball_screens_per_100": 20.0, "off_ball_screens_per_100": 27.0, "handoffs_per_100": 5.7},
            {"season": "2025-26", "team": "MIL", "player": "Giannis Antetokounmpo", "source": "miami_full_season_actions",
             "sample": "Second Spectrum, per 100 with the player on the floor as reported by Nekias Duncan.",
             "ball_screens_set_per_100": 26.5, "off_ball_screens_set_per_100": 7.2},
        ],
    }


def lookup(record, path):
    for part in path:
        record = record.get(part, {})
    return None if isinstance(record, dict) else record


FITTED_METRICS = {
    key: ("bbi_proxy", key)
    for key in ("ball_screen_aggression_index", "ball_screen_versatility_index", "help_activity_index",
                "rim_attempts_defended_per_75", "guard_assignments_vs_centers_pct",
                "center_assignments_vs_point_guards_pct")
} | {
    key: ("nba_assignment_proxy", key)
    for key in ("G_defending_C_partial_possession_pct", "C_defending_G_partial_possession_pct")
} | {
    "screen_assists_per_100": ("screen_assists_per_100",),
    "handoff_endings_per_100": ("synergy_qualifying_player_stints", "handoff_offense", "endings_per_100_team_possessions"),
    "off_screen_endings_per_100": ("synergy_qualifying_player_stints", "off_screen_offense",
                                  "endings_per_100_team_possessions"),
    "isolation_defense_endings_per_100": ("synergy_qualifying_player_stints", "isolation_defense",
                                         "endings_per_100_team_possessions"),
}
ROSTER = ("rotation_height_inches", "big_height_inches", "big_minutes_per_100_player_minutes",
          "mobile_share_of_big_minutes_pct",
          "role_adjusted_defensive_feet_per_min", "big_lane_agility_seconds")


def ranks(numbers):
    ordered = sorted(enumerate(numbers), key=lambda row: row[1])
    result = [0.0] * len(numbers)
    offset = 0
    while offset < len(ordered):
        end = offset + 1
        while end < len(ordered) and ordered[end][1] == ordered[offset][1]:
            end += 1
        for index, _ in ordered[offset:end]:
            result[index] = (1 + offset + end) / 2
        offset = end
    return result


def correlation(x, y, rank=False):
    if len(x) < 3 or min(x) == max(x) or min(y) == max(y):
        return None
    return round_number(statistics.correlation(ranks(x), ranks(y)) if rank else statistics.correlation(x, y))


def evaluate(predictions, unit="teams"):
    actual = [y for _, y in predictions]
    predicted = [y for y, _ in predictions]
    return {
        unit: len(actual),
        "mean_absolute_error": round_number(statistics.mean(abs(x - y) for x, y in predictions)) if actual else None,
        "rank_correlation": correlation(predicted, actual, rank=True),
    }


def shrink(values, league):
    return (sum(values) + league) / (len(values) + 1)


def score_models(observations, metric_path):
    suitable = [r for r in observations if lookup(r, metric_path) is not None
                and (metric_path[0] not in {"bbi_proxy", "nba_assignment_proxy"}
                     or r["bbi_proxy"]["minute_coverage_pct"] >= 70)]
    known = [r for r in suitable if r["season"] != SEASONS[2026]]
    holdout = [r for r in suitable if r["season"] == SEASONS[2026]]
    baseline = statistics.mean(lookup(r, metric_path) for r in known)
    prior_by_team, prior_by_coach, prior_by_pair = defaultdict(list), defaultdict(list), defaultdict(list)
    for row in known:
        value = lookup(row, metric_path)
        prior_by_team[row["team"]].append(value)
        if coach := row["coach"]:
            prior_by_coach[coach].append(value)
            prior_by_pair[row["team"], coach].append(value)

    predictions = {}
    roster_models = {}
    for feature in ROSTER:
        pairs = [(r["bbi_proxy"][feature], lookup(r, metric_path)) for r in known
                 if r["bbi_proxy"][feature] is not None]
        x, y = zip(*pairs)
        slope, intercept = statistics.linear_regression(x, y)
        roster_models[feature] = {
            "training_teams": len(pairs), "intercept": round_number(intercept, 8),
            "slope": round_number(slope, 8), "training_pearson": correlation(x, y),
            "limits": [min(x), max(x)],
        }
    for row in holdout:
        team, coach = row["team"], row["coach"]
        team_prior = prior_by_team[team]
        coach_prior = prior_by_coach[coach]
        pair_prior = prior_by_pair[team, coach]
        estimates = {
            "league_mean": baseline,
            "team_history": shrink(team_prior, baseline),
            "coach_history": shrink(coach_prior, baseline),
            "same_coach_and_team_history": shrink(pair_prior, baseline),
        }
        for feature, model in roster_models.items():
            x = row["bbi_proxy"][feature]
            if x is not None:
                lower, upper = model["limits"]
                estimates[f"observed_roster_{feature}"] = model["intercept"] + model["slope"] * min(max(x, lower), upper)
        predictions[team] = {
            "coach": coach, "observed": lookup(row, metric_path),
            "prior_team_seasons": len(team_prior), "prior_coach_seasons": len(coach_prior),
            "prior_same_coach_team_seasons": len(pair_prior),
            "predictions": {k: round_number(v) for k, v in estimates.items()},
        }
    for feature, model in roster_models.items():
        pairs = [(r["bbi_proxy"][feature], lookup(r, metric_path)) for r in holdout
                 if r["bbi_proxy"][feature] is not None]
        x, y = zip(*pairs)
        model["holdout_pearson"] = correlation(x, y)
        model["holdout_league_mean_on_same_teams"] = evaluate([(baseline, value) for value in y])

    cohorts = {}
    for name, selected in (
        ("all", list(predictions.values())),
        ("same_coach_team_history", [r for r in predictions.values() if r["prior_same_coach_team_seasons"]]),
        ("known_coach_no_same_team_history", [r for r in predictions.values()
                                              if r["prior_coach_seasons"] and not r["prior_same_coach_team_seasons"]]),
        ("no_coach_history", [r for r in predictions.values() if not r["prior_coach_seasons"]]),
    ):
        if selected:
            cohorts[name] = {
                key: evaluate([(r["predictions"][key], r["observed"]) for r in selected if key in r["predictions"]])
                for key in sorted({key for r in selected for key in r["predictions"]})
            }
    annual_pairs = {}
    for earlier, later in ((2024, 2025), (2025, 2026)):
        by_year = {year: {r["team"]: r for r in suitable if r["season"] == SEASONS[year]}
                   for year in (earlier, later)}
        team_pairs = [(by_year[earlier][team], by_year[later][team])
                      for team in sorted(by_year[earlier].keys() & by_year[later].keys())]
        cohorts_for_year = {}
        for name, pairs in (
            ("all", team_pairs),
            ("same_coach", [(a, b) for a, b in team_pairs if a["coach"] and a["coach"] == b["coach"]]),
            ("different_named_coach", [(a, b) for a, b in team_pairs
                                       if a["coach"] and b["coach"] and a["coach"] != b["coach"]]),
        ):
            x = [lookup(a, metric_path) for a, _ in pairs]
            y = [lookup(b, metric_path) for _, b in pairs]
            cohorts_for_year[name] = {
                "team_pairs": len(pairs), "rank_correlation": correlation(x, y, rank=True),
                "mean_year_to_year_abs_change": round_number(statistics.mean(abs(a - b) for a, b in zip(x, y)))
                if pairs else None,
            }
        annual_pairs[f"{SEASONS[earlier]} to {SEASONS[later]}"] = cohorts_for_year
    return {
        "train_team_seasons": len(known), "training_league_mean": round_number(baseline),
        "test_by_team": predictions, "holdout_score": cohorts, "consecutive_years": annual_pairs,
        "retrospective_roster_models": roster_models,
    }


def fit_player_screen_assists(player_seasons, roles_by_year):
    history = defaultdict(Counter)
    positions = defaultdict(Counter)
    all_training = Counter()
    for year in (2024, 2025):
        for pid, row in player_seasons[year].items():
            count = {"assists": row["screen_assists"], "possessions": row["possessions_on_court"]}
            history[pid].update(count)
            pos = position_group(roles_by_year[year].get(pid, {}).get("position"))
            if pos:
                positions[pos].update(count)
            all_training.update(count)

    def screen_rate(tally):
        return ratio(tally["assists"], tally["possessions"], 100)

    league = screen_rate(all_training)
    records = []
    for pid, row in player_seasons[2026].items():
        if row["possessions_on_court"] < 1000:
            continue
        # Carry only previously observed position and production to the holdout.
        prior_pos = next((roles_by_year[y][pid]["position"] for y in (2025, 2024)
                          if pid in roles_by_year[y] and roles_by_year[y][pid]["position"]), None)
        position_rate = screen_rate(positions[position_group(prior_pos)]) if prior_pos else league
        old = history[pid]
        player_rate = (100 * old["assists"] + position_rate * 1000) / (old["possessions"] + 1000)
        records.append((row["screen_assists_per_100"], league, position_rate, player_rate, bool(old)))
    return {
        "training_league_rate": league,
        "training_rates_by_listed_position": {pos: screen_rate(positions[pos]) for pos in ("G", "F", "C")},
        "holdout_minimum_on_court_possessions": 1000,
        "historical_player_shrinkage_equivalent_possessions": 1000,
        "holdout": {
            label: {model: evaluate([(r[i], r[0]) for r in sample], unit="players")
                    for i, model in enumerate(("league", "prior_position", "prior_player_shrunk_to_position"), 1)}
            for label, sample in (
                ("all", records), ("returning", [r for r in records if r[-1]]),
                ("no_training_history", [r for r in records if not r[-1]]),
            )
        },
    }


def build(cache, fetch, verify_tracking=None):
    inputs, provenance = public_assets(cache, fetch)
    roles_by_year, local_provenance = load_bbi()
    coaches = json.loads(ROTATION.read_text(encoding="utf-8"))["coach_comparison"]["team_seasons"]
    lane_agility = lane_agility_data()
    team_seasons, player_seasons, matchup_seasons, league = {}, {}, {}, {}
    for year, season in SEASONS.items():
        teams, players = nba_season(inputs[year])
        roles = roles_by_year[year]
        add_bbi_team_profiles(teams, players, roles, lane_agility, year)
        matchup_seasons[season] = add_nba_matchups(inputs[year], teams, players, roles)
        player_seasons[year] = players
        for team, record in teams.items():
            record.update(team=team, season=season, coach=coaches[f"{year}|{team}"]["coach"])
        team_seasons[season] = teams
        possessions = sum(record["possessions"] for record in teams.values())
        screen_assists = sum(record["screen_assists"] for record in teams.values())
        league[season] = {
            "team_count": len(teams), "games": sum(record["games"] for record in teams.values()) // 2,
            "team_possessions": possessions, "screen_assists": screen_assists,
            "hustle_team_minute_coverage_pct": ratio(sum(r["tracking_team_minutes"] for r in teams.values()),
                                                     sum(r["team_minutes"] for r in teams.values()), 100),
            "screen_assists_per_100": ratio(screen_assists, possessions, 100),
            "player_hustle_rows": len(players), "bbi_defensive_player_seasons": len(roles),
            "synergy_qualifying_player_stints": {},
        }
        for metric in SYNERGY:
            summaries = [team["synergy_qualifying_player_stints"][metric] for team in teams.values()]
            endings = sum(row["endings"] for row in summaries)
            league[season]["synergy_qualifying_player_stints"][metric] = {
                "stints": sum(row["stints"] for row in summaries), "endings": endings,
                "endings_per_100_team_possessions": ratio(endings, possessions, 100),
                "points_per_ending": ratio(sum(row["points"] for row in summaries), endings),
            }

    team_rows = [r for teams in team_seasons.values() for _, r in sorted(teams.items())]
    tracking_and_film = public_samples(verify_tracking)
    switch_samples = tracking_and_film["league_switch_pct_of_ball_screens"]
    switch_prediction = statistics.mean(switch_samples[s] for s in (SEASONS[2024], SEASONS[2025]))
    return {
        "schema_version": 1,
        "purpose": "Private Stage 2 coach and possession research. No game settings or player ratings.",
        "training_seasons": [SEASONS[2024], SEASONS[2025]],
        "holdout_season": SEASONS[2026],
        "sources": SOURCES,
        "public_release_assets": provenance,
        "local_inputs_sha256": local_provenance | {
            str(path.relative_to(ROOT)): file_checksum(path) for path in (ROTATION, COMBINE)
        },
        "measurement_notes": {
            "screen_assists": "Made baskets directly credited to a screen, divided by NBA advanced possessions. "
                              "Players use on-court possessions across all their teams.",
            "synergy_qualifying_player_stints": "NBA.com/Synergy player by team stints above the source's play-type "
                                               "minimum. Team aggregates omit unqualified stints. Defensive sums "
                                               "count player attributions and cannot be deduplicated by team possession. "
                                               "Endings involve a shot, free throws or turnover; initiating actions are "
                                               "a different denominator.",
            "assignments": "Season-aggregated assignments, including initial matchups, switches and other "
                           "changes. Effective FG% uses attributed field goal attempts. No intervention or hunt labels.",
            "bbi": "Minutes-weighted private-research aggregates from the local Basketball Index input. "
                   "Team summaries exclude multi-team players. Coverage aggression and help are indexes. "
                   "Rim defended attempts and contested share are proxies for rim involvement.",
            "unobserved_team_season_rate_fields": [
                "ball_screen_drop", "ball_screen_switch", "ball_screen_hedge_show", "ball_screen_blitz_trap",
                "ball_screen_at_level", "side_ball_screen_ice", "post_double", "strong_side_help",
                "weak_side_help", "zone", "post_switch_mismatch_hunt", "all_screens_set", "all_handoffs",
                "all_off_ball_screens",
            ],
            "lane_agility": "Draft combine drill time in seconds, lower means faster. Unambiguous normalized name "
                            "matches only. Held-out roster mixtures use realized minutes. The feature is withheld "
                            "when under 45% of attributed big-man minutes have a combine time.",
            "coach": "Named head coach for single-coach seasons from the rotation research. "
                     "Mixed seasons counted at team level with a null coach.",
        },
        "public_samples": tracking_and_film,
        "league": league,
        "teams": team_seasons,
        "players_screening": {SEASONS[year]: {str(pid): row for pid, row in players.items()}
                              for year, players in player_seasons.items()},
        "matchups": matchup_seasons,
        "fit": {
            "coach_and_team_rule": "Average earlier matching team, coach, or coach-team observations with one "
                                   "training-league-mean observation for shrinkage; fall back to that mean.",
            "roster_rule": "One straight line per feature using training seasons. Uses realized holdout roster features "
                           "for a retrospective diagnostic; clips values to the training feature limits.",
            "bbi_and_assignment_minimum_attributed_minutes_pct": 70,
            "league_switch_share_reference": {
                "older_seasons_mean_pct": switch_prediction, "observed_april_2026_pct": switch_samples[SEASONS[2026]],
                "absolute_difference_pp": round_number(abs(switch_samples[SEASONS[2026]] - switch_prediction)),
            },
            "team_metrics": {key: score_models(team_rows, path) for key, path in FITTED_METRICS.items()},
            "player_screen_assists": fit_player_screen_assists(player_seasons, roles_by_year),
        },
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cache", type=Path, default=CACHE)
    parser.add_argument("--output", type=Path, default=OUTPUT)
    parser.add_argument("--fetch", action="store_true", help="Download missing public Parquet releases")
    parser.add_argument("--verify-tracking", type=Path, help="Verify the film samples from local tracking files")
    args = parser.parse_args()
    result = build(args.cache, args.fetch, args.verify_tracking)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    temp_path = args.output.with_suffix(args.output.suffix + ".tmp")
    temp_path.write_text(json.dumps(result, indent=2, sort_keys=True, allow_nan=False) + "\n", encoding="utf-8")
    temp_path.replace(args.output)
    print(f"Wrote {args.output} from {len(result['public_release_assets'])} public season tables")


if __name__ == "__main__":
    main()
