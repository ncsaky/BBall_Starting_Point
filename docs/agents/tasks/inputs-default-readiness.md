# Can new saves default to the 94-input ratings?

_Claude (Opus agent), 2026-11-18/19, branch `worktree-agent-afad0c0de05059c51`. Measurement only: no game code or default changed._

**TL;DR**
- **Yes, flip the default soon.** After two AI-run seasons the 94-input league ages *better* than the older ratings: star counts stay steady (7 players at 72+ after two years, 10 at the start) while the older set inflates (27 → 33); its stat lines stay closer to the real NBA (13 of 18 league measures in range vs 11 of 18); no broken values, and the card always agrees with the engine.
- **What must happen first (about a day of work):** flip four default switches, rewrite 12 tests that pin the older ratings (all fail only because of the flip; none is a game bug), and smoke-test a packaged build. **Should follow quickly:** one rating scale on screen (the card says Jokić 95.4, the tables say 77.9) and a speed fix (a month takes ~55% longer on the 94-input ratings in an aged league).
- **Small setbacks to accept and state:** slower months; fewer "star" numbers on screen; generated draftees rarely reach the top 100 within two drafts; the league gets slightly more even in year two than the real NBA (both rating sets, a bit more with the 94 inputs).

## 1. What was run

Two leagues, same seed (17), same team (GSW, hands-off: the AI runs every team, including trades, free agency, draft and development), from the 2026-27 opening day to 2028-11-01 (two full seasons, two drafts, two free agencies) through the same app actions as the GUI. Harness: `scripts/two_season_league_probe.py` (the `build_mature_fixture.py` loop with the rating set as a flag). Analysis: `scripts/inputs_readiness_report.py`. Both ran in parallel on a heavily loaded machine (load 15-90), about 40 minutes each.

Final saves (kept for the trade review): `output/inputs-readiness/<set>/saves/league.json` plus `league.history.sqlite3`. Per-action checkpoints were deleted.

"Overall" below is the engine's own player value at a neutral 24 minutes (what the AI front offices read), on the scale the tables show. Opening day = a fresh save of the same seed.

## 2. League health after two seasons

### Stars and talent spread (rostered players)

| | Older ratings, opening | Older, after 2 seasons | 94 inputs, opening | 94 inputs, after 2 seasons |
|---|---:|---:|---:|---:|
| Overall 72+ | 27 | **33** | 10 | **7** |
| Overall 70+ | 39 | 51 | 17 | 16 |
| Overall 65+ | 83 | 107 | 64 | 64 |
| Overall 60+ | 153 | 202 | 123 | 127 |
| League median overall | 56.6 | 59.0 | 54.6 | 56.0 |
| Best player | Wembanyama 81.5 | Giannis 79.5 | Jokić 79.1 | Jokić / Gilgeous-Alexander 77.9 |

The older ratings inflate: two seasons add six 72+ players and 24 players at 65+. The 94-input league holds its shape (65+ unchanged at 64).

### Top 10 after two seasons

| # | Older ratings | Age | Ovr | 94 inputs | Age | Ovr |
|---|---|---:|---:|---|---:|---:|
| 1 | Giannis Antetokounmpo | 33.9 | 79.5 | Nikola Jokić (BOS) | 33.7 | 77.9 |
| 2 | Scottie Barnes | 27.3 | 79.2 | Shai Gilgeous-Alexander | 30.3 | 77.9 |
| 3 | Cooper Flagg | 21.9 | 78.6 | Luka Dončić (DEN) | 29.7 | 74.2 |
| 4 | Chet Holmgren | 26.5 | 78.5 | Giannis Antetokounmpo | 33.9 | 74.2 |
| 5 | Anthony Edwards | 27.2 | 78.3 | Victor Wembanyama | 24.8 | 73.8 |
| 6 | Shai Gilgeous-Alexander (DEN) | 30.3 | 78.0 | Cade Cunningham | 27.1 | 72.2 |
| 7 | Darius Acuff Jr. | 22.0 | 77.7 | Scottie Barnes | 27.3 | 72.2 |
| 8 | Jaren Jackson Jr. | 29.1 | 77.6 | Tyrese Haliburton | 28.7 | 71.8 |
| 9 | Bam Adebayo | 31.3 | 77.3 | Donovan Mitchell (ORL) | 32.2 | 71.5 |
| 10 | Victor Wembanyama | 24.8 | 76.9 | Austin Reaves | 30.4 | 71.5 |

Older ratings: Jokić falls to 14th, Andrew Wiggins (33.7) is 18th, and a 2027 rookie drafted 4th (Quentin Coleman, 20) is already 11th. 94 inputs: the top looks like today's NBA, aged two years. Full top 30 is in `output/inputs-readiness/report_<set>.json`.

### Young players (23 and under) and draftees

| | Older ratings | 94 inputs |
|---|---|---|
| Best young players | Flagg 78.6 (#3), Acuff 77.7 (#7), Coleman 76.2 (#11, 2027 pick), Ace Bailey 74.7, Dybantsa 72.8, Peterson 72.7 | Acuff 69.8 (#18), Peterson 69.2 (#22), Flagg 68.7 (#25), Harper 67.2 (#37), Flemings 64.9, Philon 64.2 |
| 2027-28 draftees in the top 100 | 16 (10 real college players, 6 generated) | 3 (all real college players) |
| Best generated draftee | Beckham Black (2028, pick 3) 71.6, #35 at age 19 | Beckham Black (2028, pick 2) 60.6, #118 |
| Best 2027 real college draftee | Coleman (pick 4) 76.2, #11 | Patrick Ngongba II (pick 5) 63.5, #83 |
| Average age of the top 100 | 28.4 → 26.9 | 28.9 → 29.1 |

The older ratings turn rookies into stars within a year (known, accepted earlier). The 94-input ratings go the other way: no generated draftee reaches the top 100 within two drafts, and only three real 2027 college players do (all picks 5-31, aged 22). That matches the open note from the prospect work: top-3 picks become stars less often than real ones.

### Rosters, payroll, trades

| | Older ratings | 94 inputs |
|---|---|---|
| Roster sizes after 2 seasons | 14-15 | 14-15 |
| Payroll spread (low / median / high, $M) | 117 / 215 / 247 | 114 / 215 / 253 |
| Trades (2026-27 / 2027-28 / 2028-29 so far) | 87 (35 / 41 / 11) | 88 (35 / 41 / 12) |
| Players moved / picks moved | 177 / 102 | 178 / 108 |
| Players 23 or younger moved | 10 | 10 |
| Players earning $8M or less moved | 74 | 53 |
| Star sent out for only young players or picks | 1 | 1 |
| Players 24 or younger per team (opening → after) | 4.7 → 5.4, most on one team 9 → 10 | 4.5 → 4.9, most on one team 9 → 8 |

**No hoarding of young, cheap players** after today's trade-value change: the young-player count per team gets *more* even in the 94-input league, young players change hands as rarely as before, and nearly all big trades are stars or high-salary veterans swapped for other veterans. Trades worth a human look (94 inputs): Jokić for Dončić straight up (Denver and the Lakers, July 2027, both "exiting" their window); Mitchell for Banchero plus a first; Durant for Jaylen Brown; Anthony Davis for Anunoby. Older ratings: Jokić for Gilgeous-Alexander plus McCain (February 2028); Booker for Kyrie Irving plus young players; Brunson for Tre Johnson plus two others.

**Trade lists for review** (every trade: date, teams, each side's players and picks including swap and protection terms, age and contract at the trade, minutes before the trade, each team's record and team-building phase, and both teams' valuation notes):
- `output/inputs-readiness/trades_inputs_v1.json` / `.md`
- `output/inputs-readiness/trades_legacy_traits.json` / `.md`

Limits: the save does not store a player's market value at trade time, so the lists give each player's value at the end of the run plus each team's valuation of the whole trade at the time (incoming / outgoing / net). Minutes before a trade come from game logs, which the save keeps only for 2027-28 and later; 2026-27 trades show the coach's minutes projection instead.

### Minutes (both rating sets: not caused by the ratings)

| Completed season | Players at 30+ min/game | Players at 34+ min/game | Top-30 players' average min/game | Most min/game |
|---|---:|---:|---:|---:|
| Real NBA 2025-26 (40+ games) | 71 | 18 | — | 38.0 |
| Older ratings 2026-27 / 2027-28 | 146 / 153 | 94 / 96 | 36.5 / 37.2 | 40.7 |
| 94 inputs 2026-27 / 2027-28 | 150 / 146 | 84 / 98 | 36.1 / 36.8 | 40.5 |

The AI coaches play their starters far more than real coaches do in the full, as-played game (about five times as many 34-minute players). This is the same in both rating sets, so it does not affect the default decision, but it is the biggest realism gap this run found. Worth its own task (the rotation-shape work tuned the opening rotation, not the season as played with injuries, fatigue and blowouts).

## 3. Aged scorecards

### What could and could not be measured

- **Betting-odds test: not measurable.** It needs market lines for real games; an aged league has none. The closest honest substitute is team-strength spread and parity against the real league (below).
- **Real-stat test, official form: not measurable.** It replays the real 2025-26 games with real minutes, which needs today's real rosters. Instead: (a) the same league measures from a 1,230-game run with healthy, coach-projected rotations, opening day vs. aged league, same mode (so the change is the honest signal); (b) per-team-game rates from the two seasons as actually played; (c) the spread of per-36 numbers among rotation players vs. the real league.

### League measures, 1,230 games with projected healthy rotations (18 measures, band = real 2025-26 ± team spread)

| | Older, opening | Older, aged | 94 inputs, opening | 94 inputs, aged |
|---|---:|---:|---:|---:|
| Measures in range | 14/18 | **11/18** | 15/18 | **13/18** |
| Points per game (real 115.6) | 119.5 | 122.8 (out) | 119.2 | 119.2 |
| Offensive rating (real 112.8) | 115.7 | 117.6 (out) | 115.3 | 114.8 |
| True shooting (real .581) | .605 (out) | .621 (out) | .607 (out) | .610 (out) |
| Threes tried per 100 (real 36.1) | 34.0 | 32.8 | 33.9 | **30.4 (out)** |
| Turnover rate (real 12.7) | 13.2 | 13.8 | 13.5 | 14.1 (out) |
| Free-throw rate (real .264) | .310 (out) | .325 (out) | .306 (out) | .295 |

This mode always reads lower than the official replay (which is 18/18 for both sets); compare columns, not against 18. The older league drifts toward more scoring; the 94-input league stays on scoring but drifts toward fewer three-point attempts (30.4 per 100, real 36.1) as rookies and generated players replace shooters. Worth a look: whether generated and rookie three-point volume is set too low.

### As-played seasons (per team game)

| | Real 2025-26 | Older 2026-27 | Older 2027-28 | 94 inputs 2026-27 | 94 inputs 2027-28 |
|---|---:|---:|---:|---:|---:|
| Points | 115.6 | 118.4 | 119.5 | 118.1 | 118.2 |
| True shooting | .581 | .602 | .609 | .603 | .606 |
| Three-point attempt share | .415 | .401 | .398 | .402 | .391 |
| Free-throw rate | .264 | .293 | .305 | .298 | .294 |
| Assists | 26.6 | 27.5 | 27.9 | 28.2 | 28.5 |
| Turnovers | 14.4 | 14.9 | 15.2 | 15.0 | 15.6 |

### Parity (team strength spread)

| | Real 2025-26 | Older yr 1 / yr 2 | 94 inputs yr 1 / yr 2 |
|---|---:|---:|---:|
| Spread of wins (standard deviation) | 13.6 | 11.2 / 10.8 | 11.1 / **10.1** |
| Teams with 55+ wins | 4 | 3 / 4 | 4 / 2 |
| Teams with 25 or fewer wins | 6 | 4 / 4 | 3 / 1 |
| Spread of point margin per game | 6.1 | 6.0 / 5.4 | 5.9 / 5.0 |

Both leagues are more even than the real NBA and get slightly more even in year two; the 94-input league a bit more so (fewer true contenders and tankers). A small, stated setback; a later front-office task (contenders consolidating, rebuilders selling) is the right fix, not ratings.

### Player stat spread (per 36 minutes, rotation players, 10th / 50th / 90th percentile)

| | Real | Older, aged | 94 inputs, aged |
|---|---|---|---|
| Points | 11.2 / 16.9 / 24.7 | 6.6 / 16.6 / 25.6 | 11.7 / 16.6 / 23.2 |
| Assists | 1.9 / 3.5 / 7.0 | 2.3 / 3.5 / 5.9 | 2.0 / 3.6 / 6.4 |
| Rebounds | 3.8 / 5.8 / 10.5 | 3.0 / 5.7 / 8.8 | 3.1 / 6.0 / 9.1 |
| Threes tried | 1.6 / 5.8 / 8.8 | 1.1 / 4.9 / 7.9 | 0.6 / 4.6 / 7.6 |

The 94-input league keeps a realistic bench (low-end scoring matches the real league; the older set's bench scores far too little) and is closer on playmakers; both are short of real elite rebounders and high-volume shooters.

### Other checks (gate 4 of the Stage 1 design)

- No missing or out-of-range values in any of the 811 players' 94 inputs after two seasons of development.
- The card header and the AI's own value agree for every one of the top 40 players (0 mismatches).

### Speed

| | Older ratings | 94 inputs |
|---|---:|---:|
| One month from 2028-11-01, same machine, back to back | 36 s | 56 s |
| Median month during the parallel runs (heavy load) | 44 s | 88 s |
| 2028 draft day during the runs (heavy load, not re-checked) | 67 s | 720 s |

A profile of one 94-input offseason step shows the 94-input model being rebuilt from scratch every time the game copies the league (six times in one step, about a quarter of the time). Caching it per save state should recover most of the gap. The draft-day number was measured under heavy load only and needs a controlled re-check before anyone acts on it. Both sets are already above the 10-20 s month target on this machine.

## 4. Readiness inventory: what still uses or assumes the older ratings

| Where | What it does today | If new saves default to the 94 inputs |
|---|---|---|
| `save.py` `create_league_save` / `_create_league_save` (`ratings_model="legacy_traits"`) | Default for every new save | Change to `inputs_v1` |
| `app_actions.py` create-save (`or "legacy_traits"`) | GUI and API new games | Change; the GUI sends no rating set, so **every GUI game is on the older ratings today** — beta testers have never played the 94 inputs |
| `cli.py` `--ratings-model` default | CLI new games | Change |
| `ratings_model.ratings_model_for` fallback | Saves without a rating set, and the save-less scorecard tools (`calibration_report.py`, `validate-season-probabilities`) use the older set unless `NBA_GM_RATINGS_MODEL=inputs_v1` | Change the fallback so both scorecards measure the default set |
| GUI New Game screen | No rating-set choice | Optional: offer "classic ratings" for one beta cycle |
| Player card (`app.js` `inputsProfilePage`, `playerSummaryRatings`) | 94-input saves show the four-layer card and a header on an unclipped 50 + 15z scale; tables and lists show the engine value on the older scale | **Same player, two numbers** (Jokić 95.4 on the card, 77.9 in tables; Reaves 83.1 vs 71.5). Order always agrees; the numbers don't |
| Mode branches in the engine (`sim.py` points/assists/box rates and the +1.60 offense calibration, `health.py` season-draw size, `transactions.py` impact remap, `impact_value.py`, `development_outlook.py`, `save.py` development routing) | Each has a 94-input path and an older path | Nothing breaks; the older paths stay for older saves until retirement |
| `build_mature_fixture.py` and `tests/fixtures/mature2036_seed17.json.xz` | Built and checked on the older ratings only | Keep as an older-ratings regression fixture for now; build a 94-input one later |
| Soak / market-health harnesses (`ten_season_soak.py`, `overnight_market_health.py`) | Create saves without a rating set | Follow the new default automatically |
| Packaging (`packaging/macos/build.py`) | Ships `data/canonical/*.json` and `.gz`, so the inputs file is included | Works, but also ships the 123 MB uncompressed copy when it exists locally; exclude it. Needs one packaged smoke test |
| A game root without the inputs file | Older ratings work | New game fails ("player_inputs_2026_27.json is missing"); fine for real installs, breaks tests that build a temporary root |
| Small custom universes (tests) | Older ratings work | The 94-input fit fails on tiny leagues ("No current league values for legacy trait release_speed") |

### Tests with the default flipped (measured in a scratch copy)

- **Core suite: 334 of 334 pass.**
- **19 save-creating extra modules (375 tests): 12 failures in 8 modules, all pass on today's default.** None is a game bug:

| Test | Why it fails with the flip | Fix |
|---|---|---|
| `test_forward_tuning` (2) | Expects the older hidden ratings exactly | Pin `ratings_model="legacy_traits"` or use relative checks |
| `test_imported_rookie_ratings` (2), `test_imported_tail` (1), `test_player_tuning` (1) | Exact older-ratings values | Same |
| `test_foundation` zero-traits (1) | A zero hidden rating is re-derived from the inputs (9.2) | Pin the older set |
| `test_foundation` trade-finder (1) | A pinned market case (Micah Potter) has a different value | Pin the older set or re-pick the case |
| `test_foundation` random-team filename (1) | Temporary game root lacks the inputs file | Copy the `.gz` into the temporary root |
| `test_player_lifecycle` roster cap (1) | Tiny test league can't fit the 94-input model | Pin the older set |
| `test_player_profile` (1) | Asserts that default saves have no 94-input card | Update the assertion |
| `test_talent_balance` old save (1) | Old-save compatibility | Retire (old saves don't matter) |

## 5. Blockers, ranked

| # | Item | Must / should | Effort |
|---|---|---|---|
| 1 | Flip the four defaults (save, app action, CLI, scorecard-tool fallback) | Must | 30 min |
| 2 | Fix the 12 tests above | Must | 2-3 h |
| 3 | Packaged build smoke test on the 94 inputs; exclude the uncompressed inputs copy from packages | Must before the next beta ZIP | 1 h |
| 4 | One rating scale on screen (card header vs tables) | Should, before beta testers see it | Half a day (decide the scale, then payload + GUI) |
| 5 | Speed: cache the installed 94-input model per save state; re-check draft day under normal load | Should | Half a day |
| 6 | User review of the card and about 20 known players (Stage 1 gate 5) | Should (user) | User time |
| 7 | Three-point volume drifts down in the aged 94-input league | Watch / own task | Investigation |
| 8 | Parity compresses in year two (both sets, slightly more on the 94 inputs) | Watch / front-office task | — |
| 9 | Stars' minutes far above real in the as-played season (both sets) | Own task (not a flip blocker) | — |
| 10 | Generated and top draftees slow to become stars on the 94 inputs | Known follow-up from prospect work | — |

## 6. Recommendation

Flip the default now, as one small change: items 1-3 (about half a day including the test fixes and a packaged smoke test), with a short note to beta testers. Do item 4 before the next beta ZIP so players don't see two different numbers for the same player, and item 5 soon after. Keep the older ratings available from the CLI (and optionally as "classic ratings" in New Game) for comparison; retiring them is the later stage.

Why now: the 94-input set already beats the older set on both opening-day scorecards (odds Brier 0.1939 vs 0.2140; real stats 18/18 both), and this run shows it also ages better: no star inflation, a realistic bench, closer league measures after two seasons (13/18 vs 11/18), no broken values, card and engine in agreement, and no front-office pathology from today's trade-value change. The setbacks to state openly are speed (+55% per month in an aged league), fewer high numbers on screen, slower rookie stardom, and slightly flatter parity in year two.

## Files

- Harness: `scripts/two_season_league_probe.py`; analysis: `scripts/inputs_readiness_report.py`
- Reports: `output/inputs-readiness/report_legacy_traits.json`, `output/inputs-readiness/report_inputs_v1.json`
- Trade lists: `output/inputs-readiness/trades_<set>.json` and `.md`
- Final saves: `output/inputs-readiness/<set>/saves/league.json` and `league.history.sqlite3`
