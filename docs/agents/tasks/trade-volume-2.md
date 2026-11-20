# Trade volume 2: trades on the real calendar, market targets, free-agent prices for stars (2026-11-20)

_Claude (Opus agent), branch `worktree-agent-a75a1b26713a9f12d` (from main at 7b3e095). Follows `trade-volume.md`
("What's left"). Status: **review** (committed on the branch, not pushed or merged)._

## TL;DR
- **More trades, at the times real teams make them: 66 -> 80 over two seasons (real about 110).** Draft nights 5 -> 9
  and 7 (real 8-11), late-summer trades 0 -> 6, three-team deals 7 -> 11. The cause was mostly caps on the calendar.
  Real teams make almost no trades from October to mid-January, so that part was already right.
- **The trade deadline is still short (about 25 deadline-week trades in two seasons, against about 50 real).** The
  funnel shows why: buyer and seller prices rarely overlap, because salary matching forces buyers to give up
  players they value. Two new target kinds and a fairer pick rule helped only a little. The next fixes are listed below.
- **Stars now get star money.** Before, Jokic signed for $18.9M; now he asks his $61.8M max, teams re-sign their
  stars first, and rebuilding teams stop paying veterans. The middle of the free-agent market keeps the old rule
  for now.

## What the real calendar says (and what it changed about the plan)
Real counts, every trade counted once (Basketball-Reference "2025-26 NBA Transactions"; Hoops Rumors "2025 NBA
offseason trades" and "2025/26 in-season NBA trades"; ESPN "NBA trade tracker: 2026 offseason"; fetched 2026-11-20):

| Window | 2025-26 league year | 2026 offseason | Two-season probe before this task |
|---|---:|---:|---:|
| Draft week (June) | 12 in June 2025 (8 on the draft's two days) | 14-28 in June 2026 (11 on draft night, pick swaps included) | 5 a draft (the cap) |
| July | 16 (14 on the two days the moratorium ended) | 8 (3 on July 1) | 7 and 10 |
| August + September | 3 | 5 | 0 (the game skipped them) |
| October to mid-January | 0 (one trade on Jan 9) | - | 7 and 5 |
| Deadline week (Feb 1-5) | 28 (2, 0, 2, 6, then 18 on deadline day) | - | 11 and 13 |
| Whole year | about 60-75 | | 33 a year |

So the brief's guess that the missing trades are ordinary in-season trades was not right: real teams make almost no
trades between October and mid-January (one in 2025-26), and the game already made 5-7 a season there. The real gap
is in four places: **draft night** (5, held by a cap, against 8-11), **the opening days of free agency** (the game
allowed at most two trades a day), **late July to September** (the game skipped from free agency to September 1 and
allowed no trades in training camp), and **deadline day** (5-6 a day of supply against 18 real).

## The funnel, window by window
Measured with the new `scripts/trade_funnel_probe.py` on save copies the probe now keeps at each market moment
(`--snapshots`): the same search the game runs that day, run past the day's slot limit, counting every stage.

"Before" is main's code and "after" is this branch, both run on the same before-run saves. A "deal" is a trade both
teams accept. In-season windows use the game's deadline search, free agency uses its everyday search, and every run
ignores the day's slot limit.

| Market day (before-run save) | Teams searching | Targets (per team) | Pairings | Packages built | Sent to the full check | Accepted | Deals found | Slots that day |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| Jan 21 2027 (normal day), before | 29 | 74 (2.6) | 103 | 346 | 56 | 6 | 7 | 0-1 |
| ... after | 29 | 98 (3.4) | 157 | 416 | 61 | 7 | 8 | 0-1 |
| Feb 5 2027 (deadline day), before | 29 | 74 (2.6) | 145 | 723 | 68 | 5 | 5 | 13 |
| ... after | 29 | 98 (3.4) | 229 | 999 | 84 | 6 | 6 | 13 |
| Feb 5 2028 (deadline day), before | 29 | 78 (2.7) | 208 | 2,275 | 46 | 3 | 3 | 14 |
| ... after | 29 | 102 (3.5) | 289 | 2,487 | 61 | 6 | 6 | 14 |
| Jul 1 2027 (free agency day 1), before | 29 | 72 (2.5) | 137 | 387 | 26 | 7 | 7 | at most 2 |
| ... after | 29 | 92 (3.2) | 179 | 524 | 36 | 11 | 7 | 0-6 (mean 3.5) |
| Jul 1 2028 (free agency day 1), before | 29 | 73 (2.5) | 128 | 511 | 44 | 7 | 7 | at most 2 |
| ... after | 29 | 97 (3.3) | 178 | 555 | 44 | 11 | 10 | 0-6 (mean 3.5) |

What it shows:
- **Every AI team already searches on every market day** (29 of 29), so "too few teams searching" was really
  about whether the market opens at all that day. The calendar decides that: a normal autumn day has about a 2-7%
  chance of a trade slot, which matches the real, almost empty autumn.
- **What limits each window is different:**
  - October to January is limited by slots: the market could make 7-8 deals on a normal day but has 0-1 slots, which
    is right.
  - The opening days of free agency were limited by the cap: 7-10 deals available against at most 2 a day.
  - Draft night was limited by the cap: the cap was 5 and every draft used all 5.
  - Deadline day is limited by supply: 3-6 deals against 13-14 slots.
- **Where the deadline supply is lost:**
  - 75-95% of the packages the search builds are screened out before the full check, because the two sides' prices
    don't overlap. Each team values its own players and picks more than the other team does, and salary matching
    forces a buyer to send back rotation players it values highly.
  - About 1 in 10 of the packages that reach the check is accepted.
  - Most refusals come from two hard rules:
    - the buyer's "too much draft capital for the improvement" rule, which refused even one second-round pick for a
      rotation player;
    - the seller's "this weakens a competing rotation" rule, which correctly protects young starters.
  - Packages where only one side is a little short are 25-40% of refusals, so counter-asks (trade step 3) would
    win back a few deals but are not the main limit. I did not build them.
- **Which targets turn into deals:**
  - Salary dumps and "proven player from a seller" make the most deals.
  - Contending teams' "a skill it lacks" target makes many pairings but almost no deals (67 pairings, 0 deals on
    deadline day 2027).
  - Rebuilding teams' "young starter" target is mostly refused by the selling side, correctly.

## What changed
### 1. Trades follow the real calendar (`trade_calendar.py`, `play.py`, `save.py`)
- **Free-agency days** (the game's July 1-5): AI teams can now make up to 6 trades a day (was 2 a day, shared with the
  slots for offers to your team). The expected numbers are 3.5, 2.5, 1.5, 1.0 and 0.8 a day, about 9 in total.
  Real Julys had 16 (2025) and 8 (2026) trades, mostly in the first days; the busiest real days had 8 and 5.
  Offers to your team keep their own slots.
- **Late July and August**: the game skips from the end of free agency to September 1, so the trades of those weeks
  never happened. A market now runs once on August 1 on the way, with about 4.5 trades a summer (at most 8). Real
  summers had about 2-3 in late July and 2-3 in August. The search is the same target search as the rest of the year,
  and it never makes a deal for your team.
- **September** (training camp): trades are legal again for everyone, including you, as in the real league. AI teams
  get a few chances a month, about 1.8 trades (real: 1 and 2).
- **December**: most players signed in the summer can't be traded until December 15. December's few trade chances
  now come after the 15th (the month's total is about the same).
- **Draft night**: up to 10 trades a draft and 3 per part of the draft (was 5 and 2). Real draft nights had 8 (2025,
  over two days) and 11 (2026), pick-only swaps included.
- **Deadline week is unchanged**: the expected slots (about 26 over the week, 15 of them on deadline day) already
  match the real 28 (18 on deadline day). The shortfall there is supply, not slots.

### 2. Two new kinds of targets (`trade_targets.py`)
The real trades the search never looked for (from `data/research/real_trades/trades_2025_2027.json`):
- **"A proven rotation player from a team that is selling"**, for contending and rising teams. Any position; he
  has to make the buyer's top eight. The seller must be rebuilding or retooling and have its own reason to move him
  (a veteran older than its timeline, an expiring veteran, or the trade block). Contenders take players up to 34;
  rising teams up to 31 on 3 years or less. This is the most common real trade after tax moves: Dosunmu, Vucevic,
  Conley, Middleton and Huerter. Before, a contender only looked at its single thinnest position or one missing skill.
- **"A backup at its thinnest spot"**, for contending and rising teams: a player at least 8 points of on-court
  value better than the current backup, paid $15M or less, from a team with a reason to move him. Real examples:
  Kennard, Alvarado, Isaiah Joe and Aaron Wiggins.
- Teams now keep up to 5 targets (was 3), so these two are added alongside the existing ones.
- The quick price screen now allows the same draft spending for real depth as the full check does (0.6 points per
  point of backup gain; `backup_gain`). Before, it dropped every backup package that included a pick.
- Rebuilding teams get neither target. They still don't buy veterans.

### 3. A rotation player may cost about two second-round picks (`trade_roster.pick_investment_outlook`)
- **The rule**: the full check refuses to spend draft picks on a "marginal acquisition". It allowed 8 points of
  draft value plus credit for measured improvement, but in this game one future second-round pick is worth 12-20
  points to a team, so it refused even one second for a player who would play 20 minutes.
- **The change**: a player who takes more than a backup's 16 minutes for the buyer now earns up to 25 more points
  of allowance, about two seconds, the full amount at 24 minutes. Backups and deeper bench players are unchanged.
- **Grounding**: real teams paid one or two seconds for such players: Detroit for Isaiah Joe, Atlanta for Aaron
  Wiggins, Oklahoma City for Nique Clifford.
- This is the one change to the acceptance check, and it applies only to this class of player. A first-round pick
  for no improvement is still refused (tested).

### 4. Free agency: rebuilding teams don't pay veterans; stars ask star money (`payroll_plan.py`, `contract_ai.py`, `cap_rules.py`, `play.py`, `save.py`)
- **Rebuilding teams and veterans**: a rebuilding team no longer signs a free agent aged 30 or older for more than
  the non-taxpayer mid-level exception: $15.044M in 2026-27 (NBA.com cap release), growing with the cap. Before,
  the rebuilding Clippers signed Jimmy Butler (38) for one year at $36M. Re-signing a team's own players is not
  affected, and young players are not limited.
- **Asking prices for starters and stars**:
  - The opening classes (2026, 2027) are still priced from the precomputed market research.
  - Every later free agent asked minutes x $0.48M. In the before run, Nikola Jokic asked $17.8M and signed with
    Boston for $18.9M, Kevin Durant asked $15.8M and Ja Morant $17.3M.
  - Now a free agent rated high-end starter or better who has no research price asks the game's contract-market
    price instead, when it is higher. That price uses the same formula the research used (value, role tier, age,
    health), grows with the cap, and never goes above the real maximum salary for his years in the league: 25% of
    the cap with 0-6 years, 30% with 7-9, 35% with 10 or more (new `cap_rules.max_salary`).
  - Effect on the 2028 class: Jokic $61.8M (his 35% max), Donovan Clingan $33.0M, Ja Morant $27.2M, Zion Williamson
    $26.5M, Kevin Durant (40) $27.3M. Only 12 of 261 asks changed.
- **Teams keep their stars**:
  - An AI team now always keeps its expiring starter-or-better (33 or younger) if its cap and payroll plan allow.
    Before, this was a dice roll capped at 72%, which is how Denver lost Jokic.
  - He re-signs at that same market price. Before, the re-signing rule paid minutes x $0.52M capped at $32M, which
    would have paid Jokic about $24M.
- **Why only starters and stars**: the same formula prices young bench players at the rotation-tier cap. I tested
  it on the 2027 class, and many $6M asks became $16.6M, so lower tiers keep the old rule.
- **How it compares with real contracts**: against real 2026 contracts the formula still prices stars low (Trae
  Young $38.6M against a real $53.0M, Austin Reaves $31.8M against $46.25M, Jalen Duren $29.0M against $40.0M). So
  it is a floor under the old ask, not a full price model. See "What's left".

### 5. Measurement
- `scripts/trade_funnel_probe.py` (new): the funnel on any saved day, by target kind, with every refusal's rule.
- `scripts/two_season_league_probe.py --snapshots`: keeps save copies at the deadline, the draft, the first day of
  free agency and training camp, so the funnel can replay those days.
- `data/research/free_agent_contracts_2025_2026.json` (new): real 2025 and 2026 free-agent contracts (36 and 48),
  the cap and mid-level figures, and the max-salary tiers, with sources. Some entries are marked uncertain.

## Before and after against real
Two-season probe: seed 17, Golden State hands-off, 94-input ratings, 2026-10-20 to 2028-11-01, one run at a time.
- **Before** is main at 7b3e095 (the merged trade-volume work plus the later merges).
- **After** is this branch at e74e2a0 (sections 1-4). It does not include the September fix (6f1f42c, below).
- Taxpayers are counted at the real line in both runs.

| Measure | Before | After | Real |
|---|---:|---:|---:|
| Trades, whole run (2026-27 / 2027-28 / summer and Oct 2028) | 66 (23/30/13) | **80** (32/29/19) | ~110-140 (60-75 a year) |
| ... deadline week, per season | 11 / 13 | **16 / 9** | 23-28 |
| ... draft (June), per draft | 5 / 5 | **9 / 7** | 8-11 on draft night, 12-28 in June |
| ... July, 2027 / 2028 | 7 / 10 | 6 / 12 | 16 (2025), 8 (2026) |
| ... August, 2027 / 2028 | 0 / 0 | **2 / 4** | 2-3 |
| ... October to January, per season | 7 / 5 | 7 / 5 | 1 (2025-26) |
| Three-team trades | 7 | **11** (7 draft chains, 2 salary absorbers, 2 tax relief) | ~8 a season |
| Teams over the line entering deadline week -> season end, 2027 | 11 -> 9 | 13 -> 11 | 14 -> 7 (2026) |
| ... 2028 | 10 -> 9 | 11 -> 8 | 7-14 -> 6-8 |
| Tax payout per team under the line (2026-27 / 2027-28) | $4.1M / $3.7M | $4.8M / $3.1M | $4.9M-$11.5M |
| Players traded twice / three times | 5 / 0 | 19 / 0 | |
| ... traded again within 6 months (the "hot potato" case) | 2 | 4 (2 within 4 months) | rare |
| Young starters moved | 1 | **0** | |
| Rebuilding team takes a 30+ player on $15M+ for 2+ years | 1 | **0** | ~0 |
| Rebuild sales / salary dumps (with a pick) | 12 / 16 (6) | 11 / 12 (8) | |
| Trades with every team's reason stated | 64 of 66 | **78 of 80** | |
| Odd phase labels at the deadline | 0 | 0 | |
| CPU seconds, whole run (2027 deadline; 2028 deadline, 2 steps) | 1,182 (53; 94) | **1,175** (58; 84) | |
| 2028 free agency: market signings / re-signings / waiver claims | 95 / 36 / 13 | 83 / 36 / 8 | |
| 2028 market signings: salary as a share of the ask (median, middle half) | 1.09 (1.01-1.15) | 1.07 (1.00-1.14) | |

How to read it:
- **More trades, for the right reasons, but still short of real (80 against about 110).**
  - The gain is where the funnel said the caps were: draft night (+6), the summer (+12, including 6 in the new
    August market) and three-team deals (+4).
  - Deadline week stayed about the same over the two seasons (24 -> 25). It is limited by supply, and the two new
    targets and the pick allowance add only one or two deals per deadline day (funnel table above).
  - The real deadline is the biggest remaining gap: 25 against about 50 over two seasons.
- **October to January is right as it is.** The game's 5-7 a season is already above the real 2025-26 (one trade).
- **The earlier gains hold:**
  - no young starters moved;
  - no rebuilding team took on a big veteran contract;
  - 78 of 80 trades state both teams' reasons;
  - taxpayers stay in the real range;
  - speed is the same, with the deadline days as fast or faster.
- **The one cost is more players traded twice: 5 -> 19.**
  - Most of it comes with more trades: 15 of the 19 second trades came 6 months or more after the first, usually a
    year later, which is common for real role players.
  - Quick re-trades went from 2 to 4: Kobe Sanders after 78 days and Jerquarius Stanback after 117, both moved
    on in a salary dump.
  - Worth watching. The 60-day "recently traded" rule is unchanged.
- **Free agency:**
  - Stars now get star money. Nikola Jokic signed for $59.8M x 4 (Charlotte; his ask was his $61.8M max).
    Before, he signed with Boston for $18.9M.
  - Kevin Durant (40) signed for $24.9M x 1, Kyrie Irving $28.4M x 2, Zion Williamson $23.8M x 4.
  - Re-signings: Giannis Antetokounmpo $46.6M (was $25.0M), Donovan Clingan $33.1M, Ja Morant $27.5M.
  - Jimmy Butler (39) is no longer bought by a rebuilding team.
  - Denver still lost Jokic: at $61.8M the re-signing would put Denver past its hard cap, and the game has no Bird
    rights exception for re-signing over it.
  - Compared with real 2025 and 2026 contracts, top stars are now in the real range (Trae Young $53.0M, Reaves
    $46.25M). The middle of the market keeps the old rule (see "What's left").

The biggest trades, read like a person (after run):
1. **Deadline 2027, New Orleans / Charlotte.** Rising Charlotte gets Dejounte Murray (30, $32.8M) from rebuilding
   New Orleans for Grant Williams and two seconds. This came from the new "proven player from a seller" target.
   **Textbook** rebuild sale.
2. **Deadline 2027, New York / Lakers.** The rising Lakers get Josh Hart from New York, which moved him to get under
   the tax, for Kevon Looney, Jarred Vanderbilt and two seconds (the same new target). **Textbook.**
3. **Deadline 2027, New Orleans / San Antonio.** Contending San Antonio gets Trey Murphy III for Kornet, Carter
   Bryant, Champagnie and a protected first. **Textbook** contender buy (the same deal as the before run).
4. **Summer 2028, Phoenix / Lakers.** The contending Lakers get Miles Bridges (30) from rebuilding Phoenix for a
   young player and a future first. **Textbook.**
5. **Summer 2028, Chicago / Detroit.** Retooling Detroit gets Josh Giddey (25) as Gary Payton II's successor for a
   protected first and a second. **Textbook.**
6. **Deadline 2028, Indiana / Oklahoma City.** Contending Oklahoma City gets Ivica Zubac (31) for rebounding, for
   Alex Caruso (34) and a second. **Textbook**: a swap of veterans for a need.
7. **August 2028, Atlanta / Portland.** Rising Portland gets Nickeil Alexander-Walker for Damian Lillard (38,
   $25.5M, one year left) and two seconds. **Borderline**: rebuilding Atlanta takes an expensive 38-year-old's
   expiring deal for two seconds. It is the real "expiring salary for seconds" shape, but a big number.
8. **Draft nights**:
   - 2027: nine trades, including three three-team chains, Boston and New York buying picks 11 and 13 with future
     firsts, and three early second-round swaps.
   - 2028: seven trades, including four chains.
   - The same shapes as the real June 2026 draft, spread over picks 11-60 (none in the top 10).
9. **Tax moves**: Boston moved Sam Hauser to Chicago in October 2028 to get under the line, and Indiana, New York,
   Minnesota and the Lakers moved bench salary at the 2028 deadline.

The two trades without a stated reason come from the older free-agency trade paths (the cap-room and fallback
trades), as in the before run: Memphis / Lakers for Walker Kessler, and Sacramento / Houston for Reed Sheppard.

## What's left
- **Deadline day is the big remaining gap.** About 25 deadline-week trades over two seasons against about 50 real.
  The funnel shows the cause: the search builds plenty of packages, but the two sides' prices rarely overlap.
  - Each team values its own players more than the other team does.
  - Salary matching makes a buyer send back rotation players it values highly. Real contenders send injured or
    unwanted contracts.
  - Next levers, in order:
    1. Let a buyer match salary with contracts it would rather not have (its own "salary I'd move" list), so it
       does not have to give up rotation players.
    2. Counter-asks (trade step 3), for the 25-40% of refusals where one side is only a little short.
    3. A second, late market pass on deadline day after the first deals change rosters.
- **Free-agent prices below the starter tier still come from minutes after the first two summers.**
  - The contract-market formula is too flat to use for everyone. Compared with real 2026 contracts it underprices
    stars by about a third and overprices the middle: on the 2027 class many $6M young bench players came out at
    $16.6M.
  - A real price model needs a new fit of salary share against the game's value, age and role, using the 84 real
    contracts now in `data/research/free_agent_contracts_2025_2026.json` (some marked uncertain; the 2025 half is
    weaker), plus league-wide cap room as a market factor.
  - Separate small task. Stars and starters are covered for now.
- **No Bird rights.**
  - A team can only re-sign its star under its hard cap. The re-signing order fix (stars first) kept Jokic in Denver
    when the same 2028 draft save was replayed.
  - A team already near the hard cap can still lose a star it would really keep.
- **More players traded twice** (5 -> 19, quick re-trades 2 -> 4). Most of the increase comes with more trades,
  but a "recently acquired" guard of about 6 months for salary dumps would remove the quick ones.
- **Draft week player trades**: real Junes also had 4-9 player trades around the draft (Giannis, LaMelo Ball and
  Kawhi Leonard in June 2026). The game makes only pick trades on draft night. A pre-draft market would need care,
  because pending free agents are still on rosters then.
- **September in the probe**: the September market (commit 6f1f42c) came after the after run; the confirmation
  run below includes it.

## Tests and checks
- New `tests/test_trade_volume_2.py` (20 tests):
  - the calendar: free-agency days, late summer, September in both paths, December 15, training-camp trades, the
    draft caps;
  - the market targets and the quick-screen depth rule;
  - the rotation pick allowance;
  - the rebuilding-veteran rule;
  - max salary, star asks, star retention and the re-signing order.
- The 49 trade, market, contract, free-agency, waiver, lifecycle and foundation modules (the trade-volume list plus
  the new file; 693 tests):
  - All pass except `test_pick_and_pop`, whose reference file under `output/` is not in this worktree (same as main).
  - The two `test_summer_trade_reviews` tests that assumed two trades a day were updated (commit 5b3fd14) and pass.
- `node --test tests/*.test.cjs`: 282 of 283 pass. The startup-movie test needs the ignored movie file, as on main.
- **Not yet run**:
  - `bash scripts/run_core_tests.sh`;
  - the odds check (`validate-season-probabilities --runs 20`).

  Both were waiting for the confirmation probe to finish, to keep one heavy job at a time. Nothing in this branch
  touches the game simulation, so the odds check should match main byte for byte; the coordinator should still run it.

## Files
- `trade_calendar.py`: free-agency day slots, the late-summer market, September, December 15, real-timing sources.
- `play.py`: free-agency day trades (up to 6), `run_late_summer_ai_trades` / `run_summer_ai_market`, draft-night
  caps, `with_star_market_ask`.
- `save.py`: trades legal in training camp; the training-camp market; the September market inside the rollover;
  stars kept and re-signed at market price (`annotate_star_asks`, `re_signing_order`).
- `trade_targets.py`: the "proven player from a seller" and "backup" targets, up to 5 targets, `backup_gain` in the
  quick screen.
- `trade_roster.py`: the rotation-role pick allowance.
- `payroll_plan.py`: a rebuilding team doesn't pay veteran free agents above the mid-level.
- `contract_ai.py`: `star_market_ask_millions`, `years_of_service`.
- `cap_rules.py`: `max_salary` by years of service.
- Scripts: `scripts/trade_funnel_probe.py` (new), `scripts/two_season_league_probe.py` (`--snapshots`).
- Data: `data/research/free_agent_contracts_2025_2026.json` (new).
- Tests: new `tests/test_trade_volume_2.py`; `tests/test_summer_trade_reviews.py` updated for the free-agency
  trade slots.

## Resume state
- **Done**:
  - code and tests (all committed on the branch);
  - the before and after two-season probes, with metrics and the trade read;
  - the funnel on saved deadline, normal and free-agency days;
  - real trade timing and free-agent contract research;
  - this report and the board row.
- **Running at hand-back**: the confirmation probe of the final code, which adds the September market and the
  re-signing order (`output/tv2/final2-src`, log `output/tv2/final2.log`, PID in `output/tv2/final2.pid`). When it
  is done, run:

  `PYTHONPATH=src:scripts .venv/bin/python -u scripts/trade_probe_metrics.py --run output/tv2/final2-src/output/probe --label final2 --out output/tv2/results`

  Then check that Jokic stays in Denver and that the after-run numbers hold.
- **Then run** `bash scripts/run_core_tests.sh` and the odds check.
- **Local outputs** (git-ignored):
  - `output/tv2/results/` (metrics and trade lists: `base`, `final`);
  - `output/tv2/funnel/` (the funnel JSONs);
  - probe saves and snapshots under `output/tv2/{base,final,final2}-src/output/probe/`.
- **Worktree symlinks** (untracked: `.venv`, `data/research/barttorvik`, plus ignored data files) were not committed.
