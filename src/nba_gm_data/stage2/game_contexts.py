"""Real 2025-26 on-floor contexts and per-player real rates for the Stage 2 rebound and foul spot-checks.

Light: reads the season's box scores (data/research/game_boxscores_2025_26.json, regular season), ESPN season totals
(data/research/player_career_stats.json for 2025-26, data/research/espn_career_raw/ for the held-out 2022-23 season)
and the league input file through the Stage 2 bridge. No game is simulated.

Contexts: for every real game and both directions (team A on offence against team B), K lineups are drawn, each player
taking part in proportion to his real minutes that night (five drawn without replacement, weighted by minutes). Players
without inputs (left the league) get the league-median profile of every input (documented stand-in; their minutes share
is reported). Per-player real rebound rates use the Basketball-Reference definition: his rebounds over the rebounds
available while he was on the floor (minutes share of each game's team + opponent rebounds).
"""
from __future__ import annotations

import json
import math
import random
from collections import defaultdict
from pathlib import Path
from statistics import median
from typing import Any

from ..box_rates import flatten_inputs
from .league_inputs import (_league_p05, _league_priors, bridge_document, load_league_documents, player_directory,
                            sprint_reference)

BOX_FILE = "data/research/game_boxscores_2025_26.json"
CAREER_FILE = "data/research/player_career_stats.json"
ESPN_RAW_DIR = "data/research/espn_career_raw"
GENERIC = "__league_median__"


def _int(x: Any) -> int:
    try:
        return int(x)
    except (TypeError, ValueError):
        return 0


def _made_att(text: str) -> tuple[int, int]:
    try:
        a, b = str(text).split("-")
        return int(a), int(b)
    except ValueError:
        return 0, 0


def league_flat_inputs(root: str | Path) -> dict[str, dict[str, float]]:
    """player id -> flattened inputs (bridged: unknown cells get the documented group prior), plus a league-median
    stand-in under GENERIC for players without inputs."""
    documents = load_league_documents(root)
    directory = player_directory(root)
    priors = _league_priors(root)
    p05 = _league_p05(root)
    sprint = sprint_reference(root)
    out = {}
    for pid, doc in documents.items():
        bridged, _ = bridge_document(doc, priors, directory.get(pid, {}).get("group", "wing"), p05, sprint)
        out[pid] = flatten_inputs(bridged["inputs"])
    keys = set.intersection(*(set(v) for v in out.values()))
    out[GENERIC] = {k: median(v[k] for v in out.values()) for k in keys}
    regions = ("rim", "short_paint", "midrange", "three")
    total = sum(out[GENERIC][f"T02.{r}"] for r in regions)
    for r in regions:
        out[GENERIC][f"T02.{r}"] /= total
    return out


def espn_to_player(root: str | Path) -> dict[str, str]:
    return {info["espn_player_id"]: pid for pid, info in player_directory(root).items() if info.get("espn_player_id")}


def load_games(root: str | Path) -> list[dict]:
    """Regular-season games: per team its player rows (player id or None, minutes, box counts) and team totals."""
    root = Path(root)
    espn = espn_to_player(root)
    raw = json.loads((root / BOX_FILE).read_text())["games"]
    games = []
    for g in raw:
        if g.get("phase") != "regular" or len(g.get("teams", [])) != 2:
            continue
        teams = {}
        for t in g["teams"]:
            s = t["stats"]
            fgm, fga = _made_att(s.get("fieldGoalsMade-fieldGoalsAttempted"))
            ftm, fta = _made_att(s.get("freeThrowsMade-freeThrowsAttempted"))
            f3m, f3a = _made_att(s.get("threePointFieldGoalsMade-threePointFieldGoalsAttempted"))
            teams[t["team_abbrev"]] = {"oreb": _int(s.get("offensiveRebounds")), "dreb": _int(s.get("defensiveRebounds")),
                                       "fga": fga, "fgm": fgm, "fta": fta, "ftm": ftm, "fg3a": f3a,
                                       "fouls": _int(s.get("fouls")), "tov": _int(s.get("totalTurnovers")), "players": []}
        for p in g.get("players", []):
            minutes = float(p.get("minutes") or 0.0)
            if p.get("dnp") or minutes <= 0 or p.get("team_abbrev") not in teams:
                continue
            teams[p["team_abbrev"]]["players"].append({
                "pid": espn.get(str(p.get("espn_player_id"))), "name": p.get("player_name"), "minutes": minutes,
                "oreb": _int(p.get("oreb")), "dreb": _int(p.get("dreb")), "pf": _int(p.get("pf")), "fta": _int(p.get("fta"))})
        if any(not t["players"] for t in teams.values()):
            continue
        for t in teams.values():
            t["game_minutes"] = max(48.0, sum(p["minutes"] for p in t["players"]) / 5.0)
        games.append({"game_id": g["game_id"], "teams": teams})
    return games


def season_totals(root: str | Path, season: str = "2025-26") -> dict[str, dict]:
    """player id -> ESPN season totals (fga, fta, minutes...) for 2025-26 from player_career_stats.json."""
    root = Path(root)
    careers = json.loads((root / CAREER_FILE).read_text())["players"]
    espn = espn_to_player(root)
    out = {}
    for eid, row in careers.items():
        pid = espn.get(str(eid))
        if not pid:
            continue
        for s in row.get("seasons", []):
            if s.get("season") == season:
                out[pid] = {k: float(s.get(k) or 0.0) for k in ("minutes", "games", "fga", "fgm", "fg3a", "fta", "ftm", "rebounds", "points")}
    return out


def espn_raw_season(root: str | Path, season: str) -> dict[str, dict]:
    """player id -> season totals from the raw ESPN career files (OR, DR, PF, FGA, FTA, minutes); traded players' rows
    summed. Used for the held-out season."""
    root = Path(root)
    espn = espn_to_player(root)
    out = {}
    for path in sorted((root / ESPN_RAW_DIR).glob("*.json")):
        pid = espn.get(path.stem)
        if not pid:
            continue
        data = json.loads(path.read_text())
        cats = {c["name"]: c for c in data.get("categories", [])}
        if "totals" not in cats or "averages" not in cats:
            continue
        tl, al = cats["totals"]["labels"], cats["averages"]["labels"]
        tot = defaultdict(float)
        for row in cats["totals"]["statistics"]:
            if row["season"]["displayName"] != season:
                continue
            st = dict(zip(tl, row["stats"]))
            fgm, fga = _made_att(st["FG"])
            ftm, fta = _made_att(st["FT"])
            f3m, f3a = _made_att(st["3PT"])
            for k, v in (("oreb", st["OR"]), ("dreb", st["DR"]), ("pf", st["PF"])):
                tot[k] += float(v)
            tot["fga"] += fga
            tot["fta"] += fta
            tot["fg3a"] += f3a
        for row in cats["averages"]["statistics"]:
            if row["season"]["displayName"] != season:
                continue
            st = dict(zip(al, row["stats"]))
            tot["minutes"] += float(st["GP"]) * float(st["MIN"])
            tot["games"] += float(st["GP"])
        if tot.get("minutes"):
            out[pid] = dict(tot)
    return out


def real_rebounding(games: list[dict]) -> dict[str, dict]:
    """player id -> season minutes, offensive/defensive rebounds and the rebounds available while he was on the floor,
    plus personal fouls and free-throw attempts from the same box scores."""
    out: dict[str, dict] = defaultdict(lambda: defaultdict(float))
    for g in games:
        (a, ta), (b, tb) = g["teams"].items()
        for team, opp in ((ta, tb), (tb, ta)):
            ochances = team["oreb"] + opp["dreb"]
            dchances = team["dreb"] + opp["oreb"]
            for p in team["players"]:
                if not p["pid"]:
                    continue
                r = out[p["pid"]]
                share = p["minutes"] / team["game_minutes"]
                r["minutes"] += p["minutes"]
                r["games"] += 1
                r["oreb"] += p["oreb"]
                r["dreb"] += p["dreb"]
                r["pf"] += p["pf"]
                r["fta"] += p["fta"]
                r["oreb_chances"] += share * ochances
                r["dreb_chances"] += share * dchances
    return {pid: dict(v) for pid, v in out.items()}


def league_rebound_environment(games: list[dict]) -> dict[str, float]:
    """League numbers from team totals: team offensive-rebound percentage, chances per 48 team-minutes, fouls."""
    oreb = dreb = fga = fgm = fta = fouls = minutes = poss = 0.0
    for g in games:
        (a, ta), (b, tb) = g["teams"].items()
        for team, opp in ((ta, tb), (tb, ta)):
            oreb += team["oreb"]
            dreb += team["dreb"]
            fga += team["fga"]
            fgm += team["fgm"]
            fta += team["fta"]
            fouls += team["fouls"]
            minutes += team["game_minutes"]
            poss += team["fga"] + .44 * team["fta"] - team["oreb"] + team["tov"]
    games_48 = minutes / 48.0
    return {"orb_pct": oreb / (oreb + dreb), "oreb_chances_per48": (oreb + dreb) / games_48,
            "dreb_chances_per48": (oreb + dreb) / games_48, "fg_misses_per48": (fga - fgm) / games_48,
            "fouls_per100": 100 * fouls / poss, "fta_per100": 100 * fta / poss, "ft_rate": fta / fga,
            "possessions_per48": poss / games_48, "fga_per100": 100 * fga / poss}


def team_rebounding(games: list[dict]) -> dict[str, float]:
    """team abbreviation -> real offensive-rebound percentage."""
    acc = defaultdict(lambda: [0.0, 0.0])
    for g in games:
        (a, ta), (b, tb) = g["teams"].items()
        for name, team, opp in ((a, ta, tb), (b, tb, ta)):
            acc[name][0] += team["oreb"]
            acc[name][1] += team["oreb"] + opp["dreb"]
    return {k: v[0] / v[1] for k, v in acc.items() if v[1]}


def _draw_five(rng: random.Random, players: list[dict]) -> list[dict]:
    pool = list(players)
    chosen = []
    for _ in range(min(5, len(pool))):
        total = sum(p["minutes"] for p in pool)
        x = rng.random() * total
        acc = 0.0
        for k, p in enumerate(pool):
            acc += p["minutes"]
            if acc >= x:
                chosen.append(pool.pop(k))
                break
        else:
            chosen.append(pool.pop())
    return chosen


def build_contexts(games: list[dict], per_direction: int, seed: int = 20261121) -> list[dict]:
    """On-floor lineups drawn from real games: {'team', 'opp', 'offense': [pid or GENERIC]*5, 'defense': [...]*5}."""
    rng = random.Random(seed)
    out = []
    for g in games:
        (a, ta), (b, tb) = g["teams"].items()
        for name, team, oname, opp in ((a, ta, b, tb), (b, tb, a, ta)):
            if len(team["players"]) < 5 or len(opp["players"]) < 5:
                continue
            for _ in range(per_direction):
                off = [p["pid"] or GENERIC for p in _draw_five(rng, team["players"])]
                de = [p["pid"] or GENERIC for p in _draw_five(rng, opp["players"])]
                out.append({"team": name, "opp": oname, "game": g["game_id"], "offense": off, "defense": de})
    return out


def neutral_contexts(player_ids: list[str], pool: list[tuple[str, float]], per_player: int, seed: int = 7) -> list[dict]:
    """Context-free lineups for one player each: four teammates and five opponents drawn from the league's
    minutes pool (for the held-out season, whose lineups are not in the repo)."""
    rng = random.Random(seed)
    ids = [p for p, _ in pool]
    weights = [w for _, w in pool]
    cum = []
    acc = 0.0
    for w in weights:
        acc += w
        cum.append(acc)
    import bisect

    def draw(exclude: set) -> str:
        while True:
            k = bisect.bisect_left(cum, rng.random() * acc)
            pid = ids[min(k, len(ids) - 1)]
            if pid not in exclude:
                exclude.add(pid)
                return pid

    out = []
    for pid in player_ids:
        for side in ("offense", "defense"):
            for _ in range(per_player):
                used = {pid}
                mates = [pid] + [draw(used) for _ in range(4)]
                opps = [draw(used) for _ in range(5)]
                ctx = {"team": "neutral", "opp": "neutral", "game": "neutral", "focus": pid}
                ctx["offense"], ctx["defense"] = (mates, opps) if side == "offense" else (opps, mates)
                out.append(ctx)
    return out


def minutes_without_inputs(games: list[dict], known: set[str]) -> float:
    total = missing = 0.0
    for g in games:
        for t in g["teams"].values():
            for p in t["players"]:
                total += p["minutes"]
                if not p["pid"] or p["pid"] not in known:
                    missing += p["minutes"]
    return missing / total if total else 0.0


def weighted_errors(pairs: list[tuple[float, float, float, float]]) -> dict[str, float] | None:
    """pairs of (predicted, real, weight, real-rate sampling variance). Bias, error beyond noise, correlation."""
    pairs = [p for p in pairs if p[2] > 0 and p[0] is not None and p[1] is not None]
    if len(pairs) < 3:
        return None
    w = sum(p[2] for p in pairs)
    mp = sum(p[2] * p[0] for p in pairs) / w
    mr = sum(p[2] * p[1] for p in pairs) / w
    mse = sum(p[2] * (p[0] - p[1]) ** 2 for p in pairs) / w
    noise = sum(p[2] * p[3] for p in pairs) / w
    cov = sum(p[2] * (p[0] - mp) * (p[1] - mr) for p in pairs) / w
    vp = sum(p[2] * (p[0] - mp) ** 2 for p in pairs) / w
    vr = sum(p[2] * (p[1] - mr) ** 2 for p in pairs) / w
    return {"players": len(pairs), "real": round(mr, 4), "predicted": round(mp, 4), "bias": round(mp - mr, 4),
            "rmse": round(math.sqrt(mse), 4), "excess_rmse": round(math.sqrt(max(0.0, mse - noise)), 4),
            "noise_rmse": round(math.sqrt(noise), 4),
            "corr": round(cov / math.sqrt(vp * vr), 3) if vp > 0 and vr > 0 else None,
            "pred_sd": round(math.sqrt(vp), 4), "real_sd": round(math.sqrt(vr), 4)}


def split_half(pid: str) -> int:
    """Fixed player halves (same hash as the shooting check): 0 = fit half, 1 = held-out half."""
    import hashlib
    return int(hashlib.sha256(pid.encode()).hexdigest(), 16) % 2
