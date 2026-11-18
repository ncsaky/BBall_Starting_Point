#!/usr/bin/env python3
"""Real college prospects for the first future drafts (2027-2029): draft projection, evidence fits, game bundle.

Reads the local Barttorvik tables (data/research/barttorvik/raw, git-ignored) and writes the committed, derived
game file data/canonical/real_prospects.json. Re-run later in the college season to refresh the bundle:

    PYTHONPATH=src .venv/bin/python scripts/research/real_prospects.py            # fit, evaluate, write bundle
    PYTHONPATH=src .venv/bin/python scripts/research/real_prospects.py --apply-universe
        # also rebuild the stored 2027 class in data/canonical/universe_2026_27_offseason.json

What it does (details in docs/agents/tasks/real-prospects.md):
1. Draft projection from history. For every college player-season 2008-2026 and each horizon h = 0, 1, 2 it
   fits (a) the chance he is drafted in the draft h years later (logistic regression) and (b) his pick if drafted
   (regression on log pick). Features: recruit rating, age on draft day, class year, box plus-minus split,
   usage, minutes share, height, team strength, the prior season's plus-minus and a few skill rates.
   Checked out of sample: fit on drafts up to 2021, scored on the 2022-2026 drafts.
2. Current players. The 2026-27 season is only a few games old, so each player's current level blends this
   season's games with last season (moved forward by the typical one-year change for his class) or, for
   freshmen, with the average freshman of his recruiting band. Each player joins at most one class (2027, 2028
   or 2029: the one he is most likely to be drafted in), is ranked by expected draft value, and is given the
   draft slot that the same rank among college draftees has historically gone (other slots belong to players the
   data cannot see: international, high-school and G League prospects).
3. College -> pro skills. Final college seasons of players drafted 2019-2025 are paired with their current
   94-input ratings (data/canonical/player_inputs_2026_27.json); a small regression per skill (adjusted for
   years in the league and draft slot) gives the direction and size used in the game.
"""
from __future__ import annotations

import argparse
import csv
import datetime as dt
import hashlib
import json
import math
import re
import statistics
import sys
import unicodedata
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts" / "research"))
sys.path.insert(0, str(ROOT / "src"))

import barttorvik  # noqa: E402

RAW = barttorvik.RAW_DIR
TEAMS = RAW / "teams"
COACHES = RAW / "coaches.json"
BUNDLE = ROOT / "data" / "canonical" / "real_prospects.json"
REPORT = ROOT / "output" / "real-prospects" / "report.json"
CURRENT_SEASON = 2027          # the 2026-27 college season (only a few games played)
FIRST_SEASON = 2008
HORIZONS = (0, 1, 2)           # draft in the same spring, one year later, two years later
TRAIN_LAST_DRAFT = 2021        # out-of-sample check: fit on drafts <= 2021 ...
TEST_DRAFTS = tuple(range(2022, 2027))  # ... score the 2022-2026 drafts
DRAFT_DAY = (6, 25)
PAIR_DRAFTS = range(2019, 2026)
NEGATIVE_SHARE = 0.15

# ----------------------------------------------------------------------------------------------- small numerics


def solve(matrix: list[list[float]], vector: list[float]) -> list[float]:
    n = len(vector)
    a = [row[:] + [vector[i]] for i, row in enumerate(matrix)]
    for col in range(n):
        pivot = max(range(col, n), key=lambda r: abs(a[r][col]))
        a[col], a[pivot] = a[pivot], a[col]
        p = a[col][col] or 1e-12
        for r in range(n):
            if r != col and a[r][col]:
                f = a[r][col] / p
                a[r] = [x - f * y for x, y in zip(a[r], a[col])]
    return [a[i][n] / (a[i][i] or 1e-12) for i in range(n)]


def standardizer(rows: list[list[float]]) -> tuple[list[float], list[float]]:
    k = len(rows[0])
    means = [statistics.fmean(r[j] for r in rows) for j in range(k)]
    sds = [statistics.pstdev([r[j] for r in rows]) or 1.0 for j in range(k)]
    return means, sds


def logistic_fit(x: list[list[float]], y: list[int], w: list[float], ridge: float = 1.0) -> list[float]:
    """Weighted L2 logistic regression (Newton). x already standardized; intercept added here."""
    k = len(x[0]) + 1
    beta = [0.0] * k
    xs = [[1.0, *row] for row in x]
    for _ in range(25):
        grad = [0.0] * k
        hess = [[0.0] * k for _ in range(k)]
        for row, target, weight in zip(xs, y, w):
            z = sum(b * v for b, v in zip(beta, row))
            p = 1 / (1 + math.exp(-max(-35, min(35, z))))
            g = weight * (target - p)
            h = weight * p * (1 - p)
            for i in range(k):
                grad[i] += g * row[i]
                hi = h * row[i]
                hrow = hess[i]
                for j in range(i, k):
                    hrow[j] += hi * row[j]
        for i in range(k):
            for j in range(i):
                hess[i][j] = hess[j][i]
            if i:
                grad[i] -= ridge * beta[i]
                hess[i][i] += ridge
        step = solve(hess, grad)
        beta = [b + s for b, s in zip(beta, step)]
        if max(abs(s) for s in step) < 1e-7:
            break
    return beta


def linear_fit(x: list[list[float]], y: list[float], ridge: float = 1.0, w: list[float] | None = None) -> list[float]:
    k = len(x[0]) + 1
    w = w or [1.0] * len(y)
    xtx = [[0.0] * k for _ in range(k)]
    xty = [0.0] * k
    for row, target, weight in zip(x, y, w):
        r = [1.0, *row]
        for i in range(k):
            xty[i] += weight * r[i] * target
            for j in range(k):
                xtx[i][j] += weight * r[i] * r[j]
    for i in range(1, k):
        xtx[i][i] += ridge
    return solve(xtx, xty)


def dot(beta: list[float], row: list[float]) -> float:
    return beta[0] + sum(b * v for b, v in zip(beta[1:], row))


def sigmoid(z: float) -> float:
    return 1 / (1 + math.exp(-max(-35, min(35, z))))


def auc(scores: list[float], labels: list[int]) -> float:
    pairs = sorted(zip(scores, labels))
    rank_sum, pos, n = 0.0, 0, len(pairs)
    i = 0
    while i < n:
        j = i
        while j < n and pairs[j][0] == pairs[i][0]:
            j += 1
        avg_rank = (i + j + 1) / 2
        for k in range(i, j):
            if pairs[k][1]:
                rank_sum += avg_rank
                pos += 1
        i = j
    neg = n - pos
    return (rank_sum - pos * (pos + 1) / 2) / (pos * neg) if pos and neg else float("nan")


def spearman(a: list[float], b: list[float]) -> float:
    def ranks(v):
        order = sorted(range(len(v)), key=lambda i: v[i])
        r = [0.0] * len(v)
        for pos, i in enumerate(order):
            r[i] = pos
        return r
    ra, rb = ranks(a), ranks(b)
    return statistics.correlation(ra, rb) if len(a) > 2 else float("nan")


def stable_unit(*parts) -> float:
    digest = hashlib.sha256(json.dumps(parts).encode()).digest()
    return int.from_bytes(digest[:8], "big") / 2**64


# ----------------------------------------------------------------------------------------------- data


def num(value, default=0.0):
    return default if value is None or value == "" or isinstance(value, str) else float(value)


def load_team_context() -> dict[tuple[int, str], dict]:
    ctx = {}
    for path in sorted(TEAMS.glob("team_results_*.csv")):
        season = int(path.stem.split("_")[-1])
        with path.open(newline="", encoding="utf-8") as handle:
            for row in csv.DictReader(handle):
                try:
                    ctx[(season, row["team"])] = {"barthag": float(row["barthag"]), "adjoe": float(row["adjoe"]),
                                                  "adjde": float(row["adjde"]), "conf": row.get("conf")}
                except (KeyError, ValueError):
                    continue
    return ctx


def load_coaches() -> dict[tuple[int, str], str]:
    """Optional coach names per team-season (captured separately; absent until that capture lands)."""
    if not COACHES.exists():
        return {}
    try:
        rows = json.loads(COACHES.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    rows = rows.get("coaches", rows) if isinstance(rows, dict) else rows
    out = {}
    for row in rows or []:
        try:
            out[(int(row["year"]), str(row["team"]))] = str(row["coach_name"])
        except (KeyError, TypeError, ValueError):
            continue
    return out


def season_minutes(row) -> float:
    return num(row.get("mpg")) * num(row.get("games"))


def known_birth_date(row) -> dt.date | None:
    """Barttorvik fills unknown birthdays with October 15 of a class-typical year; treat those as unknown."""
    text = str(row.get("birth_date") or "")[:10]
    if not text or text.endswith("-10-15"):
        return None
    try:
        return dt.date.fromisoformat(text)
    except ValueError:
        return None


CLASS_INDEX = {"Fr": 0, "So": 1, "Jr": 2, "Sr": 3}
# Age on draft day by class year in the draft season (players with a real birthday).
TYPICAL_AGE_BY_CLASS = {0: 19.3, 1: 20.3, 2: 21.3, 3: 22.4}


def class_index(row) -> int:
    return CLASS_INDEX.get(str(row.get("class_year") or "")[:2], 2)


# ----------------------------------------------------------------------------------------------- college profile
# Derived rates used by both the draft model and the skill mapping. Shooting uses career makes/attempts with a
# prior (small samples shrink toward typical college shooting).
FT_PRIOR, FT_PRIOR_N = 0.705, 60.0
THREE_PRIOR, THREE_PRIOR_N = 0.335, 100.0
RIM_PRIOR, RIM_PRIOR_N = 0.60, 40.0
MID_PRIOR, MID_PRIOR_N = 0.37, 50.0

from nba_gm_data.real_prospects import (  # noqa: E402  (shared with the game: one definition of the skill scale)
    PROFILE_RATES, SKILL_COMPOSITES, composite, input_parts, pair_features, size_score, skill_scores)


def season_rates(row) -> dict[str, float]:
    minutes = max(1.0, season_minutes(row))
    fga = num(row.get("two_a")) + num(row.get("three_a"))
    rim_m, mid_m = num(row.get("rim_m")), num(row.get("mid_m"))
    unast = rim_m * (1 - num(row.get("rim_ast_pct"), 50) / 100) + mid_m * (1 - num(row.get("mid_ast_pct"), 50) / 100)
    return {
        "min_pct": num(row.get("min_pct")), "usg": num(row.get("usg"), 18), "ortg": num(row.get("ortg"), 100),
        "ts": num(row.get("ts"), 52), "orb_pct": num(row.get("orb_pct")), "drb_pct": num(row.get("drb_pct")),
        "ast_pct": num(row.get("ast_pct")), "tov_pct": num(row.get("tov_pct"), 18), "blk_pct": num(row.get("blk_pct")),
        "stl_pct": num(row.get("stl_pct")), "ftr": num(row.get("ftr"), 30), "gbpm": num(row.get("gbpm"), -3),
        "ogbpm": num(row.get("ogbpm"), -2), "dgbpm": num(row.get("dgbpm"), -1),
        "three_rate": num(row.get("three_a")) / fga if fga else 0.3,
        "three_per40": num(row.get("three_a")) / minutes * 40,
        "rim_per40": num(row.get("rim_a")) / minutes * 40,
        "dunk_per40": num(row.get("dunk_a")) / minutes * 40,
        "unast_per40": unast / minutes * 40,
        "unast_three": 1 - num(row.get("three_ast_pct"), 85) / 100 if num(row.get("three_m")) else 0.1,
        "ast_to": min(5.0, num(row.get("ast_to"), 1.0)),
        "fouls40": num(row.get("fouls_committed_per40"), 4),
    }


SHOOT_KEYS = ("ftm", "fta", "three_m", "three_a", "rim_m", "rim_a", "mid_m", "mid_a")


def shooting(totals: dict[str, float]) -> dict[str, float]:
    return {
        "ft_pct": (totals["ftm"] + FT_PRIOR * FT_PRIOR_N) / (totals["fta"] + FT_PRIOR_N),
        "three_pct": (totals["three_m"] + THREE_PRIOR * THREE_PRIOR_N) / (totals["three_a"] + THREE_PRIOR_N),
        "rim_pct": (totals["rim_m"] + RIM_PRIOR * RIM_PRIOR_N) / (totals["rim_a"] + RIM_PRIOR_N),
        "mid_pct": (totals["mid_m"] + MID_PRIOR * MID_PRIOR_N) / (totals["mid_a"] + MID_PRIOR_N),
        "fta": totals["fta"], "three_a": totals["three_a"],
    }


def career_totals(rows) -> dict[str, float]:
    return {k: sum(num(r.get(k)) for r in rows) for k in SHOOT_KEYS}


# ----------------------------------------------------------------------------------------------- features
FEATURES = ("recruit", "recruit_missing", "recruit_elite", "recruit_fr", "age", "age_sq", "fr", "so", "jr",
            "obpm", "dbpm", "min_pct", "usg", "height", "team", "prev_bpm", "prev_missing", "bpm_gain",
            "blk", "ast", "stl", "three_rate", "ft", "ts")


def make_state(row, rates, shoot, minutes, prev_row, team: float) -> dict:
    """Everything the draft model needs about one player-season, in a form that can be projected a year ahead."""
    rr = row.get("recruit_rating")
    prev = None
    if prev_row is not None and season_minutes(prev_row) > 0:
        prev = (season_rates(prev_row)["gbpm"], season_minutes(prev_row))
    return {"rates": rates, "shoot": shoot, "minutes": minutes, "prev": prev, "season": int(row["season"]),
            "rr": None if rr is None or isinstance(rr, str) else float(rr) / 100, "cls": class_index(row),
            "born": known_birth_date(row), "height": row.get("height_in"), "team": team}


def state_age(state, draft_year: int) -> float:
    if state["born"] is not None:
        return (dt.date(draft_year, *DRAFT_DAY) - state["born"]).days / 365.25
    return TYPICAL_AGE_BY_CLASS[min(3, state["cls"])] + (draft_year - state["season"]) + max(0, state["cls"] - 3)


def eligible(state, draft_year: int) -> bool:
    """NBA age rule: 19 during the calendar year of the draft (unknown birthdays: assume eligible)."""
    return state["born"] is None or state["born"].year <= draft_year - 19


def features(state, draft_year: int) -> list[float]:
    rates, shoot, minutes = state["rates"], state["shoot"], state["minutes"]
    rr, cls = state["rr"], state["cls"]
    age = max(17.5, min(27.0, state_age(state, draft_year)))
    rel = min(1.0, minutes / 600)
    obpm = rates["ogbpm"] * rel + (-2.0) * (1 - rel)
    dbpm = rates["dgbpm"] * rel + (-0.5) * (1 - rel)
    prev = None
    if state["prev"] is not None:
        prel = min(1.0, state["prev"][1] / 600)
        prev = state["prev"][0] * prel + (-2.5) * (1 - prel)
    height = state["height"]
    return [
        rr or 0.0, 0.0 if rr else 1.0, max(0.0, (rr or 0) - 0.9) * 10, (rr or 0) * (cls == 0),
        age - 21, (age - 21) ** 2, float(cls == 0), float(cls == 1), float(cls == 2),
        obpm, dbpm, rates["min_pct"] / 100, rates["usg"] / 100,
        ((height or 78) - 78) / 3, state["team"],
        prev if prev is not None else 0.0, 0.0 if prev is not None else 1.0,
        (obpm + dbpm - prev) if prev is not None else 0.0,
        min(15.0, rates["blk_pct"]) / 5, min(45.0, rates["ast_pct"]) / 10, min(6.0, rates["stl_pct"]),
        rates["three_rate"], shoot["ft_pct"], rates["ts"] / 100,
    ]


def project_state(state, deltas) -> dict:
    """The same player a season later: typical one-year change for his class, a full season of minutes."""
    shift = deltas.get(min(3, state["cls"]), {})
    rates = {k: v + shift.get(k, 0.0) for k, v in state["rates"].items()}
    rates["min_pct"] = max(0.0, min(95.0, rates["min_pct"]))
    shoot = dict(state["shoot"])
    for key in ("ft_pct", "three_pct"):
        shoot[key] += shift.get(key, 0.0)
    return {**state, "rates": rates, "shoot": shoot, "minutes": rates["min_pct"] / 100 * 40 * 31,
            "prev": (state["rates"]["gbpm"], state["minutes"]), "season": state["season"] + 1,
            "cls": state["cls"] + 1}


# ----------------------------------------------------------------------------------------------- history


def load_history():
    rows = []
    for season in range(FIRST_SEASON, CURRENT_SEASON + 1):
        path = RAW / f"players_{season}.csv"
        if path.exists():
            for row in barttorvik.load(season):
                row["season"] = int(num(row.get("season"), season)) or season
                rows.append(row)
    by_player = defaultdict(dict)
    for row in rows:
        if row.get("player_id"):
            prior = by_player[row["player_id"]].get(row["season"])
            if prior is None or season_minutes(row) > season_minutes(prior):
                by_player[row["player_id"]][row["season"]] = row
    return by_player


def team_strength(ctx, season: int, team: str) -> float:
    current = ctx.get((season, team), {}).get("barthag")
    if season == CURRENT_SEASON:
        prior = ctx.get((season - 1, team), {}).get("barthag")
        if current is not None and prior is not None:
            return 0.4 * current + 0.6 * prior
        current = current if current is not None else prior
    return 0.3 if current is None else current


def development_deltas(by_player) -> dict[int, dict[str, float]]:
    """Typical one-year change of each rate for players returning with real minutes, by class."""
    changes = defaultdict(lambda: defaultdict(list))
    for seasons in by_player.values():
        for season, row in seasons.items():
            nxt = seasons.get(season + 1)
            if season + 1 >= CURRENT_SEASON or not nxt:
                continue
            if num(row.get("min_pct")) < 30 or num(nxt.get("min_pct")) < 30:
                continue
            a, b = season_rates(row), season_rates(nxt)
            cls = class_index(row)
            for key in PROFILE_RATES:
                changes[cls][key].append(b[key] - a[key])
            sa, sb = shooting(career_totals([row])), shooting(career_totals([nxt]))
            for key in ("ft_pct", "three_pct"):
                changes[cls][key].append(sb[key] - sa[key])
    return {cls: {key: statistics.median(vals) for key, vals in keys.items()} for cls, keys in changes.items()}


def freshman_priors(by_player) -> dict[str, dict[str, float]]:
    bands = defaultdict(list)
    for seasons in by_player.values():
        for season, row in seasons.items():
            if season >= CURRENT_SEASON or class_index(row) != 0 or num(row.get("min_pct")) < 20:
                continue
            bands[recruit_band(row)].append(season_rates(row))
    return {band: {key: statistics.fmean(r[key] for r in rows) for key in PROFILE_RATES} for band, rows in bands.items()}


def recruit_band(row) -> str:
    rr = row.get("recruit_rating")
    rr = 0 if rr is None or isinstance(rr, str) else rr
    return "98+" if rr >= 98 else "95-98" if rr >= 95 else "90-95" if rr >= 90 else "80-90" if rr >= 80 else "other"


def build_states(by_player, ctx):
    """Every historical player-season with a known draft outcome (draft seasons up to the last completed one)."""
    states = []
    for pid, seasons in by_player.items():
        ordered = sorted(seasons)
        last = ordered[-1]
        pick = next((r["nba_pick"] for r in seasons.values() if r.get("nba_pick")), None)
        for season in ordered:
            row = seasons[season]
            if season >= CURRENT_SEASON:
                continue
            minutes = season_minutes(row)
            if minutes < 40 and not row.get("recruit_rating"):
                continue
            shoot = shooting(career_totals([seasons[s] for s in ordered if s <= season]))
            state = make_state(row, season_rates(row), shoot, minutes, seasons.get(season - 1),
                               team_strength(ctx, season, row["team"]))
            states.append({"pid": pid, "season": season, "state": state, "last": last,
                           "returned": season + 1 in seasons, "pick": pick})
    return states


def horizon_examples(states, h: int):
    out = []
    for item in states:
        draft = item["season"] + h
        if draft > CURRENT_SEASON - 1:
            continue
        drafted = int(bool(item["pick"]) and item["last"] == draft)
        out.append({"pid": item["pid"], "season": item["season"], "draft": draft, "y": drafted,
                    "pick": item["pick"] if drafted else None, "x": features(item["state"], draft),
                    "state": item["state"]})
    return out


def return_rates(states) -> dict[int, float]:
    """Share of undrafted players who play another college season, by class (recent seasons: portal/NIL era)."""
    out = {}
    for cls in range(4):
        rows = [s for s in states if s["state"]["cls"] == cls and 2022 <= s["season"] <= CURRENT_SEASON - 2
                and s["state"]["rates"]["min_pct"] >= 15 and not (s["pick"] and s["last"] == s["season"])]
        out[cls] = round(sum(s["returned"] for s in rows) / max(1, len(rows)), 3)
    out[3] = min(out[3], 0.05)  # the extra COVID year is over: seniors are out of eligibility
    return out


def negative_weight(example) -> float:
    """Keep every drafted example and a fixed share of the rest (weighted back up), to keep the fit quick."""
    if example["y"]:
        return 1.0
    return 1 / NEGATIVE_SHARE if stable_unit(example["pid"], example["season"]) < NEGATIVE_SHARE else 0.0


def fit_horizon(train):
    use = [(e, negative_weight(e)) for e in train]
    use = [(e, w) for e, w in use if w > 0]
    means, sds = standardizer([e["x"] for e, _ in use])
    z = lambda x: [(v - m) / s for v, m, s in zip(x, means, sds)]
    beta = logistic_fit([z(e["x"]) for e, _ in use], [e["y"] for e, _ in use], [w for _, w in use], ridge=2.0)
    drafted = [e for e in train if e["y"]]
    pick_beta = linear_fit([z(e["x"]) for e in drafted], [math.log(e["pick"]) for e in drafted], ridge=3.0)
    resid = [math.log(e["pick"]) - dot(pick_beta, z(e["x"])) for e in drafted]
    return {"means": means, "sds": sds, "draft_beta": beta, "pick_beta": pick_beta,
            "pick_log_sd": statistics.pstdev(resid), "n": len(train), "n_drafted": len(drafted)}


def predict(model, x) -> tuple[float, float]:
    zx = [(v - m) / s for v, m, s in zip(x, model["means"], model["sds"])]
    p = sigmoid(dot(model["draft_beta"], zx))
    expected_pick = math.exp(dot(model["pick_beta"], zx) + model["pick_log_sd"] ** 2 / 2)
    return p, max(1.0, min(75.0, expected_pick))


def chain_predict(model0, state, deltas, returns, horizons=HORIZONS) -> dict[int, tuple[float, float]]:
    """Chance of being drafted in each of the next drafts and the expected pick there.

    Drafted h years ahead = not drafted (or not yet eligible) in each earlier draft, back in college, then drafted
    from the projected season. One model (this season's draft) is applied to the player now and as projected."""
    out = {}
    survive = 1.0
    current = state
    for h in range(max(horizons) + 1):
        draft = state["season"] + h
        if h:
            survive *= returns.get(min(3, current["cls"]), 0.0)
            current = project_state(current, deltas)
        p, pick = predict(model0, features(current, draft))
        if not eligible(current, draft) or current["cls"] > 3:
            p = 0.0
        out[h] = (survive * p, pick)
        survive *= 1 - p
    return {h: out[h] for h in horizons}


def horizon_predict(models, state, returns) -> dict[int, tuple[float, float]]:
    """Chance of being drafted in each of the next drafts (direct model per horizon) and the expected pick there.

    A draft the player is too young for passes its chance on to the next one (he must return to school), and
    the chances are scaled down if they add up to more than one (the horizons are fitted separately)."""
    out, carry = {}, 0.0
    for h in HORIZONS:
        draft = state["season"] + h
        p, pick = predict(models[h], features(state, draft))
        if state["cls"] + h > 3 or not eligible(state, draft):
            carry, p = carry + p, 0.0
        elif carry:
            p, carry = p + carry * returns.get(min(3, state["cls"] + h - 1), 0.0), 0.0
        out[h] = [p, pick]
    total = sum(v[0] for v in out.values())
    if total > 1:
        for v in out.values():
            v[0] /= total
    return {h: (v[0], v[1]) for h, v in out.items()}


def pick_value(pick: float) -> float:
    """Relative worth of a draft slot (smooth, top-heavy; pick 1 = 1.0, pick 10 ~ 0.53, pick 30 ~ 0.24)."""
    return math.exp(-0.07 * (pick - 1)) * 0.75 + 0.25 * (1 - min(pick, 61) / 61)


def draft_score(p: float, expected_pick: float) -> float:
    return p * pick_value(expected_pick)


def slot_tables(by_player) -> dict[int, list[float]]:
    """k-th best college draftee (by actual pick) visible h years before the draft -> his average pick."""
    tables = {}
    for h in HORIZONS:
        per_rank = defaultdict(list)
        for draft in range(2010, CURRENT_SEASON):
            picks = sorted(
                r["nba_pick"] for seasons in by_player.values()
                for r in [seasons.get(draft)] if r and r.get("nba_pick") and max(seasons) == draft
                and (draft - h) in seasons)
            for k, pick in enumerate(picks, start=1):
                per_rank[k].append(pick)
        means = []
        for k in sorted(per_rank):
            if len(per_rank[k]) < 5:
                break
            means.append(round(statistics.fmean(per_rank[k]), 2))
        tables[h] = means
    return tables


def college_counts(by_player) -> dict[int, float]:
    out = {}
    for h in HORIZONS:
        counts = []
        for draft in range(2012, CURRENT_SEASON):
            counts.append(sum(1 for seasons in by_player.values() if max(seasons) == draft and seasons.get(draft)
                              and seasons[draft].get("nba_pick") and (draft - h) in seasons))
        out[h] = round(statistics.fmean(counts), 1)
    return out


def ranking_metrics(scored, draft) -> dict:
    """scored: (example, probability, expected pick, score) for one draft and horizon."""
    ranked = sorted(scored, key=lambda s: -s[3])
    drafted = [s for s in scored if s[0]["y"]]
    actual_top10 = {s[0]["pid"] for s in sorted(drafted, key=lambda s: s[0]["pick"])[:10]}
    model_top10 = {s[0]["pid"] for s in ranked[:10]}
    n_drafted = len(drafted)
    model_topn = {s[0]["pid"] for s in ranked[:n_drafted]}
    first_round = {s[0]["pid"] for s in drafted if s[0]["pick"] <= 30}
    ranks = {s[0]["pid"]: i for i, s in enumerate(ranked, start=1)}
    lottery = [s for s in drafted if s[0]["pick"] <= 14]
    return {
        "draft": draft, "players": len(scored), "drafted": n_drafted,
        "auc": round(auc([s[1] for s in scored], [s[0]["y"] for s in scored]), 4),
        "spearman_rank_vs_pick": round(spearman([ranks[s[0]["pid"]] for s in drafted], [s[0]["pick"] for s in drafted]), 3),
        "top10_overlap": len(actual_top10 & model_top10),
        "top30_drafted": sum(1 for s in ranked[:30] if s[0]["y"]),
        "top30_first_round": sum(1 for s in ranked[:30] if s[0]["pid"] in first_round),
        "topN_drafted_share": round(len(model_topn & {s[0]["pid"] for s in drafted}) / max(1, n_drafted), 3),
        "lottery_picks_in_model_top20": sum(1 for s in lottery if ranks[s[0]["pid"]] <= 20),
        "lottery_picks": len(lottery),
        "expected_count": round(sum(s[1] for s in scored), 1),
    }


SUMMARY_KEYS = ("auc", "spearman_rank_vs_pick", "top10_overlap", "top30_drafted", "top30_first_round",
                "topN_drafted_share", "lottery_picks_in_model_top20", "lottery_picks", "drafted", "expected_count")


def evaluate(states, deltas, returns) -> dict:
    """Fit on drafts <= TRAIN_LAST_DRAFT, score TEST_DRAFTS: direct per-horizon models vs the chained model."""
    out = {}
    train0 = [e for e in horizon_examples(states, 0) if e["draft"] <= TRAIN_LAST_DRAFT]
    model0 = fit_horizon(train0)
    for h in HORIZONS:
        examples = horizon_examples(states, h)
        direct = fit_horizon([e for e in examples if e["draft"] <= TRAIN_LAST_DRAFT])
        test = [e for e in examples if e["draft"] in TEST_DRAFTS]
        results = {}
        for label in ("direct", "chained"):
            per_draft = []
            for draft in TEST_DRAFTS:
                scored = []
                for e in (e for e in test if e["draft"] == draft):
                    if label == "direct":
                        p, pick = predict(direct, e["x"])
                        if not eligible(e["state"], draft):
                            p = 0.0
                    else:
                        p, pick = chain_predict(model0, e["state"], deltas, returns, (h,))[h]
                    scored.append((e, p, pick, draft_score(p, pick)))
                per_draft.append(ranking_metrics(scored, draft))
            results[label] = {"summary": {k: round(statistics.fmean(d[k] for d in per_draft), 3) for k in SUMMARY_KEYS},
                              "per_draft": per_draft}
        out[h] = {"train_examples": direct["n"], "train_drafted": direct["n_drafted"], **results}
    return out


# ----------------------------------------------------------------------------------------------- current players


def current_profile(seasons, priors, deltas) -> tuple[dict, dict, float]:
    """Best estimate of a current player's level: this season's games blended with last season / a prior."""
    row = seasons[CURRENT_SEASON]
    cur = season_rates(row)
    cur_min = season_minutes(row)
    parts = [(cur, cur_min)]
    prev = seasons.get(CURRENT_SEASON - 1)
    if prev and season_minutes(prev) > 0:
        shift = deltas.get(class_index(prev), {})
        moved = {k: v + shift.get(k, 0.0) for k, v in season_rates(prev).items()}
        parts.append((moved, 0.6 * season_minutes(prev)))
    else:
        prior = priors.get(recruit_band(row)) or priors.get("other")
        parts.append((prior, 250.0))
    total = sum(w for _, w in parts) or 1.0
    blended = {k: sum(r[k] * w for r, w in parts) / total for k in PROFILE_RATES}
    shoot = shooting(career_totals(list(seasons.values())))
    # Treat the blend as a projected full season: minutes share x 40 x 31 games.
    minutes = blended["min_pct"] / 100 * 40 * 31
    return blended, shoot, minutes


def universe_exclusions() -> set[str]:
    """Names of players already in the game (the NBA universe, including the drafted 2026 class)."""
    from nba_gm_data.utils import normalize_name
    path = ROOT / "data" / "canonical" / "universe_2026_27_offseason.json"
    universe = json.loads(path.read_text(encoding="utf-8"))
    return {normalize_name(player.get("name")) for player in universe.get("players", [])}


def season_card(row) -> dict:
    games = max(1, int(num(row.get("games"))))
    fga = num(row.get("two_a")) + num(row.get("three_a"))
    fgm = num(row.get("two_m")) + num(row.get("three_m"))
    pct = lambda m, a: round(100 * m / a, 1) if a else None
    return {
        "season": f"{row['season'] - 1}-{str(row['season'])[-2:]}", "team": row.get("team"), "conf": row.get("conf"),
        "class_year": row.get("class_year"), "games": games, "mpg": round(num(row.get("mpg")), 1),
        "ppg": round(num(row.get("pts_pg")), 1), "rpg": round(num(row.get("reb_pg")), 1),
        "apg": round(num(row.get("ast_pg")), 1), "spg": round(num(row.get("stl_pg")), 1),
        "bpg": round(num(row.get("blk_pg")), 1),
        "topg": round(num(row.get("ast_pg")) / num(row.get("ast_to")), 1) if num(row.get("ast_to")) > 0 else None,
        "fga_per_game": round(fga / games, 1), "fg_pct": pct(fgm, fga),
        "fg3m_per_game": round(num(row.get("three_m")) / games, 1), "fg3a_per_game": round(num(row.get("three_a")) / games, 1),
        "fg3_pct": pct(num(row.get("three_m")), num(row.get("three_a"))),
        "fta_per_game": round(num(row.get("fta")) / games, 1), "ft_pct": pct(num(row.get("ftm")), num(row.get("fta"))),
        "usg": round(num(row.get("usg")), 1), "bpm": round(num(row.get("gbpm")), 1),
        "ast_pct": round(num(row.get("ast_pct")), 1), "blk_pct": round(num(row.get("blk_pct")), 1),
        "stl_pct": round(num(row.get("stl_pct")), 1), "ts": round(num(row.get("ts")), 1),
    }


def rounded(values: dict, digits: int = 4) -> dict:
    return {k: round(v, digits) for k, v in values.items()}


# ----------------------------------------------------------------------------------------------- scouting inputs
# Public draft boards (2027) and recruiting ranks (2028-2029), read by hand into data/research/prospect_scouting/.
SCOUTING = ROOT / "data" / "research" / "prospect_scouting"
BOARDS_FILE = SCOUTING / "draft_2027_boards.json"
RECRUITS_FILE = SCOUTING / "recruits_2028_2029.json"
DRAFT_YEARS = tuple(CURRENT_SEASON + h for h in HORIZONS)
SCOUT_AS_OF = dt.date(2026, 11, 19)  # when the boards were read
BOARD_AGE_DATE = dt.date(2026, 11, 5)  # board ages are "as of publication" (mostly ESPN, 5 November)
BOARD_HALF_LIFE_DAYS = 90.0  # a board loses half its weight every 90 days (SI's June list ~0.3, B/R's August ~0.5)
MOCK_WEIGHT = 0.75  # mocks mix in team fit and need, so they count a little less than big boards
UNDATED_WEIGHT = 0.8  # Tankathon's live board carries no date
# 2027: weight of the college model against the scouts = games / (games + 20). With 3-6 games played the scouts carry
# about 85%; by mid-season (20 games) it is even; the model's same-spring accuracy (rank vs pick 0.62) is measured
# on full seasons, and the boards already fold in high-school, summer and last-season evaluation.
MODEL_GAMES_HALF = 20.0
UNLISTED_RANK = 150  # a college player on no board sits past the deepest boards (ESPN and B/R list 100)
INJURY_SEASON_OUT_FACTOR = 0.5  # announced season-ending injury: half the chance of going this spring (judgement)
POOL_MIN_CHANCE = 0.03  # unlisted college players join the pool with at least a 3% chance in one of the drafts
# International youth-tournament standouts with no board rank: no local history to fit, so a stated judgement prior
# (chance in the first draft he is eligible for, in the next one, expected pick if drafted). Tier A: all-tournament
# teams / award winners; tier B: the rest of the scouting notes.
INTL_UNRANKED = {"A": (0.25, 0.10, 40.0), "B": (0.10, 0.05, 50.0)}
NAME_ALIASES = {"jojo tugler": "joseph tugler", "rueben prey": "ruben prey"}
TEAM_ALIASES = {"uconn": "connecticut", "miami (fl)": "miami fl", "nc state": "n.c. state", "ole miss": "mississippi"}
RANK_BANDS = (5, 10, 20, 30, 45, 60, 80, 100, 150, 250)
RETURN_BANDS = (10, 30, 60, 100, 250)
RECRUIT_BANDS = ((1, 5), (6, 10), (11, 20), (21, 30), (31, 50), (51, 100))
RECRUIT_COHORTS = range(2008, 2023)  # freshmen whose first four college years are all observed (drafts to 2026)
SUFFIXES = {"jr", "sr", "ii", "iii", "iv", "v"}
MONTHS = {m: i for i, m in enumerate(("jan", "feb", "mar", "apr", "may", "jun", "jul", "aug", "sep", "oct", "nov", "dec"), 1)}


def name_key(name) -> str:
    """Name for matching across sources: no accents, punctuation or Jr./II/III, plus a small alias map."""
    text = unicodedata.normalize("NFKD", str(name or "")).encode("ascii", "ignore").decode().lower()
    text = re.sub(r"[.'`]", "", text)
    text = re.sub(r"[-_,]", " ", text)
    key = " ".join(part for part in text.split() if part not in SUFFIXES)
    return NAME_ALIASES.get(key, key)


def team_key(team) -> str:
    text = str(team or "").lower().strip()
    text = TEAM_ALIASES.get(text, text)
    return re.sub(r"\bstate\b", "st.", text)


def source_weight(source) -> float:
    weight = MOCK_WEIGHT if source.get("kind") == "mock_draft" else 1.0
    if source.get("published"):
        age = (SCOUT_AS_OF - dt.date.fromisoformat(source["published"])).days
        return weight * 0.5 ** (max(0, age) / BOARD_HALF_LIFE_DAYS)
    return weight * UNDATED_WEIGHT


def imputed_rank(source) -> float:
    """A player missing from a list of length L sits somewhere past its end."""
    length = float(source.get("ranked_count") or 30)
    return length + max(5.0, 0.3 * length)


def consensus_board(boards) -> tuple[list[dict], dict[str, float]]:
    """Weighted geometric mean of each player's ranks across the boards (missing ranks imputed past the list)."""
    sources = {s["id"]: s for s in boards["sources"]}
    weights = {sid: round(source_weight(s), 4) for sid, s in sources.items()}
    total = sum(weights.values())
    rows = []
    for player in boards["players"]:
        ranks = {sid: int(r) for sid, r in (player.get("ranks") or {}).items() if sid in sources and r}
        if not ranks:
            continue
        log_rank = sum(w * math.log(ranks.get(sid) or imputed_rank(sources[sid])) for sid, w in weights.items()) / total
        rows.append({**player, "consensus_score": round(math.exp(log_rank), 3), "source_ranks": ranks})
    rows.sort(key=lambda r: (r["consensus_score"], r["name"]))
    for k, row in enumerate(rows, start=1):
        row["consensus_rank"] = k
    return rows, weights


def birth_from_note(note, as_of: dt.date = BOARD_AGE_DATE) -> dt.date | None:
    """Birth date from a scouting age note: 'Born June 11 2010', 'Born Jan 2009', 'Born 2008', 'born 2008-09-30',
    or a decimal age as of the board ('19.1 (ESPN, Nov 5)', '18-19')."""
    text = str(note or "").lower()
    if m := re.search(r"born (\d{4})-(\d{2})-(\d{2})", text):
        return dt.date(int(m[1]), int(m[2]), int(m[3]))
    if m := re.search(r"born ([a-z]{3})[a-z]* (\d{1,2}),? (\d{4})", text):
        if m[1] in MONTHS:
            return dt.date(int(m[3]), MONTHS[m[1]], int(m[2]))
    if m := re.search(r"born ([a-z]{3})[a-z]* (\d{4})", text):
        if m[1] in MONTHS:
            return dt.date(int(m[2]), MONTHS[m[1]], 15)
    if m := re.search(r"born (\d{4})", text):
        return dt.date(int(m[1]), 7, 1)
    if m := re.match(r"\s*(\d{2})-(\d{2})\b", text):
        age = (int(m[1]) + int(m[2])) / 2 + 0.5
    elif m := re.match(r"\s*(\d{2}(?:\.\d+)?)", text):
        age = float(m[1]) + (0.5 if "." not in m[1] else 0.0)
    else:
        return None
    return as_of - dt.timedelta(days=round(age * 365.25))


def age_on_draft_day(born: dt.date, year: int) -> float:
    return round((dt.date(year, *DRAFT_DAY) - born).days / 365.25, 2)


def height_from_text(text) -> float | None:
    m = re.search(r"(\d)-(\d{1,2}(?:\.\d+)?)", str(text or ""))
    return round(12 * int(m[1]) + float(m[2]), 1) if m else None


def position_from_text(text, height: float | None) -> str | None:
    """Scouting position strings in the generator's vocabulary ('CG' combo guard, 'F' forward, 'G' guard)."""
    tokens = [t.strip().upper() for t in re.split(r"[/,]", str(text or "")) if t.strip()]
    out = []
    for token in tokens:
        if token in {"PG", "SG", "SF", "PF", "C"}:
            out.append(token)
        elif token == "CG":
            out += ["SG", "PG"]
        elif token == "G":
            out += ["PG", "SG"]
        elif token == "F":
            out += ["PF", "SF"] if (height or 80) >= 81 else ["SF", "PF"]
    out = list(dict.fromkeys(out))[:2]
    return "/".join(out) or None


# ----------------------------------------------------------------------------------------------- scouting tags
# A strength tag is about +1 standard deviation on the skill(s) it names, a concern about -1 (game: real_prospects.
# TAG_WEIGHT_*). Rules are read in this order and a tag counts for at most two skills (split 1/sqrt(n)).
TAG_MAX_SD = 1.5
RECRUIT_SCOUT_SHARE = 0.5
TAG_SKIP = ("very young", "injur", "acl", "surgery", "not stated", "none noted", "thin scouting", "winning",
            "multi-lineup", "uncertain pro role", "unclear star", "likely role player", "few clear holes",
            "no single standout", "other areas", "may not play", "limited minutes", "versatil", "multi-position play",
            "limited ceiling")
TAG_RULES = (
    ("rim_protection", ("rim protect", "shot block", "blocking", "defensive center", "rim deterr")),
    ("rebounding", ("rebound", "glass")),
    ("rim_pressure", ("rim attack", "rim pressure", "downhill", "slashing", "driv", "finish", "transition", "attack",
                      "lob", "above-the-rim", "dunk", "contact", "cutting", "paint", "interior", "post ",
                      "back-to-basket", "inside", "open-court", "at the rim")),
    ("shooting", ("shoot", "three", "3-point", "range", "free throw", "free-throw", "jump shot", "jumper", "release",
                  "stroke", "spacing", "floor-stretch", "stretch", "shooter", "touch", "mechanics", "face-up")),
    ("shot_creation", ("creat", "shot-making", "shotmaking", "pull-up", "off the dribble", "off-dribble", "handle",
                       "ball handling", "ball-handling", "ball skills", "scoring", "scorer", "stepback", "go-to",
                       "elusive", "shifty", "microwave", "shoot-dribble-pass", "overdribbl", "ball-screen")),
    ("passing", ("pass", "playmak", "vision", "distribution", "floor general", "hub", "connective", "unselfish",
                 "point guard", "half-court organization")),
    ("defense", ("defens", "defend", "steal", "switch", "guarding", "ball-pressure", "lateral", "foot speed",
                 "screen navigation", "two-way", "3-and-d", "disrupt", "foul")),
    ("feel", ("feel", "iq", "cerebral", "decision", "processing", "turnover", "ball security", "shot selection",
              "maturity", "coachab")),
    ("athleticism", ("athlet", "explos", "bouncy", "burst", "quick", "speed", "runs and jumps", "mobility", "fluid",
                     "power", "pace", "heavy feet", "tools")),
    ("size", ("size", "length", "wingspan", "frame", "long", "height", "undersized", "small", "thin", "slight",
              "strength", "physical", "7-", "weight", "measurables")),
    ("motor", ("motor", "energy", "competitive", "tough", "effort", "dirty-work", "tenacious", "activ", "passivity",
               "conditioning")),
    ("nba_readiness", ("nba-ready", "ready", "productive", "production", "efficient", "efficiency", "polish", "raw",
                       "project", "unproven", "adjust", "late to the sport", "developing", "consistency")),
)


def tag_skills(tag: str) -> list[str]:
    text = str(tag or "").lower().replace("long-range", "deep range")
    if text.strip() == "age" or any(skip in text for skip in TAG_SKIP):
        return []
    hits = [skill for skill, keys in TAG_RULES if any(key in text for key in keys)]
    return hits[:2]


def tag_scores(strengths, weaknesses) -> dict[str, float]:
    out: dict[str, float] = defaultdict(float)
    for sign, tags in ((1.0, strengths), (-1.0, weaknesses)):
        for tag in tags or []:
            hits = tag_skills(tag)
            for skill in hits:
                out[skill] += sign / math.sqrt(len(hits))
    # Several outlets often say the same thing: the total per skill is eased to at most about 1.5 standard deviations.
    return {k: round(TAG_MAX_SD * math.tanh(v / TAG_MAX_SD), 3) for k, v in sorted(out.items()) if v}


# ----------------------------------------------------------------------------------------------- timing evidence


def curve_value(points: list[list[float]], rank: float) -> float:
    """Piecewise-linear read of a [[rank, value], ...] curve (flat beyond its ends)."""
    if rank <= points[0][0]:
        return points[0][1]
    for (r0, v0), (r1, v1) in zip(points, points[1:]):
        if r0 <= rank <= r1:
            return v0 + (v1 - v0) * (rank - r0) / (r1 - r0)
    return points[-1][1]


def band_centers(bands) -> list[float]:
    lows = (0, *bands[:-1])
    return [(lo + 1 + hi) / 2 for lo, hi in zip(lows, bands)]


def scout_curves(states, models) -> dict:
    """What a preseason rank has meant, from history (drafts 2010-2026, college players ranked by the same-spring
    model's draft value): the chance the k-th ranked player is drafted that June (hit), and for a ranked player who
    is not drafted that June but has eligibility left, the chance he is drafted the next June and, if not, the one
    after (back). Scouts rank better than the model, so these read as a floor for a board rank."""
    outcome = {item["pid"]: (item["pick"], item["last"]) for item in states}
    per_draft = defaultdict(list)
    for e in horizon_examples(states, 0):
        if e["draft"] < 2010:
            continue
        p, pick = predict(models[0], e["x"])
        if not eligible(e["state"], e["draft"]):
            p = 0.0
        per_draft[e["draft"]].append((draft_score(p, pick), e))
    hit = defaultdict(lambda: [0, 0])
    back = defaultdict(lambda: [0, 0, 0, 0])
    for draft, scored in per_draft.items():
        scored.sort(key=lambda s: (-s[0], s[1]["pid"]))
        for rank, (_, e) in enumerate(scored[:RANK_BANDS[-1]], start=1):
            band = next(b for b in RANK_BANDS if rank <= b)
            hit[band][0] += e["y"]
            hit[band][1] += 1
            cls = e["state"]["cls"]
            if e["y"] or cls >= 3 or draft + 1 > CURRENT_SEASON - 1:
                continue
            pick, last = outcome[e["pid"]]
            rb = next(b for b in RETURN_BANDS if rank <= b)
            drafted_next = bool(pick) and last == draft + 1
            back[rb][0] += drafted_next
            back[rb][1] += 1
            if not drafted_next and cls <= 1 and draft + 2 <= CURRENT_SEASON - 1:
                back[rb][2] += bool(pick) and last == draft + 2
                back[rb][3] += 1
    rates, low = [], 1.0
    for center, band in zip(band_centers(RANK_BANDS), RANK_BANDS):
        low = min(low, hit[band][0] / max(1, hit[band][1]))  # a better rank never has a lower chance
        rates.append([center, round(low, 3)])
    back_rows = []
    for center, band in zip(band_centers(RETURN_BANDS), RETURN_BANDS):
        a, n1, b, n2 = back[band]
        back_rows.append([center, round(a / max(1, n1), 3), round(b / max(1, n2), 3), n1, n2])
    return {"hit_by_rank": rates, "back_by_rank": back_rows,
            "hit_counts": {str(b): hit[b] for b in RANK_BANDS}}


def freshman_ranks(by_player) -> dict[int, list[tuple[float, str]]]:
    """Each season's freshmen with a recruiting rating, best first (rank k ~ the k-th recruit of his class)."""
    out = defaultdict(list)
    for pid, seasons in by_player.items():
        for season, row in seasons.items():
            rr = row.get("recruit_rating")
            if class_index(row) == 0 and isinstance(rr, float) and rr > 0:
                out[season].append((rr, pid))
    for rows in out.values():
        rows.sort(key=lambda r: (-r[0], r[1]))
    return out


def recruit_timing(by_player, fresh) -> dict:
    """By recruiting rank within his class: chance of being drafted after 1, 2, 3 or 4 college years (freshmen
    2008-2022, whose four years are all observed) and the typical pick each time (all observed cohorts; geometric
    mean shrunk toward the band's overall mean with 3 pseudo-picks)."""
    rows = []
    for lo, hi in RECRUIT_BANDS:
        share, n = Counter(), 0
        picks = defaultdict(list)
        for season, ranked in fresh.items():
            if season >= CURRENT_SEASON:
                continue
            for k, (_, pid) in enumerate(ranked[:hi], start=1):
                if k < lo:
                    continue
                seasons = by_player[pid]
                pick = next((r["nba_pick"] for r in seasons.values() if r.get("nba_pick")), None)
                years = max(seasons) - season + 1
                if season in RECRUIT_COHORTS:
                    n += 1
                    if pick and years <= 4:
                        share[years] += 1
                if pick and season + years - 1 <= CURRENT_SEASON - 1 and years <= 4:
                    picks[years].append(pick)
        all_logs = [math.log(p) for v in picks.values() for p in v]
        prior = statistics.fmean(all_logs) if all_logs else math.log(30)
        typical = {str(y): round(math.exp((sum(math.log(p) for p in picks.get(y, [])) + 3 * prior)
                                          / (len(picks.get(y, [])) + 3)), 1) for y in (1, 2, 3, 4)}
        rows.append({"ranks": [lo, hi], "players": n,
                     "drafted_after_years": {str(y): round(share[y] / max(1, n), 3) for y in (1, 2, 3, 4)},
                     "not_drafted_within_4": round(1 - sum(share.values()) / max(1, n), 3),
                     "typical_pick": typical,
                     "median_pick": {str(y): statistics.median(picks[y]) for y in (1, 2, 3, 4) if picks.get(y)},
                     "picks_seen": {str(y): len(picks.get(y, [])) for y in (1, 2, 3, 4)}})
    rating_by_rank = []
    for k in range(1, 101):
        values = [ranked[k - 1][0] for season, ranked in fresh.items() if 2015 <= season < CURRENT_SEASON and len(ranked) >= k]
        rating_by_rank.append(round(statistics.median(values), 2))
    return {"bands": rows, "rating_by_rank": rating_by_rank, "cohorts": [RECRUIT_COHORTS[0], RECRUIT_COHORTS[-1]]}


def recruit_band_row(timing, rank: int) -> dict:
    for row in timing["bands"]:
        if row["ranks"][0] <= rank <= row["ranks"][1]:
            return row
    return timing["bands"][-1]


def visible_slot_tables(by_player, fresh) -> dict[int, list[float]]:
    """Order statistics for the later drafts: the k-th best draftee among players visible h years before the draft
    (college players then, plus that many top recruits of the high-school classes still to arrive: top 50 of the
    class entering the next season, top 40 of the one after), averaged over drafts 2012-2026 -> his pick."""
    rank_of = {}
    for season, ranked in fresh.items():
        for k, (_, pid) in enumerate(ranked, start=1):
            rank_of[pid] = (season, k)
    drafted = [(pid, max(seasons), seasons[max(seasons)]["nba_pick"]) for pid, seasons in by_player.items()
               if seasons[max(seasons)].get("nba_pick")]
    tables = {}
    for h in (1, 2):
        per_rank = defaultdict(list)
        for draft in range(2012, CURRENT_SEASON):
            picks = []
            for pid, last, pick in drafted:
                if last != draft:
                    continue
                visible = (draft - h) in by_player[pid]
                if not visible and pid in rank_of:
                    season, k = rank_of[pid]
                    visible = (season == draft - h + 1 and k <= 50) or (h == 2 and season == draft and k <= 40)
                if visible:
                    picks.append(pick)
            for k, pick in enumerate(sorted(picks), start=1):
                per_rank[k].append(pick)
        means = []
        for k in sorted(per_rank):
            if len(per_rank[k]) < 5:
                break
            means.append(round(statistics.fmean(per_rank[k]), 2))
        tables[h] = means
    return tables


def position_priors(by_player, norms) -> dict[str, dict[str, float]]:
    """Typical broad-skill scores of drafted college players by primary position (for prospects without college
    numbers: a centre starts from the typical drafted centre's rim protection, a point guard from his passing)."""
    from nba_gm_data import real_prospects as rp
    groups = defaultdict(list)
    for seasons in by_player.values():
        last = max(seasons)
        row = seasons[last]
        if not row.get("nba_pick") or last >= CURRENT_SEASON:
            continue
        x = pair_features(season_rates(row), shooting(career_totals(list(seasons.values()))), row.get("height_in"))
        position = rp.position_for({"role": row.get("role"), "height_inches": row.get("height_in")})
        groups[position.split("/")[0]].append(skill_scores(x, norms))
    return {pos: {k: round(statistics.fmean(r[k] for r in rows), 3) for k in SKILL_COMPOSITES} for pos, rows in groups.items()}


# ----------------------------------------------------------------------------------------------- the pool


def last_season_state(seasons, deltas, ctx):
    """A player with no games yet this season (injured, or not yet in the current table): last season moved
    forward one class, as a projected full season."""
    row = seasons[max(seasons)]
    shift = deltas.get(class_index(row), {})
    rates = {k: v + shift.get(k, 0.0) for k, v in season_rates(row).items()}
    rates["min_pct"] = max(0.0, min(95.0, rates["min_pct"]))
    shoot = shooting(career_totals(list(seasons.values())))
    state = make_state(row, rates, shoot, rates["min_pct"] / 100 * 40 * 31, row, team_strength(ctx, CURRENT_SEASON - 1, row["team"]))
    state.update({"season": CURRENT_SEASON, "cls": class_index(row) + 1,
                  "prev": (season_rates(row)["gbpm"], season_minutes(row))})
    return state


def timing_from_scouts_and_model(rank, p_model, e_model, weight, curves, cls_now, *, injured=False, young_2027=False):
    """Chance of being drafted in 2027, 2028 and 2029, and the expected pick each year.

    2027: scouts' chance for his board rank (history: hit by rank) blended with the model's by `weight`; a player
    on no board gets at most the chance past the boards' depth. Later years: once he has not gone in 2027, the
    model's own split of what is left (or the history of returning ranked players for a board rank), blended the
    same way. Expected pick: log-blend of the board rank and the model's expected pick."""
    listed = rank is not None
    scout_rank = rank if listed else UNLISTED_RANK
    hit = curve_value(curves["hit_by_rank"], scout_rank)
    back = [[r[0], r[1]] for r in curves["back_by_rank"]], [[r[0], r[2]] for r in curves["back_by_rank"]]
    if p_model is None:
        p_model, e_model, weight = [0.0, 0.0, 0.0], [scout_rank] * 3, 0.0
    scout0 = hit if listed else min(p_model[0], hit)
    p0 = 0.0 if young_2027 else weight * p_model[0] + (1 - weight) * scout0
    if injured:
        p0 *= INJURY_SEASON_OUT_FACTOR
    left = 1.0 - p_model[0]
    q_model = [min(1.0, p_model[1] / left) if left > 1e-6 else 0.0,
               min(1.0, p_model[2] / (left - p_model[1])) if left - p_model[1] > 1e-6 else 0.0]
    q = []
    for h in (1, 2):
        if listed:
            # A returner who keeps his board rank faces the same choice next spring: at least this year's chance.
            scout_q = 0.0 if cls_now + h > 3 else max(hit, curve_value(back[h - 1], scout_rank))
            if young_2027 and h == 1:
                scout_q = hit  # too young for 2027: his first draft is 2028
            q.append(weight * q_model[h - 1] + (1 - weight) * scout_q)
        else:
            q.append(q_model[h - 1])
    chances = [p0, (1 - p0) * q[0], (1 - p0) * (1 - q[0]) * q[1]]
    if listed:
        picks = [math.exp(weight * math.log(max(1.0, e)) + (1 - weight) * math.log(rank)) for e in e_model]
    else:
        picks = [math.exp(weight * math.log(max(1.0, e_model[0])) + (1 - weight) * math.log(UNLISTED_RANK)), *e_model[1:]]
    return [round(c, 4) for c in chances], [round(p, 1) for p in picks]


def scouting_record(board=None, recruit=None, college_team=None) -> dict:
    """What the card shows about the scouts' view (ranks, sources, tags, where he plays)."""
    out = {"strengths": [], "weaknesses": []}
    for source in (recruit, board):  # board last: its ranks, team and tags lead
        if not source:
            continue
        out["strengths"] = list(dict.fromkeys([*out["strengths"], *(source.get("strengths") or [])]))
        out["weaknesses"] = list(dict.fromkeys([*out["weaknesses"], *(source.get("weaknesses") or [])]))
        out["country"] = source.get("country") or out.get("country")
        out["league"] = source.get("league")
    if recruit:
        out["team"] = recruit.get("current_team")
        out["committed_to"] = recruit.get("committed_to")
        out["hs_class"] = recruit.get("hs_class")
        out["recruit_ranks"] = dict(recruit.get("ranks") or {})
    if board:
        out["team"] = board.get("team")
        out["consensus_rank"] = board["consensus_rank"]
        out["consensus_score"] = board["consensus_score"]
        out["board_count"] = len(board["source_ranks"])
        out["source_ranks"] = board["source_ranks"]
    if college_team:
        out["team"] = college_team
    for key in ("strengths", "weaknesses"):
        out[key] = [t for t in out[key] if str(t).lower() not in {"not stated", "not stated in sources", "none noted"}]
    return {k: v for k, v in out.items() if v not in (None, [], {})}


def build_pool(by_player, ctx, models, priors, deltas, returns, coaches, curves, timing, norms, pos_priors):
    """Every real player who could be drafted in 2027-2029, with his chance per year and what he looks like then."""
    from nba_gm_data import real_prospects as rp
    from nba_gm_data.utils import normalize_name
    excluded = universe_exclusions()
    boards = json.loads(BOARDS_FILE.read_text(encoding="utf-8"))
    recruits = json.loads(RECRUITS_FILE.read_text(encoding="utf-8"))
    board_rows, board_weights = consensus_board(boards)

    current_by_key, last_by_key = defaultdict(list), defaultdict(list)
    for pid, seasons in by_player.items():
        if CURRENT_SEASON in seasons:
            current_by_key[name_key(seasons[CURRENT_SEASON]["name"])].append(pid)
        elif CURRENT_SEASON - 1 in seasons:
            last_by_key[name_key(seasons[CURRENT_SEASON - 1]["name"])].append(pid)

    def match(name, team):
        key = name_key(name)
        for table in (current_by_key, last_by_key):
            pids = table.get(key) or []
            if len(pids) > 1 and team:
                pids = [pid for pid in pids if team_key(by_player[pid][max(by_player[pid])]["team"]) == team_key(team)] or pids
            if len(pids) == 1:
                return pids[0]
        return None

    linked = defaultdict(dict)  # college pid -> {"board": row, "recruit": row}
    others = {}  # name key -> {"board": row, "recruit": row} for players without college data
    for row in board_rows:
        pid = match(row["name"], row.get("team")) if row.get("league") == "NCAA" else None
        if pid:
            linked[pid]["board"] = row
        else:
            others.setdefault(name_key(row["name"]), {})["board"] = row
    for row in recruits["players"]:
        pid = match(row["name"], None) if row.get("league", "").startswith(("College", "International (NCAA")) else None
        if pid:
            linked[pid]["recruit"] = row
        elif row.get("league") == "HS" or name_key(row["name"]) in others or row.get("league", "").startswith("International"):
            others.setdefault(name_key(row["name"]), {})["recruit"] = row

    pool, report = [], {"matched_board": 0, "board_without_college_data": [], "recruit_college_links": []}
    for pid, seasons in by_player.items():
        link = linked.get(pid, {})
        row = seasons.get(CURRENT_SEASON)
        if row is None and not link:
            continue
        if row is not None and (row.get("nba_pick") or num(row.get("games")) < 1):
            if not link:
                continue
        name = (row or seasons[max(seasons)])["name"]
        if normalize_name(name) in excluded:
            continue
        if row is not None and num(row.get("games")) >= 1:
            rates, shoot, minutes = current_profile(seasons, priors, deltas)
            state = make_state(row, rates, shoot, minutes, seasons.get(CURRENT_SEASON - 1),
                               team_strength(ctx, CURRENT_SEASON, row["team"]))
            games = int(num(row.get("games")))
        else:
            state = last_season_state(seasons, deltas, ctx)
            row, games = seasons[max(seasons)], 0
        board, recruit = link.get("board"), link.get("recruit")
        if state["born"] is None:  # Barttorvik's placeholder birthday: use the scouts' age when they give one
            note_born = birth_from_note((board or {}).get("age_note")) or birth_from_note((recruit or {}).get("age_note"))
            if note_born is None and recruit and recruit.get("projected_draft_year"):
                note_born = dt.date(int(recruit["projected_draft_year"]) - 19, 7, 1)
            if note_born is not None:
                state["born"] = note_born
        per_h = horizon_predict(models, state, returns)
        p_model = [per_h[h][0] for h in HORIZONS]
        e_model = [per_h[h][1] for h in HORIZONS]
        weight = games / (games + MODEL_GAMES_HALF)
        injured = any("expected to miss 2026-27" in str(t).lower() for t in (board or {}).get("weaknesses", []))
        chances, picks = timing_from_scouts_and_model((board or {}).get("consensus_rank"), p_model, e_model, weight,
                                                       curves, state["cls"], injured=injured,
                                                       young_2027=not eligible(state, CURRENT_SEASON))
        if not link and max(chances) < POOL_MIN_CHANCE:
            continue
        if board:
            report["matched_board"] += 1
        if recruit:
            report["recruit_college_links"].append(name)
        views = {}
        projected = state
        for h, year in enumerate(DRAFT_YEARS):
            if h:
                projected = project_state(projected, deltas)
            if chances[h] < 0.001:
                continue
            views[str(year)] = {
                "expected_pick": picks[h], "age_at_draft": round(state_age(state, year), 2),
                "class_year_at_draft": ["Fr", "So", "Jr", "Sr"][min(3, state["cls"] + h)],
                "effective_minutes": round(projected["minutes"], 0),
                "projected_profile": {**rounded(projected["rates"]),
                                      **rounded({k: projected["shoot"][k] for k in ("ft_pct", "three_pct", "rim_pct", "mid_pct")}),
                                      "fta": projected["shoot"]["fta"], "three_a": projected["shoot"]["three_a"]},
            }
        if not views:
            continue
        born = state["born"]
        scouting = scouting_record(board, recruit, row.get("team")) if (board or recruit) else {}
        pool.append({
            "id": f"college_{pid}", "kind": "college",
            "barttorvik_id": pid, "name": board["name"] if board else name,
            "college_team": row.get("team"), "conference": row.get("conf"),
            "coach": coaches.get((CURRENT_SEASON, row.get("team"))), "class_year_now": ["Fr", "So", "Jr", "Sr"][min(3, state["cls"])],
            "birth_date": born.isoformat() if born else None, "age_estimated": known_birth_date(row) is None,
            "height_inches": row.get("height_in"), "role": row.get("role") or None,
            "recruit_rating": row.get("recruit_rating"), "hometown": row.get("hometown") or None,
            "games_this_season": games, "model_weight": round(weight, 3),
            "scout_share": round(1 - weight, 3) if board else 0.0,
            "seasons": [season_card(seasons[s]) for s in sorted(seasons, reverse=True)[:4]],
            "scouting": scouting, "tag_scores": tag_scores(scouting.get("strengths"), scouting.get("weaknesses")),
            "chance_by_year": {str(y): c for y, c in zip(DRAFT_YEARS, chances) if str(y) in views},
            "model": {"chance_by_year": {str(y): round(p, 4) for y, p in zip(DRAFT_YEARS, p_model)},
                      "expected_pick_by_year": {str(y): round(e, 1) for y, e in zip(DRAFT_YEARS, e_model)}},
            "years": views,
        })

    rating_by_rank = timing["rating_by_rank"]
    for key, link in sorted(others.items()):
        board, recruit = link.get("board"), link.get("recruit")
        source = board or recruit
        league = str(source.get("league") or "")
        if league == "HS":
            kind = "high_school"
        elif league.startswith("International"):
            kind = "international"
        else:
            kind = "college_no_stats"
            report["board_without_college_data"].append(source["name"])
        height = height_from_text((board or {}).get("height")) or height_from_text((recruit or {}).get("height"))
        position = (position_from_text((board or {}).get("position"), height)
                    or position_from_text((recruit or {}).get("position"), height) or ("SF" if kind != "high_school" else "SG"))
        born = birth_from_note((board or {}).get("age_note")) or birth_from_note((recruit or {}).get("age_note"))
        hs_class = (recruit or {}).get("hs_class") if kind == "high_school" else None
        first_year = int((recruit or {}).get("projected_draft_year") or CURRENT_SEASON) if not board else CURRENT_SEASON
        if hs_class:
            first_year = int(hs_class) + 1  # one year out of high school
        if born is None:
            born = dt.date(first_year - 19, 4, 1) if kind == "high_school" else dt.date(first_year - 19, 7, 1)
        while born.year > first_year - 19:  # the age rule: 19 during the draft's calendar year
            first_year += 1
        recruit_rating, chances, picks = None, [0.0, 0.0, 0.0], [60.0, 60.0, 60.0]
        if board:
            chances, picks = timing_from_scouts_and_model(
                board["consensus_rank"], None, None, 0.0, curves, 0,
                injured=any("expected to miss 2026-27" in str(t).lower() for t in board.get("weaknesses", [])),
                young_2027=first_year > CURRENT_SEASON)
        elif kind == "high_school":
            k = int((recruit.get("ranks") or {}).get(f"247_composite_{hs_class}") or min((recruit.get("ranks") or {"x": 75}).values()))
            band = recruit_band_row(timing, k)
            recruit_rating = rating_by_rank[min(len(rating_by_rank), k) - 1]
            for n in (1, 2, 3):
                year = first_year + n - 1
                if year in DRAFT_YEARS:
                    chances[DRAFT_YEARS.index(year)] = band["drafted_after_years"][str(n)]
                    # within a band the better-ranked recruit goes first (0.05 of a pick per rank place)
                    picks[DRAFT_YEARS.index(year)] = round(band["typical_pick"][str(n)] + 0.05 * k, 2)
        else:  # international without a board rank
            notes = " ".join(str(recruit.get(k) or "") for k in ("notes", "age_note")).lower()
            tier = "B" if "lower tier" in notes else "A"
            first, second, pick = INTL_UNRANKED[tier]
            for n, chance in ((0, first), (1, second)):
                year = first_year + n
                if year in DRAFT_YEARS:
                    chances[DRAFT_YEARS.index(year)] = chance
                    picks[DRAFT_YEARS.index(year)] = pick
        views = {}
        for h, year in enumerate(DRAFT_YEARS):
            if chances[h] < 0.001 or year < first_year:
                continue
            views[str(year)] = {
                "expected_pick": picks[h], "age_at_draft": age_on_draft_day(born, year),
                "class_year_at_draft": ["Fr", "So", "Jr", "Sr"][min(3, year - first_year)] if kind == "high_school" else None,
            }
        if not views:
            continue
        scouting = scouting_record(board, recruit)
        base = dict(pos_priors.get(position.split("/")[0]) or pos_priors.get("SF"))
        if height:
            base["size"] = size_score(height, norms)
        pool.append({
            "id": f"{kind}_{re.sub(r'[^a-z0-9]+', '_', key).strip('_')}", "kind": kind, "name": source["name"],
            "position": position, "height_inches": height, "weight_lbs": (recruit or {}).get("weight_lbs"),
            "birth_date": born.isoformat(), "age_estimated": True,
            "recruit_rating": recruit_rating, "recruit_rating_estimated": recruit_rating is not None,
            # A draft board rank fixes his place; a recruiting rank (or a tournament note) is a looser signal
            # (top-5 recruits went anywhere from pick 1 to 30), so half of his level keeps the usual spread.
            "scout_share": 1.0 if board else RECRUIT_SCOUT_SHARE,
            "scouting": scouting, "skill_base": base,
            "tag_scores": tag_scores(scouting.get("strengths"), scouting.get("weaknesses")),
            "chance_by_year": {y: chances[DRAFT_YEARS.index(int(y))] for y in views},
            "years": views,
        })
    pool.sort(key=lambda e: (min(v["expected_pick"] for v in e["years"].values()), e["id"]))
    report["sources"] = board_weights
    report["expected_drafted_by_year"] = {str(y): round(sum(e["chance_by_year"].get(str(y), 0.0) for e in pool), 1) for y in DRAFT_YEARS}
    report["pool_by_kind"] = dict(Counter(e["kind"] for e in pool))
    return pool, report


# ----------------------------------------------------------------------------------------------- college -> pro skills
# Which college rates speak to which of the 94 inputs. Each target is fitted as
#   input = a + sum(b * college feature) + c * years in league + d * log(draft pick)
# on players drafted 2019-2025 (final college season; career shooting), then used at entry (0 years).
INPUT_TARGETS = {
    "S07": ("ft_pct",),
    "S01": ("three_pct", "three_rate", "ft_pct"),
    "S02": ("three_pct", "unast_three", "three_per40", "ft_pct"),
    "S03": ("three_pct", "three_per40", "ft_pct"),
    "S08": ("ft_pct", "three_pct", "three_per40"),
    "S09": ("three_rate", "three_pct"),
    "S04": ("mid_pct", "ft_pct"),
    "S05": ("mid_pct", "unast_per40", "ft_pct"),
    "S10": ("rim_pct", "rim_per40"),
    "S12": ("dunk_per40", "height_c"),
    "S15": ("ftr", "rim_per40"),
    "S24": ("ftr", "usg"),
    "S16": ("usg", "unast_per40", "ast_pct"),
    "S18": ("usg", "unast_per40", "unast_three"),
    "S19": ("usg", "unast_per40", "ftr"),
    "S17": ("tov_pct", "usg", "ast_pct"),
    "S20": ("ast_pct", "usg"),
    "S29": ("orb_pct",),
    "S30": ("drb_pct",),
    "S31": ("drb_pct", "orb_pct"),
    "S32": ("drb_pct", "orb_pct"),
    "S36": ("blk_pct", "height_c"),
    "S37": ("blk_pct", "height_c"),
    "S41": ("stl_pct",),
    "S42": ("stl_pct",),
    "S43": ("stl_pct",),
    **{f"F0{i}.{part}": ("ast_pct", "ast_to") for i in range(1, 10) for part in ("recognition", "execution")},
    "T08": ("usg",),                  # offensive involvement preference (measured-usage scale)
}


def fit_input_mapping(by_player) -> dict:
    from nba_gm_data.input_estimator import scalar_value
    from nba_gm_data.utils import normalize_name
    universe = json.loads((ROOT / "data/canonical/universe_2026_27_offseason.json").read_text(encoding="utf-8"))
    inputs_path = ROOT / "data/canonical/player_inputs_2026_27.json"
    if inputs_path.exists():
        documents = json.loads(inputs_path.read_text(encoding="utf-8"))["players"]
    else:
        import gzip
        with gzip.open(str(inputs_path) + ".gz", "rt") as handle:
            documents = json.load(handle)["players"]
    final_rows = {}
    for seasons in by_player.values():
        last = max(seasons)
        row = seasons[last]
        if row.get("nba_pick") and last < CURRENT_SEASON:
            final_rows[(normalize_name(row["name"]), str(row.get("birth_date") or "")[:10])] = (row, seasons)
    by_name = defaultdict(list)
    for (name, born), value in final_rows.items():
        by_name[name].append(value)
    pairs = []
    for player in universe["players"]:
        try:
            year = int(player.get("draft_year") or 0)
        except (TypeError, ValueError):
            continue
        if year not in PAIR_DRAFTS or player["id"] not in documents:
            continue
        key = (normalize_name(player["name"]), str(player.get("birthdate") or "")[:10])
        match = final_rows.get(key)
        if match is None and len(by_name.get(key[0], [])) == 1:
            match = by_name[key[0]][0]
        if match is None:
            continue
        row, seasons = match
        last = max(seasons)
        if last != year:
            continue
        rates = season_rates(row)
        prev = seasons.get(last - 1)
        if prev and season_minutes(prev) > 0:
            # Final season plus half of the one before, by minutes: steadier rates for one-and-done-ish samples.
            w0, w1 = season_minutes(row), 0.5 * season_minutes(prev)
            rates = {k: (rates[k] * w0 + season_rates(prev)[k] * w1) / (w0 + w1) for k in PROFILE_RATES}
        shoot = shooting(career_totals(list(seasons.values())))
        inputs = documents[player["id"]]["inputs"]
        values = {iid: scalar_value(rec) for iid, rec in inputs.items()}
        pairs.append({"name": player["name"], "years": 2026 - year, "pick": int(player.get("draft_position") or row["nba_pick"]),
                      "x": pair_features(rates, shoot, player.get("height_inches") or row.get("height_in")),
                      "inputs": values})
    mapping = {}
    for target, keys in INPUT_TARGETS.items():
        usable = [p for p in pairs if p["inputs"].get(target) is not None]
        if len(usable) < 30:
            continue
        stats = {k: (statistics.fmean(p["x"][k] for p in usable), statistics.pstdev([p["x"][k] for p in usable]) or 1.0)
                 for k in keys}
        rows = [[(p["x"][k] - stats[k][0]) / stats[k][1] for k in keys] + [p["years"] - 3, math.log(p["pick"]) - 3]
                for p in usable]
        ys = [p["inputs"][target] for p in usable]
        beta = linear_fit(rows, ys, ridge=4.0)
        college_part = [sum(b * v for b, v in zip(beta[1:1 + len(keys)], r[:len(keys)])) for r in rows]
        fitted = [dot(beta, r) for r in rows]
        resid = [y - f for y, f in zip(ys, fitted)]
        r_college = statistics.correlation(college_part, ys) if statistics.pstdev(college_part) > 0 else 0.0
        r_all = statistics.correlation(fitted, ys)
        mapping[target] = {
            "features": list(keys), "means": [round(stats[k][0], 5) for k in keys], "sds": [round(stats[k][1], 5) for k in keys],
            "intercept": round(beta[0], 4), "coef": [round(b, 4) for b in beta[1:1 + len(keys)]],
            "years_coef": round(beta[-2], 4), "log_pick_coef": round(beta[-1], 4),
            "residual_sd": round(statistics.pstdev(resid), 3), "r_college": round(r_college, 3), "r_all": round(r_all, 3),
            "n": len(usable),
        }
    return {"pairs": len(pairs), "targets": mapping,
            "notes": "input = intercept + sum(coef * (feature - mean) / sd) + years_coef * (years - 3) "
                     "+ log_pick_coef * (ln(pick) - 3); entry uses years = 0."}


def drafted_final_profiles(by_player) -> list[dict]:
    out = []
    for seasons in by_player.values():
        last = max(seasons)
        row = seasons[last]
        if not row.get("nba_pick") or last >= CURRENT_SEASON:
            continue
        out.append(pair_features(season_rates(row), shooting(career_totals(list(seasons.values()))), row.get("height_in")))
    return out


def college_norms(by_player) -> dict:
    """Mean and spread of each college rate, and of each broad-skill composite, among drafted players' final seasons."""
    rows = drafted_final_profiles(by_player)
    rates = {k: [round(statistics.fmean(r[k] for r in rows), 5), round(statistics.pstdev([r[k] for r in rows]) or 1.0, 5)]
             for k in rows[0]}
    raw = {skill: [composite(r, weights, rates) for r in rows] for skill, weights in SKILL_COMPOSITES.items()}
    return {"rates": rates, "composite_sd": {k: round(statistics.pstdev(v) or 1.0, 5) for k, v in raw.items()},
            "drafted_seasons": len(rows)}


# ----------------------------------------------------------------------------------------------- main


def build(write: bool = True) -> dict:
    by_player = load_history()
    ctx = load_team_context()
    coaches = load_coaches()
    states = build_states(by_player, ctx)
    deltas = development_deltas(by_player)
    returns = return_rates(states)
    evaluation = evaluate(states, deltas, returns)
    models = {h: fit_horizon(horizon_examples(states, h)) for h in HORIZONS}
    tables = slot_tables(by_player)
    counts = college_counts(by_player)
    priors = freshman_priors(by_player)
    mapping = fit_input_mapping(by_player)
    norms = college_norms(by_player)
    curves = scout_curves(states, models)
    fresh = freshman_ranks(by_player)
    timing = recruit_timing(by_player, fresh)
    visible = visible_slot_tables(by_player, fresh)
    pos_priors = position_priors(by_player, norms)
    pool, pool_report = build_pool(by_player, ctx, models, priors, deltas, returns, coaches, curves, timing, norms, pos_priors)
    bundle = {
        "version": "real_prospects_v2",
        "built": dt.date.today().isoformat(),
        "source": ("Barttorvik (T-Rank) college player and team tables, seasons 2008-2027 (derived values only); "
                   "public 2027 draft boards and mocks; 247Sports Composite recruit ranks (classes of 2027-2028)."),
        "current_college_season": f"{CURRENT_SEASON - 1}-{str(CURRENT_SEASON)[-2:]}",
        "draft_years": [str(y) for y in DRAFT_YEARS],
        "class_size": 60,
        # Declared real players are ordered by expected pick. 2027: the boards rank the whole draft, so the k-th
        # declared player is anchored to slot k. 2028-2029: the k-th goes to the average pick of the k-th draftee
        # among players visible that far ahead (college players plus the top recruits still to arrive).
        "slot_tables": {str(DRAFT_YEARS[0]): "rank", **{str(DRAFT_YEARS[h]): visible[h] for h in (1, 2)}},
        "declaration": {
            "method": ("One draw per save and player against his chance by year (real_prospects.declaration_year). "
                       "2027: board consensus blended with the college model, model weight = games / (games + 20). "
                       "Later years: the model's split of what is left, or for ranked players the history of "
                       "returning ranked players. Recruits: history by recruiting rank. Internationals: board rank, "
                       "else a stated prior."),
            "model_weight_games_half": MODEL_GAMES_HALF, "unlisted_rank": UNLISTED_RANK,
            "injury_season_out_factor": INJURY_SEASON_OUT_FACTOR, "international_unranked_prior": INTL_UNRANKED,
            "rank_curves": curves, "recruit_timing": timing, "expected_drafted_by_year": pool_report["expected_drafted_by_year"],
        },
        "scouting_sources": {"boards": pool_report["sources"], "board_half_life_days": BOARD_HALF_LIFE_DAYS,
                             "mock_weight": MOCK_WEIGHT, "undated_weight": UNDATED_WEIGHT,
                             "as_of": SCOUT_AS_OF.isoformat()},
        "projection": {
            "features": list(FEATURES),
            "models_by_horizon": {str(h): {k: models[h][k] for k in ("means", "sds", "draft_beta", "pick_beta", "pick_log_sd", "n", "n_drafted")}
                                  for h in HORIZONS},
            "return_to_college_by_class": {str(k): v for k, v in returns.items()},
            "slot_by_college_rank": {str(h): tables[h] for h in HORIZONS},
            "college_draftees_per_draft": {str(h): counts[h] for h in HORIZONS},
            "out_of_sample": {str(h): {k: evaluation[h][k]["summary"] for k in ("direct", "chained")} for h in HORIZONS},
        },
        "development_per_year": {str(k): rounded(v) for k, v in sorted(deltas.items())},
        "college_norms": norms,
        "position_skill_priors": pos_priors,
        "input_mapping": mapping,
        "coaches_available": bool(coaches),
        "pool_summary": {k: v for k, v in pool_report.items() if k != "sources"},
        "prospects": pool,
    }
    if write:
        write_bundle(bundle)
        REPORT.parent.mkdir(parents=True, exist_ok=True)
        REPORT.write_text(json.dumps({"evaluation": evaluation, "input_mapping": mapping, "pool": pool_report},
                                     indent=1, sort_keys=True), encoding="utf-8")
    return bundle


def write_bundle(bundle: dict) -> None:
    """Pretty top level, one line per prospect (the pool is large; one line each keeps diffs readable)."""
    head = {k: v for k, v in bundle.items() if k != "prospects"}
    text = json.dumps(head, indent=1, sort_keys=True, ensure_ascii=False)
    rows = ",\n".join("  " + json.dumps(p, sort_keys=True, ensure_ascii=False, separators=(",", ":")) for p in bundle["prospects"])
    BUNDLE.write_text(text[:-2] + ',\n "prospects": [\n' + rows + "\n ]\n}\n", encoding="utf-8")


def apply_universe() -> None:
    """Rebuild the stored next-draft class (prospects, traits, scouting reports, team boards) in the canonical
    universe with the current generator and real prospects, and register the college source. Only those
    collections change; the file keeps its key order and formatting."""
    from nba_gm_data import draft
    from nba_gm_data import real_prospects as rp
    from nba_gm_data.storage import load_universe_json
    path = ROOT / "data/canonical/universe_2026_27_offseason.json"
    rp.clear_caches()
    universe = load_universe_json(path)
    context = draft.build_draft_context(universe, None)
    raw = json.loads(path.read_text(encoding="utf-8"))
    for key, value in context.items():
        raw[key] = value
    if not any(source.get("id") == rp.SOURCE_ID for source in raw.get("sources", [])):
        raw.setdefault("sources", []).append({
            "id": rp.SOURCE_ID, "title": rp.SOURCE_TITLE, "kind": "derived_public_college_statistics",
            "trust_level": "derived_model", "path": "data/canonical/real_prospects.json", "url": "https://barttorvik.com",
            "retrieved_at": "2026-11-19", "notes": rp.SOURCE_NOTES})
    if not any(source.get("id") == rp.SCOUTING_SOURCE_ID for source in raw.get("sources", [])):
        raw.setdefault("sources", []).append({
            "id": rp.SCOUTING_SOURCE_ID, "title": rp.SCOUTING_SOURCE_TITLE, "kind": "public_scouting_rankings",
            "trust_level": "public_consensus", "path": "data/research/prospect_scouting/",
            "retrieved_at": "2026-11-19", "notes": rp.SCOUTING_SOURCE_NOTES})
    for source in raw.get("sources", []):
        if source.get("id") == rp.SOURCE_ID:
            source["notes"] = rp.SOURCE_NOTES
    counts = (raw.get("meta") or {}).get("counts")
    if isinstance(counts, dict):
        for key in (*context, "sources"):
            if key in counts:
                counts[key] = len(raw[key])
    with path.open("w", encoding="utf-8") as handle:
        json.dump(raw, handle, ensure_ascii=False, indent=2)
        handle.write("\n")


def print_summary(bundle: dict) -> None:
    print("Out of sample (fit on drafts <= 2021, scored on 2022-2026):")
    for h, by_kind in bundle["projection"]["out_of_sample"].items():
        print(f"  horizon {h} direct: {by_kind['direct']}")
    dec = bundle["declaration"]
    print("Rank curves (history):", json.dumps(dec["rank_curves"]["hit_by_rank"]), json.dumps(dec["rank_curves"]["back_by_rank"]))
    print("Recruit timing:")
    for row in dec["recruit_timing"]["bands"]:
        print(f"  ranks {row['ranks']}: n={row['players']} after years {row['drafted_after_years']} "
              f"none {row['not_drafted_within_4']} typical pick {row['typical_pick']} seen {row['picks_seen']}")
    print("Slot tables:", {k: (v if isinstance(v, str) else v[:12]) for k, v in bundle["slot_tables"].items()})
    print("Pool:", json.dumps(bundle["pool_summary"]))
    for year in bundle["draft_years"]:
        rows = sorted((p for p in bundle["prospects"] if year in p["years"]),
                      key=lambda p: p["years"][year]["expected_pick"])[:15]
        print(f"\n{year}: best expected picks among players who may declare")
        for p in rows:
            v = p["years"][year]
            rank = (p.get("scouting") or {}).get("consensus_rank") or (p.get("scouting") or {}).get("recruit_ranks")
            print(f"  E{v['expected_pick']:>6} {p['name']:<26} {p['kind']:<16} {str(p.get('college_team') or (p.get('scouting') or {}).get('team'))[:18]:<18}"
                  f" age {v['age_at_draft']} chance {p['chance_by_year']} rank {rank}")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--no-write", action="store_true")
    parser.add_argument("--apply-universe", action="store_true")
    args = parser.parse_args()
    bundle = build(write=not args.no_write)
    print_summary(bundle)
    if args.apply_universe:
        apply_universe()
        print("Stored 2027 class rebuilt in the canonical universe.")


if __name__ == "__main__":
    main()
