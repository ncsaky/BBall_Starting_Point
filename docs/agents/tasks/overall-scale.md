# OVERALL-SCALE: one OVR / OFF / DEF scale everywhere

Owner: Claude (Opus agent), worktree branch `worktree-agent-a51c9b4f11d2d9b84`. Status: **review** (committed on the
branch; not pushed or merged). User decision: `docs/agents/tasks/stage2-plan.md`, "User decisions (2026-11-21, night)".

## TL;DR

1. Every screen now shows the same OVR, OFF and DEF for a player: the card, every table, lists, the draft board, the
   assistant's texts and the command-line game. It is a straight line in the game's own value of the player.
2. 90+ is the MVP tier: exactly the analysts' top five (Jokić 95.4, Gilgeous-Alexander 94.5, Wembanyama 92.8, Dončić 91.3, Giannis 90.4). Most rotation players are in the 70s and 80s (95%). The end of the bench reaches the high 60s.
3. Display only. The AI still reads its own number, and trade-want matching was moved onto it, so no AI decision changes. The real-stat scorecard is identical (18/18).

## 1. The mapping and its anchors

The engine's value of a player is his fitted impact: points per 100 possessions in Basketball Index LEBRON units. The
AI orders players by it (the AI's summary number is this value re-spread by league rank). Each display rating is a
straight line in that value (`impact_value.DISPLAY_LINES`):

| Rating | Line | Anchors (why) |
|---|---|---|
| **OVR** | 71.5 + 3.0 x impact | **90** at +6.17: halfway between the analysts' clear top five (lowest: Giannis +6.29) and the next player (Kawhi +6.02). **71.5** at 0.0, a net-zero player. With these, 70 falls at -0.5, about the edge of a team's rotation (the 5th percentile of rotation players). |
| **OFF** | 75.0 + 3.0 x offensive impact | Same steepness as OVR. 90 at +5.0, so elite offense is rare (four players). |
| **DEF** | 72.0 + 6.0 x defensive impact | 90 at +3.0. Defensive impact varies about half as much between players as offensive impact (league range 4.9 vs 8.6 points), so the line is twice as steep. That keeps elite defenders as visible as elite scorers. |

- **What a point means:** one OVR point is a third of a point of net impact per 100 possessions, everywhere on the scale. No compression at the top, and no cap at 100. A player who develops past Jokić keeps rising.
- **How OVR relates to OFF and DEF:** overall impact is offensive plus defensive impact. So, exactly (before rounding), **OVR = OFF + DEF / 2 − 39.5**. One OFF point is worth one OVR point, and one DEF point is worth half. That is a real fact about the value model, not a display choice: the best defender (Wembanyama, +3.5) adds about half as much as the best offensive player (Gilgeous-Alexander, +6.5). Example: Jokić 93.6 OFF and 82.5 DEF give 93.6 + 41.3 − 39.5 = 95.4.
- **Fixed constants:** the lines are fixed numbers in the engine's own units, not re-fitted each season. The same value always shows the same rating, and the league can drift up or down over a career. If the value fit (`impact_value_fit.json`) is refitted, `tests/test_overall_scale.py` checks that the bands still hold.

## 2. Band counts (2026-27 opening league, 691 players)

"Rotation" means each team's top 9 by projected minutes (270 players).

| Scale | Group | 90+ | 85-89 | 80-84 | 75-79 | 70-74 | 65-69 | 60-64 |
|---|---|---|---|---|---|---|---|---|
| OVR | all players | 5 | 14 | 48 | 208 | 332 | 84 | 0 |
| OVR | rotation | 5 | 14 | 45 | 112 | 86 | 8 | 0 |
| OFF | all players | 4 | 22 | 76 | 296 | 283 | 10 | 0 |
| OFF | rotation | 4 | 22 | 61 | 133 | 50 | 0 | 0 |
| DEF | all players | 7 | 20 | 68 | 214 | 301 | 78 | 3 |
| DEF | rotation | 6 | 15 | 44 | 82 | 93 | 28 | 2 |

**OVR spread:**
- All players: lowest 65.8 (Doug McDermott), median 74.0, best 95.4.
- Rotation players: lowest 66.6, 10th percentile 71.6, median 76.6, 90th percentile 83.4.
- 95% of rotation players are in the 70s or 80s, and 3% are in the high 60s.

**90+ lists:**
- **OVR:** Jokić 95.4, Gilgeous-Alexander 94.5, Wembanyama 92.8, Dončić 91.3, Giannis 90.4.
  - These are exactly the analysts' consensus top five (ESPN, Ringer and Nerd Sesh all have the same five, in slightly different orders).
  - Next is Kawhi Leonard at 89.6, who is sixth in the consensus.
- **OFF:** Gilgeous-Alexander 94.5, Dončić 94.1, Jokić 93.6, Haliburton 90.1.
- **DEF:** Wembanyama 93.0, Ausar Thompson 90.3, Mitchell Robinson 90.3, Holmgren 90.3, Hartenstein 90.1, Robert Williams III 90.0, Jarrett Allen 90.0.
  - Gobert is 89.6, just under.

## 3. Top 30: old card, old table, new

"Old card" was the card's own line (median 50, best ~98). "Old table" was the AI's summary number shown in tables. Both
had the same order; neither matched the other.

| # | Player | Impact /100 | Old card | Old table | **New OVR** | New OFF | New DEF | Analyst consensus rank |
|---|---|---|---|---|---|---|---|---|
| 1 | Nikola Jokić | +7.96 | 97.8 | 78.0 | **95.4** | 93.6 | 82.5 | 1 |
| 2 | Shai Gilgeous-Alexander | +7.66 | 95.8 | 75.7 | **94.5** | 94.5 | 79.0 | 3 |
| 3 | Victor Wembanyama | +7.09 | 91.9 | 74.2 | **92.8** | 85.8 | 93.0 | 2 |
| 4 | Luka Dončić | +6.61 | 88.8 | 74.2 | **91.3** | 94.1 | 73.6 | 5 |
| 5 | Giannis Antetokounmpo | +6.29 | 86.6 | 73.9 | **90.4** | 88.9 | 81.9 | 4 |
| 6 | Kawhi Leonard | +6.02 | 84.8 | 73.9 | **89.6** | 88.8 | 80.5 | 6 |
| 7 | Donovan Mitchell | +5.42 | 80.8 | 73.6 | **87.8** | 89.6 | 75.4 | 11 |
| 8 | LeBron James | +5.23 | 79.5 | 73.2 | **87.2** | 87.6 | 78.3 | 19 |
| 9 | Cade Cunningham | +5.22 | 79.4 | 72.9 | **87.2** | 87.3 | 78.7 | 9 |
| 10 | Tyrese Haliburton | +5.11 | 78.7 | 72.5 | **86.8** | 90.1 | 72.5 | 13 |
| 11 | Jayson Tatum | +4.94 | 77.5 | 72.3 | **86.3** | 88.0 | 75.7 | 7 |
| 12 | Stephen Curry | +4.91 | 77.3 | 71.4 | **86.2** | 89.1 | 73.3 | 8 |
| 13 | Joel Embiid | +4.88 | 77.1 | 71.4 | **86.1** | 85.8 | 79.6 | 27 |
| 14 | Chet Holmgren | +4.75 | 76.3 | 71.2 | **85.8** | 80.1 | 90.3 | 14 |
| 15 | Kristaps Porziņģis | +4.72 | 76.1 | 70.3 | **85.7** | 84.2 | 82.0 | - |
| 16 | Scottie Barnes | +4.61 | 75.3 | 69.9 | **85.3** | 81.6 | 86.4 | 10 |
| 17 | Anthony Davis | +4.50 | 74.6 | 69.8 | **85.0** | 80.5 | 87.9 | 35 |
| 18 | Anthony Edwards | +4.50 | 74.5 | 69.7 | **85.0** | 87.0 | 75.1 | 15 |
| 19 | Derrick White | +4.49 | 74.5 | 69.7 | **85.0** | 82.2 | 84.4 | 24 |
| 20 | Kevin Durant | +4.45 | 74.2 | 69.6 | **84.9** | 85.2 | 78.4 | 16 |
| 21 | Evan Mobley | +4.14 | 72.2 | 69.4 | **83.9** | 79.5 | 87.8 | 17 |
| 22 | Paul George | +4.12 | 72.0 | 69.4 | **83.9** | 81.8 | 83.1 | 43 |
| 23 | Jimmy Butler III | +4.11 | 72.0 | 69.4 | **83.8** | 84.2 | 78.4 | 66 |
| 24 | Karl-Anthony Towns | +4.11 | 72.0 | 69.2 | **83.8** | 83.2 | 80.3 | 12 |
| 25 | De'Aaron Fox | +4.08 | 71.7 | 69.1 | **83.7** | 85.2 | 76.0 | 40 |
| 26 | Damian Lillard | +4.06 | 71.6 | 69.1 | **83.7** | 88.2 | 70.0 | 65 |
| 27 | Jalen Williams | +4.01 | 71.3 | 69.1 | **83.5** | 82.6 | 80.9 | 22 |
| 28 | Kyrie Irving | +3.98 | 71.1 | 69.0 | **83.4** | 87.4 | 71.1 | 36 |
| 29 | Isaiah Hartenstein | +3.94 | 70.8 | 68.9 | **83.3** | 77.8 | 90.1 | 51 |
| 30 | Jalen Suggs | +3.94 | 70.8 | 68.6 | **83.3** | 81.3 | 83.0 | 69 |

**Players the analysts rank higher than the value model does:**
- Jalen Brunson: 44th by value, 81.6 OVR. ESPN and Ringer both rank him 6th.
- Bam Adebayo: 81.0. OG Anunoby: 80.7.
- These are value-model questions, not display ones. The display shows the model's value faithfully.

## 4. Every place switched

**One function** (`save.player_display_attribute_summary`) now gives OVR/OFF/DEF on the new scale.
- It feeds every table that already used it: roster, free agency, trade (finder, block, market, offers), draft and league tables, player finder, comparisons, the extension screen, the assistant GM texts and the rating colour quartiles and averages.
- Subratings keep their own grade, unchanged.

Places that showed a different number and were switched:
- **Player card** (`player_profile.engine_header`): now returns the display summary itself.
  - The card's own line (`_ImpactLine`) and the leftover `engine_raw` field (the AI's summary under a second scale) are removed.
  - The card's scale note is rewritten.
- **Team page live/rotation payload** (`save.py`, rotation rows): it sent the AI's summary as `overall`/`attributes`. It now sends the display ratings.
- **Development trend chart** (`app_actions.development_overall_path`):
  - It used to value each month with the old hand formula in a stripped context, a third scale.
  - It now values each month like the card. Today's point equals the card.
- **Draft prospects** (`prospect_cards.py`: draft board, prospect card, command-line scouting):
  - "Now" used the old hand formula. It now goes through the same conversion.
  - Potential, floor and ceiling convert the same way. See "What's left", item 1.
- **Fantasy draft:**
  - The growth outlook's ceiling and growth are now on the display scale, starting from the player's own displayed OVR.
  - The fantasy AI's scoring still reads its engine-scale fields.
- **Extension projections** (`extension_analysis.py`): projected seasons are valued like the card. They used the old formula in a stripped context.
- **Season slides** (`season_slides._player_ref`).
- **Trade wants** (OVR/OFF/DEF thresholds):
  - Thresholds stay stored and matched on the AI's scale, so AI matching is unchanged.
  - The wants screen shows them on the display scale. Thresholds the user types are converted back when saved.
  - A threshold left as shown keeps its stored value exactly, so re-saving doesn't drift.
- **Roster card OFF column** (`gui/assets-desktop.js`, rating renderer only). Found in the running app:
  - The column ignored the server's OFF and showed an average of three subratings (shooting, creation, passing) under the OFF label. For example, Michael Porter Jr. showed 64.9 there and 82.2 on his card.
  - It now reads the server's OFF like OVR and DEF. This bug predates this task.
- **Command-line game** (`play.py`): every OVR/OFF/DEF print now shows the display ratings. These are the cut list, league trait table, trade asset lists, re-signing, free-agent market and comparison, signings, the free-agent investigation (its colour cut-offs moved to 70/80), save free agents, trade offer details, trade player picker and dashboard ratings. Rankings that order those lists still use the AI's number.

**Kept on the AI's scale on purpose** (AI decisions; they now read `save.player_engine_attribute_summary`, which is the old behaviour exactly):
- `trade_wants.player_facts`, used for AI and user want matching.
- `trade_targets`, used for skill-need matching (it reads DEF).

Without this, the AI would have compared the new display numbers against thresholds written for its own scale. That would have changed trades.

**Not changed:**
- The AI's `player_attribute_summary` and every threshold the AI compares against it.
- `presentation_rating_value`.
- The simulation.
- Legacy mode (no new ratings): OVR/OFF/DEF show their grade, exactly as before.
- `gui/app.js` needed no change. Its rating cells already render the server's display values, the card header included.

**Speed:** a display summary costs about 0.12 ms per player with the game's caches on (0.08 ms before). Tables are not noticeably slower.

## 5. Tests

- New: `tests/test_overall_scale.py` (9 tests):
  - Card equals table for named stars plus every 37th player.
  - The scale is a straight line: equal value gaps give equal rating gaps.
  - Order matches the AI.
  - Band counts are within the intended ranges.
  - 90+ includes the analysts' top four.
  - OVR = OFF + DEF/2 − 39.5.
  - Potential-style numbers convert monotonically with no cap and round-trip.
  - AI matching stays on the AI's scale.
  - Trade-want thresholds convert for display and back.
- Updated: `tests/test_player_profile.py`. Two tests pinned the old card line (median 50, best ~98) and the removed `engine_raw` field. They now check card = table and the new line; comments say why.
- **Focused run** (`run_tests_parallel.py --workers 2 --match "player_profile|ratings|summary|display|gui_concept|impact_value|overall_scale|fantasy|prospect|trade_wants|extension|wants|scale" --js`):
  - 137 modules, 1,666 tests.
  - Two failures were old display numbers pinned by tests, now updated with a comment:
    - `test_foundation` league trait table: it pinned the table OVR to the AI's summary.
    - `test_fantasy_draft`: it pinned the shown OVR equal to the engine's number. It now checks the same order.
  - Six errors are not caused by this change: five tests need git-ignored `output/` reference files that this worktree doesn't have (experimental-engine fixtures, a defensive-scale comparison file), and `startup_video.test.cjs` needs a git-ignored video asset. The GUI-server smoke test timed out once under load and passed on rerun.
  - After the updates, all three affected tests pass.
- **Core suite** (`scripts/run_core_tests.sh`): 338 tests, OK.
- **Browser JS tests:** all pass except `startup_video` (missing asset, as above).
- **Real-stat scorecard** (`calibration_report.py --games 1230 --mode replay-real-minutes`): **18/18**.
  - The output is identical line for line to the main checkout's latest run (`output/parallel-tests/calibration.txt`). Only the "games in N seconds" timing line differs. Display only, as intended.
  - Saved at `output/overall-scale/calibration.txt` in the worktree.
- **Running app** at 1440 wide, on a new save (Brooklyn). Screenshots are in `output/overall-scale/` (worktree):
  - The card shows Jokić 95.4 / 93.6 / 82.5 on both pages, with the new scale note (`card_page1_jokic_1440.png`, `card_page2_ratings_jokic_1440.png`).
  - The Player Finder league table shows the same numbers and the same top order as the 90+ list (`league_player_finder_1440.png`).
  - The Roster table shows the card's numbers, after the OFF-column fix (`roster_table_1440.png`).
  - **Free-agency room:**
    - The room is locked in preseason, so it couldn't be shown on screen without simulating to the offseason (not a light job).
    - Its payload was checked directly in the running app: 80 candidates, all on the new scale. Example: Russell Westbrook 75.0 / 77.6 / 73.8, which satisfies OVR = OFF + DEF/2 − 39.5.
    - Its table renders `ratings.overall`.

## What's left

1. **Prospect potentials (decision for the user).**
   - Potential, floor and ceiling are written on the AI's scale, but the top of that range is far above any real player. A potential of 87.9 (Boozer, Dybantsa) is about 10 points above Jokić's 78.
   - Converted honestly onto the one scale, the top tenth of draft prospects show potentials of 100 to 120.
   - The development model treats potential as an upside index (it sets how much room each skill has), not as a forecast of the player's final value.
   - Options:
     - (a) Recalibrate potential so it means the expected peak value. That is a development-model task.
     - (b) Show potential as a growth range ("+N at peak") instead of an absolute number.
     - (c) Keep it as now: labelled, same scale, and visibly above the MVP tier.
   - No clipping was added (rule 3).
2. **Team-level "overall/offense/defense"** in the team identity panels (team signals, the power-rank slide, the CLI team identity) are team aggregates built from the AI's summary numbers. They are not player OVRs and were left alone. If they should read on the same scale, that is a small follow-up.
3. **Generic colour helpers in the GUI.** `ratingTone` (≥92 elite, ≥82 strong, <68 weak) and `plainNumber` (≥70 green) apply to every rating, subratings included. On the new OVR scale, `plainNumber` turns almost every OVR green. Main table cells use league quartiles, which adjust automatically. I didn't touch the shared helpers, to avoid conflicts with the free-agency slice-4 agent.
4. **Free-agency room on screen:** check it visually the next time a save is in the offseason (its payload is verified).
5. **Audit and probe scripts** in `scripts/` that call `player_display_attribute_summary` on new-ratings saves now get display-scale OVR/OFF/DEF. Any that compare against AI-scale cut-offs should switch to `player_engine_attribute_summary`. None of them is gameplay.
