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
import statistics
import sys
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
# A real player joins a class only if he has at least this chance of being drafted that year; fewer but likelier
# names beat a long list of long shots (the rest of the class is generated).
MIN_PROBABILITY = 0.15

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

PROFILE_RATES = ("min_pct", "usg", "ortg", "ts", "orb_pct", "drb_pct", "ast_pct", "tov_pct", "blk_pct", "stl_pct",
                 "ftr", "gbpm", "ogbpm", "dgbpm", "three_rate", "three_per40", "rim_per40", "dunk_per40",
                 "unast_per40", "unast_three", "ast_to", "fouls40")


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


def assign_current(by_player, ctx, models, slot_table, counts, priors, deltas, returns, coaches) -> tuple[list[dict], dict]:
    from nba_gm_data.utils import normalize_name
    excluded = universe_exclusions()
    candidates = []
    for pid, seasons in by_player.items():
        row = seasons.get(CURRENT_SEASON)
        if not row or row.get("nba_pick") or num(row.get("games")) < 1:
            continue
        if normalize_name(row["name"]) in excluded:
            continue
        rates, shoot, minutes = current_profile(seasons, priors, deltas)
        state = make_state(row, rates, shoot, minutes, seasons.get(CURRENT_SEASON - 1),
                           team_strength(ctx, CURRENT_SEASON, row["team"]))
        per_h = horizon_predict(models, state, returns)
        h_best = max(per_h, key=lambda h: (per_h[h][0], -h))
        p, pick = per_h[h_best]
        if p < 0.01:
            continue
        candidates.append({"pid": pid, "row": row, "seasons": seasons, "h": h_best, "p": p, "pick": pick,
                           "per_h": per_h, "score": draft_score(p, pick), "state": state})
    classes = {}
    out = []
    for h in HORIZONS:
        pool = sorted((c for c in candidates if c["h"] == h), key=lambda c: (-c["score"], c["pid"]))
        expected = sum(c["p"] for c in pool)
        pool = [c for c in pool if c["p"] >= MIN_PROBABILITY]
        n = int(min(len(pool), len(slot_table[h]), round(counts[h]), round(expected)))
        used_slots = set()
        for k, cand in enumerate(pool[:n], start=1):
            slot = int(round(slot_table[h][k - 1]))
            while slot in used_slots:
                slot += 1
            used_slots.add(slot)
            row = cand["row"]
            year = CURRENT_SEASON + h
            state = cand["state"]
            for _ in range(h):
                state = project_state(state, deltas)
            seasons = cand["seasons"]
            born = known_birth_date(row)
            out.append({
                "id": f"college_{cand['pid']}", "barttorvik_id": cand["pid"], "name": row["name"],
                "draft_year": str(year), "class_rank": k, "projected_pick": slot,
                "draft_probability": round(cand["p"], 3), "expected_pick_if_drafted": round(cand["pick"], 1),
                "draft_chance_by_year": {str(CURRENT_SEASON + hh): round(v[0], 3) for hh, v in cand["per_h"].items()},
                "draft_score": round(cand["score"], 4),
                "college_team": row.get("team"), "conference": row.get("conf"),
                "coach": coaches.get((CURRENT_SEASON, row.get("team"))),
                "class_year_now": row.get("class_year"),
                "class_year_at_draft": ["Fr", "So", "Jr", "Sr"][min(3, class_index(row) + h)],
                "birth_date": born.isoformat() if born else None,
                "age_at_draft": round(state_age(cand["state"], year), 2), "age_estimated": born is None,
                "height_inches": row.get("height_in"), "role": row.get("role") or None,
                "recruit_rating": row.get("recruit_rating"), "hometown": row.get("hometown") or None,
                "games_this_season": int(num(row.get("games"))),
                "effective_minutes": round(cand["state"]["minutes"], 0),
                "projected_profile": {**rounded(state["rates"]),
                                      **rounded({k: state["shoot"][k] for k in ("ft_pct", "three_pct", "rim_pct", "mid_pct")}),
                                      "fta": state["shoot"]["fta"], "three_a": state["shoot"]["three_a"]},
                "seasons": [season_card(seasons[s]) for s in sorted(seasons, reverse=True)[:4]],
            })
        classes[str(CURRENT_SEASON + h)] = {"real_players": n, "expected_from_model": round(expected, 1),
                                            "historical_college_draftees": counts[h]}
    return out, classes


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


def pair_features(rates: dict, shoot: dict, height: float | None) -> dict[str, float]:
    return {**{k: rates[k] for k in PROFILE_RATES}, **{k: shoot[k] for k in ("ft_pct", "three_pct", "rim_pct", "mid_pct")},
            "height_c": (height or 78) - 78}


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


# Broad draft traits from college rates: weights on standardized rates (against drafted players' final seasons);
# each composite is then rescaled to unit spread over that same drafted pool.
SKILL_COMPOSITES = {
    "shooting": {"ft_pct": 0.4, "three_pct": 0.3, "three_rate": 0.2, "three_per40": 0.1},
    "shot_creation": {"usg": 0.45, "unast_per40": 0.35, "unast_three": 0.2},
    "rim_pressure": {"rim_per40": 0.4, "ftr": 0.35, "dunk_per40": 0.25},
    "passing": {"ast_pct": 0.65, "ast_to": 0.35},
    "defense": {"stl_pct": 0.45, "dgbpm": 0.35, "blk_pct": 0.2},
    "rim_protection": {"blk_pct": 0.75, "height_c": 0.25},
    "rebounding": {"drb_pct": 0.5, "orb_pct": 0.5},
    "feel": {"ast_to": 0.3, "gbpm": 0.4, "tov_pct": -0.3},
    "athleticism": {"dunk_per40": 0.35, "stl_pct": 0.2, "blk_pct": 0.15, "rim_per40": 0.15, "orb_pct": 0.15},
    "size": {"height_c": 1.0},
    "motor": {"orb_pct": 0.4, "stl_pct": 0.3, "min_pct": 0.3},
    "nba_readiness": {"gbpm": 0.5, "ortg": 0.25, "min_pct": 0.25},
}


def drafted_final_profiles(by_player) -> list[dict]:
    out = []
    for seasons in by_player.values():
        last = max(seasons)
        row = seasons[last]
        if not row.get("nba_pick") or last >= CURRENT_SEASON:
            continue
        out.append(pair_features(season_rates(row), shooting(career_totals(list(seasons.values()))), row.get("height_in")))
    return out


def composite(x: dict, weights: dict, rates: dict) -> float:
    return sum(w * (x[k] - rates[k][0]) / rates[k][1] for k, w in weights.items())


def college_norms(by_player) -> dict:
    """Mean and spread of each college rate, and of each broad-skill composite, among drafted players' final seasons."""
    rows = drafted_final_profiles(by_player)
    rates = {k: [round(statistics.fmean(r[k] for r in rows), 5), round(statistics.pstdev([r[k] for r in rows]) or 1.0, 5)]
             for k in rows[0]}
    raw = {skill: [composite(r, weights, rates) for r in rows] for skill, weights in SKILL_COMPOSITES.items()}
    return {"rates": rates, "composite_sd": {k: round(statistics.pstdev(v) or 1.0, 5) for k, v in raw.items()},
            "drafted_seasons": len(rows)}


def skill_scores(x: dict, norms: dict) -> dict[str, float]:
    """Standard scores of each broad skill against drafted college players (0 = typical draftee)."""
    return {skill: round(composite(x, weights, norms["rates"]) / norms["composite_sd"][skill], 3)
            for skill, weights in SKILL_COMPOSITES.items()}


def input_parts(x: dict, mapping: dict) -> dict[str, float]:
    """College part of each fitted 94-input target (the game adds the intercept, years and draft-slot terms)."""
    out = {}
    for iid, fit in mapping["targets"].items():
        out[iid] = round(sum(c * (x[k] - m) / sd for k, c, m, sd in zip(fit["features"], fit["coef"], fit["means"], fit["sds"])), 3)
    return out


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
    prospects, classes = assign_current(by_player, ctx, models, tables, counts, priors, deltas, returns, coaches)
    mapping = fit_input_mapping(by_player)
    norms = college_norms(by_player)
    for prospect in prospects:
        profile = prospect["projected_profile"]
        x = pair_features(profile, profile, prospect["height_inches"])
        prospect["skill_scores"] = skill_scores(x, norms)
        prospect["input_parts"] = input_parts(x, mapping)
    for year, info in classes.items():
        members = [p for p in prospects if p["draft_year"] == year]
        info.update({f"top_{n}": sum(1 for p in members if p["projected_pick"] <= n) for n in (10, 30, 60)})
    bundle = {
        "version": "real_prospects_v1",
        "built": dt.date.today().isoformat(),
        "source": "Barttorvik (T-Rank) college player and team tables, seasons 2008-2027; derived values only.",
        "current_college_season": f"{CURRENT_SEASON - 1}-{str(CURRENT_SEASON)[-2:]}",
        "draft_years": sorted(classes),
        "classes": classes,
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
        "input_mapping": mapping,
        "coaches_available": bool(coaches),
        "prospects": prospects,
    }
    if write:
        BUNDLE.write_text(json.dumps(bundle, indent=1, sort_keys=True, ensure_ascii=False) + "\n", encoding="utf-8")
        REPORT.parent.mkdir(parents=True, exist_ok=True)
        REPORT.write_text(json.dumps({"evaluation": evaluation, "classes": classes, "input_mapping": mapping},
                                     indent=1, sort_keys=True), encoding="utf-8")
    return bundle


def apply_universe() -> None:
    """Rebuild the stored next-draft class (prospects, traits, scouting reports, team boards) in the canonical
    universe with the current generator and real prospects, and register the college source. Only those
    collections change; the file keeps its key order and formatting."""
    from nba_gm_data import draft
    from nba_gm_data import real_prospects as rp
    from nba_gm_data.storage import load_universe_json
    path = ROOT / "data/canonical/universe_2026_27_offseason.json"
    rp._load.cache_clear()
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
        for kind, summary in by_kind.items():
            print(f"  horizon {h} {kind}: {summary}")
    print("Classes:", json.dumps(bundle["classes"], indent=1))
    for year in bundle["draft_years"]:
        print(f"\n{year} real prospects (top 15):")
        for p in [p for p in bundle["prospects"] if p["draft_year"] == year][:15]:
            prof = p["projected_profile"]
            print(f"  #{p['projected_pick']:>2} {p['name']:<24} {p['college_team']:<16} {p['class_year_now']} age {p['age_at_draft']}"
                  f" p={p['draft_probability']:.2f} usg {prof['usg']:.0f} 3P {prof['three_pct']:.3f} FT {prof['ft_pct']:.3f}"
                  f" ast {prof['ast_pct']:.0f} blk {prof['blk_pct']:.1f} bpm {prof['gbpm']:.1f}")
    print("\nCollege -> pro skill fits (correlation of the college part, n):")
    for target, fit in bundle["input_mapping"]["targets"].items():
        print(f"  {target}: r={fit['r_college']:+.2f} all={fit['r_all']:.2f} n={fit['n']} coef={fit['coef']}")


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
