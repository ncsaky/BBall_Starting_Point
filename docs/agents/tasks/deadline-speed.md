# Deadline speed (worktree branch, 2026-11-19)

**TL;DR**
- **The trade-deadline run is about 10-20% faster with identical results** (CPU time, paired runs on a heavily loaded machine): old ratings 149-162 → 136-144 s (-9 to -11%), new 94-input ratings 162-181 → 136-146 s (-16 to -19%). Regular months in new-ratings saves got 12-18% faster too; old-ratings months are unchanged.
- **Every checked phase produced an identical save, history database and GUI response** to `cfe41f7` (deadline run, the month before it and the month after it, both rating modes, two rounds).
- **No big exact win is left.** The ~20,000 evaluations are genuine and spread over many small steps. The real lever is evaluating fewer packages, which is the separate trade-search redesign. The facts it needs are in "Where the 20,000 evaluations come from" below.

## What changed, in plain words

Nothing about ratings, the game simulation, the coach model or AI decisions changed. Every change remembers a result that was being recomputed from identical inputs, or finds a record without scanning the whole league.

1. **Rotation guesses for hypothetical trades.** For every trade an AI team seriously considers, the engine forecasts its best 8-10 man rotation after the trade.
   - The "who starts where" step now remembers each player's fit for each starting slot, and its small search runs on plain arrays instead of rebuilding dictionaries. It gives the same lineup, ties included.
   - About half of the post-trade rotations are identical to ones already scored that day. Their team strength is now remembered.
   - The final roster strength reuses the number the rotation was chosen by instead of scoring the same rotation again.
2. **Trade values inside one search.** A player's market value, a team's roster list, a team's published wants and each asset list are now looked up or worked out once per search instead of once per package.
3. **New-ratings saves:** each player's current inputs (base ratings plus this save's development) used to be rebuilt every time anything asked for them, about 130,000 times in the deadline run. They are now kept per player until his development changes. Replaying the season's development on every league rebuild also reuses its routing. The player feature numbers behind trade valuations are kept across the many league rebuilds (one per market day and one per applied trade), keyed by everything they read.
4. **Contract and injury lookups** during roster forecasts use an index instead of scanning every contract and every health row.

## Before / after (paired runs, CPU seconds; wall time in brackets)

The original engine (`cfe41f7`) and this branch ran the same step from the same checkpoint at the same time, one process each. The machine was shared with two other agents (load 20-60), so wall times are roughly double what a quiet machine shows. CPU time is the fairer measure.

| Phase | Old ratings: before → after | New ratings: before → after |
|---|---|---|
| Deadline run (Jan 21 → Feb 5), round 1 | 162 → 144 (272 → 246) | 181 → 146 (405 → 329) |
| Regular month (Nov 20 → Dec 21), round 1 | 36.7 → 35.7 | 56.8 → 47.4 |
| After deadline (Feb 5 → Mar 8), round 1 | 34.3 → 34.0 | 70.5 → 57.7 |
| Deadline run, round 2 | 149 → 136 (221 → 222) | 162 → 136 (307 → 271) |
| Regular month, round 2 | 34.8 → 34.5 | 48.6 → 42.6 |
| After deadline, round 2 | 28.4 → 28.5 | 65.9 → 56.5 |

Round 1 is the first commit alone; round 2 is the final branch (adds the valuation-feature memo). Wall times swing with the other agents' load (both engines of a pair ran side by side, so they shared it).

## Parity evidence

- Harness: `scripts/check_month_parity.py season-run ... --ref cfe41f7` against this checkout, then `compare --season`. It checks the save JSON (only random snapshot ids removed), every history-database row and the GUI response.
- Checkpoints: the GSW / seed 17 season from the season-speed task (steps 1, 3 and 4: the month before the deadline run, the deadline run itself, the month after), both rating modes.
- **Round 1 (first commit): IDENTICAL on all 6.** **Round 2 (final branch, fresh original-engine runs): IDENTICAL on all 6.**
- The saved AI trade-search diagnostics (counts of packages, calls and cache hits written into each day's trade record) are part of the save, so every memo was placed below the counted steps. The counts did not change.
- Extra checks: a diagnostic replay that records every evaluation (wrapping the evaluation function, no behaviour change) also came out identical. With `NBA_GM_RUNTIME_AUDIT=1` (every valuation-feature and contention memo hit is recomputed and compared, and a mismatch stops the run) the new-ratings deadline run finished clean and identical.

## Tests

- New `tests/test_deadline_speed_exact.py` (13 tests): the new starting-slot search against a copy of the old one on 60 random and tied rosters; slot-fit memo keys follow every input; market-value, team-index, normalized-asset, wants, long-injury and contract-index memos match fresh results and ignore other league lists; rotation-strength memo follows player records and league meta; valuation-feature memo follows minutes, ratings and model switches.
- `bash scripts/run_core_tests.sh`: **334 tests OK** (2 skips), on both commits.

## Where the 20,000 evaluations come from (facts for the trade-search redesign)

Measured on the same deadline run (old ratings, GSW seed 17, Jan 21 → Feb 5) by recording every package evaluation.

Line numbers are on this branch.

**When the search runs.** `save.queue_ai_recommendations` (`save.py:5620`) asks `trade_calendar.market_day` (`trade_calendar.py:21`) for the day's trade slots. In this run AI-to-AI searches ran on 7 days: Jan 25 (2 slots, shallow search) and the six days from Jan 30 to Feb 5 (1, 1, 2, 2, 5 and 13 slots; full "deadline depth" when the deadline is 6 days away or less, `save.py:5677`). On days with user-offer slots a second, much smaller search looks only for offers to the user (`save.py:5686`, about 460 evaluations over the whole run).

**How one search spends its evaluations** (`transactions.simulate_ai_trades`, `transactions.py:886`):

| Step | Code | Deadline-depth numbers |
|---|---|---|
| Targets | top 120 trade-block players by block score plus private non-core targets (`:891`, `:902`) | 72-84 targets reach the buyer loop per day; 58-73 of them get at least one package |
| Buyers per target | best 4 fits plus a shuffled tail, up to 12 (`:934`) | ~6.6 buyers per target (450-560 buyer visits a day) |
| Packages per buyer | `buyer_offer_package_options` → `buyer_offer_packages_for_value` (`:3073`) builds up to 12 (`:938`) | ~9.6 packages per buyer, ~46 per target |
| Evaluations | `evaluate_trade_decision` (`:958`) for each package | 2,565-3,703 a day; 19,534 AI-to-AI over the run |
| Stop | first accepted package per target, or 35 approved deals (`:994`) | never reached 35: 25-27 deals kept a day |
| Three-team repairs | 64 attempts a day (`:1001`) | 0 agreements in the whole run |

Per team per day: each team takes part in roughly 200-400 evaluations a day as buyer or seller (most: UTA, DET, NYK, PHI, MIA; least: GSW, DAL, HOU).

**The funnel (whole run, 19,995 evaluations including the small user-offer searches):**

| Outcome | Count | Share | Where decided |
|---|---|---|---|
| Rejected by the seller's quick price check (seller's net value below -9, or breaks a core commitment) | 15,540 | 78% | `evaluate_trade_participants`, `transactions.py:4052` |
| Rejected as "premium player without a comparable return" before pricing | 478 | 2% | `transactions.py:791` |
| Fully evaluated (both sides priced, roster forecasts run) | 3,977 | 20% | `transactions.py:4109` onward |
| ... of which acceptable to both AI teams | 378 | 1.9% | `ai_trade_candidate_accepted`, `transactions.py:1049` |
| Kept as tentative deals (after asset conflicts and the 35 cap) | ~26 a day | | |
| Chosen for the day's slots | 26 over the run | 0.13% | `save.py:5704` |
| Executed after the live re-check | 24 | 0.12% | `process_ai_actions_in_memory` (`save.py:2444`) → `apply_trade_to_state` (`transactions.py:1200`) |

Main reasons a fully evaluated package fails (decisions per side): 2,200 "too much draft capital for the rotation gain" (`trade_roster.py:306` / `transactions.py:4124`), 2,099 "weakens a competing rotation or forces cuts" (`trade_roster.py:300`), 512 plain "net value below threshold". By side: buyer rejects 1,578, seller rejects 998, both reject 1,023.

Package shapes evaluated most: player + player + pick (2,432), two players (2,122), player + pick (1,904), three players + pick (1,644), a single pick (1,641), two picks (1,520).

**What this means for the redesign (facts, not a proposal):**
- On a 1-slot day the search still finds about 26 approved deals and uses one. Most of each day's work is spent after the day's slots could already be filled.
- Four out of five evaluations die at the seller's first price check, which is cheap compared with the full evaluation but still costs a full package build, legality check and pricing. A package generator that knew the seller's asking price would skip most of them.
- The full evaluations (20%) are where the cost is: each one forecasts the buyer's rotation after the trade, and those forecasts are about half of all deadline time.
- Three-team repair attempts (64 a day) produced nothing in this run.

## What is left, and notes

- **Remaining cost (old ratings, profiled):** trade searches ~70% (full evaluations' roster forecasts ~20%, package building ~17%, pick-term previews ~6%, legality/salary checks ~6%), applying and re-checking the day's trades ~13%, daily lifecycle ~7%, games ~3%.
- **Not done, considered exact but low value or risky:** the pick-presentation guard (re-checks every pick owner on each call, ~3%); the salary-matching checks are counted in the saved search diagnostics, so caching them would change the save.
- **Latent issue noted by month-speed still stands:** `trade_wants` match caches are shared between pick-term previews and the base search. Any change to search order can change results through it. The redesign should fix it first.
- **Disk:** about 3 GB free during this task. Harness outputs were deleted after use.

## How to rerun

```
PYTHONPATH=src:scripts .venv/bin/python scripts/check_month_parity.py season-run --model legacy --label base --ref cfe41f7 --steps 1,3,4
PYTHONPATH=src:scripts .venv/bin/python scripts/check_month_parity.py season-run --model legacy --label after --steps 1,3,4
PYTHONPATH=src:scripts .venv/bin/python scripts/check_month_parity.py compare base after --season legacy --steps 1,3,4
```

The checkpoints come from the season-speed task (copied from that worktree into `output/month-speed/season/{legacy,inputs}/seeds/NN/`; `season-prepare` rebuilds them).
