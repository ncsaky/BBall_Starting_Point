# Bounded V9 Season Audit

Approved scope: two disposable V9 careers, seeds 29 and 913, one completed
2026-27 season each plus its offseason. Both stop at **October 1, 2027**.
This is not another ten-season batch. No UI work, live ratings tuning,
minute-penalty change, prospect-development change or playable-save migration
is included.

## Setup And Safety

`scripts/overnight_offense_audit.py` freezes the model and data under:

`/Users/noahtyler/.cache/nba-gm-audits/offense-season-v9-2026-10-27`

All simulation mutations use real app actions and saves in that frozen runtime.
The worker and supervisor refuse access to the original workspace. The existing
URI-aware read guard handles SQLite file URLs correctly. Later edits to the
development checkout cannot change the experiment's rules or analysis.

Existing completed V8 candidate careers supply the first-season comparison;
no V8 seasons are rerun. Starting players, numeric traits, contracts, medicals,
picks and prospect classes are identical. Prospect/development code and the
hands-off GSW decision policy are checked against the reference runtime. These
are historical comparisons, not a claim that new matched controls were run.
Both simulation seeds share the initial stored draft universe.

The user policy matches the V8 experiment: no discretionary trades, bids or
extensions; automatic draft; existing explicit deadline/postseason confirmations;
staff retention when affordable, fallback otherwise; legal low-role cutdowns.
Required game decisions are handled by that existing policy, not bypassed.

The pilot creates the actual two careers and advances seed 29 through the
opening regular-season window. It verifies persisted scoring and shooting
identities, team minutes and V9 activation. The overnight run resumes those
same checkpoints rather than restarting or rerolling them.

Each month/phase action commits a checkpoint and observation. At most two
workers run at once, with a fresh process per action to bound memory buildup.
Failed or interrupted actions retain their pending marker and are not blindly
retried. The supervisor enforces:

- One completed season per seed, ending October 1, 2027.
- Four-hour batch time limit; 45-minute individual-action limit.
- 8 GiB free-disk floor, 6 GiB worker-memory ceiling and 2.5 GiB audit-directory
  budget. Critical resource limits terminate only these disposable workers.
- Normal stops allow the current action a bounded checkpoint grace period.
- Mac idle sleep prevention only while the supervisor is running; closing the
  laptop lid or shutting down can still interrupt local computation.

The chat does not have to remain active. A completed batch automatically writes
`review.md` and `review.json` alongside `status.json`. No background script
changes the game's tuning or source files. Findings and any narrowly justified
fixes can be reviewed when the user returns.

## Progress

Run this from any Terminal directory:

```sh
"/Users/noahtyler/Documents/BBall_data/BBall_Starting_Point/.venv/bin/python" "/Users/noahtyler/Documents/BBall_data/BBall_Starting_Point/scripts/overnight_offense_audit.py" status
```

It prints each simulation date, completed-season count, checkpoint count and
any failure or safety stop. For a deliberate checkpoint stop, replace `status`
with `stop`. Do not manually replay a pending action after a failure.

## Measurements

The final comparison validates 30 teams playing 82 regular-season games each.
It reports league shooting/scoring totals, free-throw volume, per-player
production, and shared initial role cohorts: post bigs, nonspacing centers,
stretch bigs, guards and other positions. Cohort per-minute rates require 300
minutes; tiny samples stay visible without defining cohort averages.

Roster retention, next-season projected roles and salary commitments are
compared for the same V8 October 1 starting-roster IDs. Monthly censuses and
daily free-agency offer snapshots preserve evidence for investigating AI
decisions. Performance logs include action time, memory and disk use.

Changes in rosters/minutes are outcomes to investigate, not automatic proof
of incorrect AI valuation. This one-season audit does not establish long-run
star replacement, rookie equilibrium, or independent draft-class quality.

Focused harness tests cover endpoint limits, completed-season validation,
weighted statistical rates, tiny-sample treatment and checkpoint reporting.
