# FA-REAL slice 1: the money rules

_Claude (Opus agent), branch `worktree-agent-afd2d3c7a0ddb24ed` (from main at be73218; merges cleanly with main at
af328df). Status: **review** (slice 1). Committed on the branch only; not pushed or merged._

## TL;DR
- **One money calculator now decides every free-agent signing**: whether the team can legally pay, how (Bird rights to
  keep its own player, cap room, the minimum, a mid-level exception, which is a yearly signing budget for teams over
  the salary cap, or the bi-annual), and what it locks in. "Hard-capped" means a ceiling the team can't pass for the
  rest of the season once it uses certain exceptions.
- **The free-agency room shows it all** in plain words, with a cap sheet. Cap holds are placeholders on the cap for
  your unsigned free agents; you can renounce one (give up his rights) after a before/after preview.
- **Same results, real accounting**: on the 2027 offseason replay the same players stay and move, but every signing is
  paid a legal way (13 teams used a mid-level, 11 hard caps triggered), contracts rise year by year, and stars are kept.

## What the calculator does (`src/nba_gm_data/cap_ledger.py`)
- **Exact lines.** 2026-27: cap $164.961M, tax $200.428M, first apron $209.015M, second apron $221.686M, floor
  $148.465M (no more rounding to $0.1M). Later seasons keep the game's 3.5% growth, to the dollar (no better documented
  projection in the repo). `cap_rules.cap_lines_for_season` now also returns `salary_floor`.
- **Payroll breakdown** (`team_payroll`), three views:
  - cap payroll = signed cap charges + dead money + cap holds + unsigned first-round picks + a rookie minimum for each
    empty spot below 12 (July 1 to opening night). Cap room = cap minus this.
  - tax payroll and apron payroll = signed cap charges + dead money (holds don't count).
  - Holds: Full Bird 190% of last salary below the league average / 150% at or above (300% / 250% off a first-round
    rookie deal), Early Bird 130%, Non-Bird 120%; never above his max or below his minimum; a player coming off a
    minimum holds at the minimum. Holds count from June 22 (the game's end of the playoffs) to opening night.
- **Renouncing** (`renounce`, `renounce_preview`): the hold disappears and so do the Bird rights. The user has a
  Renounce button; AI teams renounce holds on players outside their rotation (under 18 projected minutes) when that
  opens at least a full mid-level's worth of room (`ai_renounce_for_room`; 5 renounced in the replay, all Memphis).
- **Exceptions as budgets** with balances, splits and eligibility (2026-27 amounts, grown with the cap after):
  full mid-level $15.044M (4 years), taxpayer mid-level $6.064M (2 years), room mid-level $9.366M (3 years),
  bi-annual $5.477M (2 years, not two seasons in a row), minimum. Using cap room gives up the full/taxpayer mid-level and
  bi-annual and opens the room mid-level. The taxpayer amount shares the mid-level budget.
- **Hard caps by move** (`commit` / `trigger_hard_cap`): full mid-level and bi-annual hard-cap at the first apron,
  taxpayer mid-level at the second; the tightest wins; recorded per team and cap year in
  `save["cap_ledger"]["seasons"][season][team]`. Bird rights can pass both aprons, never a triggered hard cap.
- **Max and min**: true max = 25/30/35% of the cap by service, or 105% of his last salary; minimum scale by service
  (2026-27 table); a veteran's (3+ years) one-year minimum counts at the two-year minimum (salary and cap charge
  differ; stored as `cap_charge` on the contract season). The max is enforced in the signing check.
- **Raises**: a share of year one added each year (8% Bird, 5% others): $30M at 8% is $30.0M / $32.4M / $34.8M (the
  audit's compounding gave $34.992M). Saved year by year (`salary_schedule`, `seasons`); no more flat salaries. Early
  Bird needs at least two years. The user can choose the largest legal raise or none.
- **Trade dates**: each new contract records `trade_eligible_date` (the later of December 15 and three months; January
  15 for a Full/Early Bird raise over 20% that leaves the team over the cap). Separate from the AI's six-month re-trade
  habit.
- **Reserve, commit, release**: an outstanding bid carries its `payment`; while active it holds its room or exception
  money (`reservations`), so the same money can't be promised twice. `commit` records the signing; `release` frees a
  losing bid. Slice 3's offer sheets plug into the same three calls.
- **Who uses it**: `play.signing_cap_check` (now a thin wrapper), AI market bids (`play.ai_bid_payment`: the price by
  the first legal route, else a "full mid-level offer" if that is at least 80% of the price), the day's acceptances
  (re-checked against the books as they are), the user's offers (`manual_save_pool_signing`, the GUI and the text
  room), the AI re-signing pass, rollover strategic signings, roster repair (true one-year minimums instead of a flat
  $2.25M), in-season released-player signings and waiver claims (room, minimum, or since 2024-25 the full/room
  mid-level or bi-annual). `contract_ai.apply_contract_to_save_state` writes the schedule and commits the payment.
  `save.team_cap_summary` reads the ledger (same keys as before plus cap room, holds, aprons, floor, hard cap).

## Scenario results (`tests/test_cap_ledger.py`, 22 tests)
| Scenario | Result |
|---|---|
| $19M hold kept, re-signed for less, freed room used | $145M payroll + $19M Full Bird hold ($10M player) leaves $6.7M room: a $15M outside signing can't use room. Re-sign him for $8M with Bird rights ($8.0M / $8.64M / $9.28M, tradable Dec 15) and $17.7M of room opens; the $15M signing then goes through on cap room. |
| Hard-capped team blocked from a Bird re-signing | A team that used the full mid-level is hard-capped at the first apron; its Bird re-signing for $20M is refused ("hard-capped at the first apron"); one that fits under the ceiling goes through. |
| Taxpayer team, taxpayer mid-level | $218M payroll (over the first apron): $6M for 2 years is paid with the taxpayer mid-level (hard cap at the second apron); the full mid-level, $7M, or 3 years are refused; a minimum still works. |
| Cap room loses the full mid-level | After a $45M room signing the full mid-level and bi-annual are gone; the room mid-level pays $9M; $12M is refused. |
| Early Bird two-year minimum | One year refused ("at least two years"); two years paid with Early Bird rights. |
| 8% schedule | $30.0M, $32.4M, $34.8M (AI re-signing terms too). |
| True max and min by service | $41.24M / $49.49M / $57.74M; 105% of a $50M salary = $52.5M; minimums $1.358M (0 years) to $3.877M (10+). A $45M offer to a 4-year player is refused (max $42.7M). |
| Veteran minimum cap charge | 10-year veteran, one year: pays $3.877M, counts $2.449M; two years: counts in full. |
| Bird past both aprons | $225M team re-signs its Full Bird player for $35M x 5 (no hard cap added). |
| Splitting the mid-level, holding bid money, bi-annual twice, waiver claims, empty-spot charges, AI renounce rule | all pass |
| Screen = save (rule 4) | On a real new career the quote the room shows (route, year-by-year salary, trade date) is exactly the contract the save writes after the offer is signed, and the exception money used matches. |

## One offseason, before and after
The 2027 offseason replayed from the same draft-day save (seed 17, Golden State hands-off; `output/tv2/final2-probe/
snapshots/draft_2027`), main (be73218) against this branch, through rollover to October 1. Scripts in
`output/fa-real-slice1/` (`replay.py`, `metrics.py`, `stars.py`).

| Measure (2027-28) | Main | This branch | Real |
|---|---:|---:|---:|
| Expiring contracts tracked | 152 | 152 | |
| Stayed / moved (return-to-own-team share) | 18 / 39 (32%) | 18 / 38 (32%) | 45-55% |
| Unsigned on opening day (after rollover exits) | 52 | 54 | |
| Market signings / AI re-signings / repair minimums | 30 / 11 / 53 | 32 / 10 / 50 | |
| Signings by how they were paid | not recorded | minimum 54, Bird 15, full mid-level 13, room 6, bi-annual 3, room mid-level 2, taxpayer mid-level 1 (rookies separate) | |
| Teams using a mid-level | n/a (no exceptions) | **13** | 18-23 |
| Teams that used cap room | n/a | 3 | |
| Hard caps triggered | none tracked | 10 at the first apron, 1 at the second | |
| Teams over the tax / first apron / second apron, opening | 11 / 7 / 2 | 11 / 7 / 2 | 7-14 / - / - |
| Teams under the floor, opening | 1 | 0 | |
| Free agents left, opening | 120 | 120 | |

How to read it:
- **The rules changed how deals are paid, not who goes where.** The market was already mostly mid-level-sized for
  over-the-cap teams, so the same players moved; now each deal names its route and its locks.
- **Fewer teams use a mid-level than real (13 vs 18-23), and the return share stays at 32% (real 45-55%).** Both come
  from a thin AI market, not the cap rules: on day one only 16 bids were made league-wide, and the owner's payroll rule
  (`payroll_plan`, "keep room below the tax line for its phase") refuses most of the rest, including incumbents' Bird
  bids for their own regulars (Minnesota and DiVincenzo, Oklahoma City and Cason Wallace). Kyle Kuzma (28 minutes)
  drew no bid in five days and was signed by roster repair at the minimum, on main as well. Next free-agency task.
- **Stars kept (KEEP-STARS holds)**: of the 60 best players by on-court value, three had expiring contracts.
  Brandon Miller (31st) stays in Charlotte at $28.8M x 5 in both runs. Jimmy Butler (29th) belongs to the hands-off
  user team, which never re-signs, and lands in Boston at the minimum in both (now his true veteran minimum, $4.0M, not
  a flat $2.25M). Paul Reed (45th) is out of the league in both. The KEEP-STARS unit tests pass on the new rules
  (Bird re-signings past both aprons; refused above the Bird limit without room or an exception).
- **Speed**: the offseason from the draft's end to October 1 (re-signing, five market days, sim to end, camp and
  rollover) took 157 s on main and 146 s on the final branch (the first branch run took 171 s before the team index was
  cached; the profiler showed the ledger at about 7% of the market's time, mostly rebuilding that index). The laptop
  is shared, so differences of about 10% are noise: not slower. Simulated months are untouched (the calculator only
  runs on signings, claims and the free-agency room).

## Screenshots (`output/fa-real-slice1/screenshots/`)
- `1440-resigning-room.jpg`: the re-signing window. Chips: cap room -$80.5M (Golden State's seven holds, $128.4M),
  under the tax, under the first apron. Builder: Jimmy Butler's range is his minimum to the most a legal route allows,
  how you pay (best legal way or a chosen route), raises (largest legal or none).
- `1440-how-paid-zoom.png`: "How it's paid": full Bird rights, $33.6M / $36.3M / $39.0M / $41.7M, locks in, tradable
  Dec 15; the cap table by season with cap room, tax room and first-apron room.
- `1440-cap-sheet.jpg`: the cap sheet: signed, dead, holds, empty-spot charges, cap payroll, room, tax and aprons, hard
  cap, the four exceptions with budget, balance, years and status, and each hold with its room-after and Renounce.
  Renouncing Georges Niang ($2.5M hold) moved room from -$80.5M to -$77.9M, exactly the preview.
- `1440-market-mid-level-offer.jpg`: open market, $12M x 4 to Javon Small: "paid with the full mid-level exception;
  hard-caps GSW at the first apron ($216.3M) for the rest of 2027-28", schedule $12.0M to $13.8M.
- `1024-builder.jpg`: at 1024 wide the room's windows keep their card-board positions (the board does not reflow at
  this width, as before); the builder's new sections read correctly.

## Trade hook-up note for the coordinator (I did not touch `transactions.py` or `trade_*.py`)
- **Signing trade dates**: `transactions.recently_signed_player_ids` uses a fixed December 1 unlock from the signing
  log. Replace its body with `cap_ledger.trade_blocked_player_ids(save, as_of_date)` (players whose contract's
  `trade_eligible_date` is after today; written for every free-agent signing from now on), or check one player with
  `cap_ledger.newly_signed_trade_block(save, player_id, today)`. Keep the six-month AI re-trade hold separate.
- **Hard caps from trades**: when the trade code learns sign-and-trades and aggregation, call
  `cap_ledger.trigger_hard_cap(save, team_id, season, "first_apron" | "second_apron", "<move in words>")`, and check
  `cap_ledger.hard_cap(save, team_id, season)` before a trade that adds salary. Today trades only test the blanket
  second apron (`cap_lines_for_season(...)["hard_cap"]`).
- **Cap lines**: trade code reads `cap_rules.cap_lines_for_season`, now unrounded (e.g. tax line $200.428M, not
  $200.4M). That nudges AI trade decisions slightly (outcome change; expected).
- **Cap charges**: the trade code's payroll sums contract `salary`; a veteran's one-year minimum now also carries
  `cap_charge` (lower). Use `cap_ledger.cap_charge(row)` for tax and apron math when convenient.

## Tests and checks
- `bash scripts/run_core_tests.sh`: 338 OK (2 skipped), on the final code.
- New `tests/test_cap_ledger.py` (22 tests, scenarios above) and 31 related modules (keep_stars, fitted salary,
  free-agency bids, extension builder, trade_volume and trade_volume_2, foundation, room payload, waivers, contract
  protection, roster space and retention, multiplayer, soak runner, lifecycle and more): 580 tests; the 3 failures
  (exact lines, a Bird re-signing test, an AI waiver claim) were fixed as below and those modules rerun green.
- Tests changed because the rules changed (each says so in a comment): the exact lines (no rounding); AI bids are
  checked through `ai_bid_payment` (the old ones mocked `signing_cap_check`); the price-floor tests take legality as
  given (legality has its own tests); a 2-year offer below a player's minimum is now paid at his minimum schedule;
  Bird re-signings may pass the aprons (two KEEP-STARS / TRADE-VOLUME tests now build a real payroll instead of mocking
  `team_cap_summary`); the browser's cap verdict test now checks it mirrors the engine's quote; a test stub takes the
  new `payment` keyword.
- One behaviour kept on purpose: AI waiver claims still need room or a minimum contract (the rules also allow the full
  or room mid-level or bi-annual since 2024-25, which the user can use; letting the AI do it changed claim outcomes in
  `test_foundation`).
- `node` tests: all pass except `startup_video.test.cjs`, which needs the git-ignored movie file (as on main).
- Real-stat scorecard (`calibration_report.py --games 1230 --mode replay-real-minutes`): **18/18** league metrics in
  band. Game simulation is untouched; the betting-odds check was not rerun (no game-sim change).
- Determinism: same seeds give the same results (run1 and run2 identical). RNG streams are unchanged; outcomes change
  where the rules now refuse or reroute a deal, and the trade AI sees unrounded lines.
- GUI checked in a running app at 1440 and 1024 wide (screenshots above): quote, cap table, cap sheet and Renounce
  work; no console errors seen.

## What's left (slice 2 and later)
- Calendar and options (slice 2): holds and the rights window still follow today's phase dates (June 27 re-signing,
  July 1 market); qualifying offers and restricted free agency are not modelled (young starters are still kept by the
  KEEP-STARS shortcut); options are not decided.
- Thin AI market: few bids per day and the owner payroll rule blocking incumbents' Bird bids keep the return share
  and mid-level use below real (see the table). Worth its own task.
- Not modelled yet: exception "holds" for a team going under the cap, the room mid-level for teams that never used
  room, mid-level proration after January 10, the disabled-player exception, traded-player exceptions, 120% rookie-scale
  holds for unsigned picks (the game signs picks on draft night), unlikely bonuses and qualifying offers in apron
  payroll, the second-round pick exception, two-way slots.
- Roster repair still fills to the roster minimum past a triggered hard cap (written at the true minimum and noted on
  the ledger); a real team would have to cut first.
- Extensions still use their own check (`extension_offer_fits_hard_cap`); hook them to the ledger in slice 2.
- Multiplayer: `renounce_cap_hold` and `free_agent_offer_quote` were registered in `multiplayer.py` (two lines).

## Resume state
- Done: all of slice 1, tests, replay, screenshots, this report, board row set to review. Branch commits only.
- Local outputs (git-ignored): `output/fa-real-slice1/` (base and run replays, metrics, profiler output, scripts).
