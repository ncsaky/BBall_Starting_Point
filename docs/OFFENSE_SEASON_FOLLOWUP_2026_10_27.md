# V9 Retention And Box-Score Follow-Up

## Decision

Keep the V9 interior-offense changes. This review changes no game rules,
canonical ratings, minutes penalties, development, UI or saves. No additional
seasons were run. The inspected backend files match the frozen V9 experiment.

The most actionable retention issue is **signing/roster-plan inconsistency**,
not evidence for another blanket center buff or a prospect nerf. The user's
separate complaint about repetitive secondary statistics is strongly reproduced.

## Evidence And Limits

Machine-readable report:
`output/offense-season-followup-2026-10-27/detail/review.json`.

Read-only script: `scripts/review_offense_season.py`.

Four saved first seasons were inspected: V8 and V9, seeds 29 and 913. Each
contains exactly 1,230 regular-season games. V8's completed careers contain a
second season, but this review excludes it from games, transactions, roster
observations, market offers and exits. Manifest-visible SQLite history and live
tails are deduplicated using the history API. All four save JSON/history hashes
remained unchanged during review. No playable saves were loaded.

These remain historical, path-dependent comparisons, not randomized causal
estimates. Identical seed labels do not keep subsequent trades, injuries,
staff decisions or random draws identical after model behavior diverges.
Monthly observations bracket transitions; exact transaction dates are available,
but exact cut-time candidate rankings were not logged. September roster views
are not presented as those missing rankings.

## Which Centers Lost Spots?

Same initial 39-player nonspacing-center cohort as the overnight report:

| Seed | Retained in V8, not V9 | Retained in V9, not V8 |
| --- | --- | --- |
| 29 | Kevon Looney, DeAndre Jordan, Oso Ighodaro | Clint Capela |
| 913 | Day'Ron Sharpe, Deandre Ayton | Oso Ighodaro |

### Looney, Seed 29

- Played all 82 games, 17.41 MPG, in V9.
- Memphis signed him July 4 for **$7.4M annually, two years**. The offer's
  player-interest context estimated 20.6 MPG.
- September 1: Memphis had **21 players**, including five centers. Looney's
  projection was zero; Edey, Stewart and Post had projected roles.
- October 1: Memphis cut him while shrinking to 15 players. Looney remained an
  available free agent, not a retirement or league exit.
- Fixed-24-minute engine rating was **54.2 in both V8 and V9** at the endpoint.
  V8 Atlanta retained him, but also projected zero minutes. That retained count
  does not establish a useful veteran rotation role in the control.

### Sharpe, Seed 913

- Played **69 games at 26.70 MPG**, with 13 games missed during the season.
- June 27: projected 28.76 MPG. September: Brooklyn had 21 players and his
  projection was zero, while Nick Richards and newly signed Looney had roles.
- October 1: cut to reach 15, not retired or permanently removed.
- His fixed-minute engine rating rose slightly, **54.3 to 54.6**, from the
  season-opening observation to the next October. V8 and V9 endpoint fixed-minute
  ability were both 54.6. The displayed OVR fall to 71.1 largely reflects loss of
  role, not a collapse in underlying talent.

### Ighodaro, Seed 29

- Played **81 games at 19.35 MPG**, one missed game.
- Phoenix's roster grew to 21 with five centers. By the pre-cut snapshot his
  projected minutes were zero. Williams, Maluach, Vukcevic and a generated center
  had roles.
- Cut October 1. Fixed-minute engine rating was **53.2 in both versions** at
  the endpoint. In seed 913 the direction reverses: V9 retains him, V8 cuts him.
  This is not consistent evidence of a V9-specific Ighodaro rating failure.

### Ayton, Seed 913

- Traded from Washington to Milwaukee October 12; played 32 games at 24.80 MPG.
- A generated January 2 knee injury carried 132 expected days out; the final
  regular-season census recorded 50 games missed. This is a genuine availability
  complication, not evidence that healthy centers were universally ignored.
- Chicago nevertheless signed him July 4 for **$4.6M annually, two years**;
  the offer context estimated 22.7 MPG.
- Chicago reached 21 players, projected him at zero minutes, and cut him October
  1. V8 Minnesota retained him only through September's automatic depth repair.
- Fixed-minute endpoint ability was **45.9 in both arms**. This review does not
  validate that imported rating as an accurate real-world assessment of Ayton.

### Older/Fringe Exits And Positive Outcomes

Jordan was traded to Charlotte, cut June 25 and archived September 1 as an
unsigned fringe league exit, not a true retirement. V8 instead gave him a Boston
automatic depth-repair contract. Eubanks, Powell, Tshiebwe and Cardwell also
left the active pool in both arms; those common departures are preserved in the
report rather than hidden by net retained counts. Diabate and Jemison remained
available rather than being silently deleted. Capela was traded to New York in
V9 and retained; in V8 he was cut and later archived.

## The Structural Retention Gap

Across **all positions**, not just centers:

| Arm | Seed | Summer FA signings | Same-team cuts next October 1 |
| --- | --- | ---: | ---: |
| V8 | 29 | 76 | 20 |
| V8 | 913 | 54 | 11 |
| V9 | 29 | 70 | 14 |
| V9 | 913 | 67 | 15 |

Thus **29/137 V9 summer signings** were cut by the same signing team at the
next regular-roster deadline. These are ledger-recorded FA signings, not unsigned
camp invitations, automatic depth signings or mere offers. The signings carried
$210.4M in combined annual face value. This figure is **not** an audited claim
about guaranteed money paid or dead-cap accounting.

Verified code paths:

- `play.py:4976`: bidding reserves money and up to 21 offseason roster slots.
  Suitor selection and the admission loop do not project whether a bid survives
  the final 15-player cutdown.
- `play.py:5072`: offer role expectations are estimated separately from an actual
  post-signing roster/rotation projection. Looney and Ayton's attractive role
  estimates did not resemble their eventual zero-minute roles.
- `save.py:1056`: retention ranks OVR, projected minutes, youth/upside, age and a
  small cheap-contract bonus. It does not directly consume the new offensive
  facets. It clears temporary injury availability through a healthy projection,
  so a simple current-injury-zero-minutes explanation is insufficient.
- `save.py:6893`: OVR itself already includes projected minutes. Retention then
  adds another minutes bonus. A player displaced from the rotation can lose
  value twice even with unchanged underlying skills. The direction is verified;
  exact contribution to each historical cut is not logged.

**Recommended next retention fix:** make paid AI signings pass a prospective
final-roster/rotation check, including incoming rookies, existing commitments,
replacement value and role overlap. A team may rationally replace a player;
it should plan that replacement before signing redundant paid depth. Do not
simply forbid all rosters over 15, guarantee every signing a roster spot, waive
someone immediately just to hide churn, or grant centers categorical immunity.
Evaluate a role-neutral specialist score for cuts alongside this shared planning
view; do not change user scoring/minute penalties as a shortcut.

## Box-Score Variability

The user prioritizes realistic sequences of games over an individual plausible
box score. These measurements distinguish pooled variation from variation within
the same team and include per-player and stable-role summaries in the JSON.

Fresh reference: 72 evenly spaced cached 2025-26 regular-season game IDs were
requested directly from ESPN. **70 complete games / 140 team lines** passed the
named-field parser and score reconciliation. Two malformed/missing responses
were excluded and recorded. This is a descriptive sample, not a precise league
distribution target, matched opponent experiment or independent calibration set.
Player-turnover sums exclude team turnovers in both the reference and sim.

The request URLs and failures are preserved in
`output/offense-season-followup-2026-10-27/espn-reference-72.json`.
Example primary endpoint:
https://site.api.espn.com/apis/site/v2/sports/basketball/nba/summary?event=401809243

Standard deviations of individual team-game outcomes:

| Statistic | V9 seed 29 | V9 seed 913 | Fresh ESPN sample |
| --- | ---: | ---: | ---: |
| Points | 12.82 | 12.76 | 11.81 |
| Rebounds | 1.51 | 1.50 | 6.62 |
| Assists | 1.52 | 1.47 | 5.08 |
| Player turnovers | 1.00 | 1.00 | 4.38 |
| Steals | 0.45 | 0.50 | 3.15 |
| Blocks | 0.65 | 0.69 | 2.66 |
| FG percentage points | 3.48 | 3.58 | 5.10 |
| 3PT percentage points | 8.41 | 8.79 | 6.97 |

Within-team variation is even narrower: rebounds SD ~1.2, assists ~1.15,
turnovers ~0.94, steals ~0.34 and blocks ~0.36. Between-team ability differences
therefore do not explain away the compression. V8 already had it. Older V8
shooting also closely reproduces the user's ~42%-every-game observation: pooled
FG% was ~42.8% with only ~1.17 percentage points of SD. V9 improved this but did
not fully fix FG variability.

At the individual level, Curry had **exactly two turnovers in all 67 seed-29
appearances and all 65 seed-913 appearances**. Edey had exactly one steal in
78/79 appearances in seed 29. These are directly saved box scores, not UI
rounding or season-average displays.

### Verified Mechanisms

- `sim.py:1331-1352`: secondary team totals are normalized to targets with only
  **12-18% of raw fluctuations**, then rounded and clamped. This removes much
  of the variation that initial player draws supplied. Rebound/assist totals
  also are not reconciled against the other generated shooting outcomes.
- `sim.py:1221-1223`: turnovers/steals/blocks begin with a deterministic
  minute-rating term plus a narrow uniform random addition before rounding.
  Some players consequently repeat one integer essentially every night.
- `sim.py:1415-1448`: legacy total FGA is reconstructed from made baskets and
  a nearly fixed target FG%. This produces plausible-looking final scores
  without plausible shooting-efficiency variation.
- `offense.py:210`: V9 properly samples individual 3PT makes, so 3PT variance
  is not currently deficient in these careers. But 2PT attempts are still
  reconstructed from makes divided by expected accuracy, plus noise SD 0.6.
  This remains a much narrower 2PT-efficiency mechanism than sampling misses
  and makes. Points are chosen first and shooting is forced to fit afterward,
  which also restricts realistic cold-shooting/attempt-volume combinations.

**Do not add generic extra noise to all statistics.** Prioritize secondary-stat
event counts and shooting-opportunity reconciliation; keep ability, role,
minutes, opponent pressure, pace and available missed shots meaningful. Preserve
deterministic per-game seeding and daily/bulk/save-reload consistency. Any change
to the V9 shot generator must retain the V8 legacy branch for existing careers
unless migration is separately approved.

### Additional Accounting Findings

All four seasons passed existing player/team sums, shooting identities, counts,
final scores and minute-accounting checks. The expanded review found **15 V9
team-games with more assists than made field goals** (7 and 8 by seed), versus
2 in V8. This is a genuine accounting problem to fix with opportunity-aware
assists, not proof that the existing tests certified every basketball constraint.
No steals-over-opponent-turnovers or blocks-over-opponent-missed-FGA violations
were found. Rebounds were not certified against a full possession ledger.

Free-throw volume tuning is deliberately not a priority in this pass. However,
the all-box-score review also measured V9's weighted season FT% at about 87%,
and unweighted team-game FT% near 87%. The point-budget/parity adjustment can
raise realized accuracy; flag this for a later shooting-accounting check, not a
reason to change volume now.

The old cached research box scores contain missing `fgm`/`fga` despite having
other stats. They were used **only for selecting reference game IDs**, never
as zero-FG observations. Fresh data uses ESPN's named `FG` label, with scoring
identity checks. V9 historical shot priors use the separate career-stat source,
not this defective cached box-score FG field. This review does not repair or
recertify other consumers of the older cache.

## Next Implementation Boundaries

1. Cut-aware paid signing decisions and consistent specialist retention. Test
   crowded teams resembling MEM/BKN/CHI/PHX, rational upgrades over incumbents,
   non-overflow teams, pending bid reservations, rookies, temporary injuries,
   real long-term injury effects and user-rotation preservation. Replay short
   saved offseason windows, not another multi-season batch. Do not require
   these four named players always be kept.
2. A versioned box-score distribution fix. Test meaningful within-team and
   fixed-minute within-player variance, realistic rare low/high outcomes,
   assists <= FGM, steals <= opponent TO, block/miss constraints, exact player
   sums, minutes and shooting identities, plus seed/reload/advance-length
   consistency. Establish baseline means and avoid accidentally raising
   averages while widening distributions. Do not blindly increase V9 3PT noise
   or change final-score variation merely because secondary stats are faulty.

## Verification

28 focused tests passed: six new read-only review/parser tests, five overnight
harness tests, seven existing basketball-accounting tests and ten offensive-role
tests. This is not a full-suite claim. The audit's basketball failures are
reported findings, not silently excluded tests. No pending simulation work remains.

To regenerate without fetching more data, choose a new output directory:

```sh
PYTHONPATH=src:scripts .venv/bin/python scripts/review_offense_season.py \
  --output output/offense-season-followup-rerun \
  --reference-cache output/offense-season-followup-2026-10-27/espn-reference-72.json
```
