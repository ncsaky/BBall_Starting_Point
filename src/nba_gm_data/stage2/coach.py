"""Stage 2 coach: who is on the floor, decided live through the game (S2-COACH).

The pre-game plan comes from today's coach model, unchanged (engine._prepare_pools): tonight's planned minutes (the real
minutes in replayed games; in generated games the coach's rotation or the GM's rough targets, with today's steps for
absent teammates, matchup minutes, the ramp-up after an absence and the human team's game-day variation). That plan is
what a player would play in a close game. This module is the in-game part of the same coach: it decides at every
stoppage who plays, and so how the night's minutes move around the plan.

What the coach reacts to, and the evidence for each rule:
- Rotation rhythm (stint and rest lengths by role). Each stint gets a length drawn around his role's typical stint;
  the coach brings back whoever is furthest behind his plan once he has rested. FITTED by simulation so that stints,
  rests, minutes by quarter and depth match the real 2023-26 play-by-play study (data/research/rotation_evidence.json,
  docs/agents/tasks/rotation-evidence.md).
- Fatigue: a stint's length also follows the player's conditioning (P11) and tonight's tired legs (today's tip-off
  fatigue); how long he must rest follows his recovery (P12). Tired legs on the second night of a back-to-back cost
  about 0.6 minutes (the real paired comparison in the rotation study). The conditioning and recovery weights are
  stand-ins (no direct evidence; both inputs are mostly position priors today).
- Foul trouble: when a player picks up his 2nd foul in the 1st quarter, his 3rd before halftime, or his 4th or 5th, the
  coach pulls him within a minute with the real chance for that foul, period and role, and brings him back after the
  real bench time (or, for late 4th and 5th fouls, sometimes not at all). Held-out fits from the rotation study.
- Blowouts: in the 4th quarter each regular on the floor leaves for good with the real per-minute chance for the
  time left and the live margin (held-out fits); players outside the planned rotation (generated games) come in once
  garbage time is long enough to matter, as today's coach does (game_minutes.GARBAGE_EXTRAS_*).
- Close finishes: the coach's five most-trusted players (largest plans) close a game within a few points late in the
  4th quarter and in overtime (real: starters fill three quarters of close-finish floor time, stars nearly all).
- Hot and cold hands: the coach revises tonight's plan with the player's shooting so far (field-goal points above or
  below what his shots should bring). FITTED to real 2025-26 box scores (regulars in close games: +0.36 minutes per
  field-goal point per 10 minutes above his own rate, almost all of it on the cold side).
- Injuries and rust: a player hurt during a generated game (today's health model, `health_injury_exit`) leaves after
  that share of his plan and does not return; a player back from an absence (rust, or the minutes ramp) gets shorter
  stints. Foul-outs leave for good.
- Matchups: the pre-game matchup minutes are in the plan (today's model); live, who guards whom (stage2.matchups) and
  the pick-and-roll coverages (stage2.screens) carry them.

The coach has its own random stream (engine.py), so its draws never shift the possession stream's numbers.
No player rating is read differently or moved here (AGENTS.md rule 1).
"""
from __future__ import annotations

import math
import random

VERSION = "stage2_coach_v1_2026_11_24"
ROLES = ("star", "starter", "sixth_man", "bench", "reserve")
TRACE = False   # research hook (scripts/research/s2_coach_check.py): each coach keeps a log of its decisions; off in play

# ---- Real-data decision tables (data/research/rotation_evidence.json; tests check these copies) ----------------------
# Chance the coach pulls a player within a minute of this foul (held-out fits, 2023-25 seasons, checked on 2025-26):
# key = fouls + period class, then role.
FOUL_EXIT = {
    "2_Q1": {"star": .5298, "starter": .6772, "sixth_man": .2443, "bench": .3451},
    "3_first_half": {"star": .548, "starter": .7384, "sixth_man": .7594, "bench": .784},
    "4_Q1_Q3": {"star": .5185, "starter": .6807, "sixth_man": .3785, "bench": .4128},
    "4_Q4_OT": {"star": .1318, "starter": .1532, "sixth_man": .2277, "bench": .2852},
    "5_Q1_Q3": {"star": .6759, "starter": .8049, "sixth_man": .6058, "bench": .6612},
    "5_Q4_OT": {"star": .2662, "starter": .3351, "sixth_man": .4728, "bench": .4176},
}
# ... of which this share would have left within the minute anyway (exit within a minute after a FIRST first-quarter
# foul, pooled 2024-26): the coach's foul decision adds only the excess over his normal rotation.
FOUL_BASE_EXIT = {"star": .134, "starter": .184, "sixth_man": .076, "bench": .119}
# Bench time if he came back (seconds; 25th, 50th, 75th percentile, pooled 2024-26).
FOUL_BENCH = {
    "2_Q1": {"star": (314.0, 380.0, 442.0), "starter": (346.0, 469.0, 580.0), "sixth_man": (215.0, 356.0, 495.95),
             "bench": (259.05, 386.0, 669.5)},
    "3_first_half": {"star": (90.5, 201.0, 350.75), "starter": (104.0, 205.0, 380.0),
                     "sixth_man": (400.775, 555.3, 815.75), "bench": (474.0, 714.0, 967.5)},
    "4_Q1_Q3": {"star": (202.0, 294.0, 411.0), "starter": (297.4, 429.0, 559.0), "sixth_man": (184.375, 305.5, 436.5),
                "bench": (257.95, 397.0, 554.5)},
    "4_Q4_OT": {"star": (55.0, 136.0, 220.0), "starter": (97.0, 159.0, 214.5), "sixth_man": (171.25, 215.5, 310.0),
                "bench": (129.0, 223.25, 321.225)},
    "5_Q1_Q3": {"star": (358.0, 418.0, 605.0), "starter": (311.5, 454.5, 612.0), "sixth_man": (343.0, 414.0, 477.0),
                "bench": (329.475, 388.95, 482.75)},
    "5_Q4_OT": {"star": (104.75, 169.0, 233.75), "starter": (122.75, 191.5, 275.0), "sixth_man": (87.55, 218.0, 305.8),
                "bench": (135.0, 236.5, 349.25)},
}
# Share of those pulled who came back that night (pooled 2024-26).
FOUL_RETURNED = {
    "2_Q1": {"star": .995, "starter": .996, "sixth_man": 1.0, "bench": .946},
    "3_first_half": {"star": 1.0, "starter": .993, "sixth_man": .996, "bench": .962},
    "4_Q1_Q3": {"star": .904, "starter": .901, "sixth_man": .907, "bench": .786},
    "4_Q4_OT": {"star": .433, "starter": .484, "sixth_man": .417, "bench": .377},
    "5_Q1_Q3": {"star": .778, "starter": .804, "sixth_man": .84, "bench": .667},
    "5_Q4_OT": {"star": .557, "starter": .505, "sixth_man": .378, "bench": .393},
}
# Permanent 4th-quarter exits: chance a starter on the floor leaves for good in the next minute, by minutes left (9, 6,
# 3, 1) and live margin from his team's side (held-out fits).
Q4_EXIT = {
    9: {"close_0_5": .0172, "ahead_6_14": .0198, "behind_6_14": .0253, "ahead_15_19": .0361, "behind_15_19": .0469,
        "ahead_20_24": .0814, "behind_20_24": .0806, "ahead_25_plus": .2053, "behind_25_plus": .1584},
    6: {"close_0_5": .0137, "ahead_6_14": .0201, "behind_6_14": .0285, "ahead_15_19": .0309, "behind_15_19": .0808,
        "ahead_20_24": .1344, "behind_20_24": .1867, "ahead_25_plus": .2257, "behind_25_plus": .2276},
    3: {"close_0_5": .0086, "ahead_6_14": .024, "behind_6_14": .049, "ahead_15_19": .2966, "behind_15_19": .3413,
        "ahead_20_24": .5544, "behind_20_24": .375, "ahead_25_plus": .3461, "behind_25_plus": .0898},
    1: {"close_0_5": .0888, "ahead_6_14": .1388, "behind_6_14": .1191, "ahead_15_19": .2641, "behind_15_19": .0788,
        "ahead_20_24": .1652, "behind_20_24": .0161, "ahead_25_plus": .0163, "behind_25_plus": .0152},
}

# ---- The coach's own numbers. FITTED = set by simulation against the rotation study (scripts/research/
# s2_coach_check.py); the rest are documented stand-ins. -------------------------------------------------------------
COACH = {
    # In-game injuries (S2-TENTH): 1 = he also leaves once the game reaches his drawn share of regulation, not only once
    # he has played that share of his planned minutes; 0 = the plan share only (S2-COACH).
    "injury_clock": 1.0,
    # Typical stint (seconds, the median of a lognormal draw per stint) and its spread, by role. FITTED: stints, rests,
    # minutes by quarter (real stint medians: star 528 s, starter 427, sixth man 403, bench 313).
    "stint_star": 560.0, "stint_starter": 460.0, "stint_sixth_man": 560.0, "stint_bench": 540.0, "stint_reserve": 400.0,
    "stint_sigma": .38,
    # The opening stint of each half has its own, tighter draw (real medians: star 548 s, starter 449; quartiles about
    # 0.75x-1.3x).
    "open_star": 510.0, "open_starter": 415.0, "open_sigma": .25,
    # Closing the half: from half_s seconds left in the 2nd and 4th quarters the starters who have rested come back
    # (claim bonus half_bonus) and the bench players on the floor may be taken off before their stint is done. Real
    # stars return with about 7:30 left in the 2nd quarter and play to halftime.
    "half_s": 450.0, "half_bonus": .5,
    # Shortest rest before he may come back (seconds), by role. FITTED (real rest medians: star 239 s, starter 277,
    # sixth man 317, bench 412).
    "rest_star": 170.0, "rest_starter": 195.0, "rest_sixth_man": 210.0, "rest_bench": 230.0, "rest_reserve": 230.0,
    # Conditioning (P11) lengthens stints and recovery (P12) shortens rests: factor exp(k * (grade - 50) / 25).
    # Stand-ins (no direct evidence; both inputs are mostly position priors today).
    "k_conditioning": .20, "k_recovery": .20,
    # Tonight's tired legs (today's tip-off fatigue): above a day's-rest level (12), each point costs this share of the
    # plan and of stint length. FITTED to the real paired second-night gap (-0.60 minutes; fatigue about 18 vs 12).
    "fatigue_ref": 12.0, "fatigue_plan": .0033, "fatigue_stint": .01,
    # Players back from an absence (rust, or the minutes ramp) get shorter stints (stand-in, a minutes restriction).
    "rust_stint": .85,
    # Swapping: a rested bench player replaces the on-court player with the lowest claim when his own claim is higher by
    # this much (claim = share of the remaining time he must play to meet his plan), and only once that player has
    # played this share of his stint. FITTED with the stint numbers.
    "swap_margin": .30, "max_swaps": 2, "swap_stint_share": .85,
    # ... a rested starter may replace a bench player once that player has played this share of his stint (starters
    # rest about four to five minutes; the bench gives way to them).
    "swap_starter_share": .5,
    # A player who has played his plan leaves once he is this far past it (seconds), outside close finishes and
    # garbage time.
    "plan_over_s": 45.0,
    # Spot players: a plan under this many minutes (the 11th-13th men of a deep plan) plays only in garbage time or
    # when the coach is short (foul trouble, injuries); his minutes go to the rotation. Real teams give 10.8 players a
    # minute or more a night.
    "spot_min": 6.0,
    # Close finishes: the 4th quarter's last close_s seconds (and all of overtime) with the margin within close_margin:
    # the coach's five most-trusted players (largest plans) close, rested or not, and a player sitting in foul trouble
    # comes back for the last close_return_s seconds. FITTED to the real close-finish shares (starters .74 of the floor
    # time, stars .94).
    "close_s": 300.0, "close_margin": 8, "close_bonus": 3.0, "close_return_s": 180.0,
    # The four most-trusted always close; the 5th and 6th share the last spot (bonus close_bonus_56 each, so tonight's
    # plan decides between them). Real closing fives hold 3.7 starters on average; the exact starting five holds 20%.
    "close_bonus_56": 2.5,
    # ...and they are brought back for it: from the 7:00 timeout of the 4th with the game within approach_margin, the
    # closers are not taken off for a rest, and one who has sat approach_rest_s seconds may come back (claim bonus
    # approach_bonus). Real stars play about seven of the 4th quarter's twelve minutes.
    "approach_s": 420.0, "approach_margin": 12, "approach_bonus": 1.0, "approach_rest_s": 60.0,
    # Blowouts (4th quarter, live margin of blowout_margin or more): regulars who are sitting stay seated (the real
    # per-minute exits apply to those on the floor). From the last blowout_q3_s seconds of the 3rd quarter, a margin of
    # blowout_q3_margin or more starts the same exits (stand-in: the study's earliest window is 9:00 left in the 4th).
    "blowout_margin": 20, "blowout_q3_s": 180.0, "blowout_q3_margin": 25,
    # Garbage time (4th quarter): spot players come in once the margin is at least garbage_margin with garbage_s or less
    # left (or garbage_margin_big at any point of the quarter); players outside the planned rotation (generated games)
    # once it is reserve_margin with reserve_s left. Low-plan players get the first call. Stand-in thresholds mirroring
    # today's GARBAGE_EXTRAS_MIN (garbage time from a 15-20 point margin).
    "garbage_margin": 15, "garbage_s": 360.0, "garbage_margin_big": 22, "garbage_bonus": .6,
    "reserve_margin": 22, "reserve_s": 300.0,
    # Regulars (plan at or above this many minutes) are the ones who rest in blowouts (the real hazards are for
    # starters; core_share in game_minutes uses 14-32 minutes).
    "regular_min": 22.0,
    # Hot and cold hands: the plan moves by this many minutes per field-goal point per 10 minutes above (hot) or below
    # (cold) his own expected rate, once he has played enough to judge (judge_s). FITTED to real 2025-26 (regulars in
    # close games: slope +0.36 overall, mostly cold: -4 per 10 -> about -3.7 minutes, +4 -> about none).
    "k_hot": .10, "k_cold": .70, "heat_cap": 6.0, "judge_s": 600.0,
    # Stars: starters with a plan of 30+ minutes and a usage weight of .27+ (about 22 points a game at 30 minutes, the
    # rotation study's star definition).
    "star_minutes": 30.0, "star_usage": .27,
    # Replayed games (the betting test): tonight's plan is each player's real minutes, which already hold the real
    # game's garbage time and foul trouble. 1 = the coach keeps to them and decides only when each plays (no spot
    # players, no blowout exits or garbage time; foul-trouble pulls, rhythm, close finishes and hot hands stay);
    # 0 = the full in-game coach, as in generated games.
    "replay_faithful": 1.0,
}


def stint_key(fouls: int, period: int) -> str | None:
    """The rotation study's foul situation for a player's foul number `fouls` in `period`, or None."""
    if fouls == 2 and period == 1:
        return "2_Q1"
    if fouls == 3 and period <= 2:
        return "3_first_half"
    if fouls in (4, 5):
        return f"{fouls}_Q1_Q3" if period <= 3 else f"{fouls}_Q4_OT"
    return None


def margin_band(margin: int) -> str:
    m = abs(margin)
    if m <= 5:
        return "close_0_5"
    side = "ahead" if margin > 0 else "behind"
    if m <= 14:
        return f"{side}_6_14"
    if m <= 19:
        return f"{side}_15_19"
    if m <= 24:
        return f"{side}_20_24"
    return f"{side}_25_plus"


def q4_exit_per_minute(t_left: float, margin: int) -> float:
    """Real chance per minute that a starter on the floor leaves for good, at t_left seconds left in the 4th."""
    bucket = 9 if t_left > 450 else 6 if t_left > 270 else 3 if t_left > 120 else 1
    return Q4_EXIT[bucket][margin_band(margin)]


def garbage_now(c: dict, q4: bool, am: int, t_left: float, faithful: bool) -> bool:
    return not faithful and q4 and (am >= c["garbage_margin"] and t_left <= c["garbage_s"] or am >= c["garbage_margin_big"])


def _lognormal_draw(rng: random.Random, p25: float, p50: float, p75: float) -> float:
    """A draw with the given median and (on the log scale) the quartiles' spread."""
    sigma = max(.05, (math.log(max(p75, p50 + 1)) - math.log(max(1.0, p25))) / 1.349)
    return p50 * math.exp(sigma * rng.gauss(0.0, 1.0))


class Coach:
    """One team's in-game coach. `team` is the game's TeamState; the coach owns `team.on` changes."""

    def __init__(self, team, *, roles: list[str], plan_s: list[float], flats: list[dict], fatigue: list[float],
                 rust: list[bool], injury_exit: list[float | None], rng: random.Random, params: dict | None = None,
                 replay: bool = False):
        self.team = team
        self.c = dict(COACH, **(params or {}))
        c = self.c
        # Replayed games, faithful to the real minutes: the plan is what really happened.
        self.faithful = bool(replay and c["replay_faithful"])
        if self.faithful:
            c["spot_min"] = 0.0
        self.rng = rng
        self.n = n = len(roles)
        self.roles = roles
        self.base_plan = list(plan_s)
        f_ref = c["fatigue_ref"]
        self.plan = [p * (1.0 - c["fatigue_plan"] * max(0.0, fat - f_ref)) for p, fat in zip(plan_s, fatigue)]
        self.reserve = [r == "reserve" for r in roles]
        # Trust order for close finishes: the coach's largest plans (ties to starters).
        order = sorted(range(n), key=lambda i: (-plan_s[i], roles[i] not in ("star", "starter"), i))
        self.closers = set(order[:4])        # always close
        self.closers56 = set(order[4:6])     # share the fifth closing spot
        self.starters_set = set(team.starters)
        self.regular = [plan_s[i] >= c["regular_min"] * 60.0 for i in range(n)]
        self.core = [self.regular[i] or roles[i] in ("star", "starter") for i in range(n)]
        self.spot = [not self.reserve[i] and plan_s[i] < c["spot_min"] * 60.0 and roles[i] not in ("star", "starter")
                     for i in range(n)]
        self.stint_mean = []
        self.rest_min = []
        for i in range(n):
            flat = flats[i] or {}
            cond = math.exp(c["k_conditioning"] * (float(flat.get("P11", 50.0)) - 50.0) / 25.0)
            rec = math.exp(-c["k_recovery"] * (float(flat.get("P12", 50.0)) - 50.0) / 25.0)
            tired = 1.0 - c["fatigue_stint"] * max(0.0, fatigue[i] - f_ref)
            self.stint_mean.append(c[f"stint_{roles[i]}"] * cond * max(.5, tired) * (c["rust_stint"] if rust[i] else 1.0))
            self.rest_min.append(c[f"rest_{roles[i]}"] * rec)
        self.stint_len = [0.0] * n          # tonight's drawn length of his current stint
        self.off_since = [-1e9] * n          # game time (elapsed seconds) he last left the floor (-1e9: fresh)
        self.benched_until = [0.0] * n       # foul trouble: not before this game time (elapsed seconds)
        self.done = [False] * n              # out for the night (foul trouble, injury, six fouls)
        self.rested_out = [False] * n        # sat down for good in a blowout (back only if the game tightens again)
        self.injured = [False] * n
        self.exit_s = [None if e is None else max(1.0, float(e) * plan_s[i]) for i, e in enumerate(injury_exit)]
        # S2-TENTH: ... or once the game itself reaches that share of regulation, so a player who plays less than planned
        # (a blowout, foul trouble) still leaves hurt (before, about 15% of in-game injuries never showed as an exit).
        clock = c["injury_clock"]
        self.exit_game_s = [None if e is None or not clock else max(1.0, float(e) * 2880.0) for e in injury_exit]
        self.heat = [0.0] * n                # field-goal points above expectation so far
        self.pending = False                 # a forced change waits for the next stoppage
        self.last_elapsed = 0.0
        self.log: list | None = [] if TRACE else None   # research trace: (elapsed, five, margin) at each decision

    # ---- events from the game ------------------------------------------------------------------------------------
    def on_shot(self, i: int, points: int, expected: float) -> None:
        self.heat[i] += points - expected

    def on_foul(self, i: int, fouls: int, period: int, elapsed: float) -> None:
        """His foul number `fouls`: the coach may pull him (foul trouble), with the real chance and bench time."""
        if fouls >= 6:
            self.done[i] = True
            self.pending = True
            return
        key = stint_key(fouls, period)
        if key is None or self.reserve[i]:
            return
        role = self.roles[i] if self.roles[i] in FOUL_EXIT[key] else "bench"
        p = FOUL_EXIT[key][role]
        base = FOUL_BASE_EXIT[role]
        p_pull = max(0.0, (p - base) / (1.0 - base))
        rng = self.rng
        if rng.random() >= p_pull:
            return
        if rng.random() >= FOUL_RETURNED[key][role]:
            self.done[i] = True
        else:
            bench = _lognormal_draw(rng, *FOUL_BENCH[key][role])
            if key == "3_first_half" and role in ("star", "starter"):
                bench = max(bench, 1440.0 - elapsed)    # the starters' typical return: the start of the 3rd quarter
            self.benched_until[i] = elapsed + bench
        self.pending = True

    # ---- helpers ------------------------------------------------------------------------------------------------
    def _draw_stint(self, i: int, opening: bool = False) -> float:
        c = self.c
        if opening and self.roles[i] in ("star", "starter"):
            base = c[f"open_{self.roles[i]}"] * self.stint_mean[i] / c[f"stint_{self.roles[i]}"]
            return base * math.exp(c["open_sigma"] * self.rng.gauss(0.0, 1.0))
        return self.stint_mean[i] * math.exp(c["stint_sigma"] * self.rng.gauss(0.0, 1.0))

    def plan_now(self, i: int) -> float:
        """Tonight's plan for him, revised by how he is shooting (hot and cold hands)."""
        c = self.c
        secs = self.team.secs[i]
        plan = self.plan[i]
        if secs < 60.0 or plan <= 0:
            return plan
        rate = self.heat[i] / max(300.0, secs) * 600.0     # field-goal points per 10 minutes above his expectation
        rate = max(-c["heat_cap"], min(c["heat_cap"], rate))
        trust = min(1.0, secs / c["judge_s"])
        return plan + 60.0 * trust * rate * (c["k_hot"] if rate > 0 else c["k_cold"])

    # ---- the decision ---------------------------------------------------------------------------------------------
    def decide(self, *, period: int, t_left: float, elapsed: float, margin: int, period_start: bool) -> bool:
        """Choose the five for the next stretch. Returns True when the five changed."""
        team, c, rng = self.team, self.c, self.rng
        n = self.n
        secs, stint = team.secs, team.stint
        if not period_start and not self.pending and self._quiet(period, t_left, elapsed, margin):
            self.last_elapsed = elapsed
            return False
        dt_min = max(0.0, elapsed - self.last_elapsed) / 60.0
        self.last_elapsed = elapsed
        on = list(team.on)
        # Injuries: he leaves once he has played his share of the plan (or the game has reached that share).
        for i in range(n):
            if self.exit_s[i] is not None and not self.injured[i] and self._hurt_now(i, elapsed):
                self.injured[i] = self.done[i] = True
        q4 = period == 4
        regulation = period <= 4
        am = abs(margin)
        # Blowouts: each regular on the floor may leave for good, with the real per-minute chance for the time left and
        # the live margin (4th quarter; a 25-point game from late in the 3rd).
        faithful = self.faithful
        if not faithful and dt_min > 0 and (q4 and am >= 6
                                            or period == 3 and t_left <= c["blowout_q3_s"] and am >= c["blowout_q3_margin"]):
            p_min = q4_exit_per_minute(t_left if q4 else 720.0, margin)
            p = 1.0 - (1.0 - p_min) ** dt_min
            for i in on:
                if self.core[i] and not self.done[i] and not self.rested_out[i] and rng.random() < p:
                    self.rested_out[i] = True
        blowout = q4 and am >= c["blowout_margin"] and not faithful
        remaining = max(60.0, 2880.0 - elapsed) if regulation else max(60.0, t_left)
        close = not regulation or (q4 and t_left <= c["close_s"] and am <= c["close_margin"])
        approach = close or q4 and t_left <= c["approach_s"] and am <= c["approach_margin"]
        half_close = period in (2, 4) and t_left <= c["half_s"] and not garbage_now(c, q4, am, t_left, faithful)
        garbage = garbage_now(c, q4, am, t_left, faithful)
        reserves_in = q4 and am >= c["reserve_margin"] and t_left <= c["reserve_s"]
        out_fouled = team.out
        closers = self.closers
        starters_set = self.starters_set
        late_return = close and t_left <= c["close_return_s"]

        def available(i: int) -> bool:
            if i in out_fouled or self.done[i]:
                return False
            if self.rested_out[i] and not (approach and am <= c["close_margin"]):
                return False
            if self.benched_until[i] > elapsed and not (late_return and i in closers):
                return False
            if self.reserve[i]:
                return reserves_in
            if blowout and self.core[i] and i not in on:
                return False                 # sitting in a blowout: he stays seated
            return True

        plans = [self.plan_now(i) if regulation else self.plan[i] for i in range(n)]

        def claim(i: int) -> float:
            """How much he should be on the floor now: the share of the remaining time he must play to meet tonight's
            plan, plus close-finish trust and garbage-time order."""
            v = (plans[i] - secs[i]) / remaining
            if approach and i in closers:
                v += c["close_bonus"] if close else c["approach_bonus"]
            elif close and i in self.closers56:
                v += c["close_bonus_56"]
            elif half_close and i in starters_set:
                v += c["half_bonus"]
            if garbage and not self.core[i]:
                v += c["garbage_bonus"] * (1.0 - min(1.0, self.base_plan[i] / 2160.0))
            return v

        avail = [i for i in range(n) if available(i)]
        rotation = [i for i in avail if not self.spot[i] or garbage]
        if len(avail) < 5:
            # Short-handed: everyone who can play, then the least-bad of the rest (fouled out last).
            extra = sorted((i for i in range(n) if i not in avail and i not in out_fouled),
                           key=lambda i: (self.injured[i], -self.base_plan[i]))
            extra += [i for i in range(n) if i in out_fouled and i not in extra]
            return self._set((avail + extra)[:5], on, elapsed, margin)
        if period_start and (period in (1, 3) or not regulation):
            if period in (1, 3):
                first = [i for i in team.starters if i in avail]
            else:
                first = sorted((i for i in closers if i in avail), key=lambda i: -claim(i))
            new = first[:5]
            order = sorted(rotation, key=lambda i: (-claim(i), i)) + sorted(avail, key=lambda i: (-claim(i), i))
            for i in order:
                if len(new) < 5 and i not in new and self._fits(new, i):
                    new.append(i)
            for i in order:
                if len(new) < 5 and i not in new:
                    new.append(i)
            return self._set(new, on, elapsed, margin, opening=period in (1, 3))
        cl = {i: claim(i) for i in avail}
        off_since, rest_min, stint_len = self.off_since, self.rest_min, self.stint_len
        # Who must come off now.
        must = []
        for i in on:
            if i not in cl:
                must.append(i)               # fouled out, hurt, benched for fouls, done for the night
                continue
            if approach and i in closers:
                continue
            if garbage and not self.core[i]:
                continue
            if self.spot[i] and not garbage:
                must.append(i)               # a spot player goes back to the bench once he is not needed
                continue
            if stint[i] >= stint_len[i] or secs[i] > plans[i] + c["plan_over_s"] and not (q4 and am <= 12):
                must.append(i)
        keep = [i for i in on if i not in must]
        bench = [i for i in rotation if i not in on]
        rested = [i for i in bench if elapsed - off_since[i] >= rest_min[i]
                  or approach and i in closers and (close or elapsed - off_since[i] >= c["approach_rest_s"])]
        for i in must:
            pool = [j for j in rested if j not in keep]
            best = self._best(pool, keep, cl, prefer_group=team.groups[i])
            if best is None and i in cl and not self.spot[i]:
                keep.append(i)               # nobody rested to replace him: he plays on
                stint_len[i] = stint[i] + 60.0
                continue
            if best is None:
                pool = [j for j in avail if j not in keep]          # short: anyone available, spot players too
                best = self._best(pool, keep, cl, prefer_group=team.groups[i])
                if best is None:
                    if i in cl:
                        keep.append(i)
                    continue
            keep.append(best)
            if best in rested:
                rested.remove(best)
        # Voluntary swaps: a rested player with a clearly higher claim replaces the lowest claim on the floor, once
        # that player has played most of his stint (or is past his plan, or the game has turned close or garbage).
        for _ in range(int(c["max_swaps"])):
            cand = [j for j in rested if j not in keep]
            if not cand or len(keep) < 5:
                break
            j = max(cand, key=lambda j: (cl[j], -j))
            share_for = c["swap_starter_share"] if j in starters_set else c["swap_stint_share"]
            movable = [i for i in keep if i in cl and (
                stint[i] >= (share_for if i not in starters_set else c["swap_stint_share"]) * stint_len[i] or cl[i] < 0
                or approach or garbage or half_close and i not in starters_set) and not (approach and i in closers)]
            movable = [i for i in movable if self._fits([k for k in keep if k != i], j)]
            if not movable:
                break
            low = min(movable, key=lambda i: (cl[i], i))
            if cl[j] <= cl[low] + c["swap_margin"]:
                break
            keep = [i for i in keep if i != low] + [j]
            rested.remove(j)
        while len(keep) < 5:
            pool = [j for j in rotation if j not in keep] or [j for j in avail if j not in keep] \
                or [j for j in range(n) if j not in keep]
            best = self._best(pool, keep, cl, prefer_group=None)
            if best is None:
                break
            keep.append(best)
        return self._set(keep[:5], on, elapsed, margin)

    def _quiet(self, period: int, t_left: float, elapsed: float, margin: int) -> bool:
        """True when this stoppage cannot change the five: nobody on the floor is due off or far enough into his stint
        to be swapped, no injury is due, and the game is in no special state (4th-quarter margins, the end of a half,
        close finishes, garbage time). Skips the full decision at most stoppages; same choices either way."""
        c = self.c
        am = abs(margin)
        if period >= 4 or period == 2 and t_left <= c["half_s"] or period == 3 and t_left <= c["blowout_q3_s"] and am >= 20:
            return False
        team = self.team
        secs, stint = team.secs, team.stint
        for i in range(self.n):
            if self.exit_s[i] is not None and not self.injured[i] and self._hurt_now(i, elapsed):
                return False
        share = min(c["swap_stint_share"], c["swap_starter_share"])
        out = team.out
        for i in team.on:
            if (i in out or self.done[i] or self.rested_out[i] or self.benched_until[i] > elapsed or self.spot[i]
                    or stint[i] >= share * self.stint_len[i] or secs[i] > self.plan_now(i)):
                return False
        return True

    def _hurt_now(self, i: int, elapsed: float) -> bool:
        g = self.exit_game_s[i]
        return self.team.secs[i] >= self.exit_s[i] or (g is not None and elapsed >= g)

    def _fits(self, five: list[int], i: int) -> bool:
        groups = self.team.groups
        g = groups[i]
        if g == "big":
            return sum(groups[k] == "big" for k in five) < 3
        if g == "guard":
            return sum(groups[k] == "guard" for k in five) < 3
        return True

    def _best(self, pool: list[int], keep: list[int], cl: dict, prefer_group: str | None) -> int | None:
        best, best_v = None, -1e18
        groups = self.team.groups
        for j in pool:
            if not self._fits(keep, j):
                continue
            v = cl.get(j, -5.0) + (.05 if prefer_group is not None and groups[j] == prefer_group else 0.0)
            if v > best_v or v == best_v and best is not None and j < best:
                best, best_v = j, v
        if best is None and pool:
            best = max(pool, key=lambda j: (cl.get(j, -5.0), -j))
        return best

    def _set(self, new: list[int], on: list[int], elapsed: float, margin: int = 0, opening: bool = False) -> bool:
        team = self.team
        self.pending = False
        if self.log is not None:
            self.log.append((round(elapsed, 1), tuple(sorted(new)), margin))
        if opening:
            for i in new:                    # each half opens with fresh stints (halftime reset the counters)
                team.stint[i] = 0.0
                self.stint_len[i] = self._draw_stint(i, True)
        if set(new) == set(on) and len(new) == len(on):
            return False
        new_set = set(new)
        for i in on:
            if i not in new_set:
                team.stint[i] = 0.0
                self.off_since[i] = elapsed
        for i in new:
            if i not in on and not opening:
                team.stint[i] = 0.0
                self.stint_len[i] = self._draw_stint(i)
        team.on = sorted(new)                # a fixed order per five (the game caches each five's numbers)
        team.lineup_dirty = True
        return True

    def new_half(self) -> None:
        """Halftime: everyone is fresh; stints start over (the starters open the 3rd)."""
        for i in range(self.n):
            self.team.stint[i] = 0.0
            self.off_since[i] = -1e9

    def quarter_break(self, seconds: float = 60.0) -> None:
        """The 1st-2nd and 3rd-4th quarter breaks: a short breather for those on the floor."""
        for i in self.team.on:
            self.team.stint[i] = max(0.0, self.team.stint[i] - seconds)


def roles_for(starter_flags: list[bool], plans_min: list[float], usage: list[float], reserve: list[bool],
              params: dict | None = None) -> list[str]:
    """Tonight's roles: stars (starters with a big plan and high usage), starters, the sixth man (the bench player
    with the largest plan), bench, and reserves (outside the planned rotation; garbage time only)."""
    c = dict(COACH, **(params or {}))
    n = len(plans_min)
    roles = ["bench"] * n
    for i in range(n):
        if reserve[i]:
            roles[i] = "reserve"
        elif starter_flags[i]:
            roles[i] = "star" if plans_min[i] >= c["star_minutes"] and usage[i] >= c["star_usage"] else "starter"
    bench = [i for i in range(n) if roles[i] == "bench"]
    if bench:
        roles[max(bench, key=lambda i: (plans_min[i], -i))] = "sixth_man"
    return roles
