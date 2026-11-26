# Drafted and generated players: shot mix and turnovers (ROOKIE-THREES, 2026-11-26)

Reproduce every table: `scripts/research/rookie_threes.py` (`real`, `habits`, `league`, `run`).

## 1. Real players: first and second seasons shoot as many threes as the league and turn it over more

ESPN regular-season career totals (`data/research/player_career_stats.json`, every player on a 2026 roster; positions
and roles from the 2026-27 universe). "First and second years" = seasons one and two after the draft year.

| Season | Group | Minutes | Share of shots from three | Turnovers per play |
|---|---|---|---|---|
| 2023-24 | first and second years | 85,262 | .390 | .125 |
| 2023-24 | everyone else | 437,281 | .389 | .114 |
| 2024-25 | first and second years | 93,806 | .437 | .130 |
| 2024-25 | everyone else | 464,633 | .414 | .119 |
| 2025-26 | first and second years | 107,858 | .413 | .135 |
| 2025-26 | everyone else | 480,520 | .415 | .119 |

Turnovers per play = turnovers / (shots + .44 free throws + turnovers).

Within a position or role, young players take 1-5 points fewer of their shots from three (pooled 2023-26: point
guards .369 vs .401, shooting guards .455 vs .501, centers .138 vs .178), but young classes hold more guards and wings,
so as a group they match the league. Within a position they also turn it over 4-14% more per play. Full tables by
position and by offensive role: `rookie_threes.py real`.

No clear age pattern in how a player's own three share changes from one season to the next (players with 100+ shots
in both of two seasons: ages 22-23 -.015 a season, 24-26 +.017, 27-30 +.011, 31+ +.021; the 2024-25 league-wide jump
inflates every band), so frozen shot habits are not why the league drifts.

## 2. Cause: generated players' habits were hand-set role guesses

Draft classes from 2027 on (fictional prospects and real college prospects alike) are built by
`input_estimator._generated_definition_inputs`. Their skills and involvement already came from the 24 real players
nearest them in ability, linked profile and position. Every other habit started from a fixed guess in
`_tendency_inputs`: three share .38 for any guard or wing (.43 if labelled a shooter, .22 for a big), dribble
persistence .38 unless labelled a creator, and so on, then a small profile tilt.

Generated players (179, three classes) against the 24 nearest real players (ability and position) and the real 2025
and 2026 draft classes:

| Habit | Position | Generated before | Generated after | 24 nearest real | Real 2025-26 draftees |
|---|---|---|---|---|---|
| Three share (T02) | guard | .400 | .424 | .436 | .427 |
| Three share (T02) | wing | .383 | .409 | .433 | .422 |
| Three share (T02) | big | .195 | .229 | .229 | .197 |
| Midrange share (T02) | guard | .161 | .130 | .114 | .125 |
| Dribble persistence (T06) | guard | .478 | .607 | .600 | .586 |
| Dribble persistence (T06) | wing | .349 | .418 | .425 | .404 |
| Passing risk (T07) | wing | .340 | .360 | .364 | .362 |
| Pass choice (T01) | guard | .100 | .113 | .116 | .115 |

Stage 2's turnover rule on generated players' inputs, against their 24 nearest real players: -0.18 log-odds before
(about 16% fewer turnovers, matching the 17% fewer per play they committed in play), -0.065 after. The rest is mostly
generated bigs driving more than ability-matched real bigs, because the draft generator gives them more rim pressure;
the new rule follows that profile.

## 3. Fix (rule-level, no real player changes)

Every habit except involvement (which already did) now comes from the real players nearest the generated player in
ability, the linked legacy profile (the same links that drove the old tilt; per outcome for shot-location and the other
mixes) and position, with the same 24-neighbour weights as his skills, plus the existing small stable per-player
detail. No profile tilt on top (the profile already picks the neighbours). The action mix (T01) and transition share
(T17) are then already on the real players' measured scale, so `bbi_evidence.map_tendency_inputs` no longer
translates them a second time for generated players. Real players' inputs are untouched; nobody in the opening-day
league is generated (the first 60 arrive at the first rollover), so season 1 is identical (checked: all 1,318 Stage 2
games of season 1 match exactly).

Display: generated players' shooting-range and release grades follow their three share (trait adapter), so generated
shooters now show slightly higher shooting grades and a slightly higher three-point percentage in today's engine. That
is the same mapping real players use.

## 4. Four seasons (seed 20261125, Miami), before and after

See the task report (`docs/agents/tasks/rookie-threes.md`) for the full tables.
