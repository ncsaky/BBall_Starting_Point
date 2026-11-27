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
    "fg2_pct", "fg3_pct", "ft_pct",
]
# Box-score texture (SHOOTING-SPLITS, 2026-11-26): players used per team-game and how often rare nights happen.
# Scored apart from the league metrics. Rare-night bands allow for both seasons' sampling noise (see texture_band).
TEXTURE_EVENTS = {
    "pts40_per_game": ("points", 40), "pts50_per_game": ("points", 50), "reb20_per_game": ("rebounds", 20),
    "stl6_per_game": ("steals", 6), "tov10_per_game": ("turnovers", 10),
}
TEXTURE_METRICS = ["players_used"] + list(TEXTURE_EVENTS)
PLAYERS_USED_BAND = 0.5      # players per team-game, either side of real
TEXTURE_MODEL_TOLERANCE = 0.15   # share of the real rate allowed on top of sampling noise
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
        "fg2_pct": _div(t["fgm"] - t["fg3m"], t["fga"] - t["fg3a"]) if "fg3m" in t else None,
        "fg3_pct": _div(t["fg3m"], t["fg3a"]) if "fg3m" in t else None,
        "ft_pct": _div(t["ftm"], t["fta"]) if "ftm" in t else None,
    }
    return out


def texture_from_games(games: Iterable[list[dict[str, Any]]]) -> dict[str, Any]:
    """Players used per team-game and rare-night counts from games given as lists of player lines.

    Each line needs team_id (or team_abbrev), minutes, points, rebounds, steals, turnovers; a line with no minutes
    did not play."""
    n_games, used, counts = 0, [], {k: 0 for k in TEXTURE_EVENTS}
    for lines in games:
        n_games += 1
        per_team: dict[Any, int] = defaultdict(int)
        for line in lines:
            if float(line.get("minutes") or 0) <= 0:
                continue
            per_team[line.get("team_id", line.get("team_abbrev"))] += 1
            for key, (stat, threshold) in TEXTURE_EVENTS.items():
                counts[key] += float(line.get(stat) or 0) >= threshold
        used += list(per_team.values())
    out: dict[str, Any] = {"games": n_games, "counts": counts,
                           "players_used": statistics.fmean(used) if used else None}
    out.update({k: (v / n_games if n_games else None) for k, v in counts.items()})
    return out


def texture_band(metric: str, target: dict[str, Any], sim_games: int) -> tuple[float, float] | None:
    """Acceptance band for a texture metric: players used +/- PLAYERS_USED_BAND; a rare-night rate per game +/- two
    standard errors of both seasons' counts (Poisson) plus TEXTURE_MODEL_TOLERANCE of the real rate."""
    mean = target.get("mean")
    if mean is None:
        return None
    if metric == "players_used":
        return mean - PLAYERS_USED_BAND, mean + PLAYERS_USED_BAND
    real_games = float(target.get("games") or 0)
    if not real_games or not sim_games:
        return None
    half = 2.0 * math.sqrt(mean / real_games + mean / sim_games) + TEXTURE_MODEL_TOLERANCE * mean
    return max(0.0, mean - half), mean + half


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
    results = list(results)
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
                             ("fta", "fta"), ("ftm", "ftm"), ("orb", "offensive_rebounds"), ("tov", "turnovers"), ("ast", "assists"),
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
    texture = texture_from_games([res.get("player_lines") or [] for res in results])
    return {"n_games": n_games, "league_totals": league, "team_std": team_std, "player_lines": player_out,
            "texture": texture}


# ---------------------------------------------------------------- targets I/O and comparison

def load_targets(path: str | Path) -> dict[str, Any]:
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def _league_band(target: dict[str, Any]) -> tuple[float, float] | None:
    if target.get("mean") is None or target.get("std") is None:
        return None
    half = float(target["band_half"]) if target.get("band_half") is not None else BAND_STD_MULT * float(target["std"])
    return float(target["mean"]) - half, float(target["mean"]) + half


def compare(sim_league_totals: dict[str, Any], sim_player_lines: dict[str, dict[str, Any]], targets: dict[str, Any],
            top_n: int = 150, n_misses: int = 20, min_sim_games: int = 5,
            sim_texture: dict[str, Any] | None = None) -> dict[str, Any]:
    """Compare a simulation with the targets.

    sim_league_totals: {metric: value} (the "league_totals" from aggregate_from_results).
    sim_player_lines: {player_id: {games, minutes, <metric>_per36, ts_pct, ...}} (the "player_lines").
    sim_texture: the "texture" from aggregate_from_results (players used, rare nights); scored when the targets have it.
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
    texture = []
    for name, tgt in (targets.get("texture") or {}).items():
        sim_v = (sim_texture or {}).get(name)
        band = texture_band(name, tgt, int((sim_texture or {}).get("games") or 0))
        row = {"metric": name, "sim": sim_v, "target": tgt.get("mean"), "band": list(band) if band else None,
               "sim_count": ((sim_texture or {}).get("counts") or {}).get(name), "real_count": tgt.get("count")}
        row["within_band"] = None if sim_v is None or band is None else band[0] - 1e-9 <= sim_v <= band[1] + 1e-9
        texture.append(row)
    scored_texture = [t for t in texture if t["within_band"] is not None]
    return {
        "texture": texture,
        "texture_summary": {"within_band": sum(1 for t in scored_texture if t["within_band"]), "scored": len(scored_texture)},
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
    if report.get("texture"):
        lines.append("\nBox-score texture (per game; rare nights scaled to a 1,230-game season in brackets)")
        lines.append(f"{'metric':<16}{'sim':>9}{'target':>9}  {'band':<17} in band")
        for t in report["texture"]:
            if t["sim"] is None or t["band"] is None:
                lines.append(f"{t['metric']:<16}{'n/a':>9}")
                continue
            season = "" if t["metric"] == "players_used" else f"  [{t['sim'] * 1230:.0f} vs {t['target'] * 1230:.0f}]"
            lines.append(f"{t['metric']:<16}{t['sim']:>9.4f}{t['target']:>9.4f}  {t['band'][0]:.4f}-{t['band'][1]:.4f}"
                         f"  {'yes' if t['within_band'] else 'NO'}{season}")
        ts = report["texture_summary"]
        lines.append(f"{ts['within_band']}/{ts['scored']} texture metrics within band (sandbox-sim uses projected minutes, "
                     "flatter than a coach's: players used and big nights are judged on replay-real-minutes or a season)")
    lines.append(f"\nPlayers compared: {report['players_compared']}. Average per-36 bias (sim minus real):")
    for k, v in report["player_bias"].items():
        lines.append(f"  {k:<18}{v['mean_delta']:>+8.3f}  (mean abs {v['mean_abs_delta']:.3f})")
    lines.append("\nLargest player misses (z vs spread of that stat across real rotation players):")
    for r in report["largest_player_misses"]:
        lines.append(f"  {r['name']:<24}{r['metric']:<18}sim {r['sim']:.2f}  real {r['target']:.2f}  z {r['z']:+.1f}")
    return "\n".join(lines)
