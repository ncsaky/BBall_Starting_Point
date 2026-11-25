# AZURE-WORKER-FIX: switch machines off after failed jobs; stop re-uploading unchanged files

Progress: 5/5 - ready for the coordinator's review

## Short version
- A failed job now switches its machine off, unless another job is using it. Seen working on a real machine.
- A copy from a fresh worktree now sends only files that differ: **554 MB before, 97 MB after** (dry run, one machine).
- **Not proven:** a complete real copy with the new script. My one test job's copy timed out (details below).

## What changed
**Switching off**
- Any failure (start, copy, launch, run, fetch) or interruption (Ctrl-C, being killed, terminal closed) now ends in a
  switch-off. `--keep-on` only applies to jobs that succeed.
- The machine stays on only if another live job has claimed it or is marked as running on it. If it doesn't answer and
  nothing has claimed it, it is switched off. The switch-off is tried three times, then prints a loud warning.
- Markers left by jobs that died when a machine stopped are now ignored. Before, one could keep a machine "busy" and on.
- A failed set-up step on the machine now reports an error. Before, the script waited forever.
- A failed fetch now says so, keeps the job's folder on the machine and returns a failure. Before, it printed
  "fetched" and deleted the folder.
- A running machine that doesn't answer is no longer handed to a new job.

**Copying**
- Files are compared by content (`rsync --checksum`), not timestamp. Files matching the machine's base copy are
  copied from it on the machine itself.
- A copy over a dead connection now gives up after 10 minutes of silence instead of hanging.

## Measurements (Canada 2, 2026-11-25, one test job, 8.8 machine-minutes)
| Dry run from this fresh worktree | Files to send | Size to send |
|---|---|---|
| Old (timestamps) | 4,454 | 554 MB |
| New (contents) | 1,921 | 97 MB |

- The remaining 97 MB really differs from the machine's base copy, which is out of date. Refreshing the base copy on
  each machine would shrink uploads much further.
- The ignore-old-markers rule was checked on the machine: an old marker was ignored, a fresh one was listed.

## The test job that failed
- The real `echo ok` job failed during the copy ("server not responding") after about six minutes. The new cleanup
  switched the machine off, which is the first fix working on a real failure.
- Likely cause: my first version gave up after 90 seconds of silence, while two other jobs from this laptop started
  uploading at the same time (their copies, on the old script, got through). I raised the limit to 10 minutes.
  **That change has not been tried on a real machine**, because the task allowed one test job.
- Suggested check after merging: run one `echo ok` job.
- A partial folder, `~/runs/azfix-echo`, is left on Canada 2's disk. It is harmless and can be deleted next time that
  machine is on.

## Checks
- 10 new tests in `tests/test_azure_worker.py` pass (no Azure needed), including a real local file copy.
- A local end-to-end run (this computer standing in for the machine) passed for a good job and for a failed fetch.
- At the end: Canada 2 (my test machine) off. Canada, West US 2 and Sweden were running another session's jobs
  (`s2lp-totals`, `s2lp-final-2001`, `s2lp-final-1001`); I did not touch them. Nothing of mine is left running.

## Weak spots
- If the laptop loses its network for more than about a minute during cleanup, or the script is force-killed, the
  machine can still stay on. Check `azure_worker.py status`.
- The copy is not retried after a dropped connection. Retrying it two or three times would be a worthwhile follow-up.
- The manual `stop` command (without `--worker`) still ignores claims, so it could stop a machine that is mid-copy.
- Jobs started from the main checkout use the old script until this is merged.
