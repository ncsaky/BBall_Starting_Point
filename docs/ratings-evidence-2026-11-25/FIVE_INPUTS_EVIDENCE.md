# Five flagged inputs checked against 2025-26 evidence (RATINGS-FIVE-INPUTS, 2026-11-25)

Stage 2's ninth piece (S2-USAGE) traced most of its per-player points and threes miss to five player inputs. This file
is the evidence check: every rotation player (377 with 500+ minutes in 2025-26), not only the flagged names.
"Match" is the correlation across those players; "spread" is how wide the input spreads relative to the evidence
(1.0 = as wide as real).

Tools: `scripts/research/five_inputs_evidence.py` (the comparison), `scripts/research/five_inputs_diff.py` (what moved),
`scripts/research/compact_nba_playtypes.py` (NBA.com tables → `data/research/nba_synergy_playtypes_2025_26.json`).

## Evidence used
- **Basketball Index 2025-26 (and 2023-24, 2024-25) per-75 tables** already in the repo: rim attempts, other two-point
  attempts, threes, average two-point shot distance, rim FG%, free throws, true usage, usage.
- **Basketball-Reference shooting** (in the repo): share of attempts within 3 ft, FG% there, dunks.
- **NBA.com play types, new** (Synergy, 2025-26 regular season, offense, per player; 11 tables): fetched 2026-11-25 in
  the built-in browser after plain requests were refused (403). Raw responses and source note:
  `output/ratings-evidence/nba_playtypes_2026/` (git-ignored, 2.4 MB); the tracked compact copy keeps, per player and play
  type, possessions, points, makes, attempts and possessions ending in free throws, plus the source URLs and date.
  NBA.com lists a player in a play type only with 10+ possessions; four rotation players are missing from the
  transition table altogether (Russell Westbrook with 1,071 possessions elsewhere, Precious Achiuwa, Marvin Bagley III,
  Micah Potter), so "absent" is treated as "not measured", never as zero.
- **The 32 public 2024-25 shot charts** in the repo (`data/research/shot_chart_reference.json`), to fit how average
  two-point distance splits short paint from midrange.

## Verdicts

| Input | Verdict | Why |
|---|---|---|
| Shot-location habit (T02) | **Fixed** | The two-point split was a position prior for 345 of 377 players |
| Involvement (T08) | **Left as is; proposal written** | It is true usage, as designed; a separate scoring-share input adds almost nothing |
| Rim finishing (layup S10, dunk S12, contact S15) | **Left as is (engine)** | The inputs predict real rim FG% better than Stage 2 turns them into makes |
| Foul drawing: contact seeking (T18) | **Fixed** | Built from free throws per 75 possessions (a volume) instead of per shot |
| Foul drawing: craft (S24) | **Left as is** | Already measured per chance against the same shots (foul-security evidence, 2026-11-21) |
| Transition habit (T17 transition share) | **Fixed** | Was a prior; now NBA.com transition share |
| Cutting (T09), offensive crash (T12) | **Left as is** | Basketball Index's cut and putback counts are the same tracking as NBA.com's (r .97); adding NBA.com would count the same plays twice |

### 1. Shot-location habit (T02): fixed
**What was wrong.** T02's three share was measured (season 3PA/FGA, r .997), but the rim / short-paint / midrange split
of the twos came from a 2024-25 shot chart for only 32 players and a fixed position prior (rim .38 of shots for bigs,
.27 for everyone else, before the three share) for the other 345. The rim share of a player's twos matched
Basketball Index at only r .42, spreading a third as wide as real.

**The rule now** (`bbi_evidence.apply_measured_shot_mix`, run in the build after the other Basketball Index steps):
- per season (2025-26 weight 1, 2024-25 .6, 2023-24 .35, times that season's two-point attempts): rim share of twos and
  other twos from Basketball Index's rim and "midrange" (all non-rim twos) attempts;
- the other twos are split into short paint (4-14 ft) and midrange (14 ft to the arc) by their average distance:
  logit(short share) = 5.57 − 0.425 × distance (ft), fitted at build time on the 32 charted players; out of sample it
  predicts their chart split at r .956 (typical error 3 points of share);
- blended with the earlier split by attempts against the estimator's own prior strength (100 attempts), the same
  rule as the three share; the three share is not touched.

| Match with real (2025-26) | Before | After |
|---|---|---|
| Rim share vs Basketball Index | .836 (spread .62) | **.964** (spread .79) |
| Rim share vs Basketball-Reference 0-3 ft | .804 | **.943** |
| Rim share of twos vs Basketball Index | .417 (spread .35) | **.921** (spread .72) |
| Other twos vs Basketball Index | .668 | **.974** |
| Three share vs Basketball Index | .997 | .997 (unchanged) |

The spread stays a little under 1.0 because three seasons are averaged and small samples are shrunk; one season of
real shots is noisier than a player's habit.

### 2. Involvement (T08): left as is, proposal written
T08 matches Basketball Index's true usage at .97 (spread .91): it measures how much of the offense runs through a
player, which is its approved meaning. Whether to carry "own scoring share" separately is answered in
[INVOLVEMENT_SCORING_SHARE_PROPOSAL.md](INVOLVEMENT_SCORING_SHARE_PROPOSAL.md): the existing action mix (T01) already
predicts real usage with T08 at .956; a scoring-share input from earlier seasons would add .002. No new input.

### 3. Rim finishing (S10 layup, S12 dunk, S15 contact): left as is, engine question
- Real rim FG% (Basketball Index) matches Basketball-Reference's 0-3 ft FG% at .94, so the target is solid.
- The inputs predict it at r .79 (mostly the layup grade; dunk and contact grades add little once it is known); S10 alone .75. S10 is built from
  difficulty-adjusted rim shot-making (assisted dunks and putbacks don't inflate it), which is the right skill
  measure; the remaining gap to real FG% is shot context (how many rim shots are lobs, putbacks, cuts and transition),
  which belongs to the engine.
- Stage 2 turns the inputs into rim makes at only r .67. The flagged cases point at the engine: Nolan Traoré has a
  low layup grade (30) and real rim FG% .46, yet Stage 2 gives him .56; Toumani Camara (layup 50, contact 41) makes .67
  in real games because his rim shots are cuts and transition finishes.
- Dunk execution (S12) has no direct Basketball Index measure; it is set from Basketball-Reference dunk rates net of body
  size (2026-11-19) and is unchanged.

### 4. Foul drawing: contact seeking (T18) fixed, craft (S24) left as is
- T18's reference condition is "one scoring attempt", but its main Basketball Index sources were free throws and fouls
  drawn **per 75 possessions**, which mostly measure how often a player shoots (T18 correlated .60 with involvement).
  The mapping's own note said to divide by shot attempts; it now does (`per_sum`: two- and three-point attempts).
- Match with real free throws per shot attempt: **.771 → .877**. Today's engine's free-throw rule had been carrying an
  extra negative involvement term to undo the volume; see the scorecards for the effect.
- S24 (craft) is measured per chance by the foul-security evidence (free throws earned against what an average player
  earns from the same drives, rim shots, other twos and threes). Unchanged.
- The inputs together (T18, S24, rim share, involvement) predict real free-throw rate at .93 already before this fix;
  part of Stage 2's excess for Jaren Jackson Jr., Anthony Davis and Jusuf Nurkić came from their rim share, which the
  T02 fix lowers.

### 5. Transition habit (T17 transition share): fixed
- Before: a fixed prior (offense .50 / defense .35 / transition .15, then renormalised), matching real transition play
  at r .32 (as a share of offensive effort).
- Now (`playtype_evidence.apply_transition_evidence`): transition share of his offensive-end effort = NBA.com transition
  possessions / all his play-type possessions, shrunk for sample size by a prior strength fitted from the data (43
  possessions: true spread across players vs sampling noise, so a rotation player's own number carries about 90%);
  the defense share (Basketball Index defensive distance) is kept and the rest split into offense and transition.
  Players without NBA.com data (deep bench, rookies, the four missing ones) get their earlier value placed on the
  measured scale by rank; the mapping is saved with the other measured scales so generated rookies match.
- Match (share of offensive effort vs NBA.com transition share): **.321 → .926**, spread .59 → .93, average .235 →
  .179 (real .181).
- Today's engine reads only T17's defense share (unchanged). Stage 2 reads the transition share to set how often a
  lineup runs.

## Side effects in the build
- **Skill grades moved very slightly** (mean under 0.08 grade points; a few players up to 1.2 on offense and 2.3 on
  defense: Zach Collins, Arthur Kaluma, Jordan Clarkson, Bam Adebayo, Goga Bitadze). The build's opening-day level step
  re-solves each veteran's skill level after his inputs change; the largest moves are players where that solver stops
  before converging (Collins, Clarkson and Branden Carlson are its "worst" list). No skill was set by hand.
- The age projection, rookie level step and analyst claims ran unchanged.

## Before/after tables
See `docs/agents/tasks/ratings-five-inputs.md` (flagged players, largest movers league-wide, scorecards).
