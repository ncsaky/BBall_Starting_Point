"""Stage 2 whole-game loop: possessions, a game clock, team fouls and the bonus, live substitutions, box scores.

One game = four 12-minute quarters (plus 5-minute overtimes while tied). Each possession:
1. it starts from how the last one ended (defensive rebound, steal, made basket, dead ball); the start, the lineup's
   pace habit (T05) and transition habit (T17) set the chance it is a transition possession and how long it lasts;
2. a non-shooting foul may come first (side out; two free throws once the offense is in the bonus);
3. the finisher: the player who ends it, drawn by usage weight among the five (cards.USAGE);
4. a turnover (his turnover log-odds plus the defense's ball pressure), which may be a steal or an offensive foul;
5. otherwise a shot from his action menu (drive, roll/cut, post-up, jumper, pull-up; transition or putback when the
   possession calls for one): the action sets the shot zone, the make chance (his own conversion for that shot, the
   defense's contest or rim protection), the shooting-foul chance (stage2.fouls with an action term), the assist
   chance and the miss type;
6. a missed shot (or last free throw) goes to the rebound kernel (stage2.rebounding); an offensive rebound continues
   the possession (an immediate putback or a reset).
The clock runs through every segment; team fouls count per quarter (bonus from the 5th, or the 2nd in the last two
minutes). Substitutions follow tonight's planned minutes (today's minutes model) with live foul trouble, fatigue
stints, foul-outs and blowout rest.

No rating is moved here; the loop's own numbers are in LOOP (fitted to league targets where marked).
"""
from __future__ import annotations

import math
import random
from typing import Any

from . import fouls as F
from . import rebounding as R
from .cards import KINDS, KIND_INDEX, N_KINDS, Card

VERSION = "stage2_possession_loop_v1_2026_11_21"

KZONE = [k[2] for k in KINDS]
KMISS = [k[3] for k in KINDS]
KPTS = [k[4] for k in KINDS]
KACTION = [k[1] for k in KINDS]
PUTBACK = KIND_INDEX["putback"]
HEAVE = KIND_INDEX["heave"]
JUMPER_KINDS = frozenset(KIND_INDEX[k] for k in ("short_jumper", "mid_catch", "mid_pull", "three_corner", "three_catch",
                                                  "three_pull", "trans_three", "heave"))

# The loop's own numbers. FITTED = set against the 2025-26 league targets (data/calibration/nba_2025_26_targets.json)
# with the calibration report; the rest are documented stand-ins.
LOOP = {
    # Possession length (seconds). Half court: a floor plus a gamma tail; scaled by pace habit and coach tempo. FITTED
    # (league pace 102.0 possessions per 48 minutes).
    "hc_floor": 5.0, "hc_mean": 15.6, "hc_shape": 2.6, "trans_floor": 2.5, "trans_mean": 6.0, "reset_floor": 2.0,
    "reset_mean": 8.0, "putback_s": 2.0, "sideout_s": 3.5, "k_pace": 1.2, "tempo_scale": .01,
    # Transition chance by how the possession started, times the lineup's transition habit.
    "trans_dreb": .20, "trans_steal": .60, "trans_made": .04, "trans_dead": .06, "k_trans": 1.5,
    # Turnovers: the defense's ball pressure (log-odds per index unit); transition and offensive-foul shares.
    # k_press is FITTED with the other team-strength terms below.
    "k_press": .80, "trans_to": -.15, "off_foul_share": .08, "steal_share": .62, "k_steal_level": 1.0,
    "to_shift": .13,   # FITTED: league turnovers per 100 (the card fit is per used possession; the loop's are per chance)
    # Non-shooting fouls per possession (league level, then the defenders' own multipliers); technicals etc.
    "ns_per_poss": .068, "other_ft_per_poss": .005, "loose_ball_per_chance": .032,
    # Shooting fouls: action terms on top of the foul kernel's zone base (log-odds). Drives draw the most contact,
    # rolls, cuts and putbacks less, catch jumpers least. Stand-ins checked against FTA per FGA.
    "foul_drive": .30, "foul_roll_cut": -.35, "foul_post": .25, "foul_putback": -.30, "foul_transition": .10,
    "foul_jumper": -.15, "foul_pull_up": .05,
    # Team-strength terms (make log-odds per index unit; each index is centred on the league's average lineup):
    # defense: perimeter contest on jumpers (half the shooter's own defender, half the lineup), rim protection on rim
    # and short shots, ball pressure on turnovers (k_press above); offense: the lineup's creation and spacing.
    # FITTED together (coordinate search, scratch strength_fit) so the engine's expected margins follow the betting
    # market's spreads on the first half of 2025-26 (correlation .42 -> .57 at 3 runs a game, slope 1.04); checked on
    # the second half (.67, slope 1.24). They decide how much the ratings move results; no rating was changed.
    "k_perim": .36, "k_rim": .45, "perim_own": .5, "k_create": .44, "k_space": .29,
    # Blocks per missed shot by zone (at the league-average block weight); share credited to the help (rim) defender.
    "blk_rim": .277, "blk_short": .21, "blk_mid": .065, "blk_three": .02,
    # Assisted share of made shots by action (scaled to the league assist rate). FITTED scale.
    "ast_scale": 1.07,
    # Shooting-foul level on two-point shots on top of the kernel's zone base (FITTED: league free throws per 100).
    "foul_level": .22,
    # Game-level contest by zone (rim, short, mid, three), make log-odds: the shooting conversion was fitted at the
    # kernel's fixed reference contest; this sets the in-game average. FITTED to the league make rates by zone
    # (Basketball Index 2025-26: rim 67.4, short mid 44.8, long mid 41.7, three 36.1).
    "zone_make": (-.19, -.18, 0.0, 0.0),
    # After an offensive rebound: chance of an immediate putback by the rebounder (rim / short misses vs others).
    "putback_close": .50, "putback_far": .20,
    # Points per 100 -> make log-odds (home court, coaches, rest).
    "k_eff": .02,
    # Score effects: per point of lead (capped at 25), the leading team's shots lose this much make log-odds (effort,
    # garbage-time lineups, the trailing team's urgency). Without it the margin around the engine's own expectation
    # varied 17.4 points (today's engine 13.1; real margins vary about 14.1 around the market spread). FITTED to that.
    "k_lead": .008,
    # Heave chance when under 3 s remain at the start of a possession.
    "heave": .45,
    # Share of rebounds credited to no player (team rebounds). FITTED: rotation players' rebounds per 36 ran 1.0 high
    # (about 13%) with every rebound credited.
    "team_rebound": .11,
    # The finisher is drawn by usage weight to this power: the weight is fitted to each player's usage on its own, but
    # a share among five teammates (plus the possessions that end on putbacks and drawn fouls) flattens it. FITTED to
    # real per-player shot volume (stars' and bench players' FGA per 36 in replayed games).
    "usage_power": 1.3,
}
ASSIST = {"rim_drive": .18, "rim_finish": .93, "floater": .15, "hook": .30, "short_jumper": .40, "mid_catch": .90,
          "mid_pull": .07, "three_corner": .97, "three_catch": .92, "three_pull": .06, "putback": .04,
          "trans_rim": .55, "trans_three": .85, "heave": 0.0}
ASSIST_BY_KIND = [ASSIST[k[0]] for k in KINDS]
FOUL_ACTION = {"drive": "foul_drive", "roll_cut": "foul_roll_cut", "post": "foul_post", "putback": "foul_putback",
               "transition": "foul_transition", "jumper": "foul_jumper", "pull_up": "foul_pull_up", "heave": None}
QUARTER_S, OT_S = 720.0, 300.0
SUB_TIMES = (540.0, 360.0, 180.0)   # in-quarter checkpoints (seconds left), like the usual stoppages
FOUL_TROUBLE = {1: 2, 2: 3, 3: 4, 4: 5}
STAT_KEYS = ("points", "fgm", "fga", "fg3m", "fg3a", "ftm", "fta", "orb", "drb", "ast", "tov", "stl", "blk", "pf",
             "rim_att", "pm")
(S_PTS, S_FGM, S_FGA, S_3PM, S_3PA, S_FTM, S_FTA, S_ORB, S_DRB, S_AST, S_TOV, S_STL, S_BLK, S_PF, S_RIM, S_PM) = range(16)


class TeamState:
    """One team's side of the game: its players' cards, minutes plan, live lineup and box score."""

    def __init__(self, team_id: str, abbrev: str, cards: list[Card], targets: list[float], starters: list[int],
                 groups: list[str], eff: float, tempo: float, league: dict, eff_def: float = 0.0):
        self.team_id, self.abbrev = team_id, abbrev
        self.cards = cards
        n = len(cards)
        total = sum(targets) or 1.0
        self.target_s = [2880.0 * 5 * t / total for t in targets]   # regulation seconds, summing to 5 x 48 minutes
        self.starters = starters
        self.groups = groups
        self.secs = [0.0] * n
        self.stint = [0.0] * n
        self.stats = [[0] * 16 for _ in range(n)]
        self.out: set[int] = set()            # fouled out (or unavailable)
        self.on: list[int] = []
        self.team_fouls = 0
        self.fouls_late = 0
        self.eff = eff            # offense make log-odds term (home court, coach offense, rest)
        self.eff_def = eff_def    # defense term subtracted from the opponent's make log-odds (coach defense)
        self.tempo = tempo
        self.points = 0
        self.possessions = 0
        self.league = league
        self.loop: dict | None = None     # the game's loop numbers (set by Game)
        self.lineup_dirty = True

    # ---- lineup aggregates (recomputed when the five change) ------------------------------------------------------
    def refresh(self) -> None:
        cs = [self.cards[i] for i in self.on]
        lg = self.league
        gamma = (LOOP if self.loop is None else self.loop)["usage_power"]
        self.usage_cum = _cum([c.usage ** gamma for c in cs])
        self.ast_w = [c.ast_w for c in cs]
        self.reb = [c.reb for c in cs]
        self.reb_prof = [c.reb.profile for c in cs]
        self.pace = sum(c.pace for c in cs) / 5.0
        self.trans_pref = sum(c.trans_pref for c in cs) / 5.0
        self.perim = sum(c.perim_d for c in cs) / 5.0 - lg["perim_mean"]
        self.perim_center = lg["perim_mean"]
        # Offense: the lineup's creation (handling, separation, attack reads, passing delivery) and spacing (three-point
        # threat) make every teammate's shot a little easier (log-odds; centred on the league's average lineup).
        self.create = sum(c.create for c in cs) / 5.0 - lg["create_center"]
        self.space = sum(c.space for c in cs) / 5.0 - lg["space_center"]
        L = LOOP if self.loop is None else self.loop
        self.off_shift = L["k_create"] * self.create + L["k_space"] * self.space
        rims = sorted((c.rim_d for c in cs), reverse=True)
        self.rim = .6 * rims[0] + .4 * sum(rims) / 5.0 - lg["rim_center"]
        self.press = sum(c.press_d for c in cs) / 5.0 - lg["press_center"]
        self.stl_level = (sum(c.stl_w for c in cs) / 5.0) / lg["stl_mean"]
        self.blk_level = (sum(c.blk_w for c in cs) / 5.0) / lg["blk_mean"]
        self.ns_level = (sum(c.ns_mult for c in cs) / 5.0) / lg["ns_mean"]
        self.ns_draw_cum = _cum([c.ns_draw for c in cs])
        self.off_foul_cum = _cum([c.off_foul_w for c in cs])
        self.help = max(range(5), key=lambda j: cs[j].rim_d)
        self.lineup_dirty = False

    def in_bonus_against(self, t_left: float) -> bool:
        """True when this team's fouls put the OPPONENT in the bonus."""
        return self.team_fouls >= 5 or (t_left <= 120.0 and self.fouls_late >= 2)


def _cum(weights: list[float]) -> list[float]:
    total = sum(weights) or 1.0
    acc, out = 0.0, []
    for w in weights:
        acc += w / total
        out.append(acc)
    out[-1] = 1.0
    return out


def _pick(cum: list[float], u: float) -> int:
    for i, c in enumerate(cum):
        if u <= c:
            return i
    return len(cum) - 1


def _sig(z: float) -> float:
    if z < -30:
        return 0.0
    return 1.0 / (1.0 + math.exp(-z))


class Game:
    def __init__(self, home: TeamState, away: TeamState, rng: random.Random, foul_c: F.FoulCoefficients = F.FITTED,
                 reb_c: R.ReboundCoefficients = R.FITTED, loop: dict | None = None):
        self.home, self.away = home, away
        self.rng = rng
        self.fc = foul_c
        self.rc = reb_c
        self.L = dict(LOOP, **(loop or {}))
        L = self.L
        home.loop = away.loop = L
        self.foul_action = [(L[FOUL_ACTION[a]] if FOUL_ACTION.get(a) else 0.0) + (L["foul_level"] if KZONE[i] < 3 else 0.0)
                            for i, a in enumerate(KACTION)]
        self.assist = [a * L["ast_scale"] for a in ASSIST_BY_KIND]
        self.zone_make = [0.0 if KINDS[i][0] == "heave" else L["zone_make"][KZONE[i]] for i in range(N_KINDS)]
        self.blk_base = (L["blk_rim"], L["blk_short"], L["blk_mid"], L["blk_three"])
        self.period = 0
        self.t_left = QUARTER_S
        self.events = 0
        self.diag = [0] * (N_KINDS * 3)   # per shot kind: attempts (FGA), makes, shooting fouls
        self.lg_pace = home.league["pace_mean"]
        self.lg_trans = home.league["trans_mean"]

    # ---- substitutions -------------------------------------------------------------------------------------------
    def substitutions(self, team: TeamState, opp: TeamState, *, period_start: bool = False) -> None:
        """The coach's five for the next stretch: who is owed the most of his planned minutes, kept on for continuity,
        rested after a long stint, benched in foul trouble or a blowout; starters open each half."""
        n = len(team.cards)
        avail = [i for i in range(n) if i not in team.out]
        if len(avail) <= 5:
            team.on = avail[:5] if len(avail) >= 5 else avail + [i for i in range(n) if i not in avail][:5 - len(avail)]
            team.lineup_dirty = True
            return
        period = self.period
        game_left = max(1.0, (4 - period) * QUARTER_S + self.t_left) if period <= 4 else self.t_left
        margin = team.points - opp.points
        blowout = period >= 4 and ((abs(margin) >= 20 and self.t_left <= 360) or (abs(margin) >= 26 and self.t_left <= 540))
        top = sorted(range(n), key=lambda i: -team.target_s[i])[:6]
        pri = {}
        for i in avail:
            if period > 4:
                p = team.target_s[i] / 2880.0
            else:
                owed = team.target_s[i] - team.secs[i]
                p = owed / game_left
            if i in team.on:
                p += .10
                cap = 360.0 + 420.0 * min(1.0, team.target_s[i] / 2160.0)   # longest stint: 6-13 minutes
                if team.stint[i] > cap and period <= 4:
                    p -= .45
            if period <= 4 and team.stats[i][S_PF] >= FOUL_TROUBLE[min(4, period)] and not (period == 4 and self.t_left < 300):
                p -= .6
            if blowout and i in top:
                p -= 2.0
            if period_start and period in (1, 3) and i in team.starters and team.stats[i][S_PF] < FOUL_TROUBLE[period]:
                p += 5.0
            pri[i] = p
        order = sorted(avail, key=lambda i: (-pri[i], i))
        chosen: list[int] = []
        bigs = guards = 0
        for i in order:
            g = team.groups[i]
            if g == "big" and bigs >= 3 or g == "guard" and guards >= 3:
                continue
            chosen.append(i)
            bigs += g == "big"
            guards += g == "guard"
            if len(chosen) == 5:
                break
        for i in order:
            if len(chosen) == 5:
                break
            if i not in chosen:
                chosen.append(i)
        new = set(chosen)
        if set(team.on) != new:
            for i in team.on:
                if i not in new:
                    team.stint[i] = 0.0
            for i in new:
                if i not in team.on:
                    team.stint[i] = 0.0
            team.on = chosen
            team.lineup_dirty = True

    def _matchups(self) -> None:
        for off, de in ((self.home, self.away), (self.away, self.home)):
            if off.lineup_dirty:
                off.refresh()
            if de.lineup_dirty:
                de.refresh()
        for off, de in ((self.home, self.away), (self.away, self.home)):
            guards = R.matchups(off.reb_prof, de.reb_prof)      # defender slot -> offensive slot
            inv = [0] * 5
            for j, i in enumerate(guards):
                inv[i] = j
            off.guards_vs = guards     # used when `off` is on offense
            off.defender_of = inv

    # ---- clock ---------------------------------------------------------------------------------------------------
    def _run_clock(self, seconds: float) -> None:
        seconds = min(seconds, self.t_left)
        for team in (self.home, self.away):
            for i in team.on:
                team.secs[i] += seconds
                team.stint[i] += seconds
        before = self.t_left
        self.t_left -= seconds
        if before > 120.0 >= self.t_left:
            # The last-two-minutes foul count starts fresh.
            self.home.fouls_late = self.away.fouls_late = 0

    def _duration(self, kind: str, off: TeamState) -> float:
        L, rng = self.L, self.rng
        if kind == "trans":
            return L["trans_floor"] + rng.gammavariate(2.0, (L["trans_mean"] - L["trans_floor"]) / 2.0)
        if kind == "reset":
            return L["reset_floor"] + rng.gammavariate(2.0, (L["reset_mean"] - L["reset_floor"]) / 2.0)
        mean = (L["hc_mean"] - L["hc_floor"]) * math.exp(-L["k_pace"] * (off.pace - self.lg_pace)) * (1.0 - L["tempo_scale"] * off.tempo)
        return min(23.5, L["hc_floor"] + rng.gammavariate(L["hc_shape"], mean / L["hc_shape"]))

    # ---- scoring helpers -----------------------------------------------------------------------------------------
    def _score(self, off: TeamState, de: TeamState, slot: int, pts: int) -> None:
        off.points += pts
        off.stats[off.on[slot]][S_PTS] += pts
        for i in off.on:
            off.stats[i][S_PM] += pts
        for i in de.on:
            de.stats[i][S_PM] -= pts

    def _foul(self, de: TeamState, slot: int, *, team_foul: bool = True) -> None:
        i = de.on[slot]
        de.stats[i][S_PF] += 1
        if team_foul:
            de.team_fouls += 1
            if self.t_left <= 120.0:
                de.fouls_late += 1
        if de.stats[i][S_PF] >= 6:
            de.out.add(i)
            self.pending_sub = True

    def _free_throws(self, off: TeamState, de: TeamState, slot: int, n: int) -> bool:
        """n free throws by the offensive player in `slot`; True if the last one is made."""
        card = off.cards[off.on[slot]]
        st = off.stats[off.on[slot]]
        made = False
        for _ in range(n):
            st[S_FTA] += 1
            made = self.rng.random() < card.ft
            if made:
                st[S_FTM] += 1
                self._score(off, de, slot, 1)
        return made

    def _rebound(self, off: TeamState, de: TeamState, miss: str, shooter: int) -> tuple[bool, int]:
        probs = R.rebound_probabilities(off.reb, de.reb, off.guards_vs, miss, shooter, self.rc)
        u = self.rng.random()
        acc = 0.0
        k = 9
        for idx, p in enumerate(probs):
            acc += p
            if u <= acc:
                k = idx
                break
        # Loose-ball foul in the scramble (committed by the side that lost it), shared by rebound chance.
        if self.rng.random() < self.L["loose_ball_per_chance"]:
            if k < 5:
                j = max(range(5), key=lambda jj: probs[5 + jj] * (1 + self.rng.random()))
                self._foul(de, j)
                if de.in_bonus_against(self.t_left):
                    self._free_throws(off, de, k, 2)
            else:
                i = max(range(5), key=lambda ii: probs[ii] * (1 + self.rng.random()))
                self._foul(off, i)
        # Team rebounds (out of bounds off a player, tie-ups, shot-clock and end-of-period misses) go to the side that
        # won the ball but to no player, as in the real box score.
        credit = self.rng.random() >= self.L["team_rebound"]
        if k < 5:
            if credit:
                off.stats[off.on[k]][S_ORB] += 1
            return True, k
        if credit:
            de.stats[de.on[k - 5]][S_DRB] += 1
        return False, k - 5

    # ---- one possession ------------------------------------------------------------------------------------------
    def possession(self, off: TeamState, de: TeamState, start: str) -> str:
        """Plays one possession (until the defense gains the ball or the period ends). Returns how it ended:
        'made', 'dreb', 'steal', 'dead' or 'end'."""
        L, rng = self.L, self.rng
        off.possessions += 1
        # Technical / flagrant / clear-path free throws (no possession change): the best free-throw shooter on court.
        if rng.random() < L["other_ft_per_poss"]:
            slot = max(range(5), key=lambda s: off.cards[off.on[s]].ft)
            self._free_throws(off, de, slot, 1)
        p_trans = {"dreb": L["trans_dreb"], "steal": L["trans_steal"], "made": L["trans_made"]}.get(start, L["trans_dead"])
        p_trans *= math.exp(L["k_trans"] * (off.trans_pref - self.lg_trans))
        trans = rng.random() < p_trans
        seg = self._duration("trans" if trans else "half", off)
        final = False
        if seg >= self.t_left:
            if self.t_left < 3.0:
                left = self.t_left
                self._run_clock(left)
                if rng.random() < L["heave"]:
                    slot = _pick(off.usage_cum, rng.random())
                    return self._shot(off, de, slot, HEAVE, final=True)
                return "end"
            seg = max(.5, self.t_left - rng.random() * 1.5)
            final = True
        # Non-shooting fouls before the shot (side out; free throws in the bonus).
        if not trans:
            for _ in range(2):
                if rng.random() >= L["ns_per_poss"] * de.ns_level:
                    break
                drawer = _pick(off.ns_draw_cum, rng.random())
                d_cards = [de.cards[i] for i in de.on]
                guard = off.defender_of[drawer]
                w = [c.ns_mult * (3.0 if j == guard else 1.0) for j, c in enumerate(d_cards)]
                fouler = _pick(_cum(w), rng.random())
                self._run_clock(min(seg * .5, self.t_left))
                bonus = de.in_bonus_against(self.t_left)
                self._foul(de, fouler)
                if bonus:
                    made = self._free_throws(off, de, drawer, 2)
                    if made:
                        return "made"
                    return self._after_miss(off, de, "ft", drawer)
                seg = max(1.0, seg * .5 + L["sideout_s"] * rng.random())
                if seg >= self.t_left:
                    seg = max(.3, self.t_left - .2)
                    final = True
        self._run_clock(seg)
        # Who ends it, and does he turn it over?
        slot = _pick(off.usage_cum, rng.random())
        card = off.cards[off.on[slot]]
        z = card.to_logit + L["to_shift"] + L["k_press"] * de.press + (L["trans_to"] if trans else 0.0)
        if rng.random() < _sig(z):
            return self._turnover(off, de, slot)
        kind = _pick(card.trans_cum if trans else card.menu_cum, rng.random())
        return self._shot(off, de, slot, kind, final=final)

    def _turnover(self, off: TeamState, de: TeamState, slot: int) -> str:
        L, rng = self.L, self.rng
        if rng.random() < L["off_foul_share"]:
            who = _pick(off.off_foul_cum, rng.random())
            off.stats[off.on[who]][S_TOV] += 1
            self._foul(off, who, team_foul=False)
            return "dead"
        off.stats[off.on[slot]][S_TOV] += 1
        p_steal = L["steal_share"] * de.stl_level ** L["k_steal_level"]
        if rng.random() < p_steal:
            guard = off.defender_of[slot]
            w = [de.cards[i].stl_w * (2.5 if j == guard else 1.0) for j, i in enumerate(de.on)]
            j = _pick(_cum(w), rng.random())
            de.stats[de.on[j]][S_STL] += 1
            return "steal"
        return "dead"

    def _shot(self, off: TeamState, de: TeamState, slot: int, kind: int, *, final: bool = False,
              putback: bool = False) -> str:
        L, rng, fc = self.L, self.rng, self.fc
        card = off.cards[off.on[slot]]
        st = off.stats[off.on[slot]]
        zone = KZONE[kind]
        j = off.defender_of[slot]
        dcard = de.cards[de.on[j]]
        # Make chance: his conversion for this shot, the defense's contest or rim protection, team terms.
        lead = off.points - de.points
        z = (card.make_logit[kind] + self.zone_make[kind] + off.eff + off.off_shift - de.eff_def
             - L["k_lead"] * (25 if lead > 25 else -25 if lead < -25 else lead))
        if kind in JUMPER_KINDS:
            z -= L["k_perim"] * (L["perim_own"] * (dcard.perim_d - de.perim_center) + (1 - L["perim_own"]) * de.perim)
        elif zone <= 1:
            z -= L["k_rim"] * de.rim
        p_make = _sig(z)
        # Shooting foul: the foul kernel's zone base, the shooter's and contester's terms, plus the action.
        if kind != HEAVE:
            p_foul = _sig(fc.base[zone] + card.foul_s + dcard.d_foul + self.foul_action[kind])
        else:
            p_foul = 0.0
        if zone == 0:
            st[S_RIM] += 1
        if rng.random() < p_foul:
            self._foul(de, j)
            self.diag[3 * kind + 2] += 1
            if rng.random() < card.and1[zone] * (p_make / max(.05, _sig(card.make_logit[kind]))):
                st[S_FGA] += 1          # a made shot through a foul counts as an attempt (and-one)
                self.diag[3 * kind] += 1
                self.diag[3 * kind + 1] += 1
                if zone == 3:
                    st[S_3PA] += 1
                self._record_make(off, de, slot, kind)
                made_ft = self._free_throws(off, de, slot, 1)
                return "made" if made_ft else self._after_miss(off, de, "ft", slot)
            made_ft = self._free_throws(off, de, slot, 3 if zone == 3 else 2)
            return "made" if made_ft else self._after_miss(off, de, "ft", slot)
        st[S_FGA] += 1
        self.diag[3 * kind] += 1
        if zone == 3:
            st[S_3PA] += 1
        if rng.random() < p_make:
            self.diag[3 * kind + 1] += 1
            self._record_make(off, de, slot, kind)
            return "made"
        # Block (on the miss)
        if rng.random() < self.blk_base[zone] * de.blk_level:
            w = [de.cards[i].blk_w * (2.0 if jj == j else 1.0) * (1.5 if jj == de.help else 1.0) for jj, i in enumerate(de.on)]
            b = _pick(_cum(w), rng.random())
            de.stats[de.on[b]][S_BLK] += 1
        if final and self.t_left <= 0.0:
            return "end"
        return self._after_miss(off, de, KMISS[kind], slot)

    def _record_make(self, off: TeamState, de: TeamState, slot: int, kind: int) -> None:
        st = off.stats[off.on[slot]]
        st[S_FGM] += 1
        pts = KPTS[kind]
        if pts == 3:
            st[S_3PM] += 1
        self._score(off, de, slot, pts)
        if self.rng.random() < self.assist[kind]:
            w = [w if s != slot else 0.0 for s, w in enumerate(off.ast_w)]
            a = _pick(_cum(w), self.rng.random())
            off.stats[off.on[a]][S_AST] += 1

    def _after_miss(self, off: TeamState, de: TeamState, miss: str, shooter: int) -> str:
        if self.t_left <= 0.0:
            return "end"
        offensive, k = self._rebound(off, de, miss, shooter)
        if not offensive:
            return "dreb"
        L, rng = self.L, self.rng
        close = miss in ("rim", "short")
        if rng.random() < (L["putback_close"] if close else L["putback_far"]):
            self._run_clock(min(L["putback_s"] * (.5 + rng.random()), self.t_left))
            if self.t_left <= 0.0:
                return "end"
            return self._shot(off, de, k, PUTBACK, putback=True)
        seg = self._duration("reset", off)
        final = False
        if seg >= self.t_left:
            if self.t_left < 1.0:
                self._run_clock(self.t_left)
                return "end"
            seg = max(.3, self.t_left - rng.random())
            final = True
        self._run_clock(seg)
        slot = _pick(off.usage_cum, rng.random())
        card = off.cards[off.on[slot]]
        if rng.random() < _sig(card.to_logit + L["to_shift"] + L["k_press"] * de.press):
            return self._turnover(off, de, slot)
        kind = _pick(card.menu_cum, rng.random())
        return self._shot(off, de, slot, kind, final=final)

    # ---- the game ------------------------------------------------------------------------------------------------
    def play(self) -> None:
        rng = self.rng
        home, away = self.home, self.away
        tip = home if rng.random() < .5 else away
        other = away if tip is home else home
        self.pending_sub = False
        period = 0
        while True:
            period += 1
            self.period = period
            self.t_left = QUARTER_S if period <= 4 else OT_S
            home.team_fouls = away.team_fouls = 0
            home.fouls_late = away.fouls_late = 0
            # Q1 and OT: tip winner; Q2-Q3: the other team; Q4: tip winner (NBA rule).
            off = tip if period in (1, 4) or period > 4 else other
            if period > 4:
                off = home if rng.random() < .5 else away
            de = away if off is home else home
            for t in (home, away):
                self.substitutions(t, away if t is home else home, period_start=True)
            self._matchups()
            start = "dead"
            checkpoints = [s for s in SUB_TIMES if s < self.t_left]
            while self.t_left > 0.0:
                result = self.possession(off, de, start)
                self.events += 1
                if result == "end" or self.t_left <= 0.0:
                    break
                crossed = checkpoints and self.t_left <= checkpoints[0]
                if crossed:
                    while checkpoints and self.t_left <= checkpoints[0]:
                        checkpoints.pop(0)
                if crossed or self.pending_sub or self._trouble(off) or self._trouble(de):
                    self.pending_sub = False
                    for t in (home, away):
                        self.substitutions(t, away if t is home else home)
                    self._matchups()
                elif off.lineup_dirty or de.lineup_dirty:
                    self._matchups()
                start = {"made": "made", "dreb": "dreb", "steal": "steal"}.get(result, "dead")
                off, de = de, off
            if period >= 4 and home.points != away.points:
                break
            if period >= 14:
                break

    def _trouble(self, team: TeamState) -> bool:
        lim = FOUL_TROUBLE.get(min(4, self.period), 6)
        if self.period == 4 and self.t_left < 300:
            return False
        return any(team.stats[i][S_PF] >= lim and team.stats[i][S_PF] >= 2 for i in team.on) and self.rng.random() < .5


def box_lines(team: TeamState, players: list[dict[str, Any]], items: list[dict[str, Any]], team_abbrev: str,
              starter_ids: set[str]) -> list[dict[str, Any]]:
    """Today's player-line format from the game's box score."""
    out = []
    for i, item in enumerate(items):
        st = team.stats[i]
        p = players[i]
        out.append({
            "player_id": p["id"], "player_name": p["name"], "team_id": team.team_id, "team_abbrev": team_abbrev,
            "minutes": round(team.secs[i] / 60.0, 2),
            "health_status": item.get("health_status", "actual_or_untracked"),
            "health_fatigue": round(float(item.get("health_fatigue") or 0), 2),
            "health_rust": round(float(item.get("health_rust") or 0), 2),
            "points": st[S_PTS], "fgm": st[S_FGM], "fga": st[S_FGA], "fg3m": st[S_3PM], "fg3a": st[S_3PA],
            "ftm": st[S_FTM], "fta": st[S_FTA], "rim_attempts": st[S_RIM],
            "rebounds": st[S_ORB] + st[S_DRB], "offensive_rebounds": st[S_ORB], "defensive_rebounds": st[S_DRB],
            "assists": st[S_AST], "turnovers": st[S_TOV], "steals": st[S_STL], "blocks": st[S_BLK],
            "personal_fouls": st[S_PF], "plus_minus": st[S_PM], "starter": p["id"] in starter_ids,
            **({"fouled_out": True} if st[S_PF] >= 6 else {}),
        })
    return out


def team_line(team: TeamState, lines: list[dict[str, Any]], opp: TeamState) -> dict[str, Any]:
    keys = ("points", "fgm", "fga", "fg3m", "fg3a", "ftm", "fta", "rebounds", "offensive_rebounds", "defensive_rebounds",
            "assists", "turnovers", "steals", "blocks", "personal_fouls")
    tl = {"team_id": team.team_id, "team_abbrev": team.abbrev}
    for k in keys:
        tl[k] = sum(int(line[k]) for line in lines)
    tl["possessions"] = float(team.possessions)
    tl["off_rating"] = round(100.0 * team.points / max(1, team.possessions), 2)
    tl["engine"] = "stage2"
    return tl
