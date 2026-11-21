"""Fits and spot-checks for the Stage 2 possession loop (research only; light, no game simulation unless asked).

Every fit here sets one of the ENGINE's conversion rules from real 2025-26 data, on a fixed half of the rotation
players (the same hash as the shooting and rebound checks), and is checked on the other half. Player inputs are never
changed (AGENTS.md rule 1).

- usage weight (cards.USAGE): log of real usage share (FGA + .44 FTA + TOV per team possession on the floor) on
  tendencies (involvement T08, shoot / drive / pass / post choices T01, difficulty tolerance T04, dribble persistence
  T06) and a few creation skills (the coach gives the ball to those who can use it);
- turnover log-odds (cards.TURNOVER): real turnovers per used possession on passing risk (T07), pass and drive choices,
  dribble persistence, handle security (S17), dribble manipulation (S16), passing execution;
- block weight (cards.BLOCKS): log of real blocks per 36 on contest technique, interior positioning, reach, jump-contest
  habit, vertical and help commitment;
- dunk share (cards.DUNK): Basketball-Reference dunk share of attempts within 3 ft on reach + vertical and dunk skill;
- hook family (cards.HOOK): Basketball Index short-midrange make rates with the floater / hook / short-jumper mix the
  card gives each player.
Real data: data/calibration/nba_2025_26_targets.json (per-player per-36 rates and minutes), Basketball Index tables,
Basketball-Reference shooting.
"""
from __future__ import annotations

import json
import math
from pathlib import Path
from typing import Any, Callable, Mapping, Sequence

from .game_contexts import GENERIC, league_flat_inputs, split_half

TARGETS = "data/calibration/nba_2025_26_targets.json"
MIN_MINUTES = 500.0
TEAM_POSS_PER36 = 102.0 * 36.0 / 48.0

USAGE_TERMS = ("log T08", "log T01.shoot", "log T01.drive", "log T01.pass", "log T01.post", "log T04", "log T06",
               "S16", "S19", "S.three_mode", "S10")
TURNOVER_TERMS = ("log T07", "log T01.pass", "log T01.drive", "log T06", "log T08", "S16", "S17", "F.execution", "S20")
BLOCK_TERMS = ("S37", "S36", "P03", "log T16.jump", "P10", "log T15")


def _value(flat: Mapping[str, float], term: str) -> float:
    if term.startswith("log "):
        return math.log(max(1e-3, float(flat.get(term[4:], .2))))
    return float(flat.get(term, 50.0))


def solve_wls(rows: Sequence[Sequence[float]], y: Sequence[float], w: Sequence[float], ridge: float = 1e-6) -> list[float]:
    """Weighted least squares (intercept is the first column of rows) by Gaussian elimination."""
    k = len(rows[0])
    a = [[0.0] * k for _ in range(k)]
    b = [0.0] * k
    for x, yy, ww in zip(rows, y, w):
        for i in range(k):
            b[i] += ww * x[i] * yy
            xi = ww * x[i]
            for j in range(k):
                a[i][j] += xi * x[j]
    for i in range(1, k):
        a[i][i] += ridge * a[i][i]
    for col in range(k):
        piv = max(range(col, k), key=lambda r: abs(a[r][col]))
        a[col], a[piv] = a[piv], a[col]
        b[col], b[piv] = b[piv], b[col]
        d = a[col][col] or 1e-12
        for r in range(k):
            if r != col and a[r][col]:
                f = a[r][col] / d
                for c in range(col, k):
                    a[r][c] -= f * a[col][c]
                b[r] -= f * b[col]
    return [b[i] / (a[i][i] or 1e-12) for i in range(k)]


def real_rotation(root: str | Path) -> dict[str, dict]:
    """player id -> real 2025-26 per-36 rates and minutes (rotation players with inputs)."""
    targets = json.loads((Path(root) / TARGETS).read_text())["players"]
    flats = league_flat_inputs(root)
    out = {}
    for pid, row in targets.items():
        if pid in flats and pid != GENERIC and float(row.get("minutes") or 0) >= MIN_MINUTES:
            out[pid] = dict(row)
    return out


def _stats(pairs: list[tuple[float, float, float]]) -> dict[str, float] | None:
    if len(pairs) < 3:
        return None
    w = sum(p[2] for p in pairs)
    mp = sum(p[2] * p[0] for p in pairs) / w
    mr = sum(p[2] * p[1] for p in pairs) / w
    cov = sum(p[2] * (p[0] - mp) * (p[1] - mr) for p in pairs) / w
    vp = sum(p[2] * (p[0] - mp) ** 2 for p in pairs) / w
    vr = sum(p[2] * (p[1] - mr) ** 2 for p in pairs) / w
    mse = sum(p[2] * (p[0] - p[1]) ** 2 for p in pairs) / w
    return {"players": len(pairs), "real": round(mr, 4), "predicted": round(mp, 4), "bias": round(mp - mr, 4),
            "rmse": round(math.sqrt(mse), 4), "corr": round(cov / math.sqrt(vp * vr), 3) if vp > 0 and vr > 0 else None}


def fit_log_linear(root: str | Path, terms: Sequence[str], target: Callable[[dict], float | None],
                   link: str = "log", train: int = 0) -> dict[str, Any]:
    """Fit target(row) = link^-1(c + sum b x) on the fit half (minutes-weighted); score both halves."""
    flats = league_flat_inputs(root)
    real = real_rotation(root)
    data = []
    for pid, row in real.items():
        y = target(row)
        if y is None:
            continue
        x = [1.0] + [_value(flats[pid], t) for t in terms]
        data.append((pid, x, y, float(row["minutes"])))

    def fwd(y):
        y = min(max(y, 1e-4), 1 - 1e-4) if link == "logit" else max(y, 1e-3)
        return math.log(y / (1 - y)) if link == "logit" else math.log(y)

    def inv(z):
        return 1 / (1 + math.exp(-z)) if link == "logit" else math.exp(z)

    fit = [d for d in data if split_half(d[0]) == train]
    beta = solve_wls([d[1] for d in fit], [fwd(d[2]) for d in fit], [d[3] for d in fit])
    model = {"constant": beta[0], **{t: b for t, b in zip(terms, beta[1:])}}
    pred = {d[0]: inv(sum(b * x for b, x in zip(beta, d[1]))) for d in data}
    halves = {}
    for name, half in (("fit", train), ("held", 1 - train)):
        halves[name] = _stats([(pred[d[0]], d[2], d[3]) for d in data if split_half(d[0]) == half])
    return {"model": {k: round(v, 5) for k, v in model.items()}, "halves": halves, "predictions": pred,
            "real": {d[0]: d[2] for d in data}}


def usage_target(row: dict) -> float | None:
    used = float(row.get("fga_per36") or 0) + .44 * float(row.get("fta_per36") or 0) + float(row.get("turnovers_per36") or 0)
    return used / TEAM_POSS_PER36 if used > 0 else None


def turnover_target(row: dict) -> float | None:
    tov = float(row.get("turnovers_per36") or 0)
    used = float(row.get("fga_per36") or 0) + .44 * float(row.get("fta_per36") or 0) + tov
    return tov / used if used > 0 else None


def blocks_target(row: dict) -> float | None:
    return max(.02, float(row.get("blocks_per36") or 0))


def fit_all(root: str | Path) -> dict[str, Any]:
    return {"usage": fit_log_linear(root, USAGE_TERMS, usage_target, "log"),
            "turnover": fit_log_linear(root, TURNOVER_TERMS, turnover_target, "logit"),
            "blocks": fit_log_linear(root, BLOCK_TERMS, blocks_target, "log")}


# ---- dunk share --------------------------------------------------------------------------------------------------
def fit_dunk_share(root: str | Path, train: int = 0) -> dict[str, Any]:
    """Logistic dunk share of close attempts on (reach + vertical - 330) / 10 and (S12 - 50) / 25; grid search."""
    from .shooting_check import _bref_dunk_shares
    from .league_inputs import player_directory
    flats = league_flat_inputs(root)
    shares = _bref_dunk_shares(Path(root))
    directory = player_directory(root)
    real = real_rotation(root)
    rows = []
    for pid in real:
        espn = directory.get(pid, {}).get("espn_player_id")
        if espn and espn in shares:
            f = flats[pid]
            rows.append((pid, float(f["P03"]) + float(f["P10"]), float(f["S12"]), shares[espn],
                         float(real[pid]["minutes"])))

    def pred(params, h, s):
        base, kh, ks = params
        if h < 310.0:
            return 0.0
        return 1 / (1 + math.exp(-(base + kh * (h - 330) / 10 + ks * (s - 50) / 25)))

    def loss(params, half):
        return sum(m * (pred(params, h, s) - y) ** 2 for pid, h, s, y, m in rows if split_half(pid) == half)

    best = (-1.2, .55, .45)
    cur = loss(best, train)
    step = .4
    while step > .005:
        improved = False
        for i in range(3):
            for d in (step, -step):
                trial = list(best)
                trial[i] += d
                v = loss(trial, train)
                if v < cur:
                    best, cur, improved = tuple(trial), v, True
        if not improved:
            step /= 2
    out = {"params": {"base": round(best[0], 3), "k_height": round(best[1], 3), "k_skill": round(best[2], 3)}}
    for name, half in (("fit", train), ("held", 1 - train)):
        out[name] = _stats([(pred(best, h, s), y, m) for pid, h, s, y, m in rows if split_half(pid) == half])
    return out


# ---- hook family -------------------------------------------------------------------------------------------------
def fit_hook(root: str | Path, train: int = 0) -> dict[str, Any]:
    """Short-midrange make rate = floater share x floater + hook share x hook + jumper share x short jumper (each
    player's card mix within the short-paint region); fit the hook family's floor, slope and reach term on the fit
    half of Basketball Index short-mid FG%, attempt-weighted."""
    from . import cards as C
    from .shooting_check import real_shooting
    flats = league_flat_inputs(root)
    real = real_shooting(root)
    rows = []
    for pid, r in real.items():
        if pid not in flats or "short_mid" not in r["zones"]:
            continue
        pct, att = r["zones"]["short_mid"]
        f = flats[pid]
        menu = C.shot_menu(f)
        fl, hk, sj = (menu[C.KIND_INDEX[k]] for k in ("floater", "hook", "short_jumper"))
        tot = fl + hk + sj
        if tot <= 0:
            continue
        table = C.make_table(pid, f)
        p = C.offense_profile(pid, f)
        rows.append((pid, fl / tot, hk / tot, sj / tot, table[C.KIND_INDEX["floater"]], table[C.KIND_INDEX["short_jumper"]],
                     float(f["S23"]) / 100 * (.9 + .1 * p.balance), (float(f["P03"]) - 270) / 10, pct, att))

    def pred(params, row):
        floor, span, kr = params
        _, a, b, c, fl, sj, s23, reach, _, _ = row
        hook = min(.85, max(.15, floor + span * s23 + kr * reach))
        return a * fl + b * hook + c * sj

    def loss(params, half):
        return sum(r[-1] * (pred(params, r) - r[-2]) ** 2 for r in rows if split_half(r[0]) == half)

    best = (C.HOOK["floor"], C.HOOK["span"], C.HOOK["k_reach"])
    cur = loss(best, train)
    step = .1
    while step > .001:
        improved = False
        for i in range(3):
            for d in (step, -step):
                trial = list(best)
                trial[i] += d
                if trial[0] < 0 or trial[1] < 0 or trial[0] + trial[1] > 1:
                    continue
                v = loss(trial, train)
                if v < cur:
                    best, cur, improved = tuple(trial), v, True
        if not improved:
            step /= 2
    out = {"params": {"floor": round(best[0], 4), "span": round(best[1], 4), "k_reach": round(best[2], 4)}}
    before = (C.HOOK["floor"], C.HOOK["span"], C.HOOK["k_reach"])
    for name, half in (("fit", train), ("held", 1 - train)):
        out[name] = _stats([(pred(best, r), r[-2], r[-1]) for r in rows if split_half(r[0]) == half])
        out[name + "_before"] = _stats([(pred(before, r), r[-2], r[-1]) for r in rows if split_half(r[0]) == half])
        # The short-mid check as S2-SEAM-SHOOTING scored it (half floater, half jumper).
        out[name + "_seam_rule"] = _stats([(.5 * r[4] + .5 * r[5], r[-2], r[-1]) for r in rows if split_half(r[0]) == half])
    bigs = [r for r in rows if r[2] > .35]
    out["post_heavy_players"] = {"n": len(bigs), "after": _stats([(pred(best, r), r[-2], r[-1]) for r in bigs]),
                                 "seam_rule": _stats([(.5 * r[4] + .5 * r[5], r[-2], r[-1]) for r in bigs])}
    return out


# ---- shooting fouls by action ------------------------------------------------------------------------------------
FOUL_PARAMS = ("base0", "base1", "base2", "foul_drive", "foul_roll_cut", "foul_post", "foul_jumper", "foul_pull_up",
               "k_drive_craft")
# Signs follow the mechanism (a free fit trades actions against zones and drifts to nonsense, e.g. pull-ups never
# fouled): drives draw more contact than the zone average, rolls/cuts and catch jumpers less; foul-drawing craft can
# only add fouls on drives and pull-ups.
FOUL_BOUNDS = {"base0": (-3.0, 0.0), "base1": (-3.0, 0.0), "base2": (-5.0, -1.5), "foul_drive": (0.0, 1.5),
               "foul_roll_cut": (-1.5, 0.0), "foul_post": (-1.0, 1.0), "foul_jumper": (-1.5, 0.0),
               "foul_pull_up": (-1.0, 1.0), "k_drive_craft": (0.0, 1.5)}


def fit_fouls(root: str | Path, train: int = 0, loop: dict | None = None) -> dict[str, Any]:
    """Free throws per field-goal attempt per player, from his card's action menu: for each half-court shot kind the
    shooting-foul chance (foul kernel zone base + his drawing terms + the action term + foul-drawing craft on drives
    and pull-ups, against the league-average contester), the and-one share, plus his share of bonus free throws from
    non-shooting fouls. Fits the zone bases, the action terms and the craft term on the fit half (FGA-weighted squared
    error of FTA per FGA), scores both halves. The three-point base stays at Basketball Index's 1.1% foul rate."""
    from . import cards as C
    from .fouls import FITTED as FC
    from .game import LOOP
    loop = dict(LOOP, **(loop or {}))
    flats = league_flat_inputs(root)
    real = real_rotation(root)
    means = C.means_for(root)
    rows = []
    wsum = dsum = nsum = usum = 0.0
    cards = {}
    for pid, row in real.items():
        c = C.build_card(pid, pid, flats[pid], means)
        cards[pid] = c
        m = float(row["minutes"])
        wsum += m
        dsum += m * c.d_foul
        nsum += m * c.ns_draw
        usum += m * c.usage
    d_avg, ns_mean, u_mean = dsum / wsum, nsum / wsum, usum / wsum
    ns_fta_per_shot = loop["ns_per_poss"] * .274 * 2 / .85
    for pid, row in real.items():
        fga = float(row.get("fga_per36") or 0)
        if fga * float(row["minutes"]) / 36 < 150:
            continue
        c = cards[pid]
        kinds = []
        for k in range(10):
            if c.menu[k] > 0:
                zone, action = C.KINDS[k][2], C.KINDS[k][1]
                craft = (float(flats[pid]["S24"]) - 50) / 25 if action in ("drive", "pull_up") else 0.0
                kinds.append((c.menu[k], zone, action, craft, c.and1[zone]))
        ns = ns_fta_per_shot * (c.ns_draw / ns_mean) / (c.usage / u_mean)
        rows.append((pid, kinds, c.foul_s + d_avg, ns, float(row["fta_per36"]) / fga, fga * float(row["minutes"]) / 36))

    def predict(params: dict, r) -> float:
        _, kinds, s, ns, _, _ = r
        num = den = 0.0
        base = (params["base0"], params["base1"], params["base2"], FC.base[3])
        for m, zone, action, craft, a1 in kinds:
            z = base[zone] + s + params.get("foul_" + action, 0.0) + params["k_drive_craft"] * craft
            p = 1 / (1 + math.exp(-z))
            fta = a1 + (1 - a1) * (3 if zone == 3 else 2)
            num += m * p * fta
            den += m * (1 - p * (1 - a1))
        return (num + ns) / den

    def loss(params, half):
        return sum(r[5] * (predict(params, r) - r[4]) ** 2 for r in rows if split_half(r[0]) == half)

    params = {"base0": FC.base[0], "base1": FC.base[1], "base2": FC.base[2],
              **{k: loop[k] for k in FOUL_PARAMS if k.startswith("foul_")}, "k_drive_craft": 0.0}
    start = dict(params)
    cur = loss(params, train)
    step = .25
    while step > .004:
        improved = False
        for key in FOUL_PARAMS:
            for d in (step, -step):
                trial = dict(params)
                trial[key] += d
                lo, hi = FOUL_BOUNDS[key]
                if not lo <= trial[key] <= hi:
                    continue
                v = loss(trial, train)
                if v < cur:
                    params, cur, improved = trial, v, True
        if not improved:
            step /= 2
    out = {"params": {k: round(v, 4) for k, v in params.items()}}
    for name, half in (("fit", train), ("held", 1 - train)):
        out[name] = _stats([(predict(params, r), r[4], r[5]) for r in rows if split_half(r[0]) == half])
        out[name + "_start"] = _stats([(predict(start, r), r[4], r[5]) for r in rows if split_half(r[0]) == half])
    preds = sorted(((r[5] * (predict(params, r) - r[4]), r[0]) for r in rows))
    out["under"] = [(pid, round(v)) for v, pid in preds[:12]]
    out["over"] = [(pid, round(v)) for v, pid in preds[-12:]]
    return out
