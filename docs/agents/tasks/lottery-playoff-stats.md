# LOTTERY-PLAYOFF-STATS: the 3-2-1 draft lottery, and playoff stats kept per season

Progress: 8/8 - done

Owner: Claude (side session, worktree `lottery-playoff-stats-563e57`). Approved by the user 2026-11-26.

## Objective
A. From the 2027 draft on, run the NBA's real "3-2-1" lottery: field, odds, picks drawn, limits, order after it.
B. Each postseason's player playoff stats are their own season's: no adding up, playoff leaders show that season,
Finals MVP uses that year's Finals, player pages carry each season's playoff line (archived seasons too).

## Boundaries
`draft.py`, draft config, the playoff-stat, award and lottery code in `save.py`, `season_archive.py`, history readers,
tests, this file. Not `src/nba_gm_data/gui/`, trade code, the game engine or the board.

## Steps (M = 8)
1. Read rules, write-up and notes
2. Study lottery and playoff-stat code
3. Build the 3-2-1 lottery
4. Build per-season playoff stats
5. Tests (focused, local)
6. Two-season proof run on Azure
7. Full suite
8. Commit and report

## Resume state
- Done, ready for the coordinator's review. One commit on `claude/lottery-playoff-stats-563e57`, not pushed.
- Two-season run: `output/lps/two` (Azure job `lps-two`, log `output/lps/two.log`, checks `output/lps/proof.txt`).
- Full suite: run on the laptop at the coordinator's request (all cloud machines busy; queued Azure job cancelled
  before it claimed one). Log `output/lps/suite_local.log`.

## Report

**TL;DR**
- **The new draft lottery is in, from 2027 on.** 16 teams, 37 balls, all 16 picks drawn. The game's draw matches the
  league's published odds table.
- **Playoff stats now belong to one season each.** Leaders and Finals MVP use only that year's playoffs.
- **Not on screen yet:** the player page has each season's playoff line in its data but does not draw it, and the
  lottery screen still has old wording. Both are screen changes for the design pass (list below).

### The lottery rules the game now follows
| Who is in | Teams | Balls each | Chance at No. 1 each |
|---|---|---|---|
| Three worst records | 3 | 2 | 5.4% (never lower than 12th) |
| Other teams that missed the play-in | 7 | 3 | 8.1% |
| 9th and 10th seeds (even if they win into the playoffs) | 4 | 2 | 5.4% |
| Losers of the 7th-vs-8th game (even if they make the playoffs) | 2 | 1 | 2.7% |

- All 16 picks are drawn. The other 14 teams pick 17-30, worst record first.
- Second round: picks 31-46 run opposite to picks 1-16; picks 47-60 go by record.
- A team's own pick cannot be No. 1 two years running, or top five three years running, even if traded. The limits
  look back at the real 2025 and 2026 drafts, then at the save's own drafts. So in 2027 Washington can pick no higher
  than 2nd and Utah's pick no higher than 6th. When either is in the lottery, everyone else's chance at No. 1 rises
  (in the run below: 9.7%, 6.5% and 3.2%).
- The 2026 draft keeps the old 14-team rules.
- Odds shown on screen come from the same code as the draw.

### 2027 lottery in the two-season run
| Pick | Team (record) | Group | Chance at No. 1 |
|---|---|---|---|
| 1 | Orlando (42-40) | 9th/10th seed | 6.5% |
| 2 | Phoenix's pick, owned by Houston (22-60) | three worst | 6.5% |
| 3 | New York's pick, owned by Brooklyn (46-36) | 7th-vs-8th loser | 3.2% |
| 4 | Memphis (46-36) | 7th-vs-8th loser | 3.2% |
| 5 | Milwaukee's pick, owned by Oklahoma City (36-46) | missed play-in | 9.7% |

Picks 6-16: Utah (to Memphis), Atlanta (to San Antonio), New Orleans, Chicago, the Clippers (to Oklahoma City),
Brooklyn (to Houston), Sacramento, Miami (to Golden State), Dallas (to New York), Washington (to the Lakers), Golden
State (to the Clippers). Brooklyn and Sacramento, the two worst records, landed 11th and 12th. The draft that followed
used this order for all 60 picks (same check passed in 2028, where Portland won).

### Season 2 (2027-28) playoff leaders, players with 8 or more games
| | Points | Rebounds | Assists |
|---|---|---|---|
| 1 | Luka Dončić 31.4 (8 games) | Karl-Anthony Towns 11.5 | Luka Dončić 10.1 |
| 2 | Shai Gilgeous-Alexander 28.0 (17) | Victor Wembanyama 9.6 | Jalen Brunson 7.4 |
| 3 | Victor Wembanyama 26.5 (16) | Cameron Boozer 9.1 | Stephon Castle 7.2 |
| 4 | Tyrese Maxey 25.7 (16) | Cooper Flagg 8.7 | Dylan Harper 6.2 |
| 5 | Kyrie Irving 25.1 (14) | Santi Aldama 8.5 | Shai Gilgeous-Alexander 6.1 |

Oklahoma City won both titles; Gilgeous-Alexander was Finals MVP both times (2028: 27.5 points in a 4-game Finals).

### Proof from the run
- Two hands-off seasons on Azure, seed 20261126, no crashes (37 minutes).
- Every player's playoff totals equal the sum of that season's playoff box scores only: 0 differences among 269 players
  in 2026-27 and 271 in 2027-28.
- Each Finals MVP, recomputed from that Finals' box scores alone, matches.
- Gilgeous-Alexander's player-page data shows both postseasons: 19 games, 28.4 points (read from the season archive
  file) and 17 games, 28.0 points.
- The run's own audit still lists stale "unrostered players" and "award list" messages (also in the earlier one-season
  review) and, in season 2, an unfilled staff job on the hands-off Brooklyn team.

### How the playoff stats are stored now
At the new season the finished postseason (player totals and Finals MVP) is saved on that season's history entry and
the live table starts empty. Older seasons' playoff totals move to the season archive file with the rest of their
detail. Play-in games still count in these totals, as before. The old whole-playoffs fallback for Finals MVP is gone.
A career that already started a new season under the old code still holds added-up totals until its next rollover
(and that season's player-page line would include them); not repaired, since old saves don't matter.

### Screen changes needed (not made: the screen files are another session's)
1. Draft lottery card (`gui/app.js`, about line 6374): "Four picks drawn · Remaining teams follow record order" and
   "14 → 1" are wrong for 2027+. When `lottery.format` is `"3-2-1"`: all 16 drawn, count from 16.
2. The reveal's "jumped into the top four" notice (`gui/app.js` and `lotteryRevealState` in
   `gui/simulation-presentation.js`) assumes four drawn picks; hide it for 3-2-1.
3. Check that 16 rows fit the card (its height is fixed). Each odds row now also carries `group`, `balls`,
   `highest_pick` and `lowest_pick` if the card should show them.
4. Year-end slide (`gui/season-slideshow.js` line 259): "of 14" should use the new `lottery_teams` value. A playoff
   team can now be in the lottery.
5. Player page: every `career_seasons` row now has `playoffs` (games, team games, per-game stats, shooting) when the
   player appeared. The season strip needs a playoff line. No screen showed a career playoff total, so none was added.

### Left for others
- **Trade code:** refuse new top-12 to top-15 pick protections (`trade_pick_terms.py`, `pick_rules.py`, AI offers);
  re-fit how computer teams value future picks (`transactions.future_adjusted_pick_slot`), because the worst record no
  longer means much better odds.
- The command-line quick sim and a rollover with no draft run still ignore the saved lottery order (older problem).
- Player pages show no real playoff history from before the save (the data file `player_playoff_stats.json` exists).

### Judgement calls on rules the sources don't settle
- **Second round:** the league's odds sheet says picks 31-46 reverse the lottery; the league's explainer page says the
  whole second round goes by record. I followed the odds sheet (the approved rules, matched by other outlets).
- **12th-pick floor:** the sheet does not say how it works. Drawing only the three worst once their open slots run
  down to them reproduces the published table in every cell (within its rounding).
- **Barred team drawn too high:** it moves down to the first pick it may hold. This is the league's proposal wording as
  quoted by outlets; the final sheet is silent.
- **Ties in record** are broken as before (by team abbreviation); the real rules were not published.
- **2030 on:** the league has not voted; the game keeps 3-2-1. Penalty powers are not modeled.

### Sources
- [League odds sheet](https://ak-static.cms.nba.com/wp-content/uploads/sites/46/2026/05/NBA-3-2-1-Draft-Lottery.pdf)
- [League announcement](https://pr.nba.com/nba-board-of-governors-approves-new-draft-lottery-system-to-address-tanking/)
- [League explainer](https://www.nba.com/news/nba-draft-lottery-explainer)

### Tests
- New `tests/test_draft_lottery_321.py` (field, 40,000 draws against the published table, floor, repeat limits, order,
  screen data, protected pick, 2026 unchanged) and `tests/test_playoff_stats_by_season.py` (two postseasons, totals,
  Finals MVP, leaders, player page before and after archiving).
- Updated: `test_draft_lottery_field.py` (now the 2026 rules), `test_season_archive.py`, three lines in
  `test_foundation.py`.
- Full suite on the final code (`run_tests_parallel.py --all --workers 2 --js`, this worktree): 2,690 tests,
  0 failures, 0 errors, 80 skipped; browser tests all passed.
