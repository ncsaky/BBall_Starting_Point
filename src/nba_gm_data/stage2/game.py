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
minutes). Substitutions: with LOOP["coach"] on (S2-COACH), the in-game coach (stage2.coach) decides who plays at every
dead ball and timeout from tonight's planned minutes (today's minutes model) and the real rotation study; off, the first
loop's rotation (owed minutes at three checkpoints a quarter). With LOOP["screens"] on, self-created shots and rolls can
come off a ball screen and its coverage (stage2.screens), shaped by the defending coach's scheme (stage2.schemes). With
the coach on, quarters end with two-for-ones and games with late timeouts that advance the ball (S2-SCHEMES).

No rating is moved here; the loop's own numbers are in LOOP (fitted to league targets where marked).
"""
from __future__ import annotations

import math
import random
from typing import Any

from . import finishes as FIN
from . import fouls as F
from . import matchups as M
from . import rebounding as R
from . import screens as SC
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
    # (league pace 102.0 possessions per 48 minutes). S2-SCHEMES refit hc_mean 15.6 -> 15.75 on every 2025-26 game in
    # both modes against the same games' real boxes (scripts/research/s2_level_gap.py): replays had drifted to 102.9
    # (generated 102.2); now 102.3 / 101.7. S2-FINISHES 15.75 -> 15.65: the last five minutes of close 4th quarters now
    # run at their real, slower length (stage2.finishes), which took 0.65 possessions a game off both modes; the rest
    # of the game is a little quicker, as in real games (replays 102.2, generated 101.5, real 102.0).
    "hc_floor": 5.0, "hc_mean": 15.65, "hc_shape": 2.6, "trans_floor": 2.5, "trans_mean": 6.0, "reset_floor": 2.0,
    "reset_mean": 8.0, "putback_s": 2.0, "sideout_s": 3.5, "tempo_scale": .01,
    # Pace habit (T05) of the offense's five (k_pace) and, since pace is a game-level thing (both teams play about the
    # same number of possessions), of the defending five (k_pace_def), on the half-court length. The first loop had
    # 1.2 on the offense only, which gave a slope of game pace on the two lineups' summed habit of 37 possessions per
    # unit against a real 77 (first half of 2025-26). FITTED (S2-TOTALS-MATCHUPS, scripts/research/s2_totals_fit.py):
    # equal weights set so the slope matches the first half (80); second half 89 vs real 102; team pace correlation
    # with real .77 (was .55), team spread 1.5 possessions (real 2.3; was 0.6).
    "k_pace": 1.6, "k_pace_def": 1.6,
    # Recent form: today's engine's recent-scoring term (sim.game_environment_effect: both teams' last ten games before
    # tonight, as points per 100 and possessions), applied at today's own strength (1 = as today's engine uses it;
    # 0 = off). Kept at 1: larger values fitted the market a little better but would let a saved season's own scoring
    # feed back into pace. It is the one term here not built from the players' inputs.
    "k_form_off": 1.0, "k_form_pace": 1.0,
    # Transition chance by how the possession started, times the lineup's transition habit.
    "trans_dreb": .20, "trans_steal": .60, "trans_made": .04, "trans_dead": .06, "k_trans": 1.5,
    # Turnovers: the defense's ball pressure (log-odds per index unit); transition and offensive-foul shares.
    # k_press is FITTED with the other team-strength terms below.
    "k_press": .442, "trans_to": -.15, "off_foul_share": .08, "steal_share": .62, "k_steal_level": 1.0,
    # FITTED: league turnovers per 100 (the card fit is per used possession; the loop's are per chance). S2-TOTALS-
    # MATCHUPS .13 -> .11 with the matchups on; S2-SCHEMES .11 -> .17: later pieces (the turnover ratings follow-up,
    # the coach, screens) had left turnovers at 13.4 per 100 in both replayed and generated games against a real 14.1,
    # which was most of the 2.5-3 points a game replayed games scored above real (s2_level_gap.py).
    "to_shift": .17,
    # Non-shooting fouls per possession (league level, then the defenders' own multipliers); technicals etc.
    "ns_per_poss": .064, "other_ft_per_poss": .005, "loose_ball_per_chance": .025,
    # Shooting fouls: action terms on top of the foul kernel's zone base (log-odds). FITTED (S2-TOTALS-MATCHUPS,
    # scripts/research/s2_foul_fit.py: expected free throws per field-goal attempt from every shot try in replayed games,
    # fit half of the players vs real 2025-26, league free throws per 100 held at the real level; held-out half: error
    # .0707 -> .0622, corr .825 -> .858). Drives draw the most contact; finishing a teammate's pass (rolls, cuts, lobs)
    # far less. The first loop's stand-ins were drive .30, roll/cut -.35, post .25, putback -.30, transition .10,
    # jumper -.15, pull-up .05.
    "foul_drive": .275, "foul_roll_cut": -.725, "foul_post": -.10, "foul_putback": -.025, "foul_transition": .25,
    "foul_jumper": .05, "foul_pull_up": -.225,
    # Team-strength terms (make log-odds per index unit; each index is centred on the league's average lineup):
    # defense: perimeter contest on jumpers (half the shooter's own defender, half the lineup), rim protection on rim
    # and short shots, ball pressure on turnovers (k_press above); offense: the lineup's creation and spacing.
    # FITTED together (coordinate search, scratch strength_fit) so the engine's expected margins follow the betting
    # market's spreads on the first half of 2025-26 (correlation .42 -> .57 at 3 runs a game, slope 1.04); checked on
    # the second half (.67, slope 1.24). They decide how much the ratings move results; no rating was changed.
    # S2-TOTALS-MATCHUPS refit with the matchups on (k_perim .36 -> .286, k_rim .45 -> .347, k_press .80 -> .442; see the
    # matchup numbers below for how).
    "k_perim": .286, "k_rim": .347, "perim_own": .5, "k_create": .44, "k_space": .29,
    # Blocks per missed shot by zone (at the league-average block weight); share credited to the help (rim) defender.
    "blk_rim": .277, "blk_short": .21, "blk_mid": .065, "blk_three": .02,
    # Assisted share of made shots by action (scaled to the league assist rate). FITTED scale.
    "ast_scale": 1.07,
    # Shooting-foul level on two-point shots on top of the kernel's zone base (FITTED: league free throws per 100).
    # S2-FINISHES .22 -> .18: the last five minutes now draw their real, higher free-throw rate (stage2.finishes), which
    # put whole games 0.6 free throws per 100 above real; the rest of the game gives that back.
    "foul_level": .18,
    # ... and on rim shots only (S2-TOTALS-MATCHUPS; 0 in the first loop).
    "foul_rim": -.025,
    # Game-level contest by zone (rim, short, mid, three), make log-odds: the shooting conversion was fitted at the
    # kernel's fixed reference contest; this sets the in-game average. FITTED to the league make rates by zone
    # (Basketball Index 2025-26: rim 67.4, short mid 44.8, long mid 41.7, three 36.1).
    "zone_make": (-.19, -.18, 0.0, -.03),
    # League scoring level on every shot (make log-odds; S2-TOTALS-MATCHUPS: set so expected totals match the market on
    # the first half of 2025-26 with pace, recent form and the matchups in: the league scored 0.9 per 100 low).
    "make_level": .012,
    # After an offensive rebound: chance of an immediate putback by the rebounder (rim / short misses vs others).
    "putback_close": .50, "putback_far": .20,
    # Points per 100 -> make log-odds (home court, coaches, rest).
    "k_eff": .02,
    # Score effects: per point of lead (capped at 25), the leading team's shots lose this much make log-odds (effort,
    # garbage-time lineups, the trailing team's urgency). Without it the margin around the engine's own expectation
    # varied 17.4 points (today's engine 13.1; real margins vary about 14.1 around the market spread). FITTED to that.
    "k_lead": .007,
    # Heave chance when under 3 s remain at the start of a possession.
    "heave": .45,
    # Share of rebounds credited to no player (team rebounds). FITTED: rotation players' rebounds per 36 ran 1.0 high
    # (about 13%) with every rebound credited.
    "team_rebound": .11,
    # End-game tactics (stand-ins): chance a leading team runs out the last <24 s; chance a team trailing by 1-8 in the
    # last 45 s fouls immediately (two free throws, clock stopped).
    "end_hold": .75, "end_foul": .75,
    # Chance a team tied or behind by 1-3 in the last 24 seconds plays for the last shot (a three when behind by 3).
    # 0 in the loop's first version; S2-TOTALS-MATCHUPS fits it to the real overtime rate.
    "end_last_shot": .8,
    # The finisher is drawn by usage weight to this power: the weight is fitted to each player's usage on its own, but
    # a share among five teammates (plus the possessions that end on putbacks and drawn fouls) flattens it. FITTED to
    # real per-player shot volume (stars' and bench players' FGA per 36 in replayed games).
    "usage_power": 1.3,
    # ---- Player-on-player matchups (S2-TOTALS-MATCHUPS; stage2.matchups). 0 = the lineup averages of the loop's
    # first version; 1 = each scorer meets the defender assigned to him. Make log-odds per index unit (indices are
    # grade units / 25, centred on the league's minutes-weighted average):
    # The defense numbers below and k_perim / k_rim / k_press above are FITTED together (scripts/research/
    # s2_matchups_tune.py strength): a coordinate search on the first half of 2025-26 (correlation of the engine's
    # expected margins with the market's spreads), then one common scale (0.8) chosen by the first half's mean miss
    # against the spreads, since the search left the engine's margins 1.2x as spread out as the market's (all games,
    # 4 runs: first half corr .673 -> .690, miss 6.81 -> 6.76; second half corr .743 -> .776, slope 1.13). Then the
    # defense alone x0.85: teams' defensive ratings spread 4.9 points per 100 against a real 3.4 (offense 3.3 vs 3.2),
    # and the softer defense also missed the first half's spreads less (7.0 -> 6.7) and totals a little less.
    "matchups": 1.0,
    "k_close": .326,      # catch-and-shoot jumpers: his defender's closeout
    "k_rot": .08,         # ... and the five's rotation (help recognition, off-ball positioning)
    "k_onball": .286,      # pull-ups and short jumpers: his defender's on-ball contest
    "k_len": .10,         # ... his defender's length (wingspan beyond height, and height over the shooter), per 10 cm
    "beat0": -.40,        # drives: log-odds he gets past his man at even burst and containment
    "k_beat": 1.20,       # ... per unit of (his burst/handle/separation - his man's containment)
    "k_beat_make": .136,   # ... make log-odds per unit of (chance he is past his man - the league chance)
    "k_beat_foul": 1.23,  # ... shooting-foul log-odds per unit of the same (recovering defenders and late help foul); FITTED
                          #     with the foul-by-action numbers (s2_foul_fit.py)
    "k_fctrl": .15,       # ... his man's foul control (S45)
    "k_post": .357,       # post-ups: his defender's post defense and height
    "press_own": .5,      # turnovers: share of the ball pressure that is his own man's (the rest the five's average)
    "k_lanes": .20,       # ... the five's passing-lane defense
    # Foul-drawing craft (S24) by action, on top of the foul kernel's own shooter terms (which apply to every shot):
    # log-odds per 25 grade points. Craft shows most where the scorer creates the contact (drives, pull-ups, post-ups)
    # and least on finishes of a teammate's pass and putbacks. FITTED with the foul-by-action numbers (s2_foul_fit.py).
    "craft_drive": .375, "craft_pull_up": .35, "craft_post": -.175, "craft_finish": -.15,
    # ---- The coach (S2-COACH; stage2.coach). 1 = the in-game coach decides who plays at every stoppage (foul trouble,
    # rhythm and fatigue, blowouts, close finishes, hot and cold hands, injuries); 0 = the possession loop's first
    # rotation (owed minutes at three checkpoints a quarter), kept for before/after comparisons.
    "coach": 1.0,
    # Players in foul trouble foul less: odds factor on his shooting fouls and weight on his non-shooting fouls, by fouls
    # already committed. Today's coach model uses x0.7 with four fouls and x0.4 with five (game_minutes.FOUL_CAUTION);
    # FITTED here to the real foul-out rate of regulars (1.55% of their games; x0.7 / x0.4 gave 2.1%, x0.55 / x0.3
    # 1.6%, full AI-coached season, scripts/research/s2_coach_check.py). On with the coach only.
    "caution_4": .55, "caution_5": .3,
    # ---- Pick-and-roll coverages and switching (S2-COACH part 2; stage2.screens). 1 = self-created shots and rolls can
    # come off a ball screen, with the defense's coverage (switch, drop, show, trap) deciding who guards the shot and
    # what help waits; 0 = every shot meets the assigned defender only (needs the matchups on).
    "screens": 1.0,
    # ---- Who commits a shooting foul (S2-SCHEMES). The chance of a shooting foul is the shot's defender's (above); the
    # foul itself is his, or with these shares (rim, short paint, jumpers) a teammate's: the help at the rim, the low
    # man, a late rotation or closeout, weighted by each teammate's own foul terms (foul control S45, contest habits,
    # foul trouble). FITTED (scripts/research/s2_foul_help_fit.py: every shooting-foul chance in replayed 2025-26 games,
    # each player's fouls per 36 against real, fit half of the 311 rotation players, checked on the other half):
    # held-out error .469 -> .376 fouls per 36, correlation .789 -> .836; players at 4.5+ per 36 29 -> 13 (real 11).
    # Larger shares fit a little better still but flatten players' foul rates below the real spread (.77 at these
    # shares, real .80). Giving the share to the rim protector alone did not help (0 fitted). 0 = the shot's defender
    # always (S2-COACH and before). Shooting fouls and free throws do not change, only who is charged.
    "foul_team_rim": .6, "foul_team_short": .6, "foul_team_jump": .45,
    # ---- End of quarters and games (S2-SCHEMES; with the coach on).
    # Two-for-one: a team gaining the ball with 30-34 / 35-38 / 39-42 seconds left in the 1st-3rd quarter shoots early
    # (with 25+ seconds left) with these extra chances on top of the possessions that end that early anyway. FITTED to
    # the rotation study's early-shot share (2025-26: .19 / .53 / .64; the loop already gave .17 / .41 / .61; scripts/
    # research/s2_endgame_check.py).
    "two4one_30": .02, "two4one_35": .20, "two4one_39": .10,
    # Late timeouts (last two minutes of the 4th quarter and of overtime): a team gaining the ball (not off a steal)
    # within ten points calls one, when it still has one, with this chance per possession by the score (behind, tied,
    # ahead), times the time factor (full inside 30 s, half inside 60 s, .2 before). Each team has two. FITTED to the
    # real count (2025-26: behind .63, ahead .32, tied .07 per game in the last two minutes of the 4th; .51 per team).
    # A trailing or tied team advances the ball to the front court, which saves the back-court seconds of that
    # possession (to_advance_s, stand-in); the coach may also change the five. A leader's timeout saves no clock (he
    # runs it down anyway).
    "to_behind": .77, "to_tied": .42, "to_ahead": .25, "to_advance_s": 4.0,
    # ---- The last five minutes of the 4th quarter and overtime (S2-FINISHES; stage2.finishes, with the coach on).
    # 1 = possession length, three-point share, shooting fouls and shot quality follow the fitted table by time left
    # and score; 0 = played like any other stretch (S2-SCHEMES and before).
    "finishes": 1.0,
    # Chance a team behind by 1-3 in the last 24 seconds holds for the last shot (tied: end_last_shot above). With the
    # finishes on, FITTED to the real possession length in that situation (s2_finishes_fit.py): real teams behind
    # attack at once (5.6 seconds a possession), so the fit went to 0; off, end_last_shot.
    "end_last_shot_behind": 0.0,
    # Blowouts in the last minute (with the finishes on): a team up 11+ with 24-60 seconds left lets the shot clock run
    # out with this chance (real: 0.32 turnovers a possession there, mostly shot-clock violations, and 0.55 points); a
    # team down 11+ in the last 24 seconds stops trying (real 0.34 points a possession). FITTED (s2_finishes_fit.py;
    # S2-LAST-POSSESSION refit .377 -> .398 and .444 -> .431 with s2_lastposs_fit.py).
    "late_runout": .398, "late_concede": .431,
    # A leader's possession in the last 24 seconds against a defense that pressures before fouling (traps, the
    # inbound, five-second and back-court calls) ends in a turnover with this chance (with the finishes on). Real:
    # 0.065 turnovers a possession for a leader up 1-6 there; the loop's ordinary turnovers gave .01, so .055 is added.
    "late_press_tov": .055,
    # ---- Team strength scale (S2-FINISHES part 2). Multiplies every team-strength and matchup term above (STRENGTH_KEYS):
    # how much the gaps between lineups' defense, creation and spacing move the make and turnover chances. The players'
    # own shooting is untouched. FITTED to the real spread of team quality: across the 30 teams, 2025-26 replays gave
    # season-average margins 6.5 points apart against a real 6.1, about 5.9 once the luck of 82 games is taken out
    # (today's engine 6.5 too); x.875 gives 5.9. The betting test's spread miss falls with it (scripts/research/
    # s2_spread_check.py: expected margins moved 1.065 points per market point; the systematic miss 4.8 -> 3.9).
    "strength": .875,
    # Home court (S2-FINISHES): today's engine's home and away terms (sim.HOME_COURT_RATING / AWAY_COURT_RATING) times
    # this. FITTED to the real home margin: 2.15 / 1.63 / 1.74 points in the 2023-24 / 2024-25 / 2025-26 regular
    # seasons (play-by-play final scores; 1.84 on average; the market's 1.9 on the betting test's games). Stage 2 gave
    # 1.0 at x1, 1.9 at x1.7, 2.1 at x1.9 (scripts/research/s2_spread_check.py, 8 runs of 2025-26).
    "home_scale": 1.65,
}
CATCH_KINDS = frozenset(KIND_INDEX[k] for k in ("mid_catch", "three_corner", "three_catch", "trans_three"))
PULL_KINDS = frozenset(KIND_INDEX[k] for k in ("short_jumper", "mid_pull", "three_pull"))
DRIVE_KINDS = frozenset(KIND_INDEX[k] for k in ("rim_drive", "floater"))
HOOK = KIND_INDEX["hook"]
STRENGTH_KEYS = ("k_perim", "k_rim", "k_press", "k_create", "k_space", "k_close", "k_rot", "k_onball", "k_len",
                 "k_beat_make", "k_post", "k_lanes")
THREE_KINDS = frozenset(i for i, k in enumerate(KINDS) if k[2] == 3 and k[0] != "heave")
THREE_PULL, THREE_CATCH = KIND_INDEX["three_pull"], KIND_INDEX["three_catch"]
ASSIST = {"rim_drive": .18, "rim_finish": .93, "floater": .15, "hook": .30, "short_jumper": .40, "mid_catch": .90,
          "mid_pull": .07, "three_corner": .97, "three_catch": .92, "three_pull": .06, "putback": .04,
          "trans_rim": .55, "trans_three": .85, "heave": 0.0}
ASSIST_BY_KIND = [ASSIST[k[0]] for k in KINDS]
TRACE: dict | None = None   # research hook (see Game._trace); None in play
COVERAGE_TRACE: list | None = None   # research hook: every ball screen's personnel coverage log-odds (s2_scheme_fit.py)
FOUL_TRACE: list | None = None   # research hook: every shooting-foul chance (scripts/research/s2_foul_tail.py); None in play
TO_TRACE: dict | None = None   # research hook (see Game._to_z; scripts/research/s2_turnover_fit.py); None in play

# End of game with the coach (S2-COACH): chance the trailing team fouls on purpose per possession of the leader, by
# deficit and time left (last 10 s, 10-24 s, 24-60 s). The rotation study (data/research/rotation_evidence.json): for the
# last 24 seconds the pooled rate counting any non-shooting foul within five seconds of the possession's start (late in
# a close game those are deliberate), before that the held-out fit of tagged take fouls. The old rule fouled 75% of the
# time anywhere in the last 45 seconds and let the leader run out the clock first.
TAKE_FOUL = {"1": (.695, .75, .0499), "2_3": (.59, .734, .0611), "4_6": (.336, .687, .2013), "7_10": (.053, .215, .1566),
             "11_plus": (.024, .012, .0102)}
# A team up three fouls rather than allow a tying three (held-out fits: last 10 s, 10-24 s).
UP_THREE_FOUL = (.1761, .1083)

FOUL_ACTION = {"drive": "foul_drive", "roll_cut": "foul_roll_cut", "post": "foul_post", "putback": "foul_putback",
               "transition": "foul_transition", "jumper": "foul_jumper", "pull_up": "foul_pull_up", "heave": None}
QUARTER_S, OT_S = 720.0, 300.0
SUB_TIMES = (540.0, 360.0, 180.0)   # in-quarter checkpoints (seconds left), like the usual stoppages
# With the coach: the two mandatory timeouts of each quarter (first stoppage under 7:00 and under 3:00); every other
# dead ball (fouls, free throws, turnovers out of bounds) is a substitution chance too.
COACH_TIMEOUTS = (420.0, 180.0)
FOUL_TROUBLE = {1: 2, 2: 3, 3: 4, 4: 5}
STAT_KEYS = ("points", "fgm", "fga", "fg3m", "fg3a", "ftm", "fta", "orb", "drb", "ast", "tov", "stl", "blk", "pf",
             "rim_att", "pm", "on_for", "on_against", "screen_ast")
(S_PTS, S_FGM, S_FGA, S_3PM, S_3PA, S_FTM, S_FTA, S_ORB, S_DRB, S_AST, S_TOV, S_STL, S_BLK, S_PF, S_RIM, S_PM, S_ON_FOR,
 S_ON_AGAINST, S_SCR) = range(19)
SELF_KINDS = frozenset(KIND_INDEX[k] for k in ("rim_drive", "floater", "short_jumper", "mid_pull", "three_pull"))
RIM_FINISH = KIND_INDEX["rim_finish"]


class ScreenPlay:
    """One ball screen in a possession (stage2.screens): the coverage, the screener's slot, the defender who plays the
    shot, and the shot's matchup terms under that coverage."""
    __slots__ = ("cov", "screener", "def_slot", "pull", "beat", "rim", "fctrl", "dz", "to_dz", "handler")


class TeamState:
    """One team's side of the game: its players' cards, minutes plan, live lineup and box score."""

    def __init__(self, team_id: str, abbrev: str, cards: list[Card], targets: list[float], starters: list[int],
                 groups: list[str], eff: float, tempo: float, league: dict, eff_def: float = 0.0,
                 coach_matchup: float = 1.0):
        self.team_id, self.abbrev = team_id, abbrev
        self.coach_matchup = coach_matchup   # how much the coach puts his stopper on the top scorer (matchups.assign)
        self.cards = cards
        n = len(cards)
        total = sum(targets) or 1.0
        self.target_s = [2880.0 * 5 * t / total for t in targets]   # regulation seconds, summing to 5 x 48 minutes
        self.starters = starters
        self.groups = groups
        self.secs = [0.0] * n
        self.stint = [0.0] * n
        self.stats = [[0] * len(STAT_KEYS) for _ in range(n)]
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
        self.form_pace = 0.0      # recent-form possessions (engine.py; 0 unless the loop's k_form_pace is on)
        self.rot = self.lanes = 0.0
        self.coach = None         # stage2.coach.Coach (engine.py); None = the first loop's rotation
        self.screens_on = False   # set by Game: the box score carries screen assists only when screens are played
        self._five_cache: dict = {}
        self.reserve = [False] * n   # outside tonight's planned rotation (garbage time only)
        self.advance = False         # a late timeout moved the ball to the front court (next possession)
        self.scheme = (0.0, 0.0)     # the coach's ball-screen scheme: (aggression, switching) log-odds (stage2.schemes)
        self.late_to = 0             # late timeouts left (last two minutes of the 4th / of overtime)

    # ---- lineup aggregates (recomputed when the five change) ------------------------------------------------------
    REFRESH_KEYS = ("usage_cum", "ast_w", "reb", "reb_prof", "pace", "trans_pref", "perim", "perim_center", "create",
                    "space", "off_shift", "rim", "press", "stl_level", "blk_level", "ns_level", "ns_draw_cum",
                    "off_foul_cum", "help", "rot", "lanes")

    def refresh(self) -> None:
        """The five's aggregates; cached per five with the coach (the same fives recur through a game)."""
        if self.coach is not None:
            key = tuple(self.on)
            hit = self._five_cache.get(key)
            if hit is not None:
                for k, v in zip(self.REFRESH_KEYS, hit):
                    setattr(self, k, v)
                self.lineup_dirty = False
                return
            self._refresh()
            self._five_cache[key] = tuple(getattr(self, k) for k in self.REFRESH_KEYS)
            return
        self._refresh()

    def _refresh(self) -> None:
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
        self.rot = sum(c.rot_d for c in cs) / 5.0 - lg.get("rot_center", 0.0)
        self.lanes = sum(c.lanes_d for c in cs) / 5.0 - lg.get("lanes_center", 0.0)
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
        if L["strength"] != 1.0:
            for key in STRENGTH_KEYS:
                L[key] *= L["strength"]
        home.loop = away.loop = L
        self.foul_action = [(L[FOUL_ACTION[a]] if FOUL_ACTION.get(a) else 0.0) + (L["foul_level"] if KZONE[i] < 3 else 0.0)
                            + (L["foul_rim"] if KZONE[i] == 0 else 0.0) for i, a in enumerate(KACTION)]
        self.assist = [a * L["ast_scale"] for a in ASSIST_BY_KIND]
        craft_by_action = {"drive": L["craft_drive"], "pull_up": L["craft_pull_up"], "post": L["craft_post"],
                           "roll_cut": L["craft_finish"], "putback": L["craft_finish"]}
        self.craft_w = [craft_by_action.get(a, 0.0) for a in KACTION]
        self.zone_make = [0.0 if KINDS[i][0] == "heave" else L["zone_make"][KZONE[i]] + L["make_level"] for i in range(N_KINDS)]
        self.blk_base = (L["blk_rim"], L["blk_short"], L["blk_mid"], L["blk_three"])
        self.period = 0
        self.t_left = QUARTER_S
        self.events = 0
        self.diag = [0] * (N_KINDS * 3)   # per shot kind: attempts (FGA), makes, shooting fouls
        self.lg_pace = home.league["pace_mean"]
        self.lg_trans = home.league["trans_mean"]
        self.use_coach = bool(L["coach"]) and home.coach is not None and away.coach is not None
        # Foul caution by fouls already committed (log-odds on shooting fouls; weight on non-shooting fouls).
        c4, c5 = (L["caution_4"], L["caution_5"]) if self.use_coach else (1.0, 1.0)
        self.caution_w = (1.0, 1.0, 1.0, 1.0, c4, c5, c5, c5)
        self.caution_z = tuple(math.log(w) for w in self.caution_w)
        self.dead = False
        self.pending_sub = False
        self._pair_cache: dict = {}
        self.use_screens = bool(L["screens"]) and bool(L["matchups"])
        self.S = SC.SCREENS
        self.cov_count = [0] * 5          # ball screens by coverage (research: switch share)
        self.team_foul_share = (L["foul_team_rim"], L["foul_team_short"], L["foul_team_jump"], L["foul_team_jump"])
        self.two_for_one = self.late_timeouts = self.advances = 0   # research counters
        self.use_finishes = self.use_coach and bool(L["finishes"])
        self.late = FIN.NEUTRAL      # this possession's late-game terms (len, three, foul, make, make3, tov)
        home.advance = away.advance = False
        home.screens_on = away.screens_on = self.use_screens

    def elapsed(self) -> float:
        """Game time played so far (seconds; overtime after 48 minutes)."""
        p = self.period
        if p <= 4:
            return (p - 1) * QUARTER_S + (QUARTER_S - self.t_left)
        return 4 * QUARTER_S + (p - 5) * OT_S + (OT_S - self.t_left)

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
            key = (tuple(off.on), tuple(de.on)) if self.use_coach else None
            hit = self._pair_cache.get(key) if key is not None else None
            if hit is not None:
                (off.guards_vs, off.defender_of, off.m_catch, off.m_pull, off.m_beat, off.m_post, off.m_press,
                 off.m_fctrl) = hit
                continue
            guards = R.matchups(off.reb_prof, de.reb_prof)      # defender slot -> offensive slot
            inv = [0] * 5
            for j, i in enumerate(guards):
                inv[i] = j
            off.guards_vs = guards     # used when `off` is on offense (rebound positions: height-matched)
            off.defender_of = inv
            if self.L["matchups"]:
                self._pair_terms(off, de)
            if key is not None:
                self._pair_cache[key] = (off.guards_vs, off.defender_of, getattr(off, "m_catch", None),
                                         getattr(off, "m_pull", None), getattr(off, "m_beat", None),
                                         getattr(off, "m_post", None), getattr(off, "m_press", None),
                                         getattr(off, "m_fctrl", None))

    def _pair_terms(self, off: TeamState, de: TeamState) -> None:
        """Who guards whom (matchups.assign) and, for each scorer, his defender's terms on each kind of action."""
        L, lg = self.L, off.league
        oc = [off.cards[i] for i in off.on]
        dc = [de.cards[j] for j in de.on]
        d_of = M.assign(oc, dc, de.coach_matchup)
        off.defender_of = d_of
        b0, kb = L["beat0"], L["k_beat"]
        c_close, c_on, c_len = lg.get("closeout_center", 0.0), lg.get("onball_center", 0.0), lg.get("length_center", 0.0)
        c_burst, c_cont, c_post = lg.get("burst_center", 0.0), lg.get("contain_center", 0.0), lg.get("post_center", 0.0)
        c_press, c_fc = lg.get("press_center_player", 0.0), lg.get("fctrl_center", 0.0)
        bmean = _sig(b0)
        off.m_catch, off.m_pull, off.m_beat, off.m_post, off.m_press, off.m_fctrl = [], [], [], [], [], []
        for i, j in enumerate(d_of):
            o, d = oc[i], dc[j]
            over = (d.height - o.height) / 10.0
            off.m_catch.append(d.closeout_d - c_close)
            off.m_pull.append(L["k_onball"] * (d.onball_d - c_on) + L["k_len"] * (d.length - c_len + over))
            off.m_beat.append(_sig(b0 + kb * ((o.burst - c_burst) - (d.contain_d - c_cont))) - bmean)
            off.m_post.append(d.post_d - c_post + .5 * over)
            off.m_press.append(d.press_d - c_press)
            off.m_fctrl.append(d.foul_ctrl - c_fc)

    def _pair_one(self, o, d, lg: dict) -> tuple[float, float, float]:
        """One scorer against one defender (a switch): his pull-up contest, the chance past him (less the league's)
        and his foul control, the same terms _pair_terms gives the assigned defender."""
        L = self.L
        b0, kb = L["beat0"], L["k_beat"]
        over = (d.height - o.height) / 10.0
        pull = L["k_onball"] * (d.onball_d - lg.get("onball_center", 0.0)) + L["k_len"] * (
            d.length - lg.get("length_center", 0.0) + over)
        beat = _sig(b0 + kb * ((o.burst - lg.get("burst_center", 0.0)) - (d.contain_d - lg.get("contain_center", 0.0)))) \
            - _sig(b0)
        return pull, beat, d.foul_ctrl - lg.get("fctrl_center", 0.0)

    def _screen(self, off: TeamState, de: TeamState, slot: int, kind: int) -> ScreenPlay | None:
        """Does this half-court shot come off a ball screen, and how does the defense cover it (stage2.screens)?"""
        S, rng = self.S, self.rng
        card = off.cards[off.on[slot]]
        if kind in SELF_KINDS:
            if rng.random() >= S["p_handler"]:
                return None
            handler_slot = slot
            others = [k for k in range(5) if k != slot]
            hunt = S["k_hunt"]
            ws = [off.cards[off.on[k]].scr_w * math.exp(-hunt * de.cards[de.on[off.defender_of[k]]].contain_d)
                  for k in others]
            screener_slot = others[_pick(_cum(ws), rng.random())]
        elif kind == RIM_FINISH:
            if rng.random() >= card.roll_share:
                return None
            screener_slot = slot
            others = [k for k in range(5) if k != slot]
            handler_slot = others[_pick(_cum([off.cards[off.on[k]].usage for k in others]), rng.random())]
        else:
            return None
        handler = off.cards[off.on[handler_slot]]
        screener = off.cards[off.on[screener_slot]]
        jb, js = off.defender_of[handler_slot], off.defender_of[screener_slot]
        dball, dscr = de.cards[de.on[jb]], de.cards[de.on[js]]
        star = max(0.0, (handler.usage - .28) / .06)
        big = off.groups[off.on[screener_slot]] == "big"
        zs = SC.coverage_logits(handler, dscr, dball, big, S, star)
        if COVERAGE_TRACE is not None:
            COVERAGE_TRACE.append((de.abbrev, big, zs))
        probs = SC.probabilities_from_logits(*zs, de.scheme)
        cov = SC.choose(rng.random(), probs)
        self.cov_count[cov] += 1
        play = ScreenPlay()
        play.cov, play.screener, play.dz, play.to_dz, play.rim = cov, screener_slot, 0.0, 0.0, None
        lg = off.league
        if kind == RIM_FINISH:
            # The roll: over the smaller switched defender, against his own dropping big, or open behind a show or a
            # trap unless the five rotates.
            play.handler = False
            play.pull = play.beat = play.fctrl = 0.0
            if cov == SC.SWITCH:
                play.def_slot = jb
                play.dz = S["k_mismatch"] * max(0.0, card.height - dball.height) / 10.0
            else:
                play.def_slot = js
                if cov == SC.DROP:
                    play.dz = -S["k_drop_roll"] * (dscr.rim_d - lg.get("rimd_center", 0.0))
                else:
                    play.dz = S["k_open_roll"] * (1.0 - de.rot)
            return play
        play.handler = True
        if cov == SC.SWITCH:
            play.def_slot = js
            play.pull, play.beat, play.fctrl = self._pair_one(handler, dscr, lg)
            return play
        play.def_slot = jb
        bmean = _sig(self.L["beat0"])
        past = off.m_beat[slot] + bmean
        play.fctrl = off.m_fctrl[slot]
        if cov == SC.DROP:
            lost = min(.9, max(0.0, S["drop_nav"] + S["k_edge"] * SC.screen_edge(screener, dball)))
            play.pull = off.m_pull[slot] * (1.0 - lost) - lost * S["drop_open"]
            play.beat = past + lost * (1.0 - past) - bmean
            w = S["drop_help"]
            play.rim = (1.0 - w) * de.rim + w * (dscr.rim_d - lg.get("rimd_center", 0.0))
        elif cov == SC.SHOW:
            play.pull = off.m_pull[slot] + S["show_contest"]
            play.beat = past * (1.0 - S["show_beat"]) - bmean
            play.to_dz = S["show_to"]
        else:
            play.pull = off.m_pull[slot] + S["blitz_contest"]
            play.beat = past * (1.0 - S["show_beat"]) - bmean
            play.to_dz = S["blitz_to"]
        return play

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

    def _duration(self, kind: str, off: TeamState, de: TeamState | None = None, mult: float = 1.0) -> float:
        L, rng = self.L, self.rng
        if kind == "trans":
            return L["trans_floor"] + rng.gammavariate(2.0, (L["trans_mean"] - L["trans_floor"]) / 2.0)
        if kind == "reset":
            return L["reset_floor"] + rng.gammavariate(2.0, mult * (L["reset_mean"] - L["reset_floor"]) / 2.0)
        dpace = 0.0 if de is None else L["k_pace_def"] * (de.pace - self.lg_pace)
        # Recent-form possessions (game level: the two teams' terms averaged; one possession is about 1% of the clock).
        dpace += (off.form_pace + (de.form_pace if de is not None else off.form_pace)) / 2.0 / 101.0
        mean = (mult * (L["hc_mean"] - L["hc_floor"]) * math.exp(-L["k_pace"] * (off.pace - self.lg_pace) - dpace)
                * (1.0 - L["tempo_scale"] * off.tempo))
        return min(23.5, L["hc_floor"] + rng.gammavariate(L["hc_shape"], mean / L["hc_shape"]))

    # ---- scoring helpers -----------------------------------------------------------------------------------------
    def _score(self, off: TeamState, de: TeamState, slot: int, pts: int) -> None:
        off.points += pts
        off.stats[off.on[slot]][S_PTS] += pts
        for i in off.on:
            st = off.stats[i]
            st[S_PM] += pts
            st[S_ON_FOR] += pts
        for i in de.on:
            st = de.stats[i]
            st[S_PM] -= pts
            st[S_ON_AGAINST] += pts

    def _foul(self, de: TeamState, slot: int, *, team_foul: bool = True) -> None:
        i = de.on[slot]
        if i in de.out:
            # Fouled out earlier in this same possession (substitutions wait for its end): he is already gone, so the
            # foul is a teammate's (the one with the fewest fouls). No random draw, so the game's stream is unchanged.
            # Before 2026-11-21 a sixth and seventh foul in one possession could leave a player on 7.
            mates = [j for j in de.on if j not in de.out]
            if mates:
                i = min(mates, key=lambda j: (de.stats[j][S_PF], j))
        de.stats[i][S_PF] += 1
        self.dead = True
        if self.use_coach:
            de.coach.on_foul(i, de.stats[i][S_PF], self.period, self.elapsed())
        if team_foul:
            de.team_fouls += 1
            if self.t_left <= 120.0:
                de.fouls_late += 1
        if de.stats[i][S_PF] >= 6:
            de.out.add(i)
            self.pending_sub = True

    def _shooting_fouler(self, de: TeamState, j: int, zone: int) -> int:
        """Who is charged with a shooting foul on a shot defended by slot j: j, or with the fitted share a teammate
        (help, rotation, closeout), weighted by his own foul terms and foul trouble."""
        share = self.team_foul_share[zone]
        if share <= 0.0 or self.rng.random() >= share:
            return j
        cz = self.caution_z
        w = [0.0 if k == j else math.exp(de.cards[i].d_foul + cz[min(7, de.stats[i][S_PF])])
             for k, i in enumerate(de.on)]
        return _pick(_cum(w), self.rng.random())

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
        advance = off.advance      # after a late timeout: inbounded in the front court
        off.advance = False
        if self.use_finishes and self.period >= 4 and self.t_left <= 300.0:
            lead = off.points - de.points
            self.late = FIN.cell(self.t_left, lead)
            if self.t_left <= 60.0 and (lead >= 11 or lead <= -11):
                if lead >= 11 and self.t_left > 24.0 and L["late_runout"] > 0.0 and rng.random() < L["late_runout"]:
                    # A blowout: the leader dribbles out the shot clock (a team turnover, no player's).
                    self._run_clock(min(self.t_left, 22.0 + 2.0 * rng.random()))
                    return "end" if self.t_left <= 0.0 else "dead"
                if lead <= -11 and self.t_left <= 24.0 and L["late_concede"] > 0.0 and rng.random() < L["late_concede"]:
                    self._run_clock(self.t_left)
                    return "end"
        elif self.late is not FIN.NEUTRAL:
            self.late = FIN.NEUTRAL
        # Technical / flagrant / clear-path free throws (no possession change): the best free-throw shooter on court.
        if rng.random() < L["other_ft_per_poss"]:
            slot = max(range(5), key=lambda s: off.cards[off.on[s]].ft)
            self._free_throws(off, de, slot, 1)
        # End of the game (4th quarter or overtime): a team ahead by one or two possessions with the shot clock off
        # runs the clock out; a team behind by 1-8 in the last 45 seconds fouls at once to stop the clock.
        if self.period >= 4 and self.use_coach and self.t_left <= 60.0:
            ended = self._end_game(off, de)
            if ended is not None:
                return ended
        elif self.period >= 4:
            lead = off.points - de.points
            if 0 < lead and self.t_left <= 24.0 and rng.random() < L["end_hold"]:
                self._run_clock(self.t_left)
                return "end"
            if 1 <= lead <= 8 and self.t_left <= 45.0 and rng.random() < L["end_foul"]:
                self._run_clock(min(self.t_left, 1.0 + 3.0 * rng.random()))
                slot = _pick(off.usage_cum, rng.random())
                if self.use_coach:
                    # The coach fouls with a player who has fouls to give (the fewest on the floor).
                    low = min(de.stats[i][S_PF] for i in de.on)
                    pool = [j for j in range(5) if de.stats[de.on[j]][S_PF] == low]
                    fouler = pool[rng.randrange(len(pool))]
                else:
                    fouler = rng.randrange(5)
                self._foul(de, fouler)
                made = self._free_throws(off, de, slot, 2)
                return "made" if made else self._after_miss(off, de, "ft", slot)
            # Tied or behind by one possession in the last 24 seconds: hold for the last shot (the other team gets no
            # answer), and behind by three, take a three to tie (S2-TOTALS-MATCHUPS; stand-in rule, its chance fitted
            # to the real overtime rate).
            if -3 <= lead <= 0 and 3.0 < self.t_left <= 24.0 and rng.random() < L["end_last_shot"]:
                self._run_clock(max(.5, self.t_left - (.5 + 2.5 * rng.random())))
                slot = _pick(off.usage_cum, rng.random())
                card = off.cards[off.on[slot]]
                if rng.random() < _sig(self._to_z(card, card.to_logit + L["to_shift"] + self.late[5] + self._pressure(off, de, slot))):
                    return self._turnover(off, de, slot)
                if lead == -3:
                    kind = THREE_PULL if card.menu[THREE_PULL] >= card.menu[THREE_CATCH] else THREE_CATCH
                else:
                    kind = _pick(card.menu_cum, rng.random())
                return self._shot(off, de, slot, kind, final=True)
        p_trans ={"dreb": L["trans_dreb"], "steal": L["trans_steal"], "made": L["trans_made"]}.get(start, L["trans_dead"])
        p_trans *= math.exp(L["k_trans"] * (off.trans_pref - self.lg_trans))
        trans = not advance and rng.random() < p_trans
        seg = self._duration("trans" if trans else "half", off, de, self.late[0])
        if advance:
            # Inbounded in the front court after a timeout: no back-court seconds.
            seg = max(1.5, seg - L["to_advance_s"])
        if self.use_coach and self.period <= 3 and 30.0 <= self.t_left <= 42.0 and not trans:
            # Two-for-one: shoot early enough (25+ s left) to get the ball back for the quarter's last shot.
            t = self.t_left
            p21 = L["two4one_39"] if t >= 39.0 else L["two4one_35"] if t >= 35.0 else L["two4one_30"]
            if seg > t - 25.0 and rng.random() < p21:
                seg = max(1.5, t - 25.0 - 2.0 * rng.random())
                self.two_for_one += 1
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
                cw = self.caution_w
                w = [c.ns_mult * (3.0 if j == guard else 1.0) * cw[min(7, de.stats[de.on[j]][S_PF])]
                     for j, c in enumerate(d_cards)]
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
        if self.use_screens and not trans:
            # What he tries first, so a ball screen and its coverage can shape the turnover chance and the shot.
            kind = self._menu_kind(card, card.menu_cum)
            scr = self._screen(off, de, slot, kind)
            z = self._to_z(card, card.to_logit + L["to_shift"] + self.late[5] + self._pressure(off, de, slot)
                           + (scr.to_dz if scr is not None else 0.0))
            if rng.random() < _sig(z):
                return self._turnover(off, de, slot)
            return self._shot(off, de, slot, kind, final=final, scr=scr)
        z = self._to_z(card, card.to_logit + L["to_shift"] + self.late[5] + self._pressure(off, de, slot) + (L["trans_to"] if trans else 0.0))
        if rng.random() < _sig(z):
            return self._turnover(off, de, slot)
        kind = self._menu_kind(card, card.trans_cum if trans else card.menu_cum)
        return self._shot(off, de, slot, kind, final=final)

    def _menu_kind(self, card, cum: list[float]) -> int:
        """The scorer's shot from his menu; late in a game the situation tilts it toward or away from threes."""
        tilt = self.late[1]
        if tilt == 0.0:
            return _pick(cum, self.rng.random())
        f = math.exp(tilt)
        w, prev = [], 0.0
        for k, c in enumerate(cum):
            w.append((c - prev) * (f if k in THREE_KINDS else 1.0))
            prev = c
        return _pick(_cum(w), self.rng.random())

    def _end_game(self, off: TeamState, de: TeamState) -> str | None:
        """The coach's end-of-game calls with the coach on (the rotation study's held-out fits, per possession of the
        team that is ahead): the trailing team fouls to stop the clock with the real chance for its deficit and the
        time left; otherwise a leader with the shot clock off runs the clock out. A team up three may foul rather than
        allow a tying three. Tied or behind by one possession: hold for the last shot (a three when down three)."""
        L, rng, t_left = self.L, self.rng, self.t_left
        lead = off.points - de.points
        band = 0 if t_left <= 10.0 else 1 if t_left <= 24.0 else 2
        if lead > 0:
            if band < 2 and self.use_finishes and lead <= 10 and L["late_press_tov"] > 0.0 and rng.random() < L["late_press_tov"]:
                self._run_clock(min(t_left, 1.0 + 3.0 * rng.random()))
                return self._turnover(off, de, _pick(off.usage_cum, rng.random()))
            key = "1" if lead == 1 else "2_3" if lead <= 3 else "4_6" if lead <= 6 else "7_10" if lead <= 10 else "11_plus"
            if self.use_finishes and FIN.TAKE_LATE is not None:
                p = FIN.TAKE_LATE[str(band)][FIN.take_key(lead)]
            else:
                p = TAKE_FOUL[key][band]
            if rng.random() < p:
                self._run_clock(min(t_left, (1.0 + 3.0 * rng.random()) if band < 2 else 1.0 + 6.0 * rng.random()))
                return self._intentional_foul(off, de)
            if band < 2 and rng.random() < L["end_hold"]:
                self._run_clock(t_left)
                return "end"
            return None
        if lead == -3 and band < 2 and rng.random() < (FIN.UP_THREE if self.use_finishes else UP_THREE_FOUL)[band]:
            self._run_clock(min(t_left, 1.0 + 3.0 * rng.random()))
            return self._intentional_foul(off, de)
        hold = L["end_last_shot"] if lead == 0 or not self.use_finishes else L["end_last_shot_behind"]
        if -3 <= lead <= 0 and 3.0 < t_left <= 24.0 and rng.random() < hold:
            self._run_clock(max(.5, t_left - (.5 + 2.5 * rng.random())))
            slot = _pick(off.usage_cum, rng.random())
            card = off.cards[off.on[slot]]
            if rng.random() < _sig(self._to_z(card, card.to_logit + L["to_shift"] + self.late[5] + self._pressure(off, de, slot))):
                return self._turnover(off, de, slot)
            if lead == -3:
                kind = THREE_PULL if card.menu[THREE_PULL] >= card.menu[THREE_CATCH] else THREE_CATCH
            else:
                kind = self._menu_kind(card, card.menu_cum)
            return self._shot(off, de, slot, kind, final=True)
        return None

    def _intentional_foul(self, off: TeamState, de: TeamState) -> str:
        """A deliberate foul: the defense fouls with a player who has fouls to give; the offense's ball handler (drawn by
        usage) shoots two."""
        rng = self.rng
        slot = _pick(off.usage_cum, rng.random())
        low = min(de.stats[i][S_PF] for i in de.on)
        pool = [j for j in range(5) if de.stats[de.on[j]][S_PF] == low]
        self._foul(de, pool[rng.randrange(len(pool))])
        made = self._free_throws(off, de, slot, 2)
        return "made" if made else self._after_miss(off, de, "ft", slot)

    @staticmethod
    def _to_z(card, z: float) -> float:
        """A turnover chance's log-odds, unchanged. Research only: with TO_TRACE set, each chance's terms outside the
        card's turnover rule (penalty, level, pressure, transition) are recorded per player, so the rule can be refitted
        on expected turnovers in real game situations (scripts/research/s2_turnover_fit.py)."""
        if TO_TRACE is not None:
            TO_TRACE.setdefault(card.pid, []).append(z - card.to_logit + .01 * card.penalty)
        return z

    def _pressure(self, off: TeamState, de: TeamState, slot: int) -> float:
        """The defense's turnover pressure on this scorer (log-odds)."""
        L = self.L
        if not L["matchups"]:
            return L["k_press"] * de.press
        own = L["press_own"]
        return L["k_press"] * ((1 - own) * de.press + own * off.m_press[slot]) + L["k_lanes"] * de.lanes

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
        self.dead = True
        return "dead"

    def _shot(self, off: TeamState, de: TeamState, slot: int, kind: int, *, final: bool = False,
              putback: bool = False, scr: ScreenPlay | None = None) -> str:
        L, rng, fc = self.L, self.rng, self.fc
        card = off.cards[off.on[slot]]
        st = off.stats[off.on[slot]]
        zone = KZONE[kind]
        j = off.defender_of[slot] if scr is None else scr.def_slot
        dcard = de.cards[de.on[j]]
        # Make chance: his conversion for this shot, the defense's contest or rim protection, team terms.
        lead = off.points - de.points
        z = (card.make_logit[kind] + self.zone_make[kind] + off.eff + off.off_shift - de.eff_def
             - L["k_lead"] * (25 if lead > 25 else -25 if lead < -25 else lead) + ((self.late[3] + (self.late[4] if kind in THREE_KINDS else 0.0)) if kind != HEAVE else 0.0))
        fz = 0.0
        if L["matchups"] and kind != HEAVE:
            if kind in CATCH_KINDS:
                z -= L["k_perim"] * (1 - L["perim_own"]) * de.perim + L["k_close"] * off.m_catch[slot] + L["k_rot"] * de.rot
            elif kind in PULL_KINDS:
                z -= L["k_perim"] * (1 - L["perim_own"]) * de.perim + (off.m_pull[slot] if scr is None else scr.pull)
            elif kind in DRIVE_KINDS:
                if scr is None:
                    beat = off.m_beat[slot]
                    z += L["k_beat_make"] * beat - L["k_rim"] * de.rim
                    fz = L["k_beat_foul"] * beat - L["k_fctrl"] * off.m_fctrl[slot]
                else:
                    beat = scr.beat
                    z += L["k_beat_make"] * beat - L["k_rim"] * (de.rim if scr.rim is None else scr.rim)
                    fz = L["k_beat_foul"] * beat - L["k_fctrl"] * scr.fctrl
            elif kind == HOOK:
                z -= L["k_rim"] * de.rim + L["k_post"] * off.m_post[slot]
            elif zone <= 1:
                z -= L["k_rim"] * de.rim
            if scr is not None:
                z += scr.dz
        elif kind in JUMPER_KINDS:
            z -= L["k_perim"] * (L["perim_own"] * (dcard.perim_d - de.perim_center) + (1 - L["perim_own"]) * de.perim)
        elif zone <= 1:
            z -= L["k_rim"] * de.rim
        p_make = _sig(z)
        # Shooting foul: the foul kernel's zone base, the shooter's and contester's terms, plus the action.
        if kind != HEAVE:
            p_foul = _sig(fc.base[zone] + card.foul_s + dcard.d_foul + self.foul_action[kind] + fz
                          + self.craft_w[kind] * card.craft + self.caution_z[min(7, de.stats[de.on[j]][S_PF])]
                          + self.late[2])
            if TRACE is not None:
                self._trace(card, dcard, off, slot, kind, zone, p_make)
            if FOUL_TRACE is not None:
                FOUL_TRACE.append((zone, kind in DRIVE_KINDS, p_foul, j, de.help,
                                   tuple(de.cards[i].pid for i in de.on), tuple(de.cards[i].d_foul for i in de.on),
                                   tuple(self.caution_z[min(7, de.stats[i][S_PF])] for i in de.on)))
        else:
            p_foul = 0.0
        if zone == 0:
            st[S_RIM] += 1
        if rng.random() < p_foul:
            self._foul(de, self._shooting_fouler(de, j, zone))
            self.diag[3 * kind + 2] += 1
            if rng.random() < card.and1[zone] * (p_make / max(.05, _sig(card.make_logit[kind]))):
                st[S_FGA] += 1          # a made shot through a foul counts as an attempt (and-one)
                self.diag[3 * kind] += 1
                self.diag[3 * kind + 1] += 1
                if zone == 3:
                    st[S_3PA] += 1
                self._record_make(off, de, slot, kind)
                if scr is not None and scr.handler and rng.random() < self.S["p_screen_assist"]:
                    off.stats[off.on[scr.screener]][S_SCR] += 1
                if self.use_coach:
                    off.coach.on_shot(off.on[slot], KPTS[kind], p_make * KPTS[kind])
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
            if scr is not None and scr.handler and rng.random() < self.S["p_screen_assist"]:
                off.stats[off.on[scr.screener]][S_SCR] += 1
            if self.use_coach:
                off.coach.on_shot(off.on[slot], KPTS[kind], p_make * KPTS[kind])
            return "made"
        if self.use_coach and kind != HEAVE:
            off.coach.on_shot(off.on[slot], 0, p_make * KPTS[kind])
        # Block (on the miss)
        if rng.random() < self.blk_base[zone] * de.blk_level:
            w = [de.cards[i].blk_w * (2.0 if jj == j else 1.0) * (1.5 if jj == de.help else 1.0) for jj, i in enumerate(de.on)]
            b = _pick(_cum(w), rng.random())
            de.stats[de.on[b]][S_BLK] += 1
        if final and self.t_left <= 0.0:
            return "end"
        return self._after_miss(off, de, KMISS[kind], slot)

    def _trace(self, card, dcard, off, slot, kind, zone, p_make) -> None:
        """Research only (TRACE set by scripts/research/s2_foul_fit.py): each shot try's fixed foul terms, so the
        foul-by-action numbers can be fitted on expected values instead of noisy replays."""
        rec = TRACE.get(card.pid)
        if rec is None:
            rec = TRACE[card.pid] = [[0.0] * 6 for _ in range(N_KINDS)]
        r = rec[kind]
        drive = self.L["matchups"] and kind in DRIVE_KINDS
        r[0] += 1
        r[1] += self.fc.base[zone] + card.foul_s + dcard.d_foul
        r[2] += off.m_beat[slot] if drive else 0.0
        r[3] += off.m_fctrl[slot] if drive else 0.0
        r[4] += card.and1[zone] * (p_make / max(.05, _sig(card.make_logit[kind])))
        r[5] = card.craft

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
        seg = self._duration("reset", off, de, self.late[0])
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
        if self.use_screens:
            kind = self._menu_kind(card, card.menu_cum)
            scr = self._screen(off, de, slot, kind)
            if rng.random() < _sig(self._to_z(card, card.to_logit + L["to_shift"] + self.late[5] + self._pressure(off, de, slot)
                                              + (scr.to_dz if scr is not None else 0.0))):
                return self._turnover(off, de, slot)
            return self._shot(off, de, slot, kind, final=final, scr=scr)
        if rng.random() < _sig(self._to_z(card, card.to_logit + L["to_shift"] + self.late[5] + self._pressure(off, de, slot))):
            return self._turnover(off, de, slot)
        kind = self._menu_kind(card, card.menu_cum)
        return self._shot(off, de, slot, kind, final=final)

    # ---- the game ------------------------------------------------------------------------------------------------
    def play(self) -> None:
        if self.use_coach:
            self._play_coached()
            return
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

    def _coach_decide(self, period_start: bool) -> None:
        el = self.elapsed()
        for t, o in ((self.home, self.away), (self.away, self.home)):
            t.coach.decide(period=self.period, t_left=self.t_left, elapsed=el, margin=t.points - o.points,
                           period_start=period_start)

    def _play_coached(self) -> None:
        """The game with the in-game coach (stage2.coach): substitutions at every stoppage."""
        rng = self.rng
        home, away = self.home, self.away
        tip = home if rng.random() < .5 else away
        other = away if tip is home else home
        period = 0
        while True:
            period += 1
            self.period = period
            self.t_left = QUARTER_S if period <= 4 else OT_S
            home.team_fouls = away.team_fouls = 0
            home.fouls_late = away.fouls_late = 0
            off = tip if period in (1, 4) or period > 4 else other
            if period > 4:
                off = home if rng.random() < .5 else away
            de = away if off is home else home
            if period == 3:
                home.coach.new_half()
                away.coach.new_half()
            elif period > 1:
                home.coach.quarter_break(60.0 if period <= 4 else 120.0)
                away.coach.quarter_break(60.0 if period <= 4 else 120.0)
            self._coach_decide(period_start=True)
            self._matchups()
            start = "dead"
            checkpoints = [s for s in COACH_TIMEOUTS if s < self.t_left] if period <= 4 else []
            home.late_to = away.late_to = 2 if period >= 4 else 0
            while self.t_left > 0.0:
                self.dead = False
                if period >= 4 and self.t_left <= 120.0 and start != "steal" and off.late_to > 0 \
                        and self._late_timeout(off, de):
                    self._coach_decide(period_start=False)
                    if home.lineup_dirty or away.lineup_dirty:
                        self._matchups()
                result = self.possession(off, de, start)
                self.events += 1
                if result == "end" or self.t_left <= 0.0:
                    break
                crossed = False
                while checkpoints and self.t_left <= checkpoints[0]:
                    checkpoints.pop(0)
                    crossed = True
                late_make = period >= 4 and self.t_left <= 120.0 and result == "made"
                if (self.dead or crossed or late_make or self.pending_sub or home.coach.pending
                        or away.coach.pending):
                    self.pending_sub = False
                    self._coach_decide(period_start=False)
                if home.lineup_dirty or away.lineup_dirty:
                    self._matchups()
                start = {"made": "made", "dreb": "dreb", "steal": "steal"}.get(result, "dead")
                off, de = de, off
            if period >= 4 and home.points != away.points:
                break
            if period >= 14:
                break

    def _late_timeout(self, off: TeamState, de: TeamState) -> bool:
        """Does the team gaining the ball call a late timeout (last two minutes of the 4th or of overtime)? A trailing
        or tied team then advances the ball to the front court."""
        L = self.L
        lead = off.points - de.points
        if abs(lead) > 10:
            return False
        t = self.t_left
        base = L["to_behind"] if lead < 0 else L["to_tied"] if lead == 0 else L["to_ahead"]
        p = base * (1.0 if t <= 30.0 else .5 if t <= 60.0 else .2)
        if self.rng.random() >= p:
            return False
        off.late_to -= 1
        self.late_timeouts += 1
        if lead <= 0:
            off.advance = True
            self.advances += 1
        return True

    def _trouble(self, team: TeamState) -> bool:
        lim = FOUL_TROUBLE.get(min(4, self.period), 6)
        if self.period == 4 and self.t_left < 300:
            return False
        return any(team.stats[i][S_PF] >= lim and team.stats[i][S_PF] >= 2 for i in team.on) and self.rng.random() < .5


def box_lines(team: TeamState, players: list[dict[str, Any]], items: list[dict[str, Any]], team_abbrev: str,
              starter_ids: set[str]) -> list[dict[str, Any]]:
    """Today's player-line format from the game's box score."""
    out = []
    coach = team.coach
    for i, item in enumerate(items):
        st = team.stats[i]
        p = players[i]
        if team.reserve[i] and team.secs[i] <= 0.0:
            continue                    # outside the rotation and never needed tonight: not in the box score
        extra = {}
        if coach is not None and coach.injured[i]:
            extra["in_game_injury"] = item.get("health_injury_label") or "injury"
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
            "personal_fouls": st[S_PF], "plus_minus": st[S_PM], "on_court_points_for": st[S_ON_FOR],
            "on_court_points_against": st[S_ON_AGAINST], "starter": p["id"] in starter_ids,
            # Screen assists only when the loop plays ball screens (stage2.screens); otherwise left out (rule 4).
            **({"screen_assists": st[S_SCR]} if team.screens_on else {}),
            **({"fouled_out": True} if st[S_PF] >= 6 else {}), **extra,
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
