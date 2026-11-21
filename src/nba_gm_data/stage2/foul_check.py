"""Foul and free-throw spot-check (Stage 2): the foul kernel vs real 2025-26 per-player rates vs today's engine.

- Kernel: stage2.fouls on every player's bridged inputs, over the same real-game lineups as the rebound check
  (rebound_check.ReboundSetup). In each lineup every offensive player shoots in proportion to his real shot volume,
  from his shot-region habit (T02); his own defender (height-matched) or the rim protector contests. Non-shooting,
  offensive and loose-ball fouls come at their league rates, shared by the kernel's weights. League composition of
  fouls from Basketball Index 2025-26 (shooting 52%, non-shooting 35%, offensive 6%, loose-ball 7%).
- Real: free-throw attempts per field-goal attempt (ESPN season totals) and personal fouls per 36 (box scores);
  league fouls and free throws per 100 possessions and the free-throw rate (targets file).
- Today's engine: personal fouls per 36 from box_rates.FOULS_INPUTS (times its league scale, 1.03), and free throws
  per point times points (its expected line from sim.player_feature_vector: FTA = points x FTA-per-point x .98; FGA =
  threes per 36 + the twos his remaining points need at his percentages).
- Held out: the conversion refit is fitted on half the players and checked on the other; and both engines predict
  2022-23 (FTA per FGA, fouls per 36), outside the inputs' evidence window.
"""
from __future__ import annotations

import math
import time
from collections import defaultdict
from pathlib import Path
from typing import Any

from . import game_contexts as G
from .fouls import (FoulCoefficients, and_one_probability, defender_nonshooting_multiplier, help_defender,
                    nonshooting_weights, offensive_foul_weights, profile_from_flat, with_values)
from .rebound_check import LEAGUE_MAKE, MIN_MINUTES, T02_KEYS, ReboundSetup

ZONES = ("rim", "short", "mid", "three")
MIN_FGA = 150.0
# (key, lower bound, upper bound, step). Signs follow the mechanism: drawing craft, contact seeking, strength and
# jumping at shots can only add fouls; foul control can only remove them.
FTA_SPEC = (("base[0]", -6, 0, .25), ("base[1]", -6, 0, .25), ("base[2]", -7, 0, .25),
            ("k_craft", 0, 2, .1), ("k_seek", 0, 3, .1), ("k_finish", -1, 1, .1), ("k_strength", 0, 1, .1),
            ("k_drive", -1, 1.5, .1), ("k_ns_involvement", 0, 3, .2), ("k_ns_craft", 0, 1.5, .1), ("k_ns_seek", 0, 2, .1))
# Basketball Index 2025-26: shooting fouls are 51.9% of all personal fouls (1.54 of 2.97 per 75); offensive fouls 5.8%.
SHOOTING_FOUL_SHARE = .519
OFFENSIVE_FOUL_SHARE = .058


def rule_bonus_share(env: dict) -> float:
    """The bonus share the NBA rule gives at the league's foul rate (offensive fouls do not count toward the penalty).
    The kernel uses this instead of a fitted share: a first fit left it free and it drifted to .59, trading shooting
    fouls (7.4 per 100 against a real ~10) for bonus free throws."""
    from .fouls import bonus_share_from_rule
    per_quarter = env["fouls_per100"] * (1 - OFFENSIVE_FOUL_SHARE) / 100.0 * env["possessions_per48"] / 4.0
    return bonus_share_from_rule(per_quarter)
PF_SPEC = (("k_control", 0, 2, .1), ("k_contest", -1, 1, .1), ("k_jump", 0, 1.5, .1), ("help_share[0]", 0, 1, .05),
           ("help_share[1]", 0, 1, .05), ("k_ns_control", 0, 2, .1), ("k_ns_gamble", 0, 2, .1), ("k_off_seek", -1, 2, .1),
           ("k_off_screen", 0, 5, .25))


class FoulSetup:
    def __init__(self, reb: ReboundSetup, rebound_rates: dict | None = None, contexts: list[dict] | None = None):
        self.reb = reb
        self.root = reb.root
        self.profiles = {pid: profile_from_flat(pid, f) for pid, f in reb.flat.items()}
        self.contexts = contexts if contexts is not None else reb.contexts
        self.env = reb.env
        self.totals = reb.totals
        self.real = reb.real
        self.rebound_rates = rebound_rates or {}
        self.zone_mix = {}
        for pid, f in reb.flat.items():
            mix = [max(0.0, f.get(T02_KEYS[z], .25)) for z in ZONES]
            total = sum(mix) or 1.0
            self.zone_mix[pid] = [m / total for m in mix]
        # Defender index for each offensive player (inverse of the height matchups).
        for ctx in self.contexts:
            inv = [0] * 5
            for j, i in enumerate(ctx["guards"]):
                inv[i] = j
            ctx["defender_of"] = inv

    def possessions_per36(self) -> float:
        return self.env["possessions_per48"] * 36.0 / 48.0

    def chances_per36(self) -> float:
        return self.env["oreb_chances_per48"] * 36.0 / 48.0


def evaluate(setup: FoulSetup, c: FoulCoefficients, contexts: list[dict] | None = None) -> dict[str, Any]:
    """Per player: FTA per FGA and fouls per 36; league fouls and free throws per 100 possessions."""
    prof = setup.profiles
    # Shooter and defender halves of the shooting-foul log-odds (per coefficient set, once).
    s_term = {pid: c.k_craft * (p.craft - 50) / 25 + c.k_seek * p.seek + c.k_finish * (p.contact_finish - 50) / 25
              + c.k_strength * (p.strength - 50) / 25 for pid, p in prof.items()}
    drive_term = {pid: c.k_drive * p.drive for pid, p in prof.items()}
    d_term = {pid: -c.k_control * (p.control - 50) / 25 + c.k_contest * (p.contest - 50) / 25 + c.k_jump * p.jump
              for pid, p in prof.items()}
    and1 = {pid: [and_one_probability(p, z, c) for z in range(4)] for pid, p in prof.items()}
    ns_mult = {pid: defender_nonshooting_multiplier(p, c) for pid, p in prof.items()}
    # League-mean defender multiplier over real minutes, so nonshooting_per_poss is the league rate.
    wsum = msum = 0.0
    for pid, r in setup.real.items():
        if pid in ns_mult:
            wsum += r["minutes"]
            msum += r["minutes"] * ns_mult[pid]
    ns_norm = msum / wsum if wsum else 1.0
    exp = math.exp
    shoot_att = defaultdict(float)
    shoot_fta = defaultdict(float)
    shoot_fga = defaultdict(float)
    ns_drawn = defaultdict(float)
    on_off = defaultdict(int)
    on_def = defaultdict(int)
    def_shoot_fouls = defaultdict(float)   # per team shot attempt
    def_ns = defaultdict(float)            # per team possession
    off_fouls = defaultdict(float)         # per team possession
    league = {"att": 0.0, "fouls": 0.0, "fta": 0.0, "fga": 0.0, "ctx": 0}
    for ctx in contexts if contexts is not None else setup.contexts:
        off_ids, def_ids = ctx["offense"], ctx["defense"]
        off_p = [prof[p] for p in off_ids]
        def_p = [prof[p] for p in def_ids]
        vols = [setup.reb.volume(p) for p in off_ids]
        vt = sum(vols)
        nsw = nonshooting_weights(off_p, c)
        ofw = offensive_foul_weights(off_p, c)
        helper_cache = {}
        for i, pid in enumerate(off_ids):
            on_off[pid] += 1
            j = ctx["defender_of"][i]
            if j not in helper_cache:
                helper_cache[j] = help_defender(def_p, j)
            h_j = helper_cache[j]
            share = vols[i] / vt
            mix = setup.zone_mix[pid]
            fta = fga = fouls = 0.0
            for z in range(4):
                if mix[z] <= 0:
                    continue
                # d_term carries its own sign (foul control lowers fouls).
                sz = s_term[pid] + (drive_term[pid] if z < 2 else 0.0)
                pz = 1 / (1 + exp(-(c.base[z] + sz + d_term[def_ids[j]])))
                hz = c.help_share[z] if h_j != j else 0.0
                if hz:
                    ph = 1 / (1 + exp(-(c.base[z] + sz + d_term[def_ids[h_j]])))
                    def_shoot_fouls[def_ids[h_j]] += share * mix[z] * hz * ph
                    foul = (1 - hz) * pz + hz * ph
                else:
                    foul = pz
                def_shoot_fouls[def_ids[j]] += share * mix[z] * (1 - hz) * pz
                a1 = and1[pid][z]
                fta += mix[z] * foul * (a1 + (1 - a1) * (3 if z == 3 else 2))
                fga += mix[z] * (1 - foul * (1 - a1))
                fouls += mix[z] * foul
            shoot_att[pid] += 1
            shoot_fta[pid] += fta
            shoot_fga[pid] += fga
            league["att"] += share
            league["fouls"] += share * fouls
            league["fta"] += share * fta
            league["fga"] += share * fga
            ns = c.nonshooting_per_poss * nsw[i] * ns_mult[def_ids[j]] / ns_norm
            ns_drawn[pid] += ns
            def_ns[def_ids[j]] += ns
            off_fouls[pid] += c.offensive_per_poss * ofw[i]
        for pid in def_ids:
            on_def[pid] += 1
        league["ctx"] += 1
        league.setdefault("ns", 0.0)
        league["ns"] += sum(c.nonshooting_per_poss * nsw[i] * ns_mult[def_ids[ctx["defender_of"][i]]] / ns_norm for i in range(5))
    n = league["ctx"]
    fga_per_att = league["fga"] / n
    attempts_per_poss = (setup.env["fga_per100"] / 100.0) / fga_per_att
    poss36 = setup.possessions_per36()
    ch36 = setup.chances_per36()
    ns_per_poss = league["ns"] / n
    # Rebound chances per team possession (each team's misses), each fought for by both teams; a team commits about
    # half the loose-ball fouls of the chances in its games.
    lb_per_poss = c.loose_ball_per_chance * setup.env["oreb_chances_per48"] / setup.env["possessions_per48"]
    league_out = {
        "fouls_per100": 100 * (attempts_per_poss * league["fouls"] / n + ns_per_poss + c.offensive_per_poss + lb_per_poss),
        "fta_per100": 100 * (attempts_per_poss * league["fta"] / n + 2 * c.bonus_share * ns_per_poss + c.other_fta_per_poss),
        "shooting_fouls_per100": 100 * attempts_per_poss * league["fouls"] / n,
        "and_ones_per100": None,
    }
    league_out["ft_rate"] = league_out["fta_per100"] / setup.env["fga_per100"]
    fta_per_fga = {}
    for pid, natt in shoot_att.items():
        fta_s, fga_s = shoot_fta[pid] / natt, shoot_fga[pid] / natt
        t = setup.totals.get(pid)
        vol = setup.reb.volume(pid)
        fga_per_poss = vol * 48.0 / setup.env["possessions_per48"]
        bonus = 2 * c.bonus_share * ns_drawn[pid] / on_off[pid]
        fta_per_fga[pid] = fta_s / fga_s + bonus / max(.05, fga_per_poss)
    pf36 = {}
    for pid in set(on_def) | set(on_off):
        d = on_def.get(pid, 0)
        o = on_off.get(pid, 0)
        shoot = attempts_per_poss * def_shoot_fouls[pid] / d if d else 0.0
        ns = def_ns[pid] / d if d else 0.0
        off = off_fouls[pid] / o if o else 0.0
        rr = setup.rebound_rates
        lb = c.loose_ball_per_chance * ch36 * (rr.get("orb", {}).get(pid, .05) + rr.get("drb", {}).get(pid, .15)) * c.k_lb
        pf36[pid] = poss36 * (shoot + ns + off) + lb
    return {"fta_per_fga": fta_per_fga, "pf36": pf36, "league": league_out,
            "attempts_per_poss": attempts_per_poss}


def real_rates(setup: FoulSetup, players: list[str]) -> dict[str, dict]:
    out = {}
    for pid in players:
        t = setup.totals.get(pid)
        r = setup.real.get(pid)
        if not t or not r or r["minutes"] < MIN_MINUTES or t.get("fga", 0) < MIN_FGA:
            continue
        out[pid] = {"fta": t["fta"], "fga": t["fga"], "minutes": r["minutes"], "pf": r["pf"]}
    return out


def score(predictions: dict, real: dict[str, dict], match_level: bool = False) -> dict[str, dict]:
    """FTA per FGA (weighted by FGA; noise: Poisson FTA) and fouls per 36 (weighted by minutes; Poisson)."""
    out = {}
    pairs = []
    for pid, r in real.items():
        p = predictions.get("fta_per_fga", {}).get(pid)
        if p is not None:
            real_v = r["fta"] / r["fga"]
            pairs.append([p, real_v, r["fga"], real_v / r["fga"]])
    out["fta_per_fga"] = G.weighted_errors(_level(pairs) if match_level else [tuple(x) for x in pairs])
    pairs = []
    for pid, r in real.items():
        p = predictions.get("pf36", {}).get(pid)
        if p is not None:
            real_v = 36 * r["pf"] / r["minutes"]
            pairs.append([p, real_v, r["minutes"], real_v * 36 / r["minutes"]])
    out["pf36"] = G.weighted_errors(_level(pairs) if match_level else [tuple(x) for x in pairs])
    return out


def _level(pairs: list[list]) -> list[tuple]:
    w = sum(p[2] for p in pairs)
    scale = sum(p[2] * p[1] for p in pairs) / max(1e-9, sum(p[2] * p[0] for p in pairs))
    return [(p[0] * scale, p[1], p[2], p[3]) for p in pairs]


def today_predictions(root: str | Path, player_ids: list[str]) -> dict[str, dict[str, float]]:
    """Today's engine, from its own player features (deterministic expectations, no game simulated)."""
    from ..offense import FT_LEVEL
    from ..sim import FOUL_LEVEL, load_sim_context, player_feature_vector
    context = load_sim_context(root)
    canonical = context["canonical"]
    players = {p["id"]: p for p in canonical["players"]}
    fta_per_fga, pf36 = {}, {}
    for pid in player_ids:
        player = players.get(pid)
        if player is None:
            continue
        f = player_feature_vector(canonical, player).features
        if f.get("fouls_per36") is not None:
            pf36[pid] = float(f["fouls_per36"]) * FOUL_LEVEL
        if f.get("fta_per_point") is None or f.get("points_per36") is None:
            continue
        points = float(f["points_per36"])
        fta = points * float(f["fta_per_point"]) * FT_LEVEL
        ftm = fta * float(f["ft_pct"])
        threes = float(f.get("three_per36") or 0.0)
        twos = max(0.0, (points - ftm - 3 * threes * float(f["three_pct"])) / (2 * float(f["two_pct"])))
        fga = threes + twos
        if fga > 0:
            fta_per_fga[pid] = fta / fga
    return {"fta_per_fga": fta_per_fga, "pf36": pf36}


def refit(setup: FoulSetup, start: FoulCoefficients, players: list[str], contexts: list[dict] | None = None,
          spec=FTA_SPEC, target: str = "fta", rounds: int = 20, log=None) -> tuple[FoulCoefficients, dict]:
    """Bounded coordinate search on the kernel's own numbers. target "fta": the train half's FTA per FGA plus the league
    free throws per 100 possessions; "pf": the train half's fouls per 36 plus the league fouls per 100. Ratings
    untouched."""
    real = real_rates(setup, players)

    def loss(c: FoulCoefficients) -> float:
        res = evaluate(setup, c, contexts)
        total = w = 0.0
        if target == "fta":
            for pid, r in real.items():
                p = res["fta_per_fga"].get(pid)
                if p is not None:
                    total += r["fga"] * (p - r["fta"] / r["fga"]) ** 2
                    w += r["fga"]
            shooting = SHOOTING_FOUL_SHARE * setup.env["fouls_per100"]
            return (total / w + ((res["league"]["fta_per100"] - setup.env["fta_per100"]) / 100.0) ** 2
                    + ((res["league"]["shooting_fouls_per100"] - shooting) / 50.0) ** 2)
        for pid, r in real.items():
            p = res["pf36"].get(pid)
            if p is not None:
                total += r["minutes"] * (p - 36 * r["pf"] / r["minutes"]) ** 2
                w += r["minutes"]
        return total / w + ((res["league"]["fouls_per100"] - setup.env["fouls_per100"]) / 3.0) ** 2

    def get(c, key):
        if "[" in key:
            name, idx = key[:-1].split("[")
            return getattr(c, name)[int(idx)]
        return getattr(c, key)

    current_c = start
    current = start_loss = loss(start)
    steps = {key: st for key, _, _, st in spec}
    history = []
    for rnd in range(rounds):
        improved = False
        for key, lo, hi, _ in spec:
            for direction in (1, -1):
                trial_v = min(hi, max(lo, get(current_c, key) + direction * steps[key]))
                if trial_v == get(current_c, key):
                    continue
                trial = with_values(current_c, {key: trial_v})
                value = loss(trial)
                if value < current - 1e-10:
                    current_c, current, improved = trial, value, True
                    break
        history.append(round(current, 7))
        if log:
            log(f"round {rnd}: loss {current:.6f}")
        if not improved:
            steps = {k: v / 2 for k, v in steps.items()}
            if min(steps.values()) < .004:
                break
    return current_c, {"target": target, "start_loss": round(start_loss, 7), "end_loss": round(current, 7),
                       "history": history, "values": {key: round(get(current_c, key), 4) for key, *_ in spec}}


def misses(setup: FoulSetup, predictions: dict, real: dict[str, dict], top: int = 15) -> dict[str, dict]:
    names = G.player_directory(setup.root)
    out = {}
    rows = []
    for pid, r in real.items():
        p = predictions["fta_per_fga"].get(pid)
        if p is None:
            continue
        rows.append({"name": names.get(pid, {}).get("name", pid), "fta": round(p * r["fga"] - r["fta"]),
                     "fta_per_fga": (round(p, 3), round(r["fta"] / r["fga"], 3)), "fga": round(r["fga"])})
    rows.sort(key=lambda x: x["fta"])
    out["fta"] = {"over": list(reversed(rows[-top:])), "under": rows[:top]}
    rows = []
    for pid, r in real.items():
        p = predictions["pf36"].get(pid)
        if p is None:
            continue
        rows.append({"name": names.get(pid, {}).get("name", pid), "fouls": round(p * r["minutes"] / 36 - r["pf"]),
                     "pf36": (round(p, 2), round(36 * r["pf"] / r["minutes"], 2)), "minutes": round(r["minutes"])})
    rows.sort(key=lambda x: x["fouls"])
    out["pf"] = {"over": list(reversed(rows[-top:])), "under": rows[:top]}
    return out


def time_kernel(setup: FoulSetup, c: FoulCoefficients, n: int = 20000) -> dict[str, float]:
    """Microseconds per shot attempt resolved (shooting-foul chance with help, and-one) and per possession's
    non-shooting foul draw weights."""
    from .fouls import shot_outcome
    prof = setup.profiles
    rows = []
    for ctx in setup.contexts[:n]:
        rows.append(([prof[p] for p in ctx["offense"]], [prof[p] for p in ctx["defense"]], ctx["defender_of"]))
    best_shot = best_ns = float("inf")
    for _ in range(3):
        t0 = time.perf_counter()
        for off, de, dof in rows:
            shot_outcome(off[0], de, dof[0], 0, c)
        best_shot = min(best_shot, (time.perf_counter() - t0) / len(rows))
        t0 = time.perf_counter()
        for off, de, dof in rows:
            nonshooting_weights(off, c)
        best_ns = min(best_ns, (time.perf_counter() - t0) / len(rows))
    return {"shot attempt (foul, help, and-one)": round(best_shot * 1e6, 2),
            "non-shooting foul weights (one possession)": round(best_ns * 1e6, 2)}
