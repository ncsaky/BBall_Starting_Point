"""Foul drawing and handle security from opportunity-adjusted counts (RATINGS-FT-TOV, 2026-11-21).

Two skills, measured per chance rather than per game, so that how often a player attacks or handles the ball (his
tendencies and his coach's usage) stays out of how well he does it (rule 7):

- Foul-drawing craft (S24) = free throws he earns, divided by the free throws an average player would earn from the
  same chances: his drives, his shots at the rim, his other twos and his threes.
- Handle security (S17) = all his turnovers divided by what an average player would commit from the same load:
  shots, shot-creating passes and touches (the classic turnover-percentage load, adjusted for creating and usage);
  plus, at half weight, the balls he loses without a pass or a foul (lost balls, strips, travels, stepping out)
  against the same handling load (touches, drives, paint touches, shots). The all-turnovers measure leads because
  it predicted the next season's turnovers best (held-out check, scripts/research/ft_tov_evidence.py) and no
  passing input carries bad-pass turnovers; the ball-loss measure keeps the handle itself visible.

Method (declared; nothing fitted to simulation outcomes or to a ranking):
1. Season counts from the Basketball Index Leaderboards Values captures (the same compact recent-seasons cache the
   overlay uses): per-75 values x minutes x 99/48 possessions per minute / 75.
2. "Expected" counts: one league rate per kind of chance, fitted by non-negative weighted least squares on every
   player-season with 250+ minutes (weights = minutes). E.g. about 0.07 free throws per drive, 0.40 per shot at the
   rim, 0.27 per other two and 0.03 per three. The turnover models also scale with usage (expected x (true usage /
   league average) ^ elasticity, about 0.21-0.26): a player who uses more of the offence draws more attention, so the
   same load is harder (fit_rates). Free throws get no usage term.
3. Each player's seasons pool with the overlay's recency weights (2025-26 1.0, 2024-25 0.6, 2023-24 0.35): observed
   O and expected E. The ratio O / E is stabilised toward his position group's average ratio by an empirical-Bayes
   (gamma-Poisson) prior: ratio = (O + a * r0) / (E + a). The prior strength a (in expected events) comes from the
   league data: a = r0 * dispersion / (variance of true ratios), that variance being the observed between-player
   variance minus the counting noise. Free throws come in pairs, so their dispersion is 2.
4. Score = log ratio (turned around for losses: fewer than expected is better), turned into a normal score by its
   rank among players with about a season of minutes or more (the overlay's percentile scale); several signals for
   one input are averaged and re-ranked. Grade = 100 * logistic(1.31 * z): 50 average, 75 about the 80th
   percentile, 90 about the 97th. Smooth and bounded; nothing is clipped.
5. The grade blends with the estimator's own value by evidence weight, as the Basketball Index overlay does:
   share = w / (w + 0.35), w = sum over seasons of season weight x minutes / (minutes + 800). The overlay skips these
   two inputs (their mapping entries say "measured_by"), so the same data is not counted twice.
Analyst claims still apply afterwards (scripts/build_player_inputs.py), unchanged.
"""
from __future__ import annotations

import math
from collections import defaultdict
from pathlib import Path
from typing import Any, Iterable, Mapping

from .bbi_evidence import (CACHE_DIR, GRADE_SLOPE, MINUTES_HALF, POSSESSIONS_PER_MINUTE, PRIOR_WEIGHT,
                           SEASON_WEIGHTS, collect_values)

VERSION = "foul_security_evidence_v1_2026_11_21"
MEASURED_INPUTS = ("S24", "S17")
FIT_MINUTES = 250          # player-seasons that define the league's expected rates
SPREAD_MINUTES = 500       # player-seasons that estimate the spread of true ratios
SCALE_WEIGHT = 0.5         # evidence weight of about a season of minutes: these players set the grade scale

METRICS = {
    "minutes_probe": "Touches Per 75",
    "fta": "Stable FTA Per 75",
    "fga": "Stable FGA Per 75",
    "threes": "3PT FGA Per 75 Possessions",
    "rim": "Rim Shot Attempts Per 75 Possessions",
    "drives": "Drives Per 75 Possessions",
    "touches": "Touches Per 75",
    "paint_touches": "Paint Touches Per 75 Possessions",
    "shots": "True Shot Attempts Per 75 Possessions",
    "potential_assists": "Potential Assists Per 75 Possessions",
    "potential_assists_per_100_passes": "Potential Assists Per 100 Passes",
    "turnovers": "Turnovers Per 75 Possessions",
    "non_pass_turnovers": "Stable Non Bad Pass Turnovers Per 75",
    "bad_pass_turnovers": "Stable Bad Pass Turnovers Per 75",
    "offensive_fouls": "Stable Offensive Fouls Per 75",
    "true_usage": "Stable True Usage%",
}

# outcome, kinds of chance (exposures), counting dispersion, direction (+1 more is better, -1 fewer is better)
MODELS = {
    "foul": {"outcome": "fta", "exposures": ("drives", "rim", "other_twos", "threes"), "dispersion": 2.0,
             "direction": 1, "usage_elasticity": False, "label": "free throws earned per chance (drives, rim shots, other twos, threes)"},
    "handle": {"outcome": "handle_losses", "exposures": ("touches", "drives", "paint_touches", "shots"),
               "dispersion": 1.0, "direction": -1, "usage_elasticity": True,
               "label": "balls lost without a pass or a foul, per handling load (touches, drives, paint touches, shots)"},
    "turnover": {"outcome": "turnovers", "exposures": ("shots", "potential_assists", "touches"), "dispersion": 1.0,
                 "direction": -1, "usage_elasticity": True, "label": "all turnovers per play used or created (shots, shot-creating passes, touches)"},
    "bad_pass": {"outcome": "bad_passes", "exposures": ("passes", "potential_assists", "drives"), "dispersion": 1.0,
                 "direction": -1, "usage_elasticity": True, "label": "bad-pass turnovers per pass load (report only; passing is a separate skill)"},
}
INPUT_SIGNALS = {
    "S24": (("foul", 1.0),),
    "S17": (("turnover", 1.0), ("handle", 0.5)),
}


def season_rows(table: Mapping[tuple[str, str], Mapping[str, tuple[float, float, str | None]]],
                seasons: Iterable[str]) -> dict[tuple[str, str], dict[str, Any]]:
    """(season, player key) -> per-75 fields plus derived chances, for player-seasons with every field present."""
    rows: dict[tuple[str, str], dict[str, Any]] = {}
    for season in seasons:
        base = table.get((season, METRICS["minutes_probe"]), {})
        for key, (_, minutes, cid) in base.items():
            if minutes <= 0:
                continue
            row: dict[str, Any] = {"season": season, "key": key, "cid": cid, "minutes": float(minutes)}
            for field, metric in METRICS.items():
                cell = table.get((season, metric), {}).get(key)
                if cell is None:
                    break
                row[field] = float(cell[0])
            else:
                row["other_twos"] = max(0.0, row["fga"] - row["threes"] - row["rim"])
                pa100 = row["potential_assists_per_100_passes"]
                row["passes"] = row["potential_assists"] / (pa100 / 100.0) if pa100 > 0 else 0.0
                # Turnover kinds: raw turnovers split by the stable shares (bad pass / offensive foul / other).
                kinds = row["non_pass_turnovers"] + row["bad_pass_turnovers"]
                handle = max(0.0, row["non_pass_turnovers"] - row["offensive_fouls"])
                row["handle_losses"] = row["turnovers"] * handle / kinds if kinds > 0 else 0.0
                row["bad_passes"] = row["turnovers"] * row["bad_pass_turnovers"] / kinds if kinds > 0 else 0.0
                rows[(season, key)] = row
    return rows


def _nnls(features: list[list[float]], targets: list[float], weights: list[float], sweeps: int = 4000) -> list[float]:
    """Non-negative weighted least squares by coordinate descent on the normal equations (a handful of features)."""
    k = len(features[0])
    a = [[0.0] * k for _ in range(k)]
    b = [0.0] * k
    for x, y, w in zip(features, targets, weights):
        for i in range(k):
            b[i] += w * x[i] * y
            for j in range(k):
                a[i][j] += w * x[i] * x[j]
    beta = [0.0] * k
    for _ in range(sweeps):
        change = 0.0
        for i in range(k):
            if a[i][i] <= 0:
                continue
            new = max(0.0, (b[i] - sum(a[i][j] * beta[j] for j in range(k) if j != i)) / a[i][i])
            change = max(change, abs(new - beta[i]))
            beta[i] = new
        if change < 1e-12:
            break
    return beta


def _usage_factor(row: Mapping[str, Any], fit: Mapping[str, Any]) -> float:
    if not fit.get("usage_elasticity") or row.get("true_usage", 0) <= 0:
        return 1.0
    return (row["true_usage"] / fit["usage_reference"]) ** fit["usage_elasticity"]


def _linear(row: Mapping[str, Any], rates: Mapping[str, float]) -> float:
    return sum(rate * row[e] for e, rate in rates.items())


def fit_rates(rows: Mapping[tuple[str, str], Mapping[str, Any]], seasons: Iterable[str]) -> dict[str, dict[str, Any]]:
    """League rate per kind of chance for each model, from player-seasons in `seasons` with FIT_MINUTES+.

    Turnover models also carry a usage elasticity: players who use more of the offence face more attention, so at
    the same load they lose the ball a little more often (Dean Oliver's usage-efficiency trade-off). The elasticity
    is the slope of log(observed / expected) on log(true usage / league average) among player-seasons with
    1,000+ minutes; rates and elasticity are refitted in turn until the elasticity settles (about 0.26 for balls lost,
    0.21 for all turnovers). Free throws get no such term: a star's extra
    free throws are not a difficulty to adjust away."""
    seasons = set(seasons)
    data = [r for (s, _), r in rows.items() if s in seasons and r["minutes"] >= FIT_MINUTES]
    weights = [r["minutes"] for r in data]
    reference = sum(r["true_usage"] * r["minutes"] for r in data) / sum(weights)
    out = {}
    for name, model in MODELS.items():
        fit: dict[str, Any] = {"usage_elasticity": 0.0, "usage_reference": reference}
        for _ in range(60 if model["usage_elasticity"] else 1):
            previous = fit["usage_elasticity"]
            factors = [_usage_factor(r, fit) for r in data]
            beta = _nnls([[r[e] * f for e in model["exposures"]] for r, f in zip(data, factors)],
                         [r[model["outcome"]] for r in data], weights)
            fit["rates"] = dict(zip(model["exposures"], beta))
            if model["usage_elasticity"]:
                xs, ys = [], []
                for r in data:
                    e = _linear(r, fit["rates"])
                    if r["minutes"] >= 1000 and e > 0 and r[model["outcome"]] > 0 and r["true_usage"] > 0:
                        xs.append(math.log(r["true_usage"] / reference))
                        ys.append(math.log(r[model["outcome"]] / e))
                mx, my = sum(xs) / len(xs), sum(ys) / len(ys)
                fit["usage_elasticity"] = (sum((x - mx) * (y - my) for x, y in zip(xs, ys))
                                           / sum((x - mx) ** 2 for x in xs))
                if abs(fit["usage_elasticity"] - previous) < 1e-5:
                    break
        out[name] = fit
    return out


def counts(row: Mapping[str, Any], model: str, fits: Mapping[str, Mapping[str, Any]]) -> tuple[float, float]:
    """(observed, expected) season counts for one player-season."""
    scale = row["minutes"] * POSSESSIONS_PER_MINUTE / 75.0
    fit = fits[model]
    expected = _linear(row, fit["rates"]) * _usage_factor(row, fit)
    return row[MODELS[model]["outcome"]] * scale, expected * scale


def spread_prior(rows: Mapping[tuple[str, str], Mapping[str, Any]], seasons: Iterable[str],
                 rates: Mapping[str, Mapping[str, float]], model: str) -> dict[str, float]:
    """League mean ratio, variance of true ratios (observed variance minus counting noise) and the prior strength."""
    seasons = set(seasons)
    ratios, noise = [], []
    for (s, _), r in rows.items():
        if s not in seasons or r["minutes"] < SPREAD_MINUTES:
            continue
        o, e = counts(r, model, rates)
        if e > 0:
            ratios.append((o / e, e))
    total = sum(e for _, e in ratios)
    mean = sum(x * e for x, e in ratios) / total
    dispersion = MODELS[model]["dispersion"]
    observed_var = sum((x - mean) ** 2 for x, _ in ratios) / len(ratios)
    noise_var = sum(dispersion * mean / e for _, e in ratios) / len(ratios)
    true_var = max(observed_var - noise_var, 0.05 * observed_var)
    return {"mean": mean, "true_variance": true_var, "noise_variance": noise_var,
            "strength": mean * dispersion / true_var, "players": len(ratios)}


def pooled_ratios(rows: Mapping[tuple[str, str], Mapping[str, Any]], season_weights: Mapping[str, float],
                  rates: Mapping[str, Mapping[str, float]], priors: Mapping[str, Mapping[str, float]],
                  groups: Mapping[str, str]) -> dict[str, dict[str, Any]]:
    """canonical id -> {model: {observed, expected, ratio, raw_ratio, weight, seasons}}, stabilised toward a role prior.

    groups maps canonical id -> position group; each group's average ratio (expected-weighted, over players with
    about a season of minutes) is its prior mean, so a small sample settles at its role's level, not the league's."""
    acc: dict[str, dict[str, list[float]]] = defaultdict(lambda: defaultdict(lambda: [0.0, 0.0]))
    meta: dict[str, dict[str, Any]] = defaultdict(lambda: {"weight": 0.0, "seasons": {}})
    for (season, _), r in rows.items():
        w = season_weights.get(season)
        cid = r["cid"]
        if not w or not cid:
            continue
        for model in MODELS:
            o, e = counts(r, model, rates)
            acc[cid][model][0] += w * o
            acc[cid][model][1] += w * e
        meta[cid]["weight"] += w * r["minutes"] / (r["minutes"] + MINUTES_HALF)
        meta[cid]["seasons"][season] = round(r["minutes"])
    group_means: dict[str, dict[str, float]] = {}
    for model in MODELS:
        sums: dict[str, list[float]] = defaultdict(lambda: [0.0, 0.0])
        for cid, models in acc.items():
            if meta[cid]["weight"] < SCALE_WEIGHT:
                continue
            o, e = models[model]
            for g in (groups.get(cid, "all"), "all"):
                sums[g][0] += o
                sums[g][1] += e
        group_means[model] = {g: o / e for g, (o, e) in sums.items() if e > 0}
    out = {}
    for cid, models in acc.items():
        out[cid] = {"weight": meta[cid]["weight"], "seasons": meta[cid]["seasons"], "group": groups.get(cid, "all")}
        for model, (o, e) in models.items():
            means = group_means[model]
            r0 = means.get(groups.get(cid, "all"), means.get("all", priors[model]["mean"]))
            a = priors[model]["strength"] * r0 / priors[model]["mean"]
            out[cid][model] = {"observed": o, "expected": e, "raw_ratio": (o / e) if e > 0 else None,
                               "ratio": (o + a * r0) / (e + a), "prior_ratio": r0, "prior_strength": a}
    return out


def _standardise(values: Mapping[str, float], pool: Iterable[str]) -> dict[str, float]:
    """Normal score of each value's mid-rank among the pool (players with about a season or more), the same
    percentile-to-normal-score scale the Basketball Index overlay uses, so these grades sit on the same scale as
    every other measured skill. Players outside the pool are placed against it, not added to it."""
    import bisect
    from statistics import NormalDist
    ordered = sorted(values[c] for c in pool if c in values)
    n = len(ordered)
    out = {}
    for c, x in values.items():
        lo, hi = bisect.bisect_left(ordered, x), bisect.bisect_right(ordered, x)
        out[c] = NormalDist().inv_cdf(((lo + hi) / 2 + 0.5) / (n + 1))
    return out


def input_scores(pooled: Mapping[str, Mapping[str, Any]]) -> dict[str, dict[str, dict[str, Any]]]:
    """canonical id -> input -> {z, grade, weight, parts}: standardised over players with SCALE_WEIGHT+ evidence."""
    pool = [cid for cid, p in pooled.items() if p["weight"] >= SCALE_WEIGHT]
    signal_z = {model: _standardise({cid: MODELS[model]["direction"] * math.log(p[model]["ratio"])
                                     for cid, p in pooled.items()}, pool) for model in MODELS}
    out: dict[str, dict[str, dict[str, Any]]] = defaultdict(dict)
    for iid, signals in INPUT_SIGNALS.items():
        combined = {cid: sum(w * signal_z[m][cid] for m, w in signals) / sum(w for _, w in signals) for cid in pooled}
        z = _standardise(combined, pool) if len(signals) > 1 else combined
        for cid, value in z.items():
            out[cid][iid] = {"z": value, "grade": 100.0 / (1.0 + math.exp(-GRADE_SLOPE * value)),
                             "weight": pooled[cid]["weight"], "parts": {m: signal_z[m][cid] for m, _ in signals}}
    return out


def position_groups(universe: Mapping[str, Any] | None) -> dict[str, str]:
    from .input_estimator import _position
    return {str(p["id"]): _position(p) for p in (universe or {}).get("players", [])}


def build(root: Path, universe: Mapping[str, Any] | None = None, *,
          season_weights: Mapping[str, float] = SEASON_WEIGHTS,
          fit_seasons: Iterable[str] | None = None, table: Mapping | None = None) -> dict[str, Any]:
    """Everything the overlay and the research report need: rates, priors, pooled ratios and input scores.
    `table` ((season, metric) -> {player key: (value, minutes, canonical id)}) defaults to the local cache."""
    if table is None:
        table = collect_values(Path(root), set(METRICS.values()))
    fit_seasons = tuple(fit_seasons or season_weights)
    rows = season_rows(table, sorted(set(fit_seasons) | set(season_weights)))
    rates = fit_rates(rows, fit_seasons)
    priors = {m: spread_prior(rows, fit_seasons, rates, m) for m in MODELS}
    pooled = pooled_ratios(rows, season_weights, rates, priors, position_groups(universe))
    return {"rows": rows, "rates": rates, "priors": priors, "pooled": pooled, "scores": input_scores(pooled)}


def apply_foul_security_evidence(section: dict[str, Any], root: Path, universe: Mapping[str, Any] | None = None,
                                 table: Mapping | None = None) -> dict[str, Any]:
    """Blend the measured grades into the estimator section in place (S24, S17). Returns a summary."""
    model = build(root, universe, table=table)
    changed = 0
    for pid, doc in section["players"].items():
        ev = model["scores"].get(pid)
        if not ev:
            continue
        pooled = model["pooled"][pid]
        for iid, score in ev.items():
            record = doc["inputs"].get(iid)
            value = (record or {}).get("value")
            if not isinstance(value, dict) or not isinstance(value.get("grade"), (int, float)):
                continue
            old = float(value["grade"])
            share = score["weight"] / (score["weight"] + PRIOR_WEIGHT)
            new = round(share * score["grade"] + (1 - share) * old, 3)
            record["value"] = {**value, "grade": new}
            parts = "; ".join(
                f"{MODELS[m]['label']}: observed {pooled[m]['observed']:.1f} vs expected {pooled[m]['expected']:.1f} "
                f"(ratio {pooled[m]['raw_ratio'] or 0:.3f}, stabilised {pooled[m]['ratio']:.3f} toward the "
                f"{pooled['group']} average {pooled[m]['prior_ratio']:.3f}), score {score['parts'][m]:+.2f}"
                for m, _ in INPUT_SIGNALS[iid])
            record["evidence"] = [*(record.get("evidence") or []), {
                "source": f"{CACHE_DIR}/normalized.json (Leaderboards Values)",
                "method": (f"{VERSION}: opportunity-adjusted rate against the league's expected rate for the same "
                           f"chances -> grade {score['grade']:.3f} (z {score['z']:+.3f}), blended share {share:.2f} "
                           f"with prior/estimate {round(old, 6)}"),
                "shared_evidence_id": f"bbi:{pid}:{iid}",
                "notes": parts + "; seasons/minutes: " + ", ".join(f"{s} {m}" for s, m in sorted(pooled["seasons"].items())),
            }]
            if share >= 0.5:
                record["status"], record["reason"] = "estimated", "estimated"
            changed += 1
    rates = {m: {**{k: round(v, 4) for k, v in f["rates"].items()}, "usage_elasticity": round(f["usage_elasticity"], 3)}
             for m, f in model["rates"].items()}
    return {"foul_security_evidence": {"version": VERSION, "cells_changed": changed, "league_rates": rates,
                                       "prior_strength": {m: round(p["strength"], 1) for m, p in model["priors"].items()}}}
