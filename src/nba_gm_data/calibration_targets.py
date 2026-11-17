"""Real-NBA calibration targets and a comparison tool for game engines.

Targets are built from local 2025-26 data by ``scripts/build_calibration_targets.py``
and written to ``data/calibration/nba_2025_26_targets.json``.

Possession estimate (used everywhere, for real data and simulated data alike):
    possessions = FGA + 0.44 * FTA - ORB + TOV

Acceptance band for a league metric = target +/- BAND_STD_MULT * team std,
where the team std is the spread of the metric across the 30 real teams.
"""
from __future__ import annotations

import json
import math
import statistics
from collections import defaultdict
from pathlib import Path
from typing import Any, Iterable

BAND_STD_MULT = 1.5
FT_POSSESSION_WEIGHT = 0.44

LEAGUE_METRICS = [
    "pace", "off_rating", "points_per_game", "fga_per100", "fg3a_per100", "fta_per100",
    "fg3a_rate", "ft_rate", "efg_pct", "ts_pct", "tov_per100", "tov_pct", "orb_pct",
    "ast_per100", "ast_rate", "stl_per100", "blk_per100", "pf_per100",
]
PLAYER_COUNT_STATS = ["points", "fga", "fg3a", "fta", "rebounds", "assists", "turnovers", "steals", "blocks"]
PLAYER_COMPARE_METRICS = [f"{s}_per36" for s in PLAYER_COUNT_STATS] + ["ts_pct"]


def _div(a: float, b: float) -> float | None:
    return a / b if b else None


def league_metrics_from_totals(t: dict[str, float]) -> dict[str, float | None]:
    """Compute every league metric from raw totals for a team (or a group of teams).

    Required keys: games, minutes (team minutes, 240 per regulation game), points, fga, fgm, fg3a,
    fta, orb, tov, ast, stl, blk. Optional: pf, opp_drb (for ORB%).
    """
    poss = t["fga"] + FT_POSSESSION_WEIGHT * t["fta"] - t["orb"] + t["tov"]
    game_minutes = t["minutes"] / 5.0 if t.get("minutes") else 48.0 * t["games"]
    shooting_den = t["fga"] + FT_POSSESSION_WEIGHT * t["fta"]
    out: dict[str, float | None] = {
        "pace": _div(poss * 48.0, game_minutes) if game_minutes else None,
        "off_rating": _div(100.0 * t["points"], poss),
        "points_per_game": _div(t["points"], t["games"]),
        "fga_per100": _div(100.0 * t["fga"], poss),
        "fg3a_per100": _div(100.0 * t["fg3a"], poss),
        "fta_per100": _div(100.0 * t["fta"], poss),
        "fg3a_rate": _div(t["fg3a"], t["fga"]),
        "ft_rate": _div(t["fta"], t["fga"]),
        "efg_pct": _div(t["fgm"] + 0.5 * t["fg3m"], t["fga"]) if "fg3m" in t else None,
        "ts_pct": _div(t["points"], 2.0 * shooting_den),
        "tov_per100": _div(100.0 * t["tov"], poss),
        "tov_pct": _div(100.0 * t["tov"], shooting_den + t["tov"]),
        "orb_pct": _div(100.0 * t["orb"], t["orb"] + t["opp_drb"]) if t.get("opp_drb") else None,
        "ast_per100": _div(100.0 * t["ast"], poss),
        "ast_rate": _div(t["ast"], t["fgm"]),
        "stl_per100": _div(100.0 * t["stl"], poss),
        "blk_per100": _div(100.0 * t["blk"], poss),
        "pf_per100": _div(100.0 * t["pf"], poss) if t.get("pf") is not None else None,
    }
    return out


def player_rates(totals: dict[str, float]) -> dict[str, float | None]:
    """Per-game, per-36 and TS% from a player's totals (games, minutes, points, fga, ...)."""
    out: dict[str, float | None] = {}
    for stat in PLAYER_COUNT_STATS:
        v = float(totals.get(stat) or 0.0)
        out[f"{stat}_per_game"] = _div(v, totals["games"])
        out[f"{stat}_per36"] = _div(36.0 * v, totals["minutes"])
    den = 2.0 * (float(totals.get("fga") or 0) + FT_POSSESSION_WEIGHT * float(totals.get("fta") or 0))
    out["ts_pct"] = _div(float(totals.get("points") or 0), den)
    out["minutes_per_game"] = _div(totals["minutes"], totals["games"])
    return out


# ---------------------------------------------------------------- simulated results

def aggregate_from_results(results: Iterable[dict[str, Any]]) -> dict[str, Any]:
    """Compute league and player stats from plain-dict SimGameResult objects.

    Returns {"league_totals": {metric: value, "_team_std": {...}}, "player_lines": {player_id: {...}}}.
    League metrics are computed on league-wide summed totals; per-team metrics are also computed
    so a sim team spread is available (``team_std``).
    """
    team_tot: dict[str, dict[str, float]] = defaultdict(lambda: defaultdict(float))
    players: dict[str, dict[str, Any]] = {}
    n_games = 0
    for res in results:
        n_games += 1
        lines = res.get("team_lines") or []
        drb_by_team = {tl.get("team_id"): float(tl.get("defensive_rebounds") or 0) for tl in lines}
        minutes_by_team: dict[Any, float] = defaultdict(float)
        for pl in res.get("player_lines") or []:
            minutes_by_team[pl.get("team_id")] += float(pl.get("minutes") or 0)
            pid = str(pl.get("player_id"))
            rec = players.setdefault(pid, {"player_id": pid, "name": pl.get("player_name"), "team_id": pl.get("team_id"),
                                           "games": 0.0, "minutes": 0.0, **{s: 0.0 for s in PLAYER_COUNT_STATS}, "fgm": 0.0, "ftm": 0.0})
            m = float(pl.get("minutes") or 0)
            if m <= 0:
                continue
            rec["games"] += 1
            rec["minutes"] += m
            rec["points"] += float(pl.get("points") or 0)
            rec["fga"] += float(pl.get("fga") or 0)
            rec["fgm"] += float(pl.get("fgm") or 0)
            rec["fg3a"] += float(pl.get("fg3a") or 0)
            rec["fta"] += float(pl.get("fta") or 0)
            rec["ftm"] += float(pl.get("ftm") or 0)
            rec["rebounds"] += float(pl.get("rebounds") or 0)
            rec["assists"] += float(pl.get("assists") or 0)
            rec["turnovers"] += float(pl.get("turnovers") or 0)
            rec["steals"] += float(pl.get("steals") or 0)
            rec["blocks"] += float(pl.get("blocks") or 0)
        for tl in lines:
            tid = tl.get("team_id")
            opp_drb = sum(v for k, v in drb_by_team.items() if k != tid)
            t = team_tot[str(tid)]
            t["games"] += 1
            tm = minutes_by_team.get(tid) or 0.0
            ot = max(0, round((tm - 240.0) / 25.0))
            # Trust player minutes only when they look like 240 + 25 per overtime; otherwise assume regulation.
            t["minutes"] += 240.0 + 25.0 * ot if abs(tm - (240.0 + 25.0 * ot)) <= 8.0 else 240.0
            for key, src in (("points", "points"), ("fga", "fga"), ("fgm", "fgm"), ("fg3m", "fg3m"), ("fg3a", "fg3a"),
                             ("fta", "fta"), ("orb", "offensive_rebounds"), ("tov", "turnovers"), ("ast", "assists"),
                             ("stl", "steals"), ("blk", "blocks"), ("pf", "personal_fouls")):
                t[key] += float(tl.get(src) or 0)
            t["opp_drb"] += opp_drb
    league_sum: dict[str, float] = defaultdict(float)
    for t in team_tot.values():
        for k, v in t.items():
            league_sum[k] += v
    league = league_metrics_from_totals(dict(league_sum)) if league_sum.get("games") else {}
    per_team = [league_metrics_from_totals(dict(t)) for t in team_tot.values() if t.get("games")]
    team_std = {}
    for m in LEAGUE_METRICS:
        vals = [p[m] for p in per_team if p.get(m) is not None]
        team_std[m] = statistics.pstdev(vals) if len(vals) > 1 else None
    player_out = {}
    for pid, rec in players.items():
        if rec["games"] > 0:
            player_out[pid] = {**rec, **player_rates(rec)}
    return {"n_games": n_games, "league_totals": league, "team_std": team_std, "player_lines": player_out}


# ---------------------------------------------------------------- targets I/O and comparison

def load_targets(path: str | Path) -> dict[str, Any]:
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def _league_band(target: dict[str, Any]) -> tuple[float, float] | None:
    if target.get("mean") is None or target.get("std") is None:
        return None
    half = BAND_STD_MULT * float(target["std"])
    return float(target["mean"]) - half, float(target["mean"]) + half


def compare(sim_league_totals: dict[str, Any], sim_player_lines: dict[str, dict[str, Any]], targets: dict[str, Any],
            top_n: int = 150, n_misses: int = 20, min_sim_games: int = 5) -> dict[str, Any]:
    """Compare a simulation with the targets.

    sim_league_totals: {metric: value} (the "league_totals" from aggregate_from_results).
    sim_player_lines: {player_id: {games, minutes, <metric>_per36, ts_pct, ...}} (the "player_lines").
    """
    metrics = []
    for name, tgt in targets["league"].items():
        sim_v = sim_league_totals.get(name)
        row: dict[str, Any] = {"metric": name, "sim": sim_v, "target": tgt.get("mean"), "std": tgt.get("std")}
        band = _league_band(tgt)
        if sim_v is None or band is None:
            row.update(z=None, within_band=None, skipped=tgt.get("reason") or "no sim value or no target")
        else:
            std = float(tgt["std"])
            row["z"] = (sim_v - tgt["mean"]) / std if std else 0.0
            row["within_band"] = band[0] - 1e-9 <= sim_v <= band[1] + 1e-9
            row["band"] = list(band)
        metrics.append(row)
    scored = [m for m in metrics if m["within_band"] is not None]

    player_targets = targets.get("players", {})
    spread = targets.get("player_spread", {})
    ranked = sorted(player_targets.items(), key=lambda kv: -(kv[1].get("minutes") or 0))[:top_n]
    deltas, misses = [], []
    for pid, tp in ranked:
        sp = sim_player_lines.get(pid)
        if not sp or (sp.get("games") or 0) < min_sim_games:
            continue
        entry = {"player_id": pid, "name": tp.get("name"), "target_minutes": tp.get("minutes"), "sim_minutes_per_game": sp.get("minutes_per_game"),
                 "target_minutes_per_game": tp.get("minutes_per_game"), "metrics": {}}
        for m in PLAYER_COMPARE_METRICS:
            tv, sv = tp.get(m), sp.get(m)
            if tv is None or sv is None:
                continue
            scale = spread.get(m) or 1.0
            entry["metrics"][m] = {"sim": sv, "target": tv, "delta": sv - tv, "z": (sv - tv) / scale}
            misses.append({"player_id": pid, "name": tp.get("name"), "metric": m, "sim": sv, "target": tv, "delta": sv - tv, "z": (sv - tv) / scale})
        deltas.append(entry)
    misses.sort(key=lambda r: -abs(r["z"]))
    # Aggregate bias per metric across compared players (average signed delta).
    bias = {}
    for m in PLAYER_COMPARE_METRICS:
        ds = [e["metrics"][m]["delta"] for e in deltas if m in e["metrics"]]
        if ds:
            bias[m] = {"mean_delta": statistics.fmean(ds), "mean_abs_delta": statistics.fmean(abs(d) for d in ds), "n": len(ds)}
    return {
        "league": metrics,
        "league_summary": {"within_band": sum(1 for m in scored if m["within_band"]), "scored": len(scored),
                           "all_within_band": all(m["within_band"] for m in scored) if scored else None},
        "player_deltas": deltas,
        "player_bias": bias,
        "largest_player_misses": misses[:n_misses],
        "players_compared": len(deltas),
    }


def format_report(report: dict[str, Any]) -> str:
    lines = ["League metrics (sim vs 2025-26 NBA; band = target +/- %.1f team std)" % BAND_STD_MULT,
             f"{'metric':<16}{'sim':>9}{'target':>9}{'std':>8}{'z':>7}  in band"]
    for m in sorted(report["league"], key=lambda r: -abs(r["z"]) if r["z"] is not None else 1):
        if m["z"] is None:
            lines.append(f"{m['metric']:<16}{'n/a':>9}  ({m.get('skipped')})")
            continue
        lines.append(f"{m['metric']:<16}{m['sim']:>9.3f}{m['target']:>9.3f}{m['std']:>8.3f}{m['z']:>7.1f}  {'yes' if m['within_band'] else 'NO'}")
    s = report["league_summary"]
    lines.append(f"{s['within_band']}/{s['scored']} league metrics within band")
    lines.append(f"\nPlayers compared: {report['players_compared']}. Average per-36 bias (sim minus real):")
    for k, v in report["player_bias"].items():
        lines.append(f"  {k:<18}{v['mean_delta']:>+8.3f}  (mean abs {v['mean_abs_delta']:.3f})")
    lines.append("\nLargest player misses (z vs spread of that stat across real rotation players):")
    for r in report["largest_player_misses"]:
        lines.append(f"  {r['name']:<24}{r['metric']:<18}sim {r['sim']:.2f}  real {r['target']:.2f}  z {r['z']:+.1f}")
    return "\n".join(lines)
