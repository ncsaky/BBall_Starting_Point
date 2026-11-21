"""Shooting and finishing spot-check (Stage 2): the physics kernels vs real 2025-26 shooting vs today's engine.

What is compared (per rotation player, weighted by attempts):
- the experimental kernels (offense_response.shooting_response / finishing_response) evaluated on every player's
  bridged league profile (stage2.league_inputs), at the kernel's own reference defense (perimeter pressure .35,
  defender arrival .65 s; finishes uncontested: the interior-defense response is a separate piece);
- real 2025-26 make rates by shot type from Basketball Index's shooting tables (data/research/bbi, Leaderboards
  "Values": Rim FG%, Short/Long Mid Range FG%, Corner/ATB 3PT FG%, C&S and pull-up 3PT FG%, midrange pull-up FG%,
  floater FG%) and the box score (ESPN season totals, data/research/player_career_stats.json);
- today's engine: each player's 3P%, 2P% and FT% from the engine's own player features (sim.player_feature_vector;
  today's engine does not resolve zones).

Shot context the kernels are given comes from the player's REAL shot selection (that is what a make-rate check
conditions on): his corner/above-the-break split, his pull-up share of threes and midrange shots, and his dunk share of
rim attempts (Basketball-Reference). Ratings are never adjusted here.
"""
from __future__ import annotations

import json
import math
import time
from dataclasses import replace
from pathlib import Path
from typing import Any, Callable

from ..offense_response import OffenseCoefficients, OffensiveProfile, finishing_response, free_throw_response, shooting_response
from .league_inputs import compile_league, interior_profile, offense_profile, player_directory

SEASON = "2025-26"
MIN_MINUTES = 500  # Basketball Index's own pool cut (bbi_evidence.MIN_POOL_MINUTES)
LEAGUE_PACE = 102.0  # possessions per 48 minutes, data/calibration/nba_2025_26_targets.json league pace
CORNER_M, ATB_M = 6.7, 7.5  # corner three; typical above-the-break attempt (~24.6 ft)
SHORT_JUMPER_M, LONG_MID_M, MID_PULLUP_M = 4.3, 5.5, 5.0  # kernel's short_paint jumper; 14 ft-arc; midrange pull-up
REFERENCE_PRESSURE, REFERENCE_ARRIVAL = .35, .65  # the kernel's own declared reference contest
KERNEL_RIM_MIX = {"layup": .50, "contact_layup": .25, "dunk": .125, "lob": .125}  # CombinedOffense default, floater moved out

BBI = {
    "rim": ("Rim FG%", "Rim Shot Attempts Per 75 Possessions"),
    "mid_all": (None, "Midrange FGA Per 75"),
    "mid_made": (None, "Midrange FGM Per 75"),
    "short_mid": ("Short Mid Range FG%", None),
    "long_mid": ("Long Mid Range FG%", None),
    "three": ("3PT %", "3PT FGA Per 75 Possessions"),
    "corner3": ("Corner 3PT FG%", None),
    "atb3": ("ATB 3PT FG%", None),
    "corner_ratio": (None, "Corner 3 to ATB Ratio"),
    "cs3": ("C&S 3PT FG%", None),
    "pu3": ("3PT Pull Up FG%", "3PT Pull Up FGA Per 75"),
    "mid_pu": ("Midrange Pull Up FG%", "Midrange Pull Up FGA Per 75"),
    "floater": ("Floater FG%", None),
}
SHOT_TYPES = ("rim", "short_mid", "long_mid", "corner3", "atb3", "cs3", "pu3", "mid_pu", "floater", "fg2", "fg3", "ft", "efg")
LABELS = {"rim": "Rim (under 4 ft)", "short_mid": "Short mid (4-14 ft)", "long_mid": "Long mid (14 ft to arc)",
          "corner3": "Corner 3", "atb3": "Above-the-break 3", "cs3": "Catch-and-shoot 3", "pu3": "Pull-up 3",
          "mid_pu": "Midrange pull-up", "floater": "Floater", "fg2": "All twos (box score)", "fg3": "All threes (box score)",
          "ft": "Free throws (box score)", "efg": "Effective FG% (box score)"}


# ---- real data ---------------------------------------------------------------------------------------------------
def _bbi_table(root: Path) -> dict:
    from ..bbi_evidence import _recent_values
    return _recent_values(root)


def real_shooting(root: str | Path, season: str = SEASON, min_minutes: float = MIN_MINUTES) -> dict[str, dict]:
    """player id -> real shot-type rates and attempt estimates for 2025-26 rotation players."""
    root = Path(root)
    table = _bbi_table(root)
    directory = player_directory(root)

    def value(metric, pid):
        row = table.get((season, metric), {}).get(pid) if metric else None
        return row

    careers = json.loads((root / "data/research/player_career_stats.json").read_text())["players"]
    bref = _bref_dunk_shares(root)
    compiled = compile_league(root)["players"]
    out = {}
    for pid in directory:
        rim = value("Rim FG%", pid)
        if rim is None or rim[1] < min_minutes:
            continue
        minutes = rim[1]
        possessions = minutes * LEAGUE_PACE / 48.0

        def attempts(metric):
            row = value(metric, pid)
            return max(0.0, row[0]) * possessions / 75.0 if row else 0.0

        def pct(metric):
            row = value(metric, pid)
            return row[0] / 100.0 if row else None

        rim_att = attempts("Rim Shot Attempts Per 75 Possessions")
        mid_att = attempts("Midrange FGA Per 75")
        mid_made = attempts("Midrange FGM Per 75")
        three_att = attempts("3PT FGA Per 75 Possessions")
        ratio_row = value("Corner 3 to ATB Ratio", pid)
        ratio = max(0.0, ratio_row[0]) if ratio_row else 0.0
        corner_att = three_att * ratio / (1 + ratio)
        pu3_att = min(three_att, attempts("3PT Pull Up FGA Per 75"))
        mid_pu_att = min(mid_att, attempts("Midrange Pull Up FGA Per 75"))
        short_pct, long_pct = pct("Short Mid Range FG%"), pct("Long Mid Range FG%")
        regions = (compiled.get(pid) or {}).get("shot_regions") or {}
        observed_split = (regions["short_paint"] / (regions["short_paint"] + regions["midrange"])
                          if regions.get("short_paint", 0) + regions.get("midrange", 0) > 0 else .5)
        short_share = _short_share(mid_att, mid_made, short_pct, long_pct, observed_split)
        zones = {
            "rim": (pct("Rim FG%"), rim_att),
            "short_mid": (short_pct, mid_att * short_share),
            "long_mid": (long_pct, mid_att * (1 - short_share)),
            "corner3": (pct("Corner 3PT FG%"), corner_att),
            "atb3": (pct("ATB 3PT FG%"), three_att - corner_att),
            "cs3": (pct("C&S 3PT FG%"), three_att - pu3_att),
            "pu3": (pct("3PT Pull Up FG%"), pu3_att),
            "mid_pu": (pct("Midrange Pull Up FG%"), mid_pu_att),
            # No floater attempt count in the tables: weighted by short-mid attempts (floaters are short-mid shots).
            "floater": (pct("Floater FG%"), mid_att * short_share),
        }
        espn = directory[pid].get("espn_player_id")
        box = _box(careers.get(espn or "", {}), season)
        out[pid] = {"name": directory[pid]["name"], "group": directory[pid]["group"], "minutes": minutes,
                    "zones": {k: v for k, v in zones.items() if v[0] is not None and v[1] >= 1.0},
                    "box": box,
                    "context": {"corner_share": corner_att / three_att if three_att else 0.0,
                                "pullup_share_three": pu3_att / three_att if three_att else 0.0,
                                "pullup_share_mid": mid_pu_att / mid_att if mid_att else 0.0,
                                "dunk_share_rim": bref.get(espn or "", bref.get("__league__")),
                                "short_share_mid": short_share}}
    return out


def _short_share(total: float, made: float, short_pct: float | None, long_pct: float | None, fallback: float) -> float:
    """Short-mid share of midrange attempts (the tables give only the midrange total). Solved from
    made = s*short% + (1-s)*long% when that is well conditioned; otherwise the player's observed attempt-location split
    (his T02 input: short_paint vs midrange, built from observed attempt locations). A zone shown at exactly 0% next
    to a non-zero other zone is read as no attempts there (the tables print 0 for an empty zone)."""
    if short_pct is not None and long_pct is not None:
        if long_pct == 0 and short_pct > 0:
            return 1.0
        if short_pct == 0 and long_pct > 0:
            return 0.0
    if total and made and short_pct is not None and long_pct is not None and abs(short_pct - long_pct) >= .05:
        share = (made / total - long_pct) / (short_pct - long_pct)
        if -.05 <= share <= 1.05:
            return min(1.0, max(0.0, share))
    return fallback


def _box(profile: dict, season: str) -> dict:
    rows = [r for r in profile.get("seasons", []) if r.get("season") == season]
    if not rows:
        return {}
    r = rows[0]
    fga, fgm, fg3a, fg3m, fta, ftm = (float(r.get(k) or 0) for k in ("fga", "fgm", "fg3a", "fg3m", "fta", "ftm"))
    out = {}
    if fga - fg3a > 0:
        out["fg2"] = ((fgm - fg3m) / (fga - fg3a), fga - fg3a)
    if fg3a > 0:
        out["fg3"] = (fg3m / fg3a, fg3a)
    if fta > 0:
        out["ft"] = (ftm / fta, fta)
    if fga > 0:
        out["efg"] = ((fgm + .5 * fg3m) / fga, fga)
    return out


def _bref_dunk_shares(root: Path) -> dict[str, float]:
    """espn id -> dunk share of attempts within 3 ft, 2025-26 (Basketball-Reference); '__league__' -> league share."""
    path = root / "data/research/bref_shooting_2024_2026.json"
    if not path.exists():
        return {"__league__": .30}
    data = json.loads(path.read_text())["players"]
    by_name = {}
    from ..input_estimator import _normalize
    for key, row in data.items():
        season = (row.get("seasons") or {}).get(SEASON) or {}
        close, dunk, fga = season.get("pct_fga_00_03"), season.get("pct_fga_dunk"), season.get("fga")
        if close and dunk is not None and fga:
            by_name[_normalize(row.get("name") or "")] = (dunk / close, fga * close)
    directory = player_directory(root)
    out = {}
    num = den = 0.0
    for pid, entry in directory.items():
        hit = by_name.get(_normalize(entry.get("name") or ""))
        if hit and entry.get("espn_player_id"):
            out[entry["espn_player_id"]] = min(1.0, hit[0])
            num += hit[0] * hit[1]
            den += hit[1]
    out["__league__"] = num / den if den else .30
    return out


# ---- kernel predictions --------------------------------------------------------------------------------------
# A "conversion" is the set of coefficients each shot family is evaluated with. The kernel as built uses ONE set of
# OffenseCoefficients for every jumper and every layup/floater, and a fixed dunk line (.50 + .45 x dunk skill).
# The per-family prototype (refit_families) gives each family its own floor and slope; everything else in the kernel
# (skill selection, balance, range, release timing, contest) is unchanged, and no player input moves.
JUMPER_FAMILIES = ("catch3", "pull3", "catch2", "pull2")
FINISH_FAMILIES = ("layup", "floater")
KERNEL_DUNK = (.50, .45)


def kernel_conversion(coefficients: OffenseCoefficients = OffenseCoefficients()) -> dict[str, Any]:
    return {**{f: coefficients for f in JUMPER_FAMILIES + FINISH_FAMILIES}, "dunk": KERNEL_DUNK}


def _with(p: OffensiveProfile, coefficients: OffenseCoefficients) -> OffensiveProfile:
    return p if p.coefficients is coefficients else replace(p, coefficients=coefficients)


def _jumper(p: OffensiveProfile, distance: float, pullup_share: float, conv: dict | None = None) -> float:
    three = distance >= 6.7
    catch_p = _with(p, conv["catch3" if three else "catch2"]) if conv else p
    pull_p = _with(p, conv["pull3" if three else "pull2"]) if conv else p
    catch = shooting_response(catch_p, mode="catch", distance_m=distance, pressure=REFERENCE_PRESSURE,
                              defender_arrival_s=REFERENCE_ARRIVAL)["make_probability"] if pullup_share < 1 else 0.0
    pull = shooting_response(pull_p, mode="pull_up", distance_m=distance, pressure=REFERENCE_PRESSURE,
                             defender_arrival_s=REFERENCE_ARRIVAL)["make_probability"] if pullup_share > 0 else 0.0
    return (1 - pullup_share) * catch + pullup_share * pull


def _finish(p: OffensiveProfile, kind: str, conv: dict | None = None) -> float:
    family = "floater" if kind == "floater" else "layup"
    q = _with(p, conv[family]) if conv else p
    result = finishing_response(q, kind, contact=1.0 if kind == "contact_layup" else 0.0, delivery_quality=.95)
    if conv and result["finish"] in ("dunk", "lob") and conv["dunk"] != KERNEL_DUNK:
        a, b = conv["dunk"]
        value = a + b * p.skill(12)
        if result["finish"] == "lob":
            value *= .60 + .40 * p.skill(13)
        return min(.98, max(.02, value))
    return result["make_probability"]


def kernel_rates(p: OffensiveProfile, context: dict, *, rim_mix: str = "real", conv: dict | None = None) -> dict[str, float]:
    """The kernel's make probability for each shot type, given the player's real shot context."""
    dunk_share = context.get("dunk_share_rim")
    layup_mix = (2 / 3) * _finish(p, "layup", conv) + (1 / 3) * _finish(p, "contact_layup", conv)
    if rim_mix == "kernel" or dunk_share is None:
        rim = sum(w * _finish(p, k, conv) for k, w in KERNEL_RIM_MIX.items())
    else:
        rim = dunk_share * _finish(p, "dunk", conv) + (1 - dunk_share) * layup_mix
    pu_mid = context.get("pullup_share_mid", p.modes[1])
    pu3_all = context.get("pullup_share_three", p.modes[1])
    corner = context.get("corner_share", 0.0)
    atb_pullup = min(1.0, pu3_all / max(1e-9, 1 - corner)) if corner < 1 else 0.0
    floater = _finish(p, "floater", conv)
    corner3 = _jumper(p, CORNER_M, 0.0, conv)
    atb3 = _jumper(p, ATB_M, atb_pullup, conv)
    catch_atb = _jumper(p, ATB_M, 0.0, conv)
    cs_share_corner = min(1.0, corner / max(1e-9, 1 - pu3_all)) if pu3_all < 1 else 0.0
    cs3 = cs_share_corner * corner3 + (1 - cs_share_corner) * catch_atb
    return {
        "rim": rim,
        "short_mid": .5 * floater + .5 * _jumper(p, SHORT_JUMPER_M, pu_mid, conv),
        "long_mid": _jumper(p, LONG_MID_M, pu_mid, conv),
        "corner3": corner3,
        "atb3": atb3,
        "cs3": cs3,
        "pu3": _jumper(p, ATB_M, 1.0, conv),
        "mid_pu": _jumper(p, MID_PULLUP_M, 1.0, conv),
        "floater": floater,
        "ft": free_throw_response(p),
    }


def box_rates_from_zones(rates: dict[str, float], zones: dict[str, tuple[float, float]]) -> dict[str, float]:
    """2P%, 3P% and eFG% on the player's real attempt mix (zone attempts as weights)."""
    def mix(keys):
        n = sum(zones[k][1] for k in keys if k in zones)
        return sum(rates[k] * zones[k][1] for k in keys if k in zones) / n if n else None, n
    fg2, n2 = mix(("rim", "short_mid", "long_mid"))
    fg3, n3 = mix(("corner3", "atb3"))
    out = {}
    if fg2 is not None:
        out["fg2"] = fg2
    if fg3 is not None:
        out["fg3"] = fg3
    if fg2 is not None or fg3 is not None:
        out["efg"] = ((fg2 or 0) * n2 + 1.5 * (fg3 or 0) * n3) / (n2 + n3)
    return out


# ---- today's engine -------------------------------------------------------------------------------------------
def today_engine_rates(root: str | Path, player_ids) -> dict[str, dict[str, float]]:
    from ..sim import load_sim_context, player_feature_vector
    context = load_sim_context(root)
    canonical = context["canonical"]
    players = {p["id"]: p for p in canonical["players"]}
    out = {}
    for pid in player_ids:
        player = players.get(pid)
        if player is None:
            continue
        f = player_feature_vector(canonical, player).features
        if f.get("three_pct") is None:
            continue
        out[pid] = {"fg3": float(f["three_pct"]), "fg2": float(f["two_pct"]), "ft": float(f["ft_pct"])}
    return out


# ---- scoring --------------------------------------------------------------------------------------------------
def weighted_errors(pairs: list[tuple[float, float, float]]) -> dict[str, float] | None:
    """pairs of (predicted, real, attempts). Bias, MAE, error beyond sampling noise, correlation."""
    pairs = [(p, r, n) for p, r, n in pairs if n > 0 and p is not None and r is not None]
    if len(pairs) < 3:
        return None
    w = sum(n for _, _, n in pairs)
    bias = sum(n * (p - r) for p, r, n in pairs) / w
    mae = sum(n * abs(p - r) for p, r, n in pairs) / w
    mse = sum(n * (p - r) ** 2 for p, r, n in pairs) / w
    noise = sum(n * (r * (1 - r) / n) for p, r, n in pairs) / w  # sampling variance of the real rate
    mp = sum(n * p for p, _, n in pairs) / w
    mr = sum(n * r for _, r, n in pairs) / w
    cov = sum(n * (p - mp) * (r - mr) for p, r, n in pairs) / w
    vp = sum(n * (p - mp) ** 2 for p, _, n in pairs) / w
    vr = sum(n * (r - mr) ** 2 for _, r, n in pairs) / w
    return {"players": len(pairs), "attempts": round(w), "real": round(mr, 4), "predicted": round(mp, 4),
            "bias": round(bias, 4), "mae": round(mae, 4), "rmse": round(math.sqrt(mse), 4),
            "excess_rmse": round(math.sqrt(max(0.0, mse - noise)), 4), "noise_rmse": round(math.sqrt(noise), 4),
            "corr": round(cov / math.sqrt(vp * vr), 3) if vp > 0 and vr > 0 else None,
            "pred_sd": round(math.sqrt(vp), 4), "real_sd": round(math.sqrt(vr), 4)}


def kernel_table(real: dict, profiles: dict[str, OffensiveProfile], *, rim_mix: str = "real",
                 conv: dict | None = None) -> dict[str, dict]:
    predictions = {}
    for pid, row in real.items():
        p = profiles.get(pid)
        if p is None:
            continue
        rates = kernel_rates(p, row["context"], rim_mix=rim_mix, conv=conv)
        rates.update(box_rates_from_zones(rates, row["zones"]))
        predictions[pid] = rates
    return predictions


def score(real: dict, predictions: dict[str, dict], shot_types=SHOT_TYPES) -> dict[str, dict]:
    out = {}
    for shot in shot_types:
        pairs = []
        for pid, rates in predictions.items():
            row = real.get(pid)
            if row is None or shot not in rates:
                continue
            obs = row["box"].get(shot) if shot in ("fg2", "fg3", "ft", "efg") else row["zones"].get(shot)
            if obs:
                pairs.append((rates[shot], obs[0], obs[1]))
        result = weighted_errors(pairs)
        if result:
            out[shot] = result
    return out


def player_points_misses(real: dict, predictions: dict[str, dict], top: int = 20) -> dict[str, list]:
    """Season field-goal points the kernel over/under-predicts per player, on his real zone attempts."""
    rows = []
    for pid, rates in predictions.items():
        zones = real[pid]["zones"]
        diff = 0.0
        detail = {}
        for zone, value in (("rim", 2), ("short_mid", 2), ("long_mid", 2), ("corner3", 3), ("atb3", 3)):
            if zone in zones:
                pct, n = zones[zone]
                d = (rates[zone] - pct) * n * value
                diff += d
                detail[zone] = (round(rates[zone], 3), round(pct, 3), round(n))
        fga = sum(zones[z][1] for z in ("rim", "short_mid", "long_mid", "corner3", "atb3") if z in zones)
        rows.append({"player_id": pid, "name": real[pid]["name"], "points": round(diff, 1), "fga": round(fga),
                     "per100": round(100 * diff / fga, 1) if fga else None, "zones": detail})
    rows.sort(key=lambda r: r["points"])
    return {"over": list(reversed(rows[-top:])), "under": rows[:top]}


# ---- league level --------------------------------------------------------------------------------------------
def league_mix(real: dict, compiled: dict, predictions: dict[str, dict]) -> dict[str, Any]:
    """Shot mix (the inputs' T02 regions vs real attempts) and efficiency, rotation players, real FGA weights."""
    real_mix = {"rim": 0.0, "short_mid": 0.0, "long_mid": 0.0, "three": 0.0}
    input_mix = dict(real_mix)
    made_real = made_kernel = fga_total = three_made_real = three_made_kernel = 0.0
    for pid, row in real.items():
        z = row["zones"]
        fga = sum(z[k][1] for k in ("rim", "short_mid", "long_mid", "corner3", "atb3") if k in z)
        if not fga:
            continue
        real_mix["rim"] += z.get("rim", (0, 0))[1]
        real_mix["short_mid"] += z.get("short_mid", (0, 0))[1]
        real_mix["long_mid"] += z.get("long_mid", (0, 0))[1]
        real_mix["three"] += z.get("corner3", (0, 0))[1] + z.get("atb3", (0, 0))[1]
        regions = (compiled["players"].get(pid) or {}).get("shot_regions")
        if regions:
            input_mix["rim"] += fga * regions["rim"]
            input_mix["short_mid"] += fga * regions["short_paint"]
            input_mix["long_mid"] += fga * regions["midrange"]
            input_mix["three"] += fga * regions["three"]
        fga_total += fga
        rates = predictions.get(pid)
        for k in ("rim", "short_mid", "long_mid", "corner3", "atb3"):
            if k in z:
                pct, n = z[k]
                made_real += pct * n
                if rates:
                    made_kernel += rates[k] * n
                if k in ("corner3", "atb3"):
                    three_made_real += pct * n
                    if rates:
                        three_made_kernel += rates[k] * n
    total_real = sum(real_mix.values())
    total_input = sum(input_mix.values())
    return {"fga": round(fga_total),
            "real_mix": {k: round(v / total_real, 4) for k, v in real_mix.items()},
            "input_mix": {k: round(v / total_input, 4) for k, v in input_mix.items()},
            "efg_real": round((made_real + .5 * three_made_real) / fga_total, 4),
            "efg_kernel": round((made_kernel + .5 * three_made_kernel) / fga_total, 4)}


# ---- timing --------------------------------------------------------------------------------------------------
def time_kernel(profiles: list[OffensiveProfile], interior: list | None = None, repeats: int = 3) -> dict[str, float]:
    """Microseconds per call of each kernel, best of `repeats` passes over the given profiles."""
    from ..interior_defense import ArrivalContext, interior_response
    from ..shot_geometry import ShotGeometry
    calls: dict[str, tuple[Callable[[Any], Any], list]] = {
        "shooting_response (one jumper)": (lambda p: shooting_response(p, mode="catch", distance_m=ATB_M), profiles),
        "finishing_response (one finish)": (lambda p: finishing_response(p, "layup"), profiles),
        "one shot resolved (zone pick + make probability)": (lambda p: _resolve_one(p), profiles),
    }
    if interior:
        context = ArrivalContext(distance_m=1.5, window_s=.8)
        geometry = ShotGeometry(0.3, 0.8, 300.0, 0.0, 1.0, approach_angle_deg=90.0, attack_time_s=.6, preparation_s=.25, contact=0)
        calls["interior_response, rim contest (no geometry)"] = (
            lambda d: interior_response(d, context, zone="rim", diagnostics=False), interior)
        calls["interior_response, rim contest with shot geometry"] = (
            lambda d: interior_response(d, context, zone="rim", geometry=geometry, diagnostics=False), interior)
    out = {}
    for name, (fn, items) in calls.items():
        best = float("inf")
        for _ in range(repeats):
            start = time.perf_counter()
            for item in items:
                fn(item)
            best = min(best, (time.perf_counter() - start) / len(items))
        out[name] = round(best * 1e6, 2)
    return out


def _resolve_one(p: OffensiveProfile) -> float:
    rim, mid, three = p.locations
    if rim >= mid and rim >= three:
        return _finish(p, "layup")
    if three >= mid:
        return shooting_response(p, mode="catch", distance_m=ATB_M)["make_probability"]
    return shooting_response(p, mode="pull_up", distance_m=LONG_MID_M)["make_probability"]


# ---- kernel-conversion refit (prototype; ratings untouched) ---------------------------------------------------
def _split(pid: str) -> int:
    import hashlib
    return int(hashlib.sha256(pid.encode()).hexdigest(), 16) % 2


FIT_ZONES = ("rim", "short_mid", "long_mid", "corner3", "atb3", "cs3", "pu3", "mid_pu", "floater")


def _params(conv: dict) -> dict[str, float]:
    out = {}
    for f in JUMPER_FAMILIES:
        out[f"{f}.floor"] = conv[f].shooting_floor
        out[f"{f}.span"] = conv[f].shooting_skill_span
    out["range_penalty_per_m"] = conv["catch3"].range_penalty_per_m
    for f in FINISH_FAMILIES:
        out[f"{f}.floor"] = conv[f].finish_floor
        out[f"{f}.span"] = conv[f].finish_skill_span
    out["contact_penalty"] = conv["layup"].contact_penalty
    out["dunk.floor"], out["dunk.span"] = conv["dunk"]
    return out


def _conversion(params: dict[str, float], base: OffenseCoefficients = OffenseCoefficients()) -> dict:
    conv = {}
    for f in JUMPER_FAMILIES:
        conv[f] = replace(base, shooting_floor=params[f"{f}.floor"], shooting_skill_span=params[f"{f}.span"],
                          range_penalty_per_m=params["range_penalty_per_m"])
    for f in FINISH_FAMILIES:
        conv[f] = replace(base, finish_floor=params[f"{f}.floor"], finish_skill_span=params[f"{f}.span"],
                          contact_penalty=params["contact_penalty"])
    conv["dunk"] = (params["dunk.floor"], params["dunk.span"])
    return conv


def refit_families(real: dict, compiled: dict, train: int = 0) -> tuple[dict, dict, dict]:
    """Per-family conversion (each jumper family and layup/floater/dunk its own floor and slope; shared range and
    contact costs) fitted to real make rates on half the players (fixed hash), attempt-weighted least squares by
    coordinate search. Player inputs are never touched; the other half is the held-out check."""
    profiles = {pid: offense_profile(compiled["players"][pid], OffenseCoefficients(), pid)
                for pid in real if _split(pid) == train and pid in compiled["players"] and compiled["players"][pid]["offense"]}

    def loss(params):
        try:
            conv = _conversion(params)
        except ValueError:
            return float("inf")
        if params["dunk.floor"] < 0 or params["dunk.floor"] + params["dunk.span"] > 1:
            return float("inf")
        total = w = 0.0
        for pid, p in profiles.items():
            rates = kernel_rates(p, real[pid]["context"], conv=conv)
            for z in FIT_ZONES:
                obs = real[pid]["zones"].get(z)
                if obs:
                    total += obs[1] * (rates[z] - obs[0]) ** 2
                    w += obs[1]
        return total / w

    params = _params(kernel_conversion())
    start_loss = current = loss(params)
    step = .04
    for _ in range(80):
        improved = False
        for key in list(params):
            for direction in (1, -1):
                trial = dict(params)
                trial[key] = params[key] + direction * step
                if trial[key] < 0:
                    continue
                value = loss(trial)
                if value < current - 1e-10:
                    params, current, improved = trial, value, True
        if not improved:
            step /= 2
            if step < 1e-3:
                break
    return _conversion(params), {k: round(v, 4) for k, v in params.items()}, {"train_loss_start": round(start_loss, 6),
                                                                              "train_loss_end": round(current, 6)}


def held_out(real: dict, predictions: dict[str, dict], train: int = 0) -> dict:
    return {pid: rates for pid, rates in predictions.items() if _split(pid) != train}


def run(root: str | Path) -> dict[str, Any]:
    """The whole spot-check (light: no game simulation). Returns tables for the report."""
    root = Path(root)
    compiled = compile_league(root)
    real = real_shooting(root)
    profiles = {pid: offense_profile(rec, OffenseCoefficients(), pid) for pid, rec in compiled["players"].items() if rec["offense"]}
    kernel = kernel_table(real, profiles)
    kernel_default_rim = kernel_table(real, profiles, rim_mix="kernel")
    today = today_engine_rates(root, list(real))
    today_scored = score(real, today, ("fg2", "fg3", "ft"))
    conv, params, fit = refit_families(real, compiled)
    refit = kernel_table(real, profiles, conv=conv)
    return {
        "players": len(real),
        "kernel": score(real, kernel),
        "kernel_kernel_rim_mix": score(real, kernel_default_rim, ("rim", "fg2", "efg")),
        "today": today_scored,
        "kernel_held_out": score(real, held_out(real, kernel)),
        "refit_held_out": score(real, held_out(real, refit)),
        "today_held_out": score(real, held_out(real, today), ("fg2", "fg3", "ft")),
        "refit_coefficients": params,
        "kernel_coefficients": _params(kernel_conversion()),
        "refit_history": fit,
        "refit_all": score(real, refit),
        "misses": player_points_misses(real, kernel),
        "league": league_mix(real, compiled, kernel),
        "league_refit": league_mix(real, compiled, refit),
        "misses_refit": player_points_misses(real, refit),
        "timing_us": time_kernel(list(profiles.values()),
                                 [interior_profile(rec) for rec in compiled["players"].values() if rec["interior"]]),
    }
