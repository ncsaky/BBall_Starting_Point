# Month speed, second pass (MONTH-SPEED, branch `worktree-agent-a1a6b4fa00e03fefa`, 2026-11-22)

**TL;DR**
- **A month is now about 15-17% faster, with exactly the same results.** November: about 71-75 s → 60-65 s on a 4-core Azure machine (the laptop is usually a bit quicker). The trade-deadline month: about 235 s → 210 s (11-12%). A whole offseason (re-signing through opening night): about 530 → 473 s with a warm game server, 669 → 614 s cold.
- **Every checked run gave an identical save, history database and screen response** to the starting commit: three month scenarios on two seeds, the twelve offseason steps, with a self-checking "audit" mode switched on as well.
- **The 10-20 s target is not reachable without changing how the AI behaves or rebuilding how the league is kept in memory.** What is left is spread over many genuine pieces of work. The last section lists what it would take.

## What changed, in plain words

Nothing about ratings, the game simulation, the coach or the AI's decisions changed. Every change either remembers an answer the engine was working out again from identical inputs, or skips building something nobody reads.

1. **Player "game cards" are remembered across rebuilt leagues.** Before every game, and inside every AI roster forecast, the engine turns each player's ratings into the numbers the game simulation uses. The game rebuilds its copy of the league at least once a day, and the AI makes hundreds of "what if" copies, and each copy worked all 500 players out again. Now the result is kept and reused when nothing that goes into it has changed. The key holds every input; a player's season box-score totals are left out, because they never reach those numbers.
2. **The same for each player's shot-zone map** (where he shoots from and how well): its fingerprint used to be recomputed on every request.
3. **The coach's automatic minutes plan for each team is remembered** while the team's roster, health, ratings, the GM's minute requests and the head coach are unchanged. It used to be redone for all 30 teams several times a day.
4. **Small things that added up:**
   - The game's shot mix builds only the court-zone numbers it reads, not the display parts (dots and chart) it threw away.
   - The "tonight's opponent is big or small" check reads three strength numbers and no longer builds full shot maps for them.
   - Recording a game's box score no longer re-scans the whole season's game log once per player.
   - Projected draft-pick positions gather each team's facts once instead of once per pick.
   - The AI's trade setup no longer converts every player value and team plan into plain form twice.
   - Free-agency and waiver "would he make our final 15?" checks look up contracts and injuries through an index instead of scanning the league for each player.
   - The automatic backup written before each save no longer deep-copies the whole save just to change one file name.

## Before / after

All times are wall-clock seconds for the GUI's own advance action (`dispatch_app_action("advance_save")` or the offseason actions), on Azure pool machines. Before and after always ran **in the same job on the same machine, one after the other**. "Cold" is a fresh process; "warm" means the league had been built once before the timed click, as it has in the running game server.

**Months** (machine "westus", 4 cores):

| Scenario | Cold before → after | Warm before → after |
|---|---|---|
| November, LAL, seed 7 | 75.4 → 64.5 | 71.4 → 59.6 |
| November, BOS, seed 55 (stops at the rookie-option deadline, then continues) | 83.0 → 71.2 | 79.0 → 65.6 |
| Trade-deadline month, BOS, Jan 10 → Feb 10 (18 AI trades) | 238.7 → 209.8 | 235.1 → 210.3 |

FINAL_MONTHS_PLACEHOLDER

**Offseason**, GSW seed 17, re-signing (Jun 17) through opening night (Nov 1), 12 GUI actions:

| Step | Cold before → after ("sweden") | Warm before → after ("canada") |
|---|---|---|
| Re-signing, first stop | 24.9 → 22.2 | 18.4 → 15.1 |
| Draft (sim all) | 83.7 → 73.6 | 75.1 → 64.4 |
| After the draft | 20.8 → 19.5 | 9.5 → 8.2 |
| Re-signing, second stop | 38.9 → 35.2 | 26.3 → 23.1 |
| Free agency, 5 days | 240.3 → 221.3 | 178.6 → 158.5 |
| Free agency to Sep 1 | 78.1 → 72.1 | 65.3 → 59.5 |
| Training camp | 68.8 → 64.8 | 56.8 → 52.2 |
| Preseason to Nov 1 | 113.8 → 105.8 | 99.7 → 91.8 |
| **Total** | **669 → 614** | **530 → 473** |

(The cold column is commit `1ea931c`; FINAL_OFFSEASON_PLACEHOLDER)

Starting point for comparison, same scenarios before any change (`27aa06b`, unprofiled): November 74-75 s on both "canada2" (2 cores) and "westus" (4 cores), the deadline month 232-244 s, the offseason 665 s on "canada". A single process uses one core, so the 2-core machine was not slower for one job.

## Where the time goes now (cProfile, warm, after the changes)

Profiled runs take about twice as long; the shares are what matter.

**November (about 60 s):**
- **Game simulation, about 27%.** 222 games at roughly 70 ms each. The biggest single part is building each team's shot-zone maps for tonight's minutes.
- **The daily front-office routine, about 25%:** refreshing team plans (which rebuilds the AI's whole-league valuation of every player and team, 9 times a month), the daily minutes refresh and the injury model.
- **AI trade searches, about 12%** (two market days with trade slots).
- Smaller: the dashboard refresh after the click (6%), contract extensions (5%), applying trades (3%), in-season free-agent signings (3%).

**Trade-deadline month (about 210 s):**
- **AI trade searches, about 51%.** Of that, roughly half is the search for **offers to the user's team**: on every day with offer slots it builds up to 12 packages for each of about 120 listed players and evaluates about 6,500 of them over the month. The AI-to-AI search (starting from each team's targets) is about a third, and setting up the market review (whole-league values and shot maps) the rest.
- **Daily routine, about 15%;** **applying the 18 AI trades, about 10%** (each one rebuilds the league and the AI's valuations to re-check it live); **games, about 8%.**

**Offseason (about 470 s warm):**
- **Rebuilding the league from the save, about 35%** (219 rebuilds cold): the draft class, installing the 94-input ratings (including estimating inputs for drafted rookies), replaying development, minutes, copies.
- **The AI's whole-league valuations, about 16%;** free-agent offer processing about 10%; draft-night AI trade checks about 10%; save writes about 4%.

## Identity checks

- Harness: `scripts/check_month_parity.py` (from the first month-speed pass). New scenarios `nov-inputs-b` (Boston, seed 55, 94-input ratings, two clicks because of the rookie-option stop) and `deadline-inputs` (Boston, Jan 10 → Feb 10 with the deadline stop). `nov-inputs` is the Lakers, seed 7. The baseline engine is `27aa06b`, run from a frozen copy because the workers have no git history. `MONTH_SPEED_WARM=1` builds the league once, untimed and unsaved, before the timed click.
- Compared: the save JSON (only the random snapshot ids removed), every history-database row, and the GUI response (absolute paths and the dashboard file-time removed).
- **Results, all IDENTICAL:**
  - Feature memo alone (`1de3aea`): 3/3 months, and 3/3 with `NBA_GM_RUNTIME_AUDIT=1` (every memo hit is recomputed and compared; a difference stops the run).
  - Through `83682ae`: 12/12 offseason steps, and 12/12 with the audit on.
  - Through `1ea931c`: 3/3 months cold, 3/3 with the audit, 3/3 warm; 12/12 offseason steps cold and 12/12 warm.
  - FINAL_IDENTITY_PLACEHOLDER
- Tests: `bash scripts/run_core_tests.sh` 338 OK (2 skips) at `1ea931c`; focused modules (speed exactness tests from all three passes, contract protection, save recovery, simulation consistency, free-agency bids, waivers) 140 OK. New `tests/test_month_speed_2_exact.py` (10 tests): memo hits equal fresh results and every input change is a miss; zone-only shot maps match the full ones; strength features equal with and without zone maps; pick slots match the old per-pick code; remembered rotations match fresh ones (including the fill-in minutes); shared game-log ids match a fresh scan.

## Commits (oldest first; all exact)

| Commit | What |
|---|---|
| `605e714` | Checkpoint file, scenarios, frozen-baseline support in the harness |
| `1de3aea` | Player feature vectors remembered across league views (audit mode) |
| `81086af` | Shot diet builds only zone grids; game-log ids once per game; tests |
| `83682ae` | Spatial signature memo; signing-check index; backup copy; warm option |
| `8489209` | Opponent lean strength-only; pick-slot team facts once; plain lists once |
| `83b1c6c` | Valuation feature memo keyed on trait values, without box totals |
| `c4e7f23` | Coach's automatic rotation projection remembered (audit mode) |
| `1ea931c` | Rotation refresh gathers each team's players once |
| `0e79694` | Feature memo key leaves out box totals for zone grids too |

## What it would take to reach 10-20 s

Honest answer: the remaining time is genuine work spread across the whole day loop, and no exact trick of the kind above is left that is worth more than a few percent. Three things would be needed, roughly in order of payoff:

1. **Keep one live league in memory instead of rebuilding it from the save.** Today the engine rebuilds the full league (ratings from the 94 inputs, development, minutes, contracts) dozens of times a month and 200+ times an offseason, then rebuilds the AI's whole-league valuations on top. Updating only what changed (one trade: two rosters) would remove most of the deadline month's non-search time and about a third of the offseason. It is a big change to `save.py` and the transaction context; parity would have to be proven the same way as here. Exact, but a multi-day project.
2. **Narrow the "offers to the user" trade search.** It is about a quarter of the deadline month and runs the old listed-player search at full depth on every offer day. Making it target-driven like the AI-to-AI search, or evaluating fewer packages per listed player, would cut 40-60 s from the deadline month. **This changes which offers the user receives** (behavior-changing), so it needs the user's approval and its own league-health check.
3. **Game simulation (about 15 s of an ordinary month on this machine).** Most of it is rebuilding each team's shot-zone map for tonight's minutes. The zone maps' fingerprints include the players' season box-score totals, so they change after every game even though the zone values do not. Removing those totals from the fingerprint is exact for the numbers the game uses, but the fingerprint text is copied into team maps that the GUI shows, so it needs a check that nothing visible changes.

Even with all three, an ordinary month is likely to land around 25-35 s on this hardware and the deadline month around 60-90 s. Getting to 10-20 s on a 2021 MacBook would also need fewer AI evaluations overall (a behavior change) or the Stage 2 engine's speed.

## Notes for the coordinator

- **Files other agents hold that dominate the offseason** (not edited, described here):
  - `ratings_model.install_inputs_model` runs on every league rebuild and hashes the whole league's traits as JSON each time (about 75 ms) and re-derives every player's traits. Remembering the fitted adapter by the traits list's identity, or hashing once per save load, would save about 5% of an offseason. `apply_development` (development replay on each rebuild) is about 16% of offseason rebuild time.
  - The input estimator for drafted rookies runs once per generated player per process (about 60 s of the cold offseason profile; cached afterwards). In the running server this is paid once.
  - `offseason_decisions.user_pending_options` builds a whole league just to list the user's rookie options; called from the GUI's advance action when the deadline falls inside the click.
- **A cache that is not exact today (unchanged here):** `spatial.league_playmaking_mean` keys its cache on `id(traits)`, the player count and the date. Python reuses ids after objects are freed, so a stale value can be returned for a different league copy. It has been like this since before this pass; my memos call it in the same order as before, so they do not change what it returns. Worth fixing as a deliberate (possibly behavior-changing) change.
- **The Azure script's pool has a bug:** `start()` reads `monthly_hour_cap` from the worker entry, which only the top-level config has, so a stopped pool machine (other than the first) cannot be started (`KeyError`). I used a patched copy outside the repo. Fix: `worker.setdefault("monthly_hour_cap", cfg["monthly_hour_cap"])` in `pool()`.
- Uploading to the workers is slow (about 10-20 minutes when 300 MB of offseason checkpoints sit in the worktree). Keep checkpoints out of the worktree for jobs that do not need them.
- Untracked helpers in the worktree (not committed): `speedbase/` (frozen baseline source, job scripts, seeds, profile tools). Large outputs and profiles: `output/month-speed/fetch*` (git-ignored).

## Resume state

- Done; awaiting coordinator review. Branch `worktree-agent-a1a6b4fa00e03fefa`, not pushed.
- IN PROGRESS (remove when final): final validation of `c5aee23` running on Azure: `speed-b4` (months cold pair +
  audit), `speed-b4w` (months warm pair + profile), `speed-off4` (offseason warm pair + audit); `speed-off3`
  (offseason cold, `0e79694`). Logs `output/azure-speed-*.out`. Fill the FINAL_* placeholders from them, set the
  board row to review, commit.
