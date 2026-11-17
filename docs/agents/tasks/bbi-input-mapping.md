# BBI → player-model input mapping

TL;DR: Basketball Index (BBI) now has a reviewed map to all 94 player-model inputs: 195 metrics feed specific inputs, up from 32 in the estimator.
BBI is strongest on shooting by type, finishing, rebounding, screen and isolation defense, foul discipline, steals, and shot/possession habits. It is weakest on physical tools (height and weight only), box-outs, closeouts and specific pass types.
The map is data only. No code changed. The estimator still has to be switched over to read it.

## What was delivered

- `data/research/bbi/bbi_input_mapping.json` (tracked): for every one of the 94 inputs, the BBI metrics that inform it, with the direction (does higher mean better/more?), the strength (primary / supporting / weak), a one-line reason, a coverage label and a note on what BBI can't tell us. The file has BBI metric names only, none of BBI's definition text.
- All 664 BBI metrics are accounted for: 195 mapped to inputs, 450 marked "context only" (coach usage, role, who they guard, teammates, team scheme, overall impact like LEBRON, plus aggregate efficiency kept for the real-stat calibration targets), and 19 excluded (game-to-game consistency, duplicates, fantasy points, one ambiguous metric).
- The four layers stay separate. No metric is used by both a skill input and a tendency or physical input. Skills get per-shot, per-attempt and versus-expected quality measures. Tendencies get frequencies and shares. Physical inputs get only listed height and weight, plus weak in-game speed.

## Coverage by layer

| Layer | Good | Partial | None |
|---|---|---|---|
| Physical tools (12) | 2 (height, weight) | 1 (straight-line speed, weak) | 9 |
| Technique skills S01–S46 (46) | 18 | 21 | 7 |
| Passing recognition/execution (18) | 0 | 18 | 0 |
| Tendencies (18) | 6 | 12 | 0 |
| **Total (94)** | **26** | **52** | **16** |

"Good" means a direct, player-level quality or frequency measure exists. "Partial" means BBI only covers part of the input, or covers it indirectly. "None" means BBI has nothing usable.

## The 10 inputs where BBI helps most

1. **Catch-and-shoot threes**: per-shot shot-making versus expected, plus stabilized percentage.
2. **Pull-up threes**: the same, for pull-ups.
3. **Pull-up midrange**: per-shot shot-making versus expected.
4. **Layups / close finishing**: rim shot-making versus expected and stabilized rim percentage.
5. **Handle security**: turnovers per isolation possession, per touch, and stripped-ball losses.
6. **Foul-drawing craft**: fouls drawn per drive and per isolation.
7. **Rebound control**: BBI's offensive and defensive rebound conversion skill and win rates.
8. **Screen navigation**: ball-screen and off-ball-chaser defense, adjusted for the opponent.
9. **Foul control**: blocks per shooting foul and steals per reach-in foul.
10. **Shot-location preferences**: three-point rate, corner share, shot distances, rim and midrange shares.

Close behind: isolation defense, rim contests, on-ball steals, passing-lane interceptions, rebound positioning, floaters, post-up finishing, dribbling/holding habits, help frequency.

## Biggest gaps

- **Physical tools.** BBI has no wingspan, reach, vertical, strength, balance, first step, lateral quickness, conditioning or recovery. Average in-game speed is only a weak nudge. These still need combine, scouting or priors.
- **Skills with nothing in BBI:** release speed, dunk finishing, catching, post sealing, box-outs, closeouts and defensive communication.
- **Partial shooting:** BBI doesn't split out catch-and-shoot midrange or movement shooting. The note in the map shows how to compute a non-pull-up midrange percentage by subtraction.
- **Passing types.** Only drive-and-kick passing has a real family-specific signal; connector, skip and outlet passes have one small hint each. Post entries, pocket passes, lobs, short-roll passes and post passing rely on shared, general passing quality. They stay separate ratings, but their uncertainty should stay wide.
- **Tendency splits.** There is no post-up frequency, no reset choice, no roll/pop/slip split, no box-out frequency and no jump/stay-down split. Observed usage and off-screen sets are partly the coach's choice.

## Notes for the coordinator

- The estimator's current list uses three names that aren't in the catalog: `Stable C&S 3PT_pct` and `Stable Pull Up 3PT_pct` (the catalog spells these with `%`), and `Post Up Draw Foul Rate` (not in the catalog). Worth checking when wiring up the new map.
- Before the estimator uses any "per 75" count for a skill, divide it by the right exposure (touches, drives, attempts or contests). The map says this wherever it applies.
- Treat a metric listed under several inputs as one shared piece of evidence, not several independent ones.
- Check each capture's direction: confirm whether a stored value is raw or a percentile already ordered so that higher is better.

## Resume state

Done, awaiting coordinator review. Validation: the JSON loads; all 94 input IDs are present; every metric name matches the catalog exactly; no BBI definition text is copied; every catalog metric is accounted for exactly once across mapped, context-only and excluded. Build script (scratch, not tracked): `/private/tmp/claude-501/-Users-noahtyler-Documents-BBall-data-BBall-Starting-Point/55a5846d-ea5b-4e0f-b3af-6980522be6bf/scratchpad/build_map.py`.
