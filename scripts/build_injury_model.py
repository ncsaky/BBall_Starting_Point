#!/usr/bin/env python3
"""Fit the per-body-part injury model (v2) to Basketball Index Injury Tracker evidence.

Evidence: data/research/bbi/tools/injury_*.json (extracted by scripts/bbi_extract_tools.py from the signed-in tool page).
For each body part, a Poisson model of injuries per game played, fitted on real player-seasons 2015-16..2025-26:

    injuries(part) ~ games_played * exp(season_intercept + b . features)

features (standardized): age, age^2, height, weight, possessions per game (workload), rim pressure, offensive rebounding,
conditioning (stamina), center, guard, recent same-part injuries (time-decayed) and recent other-part injuries.
Season intercepts are unpenalized so reporting coverage across seasons cannot drive the shared slopes. Gameplay uses
one intercept per part, anchored to the 2021-22 through 2024-25 tracker totals with the engine's history discount.
The same-part term is the compounding effect; age/body/style terms decide which
injuries a player tends to get. Recovery times are not modeled parametrically: the engine samples a real absence for
the drawn part (diagnosis, days, games), weighted toward recent seasons.

    PYTHONPATH=src .venv/bin/python scripts/build_injury_model.py [--write]
Writes data/canonical/injury_model_v2.json.
"""
from __future__ import annotations

import argparse
import json
import math
import statistics
import sys
from collections import Counter, defaultdict
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

B = ROOT / "data/research/bbi/tools"
OUT = ROOT / "data/canonical/injury_model_v2.json"
EVIDENCE_OUT = ROOT / "data/canonical/injury_player_evidence_v2.json"   # git-ignored: per-player Basketball Index evidence
FIRST_SEASON = "2015-16"
RATE_ANCHOR_SEASONS = ("2021-22", "2022-23", "2023-24", "2024-25")
# Recovery times come from absences recorded since 2015, the same seasons the injury-rate models are fitted on
# (INJURIES-2, 2026-11-20). Older records describe a different reporting world: before 2005-06 the injured list had a
# five-game minimum and half the records have no logged return (median return 28 days in 2000-05, 10 in 2006-14, 5 in
# 2015-20, 4 in 2021-26). Even at a 6-year half-life they made the pool's tail half again too long against the
# tracker's own 2021-25 absences (90th percentile 45 days against 28).
RECOVERY_FIRST_YEAR = 2015
RIDGE = 3.0
HISTORY_DECAY_YEARS = 1.5
PARTS = ["ankle", "knee", "back", "hamstring", "hip", "foot", "calf", "shoulder", "groin", "quadriceps", "toe", "head",
         "wrist", "hand", "achilles", "thumb"]
# Basketball Index's rarer parts folded into the nearest of its 16 risk parts.
MERGE = {"heel": "foot", "finger": "hand", "elbow": "shoulder", "forearm": "wrist", "arm": "shoulder", "leg": "calf",
         "shin": "calf", "neck": "back", "abdomen": "back", "ribs": "back", "chest": "back", "tailbone": "back",
         "eye": "head", "dental": "head"}
FEATURES = ["age", "age2", "height", "weight", "poss_pg", "rim_pressure", "offensive_rebounding", "stamina",
            "center", "guard", "prior_same", "prior_other"]


def rows(name):
    d = json.loads((B / name).read_text())
    return d["rows"] if isinstance(d, dict) and "rows" in d else d


def season_start(season: str) -> date:
    return date(int(season[:4]), 10, 20)


def part_of(h) -> str | None:
    if h.get("cat") == "illness":
        return "illness"
    if h.get("cat") != "injury" or not h.get("part"):
        return None
    p = MERGE.get(h["part"], h["part"])
    return p if p in PARTS else None


def poisson_ridge(X, y, exposure, intercepts, lam=RIDGE, iters=60):
    """Newton/IRLS for Poisson counts with an exposure offset and unpenalized intercepts."""
    n = len(X[0])
    b = [*intercepts, *([0.0] * (n - len(intercepts)))]
    for _ in range(iters):
        g = [0.0] * n
        H = [[0.0] * n for _ in range(n)]
        for x, yi, e in zip(X, y, exposure):
            eta = sum(bi * xi for bi, xi in zip(b, x))
            mu = e * math.exp(max(-30.0, min(30.0, eta)))
            r = yi - mu
            for i in range(n):
                g[i] += r * x[i]
                for j in range(i, n):
                    H[i][j] += mu * x[i] * x[j]
        for i in range(len(intercepts), n):
            g[i] -= lam * b[i]
            H[i][i] += lam
        for i in range(n):
            for j in range(i):
                H[i][j] = H[j][i]
        # Solve H d = g (Gaussian elimination).
        A = [row[:] + [gi] for row, gi in zip(H, g)]
        for i in range(n):
            piv = max(range(i, n), key=lambda r: abs(A[r][i]))
            A[i], A[piv] = A[piv], A[i]
            for r in range(i + 1, n):
                f = A[r][i] / A[i][i]
                for c in range(i, n + 1):
                    A[r][c] -= f * A[i][c]
        d = [0.0] * n
        for i in reversed(range(n)):
            d[i] = (A[i][n] - sum(A[i][k] * d[k] for k in range(i + 1, n))) / A[i][i]
        b = [bi + di for bi, di in zip(b, d)]
        if max(abs(di) for di in d) < 1e-7:
            break
    return b


def fit_season_rates(features, counts, exposure, seasons):
    """Return season intercepts and common slopes. Zero-event seasons have zero fitted rate."""
    season_totals = Counter()
    season_exposure = Counter()
    for season, count, games in zip(seasons, counts, exposure):
        season_totals[season] += count
        season_exposure[season] += games
    fitted = sorted(season for season, count in season_totals.items() if count)
    # Within a season that reports no events, the intercept tends to negative infinity.
    # That season contributes no information about the slopes.
    design, response, games = [], [], []
    for season, x, count, gp in zip(seasons, features, counts, exposure):
        if season_totals[season]:
            design.append([float(season == key) for key in fitted] + x)
            response.append(count)
            games.append(gp)
    initial = [math.log(season_totals[key] / season_exposure[key]) for key in fitted]
    b = poisson_ridge(design, response, games, initial)
    intercepts = dict(zip(fitted, b[:len(fitted)]))
    return {key: intercepts.get(key) for key in sorted(season_totals)}, b[len(fitted):]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--write", action="store_true")
    ap.add_argument("--model-only", action="store_true", help="leave the local player evidence file alone")
    args = ap.parse_args()
    from nba_gm_data.injury_model import HISTORY_WEIGHT
    from nba_gm_data.app_actions import load_app_canonical
    from nba_gm_data.save import trait_values_by_player
    canonical = load_app_canonical(ROOT)
    players = {p["id"]: p for p in canonical["players"]}
    traits = trait_values_by_player(canonical)

    history = rows("injury_player_history.json")
    seasons = rows("injury_player_seasons.json")
    by_player = defaultdict(list)
    for h in history:
        part = part_of(h)
        if part and h.get("player_id") and h.get("start"):
            by_player[h["player_id"]].append((date.fromisoformat(h["start"][:10]), part, h))

    data = []   # (pid, season, gp, features_raw dict, Counter of part injuries)
    for r in seasons:
        pid = r.get("player_id")
        if not pid or pid not in players or r["season"] < FIRST_SEASON or (r.get("gp") or 0) < 10:
            continue
        p, t = players[pid], traits.get(pid, {})
        birth = p.get("birthdate") or p.get("birth_date")
        if not birth:
            continue
        start = season_start(r["season"])
        age = (start - date.fromisoformat(str(birth)[:10])).days / 365.25
        in_season = Counter(part for d, part, _ in by_player[pid]
                            if r["season"] == _["season"])
        prior = defaultdict(float)
        for d, part, _ in by_player[pid]:
            if d < start:
                prior[part] += math.exp(-((start - d).days / 365.25) / HISTORY_DECAY_YEARS)
        pos = str(p.get("position") or "")
        data.append((pid, r["season"], r["gp"], {
            "age": age, "height": float(p.get("height_inches") or 78), "weight": float(p.get("weight_lbs") or 215),
            "poss_pg": (r.get("poss") or 0) / max(1, r["gp"]),
            "rim_pressure": float(t.get("rim_pressure", 50)), "offensive_rebounding": float(t.get("offensive_rebounding", 50)),
            "stamina": float(t.get("stamina_cardio", 50)), "center": 1.0 if "C" in pos else 0.0,
            "guard": 1.0 if pos.startswith(("PG", "SG", "G")) else 0.0,
        }, in_season, prior))

    raw_cols = ["age", "height", "weight", "poss_pg", "rim_pressure", "offensive_rebounding", "stamina"]
    mu = {c: statistics.fmean(d[3][c] for d in data) for c in raw_cols}
    sd = {c: statistics.pstdev(d[3][c] for d in data) or 1.0 for c in raw_cols}

    def featurize(f, prior_same, prior_other):
        z = {c: (f[c] - mu[c]) / sd[c] for c in raw_cols}
        return [z["age"], z["age"] ** 2, z["height"], z["weight"], z["poss_pg"], z["rim_pressure"],
                z["offensive_rebounding"], z["stamina"], f["center"], f["guard"], prior_same, prior_other]

    model = {"version": "injury_model_v2_2026_11_18", "source": "Basketball Index Injury Tracker (data/research/bbi/tools)",
             "first_season": FIRST_SEASON, "player_seasons": len(data), "games": sum(d[2] for d in data),
             "features": FEATURES, "standardization": {"mean": mu, "sd": sd}, "history_decay_years": HISTORY_DECAY_YEARS,
             "parts": {}, "merge": MERGE,
             "rate_fit": {"season_fixed_effects": True, "anchor_seasons": RATE_ANCHOR_SEASONS}}
    fit_seasons = [row[1] for row in data]
    exposure = [row[2] for row in data]
    for part in [*PARTS, "illness"]:
        features, counts = [], []
        anchor_count = anchor_exposure = 0
        for _, season, gp, raw, in_season, prior in data:
            same = prior.get(part, 0.0)
            other = sum(v for k, v in prior.items() if k != part)
            features.append(featurize(raw, same, other))
            counts.append(in_season.get(part, 0))
            if season in RATE_ANCHOR_SEASONS:
                anchor_count += counts[-1]
                anchor_exposure += gp
        season_intercepts, slopes = fit_season_rates(features, counts, exposure, fit_seasons)
        # Match the recent tracker total using the history terms the engine actually reads. The game
        # discounts previous entries and excludes illness from its rolling injury history.
        weighted_games = 0.0
        for _, season, gp, raw, _, prior in data:
            if season not in RATE_ANCHOR_SEASONS:
                continue
            same = prior.get(part, 0.0) if part != "illness" else 0.0
            other = sum(v for k, v in prior.items() if k not in (part, "illness"))
            x = featurize(raw, HISTORY_WEIGHT * same, HISTORY_WEIGHT * other)
            weighted_games += gp * math.exp(sum(b * value for b, value in zip(slopes, x)))
        model["parts"][part] = {
            "intercept": math.log(anchor_count / weighted_games),
            "coef": dict(zip(FEATURES, slopes)),
            "season_intercepts": season_intercepts,
            "injuries": sum(counts),
            "per_1000_games": round(1000 * sum(counts) / sum(exposure), 3),
        }
        print(f"{part:11s} n={sum(counts):5d} anchor per1000={1000*anchor_count/anchor_exposure:5.2f}  " +
              " ".join(f"{k}={v:+.2f}" for k, v in zip(FEATURES, slopes) if abs(v) >= 0.08))

    # Recovery pools: real absences per part (diagnosis, days, games, surgery), most recent seasons first.
    pools = defaultdict(list)
    for h in history:
        part = part_of(h)
        if part and h["season"] >= FIRST_SEASON and h.get("days"):
            pools[part].append({"label": h.get("label"), "days": int(h["days"]), "games": int(h.get("games") or 0),
                                "surgery": int(h.get("surgery") or 0), "season": h["season"],
                                "censored": int(h.get("censored") or 0)})
    # Injuries: Basketball Index's recorded absences (all players, since RECOVERY_FIRST_YEAR), grouped by body part,
    # labeled with the specific diagnosis where one exists, weighted with its 6-year half-life. An absence without a
    # logged return lasted at least its recorded days: it takes the median of longer returned cases for that part.
    observations = {o["observation_id"]: o for o in rows("injury_observations.json")}
    time_out = rows("injury_time_out.json")
    diagnosis = {}
    for t in time_out:
        if t["level"] == "specific":
            for oid in t["observation_ids"]:
                diagnosis.setdefault(oid, t["bucket"])
    bbi_pools = defaultdict(list)
    for t in time_out:
        if t["level"] != "body_part":
            continue
        part = MERGE.get(t["bucket"], t["bucket"])
        if part not in PARTS:
            continue
        for oid in t["observation_ids"]:
            o = observations.get(oid)
            if o and o.get("days") and int(o.get("start_year") or 0) >= RECOVERY_FIRST_YEAR:
                bbi_pools[part].append(o | {"label": diagnosis.get(oid) or f"{part} injury"})
    recovery = {}
    for part, obs in bbi_pools.items():
        returned = sorted(o["days"] for o in obs if o["return_logged"])
        entries = []
        for o in obs:
            days = int(o["days"])
            if not o["return_logged"]:
                longer = [d for d in returned if d >= days]
                days = int(statistics.median(longer)) if longer else days
            entries.append({"days": days, "label": o["label"], "w": round(0.5 ** (float(o["recency_years"]) / 6.0), 5),
                            "censored": int(not o["return_logged"])})
        recovery[part] = entries
    recovery["illness"] = [{"days": r["days"], "label": r["label"] or "illness", "w": 1.0, "censored": r["censored"]}
                           for r in pools.get("illness", [])]
    model["recovery_pools"] = recovery
    for part in PARTS:
        days = sorted(e["days"] for e in recovery.get(part, []))
        if days:
            q = statistics.quantiles(days, n=10)
            print(f"  recovery {part:11s} n={len(days):5d} median={q[4]:5.1f} p90={q[8]:6.1f}")
    model["recurrence_reference"] = {r["bucket"]: r["risk_ratio"] for r in rows("injury_recurrence.json")
                                     if r.get("level") == "body_part" and r.get("risk_ratio")}
    long_term = [r for r in rows("injury_long_term.json") if (r.get("d_rapm_1y_shrunk_ci") or [0, 0])[1] < 0]
    model["lasting_effects"] = [{k: r.get(k) for k in ("level", "bucket", "region", "n_treated", "d_rapm_1y_shrunk",
                                                       "d_rapm_1y_shrunk_ci", "d_rapm_2y", "d_poss_1y_pct")}
                                for r in long_term]
    model["return_ramp"] = rows("injury_short_term.json")
    # Real players' recent injuries (start date, part, days) so a new save starts with their actual history: the same-part
    # and other-part history terms decay over ~1.5 years, so five seasons cover everything that still matters.
    recent = defaultdict(list)
    for h in history:
        part = part_of(h)
        if part and part != "illness" and h.get("player_id") and h.get("start") and h["season"] >= "2021-22":
            recent[h["player_id"]].append([h["start"][:10], part, int(h.get("days") or 0), h.get("label")])
    model["player_history"] = {pid: sorted(v) for pid, v in sorted(recent.items())}
    # Basketball Index's 2026-27 per-player injury forecast (games missed to injury per 82): the market's view of real
    # players' current proneness, blended into the AI's injury-risk score while it is fresh.
    model["player_forecast_2026_27"] = {r["player_id"]: r["missed_to_injury"] for r in rows("injury_player_projections.json")
                                        if r.get("player_id") and r.get("missed_to_injury") is not None}
    # Real players' recovery speed vs the league for the same injury (Basketball Index, shrunk percent; negative = quicker).
    model["player_recovery_pct"] = {r["player_id"]: r["recovery"]["pct"] for r in rows("injury_players.json")
                                    if r.get("player_id") and (r.get("recovery") or {}).get("pct") is not None
                                    and (r["recovery"].get("trusted") or 0)}
    print("lasting effects (CI below zero):", [(r["level"], r["bucket"], r["d_rapm_1y_shrunk"]) for r in model["lasting_effects"]])
    # Committed model = derived numbers only (user decision 2026-11-18: raw Basketball Index data stays off GitHub).
    # Recovery pools become weighted duration quantiles plus diagnosis shares by duration band; per-player evidence
    # (history, forecasts, recovery speed) goes to a separate git-ignored file the engine merges when present.
    summary = {}
    for part, pool in model.pop("recovery_pools").items():
        ordered = sorted(pool, key=lambda r: r["days"])
        total = sum(float(r.get("w") or 1.0) for r in ordered)
        quantiles, cumulative, idx = [], 0.0, 0
        for k in range(41):
            target = total * k / 40.0
            while idx < len(ordered) - 1 and cumulative + float(ordered[idx].get("w") or 1.0) < target:
                cumulative += float(ordered[idx].get("w") or 1.0)
                idx += 1
            quantiles.append(int(ordered[idx]["days"]))
        bands = []
        for limit in (3, 7, 14, 30, 60, 120, 100000):
            shares = Counter()
            for r in ordered:
                if (bands[-1][0] if bands else 0) < r["days"] <= limit:
                    shares[r["label"]] += float(r.get("w") or 1.0)
            top = shares.most_common(12)
            band_total = sum(v for _, v in top) or 1.0
            bands.append([limit, {label: round(v / band_total, 4) for label, v in top}])
        summary[part] = {"quantiles": quantiles, "labels_by_days": bands}
    model["recovery_summary"] = summary
    evidence = {key: model.pop(key) for key in ("player_history", "player_forecast_2026_27", "player_recovery_pct")}
    evidence["version"] = model["version"]
    if args.write:
        OUT.write_text(json.dumps(model, separators=(",", ":")) + "\n")
        print("wrote", OUT, f"{OUT.stat().st_size/1e6:.2f} MB")
        if not args.model_only:
            EVIDENCE_OUT.write_text(json.dumps(evidence, separators=(",", ":")) + "\n")
            print("wrote local-only", EVIDENCE_OUT.name, f"{EVIDENCE_OUT.stat().st_size/1e6:.2f} MB")


if __name__ == "__main__":
    main()
