# T2b: restore the mature roster fixture

Build a fresh seed-17 legacy career with normal AI through 2036-11-01. Restore the missing roster forecast test fixture as a compressed file in tests/fixtures. No engine changes or assertion changes; leave all work uncommitted.

Allowed implementation files: scripts/build_mature_fixture.py, tests/fixtures/, and the mature fixture loader in tests/test_roster_forecast_performance.py. This report and the board track coordination.

## Resume state

In progress. Read the current phase driver in scripts/overnight_market_health.py and the extraction fields in scripts/prepare_roster_forecast_fixture.py. Building an action-by-action runner with resumable compressed checkpoints under output/t2b and traceback logging.

Background PID: 98967. Command: `PYTHONPATH=src:scripts .venv/bin/python -u scripts/build_mature_fixture.py`. Log: `output/t2b/build.log`; per-action progress: `output/t2b/progress.jsonl`; resumable export: `output/t2b/checkpoint.nbagm.zip`. First completed action: 2026-10-20 to 2026-11-20 (56.73 s). Re-run the same command to restore the last completed checkpoint after a crash.

First full cycle verified: 2027 lottery reveal and draft entry succeeded; draft added 60 players; re-signing, daily free agency, training camp and rollover reached 2027-10-01. Continuing to the 2036 target. No engine crash so far.

Progress: three complete seasons; 2029-10-01 preseason, 179 drafted players. All three lottery/draft/offseason cycles passed. About 62 minutes elapsed; advances are slower than the initial estimate as the career grows. No engine traceback.

Progress: four complete seasons; 2030-10-01 preseason, 238 drafted players, about 106 minutes elapsed. No engine crash. A brief native process sample during a slow action is retained at output/t2b/slow-action-sample.txt. Caffeinate is tied to builder PID 98967 to prevent idle system sleep.

Resume state update: five complete seasons; latest completed checkpoint 2031-10-01, 297 drafted players. Builder PID 98967 still active. No engine traceback. January 2031 advance took 575.19 seconds, well above the initial monthly estimate; continuing without changing engine code or AI behavior.

## Coordinator note (Claude, 2026-11-17 14:04)
Restarted the builder from its checkpoint (Nov 1 2032, 6 seasons done) on current code so it picks up the SPD speed-up; user approved. New PID 19183 with caffeinate. Seasons 2026-2032 were built with the 9:37 AM code, the rest with HEAD f0eef03. That mix is fine for a test fixture. Note it in the final fixture report.
Restarted again at 2033-07-05 (PID 21446) after the growing-list speed fixes (identical results on a 2032 parity check).
2026-11-17 17:27: crashed at 2034-09-01 because a portable export caps at 512 MB expanded (save JSON 33 MB + history ~490 MB after 8 seasons). Checkpoints are now plain file copies under output/t2b/checkpoint/ (current + previous). Resumed from the last export checkpoint. Seasons from 2034-09 on also include the 2026-11-17 scoring-efficiency engine change. PRODUCT NOTE: after ~8 seasons a player can no longer export a portable save (512 MB cap); history growth (~60 MB/season) needs a decision.
