# Draft Spending for Marginal Upgrades, October 28, 2026

## Reproduced Cause

A disposable replay of January 31 through February 3, seed 17, reproduced both reported deals before edits. The market permitted an AI to override its own rejected price by up to nine value points, bounded by half its outgoing package value, without requiring a useful purpose for the picks spent.

- Cleveland sent Riley Minix and a top-ten-protected 2028 first, with a later first fallback, for Jevon Carter. Carter projected to 19 healthy rotation minutes and improved strength by 0.1354. Cleveland's own price evaluation was -5.072, but the override approved it.
- New York sent Drew Eubanks and a second for Trey Lyles. Lyles received zero minutes in its best healthy rotation; strength improved only 0.0045. New York's -7.658 evaluation was also overridden.

Neither buyer had a relevant injured rotation player. The preserved contexts are `before17/context-4ba2a886250b0e17.json.gz` and `before17/context-950b0bdb0e646f7d.json.gz` under `output/pick-investment-2026-10-28/`. The source save was not edited.

An intermediate run also found that limiting only negative-price overrides was insufficient: Cleveland substituted a different first-round package for Kyle Anderson that had a slightly positive price score but weakened its healthy rotation. The final check therefore applies to excessive non-starter draft spending even when both raw price scores are positive.

## Fix

The existing shared final-roster assessment now includes a draft-investment check:

1. Price net draft rights spent, offsetting rights received. Use actual conditional-pick and signed swap values, not a count of firsts or seconds. A later protection fallback is not an additional simultaneously traded pick.
2. Allow a smaller value-loss tolerance when the buyer spends draft assets for little measurable benefit. Useful current upgrades, retained young upside, substantial net salary relief and demonstrated injury cover increase that tolerance, never beyond the existing nine-point ceiling. The existing relative-loss and combined-value bounds still apply.
3. For incoming players outside the projected 24-minute starting rotation, or acquisitions improving healthy strength by less than 0.25, also bound capital spent by healthy rotation improvement, positional backup improvement, retained young upside, injury cover and net salary relief. A positive asset-price sum alone cannot bypass this check, nor can a nominal starting role that leaves the team weaker.
4. Count the strongest positional backup improvement, not five separate credits for one versatile player. Measure actual injury-cover improvement using rotations without relevant injured players; do not treat any injury as blanket permission to overpay. Short absences and unknown return dates receive no special cover credit.
5. Recheck the AI objection when applying a saved bilateral offer. Current protected terms are compiled before checking; explicit human roster preferences are not replaced by an AI preference. Multi-team settlement retains its fresh all-party evaluations.

These are bounded game policies, not empirically calibrated NBA price formulas. The value-loss allowance is 1.5 plus six times positive healthy strength change, 0.2 times net young-upside gain, six times duration-weighted injury-cover gain, and 0.25 per million of substantial net salary relief, capped at nine. The marginal-acquisition capital allowance is eight plus 30 times strength gain, 0.6 times the strongest backup-quality gain, 1.5 times young-upside gain, 30 times cover gain and two per million of substantial net salary relief. Newly owed waiver money reduces salary relief. The policy preserves meaningful starting upgrades, rebuilding, salary-exit and human-decision paths rather than banning picks-for-veterans.

The exact Carter package now spends 30.69 draft-value points against a non-starter allowance of 17.792; Lyles spends 14.24 against 8.135. Both receive `reject_pick_investment`, which cannot be bypassed by the generic override or a saved approval flag. Hartenstein's 36-minute starting role and Chicago's 1.4848 strength gain keep the Sabonis/OKC/Chicago facilitator package approved.

## Reproducibility Repair

The old bilateral replay rebuilt a proposal ID, which changed deterministic personality noise. Wrapping a proposal with protected-pick terms also changes its public transaction ID. Frozen comparisons now hold each recorded personality adjustment fixed and preserve proposal identity, proving that the demonstrated rejection changes are not a favorable reroll. All historical team net scores and personality adjustments in those exact replays remain identical; only the investment decision changes.

New bilateral candidates persist both the evaluation seed and original evaluation proposal ID through conditional wrapping, serialization and live checking. Old candidates lacking those fields cannot recover an unrecorded seed perfectly; frozen audit comparisons use their recorded personality values instead. Current inbox reviews are labeled as current-state checks, not historical offer-time reconstructions.

Principal implementation: `src/nba_gm_data/trade_roster.py`, `src/nba_gm_data/transactions.py`. Reproduction: `scripts/audit_trade_quality.py`. Focused regressions: `tests/test_pick_investment.py`.

## Validation

The final focused 185-test Python suite passes in 97.062 seconds. Twelve investment tests cover the original marginal cases, useful upgrades, retained/departing young upside, waiver-adjusted salary relief, draft compensation received, measured injury cover, unoverridable rejection, positive-price loopholes, serialized random identity and live application. Existing synthetic settlement fixtures now supply gameplay skill differences matching their scouting values; previously every gameplay trait defaulted to 50 despite differently priced players. This avoids weakening the production policy to satisfy invalid upgrade assumptions.

Final normal-market runs use `stable17/` and `stable29/`, with ordinary production opportunity counts, January 31 through February 3, and the same ignore-incoming-offers user policy as the original run. Both complete with unchanged source fingerprints:

| Seed | Trades | Delivered offers | Three-team trades | Three-team offers | Seconds |
| --- | --- | --- | --- | --- | --- |
| 17 | 5 | 9 | 1 | 5 | 259.71 |
| 29 | 7 | 10 | 2 | 2 | 244.47 |

Trade and offer totals remain five/nine and seven/ten, as before; the selected packages change. These are short-window results, not annual trade-frequency calibration. Delivered offers include subsequent stale offers, not extra completed transactions.

In seed 17 Cleveland gets Carter for Riley Minix without the protected first. In seed 29 it gets Carter for Tristan Enaruna without a pick. The old Lyles package and first-for-marginal-Anderson substitutions do not occur. Genuine pick spending remains: Chicago buys Hartenstein's 36-minute starting role in a Sabonis facilitator trade; Utah accepts a -3.307 price disagreement to acquire Josh Giddey while improving strength 0.57. Seed 29 also completes the Powell/Philadelphia/Detroit/Chicago facilitator route. This is evidence that search finds alternatives, not proof that every remaining player price is realistic.

The final real app-action daily-versus-bulk comparison in `parity-verified/stable/report.json` matches exactly across the month boundary. Both reach February 3 with five trades, nine offers, 24 games, three cuts, two depth signings and three waiver clearances. Full compared business state includes rosters, contracts, health, development, decisions and durable history; incidental timestamps, save revisions and storage paths are excluded. Daily took 219.081 seconds and bulk 238.246 seconds while other checks were running. These are bounded timings, not a controlled speed benchmark.

Verification uses a small frozen source copy in `verification-engine/`. Earlier `after17/`, `after29/`, `final17/` and `final29/` are intermediate evidence, not final-code proof. A separate chat changed chart/spatial source during those workspace runs. Frozen trade-code hashes match the delivered workspace code; static resource directories are read through links, not duplicated. Failed snapshot setup attempts in `verified17/`, `verified29/` and `parity-verified/verified/` are not completed simulations. No multiseason run, player-rating change or UI redesign is part of this task.

The isolated preview on port 8780 was confirmed idle, restarted and checked for a successful HTTP response. The main preview and playable saves were not interrupted or written by this task. Scoped whitespace checks and compilation pass.

## Remaining Limits

Capital and price-disagreement budgets still need wider economic calibration; the exact thresholds are explicit game policies. The audit retains relative-loss review flags for some player-only trades and the purposeful Giddey acquisition. Those flags are not silently removed or presented as resolved. This pass fixes unsupported draft spending, not all underlying player prices or long-run market balance.

Injury cover considers known absences of at least 14 days and caps duration weighting at 60 days. Backup quality uses the best positional second-option improvement rather than a full future-injury simulator. Unknown return dates and hypothetical future injuries are not automatic exceptions. Existing saved proposals without evaluation-seed metadata retain the legacy limitation described above, but current hard capital objections are checked before settlement.
