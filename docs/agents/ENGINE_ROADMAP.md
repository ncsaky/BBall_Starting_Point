# Player model and engine roadmap (revised)

_Revised 2026-11-16 after discussion with the user. Owner: Claude Code (chief operator). Supersedes the first draft from the same day._

## Why we're doing this (user's words, paraphrased)

The **old engine's results were good.** Stats and outcomes looked realistic in testing; contracts and trades needed tuning but were improving. The overhaul exists because the **old ratings didn't distinguish players well**: two very different real players could look nearly identical, and some ratings were vague. The approved 94-input model fixes that by separating four things a user should be able to see and compare:

1. **Raw technique skill**: how good the player is at a thing.
2. **Raw physical tools.**
3. **Tendencies**: what the player chooses to do.
4. **Coach usage and deployment**: how the team uses them.

So the north star is: **players are distinguishable in the ways real NBA analysts would distinguish them, the user can see those layers, and the simulation respects them.** The user's taste follows Nerd Sesh, Basketball Index, and analysts like Taylor Metrics.

## Two-stage plan

### Stage 1: new ratings drive the proven engine (target: about 2 weeks)

Get the user's actual goal into the playable game fast, without betting everything on the new engine first.

- **S1.1 Inputs for every player.** A league-wide estimator gives all 691 players and every prospect all 94 inputs, each labeled with source and uncertainty. It draws on:
  - Local stats: Crafted NBA play-type data, ESPN careers, physicals.
  - The Nerd Sesh transcript research and the hand-researched packets for 32 players.
  - Basketball Index data, if purchased (see below).
- **S1.2 Ratings the user can read.** _(User decision 2026-11-16.)_ **Replace the player card's current bars** with the full new input set, organized by the four layers. Overall and summary ratings are derived from the inputs, with no clipping at 100. The old 15 ratings stay **under the hood only**, as engine features, and are no longer shown to the user.
- **S1.3 The old engine reads the new inputs.** Today the old engine uses 15 traits. Those become derived from the 94 inputs, so the sim reflects the new ratings. Old-engine logic and calibration stay intact.
- **S1.4 AI valuation, contracts and trades** read the new derived ratings. The user explicitly wants this in Stage 1, which in effect gives the front-office AI its own new engine. Contract and trade tuning gets re-checked afterward.
- **Odds data:** the 2025-26 odds (1,096 games) are enough for now. Adding 2026-27 games is optional later.
- **S1.5 Gate:** no regression against the old ratings on both scorecards (below). Then make it the default for new saves.

### Stage 2: possession engine becomes the real engine (weeks 2–5+)

- **S2.1 Whole-game frame:** quarters, clock, five-man lineups, end of game. Codex's parts (drives, help, screens, passing, recovery, interior contests) plug in, with simple stand-ins for missing actions.
- **S2.2 Coach rotation AI.** The user sets **rough minutes** for their team. The modeled coach decides actual playing time game by game and in-game: foul trouble, fatigue, hot or cold hands, blowouts, matchups, injuries. Minutes vary realistically around the user's targets. AI teams' coaches do the same with their own targets.
- **S2.3 Possession decisions** come from player tendencies and coach usage: who initiates, which action, defensive matchups and coverage.
- **S2.4 Speed.** Live decisions use a fast rule fitted to the exact decision model, and the exact model stays as the reference. Must meet the speed budget below.
- **S2.5 Fill in missing mechanics** in the order the scorecards flag: perimeter closeouts, rebounds and putbacks, transition, post-ups, off-ball movement.
- **S2.6 Gate:** beats Stage 1 on both scorecards, meets the speed budget, and survives a five-season soak. Then it becomes the default; the old engine stays selectable for comparison.

## Scorecards (how we judge any engine)

1. **Betting-odds probability test** (already built: `nba-gm-data validate-season-probabilities` / `validate-game-probabilities`; `sim.py` `calibration_metrics`, `player_prop_calibration_metrics`).
   - Simulates each real game many times with who actually played.
   - Scores the engine's win probability, margin and total against the no-vig market odds (Brier score, log loss), plus player points props.
   - Close games aren't punished like confident misses.
   - Data: `data/research/betting_odds_2025_26.json`, 1,096 games.
2. **Real-stat targets** (built 2026-11-16: `data/calibration/nba_2025_26_targets.json`, `scripts/calibration_report.py`). League rates with team-spread bands, plus per-player per-36 lines for 386 players. Comparisons must weight by sample size and account for usage, role and deployment. A low-minute player's odd line counts for little.

Old-engine baseline on scorecard 2: 12 of 18 league metrics are in band. Free throws are far too high (FT rate .429 vs .264), and field-goal attempts too low.

## Speed budget

User target: **simulating one month in the GUI should take about 10–20 seconds** at most, including AI front-office activity. Today's measured baseline is in `docs/agents/BOARD.md`.

## Basketball Index ($5, one month)

Recommended **yes**. Its catalog maps almost one-to-one onto the 94 inputs: shot-making by context, finishing versus rim access, passing creation and quality, screening and rolling, off-ball movement, rebounding chances, rim deterrence, screen navigation, help, and matchup difficulty. Plan: `docs/ratings-evidence-2026-10-29/BBI_ACQUISITION_PLAN_2026_11_11.md`.

- **Timing:** subscribe only once the capture plan and ingestion code are ready, so the month isn't wasted.
- **Who does what:** the user signs up and pays. Claude reads the leaderboards or exports through the user's signed-in browser.
- **Open question:** whether bulk export exists. Confirm on day 1.

## Roles

- **Claude Code** is chief operator: plans, critical-path design and code, reviews, commits (with approval), and keeps the board current.
- **Codex** takes self-contained tasks from `CODEX_QUEUE.md`, one fresh chat per task, used whenever its usage allows so none goes to waste.
- Cheap subagents handle read-only sweeps and mechanical work.
