# GREEN-SUITE: a test failure should always mean something real

Progress: 5/6 - committed; one of the three groups in the full run was killed and needs rerunning

**Short version:** every standing failure was a test problem (missing local-only files, or two screen checks left
behind by approved redesigns). No game bugs found. Tests are fixed and pass when run module by module; the final full
Azure run lost one of its three groups and needs a rerun.

## Before (unchanged code, 21c499b6)
- Fresh worktree copy on Azure: 2,609 tests, 16 failures plus the start-screen video browser test.
- Main-checkout copy on Azure: 11 failures. Nine were only because Azure never receives `output/` (those pass in the
  real main checkout), so main really had 2: the two screen wording checks.

## What changed and why (tests only)
| Failure | Cause | Fix |
|---|---|---|
| Old experimental-engine checks (pilot, response, action choice, interior, settlement, rim anchor) | Saved reference files in `output/` | Skip, naming the file, when absent (`tests/local_fixtures.py`) |
| Two thin-sample rating checks | Basketball Index capture is local only | Same skip |
| Anthony Davis injury-risk ranking | Injury evidence file is local only | That check is its own test with the skip; the other asset-value checks run everywhere |
| Two Windows packaging checks | Start-screen film is local only | Worktrees and copies drop only that requirement and check everything else; the main checkout still requires it |
| Start-screen video browser test | Same film | Byte check split out and skipped outside the main checkout; the rest runs |
| Settings "no appearance options" | Font choice approved (bb56f037), button style (round 6) | Allows exactly those; colours, palettes, other font controls and new look settings still fail it |
| Scouted bar colour | Redesigned to match the slide (362ae622) | Checks one flat fill that follows the scouted share |

## Checks done
- Changed modules with the local files linked in: 162 tests pass (2 older "needs review" skips); browser video test
  11/11.
- Same without the files: pass, 47 skips, each naming its file.
- Injected regressions into the two screen checks: all caught.
- Full Azure run with the changes (`green-after`): two of three groups finished, 1,890 tests (166 modules), 0 failures,
  0 errors, 55 skips; all browser tests passed. The third group (84 modules) was killed (exit -9) with no results.

## Still open
- Rerun the full suite for the missing group. Why it was killed is not verified; another full suite (`lottery-suite`)
  was running on the same machine, so running out of memory is the likely cause.
- Older skips not touched: about 23 "needs review" tests (13 in `test_foundation`), 8 retired experimental modules
  skipped whole, and the macOS packaging module.
- Seen only on the season-archive branch's 01:50 run: `test_overall_scale` trade-want threshold (56.35 vs 56.0).
  Probably its stale unpacked ratings file (not verified); main's 9ec8eaad since fixed the stale-file loading.

## Resume state
Committed on `claude/green-suite-61006b`, not pushed. Based on 21c499b6; main has since added 9ec8eaad (ratings
loader only, not covered by these runs).
