#!/usr/bin/env python3
"""Build canonical inputs from local evidence; no simulation or network access (the 2026 rookies' level step reads
the game's player-value model, never a simulated game).

Run from any directory with PYTHONPATH=src. The generated JSON is a validated
player_model input section. Re-running also refreshes the bounded evidence tables
between markers in the E2 report; hand-written schema/method notes are preserved.
"""
from __future__ import annotations

import argparse
from collections import Counter
import json
from pathlib import Path
import time

from nba_gm_data.input_estimator import (
    DEFINITIONS, InputEstimator, METHOD_VERSION, apply_rookie_involvement, load_rookie_college,
    UNIVERSE_PATH, canonical_json, coverage_counts, estimation_status,
    load_reference_cells, validation_comparison, source_join_audit, rotation_input_spread,
)

ROOT = Path(__file__).resolve().parents[1]
ROOKIE_INVOLVEMENT_PATH = "data/research/rookie_involvement_2026.json"
BEGIN = '<!-- E2 generated evidence report -->'
END = '<!-- E2 end generated evidence report -->'
TECHNIQUE_INPUTS = tuple(iid for iid, definition in DEFINITIONS.items()
                         if definition["kind"] == "grade")


def startup_rookies(estimator: InputEstimator, universe: dict):
    """2026 draftees without a completed NBA season."""
    for player in universe["players"]:
        if player.get("draft_year") != 2026 or player.get("draft_status") != "drafted":
            continue
        career = estimator.careers.get(str(player.get("espn_player_id") or ""), {})
        if any(row.get("season") and row["season"] < "2026-27" and (row.get("games") or 0) > 0
               for row in career.get("seasons", [])):
            continue
        yield player


def estimate_startup_inputs(estimator: InputEstimator, universe: dict, college: dict | None = None) -> dict:
    """Veterans: the full evidence path. 2026 rookies (no NBA season yet): rookie technique; with `college`
    (ROOKIE-FIT), the technique of a rookie with a final college season comes from that season's evidence and his
    projected rookie-year impact. Physical tools and tendencies keep the original estimates before the overlays.
    The canonical build passes no `college` here and uses apply_rookie_college as its last step instead."""
    section = estimator.estimate_universe(universe)
    for player in startup_rookies(estimator, universe):
        rookie_inputs = estimator.estimate_player_inputs(
            player, prospect=True, college=(college or {}).get(player["id"])).to_dict()["inputs"]
        inputs = section["players"][player["id"]]["inputs"]
        # Keep the original physical and tendency estimates before the evidence overlays.
        inputs.update({iid: rookie_inputs[iid] for iid in TECHNIQUE_INPUTS})
    return section


def apply_rookie_college(section: dict, estimator: InputEstimator, universe: dict, college: dict, root: Path,
                         analysts: bool = True) -> dict:
    """ROOKIE-FIT, last build step: the 2026 rookies with a final college season get their technique from that
    season's evidence and their projected rookie-year impact, and involvement from college usage. Order: college
    technique and involvement, then the level step (level_rookies), then the rookies' analyst claims.

    It runs after every league-wide step on purpose. Several overlays read league distributions (Basketball
    Index grades kept on the estimator's scale, the measured-tendency map, analyst percentiles), so changing the
    rookies earlier would shift veterans too. Here only the rookies change: their analyst claims are re-applied to
    the new technique and involvement (their other inputs are restored, so no claim counts twice)."""
    rookies = [p for p in startup_rookies(estimator, universe) if p["id"] in college]
    # RATINGS-FOLLOWUPS step 6: college involvement on the veterans' usage scale. The college-to-involvement mapping
    # was blended into a prospect prior that sat far above veterans (about 0.5 for guards), so a rookie expected to use
    # 17% of his team's plays got the involvement of a 25% veteran and role-player rookies over-scored. Now his
    # involvement is the veterans' line at his forecast rookie usage (data/research/rookie_involvement_2026.json,
    # fitted on real rookie classes and 2025-26 veterans); this season's games stay light evidence on top.
    path = root / ROOKIE_INVOLVEMENT_PATH
    if path.exists():
        scale = json.loads(path.read_text())["players"]
        for player in rookies:
            row = scale.get(player["id"])
            if row:
                # This season's usage is already inside the target (by precision), so the separate early-games
                # involvement blend is not applied again.
                college[player["id"]] = {**college[player["id"]], "involvement": [row["involvement"], 1.0],
                                         "involvement_games": None, "involvement_method": (
                    f"rookie_involvement_v1: forecast rookie usage {row['rookie_usage']}% from college usage "
                    f"{row['college_usage']}% and draft pick {row['pick']} (real rookie classes 2015-16 to 2025-26)"
                    + (f", with this season's {row['season_usage']}% over {row['season_minutes']:.0f} minutes at weight "
                       f"{row['season_weight']} -> {row['usage']}%" if row.get("season_usage") is not None else "")
                    + f", placed on the veterans' usage line ({ROOKIE_INVOLVEMENT_PATH})")}
        # Draftees without a college line (international players): the same scale at the average draftee's college
        # usage and his pick, set directly (no other involvement evidence applies to them here).
        from nba_gm_data.input_estimator import _evidence
        for player in startup_rookies(estimator, universe):
            row = scale.get(player["id"])
            if player["id"] in college or not row or player["id"] not in section["players"]:
                continue
            record = section["players"][player["id"]]["inputs"]["T08"]
            before = float(record["value"]["probability"])
            record["value"] = dict(record["value"], probability=round(row["involvement"], 8))
            record["evidence"] = [*record["evidence"], _evidence(
                ROOKIE_INVOLVEMENT_PATH, f"rookie_involvement_v1: no college line; forecast rookie usage "
                f"{row['rookie_usage']}% at the average draftee's college usage and pick {row['pick']}, on the veterans' "
                f"usage line", "draft:" + player["id"], notes=f"target={row['involvement']}; before={before}")]
    for player in rookies:
        new = estimator.estimate_player_inputs(player, prospect=True, college=college[player["id"]]).to_dict()["inputs"]
        section["players"][player["id"]]["inputs"].update({iid: new[iid] for iid in TECHNIQUE_INPUTS})
    summary = {"rookies": len(rookies),
               "involvement": apply_rookie_involvement(section, {p["id"]: college[p["id"]] for p in rookies})}
    summary["level"] = level_rookies(section, {p["id"]: college[p["id"]] for p in rookies}, root)
    # Analysts last, as for every player (where they disagree with the measures, analysts lead), so a rookie with
    # analyst claims can end slightly off his projected level.
    if analysts:
        from nba_gm_data.analyst_evidence import apply_analyst_evidence, load_claims
        ids = {p["id"] for p in rookies}
        keep = {pid: {iid: rec for iid, rec in section["players"][pid]["inputs"].items()
                      if iid not in TECHNIQUE_INPUTS and iid != "T08"} for pid in ids}
        result = apply_analyst_evidence(section, root, [c for c in load_claims(root) if c.get("player_id") in ids])
        for pid, records in keep.items():
            section["players"][pid]["inputs"].update(records)
        summary["analyst_changes"] = sum(1 for c in result["analyst_changes"]
                                         if c["input"] in TECHNIQUE_INPUTS or c["input"] == "T08")
    return summary


# ROOKIE-FIT level step. The college evidence fixes each rookie's SHAPE (which skills are strengths); the
# translation bundle fixes his LEVEL (ROOKIE-FIT-2: his day-one ability, the impact he shows if he plays, from the
# college fit on rookies who played, scouts' board rank, readiness notes and lightly this season's games; never his
# expected playing time), offense and defense, placed on the game's
# value scale by the same line that links veterans' real single-season impact to the game's value of their
# inputs. One log-odds shift per side (all offensive technique / all defensive technique, free throws excepted)
# moves his technique until the game values him at that level. Tools, tendencies and coach usage never move.
LEVEL_TOLERANCE = 0.02           # impact points per 100 possessions
LEVEL_MAX_SHIFT = 2.5            # log-odds; a rookie needing more than this is reported, never forced further
LEVEL_FALLBACK_LINES = {"offense": (0.859, 0.795), "defense": (0.743, 0.710)}   # 2026-11-21 calibration


def _channel_inputs() -> dict[str, tuple[str, ...]]:
    from nba_gm_data.input_estimator import FAMILY_CONTEXT, FAMILY_TECHNIQUES
    out = {"offense": [], "defense": []}
    for family, ids in FAMILY_TECHNIQUES.items():
        out[FAMILY_CONTEXT[family][0]].extend(ids)
    return {k: tuple(v) for k, v in out.items()}


def _game_values(section: dict, root: Path, base: dict, ids) -> dict[str, dict]:
    """The game's own value of each listed player (offense / defense impact per 100) for this input section."""
    import copy
    from nba_gm_data import ratings_model
    from nba_gm_data.impact_value import player_impact
    key, _ = ratings_model._load_inputs_keyed(root)
    # Fresh dict objects every call: the ratings model memoizes derived ratings per inputs object.
    ratings_model._INPUT_CACHE[key] = {pid: dict(doc["inputs"]) for pid, doc in section["players"].items()}
    ratings_model._FITTED_CACHE.clear()
    canonical = copy.deepcopy(base)
    ratings_model.install_inputs_model(canonical, root)
    players = {p["id"]: p for p in canonical["players"]}
    out = {}
    for pid in ids:
        value = player_impact(canonical, players[pid]) if pid in players else None
        if value is not None:
            out[pid] = value
    return out


def _value_lines(values: dict[str, dict], universe: dict, root: Path, exclude=frozenset()) -> dict[str, tuple[float, float]]:
    """game value = a + b x real single-season O-/D-LEBRON, veterans with 1000+ minutes in 2025-26."""
    import csv
    import statistics
    from nba_gm_data.input_estimator import _normalize
    lebron = root / "data/research/bbi/captures/fanspo_tools/lebron/lebron_separate-seasons_raw_all-2010-2026.csv"
    evidence = root / "data/research/development_evidence.json"
    if not lebron.exists() or not evidence.exists():
        return dict(LEVEL_FALLBACK_LINES)
    real = {}
    with lebron.open(newline="", encoding="utf-8") as handle:
        for row in csv.DictReader(handle):
            if row["Season"] == "2026":
                real[_normalize(row["Player"])] = (float(row["O-LEBRON"]), float(row["D-LEBRON"]))
    minutes = {_normalize(r[2]): r[4] for r in json.loads(evidence.read_text())["public_inputs"]["seasons"] if r[0] == 2026}
    pairs = []
    for player in universe["players"]:
        name = _normalize(player["name"])
        if (player["id"] in values and player["id"] not in exclude and name in real and minutes.get(name, 0) >= 1000
                and player.get("draft_year") != 2026):
            pairs.append((real[name], values[player["id"]]))
    lines = {}
    for i, side in enumerate(("offense", "defense")):
        xs, ys = [p[0][i] for p in pairs], [p[1][side] for p in pairs]
        slope = statistics.covariance(xs, ys) / statistics.variance(xs)
        lines[side] = (round(statistics.fmean(ys) - slope * statistics.fmean(xs), 4), round(slope, 4))
    lines["players"] = len(pairs)
    return lines


def _shifted(record: dict, delta: float, note: dict, evidence: dict | None = None, undo_step: str | None = None,
             extra: list[dict] | None = None) -> dict:
    """The record with its technique grade moved by `delta` log-odds and the step's evidence appended.

    `undo_step` names the step (age projection with return from injury, thin sample, no track record): the evidence
    then records the grade before the step and the shift. Tools that replay last season (the betting test, the
    real-stat scorecard, the value fit) undo the opening-day projection with it; a diagnostic replay can undo every
    step (ratings_model.replay_last_season_inputs). `extra`: further evidence entries of the same shift (each carries its
    own notes), e.g. the return-from-injury part of a veteran's opening-day change."""
    import math
    out = json.loads(json.dumps(record))
    grade = out["value"]["grade"]
    new = 100 / (1 + math.exp(-(math.log(grade / (100 - grade)) + delta)))
    out["value"]["grade"] = round(new, 6)
    if undo_step:
        note = {**note, "replay_undo": {"step": undo_step, "field": "grade", "before": grade,
                                        "log_odds_shift": round(delta, 6)}}
    notes = json.loads(out["uncertainty"]["notes"])
    if "interval" in notes:
        low, high = notes["interval"]
        notes["interval"] = [round(max(0.0, min(low + new - grade, new)), 6), round(min(100.0, max(high + new - grade, new)), 6)]
    out["uncertainty"]["notes"] = json.dumps(notes, sort_keys=True, ensure_ascii=False, separators=(",", ":"))
    evidence = evidence or {"source": "data/research/rookie_translation_2026.json",
        "method": "rookie_translation_v2 level: day-one ability (impact if he plays: college fit on rookies who "
                  "played, scouts' rank, readiness notes, this season's games by minutes) placed on the game's value "
                  "scale (veteran real-impact line); one log-odds shift per side of the ball",
        "shared_evidence_id": "rookie_level:" + note["player_id"]}
    out["evidence"] = [*out["evidence"], {**evidence, "notes": json.dumps(note, sort_keys=True, separators=(",", ":"))},
                       *(extra or [])]
    return out


def level_rookies(section: dict, college: dict, root: Path, iterations: int = 25) -> dict:
    from nba_gm_data.app_actions import load_app_canonical
    if not college:
        return {"rookies": 0}
    universe = json.loads((root / UNIVERSE_PATH).read_text())
    base = load_app_canonical(root)
    channels = _channel_inputs()
    ids = sorted(college)
    original = {pid: {iid: section["players"][pid]["inputs"][iid] for side in channels for iid in channels[side]}
                for pid in ids}
    league = _game_values(section, root, base, [p["id"] for p in universe["players"]])
    lines = _value_lines(league, universe, root, exclude=set(ids))
    target = {pid: {side: lines[side][0] + lines[side][1] * float(college[pid]["projection"]["o" if side == "offense" else "d"])
                    for side in channels} for pid in ids}
    delta = {pid: {side: 0.0 for side in channels} for pid in ids}
    history = {pid: {side: [] for side in channels} for pid in ids}
    values = {pid: league[pid] for pid in ids}
    for step in range(iterations):
        worst = max(abs(target[p][s] - values[p][s]) for p in ids for s in channels)
        if worst < LEVEL_TOLERANCE:
            break
        for pid in ids:
            for side in channels:
                error = target[pid][side] - values[pid][side]
                hist = history[pid][side]
                hist.append((delta[pid][side], values[pid][side]))
                if len(hist) >= 2 and abs(hist[-1][1] - hist[-2][1]) > 1e-6 and hist[-1][0] != hist[-2][0]:
                    slope = (hist[-1][1] - hist[-2][1]) / (hist[-1][0] - hist[-2][0])
                    slope = max(0.5, slope)        # a better skill never lowers value; keep steps finite
                else:
                    slope = 4.0                    # about 4 impact points per log-odds unit (measured on rookies)
                move = max(-1.0, min(1.0, error / slope))
                delta[pid][side] = max(-LEVEL_MAX_SHIFT, min(LEVEL_MAX_SHIFT, delta[pid][side] + move))
        for pid in ids:
            note = {"player_id": pid, "target_offense": round(target[pid]["offense"], 4),
                    "target_defense": round(target[pid]["defense"], 4),
                    "projected_rookie_offense": college[pid]["projection"]["o"],
                    "projected_rookie_defense": college[pid]["projection"]["d"],
                    "shift_offense": round(delta[pid]["offense"], 4), "shift_defense": round(delta[pid]["defense"], 4),
                    "value_line": {k: lines[k] for k in channels}}
            parts = college[pid].get("parts")
            if parts:   # what the day-one ability is made of (labelled evidence; LEBRON points per 100 possessions)
                games = parts["early_games"]
                note["evidence_parts"] = {
                    "college_fit": {s: parts["college_fit"][s] for s in ("o", "d")},
                    "scout_rank": parts["scout_rank"],
                    "readiness": parts["readiness"],
                    "early_games": {k: games[k] for k in ("o", "d", "minutes", "weight", "games", "team") if k in games}}
            for side, inputs in channels.items():
                for iid in inputs:
                    section["players"][pid]["inputs"][iid] = _shifted(original[pid][iid], delta[pid][side], note)
        values = _game_values(section, root, base, ids)
    from nba_gm_data import ratings_model
    ratings_model._INPUT_CACHE.clear()
    ratings_model._FITTED_CACHE.clear()
    errors = [abs(target[p][s] - values[p][s]) for p in ids for s in channels]
    return {"rookies": len(ids), "iterations": step + 1, "value_lines": lines, "max_error": round(max(errors), 4),
            "shift_range": {s: [round(min(delta[p][s] for p in ids), 3), round(max(delta[p][s] for p in ids), 3)]
                            for s in channels},
            "at_shift_limit": sorted(p for p in ids for s in channels if abs(delta[p][s]) >= LEVEL_MAX_SHIFT)}


# Veterans' opening-day level (RATINGS-AUDIT-GSW, 2026-11-22; steps 3-4 RATINGS-FOLLOWUPS). Evidence-based steps,
# solved together after
# the rookies' step (the rookies' level is already a rookie-year forecast and is not touched):
#
# 1. Age projection. A veteran's inputs measure the level he showed over 2023-24 to 2025-26 (season weights
#    1 / 0.7 / 0.45), and a new career starts on opening day with no development in between, so every veteran started
#    at a level about a season and a half old: young players below what they will show, older players above.
#    Real evidence (data/research/age_projection_2026_27.json, Basketball Index LEBRON 2010-2026 with Basketball
#    Reference ages): from that measured blend to the next season's opening day, players gain about +0.5 points per
#    100 possessions at 20-21 and +0.3 at 23, hold at 26-28, and lose about -0.3 at 32 and -0.6 at 37-40 (offense
#    carries most of it). Each veteran moves by that amount, plus one season of change for each recent season he
#    missed entirely (his measured level is a season older), centred so the league's average player does not move.
# 2. No NBA track record. Players with no NBA minutes in 2023-24 to 2025-26 (two-way and fringe signings, players
#    back from Europe; 2026 rookies and first-round picks excepted) had no evidence of level, and their technique sat
#    at the average of established players in their listed role: a "primary ball handler" with no NBA minutes was
#    rated above most measured bench guards. Real evidence (data/research/no_track_record_level_2026_27.json): such
#    players, in the seasons they did get 250+ minutes (2011-2026), averaged -1.15 offense / -0.28 defense (LEBRON);
#    that is an upper bound, since most never got the minutes. Each is placed at that level; his shape (which skills
#    are strengths) is kept.
# Both use the rookies' mechanism: the game's value scale by the veteran real-impact line, one log-odds shift per side
# of the ball on technique. Physical tools, tendencies and coach usage never move.
AGE_PROJECTION_PATH = "data/research/age_projection_2026_27.json"
NO_TRACK_RECORD_PATH = "data/research/no_track_record_level_2026_27.json"
AGE_MEASURED_MINUTES = 250.0     # a season counts as measured with this many minutes (same as the curve's evidence)
AGE_LEVEL_TOLERANCE = 0.02       # value points; same as the rookies' level step
AGE_MAX_SHIFT = 2.5              # log-odds (as the rookies' step); reported, never forced further


def _evidence_name(name: str) -> str:
    """Name key for Basketball Reference rows, which often drop or add Jr./II/III ("Jimmy Butler III")."""
    import re
    from nba_gm_data.input_estimator import _normalize
    key = _normalize(re.sub(r"(?i)[ ,]+(jr|sr|ii|iii|iv)\.?$", "", name.strip()))
    return {"ronaldholland": "ronholland"}.get(key, key)


def _recent_minutes(root: Path) -> dict[tuple[str, int], float]:
    minutes: dict[tuple[str, int], float] = {}
    for r in json.loads((root / "data/research/development_evidence.json").read_text())["public_inputs"]["seasons"]:
        if r[0] in (2024, 2025, 2026) and r[4] is not None:
            key = (_evidence_name(r[2]), r[0])
            minutes[key] = minutes.get(key, 0.0) + float(r[4])
    return minutes


def age_projection_targets(universe: dict, root: Path) -> dict[str, dict]:
    """{player_id: {offense, defense (LEBRON points to add), age, missed}} for veterans with recent NBA minutes."""
    curve = json.loads((root / AGE_PROJECTION_PATH).read_text())
    minutes = _recent_minutes(root)
    ages = sorted(int(a) for a in curve["shift"]["offense"])
    out, weights = {}, {}
    for player in universe["players"]:
        if player.get("draft_year") == 2026 or player.get("age") is None:
            continue
        name = _evidence_name(player["name"])
        played = [minutes.get((name, y), 0.0) >= AGE_MEASURED_MINUTES for y in (2026, 2025, 2024)]
        if not any(played):
            continue
        missed = played.index(True)            # recent seasons with no measurement (0, 1 or 2)
        age = min(max(int(round(float(player["age"]))), ages[0]), ages[-1])
        row = {"age": age, "missed": missed}
        for side in ("offense", "defense"):
            value = curve["shift"][side][str(age)]
            for k in range(1, missed + 1):     # the change during each missed season (age then: age - k)
                value += curve["annual"][side][str(max(ages[0], age - k))]
            row[side] = value
        out[player["id"]] = row
        weights[player["id"]] = float(player.get("minutes_projection") or 0.0)
    total = sum(weights.values()) or 1.0
    for side in ("offense", "defense"):
        centre = sum(out[p][side] * weights[p] for p in out) / total
        for p in out:
            out[p]["uncentred_" + side] = round(out[p][side], 4)
            out[p][side] = round(out[p][side] - centre, 4)
            out[p]["centre_" + side] = round(centre, 4)
    return out


def no_track_record_players(universe: dict, root: Path) -> list[str]:
    """Veterans with no NBA minutes in 2023-24 to 2025-26 (not 2026 rookies, not first-round picks)."""
    minutes = _recent_minutes(root)
    out = []
    for player in universe["players"]:
        if player.get("draft_year") == 2026:
            continue
        if player.get("draft_round") == 1 or (player.get("draft_position") or 99) <= 30:
            continue
        name = _evidence_name(player["name"])
        if not any(minutes.get((name, y), 0.0) > 0 for y in (2026, 2025, 2024)):
            out.append(player["id"])
    return out


# 3. Thin samples (RATINGS-FOLLOWUPS, 2026-11-22). Players with 1-999 NBA minutes in 2023-24 to 2025-26 had too
#    little evidence for their own numbers to set their level, and the rest of it came from the average of
#    established players in their listed role. Real evidence (data/research/thin_sample_level_2026_27.json, Basketball
#    Index LEBRON 2011-2026): the next season of such players is best forecast by the level such players show plus his
#    own measured LEBRON over those seasons, counted by his minutes m as m / (m + 350) (cross-validated against using
#    only his own number or only the group). Splitting the group by years in the league (1-2, 3-4, 5+), age or draft
#    round did not forecast better: veterans who rarely play mostly leave the league (13% of those with 5+ years get
#    250 minutes the next season, against 40% of young players), but the ones who do play show the same level, so one
#    pooled group is used (the research file records the split levels). Each is placed at that forecast for opening day, instead of the age step: his own
#    age's change to opening day (the age step's curve) replaces the average change already inside his group's level,
#    so a 39-year-old is not given a 27-year-old's season. His skill shape is kept. Moves both ways.
THIN_SAMPLE_PATH = "data/research/thin_sample_level_2026_27.json"


def _lebron_by_season(root: Path) -> dict[str, dict[int, tuple[float, float]]]:
    import csv
    path = root / "data/research/bbi/captures/fanspo_tools/lebron/lebron_separate-seasons_raw_all-2010-2026.csv"
    rows: dict[str, dict[int, tuple[float, float]]] = {}
    if path.exists():
        with path.open(newline="", encoding="utf-8") as handle:
            for row in csv.DictReader(handle):
                rows.setdefault(_evidence_name(row["Player"]), {})[int(row["Season"])] = (
                    float(row["O-LEBRON"]), float(row["D-LEBRON"]))
    return rows


def _nba_seasons(root: Path) -> dict[str, list[tuple[int, float | None]]]:
    """Name key -> [(season end year, age then)] for every season with NBA minutes (Basketball Reference)."""
    out: dict[str, list[tuple[int, float | None]]] = {}
    for r in json.loads((root / "data/research/development_evidence.json").read_text())["public_inputs"]["seasons"]:
        if r[4]:
            out.setdefault(_evidence_name(r[2]), []).append((int(r[0]), r[3]))
    return out


def _first_nba_season(seasons: list[tuple[int, float | None]], age_now: float) -> int:
    """His first NBA season, counting only seasons whose age fits his own (a father with the same name, as Ron
    Harper and Ron Harper Jr., is not him)."""
    own = [y for y, age in seasons if age is None or abs(float(age) - (age_now - (2027 - y))) <= 1.5]
    return min(own, default=2026)


def thin_sample_targets(universe: dict, root: Path) -> dict[str, dict]:
    """{player_id: real-impact forecast for opening day 2026-27 (offense / defense) and its parts} for veterans with
    1-999 NBA minutes in 2023-24 to 2025-26 (not 2026 rookies)."""
    evidence = json.loads((root / THIN_SAMPLE_PATH).read_text())
    curve = json.loads((root / AGE_PROJECTION_PATH).read_text())
    ages = sorted(int(a) for a in curve["shift"]["offense"])
    k, groups, top = evidence["minutes_k"], evidence["groups"], evidence["thin_max_minutes"]
    minutes = _recent_minutes(root)
    lebron = _lebron_by_season(root)
    careers = _nba_seasons(root)
    weights = dict(zip((2026, 2025, 2024), (1.0, 0.7, 0.45)))     # the builder's season weights
    out = {}
    for player in universe["players"]:
        if player.get("draft_year") == 2026:
            continue
        name = _evidence_name(player["name"])
        played = {y: minutes.get((name, y), 0.0) for y in (2026, 2025, 2024)}
        total = sum(played.values())
        if not 0 < total < top:
            continue
        years = 2027 - _first_nba_season(careers.get(name, []), float(player.get("age") or 26))
        band = ("all" if evidence["grouping"] == "minutes"
                else "1-2" if years <= 2 else "3-4" if years <= 4 else "5+")
        group = groups[band]
        parts = [(lebron[name][y], weights[y] * m) for y, m in played.items() if m > 0 and y in lebron.get(name, {})]
        w = total / (total + k) if parts else 0.0
        age = min(max(int(round(float(player.get("age") or 26))), ages[0]), ages[-1])
        row = {"minutes": round(total, 1), "years_in_league": years, "group": band, "own_weight": round(w, 4), "age": age}
        for i, side in enumerate(("offense", "defense")):
            own = sum(v[i] * wt for v, wt in parts) / sum(wt for _, wt in parts) if parts else group["own_mean_" + side]
            # His own age's change to opening day (the age step's shift), less the change already in his group's level.
            age_change = curve["shift"][side][str(age)] - group["mean_case_lag_" + side]
            row["own_" + side] = round(own, 4)
            row["group_" + side] = group[side]
            row["age_change_" + side] = round(age_change, 4)
            row[side] = round(group[side] + w * (own - group["own_mean_" + side]) + age_change, 4)
        out[player["id"]] = row
    return out


# 4. Return from a major injury (RATINGS-FOLLOWUPS, 2026-11-22). A veteran whose Achilles rupture or ACL tear came
#    after (or late in) his measured seasons starts from his level before the injury. Real evidence
#    (data/research/major_injury_return_2026_27.json): 43 players back from these injuries 2010-2026 played their first
#    season back -0.45 offense / -0.20 defense (LEBRON points per 100 possessions) below what their level before and
#    their age predicted. By injury and by age at injury (under 30 / 30+) the groups differ by less than chance, so the
#    pooled cost applies to all (Basketball Index's own matched estimate: -0.54 ACL, -1.12 Achilles before its
#    shrinkage). It is added to his age-step change, times the share of his measured seasons played before the injury
#    (seasons after it already show the cost). Undone by replays of last season, like the age step.
INJURY_RETURN_PATH = "data/research/major_injury_return_2026_27.json"
INJURY_SEASON_WEIGHTS = {2026: 1.0, 2025: 0.7, 2024: 0.45}     # the builder's season weights


def injury_return_targets(universe: dict, root: Path) -> dict[str, dict]:
    """{player_id: {offense, defense (LEBRON points to add), injury, season, age_at_injury, before_share, sources}}."""
    evidence = json.loads((root / INJURY_RETURN_PATH).read_text())
    applied, split = evidence["applied_cost"], evidence["age_split"]
    minutes = _recent_minutes(root)
    by_name = {_evidence_name(p["name"]): p for p in universe["players"] if p.get("draft_year") != 2026}
    out = {}
    for case in evidence["current_players"]:
        player = by_name.get(_evidence_name(case["player"]))
        if player is None or player.get("age") is None:
            continue
        name = _evidence_name(player["name"])
        weights = {y: w * minutes.get((name, y), 0.0) for y, w in INJURY_SEASON_WEIGHTS.items()}
        total = sum(weights.values())
        if total <= 0:
            continue
        before = sum(w for y, w in weights.items() if y <= case["season"]) / total
        age_then = float(player["age"]) - (2027 - case["season"])
        group = applied[f"{case['injury']} {'30+' if age_then >= split else 'under 30'}"]
        out[player["id"]] = {"injury": case["injury"], "season": case["season"], "age_at_injury": round(age_then, 1),
                             "before_share": round(before, 4), "sources": case["sources"],
                             "offense": round(group["offense"] * before, 4), "defense": round(group["defense"] * before, 4)}
    return out


def project_veterans(section: dict, universe: dict, root: Path, iterations: int = 12) -> dict:
    from nba_gm_data.app_actions import load_app_canonical
    age_targets = age_projection_targets(universe, root) if (root / AGE_PROJECTION_PATH).exists() else {}
    fringe = no_track_record_players(universe, root) if (root / NO_TRACK_RECORD_PATH).exists() else []
    # Thin samples replace the age step (their forecast is already for opening day); the age step's centring above
    # is computed before, so every other veteran's target is unchanged.
    thin = thin_sample_targets(universe, root) if (root / THIN_SAMPLE_PATH).exists() and age_targets else {}
    for pid in thin:
        age_targets.pop(pid, None)
    injured = {pid: t for pid, t in (injury_return_targets(universe, root) if (root / INJURY_RETURN_PATH).exists()
                                     else {}).items() if pid in age_targets}
    if not age_targets and not fringe:
        return {"players": 0}
    base = load_app_canonical(root)
    channels = _channel_inputs()
    rookies = {p["id"] for p in universe["players"] if p.get("draft_year") == 2026}
    league = _game_values(section, root, base, [p["id"] for p in universe["players"]])
    lines = _value_lines(league, universe, root, exclude=rookies)
    ids = sorted(pid for pid in set(age_targets) | set(fringe) | set(thin) if pid in league)
    target, notes, evidence = {}, {}, {}
    if fringe:
        level = json.loads((root / NO_TRACK_RECORD_PATH).read_text())["level"]
    for pid in ids:
        if pid in thin:
            t = thin[pid]
            target[pid] = {side: lines[side][0] + lines[side][1] * t[side] for side in channels}
            notes[pid] = {"player_id": pid, **{"thin_" + key: value for key, value in t.items()}}
            evidence[pid] = {"source": THIN_SAMPLE_PATH, "shared_evidence_id": "thin_sample:" + pid,
                "method": "thin_sample_level_v1: 1-999 NBA minutes in 2023-24 to 2025-26, so his opening-day level is "
                          "the next-season level of players with his years in the league plus his own measured LEBRON "
                          "counted by minutes, m/(m+350) (Basketball Index LEBRON 2011-2026, cross-validated); placed on "
                          "the game's value scale (veteran real-impact line); one log-odds shift per side of the ball, "
                          "his skill shape kept"}
        elif pid in age_targets:
            t = age_targets[pid]
            hurt = injured.get(pid, {})
            target[pid] = {side: league[pid][side] + lines[side][1] * (t[side] + hurt.get(side, 0.0)) for side in channels}
            notes[pid] = {"player_id": pid, "age": t["age"], "missed_recent_seasons": t["missed"],
                          "projected_change_offense": t["offense"], "projected_change_defense": t["defense"],
                          "uncentred_offense": t["uncentred_offense"], "uncentred_defense": t["uncentred_defense"]}
            if hurt:
                notes[pid]["injury_return"] = hurt
            evidence[pid] = {"source": AGE_PROJECTION_PATH, "shared_evidence_id": "age_projection:" + pid,
                "method": "age_projection_v1: measured 2023-26 level carried to opening day 2026-27 by the real change "
                          "from that blend to the next season at his age (Basketball Index LEBRON 2010-2026, Basketball "
                          "Reference ages), plus each missed recent season, centred on the league; placed on the "
                          "game's value scale (veteran real-impact line); one log-odds shift per side of the ball"}
        else:
            target[pid] = {side: lines[side][0] + lines[side][1] * level[side] for side in channels}
            notes[pid] = {"player_id": pid, "level_offense": level["offense"], "level_defense": level["defense"]}
            evidence[pid] = {"source": NO_TRACK_RECORD_PATH, "shared_evidence_id": "no_track_record:" + pid,
                "method": "no_track_record_level_v1: no NBA minutes in 2023-24 to 2025-26, so his level is that of "
                          "such players when they did play (Basketball Index LEBRON 2011-2026, an upper bound); placed "
                          "on the game's value scale (veteran real-impact line); one log-odds shift per side of the "
                          "ball, his skill shape kept"}
    extra = {pid: [{"source": INJURY_RETURN_PATH, "shared_evidence_id": "injury_return:" + pid,
                    "method": "major_injury_return_v1: first season back from an Achilles rupture or ACL tear, the "
                              "real cost beyond age (43 returns 2010-2026, Basketball Index LEBRON; pooled across injury "
                              "and age, which differ by less than chance), times the share of his measured seasons "
                              "before the injury; part of the opening-day shift above",
                    "notes": json.dumps({"player_id": pid, **hurt}, sort_keys=True, separators=(",", ":"))}]
             for pid, hurt in injured.items()}
    original = {pid: {iid: section["players"][pid]["inputs"][iid] for side in channels for iid in channels[side]
                      if isinstance((section["players"][pid]["inputs"][iid].get("value") or {}).get("grade"), (int, float))}
                for pid in ids}
    delta = {pid: {side: 0.0 for side in channels} for pid in ids}
    history = {pid: {side: [] for side in channels} for pid in ids}
    values = {pid: league[pid] for pid in ids}
    step = 0
    for step in range(iterations):
        worst = max(abs(target[p][s] - values[p][s]) for p in ids for s in channels)
        if worst < AGE_LEVEL_TOLERANCE:
            break
        for pid in ids:
            for side in channels:
                error = target[pid][side] - values[pid][side]
                hist = history[pid][side]
                hist.append((delta[pid][side], values[pid][side]))
                if len(hist) >= 2 and abs(hist[-1][1] - hist[-2][1]) > 1e-6 and hist[-1][0] != hist[-2][0]:
                    slope = max(0.5, (hist[-1][1] - hist[-2][1]) / (hist[-1][0] - hist[-2][0]))
                else:
                    slope = 4.0
                move = max(-1.0, min(1.0, error / slope))
                delta[pid][side] = max(-AGE_MAX_SHIFT, min(AGE_MAX_SHIFT, delta[pid][side] + move))
        for pid in ids:
            note = {**notes[pid], "target_offense": round(target[pid]["offense"], 4),
                    "target_defense": round(target[pid]["defense"], 4),
                    "shift_offense": round(delta[pid]["offense"], 4), "shift_defense": round(delta[pid]["defense"], 4),
                    "value_line": {k: lines[k] for k in channels}}
            for side, inputs in channels.items():
                for iid in inputs:
                    if iid in original[pid]:
                        section["players"][pid]["inputs"][iid] = _shifted(
                            original[pid][iid], delta[pid][side], note, evidence[pid],
                            undo_step=("age_projection" if pid in age_targets else "thin_sample" if pid in thin
                                       else "no_track_record"), extra=extra.get(pid))
        values = _game_values(section, root, base, ids)
    from nba_gm_data import ratings_model
    ratings_model._INPUT_CACHE.clear()
    ratings_model._FITTED_CACHE.clear()
    errors = {p: max(abs(target[p][s] - values[p][s]) for s in channels) for p in ids}
    any_age = next(iter(age_targets.values()), {})
    return {"players": len(ids), "age_projection": sum(1 for p in ids if p in age_targets),
            "thin_sample": sum(1 for p in ids if p in thin), "injury_return": sorted(injured),
            "no_track_record": sum(1 for p in ids if p not in age_targets and p not in thin), "iterations": step + 1,
            "max_error": round(max(errors.values()), 4), "mean_error": round(sum(errors.values()) / len(errors), 4),
            "worst": sorted(errors, key=errors.get)[-3:], "value_lines": lines,
            "centre": {s: any_age.get("centre_" + s) for s in channels},
            "at_shift_limit": sorted(p for p in ids for s in channels if abs(delta[p][s]) >= AGE_MAX_SHIFT)}


def report_tables(universe: dict, section: dict, comparison: dict, elapsed: float,
                  byte_count: int, estimator: InputEstimator) -> str:
    coverage=coverage_counts(section)
    audit=source_join_audit(universe,estimator)
    spread=rotation_input_spread(section,audit)
    names={p['id']:p['name'] for p in universe['players']}
    groups={
        'Physical tools (12)': [k for k in DEFINITIONS if k.startswith('P')],
        'Shooting (9)': [f'S{i:02d}' for i in range(1,10)],
        'Finishing and receiving (6)': [f'S{i:02d}' for i in range(10,16)],
        'Handling and attack recognition (5)': [f'S{i:02d}' for i in range(16,21)],
        'Post craft (3)': [f'S{i:02d}' for i in range(21,24)],
        'Foul craft, routes and screening (5)': [f'S{i:02d}' for i in range(24,29)],
        'Rebounding technique (4)': [f'S{i:02d}' for i in range(29,33)],
        'Defense technique and recognition (14)': [f'S{i:02d}' for i in range(33,47)],
        'Passing recognition (9)': [k for k in DEFINITIONS if k.endswith('.recognition')],
        'Passing execution (9)': [k for k in DEFINITIONS if k.endswith('.execution')],
        'Conditional tendencies (18)': [k for k in DEFINITIONS if k.startswith('T')],
    }
    total=Counter(estimation_status(r) for p in section['players'].values() for r in p['inputs'].values())
    nplayers=len(section['players'])
    matched_skills=sum(1 for p in universe['players'] if _name(p['name']) in estimator.skills)
    matched_stats=sum(1 for p in universe['players'] if _name(p['name']) in estimator.stats)
    matched_career=sum(1 for p in universe['players'] if str(p.get('espn_player_id') or '') in estimator.careers)
    grades=[r['value']['grade'] for p in section['players'].values() for r in p['inputs'].values() if 'grade' in r['value']]
    lines=[BEGIN,'','## Build and coverage','',
        f'- Method: `{METHOD_VERSION}`. Built **{nplayers} × 94 = {nplayers*94:,}** complete records.',
        f'- **{total["estimated"]:,} player-evidence estimates; {total["prior"]:,} explicit priors.**',
        f'- Local joins: {matched_skills} unique skill names, {matched_stats} unique later Crafted names, {matched_career} ESPN IDs. Sources are overlapping, never additive player counts.',
        f'- Build, validation, comparison without packet experts, serialization and write: **{elapsed:.3f} seconds**; canonical JSON {byte_count/1_000_000:.2f} MB.',
        f'- Skill-grade range {min(grades):.3f}–{max(grades):.3f}; exactly 100: {sum(v==100 for v in grades)}; at least 99.9: {sum(v>=99.9 for v in grades)}. No scale-max clipping.',
        '', '| Input family | Player-evidence estimates | Priors | Total |', '|---|---:|---:|---:|']
    for family,ids in groups.items():
        estimated=sum(coverage[i]['estimated'] for i in ids)
        priors=sum(coverage[i]['prior'] for i in ids)
        lines.append(f'| {family} | {estimated:,} | {priors:,} | {estimated+priors:,} |')
    lines.extend(['','## Per-input coverage and hand-reference comparison','',
        f'Newest estimated source cells from **{comparison["reference_players"]} players**, {comparison["reference_cells"]} cells; {comparison["comparable_cells"]} comparable numeric cells. One display-only physical descriptor has no aligned scale and is excluded from numeric agreement. Unknowns do not overwrite earlier estimates. Nov15 uses `proposed_source_input_section`; scenarios, operational profiles and completion suggestions are excluded.',
        '', 'The final estimate includes a 35% adjustment toward sourced expert technique judgments. **This comparison shares expert evidence with the reference; it is not independent validation.** The last two columns rerun the estimator with every packet-expert adjustment disabled, retaining the declared legacy/statistical prior context. No constants were fitted to either comparison. Expert agreement must not be read as accuracy against ground truth. Expert-adjusted bands deliberately retain source disagreement, so they contain the reused hand value by construction; the bands without packet adjustments do not have this guarantee. This is a comparison without those packet adjustments, not a fully held-out test: legacy priors may share related expert/statistical information.',
        '', 'Differences are in each input’s native units: technique grades, FT percentage points, geometry cm or mass kg. Technique comparisons provisionally share the hand packets’ 50/75/90 anchors; FT retains its separately declared conversion-percentage scale. No mixed-unit grand average is reported. “Inside” asks whether the hand midpoint falls inside the estimator’s broad plausibility band, not whether two calibrated confidence intervals overlap. A dash means there is no comparable hand cell.',
        '', '| Input | Name | Estimated | Prior | Hand cells | Mean absolute difference | Inside band | Difference without experts | Inside without experts |',
        '|---|---|---:|---:|---:|---:|---:|---:|---:|'])
    for row in comparison['table']:
        iid=row['input_id'];count=row['count'];c=coverage[iid]
        diff=f'{row["mean_absolute_difference"]:.2f}' if count else '—'
        inside=f'{100*row["inside_fraction"]:.1f}%' if count else '—'
        baseline=f'{row["baseline_mean_absolute_difference"]:.2f}' if count else '—'
        base_inside=f'{100*row["baseline_inside_fraction"]:.1f}%' if count else '—'
        lines.append(f'| {iid} | {row["name"]} | {c["estimated"]} | {c["prior"]} | {count} | {diff} | {inside} | {baseline} | {base_inside} |')
    lines.extend(['','## Ten largest technique disagreements','',
        'Sorted within technique grades only; centimeter and kilogram differences are not ranked against grades. Each explanation identifies the evidence limitation rather than treating the hand value as truth.',
        '', '| Player | Input | Estimator | Hand reference | Difference | Explanation |',
        '|---|---|---:|---:|---:|---|'])
    for row in comparison['biggest_disagreements']:
        explanation=row['explanation']
        if 'expert' in explanation:
            gaps={
                'S20':'No tagged attack-choice windows; the conservative position/role prior retains 65% weight despite expert praise of orchestration.',
                'F04.execution':'No typed lob-delivery sample; a broad role prior is retained alongside expert evidence of passing repertoire.',
                'F04.recognition':'No counted available lob reads; general passing praise supplies direction with broad uncertainty.',
                'S09':'No deep-shot mechanics curve; global three-point accuracy cannot identify distance-extension technique.',
                'S41':'Steals and deflections mix anticipation, technique and scheme; expert anticipation evidence adjusts a broad prior.',
                'S33':'No stance/angle success sample separated from physical tools; the expert containment assessment adjusts the role prior.',
                'S02':'Global three-point outcomes and an uncertain live-dribble difficulty prior understate the expert assessment of elite pull-up shooting.',
                'S44':'No responsibility-error counts; the expert assessment of attention adjusts an otherwise broad prior.',
                'S35':'No independent navigation-technique sample; the broad prior retains most weight despite expert praise.',
            }
            explanation=gaps.get(row['input_id'],'The broad baseline retains 65% weight; isolated technique observations are unavailable.')
        lines.append(f'| {names[row["player_id"]]} | {row["input_id"]} {DEFINITIONS[row["input_id"]]["name"]} | {row["estimate"]:.2f} | {row["reference"]:.2f} | {row["absolute_difference"]:.2f} | {explanation} |')
    lines.extend(['','## Observable tendencies and shot locations','',
        'T02 now uses player attempt counts: current completed ESPN 3PA/FGA first, then valid provider attempt-rate fields, then dated observed chart counts when no newer ratio exists. The three-point share shrinks by 100 prior field-goal attempts. Retained 2024–25 aggregate chart bins inform conditional two-point locations for matched players; their totals are reconciled, coordinates use the existing basket-relative feet grid, and two-foot bin/season uncertainty stays broad. The older chart does not count again toward a newer three-point ratio.',
        '', 'LT_06 efficiency and the ambiguous FREQ field are not shot-attempt frequencies. They are not used as observed location counts. Missing two-point subregions retain declared player priors. T01 action and T03 mode tags overlap and omit some alternatives; their estimates are explicitly partial proxies, with pass/reset prior mass preserved. Roll participation supports a broad T11 roll/pop proxy, and ORB% supports a broad T12 crash proxy with an explicit assumed recovery conversion, not a claim that rebounds equal crash attempts.',
        '', '| Tendency | Player-evidence estimates | Priors | Evidence strength |',
        '|---|---:|---:|---|'])
    for iid,label in [('T01','partial action mix'),('T02','attempt-location mix'),('T03','shooting modes'),
                      ('T05','transition frequency'),('T08','possession involvement'),('T09','cutting'),
                      ('T10','off-ball movement tags'),('T11','screen/roll/pop'),('T12','offensive crash'),('T18','contact seeking')]:
        strength=('attempt-count constrained; two-point subregions partly prior' if iid=='T02' else
                  'observed tag/rate with deployment and proxy uncertainty')
        lines.append(f'| {iid} {label} | {coverage[iid]["estimated"]} | {coverage[iid]["prior"]} | {strength} |')
    lines.extend(['','Families without an observed choice denominator (risk, persistence, help, contest choice, pursuit/box-out emphasis and effort allocation) remain wide player-conditioned priors. All probability rows normalize, every input retains a value, and the source/uncertainty record says which parts are observed or inferred.'])
    lines.extend(['','## Adapter feedback: joins and player-specific priors','',
        'Priors now respond weakly to related legacy traits, provider outcomes/workload, defensive deployment and body/age context. Every such record remains `reason: prior`, with low confidence and broad bands. `legacy_trait_prior` identifies the legacy contribution; those effective summaries are not relabeled as technique measurements. Direct statistical estimates are untouched by prior conditioning. No adapter rankings or simulation results enter these rules.',
        '', f'The audit cohort contains **{audit["rotation_players"]} players** with at least 1,000 minutes in any retained 2025–26 skill snapshot, later Crafted snapshot, or unique completed ESPN regular-season row. Taking the maximum selects the audit cohort only; source denominators are never summed. The report does not rely on a skill join to qualify a missing-skill player.',
        '', '| High-minute player with missing skill row | Retained minutes | Skill snapshot | Later Crafted snapshot | ESPN ID |',
        '|---|---:|---|---|---|'])
    if audit['unmatched_skills']:
        for row in audit['unmatched_skills']:
            lines.append(f'| {row["name"]} | {row["minutes"]:.1f} | missing | {"joined" if row["stats_joined"] else "missing"} | {"joined" if row["career_joined"] else "missing"} |')
    else:
        lines.append('| None | — | all joined | — | — |')
    lines.append('')
    lines.append('High-minute players missing the later Crafted snapshot: '+(', '.join(row['name'] for row in audit['unmatched_stats']) or 'none')+'.')
    # Explicitly requested identity check, not a named ranking or estimator rule.
    wemb=next((row for row in audit['players'] if row['name']=='Victor Wembanyama'),None)
    if wemb:
        inputs=section['players'][wemb['player_id']]['inputs']
        lines.extend(['',f'**Wembanyama check:** skill snapshot {"joined" if wemb["skill_joined"] else "missing"}; later Crafted snapshot {"joined" if wemb["stats_joined"] else "missing"}; ESPN ID {"joined" if wemb["career_joined"] else "missing"}. His record did not fail a name/accent join. The earlier near-50 passing and shooting numbers came from the reference scale and conservative estimates, while release speed was a flat prior. No named-player override has been added.',
            '', '| Requested player input | Value | Evidence label |', '|---|---:|---|'])
        for iid in ('S01','S02','S03','S07','S08','S09','F01.recognition','F01.execution'):
            r=inputs[iid]
            lines.append(f'| {iid} {DEFINITIONS[iid]["name"]} | {r["value"]["grade"]:.3f} | {estimation_status(r)} |')
    flags=[r for r in spread if r['near_zero']]
    lines.extend(['','## Rotation-player spread: all 94 inputs','',
        'Population standard deviation across the audit cohort, in native units. Distribution families show every outcome separately; there is no arbitrary scalar coding of outcomes. A flag marks any component below 1 grade point, 0.5 cm/kg, or 0.01 probability. These are review flags only: no rating is changed to pass a spread threshold, and no jitter is introduced.',
        '', f'**{len(flags)} input families have a near-zero component.** '+('Review: '+', '.join(r['input_id'] for r in flags)+'.' if flags else 'None of the approved families is flat at these declared thresholds.'),
        '', '| Input | Name | Players | Standard deviation (unit or outcome) | Near-zero components |',
        '|---|---|---:|---|---|'])
    for row in spread:
        deviations='; '.join(f'{key.removeprefix("reference_opportunity/")}: {sd:.4f}' for key,sd in row['standard_deviations'].items())
        flagged=', '.join(key.removeprefix('reference_opportunity/') for key in row['near_zero']) or '—'
        lines.append(f'| {row["input_id"]} | {row["name"]} | {row["count"]} | {deviations} | {flagged} |')
    lines.extend(['',END])
    return '\n'.join(lines)


def _name(name):
    # Reuse estimator join convention; do not introduce a second match policy.
    from nba_gm_data.input_estimator import _normalize
    return _normalize(name)


def main() -> None:
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root',type=Path,default=ROOT)
    parser.add_argument('--output',type=Path,default=None)
    parser.add_argument('--report',type=Path,default=None)
    parser.add_argument('--no-report',action='store_true')
    parser.add_argument('--no-bbi',action='store_true',help='Skip the Basketball Index evidence overlay')
    parser.add_argument('--no-analysts',action='store_true',help='Skip the attributed analyst-claim evidence')
    parser.add_argument('--no-age-projection',action='store_true',help='Skip the veterans opening-day level step (age projection, no NBA track record)')
    args=parser.parse_args()
    root=args.root.resolve()
    output=args.output or root/'data/canonical/player_inputs_2026_27.json'
    report=args.report or root/'docs/agents/tasks/e2-input-estimator.md'
    started=time.perf_counter()
    universe=json.loads((root/UNIVERSE_PATH).read_text())
    estimator=InputEstimator.from_local(root)
    college=load_rookie_college(root)
    section=estimate_startup_inputs(estimator,universe)
    bbi_summary=None
    if not args.no_bbi and (root/'data/research/bbi/normalized.json').exists() and (root/'data/research/bbi/bbi_input_mapping.json').exists():
        # Player-specific Basketball Index evidence (Leaderboards Values captures) blended over the estimate.
        from nba_gm_data.bbi_evidence import apply_overlay, apply_measured_tendencies
        bbi_summary=apply_overlay(section,root)
        bbi_summary.update(apply_measured_tendencies(section,root))
        # Foul drawing and handle security per chance: free throws and turnovers against what an average player
        # earns or commits from the same drives, shots, passes and touches (RATINGS-FT-TOV, 2026-11-21).
        from nba_gm_data.foul_security_evidence import apply_foul_security_evidence
        bbi_summary.update(apply_foul_security_evidence(section,root,universe))
    # Measured dunk rates (public Basketball-Reference shooting data) for dunk execution, net of body size.
    from nba_gm_data.public_shot_evidence import apply_dunk_evidence
    bbi_summary=(bbi_summary or {})|apply_dunk_evidence(section,root,universe)
    # Strength and jump capacity: NBA Draft Combine tests (age-adjusted) blended with in-game proxies by reliability.
    from nba_gm_data.physical_evidence import apply_physical_evidence
    bbi_summary|=apply_physical_evidence(section,root,universe)
    # Attributed analyst claims last: where analysts and the measures disagree, analysts lead (user priority, 2026-11-19).
    if not args.no_analysts:
        from nba_gm_data.analyst_evidence import apply_analyst_evidence
        analyst=apply_analyst_evidence(section,root)
        analyst.pop('analyst_changes')
        bbi_summary|=analyst
    # 2026 rookies with a college season: technique and involvement from college evidence (ROOKIE-FIT). Last, so
    # no league-wide step sees the change and every veteran stays exactly as before. Involvement is set on the
    # measured scale, which exists only after the Basketball Index step.
    if not args.no_bbi:
        bbi_summary['rookie_college']=apply_rookie_college(section,estimator,universe,college,root,not args.no_analysts)
    # Veterans' opening-day level: age projection and players with no NBA track record (RATINGS-AUDIT-GSW).
    # After the rookies' step, so the rookies' forecast level (already a rookie-year projection) is not touched.
    if not args.no_bbi and not args.no_age_projection:
        bbi_summary['veteran_levels']=project_veterans(section,universe,root)
    baseline=estimate_startup_inputs(InputEstimator.from_local(root,use_expert=False),universe,college)
    comparison=validation_comparison(section,load_reference_cells(root),baseline)
    payload=canonical_json(section)
    output.parent.mkdir(parents=True,exist_ok=True)
    output.write_text(payload,encoding='utf-8')
    # Git tracks only the compressed copy (~4.5 MB vs ~92 MB); mtime=0 keeps it byte-reproducible.
    import gzip
    with open(str(output)+'.gz','wb') as raw, gzip.GzipFile(fileobj=raw,mode='wb',compresslevel=9,mtime=0,filename='') as gz:
        gz.write(payload.encode('utf-8'))
    elapsed=time.perf_counter()-started
    byte_count=len(payload.encode('utf-8'))
    if not args.no_report:
        text=report.read_text() if report.exists() else '# E2 input estimator\n'
        generated=report_tables(universe,section,comparison,elapsed,byte_count,estimator)
        if BEGIN in text and END in text:
            text=text[:text.index(BEGIN)]+generated+text[text.index(END)+len(END):]
        else:
            text=text.rstrip()+'\n\n'+generated+'\n'
        report.parent.mkdir(parents=True,exist_ok=True)
        report.write_text(text,encoding='utf-8')
    print(f'Wrote {len(section["players"])} players × 94 inputs to {output}')
    if bbi_summary:
        print(f'BBI overlay: {bbi_summary}')
    print(f'{byte_count:,} bytes; build and comparison {elapsed:.3f}s; {comparison["reference_players"]} reference players')


if __name__=='__main__':
    main()
