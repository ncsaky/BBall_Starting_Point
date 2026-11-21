"""Rebound spot-check (Stage 2): the rebound kernel vs real 2025-26 per-player rebound rates vs today's engine.

- Kernel: stage2.rebounding on every player's bridged inputs, played over lineups drawn from the real 2025-26 games
  (game_contexts). Each context is one rebound chance: a miss type and shooter drawn from the five shooters' real shot
  volume, their shot-region habits (T02) and the league's make rate by region; free-throw misses at their real share
  of rebound chances (Basketball Index: 5.3% of rebounds come off free throws).
- Real: offensive and defensive rebound percentage per player (rebounds over the rebounds available while he was on
  the floor), from the season's box scores; team offensive-rebound percentage; the targets file.
- Today's engine: rebounds per 36 from box_rates.REBOUNDS_INPUTS (it has no offensive/defensive split per player) and
  its team offensive-rebound formula (read from a calibration replay).
- Held out: the conversion refit is fitted on half the players (fixed hash) and checked on the other half; and both
  engines predict the 2022-23 season (per-36 offensive and defensive rebounds) from the same inputs in neutral
  lineups. The inputs' evidence spans 2023-24 to 2025-26, so 2022-23 is outside it (the legacy-trait prior inside
  some inputs may still carry older seasons).
"""
from __future__ import annotations

import math
import random
import time
from collections import defaultdict
from pathlib import Path
from typing import Any

from . import game_contexts as G
from .rebounding import (MISS_TYPES, ReboundCoefficients, matchups, prepare, profile_from_flat, rebound_probabilities,
                         with_values)

MIN_MINUTES = 500.0
ZONES = ("rim", "short", "mid", "three")
T02_KEYS = {"rim": "T02.rim", "short": "T02.short_paint", "mid": "T02.midrange", "three": "T02.three"}
# Real 2025-26 make rates by region for rotation players (S2-SEAM-SHOOTING, Basketball Index): misses by region.
LEAGUE_MAKE = {"rim": .674, "short": .448, "mid": .417, "three": .361}
FT_MISS_SHARE = .053  # Basketball Index 2025-26: free-throw rebounds per 75 (.349) over all rebounds per 75 (6.556)
FIT_KEYS = ("defense_edge", "k_off_skill", "k_def_skill", "k_control", "k_reach", "k_jump", "retreat", "crash_closing",
            "box_max", "box_self_cost", "box_keep", "k_box_mass", "anchor", "distance_scale", "inside")
UNIT_KEYS = ("retreat", "box_max", "box_self_cost", "box_keep", "crash_closing", "inside", "anchor")


class ReboundSetup:
    """Everything coefficient-free: profiles, lineups with their miss type, shooter and matchups."""

    def __init__(self, root: str | Path, per_direction: int = 20, seed: int = 20261121):
        self.root = Path(root)
        self.flat = G.league_flat_inputs(root)
        self.profiles = {pid: profile_from_flat(pid, f) for pid, f in self.flat.items()}
        self.games = G.load_games(root)
        self.env = G.league_rebound_environment(self.games)
        self.real = G.real_rebounding(self.games)
        self.totals = G.season_totals(root)
        self.team_real = G.team_rebounding(self.games)
        fga_rate = {pid: t["fga"] / t["minutes"] for pid, t in self.totals.items() if t.get("minutes", 0) >= 100}
        self.league_fga_rate = sum(fga_rate.values()) / len(fga_rate)
        self.fga_rate = fga_rate
        self.contexts = self._annotate(G.build_contexts(self.games, per_direction, seed), seed)
        self.missing_minutes = G.minutes_without_inputs(self.games, set(self.flat))

    def volume(self, pid: str) -> float:
        return self.fga_rate.get(pid, self.league_fga_rate)

    def _annotate(self, contexts: list[dict], seed: int) -> list[dict]:
        rng = random.Random(seed + 1)
        for ctx in contexts:
            ctx["offense"] = [p if p in self.profiles else G.GENERIC for p in ctx["offense"]]
            ctx["defense"] = [p if p in self.profiles else G.GENERIC for p in ctx["defense"]]
            off = [self.profiles[p] for p in ctx["offense"]]
            de = [self.profiles[p] for p in ctx["defense"]]
            ctx["guards"] = matchups(off, de)
            if rng.random() < FT_MISS_SHARE:
                ctx["miss"], ctx["shooter"] = "ft", 0
                continue
            weights = []
            for i, pid in enumerate(ctx["offense"]):
                f = self.flat[pid]
                vol = self.volume(pid)
                for z in ZONES:
                    weights.append((vol * f.get(T02_KEYS[z], .25) * (1 - LEAGUE_MAKE[z]), i, z))
            total = sum(w for w, _, _ in weights)
            x = rng.random() * total
            acc = 0.0
            for w, i, z in weights:
                acc += w
                if acc >= x:
                    break
            ctx["miss"], ctx["shooter"] = z, i
        return contexts


def evaluate(setup: ReboundSetup, coefficients: ReboundCoefficients, contexts: list[dict] | None = None) -> dict[str, Any]:
    """Expected rebound shares: per player (offence and defence chances) and per team (offensive-rebound %)."""
    prepared = {pid: prepare(p, coefficients) for pid, p in setup.profiles.items()}
    off_sum = defaultdict(float)
    off_n = defaultdict(int)
    def_sum = defaultdict(float)
    def_n = defaultdict(int)
    team = defaultdict(lambda: [0.0, 0])
    by_miss = defaultdict(lambda: [0.0, 0])
    for ctx in contexts if contexts is not None else setup.contexts:
        off = [prepared[p] for p in ctx["offense"]]
        de = [prepared[p] for p in ctx["defense"]]
        probs = rebound_probabilities(off, de, ctx["guards"], ctx["miss"], ctx["shooter"], coefficients)
        o = 0.0
        for i, pid in enumerate(ctx["offense"]):
            off_sum[pid] += probs[i]
            off_n[pid] += 1
            o += probs[i]
        for j, pid in enumerate(ctx["defense"]):
            def_sum[pid] += probs[5 + j]
            def_n[pid] += 1
        t = team[ctx["team"]]
        t[0] += o
        t[1] += 1
        m = by_miss[ctx["miss"]]
        m[0] += o
        m[1] += 1
    return {"orb": {p: off_sum[p] / n for p, n in off_n.items()}, "drb": {p: def_sum[p] / n for p, n in def_n.items()},
            "orb_n": dict(off_n), "drb_n": dict(def_n),
            "team_orb": {k: v[0] / v[1] for k, v in team.items()},
            "orb_by_miss": {k: v[0] / v[1] for k, v in by_miss.items()},
            "league_orb": sum(v[0] for v in team.values()) / max(1, sum(v[1] for v in team.values()))}


def rotation(setup: ReboundSetup, half: int | None = None) -> list[str]:
    out = [pid for pid, r in setup.real.items() if r["minutes"] >= MIN_MINUTES and pid in setup.profiles]
    if half is not None:
        out = [p for p in out if G.split_half(p) == half]
    return sorted(out)


def score_rates(setup: ReboundSetup, result: dict, players: list[str]) -> dict[str, dict]:
    out = {}
    for side, key, chances in (("orb", "oreb", "oreb_chances"), ("drb", "dreb", "dreb_chances")):
        pairs = []
        for pid in players:
            r = setup.real[pid]
            pred = result[side].get(pid)
            if pred is None or r[chances] <= 0:
                continue
            real = r[key] / r[chances]
            pairs.append((pred, real, r[chances], real * (1 - real) / r[chances]))
        out[side] = G.weighted_errors(pairs)
    return out


def per36_from_shares(setup: ReboundSetup, orb: float, drb: float) -> tuple[float, float]:
    """Per-36 offensive and defensive rebounds at the league's rebound chances per on-floor minute."""
    per_min = setup.env["oreb_chances_per48"] / 48.0
    return 36 * orb * per_min, 36 * drb * per_min


def score_per36(setup: ReboundSetup, predictions: dict[str, float], players: list[str], real_rows: dict[str, dict],
                key: str = "reb", match_level: bool = False) -> dict | None:
    """Per-36 rebounds (key 'reb', 'oreb' or 'dreb') against real rows {minutes, oreb, dreb}. Poisson noise."""
    pairs = []
    for pid in players:
        r = real_rows.get(pid)
        pred = predictions.get(pid)
        if r is None or pred is None or r["minutes"] < MIN_MINUTES:
            continue
        count = r["oreb"] + r["dreb"] if key == "reb" else r[key]
        real = 36 * count / r["minutes"]
        pairs.append([pred, real, r["minutes"], real * 36 / r["minutes"]])
    if match_level and pairs:
        w = sum(p[2] for p in pairs)
        scale = sum(p[2] * p[1] for p in pairs) / sum(p[2] * p[0] for p in pairs)
        for p in pairs:
            p[0] *= scale
    return G.weighted_errors([tuple(p) for p in pairs])


def today_rebounds_per36(setup: ReboundSetup) -> dict[str, float]:
    """Today's engine: each player's fitted rebounds per 36 (sim.rebound_rate_per_minute with new ratings)."""
    from ..box_rates import rebounds_per36_from_inputs
    from .league_inputs import load_league_documents
    docs = load_league_documents(setup.root)
    out = {}
    for pid, doc in docs.items():
        value = rebounds_per36_from_inputs(doc["inputs"])
        if value is not None:
            out[pid] = value
    return out


def kernel_per36(setup: ReboundSetup, result: dict) -> dict[str, dict[str, float]]:
    out = {}
    for pid in set(result["orb"]) & set(result["drb"]):
        o, d = per36_from_shares(setup, result["orb"][pid], result["drb"][pid])
        out[pid] = {"oreb": o, "dreb": d, "reb": o + d}
    return out


def refit(setup: ReboundSetup, start: ReboundCoefficients, train_half: int = 0, contexts: list[dict] | None = None,
          keys=FIT_KEYS, rounds: int = 25, step: float = .2, log=None) -> tuple[ReboundCoefficients, dict]:
    """Coordinate search on the kernel's own conversion numbers, fitted to the train half's offensive and defensive
    rebound percentages (weighted by chances) plus the league offensive-rebound percentage. Ratings untouched."""
    players = rotation(setup, train_half)
    target_league = setup.env["orb_pct"]

    def loss(c: ReboundCoefficients) -> float:
        res = evaluate(setup, c, contexts)
        total = w = 0.0
        for pid in players:
            r = setup.real[pid]
            for side, key, ch in (("orb", "oreb", "oreb_chances"), ("drb", "dreb", "dreb_chances")):
                pred = res[side].get(pid)
                if pred is None:
                    continue
                total += r[ch] * (pred - r[key] / r[ch]) ** 2
                w += r[ch]
        return total / w + 4.0 * (res["league_orb"] - target_league) ** 2

    values = {k: getattr(start, k) for k in keys}
    current_c = start
    current = start_loss = loss(start)
    history = []
    for rnd in range(rounds):
        improved = False
        for key in keys:
            for direction in (1, -1):
                base = values[key]
                delta = step * max(.05, abs(base)) if key not in UNIT_KEYS else step * .25
                trial_v = base + direction * delta
                if key in UNIT_KEYS and not 0 <= trial_v <= 1:
                    continue
                if key == "distance_scale" and trial_v <= 0:
                    continue
                trial = with_values(current_c, {key: trial_v})
                value = loss(trial)
                if value < current - 1e-9:
                    values[key], current_c, current, improved = trial_v, trial, value, True
        history.append(round(current, 7))
        if log:
            log(f"round {rnd}: loss {current:.6f} step {step:.4f}")
        if not improved:
            step /= 2
            if step < .01:
                break
    return current_c, {"start_loss": round(start_loss, 7), "end_loss": round(current, 7), "history": history,
                       "values": {k: round(v, 4) for k, v in values.items()}}


def misses(setup: ReboundSetup, result: dict, players: list[str], top: int = 15) -> dict[str, list]:
    """Biggest per-player misses in season rebounds (offensive + defensive) on his real chances."""
    rows = []
    for pid in players:
        r = setup.real[pid]
        if pid not in result["orb"] or pid not in result["drb"]:
            continue
        po, pd = result["orb"][pid] * r["oreb_chances"], result["drb"][pid] * r["dreb_chances"]
        rows.append({"player_id": pid, "name": G.player_directory(setup.root).get(pid, {}).get("name", pid),
                     "rebounds": round(po + pd - r["oreb"] - r["dreb"], 1),
                     "orb_pct": (round(100 * result["orb"][pid], 1), round(100 * r["oreb"] / r["oreb_chances"], 1)),
                     "drb_pct": (round(100 * result["drb"][pid], 1), round(100 * r["dreb"] / r["dreb_chances"], 1)),
                     "minutes": round(r["minutes"])})
    rows.sort(key=lambda x: x["rebounds"])
    return {"over": list(reversed(rows[-top:])), "under": rows[:top]}


def time_kernel(setup: ReboundSetup, coefficients: ReboundCoefficients, n: int = 20000) -> float:
    """Microseconds per rebound resolved (kernel call on a prepared lineup, matchups precomputed)."""
    prepared = {pid: prepare(p, coefficients) for pid, p in setup.profiles.items()}
    sample = setup.contexts[:n]
    rows = [([prepared[p] for p in c["offense"]], [prepared[p] for p in c["defense"]], c["guards"], c["miss"], c["shooter"])
            for c in sample]
    best = float("inf")
    for _ in range(3):
        t0 = time.perf_counter()
        for off, de, g, m, s in rows:
            rebound_probabilities(off, de, g, m, s, coefficients)
        best = min(best, (time.perf_counter() - t0) / len(rows))
    return round(best * 1e6, 2)
