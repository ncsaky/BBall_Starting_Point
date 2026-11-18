"""Lineup chemistry from real five-man lineups: how a lineup's make-up changes its scoring beyond the sum of its players.

Evidence
  * Primary: Basketball Index xPoints lineups, 2025-26 (data/research/bbi/tools/xpoints_lineups.csv): 12,481 real lineups
    with exact possession counts and actual points for and against (about half of each team's season was captured).
  * Secondary: Basketball Index Lineup Explorer, 2013-14..2025-26 (61,037 lineups). Its ratings are Basketball Index's
    *stabilized* estimates (net rating spread ~8 points at every sample size, ~0.8 correlation with the players' summed
    LEBRON), so they show Basketball Index's own lineup model more than raw results. Reported for comparison only.
  * Player descriptions per season: Basketball Index progression table (3PT and catch-and-shoot 3PT talent, usage,
    playmaking, rim protection, perimeter defense, position).

Method
  Points per 100 possessions of each lineup = intercept + one effect per player (ridge-shrunk, like RAPM) + make-up terms,
  weighted by possessions, offense and defense separately. Because every player has his own effect, anything that is a
  plain sum over the five players (e.g. "number of shooters" counted linearly) is absorbed by the player effects; only
  the *non-additive* part of fit is identified: the third non-shooter costing more than the first two, a second
  ball-dominant creator adding less than the first, rim protection covering weak perimeter defenders, and so on.
  Linear counts are still included as nuisance terms (they soak up the ridge shrinkage) and are not interpreted.
  Uncertainty: bootstrap over teams (all of a team's lineups resampled together). Out-of-sample: 5-fold
  cross-validation over lineups, held-out possession-weighted error with and without the make-up terms.

  --engine also rebuilds the same regression on the game's own expected ratings for the same real lineups (players'
  game ratings, neutral opponent), so the game's built-in fit can be compared with the evidence term by term.

Writes data/canonical/lineup_fit.json (derived coefficients only; no Basketball Index rows) with --write.

Run: PYTHONPATH=src .venv/bin/python scripts/fit_lineup_fit.py [--boot 100] [--engine] [--explorer] [--write]
"""
from __future__ import annotations

import argparse
import collections
import csv
import gzip
import json
import math
import os
import random
import statistics
import sys
import time
from pathlib import Path
from typing import Any, Callable

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

TOOLS = ROOT / "data/research/bbi/tools"
XPOINTS = TOOLS / "xpoints_lineups.csv"
EXPLORER = (TOOLS / "lineup_explorer_2013_2019.csv.gz", TOOLS / "lineup_explorer_2019_2026.csv.gz")
PROGRESSION = TOOLS / "progression_player_seasons.csv.gz"
OUT = ROOT / "data/canonical/lineup_fit.json"
REPORT_DIR = ROOT / "output/lineup-fit"

# Player descriptions (Basketball Index z-scores within season unless noted).
SHOOTER_Z = -0.75        # spacing threat = mean of 3PT talent and catch-and-shoot 3PT talent; below this = non-shooter
SETTINGS = {"shooter_z": SHOOTER_Z}
CREATOR_USAGE = 25.0     # usage % at or above which a player is a ball-dominant creator
PLAYMAKER_Z = 1.5        # playmaking talent at or above which a player is a lead playmaker
RIM_PROTECTOR_Z = 1.5    # rim protection talent at or above which a player is a rim protector
WEAK_PERIMETER_Z = -0.5  # perimeter/isolation defense below which a player is a weak perimeter defender
LOW_VERSATILITY = 65.0   # defensive versatility (0-100) below which a player guards few positions

PLAYER_RIDGE = 2000.0    # possessions-equivalent shrinkage of each player's effect (RAPM-style prior ~2.5 pts/100)
XPOINTS_POSSESSION_SHARE = 0.70  # xPoints lineup possessions are ~70% of standard possessions (checked against games)


def number(value: Any, default: float | None = None) -> float | None:
    try:
        out = float(value)
    except (TypeError, ValueError):
        return default
    return out if math.isfinite(out) else default


# --------------------------------------------------------------------------------------------- player descriptions
def load_progression() -> dict[tuple[str, str], dict[str, Any]]:
    out = {}
    with gzip.open(PROGRESSION, "rt") as handle:
        for row in csv.DictReader(handle):
            three = number(row.get("X3PT_Shooting_Talent"))
            if three is None:
                continue
            catch = number(row.get("CS_3PT_Shooting_Talent"), three)
            out[(row["nba_player_id"], row["season"])] = {
                "shoot": (three + catch) / 2.0,
                "usage": number(row.get("USGPCT"), 15.0),
                "playmaking": number(row.get("playmaking_talent"), 0.0),
                "rim": number(row.get("rim_protection"), 0.0),
                "perimeter": number(row.get("perimeter_iso_defense"), 0.0),
                "versatility": number(row.get("Versatility"), 70.0),
                "center": row.get("position") == "C",
                "olebron": number(row.get("OLEBRON"), -1.5),
                "dlebron": number(row.get("DLEBRON"), -0.5),
            }
    return out


def flags(p: dict[str, Any], shooter_z: float | None = None) -> dict[str, bool]:
    if "game_flags" in p:
        return p["game_flags"]
    shooter_z = SETTINGS["shooter_z"] if shooter_z is None else shooter_z
    return {
        "non_shooter": p["shoot"] < shooter_z,
        "creator": p["usage"] >= CREATOR_USAGE,
        "playmaker": p["playmaking"] >= PLAYMAKER_Z,
        "rim_protector": p["rim"] >= RIM_PROTECTOR_Z,
        "weak_perimeter": p["perimeter"] < WEAK_PERIMETER_Z,
        "low_versatility": p["versatility"] < LOW_VERSATILITY,
        "big": p["center"],
        "non_shooting_big": p["center"] and p["shoot"] < shooter_z,
    }


def counts(players: list[dict[str, Any]], shooter_z: float | None = None) -> dict[str, int]:
    total: dict[str, int] = collections.Counter()
    for p in players:
        for key, value in flags(p, shooter_z).items():
            total[key] += int(value)
    return dict(total)


# Make-up terms. (name, function of counts, interpreted?) Non-interpreted terms are linear sums over players
# (absorbed by player effects) kept only as nuisance controls.
Term = tuple[str, Callable[[dict[str, int]], float], bool]
OFFENSE_TERMS: list[Term] = [
    ("non_shooters", lambda c: c["non_shooter"], False),
    ("non_shooters_beyond_2", lambda c: max(0, c["non_shooter"] - 2), True),
    ("five_shooters", lambda c: float(c["non_shooter"] == 0), True),
    ("creators", lambda c: c["creator"], False),
    ("creators_beyond_1", lambda c: max(0, c["creator"] - 1), True),
    ("playmakers", lambda c: c["playmaker"], False),
    ("has_lead_playmaker", lambda c: float(c["playmaker"] >= 1), True),
    ("bigs", lambda c: c["big"], False),
    ("two_bigs", lambda c: float(c["big"] >= 2), True),
    ("non_shooting_big_x_other_non_shooters", lambda c: float(c["non_shooting_big"] >= 1) * (c["non_shooter"] - c["non_shooting_big"]), True),
    # Does a ball-dominant creator get more out of each shooter around him (the game's spacing x creation bonus)?
    ("creator_x_shooters", lambda c: float(c["creator"] >= 1) * (5 - c["non_shooter"]), True),
    ("playmaker_x_shooters", lambda c: float(c["playmaker"] >= 1) * (5 - c["non_shooter"]), True),
]
DEFENSE_TERMS: list[Term] = [
    ("rim_protectors", lambda c: c["rim_protector"], False),
    ("has_rim_protector", lambda c: float(c["rim_protector"] >= 1), True),
    ("weak_perimeter", lambda c: c["weak_perimeter"], False),
    ("weak_perimeter_beyond_1", lambda c: max(0, c["weak_perimeter"] - 1), True),
    ("rim_protector_x_weak_perimeter", lambda c: float(c["rim_protector"] >= 1) * c["weak_perimeter"], True),
    ("low_versatility", lambda c: c["low_versatility"], False),
    ("low_versatility_beyond_1", lambda c: max(0, c["low_versatility"] - 1), True),
    ("non_shooters", lambda c: c["non_shooter"], False),
    ("non_shooters_beyond_2", lambda c: max(0, c["non_shooter"] - 2), True),
    ("bigs", lambda c: c["big"], False),
    ("two_bigs", lambda c: float(c["big"] >= 2), True),
]


# ------------------------------------------------------------------------------------------------ lineup datasets
def load_xpoints(progression: dict[tuple[str, str], dict[str, Any]]) -> list[dict[str, Any]]:
    out = []
    with XPOINTS.open() as handle:
        for row in csv.DictReader(handle):
            ids = [row[f"nba_player_id_{i}"] for i in range(1, 6)]
            players = [progression.get((pid, "2025-26")) for pid in ids]
            if any(p is None for p in players):
                continue
            out.append({
                "team": row["team"], "season": "2025-26", "ids": [f"{pid}:2025-26" for pid in ids],
                "sim_ids": [row[f"player_id_{i}"] for i in range(1, 6)], "players": players,
                "w_off": number(row["possessions"], 0.0), "w_def": number(row["def_possessions"], 0.0),
                "off": {"points": number(row["pts_for"], 0.0), "expected": number(row["xpts_for"], 0.0),
                        "turnovers": number(row["tov"], 0.0), "threes": number(row["fg3a"], 0.0)},
                "def": {"points": number(row["pts_against"], 0.0), "expected": number(row["xpts_against"], 0.0)},
            })
    return out


def load_explorer(progression: dict[tuple[str, str], dict[str, Any]]) -> list[dict[str, Any]]:
    out = []
    for path in EXPLORER:
        with gzip.open(path, "rt") as handle:
            for row in csv.DictReader(handle):
                season = row["season"]
                ids = [row[f"nba_player_id_{i}"] for i in range(1, 6)]
                players = [progression.get((pid, season)) for pid in ids]
                minutes = number(row["minutes"], 0.0)
                if any(p is None for p in players) or not minutes:
                    continue
                out.append({"team": f"{row['team']}:{season}", "season": season, "ids": [f"{pid}:{season}" for pid in ids],
                            "players": players, "w_off": minutes, "w_def": minutes,
                            "off_rating": number(row["rel_ortg"], 0.0), "def_rating": -number(row["rel_drtg"], 0.0)})
    return out


def game_flag_players(lineups: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Same lineups, but each player described by the game's own ratings (the definitions the engine term uses)."""
    os.environ.setdefault("NBA_GM_RATINGS_MODEL", "inputs_v1")
    from nba_gm_data.lineup_fit import player_fit_flags
    from nba_gm_data.sim import load_sim_context, player_feature_vector
    canonical = load_sim_context(ROOT)["canonical"]
    players = {p["id"]: p for p in canonical["players"]}
    traits: dict[str, dict[str, float]] = collections.defaultdict(dict)
    for row in canonical["traits"]:
        traits[str(row["player_id"])][row["trait_key"]] = float(row.get("value") or 50.0)
    cache: dict[str, dict[str, Any]] = {}
    out = []
    for lineup in lineups:
        if any(pid not in players for pid in lineup["sim_ids"]):
            continue
        described = []
        for pid, original in zip(lineup["sim_ids"], lineup["players"]):
            if pid not in cache:
                fv = player_feature_vector(canonical, players[pid]).features
                engine_flags = player_fit_flags(fv, players[pid])
                game = {
                    "non_shooter": engine_flags["non_shooter"],
                    "creator": engine_flags["creator"],
                    "playmaker": fv["passing"] >= 80.0,
                    "rim_protector": fv["rim_deterrence"] >= 97.0,
                    "weak_perimeter": fv["defensive_events"] < 50.0,
                    "low_versatility": traits[pid].get("portability", 50.0) < 50.0,
                    "big": str(players[pid].get("position") or "").upper().startswith("C"),
                }
                game["non_shooting_big"] = game["big"] and game["non_shooter"]
                cache[pid] = {"game_flags": game}
            described.append({**cache[pid], "olebron": original["olebron"], "dlebron": original["dlebron"]})
        out.append({**lineup, "players": described, "_counts": {}})
    return out


# ------------------------------------------------------------------------------------- ridge with player effects
def ridge_fit(rows: list[tuple[list[int], list[float]]], n_players: int, ys: list[float], ws: list[float],
              lam_player: float = PLAYER_RIDGE, lam_dense: float = 1e-6, tol: float = 1e-8, max_iter: int = 600,
              start: list[float] | None = None):
    """y = b0 + sum(player effects) + dense . beta, weighted; preconditioned conjugate gradient (pure Python)."""
    k = len(rows[0][1])
    off = 1 + n_players
    n = off + k
    diag = [0.0] * n
    rhs = [0.0] * n
    for (ps, dense), w, y in zip(rows, ws, ys):
        diag[0] += w
        rhs[0] += w * y
        for p in ps:
            diag[1 + p] += w
            rhs[1 + p] += w * y
        for j, x in enumerate(dense):
            diag[off + j] += w * x * x
            rhs[off + j] += w * y * x
    for p in range(n_players):
        diag[1 + p] += lam_player
    for j in range(k):
        diag[off + j] += lam_dense

    def matvec(v: list[float]) -> list[float]:
        out = [0.0] * n
        beta = v[off:]
        for (ps, dense), w in zip(rows, ws):
            s = v[0]
            for p in ps:
                s += v[1 + p]
            for j, x in enumerate(dense):
                s += x * beta[j]
            s *= w
            out[0] += s
            for p in ps:
                out[1 + p] += s
            for j, x in enumerate(dense):
                out[off + j] += s * x
        for p in range(n_players):
            out[1 + p] += lam_player * v[1 + p]
        for j in range(k):
            out[off + j] += lam_dense * v[off + j]
        return out

    if start is not None and len(start) == n:
        x = list(start)
        r = [a - b for a, b in zip(rhs, matvec(x))]
    else:
        x = [0.0] * n
        r = rhs[:]
    z = [ri / di if di else ri for ri, di in zip(r, diag)]
    p = z[:]
    rz = sum(a * b for a, b in zip(r, z))
    norm0 = math.sqrt(sum(a * a for a in rhs)) or 1.0
    for _ in range(max_iter):
        ap = matvec(p)
        alpha = rz / (sum(a * b for a, b in zip(p, ap)) or 1e-30)
        x = [xi + alpha * pi for xi, pi in zip(x, p)]
        r = [ri - alpha * api for ri, api in zip(r, ap)]
        if math.sqrt(sum(a * a for a in r)) / norm0 < tol:
            break
        z = [ri / di if di else ri for ri, di in zip(r, diag)]
        rz_new = sum(a * b for a, b in zip(r, z))
        p = [zi + (rz_new / rz) * pi for zi, pi in zip(z, p)]
        rz = rz_new
    _LAST_SOLUTION[:] = x
    return x[0], x[1:off], x[off:]


_LAST_SOLUTION: list[float] = []


CONTROL = {"mode": "players"}  # "players": one ridge effect per player; "lebron": summed O-/D-LEBRON instead


def design(lineups: list[dict[str, Any]], side: str, outcome: Callable[[dict[str, Any]], float | None],
           terms: list[Term], index: dict[str, int], shooter_z: float | None = None, weight_cap: float | None = None):
    rows, ys, ws = [], [], []
    lebron = CONTROL["mode"] == "lebron"
    for lineup in lineups:
        w = lineup["w_off" if side == "off" else "w_def"]
        y = outcome(lineup)
        if w <= 0 or y is None:
            continue
        c = lineup.get("_counts", {}).get(shooter_z)
        if c is None:
            c = counts(lineup["players"], shooter_z)
            lineup.setdefault("_counts", {})[shooter_z] = c
        dense = [float(fn(c)) for _, fn, _ in terms]
        if lebron:
            key = "olebron" if side == "off" else "dlebron"
            rows.append(([], dense + [sum(p[key] for p in lineup["players"])]))
        else:
            rows.append(([index[i] for i in lineup["ids"]], dense))
        ys.append(y)
        ws.append(min(w, weight_cap) if weight_cap else w)
    return rows, ys, ws


def estimate(lineups, side, outcome, terms, index, **kw) -> list[float]:
    rows, ys, ws = design(lineups, side, outcome, terms, index, **{k: v for k, v in kw.items() if k in ("shooter_z", "weight_cap")})
    return ridge_fit(rows, len(index), ys, ws, lam_player=kw.get("lam_player", PLAYER_RIDGE), start=kw.get("start"))[2]


def bootstrap(lineups, side, outcome, terms, index, reps: int, seed: int = 7, **kw) -> list[list[float]]:
    by_team: dict[str, list] = collections.defaultdict(list)
    for lineup in lineups:
        by_team[lineup["team"]].append(lineup)
    teams = sorted(by_team)
    rng = random.Random(seed)
    estimate(lineups, side, outcome, terms, index, **kw)
    kw = {**kw, "start": list(_LAST_SOLUTION)}  # warm start every replicate from the full-sample solution
    out = []
    for _ in range(reps):
        sample = []
        for _ in teams:
            sample.extend(by_team[rng.choice(teams)])
        out.append(estimate(sample, side, outcome, terms, index, **kw))
    return out


def cross_validate(lineups, side, outcome, terms, index, folds: int = 5, repeats: int = 2) -> dict[str, float]:
    """Held-out possession-weighted squared error: player effects + nuisance sums vs. that plus the fit terms."""
    nuisance = [t for t in terms if not t[2]]
    gains = []
    for rep in range(repeats):
        rng = random.Random(100 + rep)
        assignment = [rng.randrange(folds) for _ in lineups]
        for fold in range(folds):
            train = [l for l, a in zip(lineups, assignment) if a != fold]
            test = [l for l, a in zip(lineups, assignment) if a == fold]
            errors = []
            for spec in (nuisance, terms):
                rows, ys, ws = design(train, side, outcome, spec, index)
                b0, a, beta = ridge_fit(rows, len(index), ys, ws)
                trows, tys, tws = design(test, side, outcome, spec, index)
                sse = sum(w * (y - (b0 + sum(a[p] for p in ps) + sum(x * b for x, b in zip(d, beta)))) ** 2
                          for (ps, d), y, w in zip(trows, tys, tws))
                errors.append(sse / sum(tws))
            gains.append(errors[0] - errors[1])
    return {"mean_gain": statistics.fmean(gains), "se": statistics.stdev(gains) / math.sqrt(len(gains)), "folds": len(gains)}


def cross_validate_terms(lineups, side, outcome, terms, index, folds: int = 5, repeats: int = 2) -> dict[str, dict[str, float]]:
    """Out-of-sample value of each fit term on its own: held-out error of (player effects + nuisance sums) minus the
    error with that one term added. Positive = the term predicts unseen lineups better."""
    nuisance = [t for t in terms if not t[2]]
    gains: dict[str, list[float]] = collections.defaultdict(list)

    def heldout(train, test, spec):
        rows, ys, ws = design(train, side, outcome, spec, index)
        b0, a, beta = ridge_fit(rows, len(index), ys, ws)
        trows, tys, tws = design(test, side, outcome, spec, index)
        return sum(w * (y - (b0 + sum(a[p] for p in ps) + sum(x * b for x, b in zip(d, beta)))) ** 2
                   for (ps, d), y, w in zip(trows, tys, tws)) / sum(tws)

    for rep in range(repeats):
        rng = random.Random(200 + rep)
        assignment = [rng.randrange(folds) for _ in lineups]
        for fold in range(folds):
            train = [l for l, a in zip(lineups, assignment) if a != fold]
            test = [l for l, a in zip(lineups, assignment) if a == fold]
            base = heldout(train, test, nuisance)
            for term in terms:
                if term[2]:
                    gains[term[0]].append(base - heldout(train, test, nuisance + [term]))
    return {name: {"mean_gain": statistics.fmean(v), "se": statistics.stdev(v) / math.sqrt(len(v))} for name, v in gains.items()}


def player_index(lineups) -> dict[str, int]:
    return {pid: k for k, pid in enumerate(sorted({i for lineup in lineups for i in lineup["ids"]}))}


def per100(field: str, side: str) -> Callable[[dict[str, Any]], float | None]:
    def fn(lineup):
        w = lineup["w_off" if side == "off" else "w_def"]
        return 100.0 * lineup[side][field] / w if w > 0 else None
    return fn


# ----------------------------------------------------------------------------------------------- engine comparison
def engine_lineup_ratings(lineups: list[dict[str, Any]], cache: Path | None, with_fit: bool = False) -> dict[str, list[float]]:
    """The game's expected offensive/defensive rating (neutral floor, league-average opponent) for each real lineup.
    with_fit=False measures the game without the lineup fit (the "before" the fit is calibrated against)."""
    os.environ.setdefault("NBA_GM_RATINGS_MODEL", "inputs_v1")
    if not with_fit:
        os.environ["NBA_GM_LINEUP_FIT"] = "off"
    from nba_gm_data.sim import lineup_feature_vector, load_sim_context, neutral_off_rating
    canonical = load_sim_context(ROOT)["canonical"]
    players = {p["id"]: p for p in canonical["players"]}
    features: dict[str, dict[str, float]] = {}
    weight: dict[str, float] = collections.Counter()
    for lineup in lineups:
        if any(pid not in players for pid in lineup["sim_ids"]):
            continue
        key = "|".join(sorted(lineup["sim_ids"]))
        weight[key] += lineup["w_off"] + lineup["w_def"]
        if key not in features:
            features[key] = lineup_feature_vector(canonical, [{"player": players[pid], "minutes": 48.0} for pid in lineup["sim_ids"]])
    average: dict[str, Any] = {}
    for name in sorted({k for v in features.values() for k in v}):
        pairs = [(v[name], weight[key]) for key, v in features.items() if isinstance(v.get(name), (int, float))]
        if pairs:
            average[name] = sum(a * w for a, w in pairs) / sum(w for _, w in pairs)
    for v in features.values():
        if "offense_model_version" in v:
            average["offense_model_version"] = v["offense_model_version"]
            break
    ratings = {key: [neutral_off_rating(canonical, v, average), neutral_off_rating(canonical, average, v)] for key, v in features.items()}
    os.environ.pop("NBA_GM_LINEUP_FIT", None)
    if cache:
        cache.parent.mkdir(parents=True, exist_ok=True)
        cache.write_text(json.dumps(ratings))
    return ratings


# ------------------------------------------------------------------------------------------- team-level translation
ENGINE_TERMS = ("non_shooters_beyond_2", "five_shooters", "creator_x_shooters")


def actual_engine_terms(c: dict[str, int]) -> dict[str, float]:
    return {"non_shooters_beyond_2": max(0, c["non_shooter"] - 2), "five_shooters": float(c["non_shooter"] == 0),
            "creator_x_shooters": float(c["creator"] >= 1) * (5 - c["non_shooter"])}


def team_expectation_check(lineups: list[dict[str, Any]]) -> list[dict[str, float]]:
    """Does 'each player is on the floor for his share of possessions, independently' predict a team's lineup make-up?

    The game plays whole rotations, so its fit terms are expectations from on-floor shares (lineup_fit.expected_terms).
    Compares, per team, the possession-weighted actual value of each term with that prediction."""
    from nba_gm_data.lineup_fit import expected_terms
    by_team: dict[str, list] = collections.defaultdict(list)
    for lineup in lineups:
        by_team[lineup["team"]].append(lineup)
    rows = []
    for team, items in sorted(by_team.items()):
        total = sum(l["w_off"] + l["w_def"] for l in items)
        share: dict[str, float] = collections.Counter()
        player_by_id = {}
        actual: dict[str, float] = collections.Counter()
        for l in items:
            w = (l["w_off"] + l["w_def"]) / total
            for pid, p in zip(l["ids"], l["players"]):
                share[pid] += w * 48.0  # minutes-equivalent: on-floor share x 48
                player_by_id[pid] = p
            for key, value in actual_engine_terms(counts(l["players"])).items():
                actual[key] += w * value
        predicted = expected_terms([(flags(player_by_id[pid]), minutes) for pid, minutes in share.items()])
        rows.append({"team": team, **{f"actual_{k}": v for k, v in actual.items()}, **{f"pred_{k}": v for k, v in predicted.items()}})
    return rows


# ------------------------------------------------------------------------------------------------- market check
MARKET_TOLERANCE = 0.02  # points: the adopted terms together may not widen the game's average gap to the market by more


def market_rows() -> list[dict[str, Any]]:
    """Every 2025-26 regular-season game with a market line: the game's expected offensive ratings with the fit off
    (real minutes, real availability), each rotation's fit flags, and the market's spread and total."""
    os.environ["NBA_GM_LINEUP_FIT"] = "off"
    os.environ.setdefault("NBA_GM_RATINGS_MODEL", "inputs_v1")
    from nba_gm_data import sim
    from nba_gm_data.lineup_fit import player_fit_flags
    ctx = sim.load_sim_context(ROOT)
    canonical = ctx["canonical"]
    coaches = {r.team_id: r for r in sim.coach_ratings(canonical)}
    teams = ctx["indices"]["teams_by_espn_id"]
    rows = []
    for game in ctx["schedule"]:
        if str(game.get("phase", "regular")) not in ("regular", "None", ""):
            continue
        gid = str(game["externalGameId"])
        odds = ctx["odds"].get(gid) or {}
        line = (odds.get("spread") or {}).get("home_line")
        total = (odds.get("total") or {}).get("line") or (odds.get("total") or {}).get("points")
        if line is None:
            continue
        home, away = teams[str(game["homeTeamId"])], teams[str(game["awayTeamId"])]
        side = {}
        for team in (home, away):
            pool = sim.game_player_pool(ctx, gid, team, "replay-real-minutes", game_date=game.get("gameDate"))
            features = sim.game_team_features(ctx, canonical, team, pool, "replay-real-minutes")
            entries = [(player_fit_flags(sim.health_adjusted_player_features(sim.player_feature_vector(canonical, item["player"]).features, item),
                                         item["player"]), float(item.get("minutes") or 0.0)) for item in pool]
            side[team["id"]] = (features, entries)
        (hf, he), (af, ae) = side[home["id"]], side[away["id"]]
        ch, ca = coaches.get(home["id"]), coaches.get(away["id"])
        rows.append({"off_h": sim.neutral_off_rating(canonical, hf, af, ch, ca), "off_a": sim.neutral_off_rating(canonical, af, hf, ca, ch),
                     "home_entries": he, "away_entries": ae, "market_margin": -float(line),
                     "market_total": float(total) if total else None})
    os.environ.pop("NBA_GM_LINEUP_FIT", None)
    return rows


def market_gaps(rows: list[dict[str, Any]], fit: dict[str, Any] | None) -> dict[str, float]:
    """Mean absolute gap between the game's expected spread/total and the market's (constant offsets removed: the
    game's home edge and scoring level are calibrated elsewhere), and how the fit's margin moves with the gap."""
    from nba_gm_data.lineup_fit import lineup_fit_effect
    poss = 101.5
    margins, totals, deltas, gaps = [], [], [], []
    for r in rows:
        dh = lineup_fit_effect(r["home_entries"], coefficients=fit) if fit else {"offense": 0.0, "defense": 0.0}
        da = lineup_fit_effect(r["away_entries"], coefficients=fit) if fit else {"offense": 0.0, "defense": 0.0}
        oh = r["off_h"] + dh["offense"] + da["defense"]
        oa = r["off_a"] + da["offense"] + dh["defense"]
        base = (r["off_h"] - r["off_a"]) * poss / 100
        margins.append(((oh - oa) * poss / 100, r["market_margin"]))
        deltas.append((oh - oa) * poss / 100 - base)
        gaps.append(r["market_margin"] - base)
        if r["market_total"]:
            totals.append(((oh + oa) * poss / 100, r["market_total"]))
    m_off = statistics.fmean(m - k for m, k in margins)
    t_off = statistics.fmean(t - k for t, k in totals)
    return {"spread_gap": statistics.fmean(abs(m - k - m_off) for m, k in margins),
            "total_gap": statistics.fmean(abs(t - k - t_off) for t, k in totals),
            "corr_with_market_gap": statistics.correlation(deltas, gaps) if fit and statistics.pstdev(deltas) > 0 else 0.0}


def market_gate(fit: dict[str, Any]) -> tuple[dict[str, Any], dict[str, Any]]:
    """Keep the evidence-adopted terms only as a set that does not move the game away from the 2025-26 betting market:
    while the set widens the spread or total gap by more than MARKET_TOLERANCE, drop the term whose removal narrows the
    spread gap most. (The full odds test confirms the final set.)"""
    rows = market_rows()
    base = market_gaps(rows, None)
    report = {"games": len(rows), "fit_off": base, "steps": []}
    current = {**fit, "offense": dict(fit["offense"]), "defense": dict(fit["defense"])}
    print(f"== market check on {len(rows)} games: fit off spread gap {base['spread_gap']:.3f}, total gap {base['total_gap']:.3f}")
    for side in ("offense", "defense"):
        for term in list(current[side]):
            alone = {**current, "offense": {}, "defense": {}}
            alone[side] = {term: current[side][term]}
            g = market_gaps(rows, alone)
            report[f"only {side}:{term}"] = g
            print(f"   only {side}:{term:28s} spread {g['spread_gap'] - base['spread_gap']:+.3f}  total {g['total_gap'] - base['total_gap']:+.3f}"
                  f"  correlation with the market gap {g['corr_with_market_gap']:+.3f}")
    while current["offense"] or current["defense"]:
        g = market_gaps(rows, current)
        terms = [(s, t) for s in ("offense", "defense") for t in current[s]]
        report["steps"].append({"terms": [f"{s}:{t}" for s, t in terms], **g})
        print(f"   set {', '.join(t for _, t in terms):60s} spread {g['spread_gap'] - base['spread_gap']:+.3f}  total {g['total_gap'] - base['total_gap']:+.3f}")
        if g["spread_gap"] - base["spread_gap"] <= MARKET_TOLERANCE and g["total_gap"] - base["total_gap"] <= MARKET_TOLERANCE:
            break
        best = None
        for s, t in terms:
            trial = {**current, "offense": dict(current["offense"]), "defense": dict(current["defense"])}
            del trial[s][t]
            spread = market_gaps(rows, trial)["spread_gap"] if trial["offense"] or trial["defense"] else base["spread_gap"]
            if best is None or spread < best[0]:
                best = (spread, s, t)
        print(f"   -> drop {best[1]}:{best[2]}")
        del current[best[1]][best[2]]
    return current, report


# ------------------------------------------------------------------------------------------------ adoption + write
PRIOR_SD = 2.0  # prior spread of true non-additive effects, points per 100 xPoints possessions (shrinks noisy estimates)
MIN_Z = 1.5     # an effect must stand at least this many standard errors from zero (actual or expected points)
MIN_GAP = 0.5   # and differ from what the game already does by at least this much (points per 100 possessions)


def term_row(table: list[dict[str, Any]], name: str) -> dict[str, Any] | None:
    return next((row for row in table if row["term"] == name), None)


def write_fit(results: dict[str, Any], engine: dict[str, Any], team_check: dict[str, Any], league_mean: dict[str, float],
              creator_shooters_mean: float) -> None:
    """Adopt a term only if (1) it has the same sign when players are described by Basketball Index instead of by the
    game's ratings, (2) it is at least MIN_Z standard errors from zero on actual or expected points, (3) the shrunk
    evidence differs from the game's current behaviour by MIN_GAP, and (4) the adopted set passes market_gate (it must not
    move the game's 2025-26 team strengths away from the betting market). The game adds the difference."""
    bbi_path = REPORT_DIR / f"fit_report_bbi_players_{SHOOTER_Z:+.3f}.json"
    if not bbi_path.exists():
        raise SystemExit(f"run the Basketball Index description first: --flags bbi --boot 100 (expects {bbi_path.name})")
    bbi = json.loads(bbi_path.read_text())["xpoints"]
    decisions = {}
    fit: dict[str, Any] = {"offense": {}, "defense": {}}
    print("== adoption (points per 100 standard possessions after shrinkage and the xPoints possession conversion)")
    for side_key, side in (("off", "offense"), ("def", "defense")):
        for term, _, interpreted in (OFFENSE_TERMS if side_key == "off" else DEFENSE_TERMS):
            if not interpreted:
                continue
            actual = term_row(results[f"{side_key} points"], term)
            expected = term_row(results[f"{side_key} expected"], term)
            other = term_row(bbi[f"{side_key} points"], term)
            game_now = term_row(engine[side_key], term)["estimate"]
            shrink = PRIOR_SD ** 2 / (PRIOR_SD ** 2 + actual["se"] ** 2)
            target = actual["estimate"] * shrink * XPOINTS_POSSESSION_SHARE
            same_sign = other is not None and other["estimate"] * actual["estimate"] > 0
            z_actual = abs(actual["estimate"]) / actual["se"]
            z_expected = abs(expected["estimate"]) / expected["se"] if expected["estimate"] * actual["estimate"] > 0 else 0.0
            clear = max(z_actual, z_expected) >= MIN_Z
            gap = target - game_now
            adopted = same_sign and clear and abs(gap) >= MIN_GAP
            decisions[f"{side}:{term}"] = {
                "evidence": actual["estimate"], "se": actual["se"], "expected_points": expected["estimate"],
                "expected_se": expected["se"], "basketball_index_description": other["estimate"] if other else None,
                "target_per_100": round(target, 3), "game_before": game_now, "added": round(gap, 3) if adopted else 0.0,
                "same_sign": same_sign, "clear_of_noise": clear, "adopted": adopted,
            }
            print(f"   {side:7s} {term:40s} evidence {actual['estimate']:+5.2f}+-{actual['se']:.2f}"
                  f"  BBI {other['estimate'] if other else float('nan'):+5.2f}  target {target:+5.2f}  game {game_now:+5.2f}"
                  f"  -> {'ADD ' + format(gap, '+.2f') if adopted else 'no change'}")
            if adopted:
                if term not in ENGINE_TERMS:
                    raise SystemExit(f"{term} passed the rule but lineup_fit.py does not implement it")
                fit[side][term] = round(gap, 4)
    payload = {
        "version": "lineup_fit_v1",
        "source": "Basketball Index xPoints lineups 2025-26 (scripts/fit_lineup_fit.py); derived coefficients only",
        "units": "points per 100 possessions per unit of the term; offense = points scored, defense = points allowed",
        "offense": fit["offense"], "defense": fit["defense"],
        "league_mean": {k: round(v, 4) for k, v in league_mean.items()},
        "creator_shooters_mean": round(creator_shooters_mean, 4),
        # Rotations: coaches stagger non-shooters and avoid all-shooter units less than chance would; the creator
        # slope term is centered within each team's creator minutes, so it carries no ratio.
        "rotation_ratio": {k: round(team_check[k]["ratio"], 4) for k in ENGINE_TERMS if k != "creator_x_shooters"},
        "rule": {"prior_sd": PRIOR_SD, "min_z": MIN_Z, "min_gap": MIN_GAP, "possession_share": XPOINTS_POSSESSION_SHARE,
                 "market_tolerance": MARKET_TOLERANCE},
        "decisions": decisions,
    }
    kept, market = market_gate(payload)
    for key, row in decisions.items():
        side, term = key.split(":")
        row["evidence_adopted"] = row.pop("adopted")
        row["kept_by_market_check"] = term in kept[side] if row["evidence_adopted"] else None
        row["adopted"] = bool(row["evidence_adopted"] and row["kept_by_market_check"])
        if not row["adopted"]:
            row["added"] = 0.0
    payload["offense"], payload["defense"] = kept["offense"], kept["defense"]
    payload["market_check"] = market
    OUT.write_text(json.dumps(payload, indent=1) + "\n")
    print(f"wrote {OUT.relative_to(ROOT)}")


# ---------------------------------------------------------------------------------------------------------- main
def describe(name: str, point: list[float], boots: list[list[float]], terms: list[Term], scale: float = 1.0) -> list[dict[str, Any]]:
    print(f"== {name}")
    out = []
    for j, (term, _, interpreted) in enumerate(terms):
        values = [b[j] for b in boots] if boots else []
        se = statistics.pstdev(values) if len(values) > 1 else float("nan")
        tag = "" if interpreted else "  (sum over players; absorbed by player effects, not interpreted)"
        print(f"   {term:40s} {point[j] * scale:+6.2f}  se {se * scale:5.2f}{tag}")
        out.append({"term": term, "estimate": round(point[j] * scale, 3), "se": round(se * scale, 3), "interpreted": interpreted})
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--boot", type=int, default=100)
    ap.add_argument("--engine", action="store_true", help="also fit the game's own lineup ratings (loads the engine)")
    ap.add_argument("--engine-cache", default=None, help="reuse/write engine lineup ratings JSON")
    ap.add_argument("--engine-with-fit", action="store_true", help="measure the game with the lineup fit on (after check)")
    ap.add_argument("--explorer", action="store_true", help="also fit the Lineup Explorer (stabilized) ratings")
    ap.add_argument("--cv", action="store_true", help="5-fold out-of-sample check")
    ap.add_argument("--sensitivity", action="store_true")
    ap.add_argument("--flags", choices=["bbi", "game"], default="bbi",
                    help="describe players by Basketball Index measures (independent) or by the game's own ratings")
    ap.add_argument("--control", choices=["players", "lebron"], default="players",
                    help="hold each player's own effect fixed (ridge, default) or control for summed LEBRON instead")
    ap.add_argument("--shooter-z", type=float, default=SHOOTER_Z)
    ap.add_argument("--tag", default="", help="suffix for the report file name")
    ap.add_argument("--write", action="store_true")
    args = ap.parse_args()
    t0 = time.time()
    CONTROL["mode"] = args.control
    SETTINGS["shooter_z"] = args.shooter_z
    progression = load_progression()
    lineups = load_xpoints(progression)
    if args.flags == "game":
        lineups = game_flag_players(lineups)
    index = player_index(lineups)
    total_poss = sum(l["w_off"] + l["w_def"] for l in lineups)
    print(f"xPoints lineups {len(lineups)}  players {len(index)}  possessions {total_poss:,.0f}  [{time.time() - t0:.0f}s]")
    report: dict[str, Any] = {"lineups": len(lineups), "players": len(index), "possessions": total_poss}

    # Raw view: offensive rating by non-shooter count (no controls).
    raw = collections.defaultdict(lambda: [0.0, 0.0, 0.0])
    for l in lineups:
        k = counts(l["players"])["non_shooter"]
        raw[k][0] += l["off"]["points"]
        raw[k][1] += l["w_off"]
        raw[k][2] += sum(p.get("olebron", 0.0) for p in l["players"]) * l["w_off"]
    print("raw offensive rating by non-shooters on the floor (no controls):")
    for k in sorted(raw):
        a = raw[k]
        print(f"   {k}: {a[1]:7.0f} poss  {100 * a[0] / a[1]:6.1f} per 100   summed O-LEBRON {a[2] / a[1]:+.2f}")

    results: dict[str, Any] = {}
    raw_boot: dict[str, Any] = {}
    for side, terms in (("off", OFFENSE_TERMS), ("def", DEFENSE_TERMS)):
        for outcome in ("points", "expected"):
            fn = per100(outcome, side)
            point = estimate(lineups, side, fn, terms, index)
            boots = bootstrap(lineups, side, fn, terms, index, args.boot) if args.boot else []
            label = f"{side} {outcome}"
            results[label] = describe(f"xPoints {label} per 100 xPoints possessions ({'+ = more points scored' if side == 'off' else '+ = more points allowed'})",
                                      point, boots, terms)
            raw_boot[label] = (point, boots)
    report["xpoints"] = results
    # Net effect (points scored minus allowed) for terms on both sides. The bootstrap uses the same team draws on
    # both sides (same seed), so replicates pair up and the net standard error includes their correlation.
    net = {}
    for outcome in ("points", "expected"):
        off_point, off_boots = raw_boot[f"off {outcome}"]
        def_point, def_boots = raw_boot[f"def {outcome}"]
        print(f"== net (offense minus defense) {outcome}, per 100 xPoints possessions")
        for name in ("non_shooters_beyond_2", "two_bigs"):
            i = [t[0] for t in OFFENSE_TERMS].index(name)
            j = [t[0] for t in DEFENSE_TERMS].index(name)
            value = off_point[i] - def_point[j]
            reps = [a[i] - b[j] for a, b in zip(off_boots, def_boots)]
            se = statistics.pstdev(reps) if len(reps) > 1 else float("nan")
            print(f"   {name:40s} {value:+6.2f}  se {se:5.2f}")
            net[f"{outcome}:{name}"] = {"estimate": round(value, 3), "se": round(se, 3)}
    report["net"] = net

    if args.sensitivity:
        sens = {}
        for z in (-1.0, -0.5):
            point = estimate(lineups, "off", per100("points", "off"), OFFENSE_TERMS, index, shooter_z=z)
            sens[f"shooter_z {z}"] = describe(f"sensitivity: non-shooter threshold z < {z} (offense points)", point, [], OFFENSE_TERMS)
        point = estimate(lineups, "off", per100("points", "off"), OFFENSE_TERMS, index, weight_cap=300.0)
        sens["weight cap 300"] = describe("sensitivity: weights capped at 300 possessions (offense points)", point, [], OFFENSE_TERMS)
        point = estimate(lineups, "def", per100("points", "def"), DEFENSE_TERMS, index, weight_cap=300.0)
        sens["def weight cap 300"] = describe("sensitivity: weights capped at 300 possessions (defense points)", point, [], DEFENSE_TERMS)
        for lam in (500.0, 8000.0):
            point = estimate(lineups, "off", per100("points", "off"), OFFENSE_TERMS, index, lam_player=lam)
            sens[f"ridge {lam}"] = describe(f"sensitivity: player ridge {lam} (offense points)", point, [], OFFENSE_TERMS)
        report["sensitivity"] = sens

    if args.cv:
        cv = {}
        for side, terms in (("off", OFFENSE_TERMS), ("def", DEFENSE_TERMS)):
            cv[side] = cross_validate(lineups, side, per100("points", side), terms, index)
            print(f"out-of-sample {side}: held-out squared error lower by {cv[side]['mean_gain']:+.2f} ± {cv[side]['se']:.2f} "
                  f"(per possession-weighted lineup, {cv[side]['folds']} folds)")
        report["cross_validation"] = cv
        per_term = {}
        for side, terms in (("off", OFFENSE_TERMS), ("def", DEFENSE_TERMS)):
            per_term[side] = cross_validate_terms(lineups, side, per100("points", side), terms, index)
            for name, row in per_term[side].items():
                print(f"   out-of-sample {side} {name:40s} {row['mean_gain']:+.3f} ± {row['se']:.3f}")
        report["cross_validation_terms"] = per_term

    check = team_expectation_check(lineups)
    print("team-level check: actual lineup make-up vs independent on-floor prediction (mean over teams)")
    team_check = {}
    for key in ENGINE_TERMS:
        a = [r[f"actual_{key}"] for r in check]
        p = [r[f"pred_{key}"] for r in check]
        ratio = sum(a) / sum(p) if sum(p) else float("nan")
        print(f"   {key:24s} actual {statistics.fmean(a):.3f}  predicted {statistics.fmean(p):.3f}  ratio {ratio:.2f}  r {statistics.correlation(a, p):.2f}"
              f"  team range {min(a):.2f}..{max(a):.2f}")
        team_check[key] = {"actual": statistics.fmean(a), "predicted": statistics.fmean(p), "ratio": ratio,
                           "r": statistics.correlation(a, p), "team_min": min(a), "team_max": max(a)}
    report["team_check"] = team_check
    total_w = sum(l["w_off"] + l["w_def"] for l in lineups)
    league_mean = {key: sum((l["w_off"] + l["w_def"]) * actual_engine_terms(counts(l["players"]))[key] for l in lineups) / total_w
                   for key in ENGINE_TERMS}
    # The creator term is a slope: shooters counted from the usual number beside a creator, so it averages zero.
    with_creator = [(l["w_off"] + l["w_def"], counts(l["players"])) for l in lineups]
    creator_weight = sum(w for w, c in with_creator if c["creator"] >= 1)
    creator_shooters_mean = sum(w * (5 - c["non_shooter"]) for w, c in with_creator if c["creator"] >= 1) / creator_weight
    league_mean["creator_x_shooters"] = 0.0
    print(f"   shooters beside a creator: {creator_shooters_mean:.2f} on average ({creator_weight / total_w:.0%} of possessions have a creator)")

    if args.engine:
        cache = Path(args.engine_cache) if args.engine_cache else None
        if cache and cache.exists():
            ratings = json.loads(cache.read_text())
        else:
            ratings = engine_lineup_ratings(lineups, cache, with_fit=args.engine_with_fit)
        engine_lineups = []
        for l in lineups:
            key = "|".join(sorted(l["sim_ids"]))
            if key in ratings:
                engine_lineups.append({**l, "off": {"points": ratings[key][0] * l["w_off"] / 100}, "def": {"points": ratings[key][1] * l["w_def"] / 100}})
        eng = {}
        for side, terms in (("off", OFFENSE_TERMS), ("def", DEFENSE_TERMS)):
            point = estimate(engine_lineups, side, per100("points", side), terms, index)
            eng[side] = describe(f"GAME {side}: same regression on the game's expected ratings for {len(engine_lineups)} real lineups", point, [], terms)
        report["engine"] = eng

    if args.write:
        if args.flags != "game" or args.control != "players" or not args.engine or args.boot < 20:
            raise SystemExit("--write needs --flags game --control players --engine and a bootstrap (it fits in the game's own terms)")
        write_fit(results, report["engine"], team_check, league_mean, creator_shooters_mean)

    if args.explorer:
        explorer = load_explorer(progression)
        eindex = player_index(explorer)
        print(f"Lineup Explorer lineups {len(explorer)}  player-seasons {len(eindex)}")
        exp_res = {}
        for side, terms in (("off", OFFENSE_TERMS), ("def", DEFENSE_TERMS)):
            fn = (lambda l: l["off_rating"]) if side == "off" else (lambda l: l["def_rating"])
            point = estimate(explorer, side, fn, terms, eindex, lam_player=30.0)
            boots = bootstrap(explorer, side, fn, terms, eindex, min(args.boot, 20), lam_player=30.0) if args.boot else []
            exp_res[side] = describe(f"Lineup Explorer {side} (stabilized ratings, minutes-weighted; {'+ = better offense' if side == 'off' else '+ = more points allowed'})",
                                     point, boots, terms)
        report["explorer"] = exp_res

    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    (REPORT_DIR / f"fit_report_{args.flags}_{args.control}_{args.shooter_z:+.3f}{args.tag}.json").write_text(json.dumps(report, indent=1, default=str))
    print(f"report -> {REPORT_DIR.relative_to(ROOT)}/fit_report_{args.flags}_{args.control}.json  [{time.time() - t0:.0f}s]")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
