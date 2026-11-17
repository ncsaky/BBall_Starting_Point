# Box-Score Accounting Repair

## Implemented

`src/nba_gm_data/box_score.py` reconciles the two finalized teams after overtime
in `sim_game_with_context`, before the independent personal-foul draw. It uses
no RNG and does not alter points, shooting counts, minutes, scores or winners.

- A team's assists cannot exceed its made field goals. A player's assists
  cannot exceed the baskets made by his teammates, excluding his own makes.
- Steals cannot exceed opponent turnovers; blocks cannot exceed opponent missed
  field goals. Not every turnover is a steal and not every miss is a block.
- Both teams compete for the same shooting team's misses. Own offensive rebounds
  plus opponent defensive rebounds cannot exceed missed FGA plus missed FTA.
- Offensive and defensive rebound totals add to team rebounds; player rebound
  totals add to team rebounds. All existing count totals still add up.
- Rim attempts cannot exceed a player's two-point attempts.
- DNP players receive no secondary events.

The deterministic largest-remainder reduction preserves existing counts whenever
consistent and only removes impossible events. It never adds baskets to justify
assists, adds misses to manufacture rebounds, or changes turnovers to justify
steals. Player identities break rounding ties, rather than input iteration order.
Applying the repair again makes no further change.

This is a universal accounting correction for newly simulated games, including
legacy careers. It is not a baseline migration or historical rewrite. Existing
stored box scores and season totals can still contain previously generated
errors; the repair does not silently rewrite a playable career's past.

## Verification

`scripts/verify_box_score_reconciliation.py` inspected copies of four completed
first seasons, 4,920 regular-season games total, without simulating additional
seasons or modifying any source save/history file.

| Model/seed | Assist-total violations before | Rebound-pool violations before | Rim-attempt violations before | All expanded checks after |
| --- | ---: | ---: | ---: | --- |
| V8 / 29 | 2 | 1 | 2,615 | Pass |
| V8 / 913 | 0 | 0 | 2,725 | Pass |
| V9 / 29 | 7 | 586 | 4,747 | Pass |
| V9 / 913 | 8 | 620 | 4,548 | Pass |

Rebound-pool counts are shooting-team pool violations, not necessarily distinct
games; rim-attempt counts are player lines. The fixed 15 V9 assist violations
were actual team-games. The test verifies unchanged per-player shooting,
minutes, points and personal fouls as well as idempotence and unchanged source
JSON/SQLite hashes. Existing arithmetic/scoring/minute checks also pass afterward.

V9 mean rebounds fell by 1.08 and 1.14 per team-game solely from removing
impossible rebound credits. Mean assists changed by less than 0.01 per
team-game. Mean steals and blocks did not change in these saved seasons, but
synthetic tests exercise their invalid-count cases.

Evidence: `output/box-score-reconciliation-2026-10-27/saved-evidence.json`.

Real app-action replays, seeds 17 and 29, October 28 to November 1:

- Four daily advances, one bulk advance and next-event advances reach the same
  date with identical meaningful saved state after normal save/reload paths.
- Each seed includes 28 games per path. Both persisted bulk results were checked
  against the expanded accounting validator, with no errors.
- No trade transactions occurred in this short window; this is not a renewed
  trade-deadline, free-agency or full-season consistency certification.

Evidence:
`output/box-score-reconciliation-2026-10-27/short-replay-absolute/report.json`.
The first attempted replay used a relative output path that the older harness
resolved twice. It failed before advancing. The successful rerun used an
absolute path; that harness issue was not disguised as a game failure or fixed
through an unrelated refactor.

44 focused tests passed: reconciliation, live sim integration, original
accounting, V9 offensive roles, read-only review and advancement consistency.
The live integration checks ten seeded games with/without reconciliation,
preserving scores, shooting, minutes and fouls and repeating exactly.
This is not a full-suite claim.

## Limits And Next Work

This fixes conservation constraints, **not the already diagnosed compressed
secondary-stat distributions**. Widening those distributions requires a separate
opportunity-aware generation change and mean/variance calibration. It should
reuse the reconciliation checks rather than bypassing them.

Aggregate FT counts do not identify which misses were final attempts, live
and-one attempts or dead-ball attempts. Missed FGA plus missed FTA is therefore
a conservative upper bound, not an exact rebound-event ledger. The repair does
not force every miss into player rebounds or claim exact possession-level
accounting, foul causality, lineup timing or foul-out timing. Such precision
requires generating the associated events together.

Primary definition reference: [NBA statistics glossary](https://www.nba.com/stats/help/glossary).
The essential implementation principle is that credited events require their
underlying opportunities; season-average plausibility alone is insufficient.
