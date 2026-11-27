# S2-TENTH (Stage 2, tenth piece): waiting fixes, elite passers and defenders, engine guards

_Owner: Claude (Opus side session), worktree `ecstatic-antonelli-371621`, branch `claude/s2-tenth-df219d`. 2026-11-26.
Status: **review**._

Progress: 7/7 - report written, committed on the branch (not pushed); ready for the coordinator's review

## TL;DR
- **Found first: the main checkout plays on old ratings.** The unpacked ratings file every checkout reads
  (`data/canonical/player_inputs_2026_27.json`, git-ignored) is older than the committed `.json.gz` in the main checkout
  (23 Nov vs 25 Nov), so the game and any replay there still use the ratings from before the five-inputs fix. Fixed
  in Stage 2's loader (it reads the `.gz` unless the unpacked copy is at least as new); the coordinator made the same
  rule in `ratings_model.py` (9ec8eaad), so both agree.
- **Elite passers, stealers and shot-blockers are much closer to real**, with season points, threes and rebounds
  unchanged. Three engine causes fixed: whether a basket is assisted now depends on who is passing (Jokic 8.8 → 10.3
  assists per 36, real 11.1; top 20 passers 7.4 → 8.2, real 9.1), and a top shot-blocker or stealer no longer counts
  twice (top 20 blockers 2.95 → 2.55 per 36, real 2.55; stealers 2.46 → 2.32, real 2.37).
- **The three waiting fixes stay off**, plus two new menu fixes built here. Each makes its own layer clearly more
  realistic (transition runners, roll men, putbacks, post-ups match NBA.com much better), but none improves season
  points, threes, rebounds or assists per player beyond seed noise, and putbacks make points slightly worse. A new
  "hold each player's total" option fixes most of the harm, so they are ready when wanted (details below).
- **Engine guards:** a team with fewer than five players now plays with empty spots instead of crashing; a player hurt
  in a game leaves even when he plays less than planned; quadruple overtime happens about once in 10,000 games (about
  once every eight seasons), which is realistic; triple overtime may run a little high.
- Scorecards: betting pair within seed noise (shown with a pure re-randomization run), props level, 18/18 (closer to
  real: average distance .30 → .26), end of games unchanged, speed unchanged. 96 Stage 2 tests pass (7 new).

## Objective and boundaries
1. Switch on the three waiting fixes (putbacks by reach, rolls by screening, transition finisher) on the settled
   ratings, refit usage with them, sharpen post-up and cut weights with NBA.com play types; keep only clear gains.
2. Elite passers', stealers' and shot-blockers' numbers against real; fix engine causes; list rating questions.
3. Engine guards: short-handed lineups, injury exits, quadruple overtime.

Touched only `src/nba_gm_data/stage2/`, `scripts/research/`, a new Stage 2 test file and this file. Today's engine is
untouched (byte-identical). Stage 2 stays off in normal gameplay. No rating or input was changed.

## 0. Stale ratings file (found first; affects every checkout)
`data/canonical/player_inputs_2026_27.json` is a git-ignored unpacked copy of the tracked `.json.gz`. Both loaders
(`ratings_model._inputs_path` and `stage2/league_inputs._inputs_path`) use the unpacked file whenever it exists and
never check whether the `.gz` is newer. After a merge updates the `.gz`, the old unpacked file keeps being read.
Checked 26 Nov (checksums of the unpacked file vs the unpacked `.gz`):

| Checkout | Unpacked file | Matches the committed ratings? |
|---|---|---|
| Main checkout (where the game is played) | 23 Nov | **No** (pre-RATINGS-FIVE-INPUTS) |
| This worktree (before refreshing) | 24 Nov | No |
| `s2-multiseason-c06763` | 25 Nov 15:52 | No |
| `ratings-five-inputs-b34513` | 25 Nov 18:21 | Yes |

So my first "before" run matched the S2-USAGE numbers to the last digit: it was on the old ratings. Azure jobs copy
the unpacked file too. Done here: refreshed this worktree's copy, and Stage 2's loader now reads the `.gz` unless the
unpacked copy is at least as new (a locally rebuilt copy still wins; a stale one is left on disk, unread; test added).
The coordinator made the same rule in `ratings_model._inputs_path` (commit 9ec8eaad on main), so both loaders agree.

## 1. The three waiting fixes (kept off) and the menu
Measured on every 2025-26 game replayed 4 times (`s2_usage_fit.py eval`), 377 rotation players, per 36 minutes, against
real. Seed noise (same settings, two seeds): points miss 8.5-8.7%, threes 12.9-13.3%, rebounds 9.8-10.2%.

| Setting (seed 3001 / 5001) | Points miss | Threes | Rebounds | Its own layer vs NBA.com play types |
|---|---|---|---|---|
| Before | 8.7% / 8.5% | 13.3 / 12.9% | 9.8 / 10.2% | transition .56, cuts + rolls .67, putback points .85 (real 1.05) |
| Transition finisher alone | 9.2% / — | 13.8% | 10.1% | transition .74 |
| Putbacks by reach alone | 9.1% / — | 13.2% | 10.1% | putback points 1.04 |
| Rolls by screening alone | 8.8% / 8.6% | 13.1 / 13.0% | 10.0 / 10.2% | cuts + rolls .74 |
| Transition, held total (new) | 8.6% / 8.5% | 13.7 / 13.1% | 10.0 / 10.4% | transition .74 |
| Putbacks, held total (new) | 9.0% / 8.7% | 12.9 / 12.7% | 10.1 / 10.3% | putback points 1.03 |
| All three, held total | 9.2% / — | 13.1% | 10.3% | all three as above |
| Transition held + rolls | — / 8.5% | 12.8% | 10.2% | transition .74, cuts + rolls .75 |

Why the fixes hurt at first: the usage rule is fitted to each player's total possessions. The transition fix gave fast
guards extra possessions on top (Ja Morant 25.6 → 27.4 usage per 36, points 23.9 → 27.6 vs real 24.6) and took them
from slow centres who were already short (Paul Reed, Jock Landale, Isaiah Stewart, Al Horford). Putbacks did the same
for bigs who already shoot more than real (Mark Williams, Neemias Queta, Luke Kornet, Deandre Ayton). Refitting the
usage rule through the loop (as S2-USAGE recommended, with speed, pace, reach and cutting terms) overfit: the fit half
got better, the held-out half's usage miss got worse (1.23 → 1.34 per 36).

New engine option, **hold each player's total** (`LOOP mix_hold`): what the transition or putback tilt gives a player
is taken back from his half-court draws, so the fixes change his mix of possessions, not how many he ends. It removes
most of the harm (transition: points 9.2% → 8.6%), but nothing beats "before" beyond noise.

**Post-ups and cuts (new, also off).** Rim-running centres took 3-5 post-up hooks per 36 against 0.3-1.4 real post-ups
(Jarrett Allen 3.6 vs 1.2, Ayton 4.2 vs 1.4, Raynaud 4.7 vs 1.4, Poeltl 2.9 vs 0.3) while getting half their real cut
and roll finishes. Cause: the short-paint split had no "finish off a pass", so a big's measured short-paint shots
became hooks. Built: a new shot type, `short_finish` (a short roll, cut or dump-off finish: roll-and-cut foul and
defense terms, make chance halfway between his hook and his floater, assisted 85% as a stand-in), and powers on the
drive, cut, roll and post habits (`MENU short_fin`, `drive_pow`, `cut_pow`, `roll_pow`, `post_pow`). Fitted offline
on NBA.com play types (`s2_menu_fit.py`, fit half, checked on the other half), with rolls by screening on:
`rim_cut .5, rim_roll .75, rim_post .76, short_post 4.0, cut_pow 1.35, roll_pow 1.45, post_pow 1.7, short_fin .2`.
Held-out half: cuts + rolls miss 1.07 → 1.00 per 36, correlation .76 → .82; post-up miss .85 → .67 (level 1.17 → 0.43
against a real 0.57; correlation .80 → .74). In games: cuts + rolls match NBA.com at .80 (was .66). Per player:
points 8.5 → 8.4%, threes 13.1 → 12.9%, but assists 12.5 → 13.1% and rebounds 9.9 → 10.1%. Not a clear gain: off.

**Verdict:** all five switches stay off, as the task asked when there is no clear gain. All are documented in `LOOP` /
`MENU` with the fitted values. My recommendation for a later piece: transition (held) plus rolls by screening are level
on every per-player measure and clearly more realistic on their own layer, so they could go on if the user values the
action mix itself; the menu refit needs its assist and rebound cost understood first.

## 2. Elite passers, stealers, shot-blockers (kept on)
The multi-season report's assist numbers predated the S2-USAGE assist refit; rechecked here first. After that refit the
elite passers were still about 20% short while the league total was right.

**Engine causes and fixes** (`stage2/game.py`):
1. **Assisted chance by who is passing** (`k_ast_team` 2, `ast_team_shift` .36). Before, whether a made shot was
   assisted depended only on its type, so a lineup with Jokic was assisted no more often than any other; he only took a
   bigger slice. Real teams' assisted share spreads .034 across the 30 teams; Stage 2's spread .015 and followed the real
   team order at .17. Now the log-odds of an assist rise with the scorer's teammates' passing: spread .022, order .45.
   Power 3 matched the real team spread and lifted the elite further (top 20: 8.5), but pushed mid-level players'
   season assists further from real (props 13.2% vs 12.3-12.5%), so 2.
2. **Blocks counted the shot-blocker twice** (`k_blk_level` .8, `blk_scale` .905). His weight raised his five's chance
   of a block and then took most of the credit. League blocks also ran 10% high (.80 vs .72 per 36).
3. **Steals, the same double count** (`k_steal_level` .5, `steal_share` .62 → .628 to hold the league level).

Assists and blocks are credit only (the game plays the same, but the extra or missing draw moves the random sequence).
A steal starts a fast break, so the steals fix changes games slightly; league steals are held at real.

Per player (every 2025-26 game replayed 4 times, two seeds; rotation players; per 36):

| | Before | After | Real |
|---|---|---|---|
| Assists: miss / correlation with real | 12.5% / .946 | 12.2-12.3% / .956 | |
| Real top 20 passers' average | 7.4 | 8.2 | 9.1 |
| Steals: miss / correlation | 15.1% / .88 | 12.7-13.1% / .89-.90 | |
| Real top 20 stealers' average | 2.46 | 2.30-2.33 | 2.37 |
| Blocks: miss / league level | 28% / .80 | 26% / .71 | .72 |
| Real top 20 shot-blockers' average | 2.95 | 2.53-2.56 | 2.55 |
| Points / threes / rebounds miss | 8.5-8.7 / 12.9-13.3 / 9.8-10.2% | same | |

| Assists per 36 | Before | After | Real |
|---|---|---|---|
| Nikola Jokić | 8.8 | 10.3 | 11.1 |
| Cade Cunningham | 8.2 | 9.6 | 10.5 |
| Josh Giddey | 7.9 | 8.5 | 10.3 |
| LaMelo Ball | 7.4 | 8.4 | 9.2 |
| Luka Dončić | 6.8 | 8.4 | 8.3 |
| James Harden | 7.8 | 9.0 | 8.2 |

| Steals per 36 | Before | After | Real | | Blocks per 36 | Before | After | Real |
|---|---|---|---|---|---|---|---|---|
| Alex Caruso | 3.54 | 2.90 | 2.54 | | Victor Wembanyama | 4.27 | 3.55 | 3.79 |
| Cason Wallace | 3.05 | 2.72 | 2.64 | | Jay Huff | 3.59 | 2.82 | 3.20 |
| Ausar Thompson | 2.97 | 2.87 | 2.77 | | Ryan Kalkbrenner | 3.45 | 3.11 | 2.46 |
| Dyson Daniels | 2.81 | 2.60 | 2.13 | | Chet Holmgren | 4.01 | 3.21 | 2.37 |
| Dru Smith | 2.50 | 2.31 | 3.16 | | Brook Lopez | 4.02 | 2.96 | 1.92 |

## 3. Engine guards
- **Fewer than five players** (`stage2/engine.py`, `cards.empty_card`): the team plays with "empty spots" instead of
  failing. A spot never shoots, passes, rebounds, screens, steals or blocks, and defends as badly as the scale allows,
  so the scorer it is matched with is left open (four against five, as today's engine plays it). It is never in the box
  score; the team's points still equal its players' points. Normal games are untouched (only used below five). Test:
  a replayed game with the home team cut to four players.
- **In-game injury exits** (`stage2/coach.py`, `COACH injury_clock` 1): a player hurt in a game left only once he had
  played his drawn share of his planned minutes, so one who played less (a blowout, foul trouble) never left. He now
  also leaves once the game reaches that share of regulation. Only generated games carry in-game injuries, so replays
  and the betting test are unaffected.
- **Overtime** (`s2_overtime_check.py`; real: play-by-play 2023-24 to 2025-26, 3,690 games):

| Per 10,000 games | Overtime | Double | Triple | Quadruple | Overtimes ending tied |
|---|---|---|---|---|---|
| Real 2023-26 | 485 | 54 | 0 | 0 | 10% |
| Stage 2 replays (19,696 games) | 412 | 45 | 9 | 0.5 | 13.5% |
| Stage 2 generated (9,848 games) | 513 | 43 | 10 | 1.0 | 11% |

Quadruple overtime comes about once per 10,000 games, about once every eight seasons: realistic. The two in the
four-season run were mostly bad luck. Triple overtime may run a little high (real: none in three seasons, where
Stage 2's rate would expect about three), because a second overtime ends tied more often (18-21%) than a first
(11-13%). Small samples; no change made.

## 4. Scorecards (before → after)
**Betting test** (20 runs, 1,018 games with market odds). "Reshuffled" is the old settings with one random number
burned at tip-off: it changes nothing but the random sequence, so it shows the seed noise.

| Seed | Before | Reshuffled (noise) | **After** |
|---|---|---|---|
| 1001: win-probability score / log loss | .1983 / .5824 | .1960 / .5767 | **.1975 / .5829** |
| 1001: spread / totals miss | 4.14 / 5.84 | 4.03 / 5.84 | **4.19 / 5.98** |
| 2001: win-probability score / log loss | .1959 / .5790 | .1963 / .5781 | **.1970 / .5786** |
| 2001: spread / totals miss | 4.04 / 5.72 | 4.05 / 5.95 | **4.04 / 5.78** |
| Average score / log loss / spread / totals | .1971 / .5807 / 4.09 / 5.78 | | **.1973 / .5808 / 4.11 / 5.88** |

Within seed noise. Two more seeds with an earlier setting (power 3) agreed (seed 3001 .1958 → .1949, 4001 .1954 →
.1973; totals 5.75 → 5.95, 5.82 → 5.82). Seeds 1001 and 2001 are the ones earlier pieces tuned on, so any reshuffle
tends to look slightly worse there.

**Player props** (`s2_props.py`, 40 games of market points lines at 200 runs; every player-game, 8 runs):

| | Before | Reshuffled (noise) | **After** |
|---|---|---|---|
| Market lines: score / log loss | .2114 / .6101 | .2141 / .6149 | **.2106 / .6071** |
| Points per game: miss / correlation | 4.36 / .737 | 4.35 / .738 | **4.40 / .732** |
| Rebounds | 1.85 / .678 | 1.86 / .677 | **1.86 / .674** |
| Assists | 1.39 / .695 | 1.39 / .696 | **1.39 / .701** |
| Threes made | 0.95 / .543 | 0.94 / .544 | **0.95 / .538** |
| Season points / rebounds / assists / threes off by | 11.3 / 11.2 / 12.3 / 10.7% | 11.3 / 11.0 / 12.5 / 10.4% | **11.5 / 11.3 / 12.5 / 10.5%** |

**Real-stat scorecard** (150 generated games, seed 1): 18/18 before and after; average distance from real .30 → .26
(blocks per 100 5.33 → 4.85, real 4.72; assists 24.9 → 26.5, real 26.1).
**End of games** (19,696 replayed games, 16 runs): overtime 4.1% → 4.0% (real 4.7%); 1-3 point finishes 13.1% →
12.6% (real 12.7%).
**Speed** (400 games, best of three, laptop with other sessions running): before 8.4-10.4 ms per replayed game and
9.3-11.0 per generated game, after 8.2-9.1 and 9.9-10.6. No change beyond the machine's noise.
**Tests:** 96 Stage 2 tests pass, 7 new in `tests/test_stage2_tenth.py`. With the new values switched back, the code
plays exactly the same games as the starting commit (20 games checked score by score).

## Weak spots
1. **No per-player scoring gain.** Season points and threes per player are where they were (8.5% / 13% in replays;
   today's engine is still better at splitting points). The waiting fixes improve realism of the action mix only.
2. **Passers still short at the very top:** Giddey 8.5 (real 10.3), T.J. McConnell 7.9 (10.7), the Nembhards 6.6 / 7.3
   (8.8 / 9.7). A few bigs and scorers got too many (Şengün 8.5 vs 6.7, Middleton 6.7 vs 4.4).
3. **Totals miss** is 0.1 higher on average after; the reshuffle shows that size of move from noise alone, but it
   deserves a look with more seeds when convenient.
4. Fits were at 4 replays per setting; differences under about 0.3 points in the miss percentages are noise.
5. The `short_finish` make chance and its 85% assisted rate are stand-ins.

## Rating questions (flagged; nothing changed)
1. **Blocks for drop-coverage centres.** Stage 2 after / real per 36: Wendell Carter Jr. 2.07 / 0.77 (contest technique
   S37 74, interior positioning S36 80, jump-contest habit .316, help commitment .559); Ivica Zubac 2.16 / 1.00 (S37 85);
   Brook Lopez 2.96 / 1.92 (S37 85, jump habit .374); Chet Holmgren 3.21 / 2.37 (S37 92); Thomas Bryant 2.53 / 1.28.
   Possibly an engine part too: the lineup's top rim protector always gets the 1.5x help share of block credit.
2. **Blocks too low:** Moussa Cissé 1.49 / 3.07 (S36 61, jump habit .265); Matas Buzelis 1.13 / 1.86 (S36 40).
3. **Steals:** Dyson Daniels 2.60 / 2.13 (interception S43 88, ball pressure S42 91); Jonathan Isaac 1.98 / 1.38 (S43
   73); Draymond Green 1.75 / 1.17; Dru Smith 2.31 / 3.16 (S43 83); Kevin Porter Jr. 1.74 / 2.37 (S43 81).
4. **Pass-first guards' passing habit.** Assist inputs are nearly identical for players with very different real assists:
   Giddey (pass choice T01.pass .151, involvement T08 .419, passing risk T07 .461, real 10.3) vs Tre Jones (.166 /
   .361 / .460, real 7.2; Stage 2 8.4); Andrew Nembhard (.136 / .369 / .408, real 8.8; Stage 2 6.6); T.J. McConnell
   (.151 / .459 / .438, real 10.7; Stage 2 7.9). The pass-choice habit may not carry how much of a team's creation runs
   through the player.

## Files
- Changed: `src/nba_gm_data/stage2/game.py` (assists by passing; block and steal levels; hold-the-total option; empty
  spot left out of the box score), `cards.py` (short-finish shot type, menu powers, `empty_card`), `engine.py` (empty
  spots; league assist mean), `coach.py` (injury exit by game clock), `league_inputs.py` (reads the .gz unless the
  unpacked inputs are at least as new),
  `loop_fit.py` (half-court kinds by name); research scripts `s2_usage_fit.py` (steals, blocks, top-20 measures),
  `s2_playtype_compare.py`, `s2_usage_breakdown.py` (new shot type in groups).
- New: `scripts/research/s2_tenth_players.py`, `s2_menu_fit.py`, `s2_team_assists.py`, `s2_overtime_check.py`,
  `s2_speed.py`, `tests/test_stage2_tenth.py`, this file.
- Output (git-ignored): `output/s2t/` (evaluations, player tables, betting runs, props, scorecard, end of games).

## Resume state
- [x] Reports read; stale inputs found, coordinator told, Stage 2 loader fixed.
- [x] Waiting fixes measured (alone, held, together, with usage refit); menu fitted and measured; all kept off.
- [x] Assists, blocks, steals: causes found, fixed, fitted (power 2 chosen over 3 on props).
- [x] Guards: empty spots, injury clock, overtime check.
- [x] Final betting pair (`output/s2t/odds_final_*`), noise runs (`odds_burn_*`), props (`props_final.json`,
  `props_burn.json`), scorecard (`cal_after.txt`), end of games (`endgame_after.txt`), speed, 96 tests.
- [x] Committed on the branch, not pushed. Coordinator: review and merge. Stage 2's loader uses the same rule as
  `ratings_model._inputs_path` (9ec8eaad).
