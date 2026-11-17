# Draft pick protections and swap offers

New careers are missing 85 reviewed draft-pick terms. The game creates 10 simpler protections from pick descriptions, leaving the reviewed swaps and several protections out.
The two trade tests pass again. One now gives the AI a useful swap to offer, and the other recognizes the game's specific rejection reasons.
The pick import fix is pending. The loader lives in `save.py`, and the user kept the original file limits.

## New-career pick terms

The command line and browser both call `create_league_save`. It calls `load_pick_obligation_overrides` in `save.py`, which reads `data/overrides/pick_obligations_overrides.json`. Its list stops at the October 23 forward tuning release. The newer November 10 roster version fails that check, even though the October 13 archive and every later registered baseline through November 10 have the same 420 underlying picks as the current build.

A disposable seed-7 Cleveland save loaded 10 generated first-round protections and zero reviewed terms. The game missed all 68 reviewed swap terms and seven second-round protections. For example, the reviewed terms let Atlanta keep its 2027 second-round pick if it lands from 31st through 55th, with Dallas receiving Atlanta's 2033 second-rounder instead. The new save lacked that enforceable protection.

With an in-memory override of the version check, the same new-career path loaded all 17 reviewed protections and 68 swap terms, locked all 17 fallback picks, and rejected zero terms. The repair needs to recognize the current starting version for this reviewed pick snapshot while keeping the rejection of unrelated snapshots. The original regression stays quarantined under the file limits.

## Trade tests

- The offer generator skips a swap if the receiving team's pick is worth more than the offered pick by over eight points. That guard dates to `841ddf8`. Every shared Cleveland and New Orleans first-round pair hit it, with gaps of about 17 to 33 points in the original fixture. The test sets comparable 2028 projections and preserves its checks for a generated swap, its direction, valid terms, and a swap asset in the proposal. Commit `5e40fef` replaced the generic headline wording with the allocation. The test now checks that New Orleans gets the more favourable pick.
- With the default projections in a disposable seed-7 career, the engine generated a legal Atlanta offer for Charlotte's Dennis Schröder that included a 2032 first-round swap. Charlotte accepted in the preview and Atlanta rejected. The offer was never applied.
- The Washington and Sacramento proposal was legal. Washington returned `reject_premium_return` because it wanted a comparable contributor or a credible young centerpiece. Sacramento returned `reject`. Commit `5e40fef` introduced the specific rejection decisions. The test allows those decisions and retains the two-team context, acceptance score, value breakdown, and illegal salary checks.

BUG-A changed tests only, so its changes have no effect on seeded gameplay. Restoring the pick terms in the diagnostic save changed the obligations and collateral locks. Trades and draft ownership can differ under those restored terms without any change to random draws.

## Checks

- The focused run had two passes and one skip. Running the protection test directly in a separate process confirmed the original assertion still fails with 85 archived terms versus zero for the current version.
- `bash scripts/run_core_tests.sh` passed with 329 tests and three skips.
- The combined foundation and imported rookie ratings run finished with 224 tests, 30 skips, two failures, and one error during concurrent edits. The failures were in deterministic rebuild and roster measurements. The extension social test raised `StopIteration`. All three passed on a focused rerun against the updated checkout, along with both restored BUG-A tests. The full combined run was not repeated.
- Logs are in `output/bug-a/`. The combined run is `modules-before.log` and the follow-up is `settled-foundation.log`.

Handed back for review with no commit.
