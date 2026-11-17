# Plus-Minus Tracking, October 28, 2026

## Cause

The simulated player lines did not include `plus_minus`. The box-score renderer used `row.plus_minus || 0`, displaying every missing value as a genuine +0. This was not a rounding error or a stat being dropped by storage.

The existing engine resolves aggregate scores, minutes and box-score counts, not a possession-by-possession substitution log. The user approved adding a lineup/scoring model rather than only hiding the missing data.

## Implementation

`plus_minus.py` constructs a deterministic conditional timeline from finalized minutes and made baskets/free throws. Each stint contains exactly five distinct players per team. Integer hundredth-minute allocations preserve the supplied minutes to their tracking precision, with only rounding adjustments in the tracking copy. Opening/closing units use the highest-minute players; the middle of each quarter uses non-overlapping five-lane interval scheduling. This is a modeled substitution pattern, not a record of tactical substitutions from a possession engine.

Made twos, threes and free throws are placed only in intervals where their scorer is playing. Opposing lineup defense conditions the relative placement weights; it does not alter any score or scoring count. Each scoring event credits all five teammates and debits all five opponents. Player rows record `plus_minus`, `on_court_points_for` and `on_court_points_against`.

Overtime captures separate cumulative scoring/minute snapshots in the existing overtime resolver. Regulation remains tied when overtime occurs, and every additional period uses its own added minutes and points. The compact saved trace contains stable player IDs, lineup indices, clock intervals and scores per stint. Detailed event logs are available to tests without bloating ordinary saves.

The tracking layer uses an independent game-seeded random stream. It is not fed back into winners, shooting, minutes, fouls, fatigue, injuries, development or AI decisions. All preexisting player/team fields remain unchanged in paired verification. The new field on `SimGameResult` is optional, so no save migration or old-game rewrite is required.

The box-score action retains the stored trace and player stats. Older games show an em dash, not fabricated zeros, and real measured/model-generated zero still displays +0. A hover title identifies the five-player scoring-stint model. DNP rows remain DNP. Unsupported/incomplete boxes stay unavailable instead of inventing lineups.

## Verification

- 52 focused Python tests pass across plus-minus, existing scoring/accounting, variation, simulation consistency and market audit helpers. Dedicated tests check scoring-player presence, five-player lineups, minute coverage, both scoring signs, DNP, true five-player full-game boxes, repeated calls, input-order independence, global-RNG isolation, rounding, invalid boxes, single/double overtime, preserved original stats, and save/reload/box-score output.
- Each team's player plus-minuses sum to exactly five times its final point differential. Reconstructed stint scoring also matches team and individual points. Forced full-simulation overtime preserves its original result and has a 100-100 regulation timeline.
- 90 real scheduled game/seed combinations all tracked successfully, including three natural overtime games. No unavailable boxes or total mismatches were found. The paired real-game test covers 32 cases across sandbox and real-minutes modes, with every preexisting player/team stat preserved and repeated output identical.
- Real app-action daily-versus-bulk advancement from November 14 to November 16 produces identical full compared business state, including 13 games and their new tracking fields. No wall-clock timestamps, revisions or storage paths are treated as basketball differences.
- The two new JavaScript display tests pass. Of 22 broader UI tests, 17 pass and five fail. The same five failures reproduce with the old plus-minus renderer restored in memory: signal/opponent animation markup, month-boundary calendar markup, and three postseason/header/version assertions. They were not changed or claimed fixed by this task.
- A local 200-box microbenchmark measured approximately 2.04 ms per tracking call, including copying the input rows. The example trace is 6,161 compact JSON bytes; the 90-game sample's maximum was 7,501 bytes. These are bounded local measurements, not a multi-season performance claim.

Evidence is under `output/plus-minus-2026-10-28/`: `sample.json`, `audit.json`, `old-renderer-ui-tests.json`, and the parity reports. Source implementation is `src/nba_gm_data/plus_minus.py`, with small hooks in `sim.py`, `schema.py`, `save.py` and the box-score renderer.

The delivered-code parity run is `parity/verified/report.json`: 13 games, identical full compared state, daily 21.057 seconds and bulk 17.504 seconds. Port 8776 was restarted under the user's existing authorization, and its served JavaScript was checked for the new tracked/missing-value rendering. Existing game results were not backfilled or rewritten.

## Limits

This is conditional plus-minus from reconstructed lineups and scoring, not a new full possession engine. It cannot explain an actual tactical substitution sequence, attribute historical unrecorded plus-minus, or model in-game coaching reactions to those reconstructed stints. It does not add season/career plus-minus summaries. Legacy games intentionally remain unavailable. No playable career was advanced to generate test evidence.
