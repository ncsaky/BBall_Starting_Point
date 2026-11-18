#!/usr/bin/env python3
"""Extract data from locally saved Basketball Index tools without running JavaScript."""
from __future__ import annotations

import argparse
import ast
import csv
import gzip
import io
import json
import re
import unicodedata
from collections import defaultdict
from html.parser import HTMLParser
from itertools import groupby
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data/research/bbi"
CANONICAL = ROOT / "data/canonical/universe_2026_27_offseason.json"
LEVELS = (50, 80, 90)
BOUNDS = [f"p{level}_{edge}" for level in LEVELS for edge in ("low", "high")]
OFF_HISTORY_SLOTS = (0, 1, 2, 3, 4, 5, 6, 8, 9, 10, 11, 12, 18)
# Established in the leaderboard importer and league trait imports.
REVIEWED_NAMES = {
    "Jimmy Butler": "Jimmy Butler III",
    "Carlton Carrington": "Bub Carrington",
    "Ron Holland": "Ronald Holland II",
}
COMPOSITES = (("XO", "xo_lebron", "offPoss"), ("XD", "xd_lebron", "defPoss"),
              ("OT", "overall_talent", "poss"))
HISTORY_COLUMNS = [
    "player", "player_id", "season", "age", "minutes", "possessions", "role",
    "metric", "actual", "forecast_sample_actual", "projected_1yr",
    "actual_minus_projected", *BOUNDS,
]
FORWARD_COLUMNS = [
    "player", "player_id", "reference_season", "reference_age", "reference_minutes",
    "target_season", "target_age", "years_ahead", "metric", "projected", *BOUNDS,
]


def null_for_nonfinite(_token):
    # The inline JavaScript uses NaN in some numeric arrays for missing values.
    return None


JSON_DECODER = json.JSONDecoder(parse_constant=null_for_nonfinite)


class Capture(HTMLParser):
    def __init__(self, path):
        super().__init__(convert_charrefs=True)
        self.scripts = []
        self.methodology = []
        self.script = None
        self.div_depth = 0
        self.feed(path.read_text(encoding="utf-8"))
        self.close()

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag == "script":
            self.script = (attrs, [])
        if tag == "div":
            if self.div_depth:
                self.div_depth += 1
            elif attrs.get("id") == "mthContent":
                self.div_depth = 1
        if tag == "br" and self.div_depth:
            self.methodology.append("\n")

    def handle_endtag(self, tag):
        if tag == "script" and self.script is not None:
            attrs, chunks = self.script
            self.scripts.append((attrs, "".join(chunks)))
            self.script = None
        if self.div_depth:
            if tag == "div":
                self.div_depth -= 1
            if tag in {"div", "p", "h2", "h3"}:
                self.methodology.append("\n")

    def handle_data(self, data):
        if self.script is not None:
            self.script[1].append(data)
        elif self.div_depth:
            self.methodology.append(data)

    def json_blocks(self):
        return {attrs["id"]: JSON_DECODER.decode(body) for attrs, body in self.scripts
                if attrs.get("type") == "application/json"}

    def inline_code(self):
        return "\n".join(body for attrs, body in self.scripts
                         if not attrs.get("src") and attrs.get("type") != "application/json")


def literal(code, name, *, python_literal=False):
    match = re.search(r"\bconst\s+" + re.escape(name) + r"\s*=\s*", code)
    if match is None:
        raise ValueError(f"Missing inline constant {name}")
    tail = code[match.end():]
    if python_literal:
        return ast.literal_eval(tail.split(";", 1)[0])
    return JSON_DECODER.raw_decode(tail)[0]


def name_key(name):
    text = unicodedata.normalize("NFKD", name.casefold())
    return "".join(letter for letter in text if letter.isalnum())


class PlayerIds:
    def __init__(self, path):
        self.index = defaultdict(set)
        players = json.loads(path.read_text(encoding="utf-8"))["players"]
        for player in players:
            self.index[name_key(player["name"])].add(player["id"])
        for alias, name in REVIEWED_NAMES.items():
            self.index[name_key(alias)].update(self.index.get(name_key(name), ()))

    def get(self, name):
        ids = self.index.get(name_key(name), ())
        return next(iter(ids)) if len(ids) == 1 else None

    def fields(self, name):
        return {"player": name, "player_id": self.get(name)}


class Export:
    def __init__(self, path):
        self.path = path
        self.inventory = []

    def write(self, name, raw, rows=None, players=None):
        if len(raw) >= 5_000_000:
            name += ".gz"
            compressed = io.BytesIO()
            with gzip.GzipFile(fileobj=compressed, mode="wb", mtime=0) as handle:
                handle.write(raw)
            raw = compressed.getvalue()
        if len(raw) >= 5_000_000:
            raise ValueError(f"{name} exceeds 5 MB even when compressed")
        self.path.mkdir(parents=True, exist_ok=True)
        (self.path / name).write_bytes(raw)
        if rows is not None:
            info = {"file": name, "rows": rows}
            if players:
                info.update(unique_players=len(players), matched_players=sum(players.values()))
            self.inventory.append(info)

    def json(self, name, data):
        rows = data if isinstance(data, list) else []
        players = {row["player"]: bool(row["player_id"]) for row in rows
                   if isinstance(row, dict) and "player" in row and "player_id" in row}
        raw = json.dumps(data, ensure_ascii=False, separators=(",", ":"), allow_nan=False)
        self.write(name + ".json", (raw + "\n").encode(), len(rows) if isinstance(data, list) else 1, players)

    def csv(self, name, columns, rows):
        out = io.StringIO(newline="")
        writer = csv.writer(out, lineterminator="\n")
        writer.writerow(columns)
        count = 0
        players = {}
        for row in rows:
            writer.writerow(row)
            count += 1
            players[row[0]] = bool(row[1])
        self.write(name + ".csv", out.getvalue().encode(), count, players)


def season_at(year):
    return f"{year}-{(year + 1) % 100:02d}"


def minus(actual, projected):
    return round(actual - projected, 8) if actual is not None and projected is not None else None


def bounds(projected, quantiles, horizon, multiplier=1):
    if projected is None:
        return [None] * len(BOUNDS)
    return [round(projected + sign * multiplier * quantiles[f"q{level}"][horizon - 1], 8)
            for level in LEVELS for sign in (-1, 1)]


def defensive_interval_multiplier(minutes):
    return max(1, 0.865 + 175.7 / (minutes + 200)) if minutes is not None else 1


def skill_history(data, metrics, slots, defensive, ids, off_roles):
    offset = 4 if defensive else 3
    count = len(metrics)
    for player, history in data["hist"].items():
        retro = {row[1]: row for row in data["retro"][player]}
        minutes_at_age = {row[0]: row[2] for row in history}
        for row in history:
            age, season, minutes = row[:3]
            predictions = retro.get(season)
            role = row[3] if defensive else off_roles.get(player, {}).get(season)
            multiplier = defensive_interval_multiplier(minutes_at_age.get(age - 1)) if defensive else 1
            for i, (metric, slot) in enumerate(zip(metrics, slots, strict=True)):
                actual = row[offset + slot]
                predicted = predictions[3 + i] if predictions else None
                model_actual = predictions[3 + count + i] if predictions else None
                yield [player, ids.get(player), season, age, minutes, None, role, metric,
                       actual, model_actual, predicted, minus(actual, predicted),
                       *bounds(predicted, data["conf_q"][metric], 1, multiplier)]


def skill_forward(data, metrics, defensive, ids):
    for player, vectors in data["preds"].items():
        age, season, minutes = data["hist"][player][-1][:3]
        if age != data["ref_ages"][player]:
            raise ValueError(f"Unexpected projection reference age for {player}")
        multiplier = defensive_interval_multiplier(minutes) if defensive else 1
        for metric, forecasts in zip(metrics, vectors, strict=True):
            for horizon, predicted in enumerate(forecasts, 1):
                yield [player, ids.get(player), season, age, minutes,
                       season_at(int(season[:4]) + horizon), age + horizon, horizon,
                       metric, predicted, *bounds(predicted, data["conf_q"][metric], horizon, multiplier)]


def composite_history(history, metric, quantiles, roles, ids):
    for player, entry in history.items():
        retro = {row[1]: row[2] for row in entry["r"]}
        for age, season, actual, possessions in entry["h"]:
            predicted = retro.get(season)
            yield [player, ids.get(player), season, age, None, possessions,
                   roles.get(player, {}).get(season), metric, actual, None, predicted,
                   minus(actual, predicted), *bounds(predicted, quantiles, 1)]


def growth(capture, export, ids):
    code = capture.inline_code()
    keys = """D DEF_DATA CS PROJ XD_CONF_Q XD_HIST XD_DEV XO_HIST XO_LEBRON XO_CONF_Q XO_DEV
              XO_ROLE ROLE_PCT_XO OT_PCT OT_CONF_Q OT_HIST OT_LEBRON ROLE_PCT_OT XD_LEBRON
              ACC_BREAKDOWN DEV COACH_DEV TV_ROSTER_DEFAULT TV_WEIGHTS TV_NBA_TEAMS ROLE_PCT""".split()
    src = {key: literal(code, key) for key in keys}
    off, defense = src["D"], src["DEF_DATA"]
    off_metrics = literal(code, "SHORT_T_ALL", python_literal=True)
    def_metrics = literal(code, "DEF_T", python_literal=True)[:-1]
    all_metrics = off_metrics + def_metrics
    roles = src["XO_ROLE"]
    def_roles = {p: {r[1]: r[3] for r in history} for p, history in defense["hist"].items()}

    def history_rows():
        yield from skill_history(off, off_metrics, OFF_HISTORY_SLOTS, False, ids, roles)
        yield from skill_history(defense, def_metrics, range(len(def_metrics)), True, ids, roles)
        for prefix, metric, _ in COMPOSITES:
            history_roles = def_roles if prefix == "XD" else roles
            yield from composite_history(src[prefix + "_HIST"], metric, src[prefix + "_CONF_Q"],
                                         history_roles, ids)

    def forward_rows():
        yield from skill_forward(off, off_metrics, False, ids)
        yield from skill_forward(defense, def_metrics, True, ids)
        for prefix, metric, _ in COMPOSITES:
            for player, row in src[prefix + "_LEBRON"]["players"].items():
                age, season, minutes = off["hist"][player][-1][:3]
                for horizon, predicted in enumerate(row["proj"], 1):
                    yield [player, ids.get(player), season, age, minutes,
                           season_at(int(season[:4]) + horizon), age + horizon, horizon,
                           metric, predicted, *bounds(predicted, src[prefix + "_CONF_Q"], horizon)]

    export.csv("growth_history", HISTORY_COLUMNS, history_rows())
    export.csv("growth_forward", FORWARD_COLUMNS, forward_rows())
    export.json("growth_history_extra", [
        {**ids.fields(player), "season": row[1],
         "unlabeled_offense_slots": {str(i): row[3 + i] for i in range(19) if i not in OFF_HISTORY_SLOTS}}
        for player, history in off["hist"].items() for row in history
    ])
    export.json("growth_player_roles", [
        {**ids.fields(player), "season": season, "offensive_role": role}
        for player, seasons in roles.items() for season, role in seasons.items()
    ])
    export.json("growth_development", [
        {**ids.fields(player), "seasons": row["s"], "minutes": row["m"],
         "offense_low_minutes_flag": bool(off["low_min"].get(player)),
         "defense_low_minutes_flag": bool(defense["low_min"].get(player)),
         "mean_skill_delta": row["o"], "offense_skill_delta": row["o_off"],
         "defense_skill_delta": row["o_def"],
         "metric_deltas": dict(zip(src["DEV"]["metrics"], row["d"], strict=True)),
         "xo_lebron_delta": src["XO_DEV"].get(player), "xd_lebron_delta": src["XD_DEV"].get(player),
         "overall_talent_delta": (round(src["XO_DEV"][player] + src["XD_DEV"][player], 8)
                                  if player in src["XO_DEV"] and player in src["XD_DEV"] else None)}
        for player, row in src["DEV"]["players"].items()
    ])
    export.json("growth_coach_development", [
        {"coach": coach, "team_seasons": row["ts"], "player_seasons": row["ps"], "minutes": row["m"],
         "mean_skill_delta": row["o"], "offense_skill_delta": row["o_off"],
         "defense_skill_delta": row["o_def"],
         "metric_deltas": dict(zip(src["COACH_DEV"]["metrics"], row["d"], strict=True)),
         "xo_lebron_delta": row.get("o_xo"), "xd_lebron_delta": row.get("o_xd"),
         "overall_talent_delta": row.get("o_ot")}
        for coach, row in src["COACH_DEV"]["coaches"].items()
    ])

    def by_metric(row, offense, defensive):
        return dict(zip(all_metrics, row[offense] + row[defensive], strict=True))

    coach_teams = []
    coach_players = []
    for coach, seasons in src["CS"].items():
        for season, row in seasons.items():
            base = {"coach": coach, "season": season, "team": row["team"]}
            coach_teams.append({
                **base, "minutes": row["min"], "players": row["n"],
                "actual": by_metric(row, "tao", "tad"), "projected": by_metric(row, "tpo", "tpd"),
                "source_delta": by_metric(row, "tdo", "tdd"),
            })
            for p in row["players"]:
                actual = by_metric(p, "ao", "ad")
                projected = by_metric(p, "po", "pd")
                coach_players.append({
                    **base, **ids.fields(p["name"]), "age": p["age"], "minutes": p["min"],
                    "actual": actual, "projected": projected,
                    "actual_minus_projected": {m: minus(actual[m], projected[m]) for m in all_metrics},
                })
    export.json("growth_coach_teams", coach_teams)
    export.json("growth_coach_players", coach_players)
    growth_projection_grid(src, export, ids, all_metrics)

    export.json("growth_model_reference", {
        "metric_labels": {**literal(code, "ALL_TL", python_literal=True),
                          "xo_lebron": "Offensive Talent", "xd_lebron": "Defensive Talent",
                          "overall_talent": "Overall Talent"},
        "skills": {metric: {"sorted_reference": data["sorted"][metric],
                            "interval_half_widths": data["conf_q"][metric],
                            "evaluation": data["eval"][metric]}
                   for data in (off, defense) for metric in data["sorted"]},
        "accuracy_breakdown": src["ACC_BREAKDOWN"],
        "defensive_role_percentiles": src["ROLE_PCT"],
        "offensive_role_percentiles": src["ROLE_PCT_XO"],
        "overall_role_percentiles": src["ROLE_PCT_OT"],
        "overall_percentiles": src["OT_PCT"],
        "composite_interval_half_widths": {metric: src[prefix + "_CONF_Q"] for prefix, metric, _ in COMPOSITES},
        "composite_coefficients": {metric: src[prefix + "_LEBRON"]["betas"]
                                   for prefix, metric, _ in COMPOSITES if prefix != "OT"},
        "low_minutes_threshold": literal(code, "MIN_THRESHOLD"),
        "roster_team_codes": src["TV_NBA_TEAMS"],
    })
    methodology = "\n".join(line.strip() for line in "".join(capture.methodology).splitlines() if line.strip())
    if not methodology:
        raise ValueError("Growth Curve methodology is missing")
    export.write("growth_methodology.txt", (methodology + "\n").encode(), 1)


def growth_projection_grid(src, export, ids, metrics):
    grid = src["PROJ"]
    roster, weights = src["TV_ROSTER_DEFAULT"], src["TV_WEIGHTS"]
    export.json("growth_team_view_roster", [
        {**ids.fields(name), "team": roster.get(name), "minutes_weight": weights.get(name)}
        for name in dict.fromkeys([*roster, *weights])
    ])
    export.json("growth_projection_grid", [
        {**ids.fields(name), "target_season": season, "years_ahead": int(horizon),
         "reference_age": meta[0], "reference_minutes": meta[1], "offensive_role": meta[2],
         "advanced_position": meta[3], "rotation_role": meta[4], "low_minutes": bool(meta[5]),
         "skill_forecasts": dict(zip(metrics, off + defense, strict=True))}
        for horizon, season in grid["seasons"].items()
        for name, meta, off, defense in zip(grid["players"], grid["meta"], grid["vals_off"][horizon],
                                            grid["vals_def"][horizon], strict=True)
    ])
    export.json("growth_composite_baselines", [
        {**ids.fields(name), "metric": metric, "baseline": row["baseline"], "role": row["role"],
         "possessions": row[possessions]}
        for prefix, metric, possessions in COMPOSITES
        for name, row in src[prefix + "_LEBRON"]["players"].items()
    ])


def injury_time_summary(observations, half_life):
    # Reproduce the page's default weighted Kaplan–Meier table. A censored
    # observation leaves the risk set at its last day but is not a return.
    rows = sorted((row for row in observations if row[0] is not None and row[0] >= 0),
                  key=lambda row: (row[0], -row[1]))
    weighted = [(days, returned, 0.5 ** (age / half_life) if half_life > 0 else 1)
                for days, returned, age, _ in rows]
    risk = sum(row[2] for row in weighted)
    sum_squared = sum(row[2] ** 2 for row in weighted)
    effective_n = risk ** 2 / sum_squared if sum_squared else 0
    survival = 1
    quantiles = dict.fromkeys((25, 50, 75, 90))
    for day, group in groupby(weighted, key=lambda row: row[0]):
        returned_weight = censored_weight = 0
        for _, returned, weight in group:
            if returned:
                returned_weight += weight
            else:
                censored_weight += weight
        if risk > 0 and returned_weight > 0:
            survival *= 1 - returned_weight / risk
        risk -= returned_weight + censored_weight
        for percentile, value in quantiles.items():
            if value is None and survival <= 1 - percentile / 100 + 1e-12:
                quantiles[percentile] = day
    n = len(rows)
    returned = sum(bool(row[1]) for row in rows)
    return {"spell_count": n, "returned_count": returned, "censored_count": n - returned,
            "returned_share": round(returned / n, 8) if n else None,
            "effective_sample_size": round(effective_n, 8),
            **{f"days_p{p}": value for p, value in quantiles.items()}}


def injuries(capture, export, ids):
    blocks = capture.json_blocks()
    data = blocks["payload"]
    panel = blocks["players"]
    observations = data["obs"]
    half_life = data["meta"]["defaultHalfLife"]
    buckets = []
    examples = []
    for row in data["buckets"]:
        key = {"level": row["level"], "bucket": row["name"]}
        buckets.append({**key, "category": row["cat"], "surgery_share": row["surg"],
                        "observation_ids": row["ids"],
                        **injury_time_summary([observations[i] for i in row["ids"]], half_life)})
        for player, month, days, diagnosis, qualifier in row["ex"]:
            examples.append({**key, **ids.fields(player), "month": month, "days": days,
                             "diagnosis": diagnosis, "source_qualifier": qualifier})
    export.json("injury_time_out", buckets)
    export.json("injury_observations", [
        {"observation_id": i, "days": days, "return_logged": bool(returned),
         "recency_years": recency, "start_year": year}
        for i, (days, returned, recency, year) in enumerate(observations)
    ])
    export.json("injury_examples", examples)
    export.json("injury_long_term", data["longterm"])
    export.json("injury_short_term", data["shortterm"]["buckets"])
    export.json("injury_recurrence", data["recurrence"])
    export.json("injury_risk_validation", list(panel["riskValidation"].values()))
    export.json("injury_players", [
        {**ids.fields(p["name"]), "player_key": p["key"],
         **{k: p.get(k) for k in ("pos", "height_in", "team", "team25", "team27", "experience",
                              "totals", "recovery")}}
        for p in panel["players"]
    ])
    for key in ("history", "seasons"):
        export.json(f"injury_player_{key}", [
            {**ids.fields(p["name"]), "player_key": p["key"], **row}
            for p in panel["players"] for row in p[key]
        ])
    export.json("injury_player_risk", [
        {**ids.fields(p["name"]), "player_key": p["key"], "body_part": part, **row}
        for p in panel["players"] for part, row in p["risk"].items()
    ])
    export.json("injury_player_projections", [
        {**p["proj"], **ids.fields(p["name"])} for p in panel["players"] if p["proj"] is not None
    ])
    durability = data["durability"]
    export.json("injury_durability_projections", [
        {**row, **ids.fields(row["player"])} for row in durability["projections"]
    ])
    teams = data["teams"]
    export.json("injury_teams", [
        {**row, "worst": {**row["worst"], **ids.fields(row["worst"]["player"])}
         if row["worst"] else row["worst"],
         "core_players": [{**p, **ids.fields(p["player"])} for p in row["core_players"]]}
        for row in teams["teams"]
    ])
    export.json("injury_model_reference", {
        **{k: data[k] for k in ("meta", "aging", "recovery")},
        "shortterm": {k: v for k, v in data["shortterm"].items() if k != "buckets"},
        "durability": {k: v for k, v in durability.items() if k != "projections"},
        "teams": {k: v for k, v in teams.items() if k != "teams"},
        "player_panel": {k: v for k, v in panel.items() if k not in ("players", "riskValidation")},
    })


MINUTES_PLAYER = {
    "n": "player", "t": "team", "ro": "rotation_role", "pk": "draft_pick",
    "miss": "games_missed_to_injury", "gh": "health_only_games_available",
    "hc": "healthy_rotation_mpg", "mpg": "projected_mpg", "gp": "projected_games_played",
    "g10": "games_played_p10", "g90": "games_played_p90", "tot": "projected_minutes",
    "t10": "minutes_p10", "t90": "minutes_p90", "own": "own_role_minutes",
    "inj": "teammate_injury_minutes_delta", "gt": "garbage_time_dnp_minutes_delta",
    "lost": "minutes_lost_to_own_absences", "m25": "mpg_2025_26", "mm": "unconstrained_model_mpg",
    "ca": "coach_preference_mpg_delta", "cy": "seasons_under_coach", "du": "durability_label",
}
MINUTES_TEAM = {
    "miss": "games_missed_to_injury", "inj": "teammate_injury_minutes",
    "gt": "garbage_time_minutes", "bench": "bench_minutes", "top8": "top_eight_minutes_pct",
}
TALENT_PLAYER = {
    "n": "player", "t": "team", "pg": "position_group", "pk": "draft_pick",
    "tal": "overall_talent", "o": "offensive_talent", "d": "defensive_talent",
    "op": "offense_role_percentile", "dp": "defense_role_percentile",
    "or": "projected_offensive_role", "dr": "projected_defensive_role",
    "om": "projected_offensive_role_mix", "dm": "projected_defensive_role_mix",
    "oh": "offensive_role_2025_26", "dh": "defensive_role_2025_26",
    "ohv": "talent_in_held_offensive_role", "dhv": "talent_in_held_defensive_role",
    "src": "talent_source", "slot": "team_rotation_slot",
    "lr": "profile_pool_league_rank", "lra": "full_pool_league_rank",
    "prof": "slot_profile", "q": "within_profile_rank", "tier": "profile_tier",
    "dl": "slot_delta", "min": "projected_minutes", "mpg": "projected_mpg",
    "hc": "healthy_rotation_mpg", "ro": "rotation_role",
}
TALENT_TEAM = {
    "name": "team_name", "net": "slot_delta_all", "net5": "slot_delta_1_to_5",
    "net6": "slot_delta_6_to_11", "tal8": "top_eight_talent_sum",
    "wtal": "weighted_talent", "hi": "higher_talent_slot_count",
    "lo": "lower_talent_slot_count", "n": "player_count",
}


def minutes_talent(capture, export, ids):
    blocks = capture.json_blocks()
    minutes, talent = blocks["data"], blocks["data-k"]
    for data, tool, player_fields, team_fields in (
        (minutes, "minutes", MINUTES_PLAYER, MINUTES_TEAM),
        (talent, "talent_grid", TALENT_PLAYER, TALENT_TEAM),
    ):
        export.json(f"{tool}_players", [
            {**{player_fields.get(k, k): v for k, v in row.items()},
             "player_id": ids.get(row["n"])}
            for row in data["players"]
        ])
        export.json(f"{tool}_teams", [
            {"team": team, **{team_fields.get(k, k): v for k, v in row.items()}}
            for team, row in data["teams"].items()
        ])
    export.json("talent_grid_reference", {k: talent[k] for k in ("edges", "ns", "n")})


def role_lab_status(capture, name):
    code = capture.inline_code()
    pattern = re.search(r"fetch\('([^']+)-'\+i\+'\.txt'", code)
    if not pattern or capture.json_blocks():
        raise ValueError(f"Unexpected payload format for {name}")
    count = literal(code, "PARTS")
    return {"capture": f"bbi_tool_{name}.html", "embedded_player_rows": 0,
            "external_payload_parts": [f"{Path(pattern[1]).name}-{i}.txt" for i in range(count)]}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--captures", type=Path, default=DATA / "captures/tools")
    parser.add_argument("--output", type=Path, default=DATA / "tools")
    parser.add_argument("--canonical", type=Path, default=CANONICAL)
    args = parser.parse_args()

    def load(name):
        return Capture(args.captures / f"bbi_tool_{name}.html")

    export = Export(args.output)
    ids = PlayerIds(args.canonical)
    growth(load("growth_curve"), export, ids)
    injuries(load("injuries"), export, ids)
    minutes_talent(load("minutes_talent_2026_27"), export, ids)

    defensive = load("defensive_role_lab")
    export.json("defensive_role_height_coefficients", [
        {"role": role, "height_coefficient_per_standard_deviation": coefficient, "t_statistic": t}
        for role, coefficient, t in literal(defensive.inline_code(), "HB", python_literal=True)
    ])
    status = [role_lab_status(load("offensive_role_lab"), "offensive_role_lab"),
              role_lab_status(defensive, "defensive_role_lab")]
    export.json("role_lab_capture_status", status)
    export.json("inventory", export.inventory.copy())
    for row in export.inventory:
        print(row["file"], row["rows"], end="")
        if row.get("unique_players"):
            print(f" ({row['matched_players']}/{row['unique_players']} player names matched)", end="")
        print()


if __name__ == "__main__":
    main()
