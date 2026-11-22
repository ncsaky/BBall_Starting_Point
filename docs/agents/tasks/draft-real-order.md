# Draft picks closer to the NBA’s order

**TL;DR.** The 2026 replay matched the NBA’s first five picks in all five runs. Lendeborg went 11th to 13th. The typical gap from the NBA order fell from four spots to two for picks 1–14 and from 8.5 to eight for picks 15–30.\
In the separate 2033 class, picks 6–14 reached five or more spots 25% of the time and ten or more spots 13% of the time, down from 38% and 25%. The NBA rates were 28% and 14%.\
The three original generated classes still had a typical second-round gap of six to 7.5 spots. Better scouting staffs continued to make smaller errors, and reaches still bought less talent on average.

## What was pushing the 2026 picks out of order

The saved May 24 mock draft ranked Yaxel Lendeborg 11th, as did the independent board. His starting profile was 55.7 for current ability and 76.9 for potential. The old scouting model took that late-season snapshot and simulated another season’s worth of news on top of it. In the original replay, it added 6.0 potential points for Lendeborg and subtracted 0.6 for Darryn Peterson. Lendeborg rose to sixth on the game’s consensus board. Chicago’s scouts estimated his potential at 84.5. Their GM was rebuilding and added 0.64 grade points for the apparent room to grow. Taking him fourth cost zero reach points because the game’s board already had him sixth. [Archived pre-draft source](../../../data/research/draft_prospects_2026.json)

The old box-score projection also gave more credit to Cameron Boozer’s stronger college production. He had a slightly higher starting potential than Peterson, 87.9 versus 87.5, and the old consensus board had Boozer first and Peterson third in the original replay. Utah took Peterson second in the current starting revision by 0.08 grade points over Boozer. He went third in two of the other four runs. The earlier handoff’s fourth-place result came from a different revision.

Scouts now use the imported pre-draft ranking alongside their own grades when the class comes from an archived public board. Where both publications ranked a player, the model uses the midpoint. This evidence carries the most weight in the lottery, fades down the board, and limits how much invented news can move a well-documented player. Staff still estimate ability and upside individually. Teams still choose using their own grades, needs and plans. Chicago’s revised estimate of Lendeborg’s potential was 79.6, and the consensus had him 11th. The actual NBA draft order enters the research comparison only. [NBA 2026 results](https://www.nba.com/news/2026-nba-draft-order)

## 2026 draft order against the NBA

The simulation kept the archived player pool, fixed pick owners and current game rosters. The four extra runs changed the scouting seed for that same pool. These are selections with fixed owners and no draft-night trades. All 30 players in the NBA’s first round match names in the pool. I grouped them by their **NBA pick** and measured how far each moved in the game, including moves into round two.

| Scouting seed | NBA picks 1–14, before | After | NBA picks 15–30, before | After |
|---|---:|---:|---:|---:|
| Original archive | 5.5 | 2 | 8 | 9 |
| 17 | 4.5 | 1.5 | 8 | 6.5 |
| 23 | 6.5 | 2 | 10 | 8.5 |
| 31 | 3.5 | 1 | 7 | 9.5 |
| 47 | 4.5 | 2 | 12 | 6 |
| **Middle gap across all five runs** | **4** | **2** | **8.5** | **8** |
| Average gap across all five runs | 6.47 | 2.96 | 10.23 | 9.25 |

| Player | Original archive before | Original archive after | After, all five runs | NBA pick |
|---|---:|---:|---:|---:|
| AJ Dybantsa | 1 | 1 | 1 | 1 |
| Darryn Peterson | 2 | 2 | 2 | 2 |
| Cameron Boozer | 3 | 3 | 3 | 3 |
| Caleb Wilson | 7 | 4 | 4 | 4 |
| Keaton Wagler | 5 | 5 | 5 | 5 |
| Yaxel Lendeborg | 4 | 12 | 11–13 | 11 |

## Reaching past the board

At picks 6–14, the team’s scouting grade now carries 75% of the weight, with the league’s scouting grade adding the remaining 25%. Each of these picks still applies its existing bonuses for fit and team strategy. The old reach cost was small enough for a single team’s unusually high grade to outweigh it. The new rule also helps a prospect when that team’s grade is unusually low.

The training comparison used the 2012–2021 NBA drafts and the first two generated classes, 2031 and 2032. I checked the original two game drafts and ran 11 further lottery seeds per class with the same players and scouting reports. The 5% league weight fit those samples best, with 31% five-spot and 22% ten-spot reaches across 196 lottery picks. It left the 2033 overshoot in place. I kept the 25% setting after the 2022–2025 and 2033 comparison, so that comparison helped choose the final setting. The stronger setting was conservative in the training runs, with 20% and 11% reaches against the NBA’s 29% and 21%. I then ran three fresh classes, 2037–2039. Those still reached somewhat too often, though less often than before.

Each cell shows the **middle absolute gap in spots**, then the share of teams that picked someone at least **five / ten spots early**. Game figures use each version’s league scouting board. The NBA figures use the public boards from the earlier study. [Historical fit and sources](draft-decisions-evidence.md)

| Picks | 2031–32 before | After | NBA 2012–21 | 2033 before | After | NBA 2022–25 |
|---|---:|---:|---:|---:|---:|---:|
| 1–5 | 1 · 0% / 0% | 1 · 0% / 0% | 1 · 12% / 0% | 0 · 20% / 0% | 0 · 20% / 0% | 0.5 · 0% / 0% |
| 6–14 | 2 · 22% / 17% | 1.5 · 17% / 6% | 3 · 29% / 21% | 5.5 · 38% / 25% | 3.5 · 25% / 13% | 3 · 28% / 14% |
| 15–30 | 8 · 32% / 23% | 8 · 42% / 26% | 6 · 37% / 25% | 5 · 38% / 6% | 5 · 44% / 6% | 6.5 · 36% / 23% |
| Second round | 8.5 · 20% / 12% | 7.5 · 20% / 12% | 10 · 44% / 32% | 6 · 17% / 13% | 6 · 20% / 10% | 9 · 42% / 29% |

| Game sample | Picks 6–14 before | After | Second-round gap before | After |
|---|---:|---:|---:|---:|
| 2026 original archive | 8 · 56% / 44% | 1 · 11% / 11% | 5.5 | 5 |
| 2026 all five seeds | 4 · 40% / 31% | 2 · 18% / 11% | 5 | 5 |
| 2034–2036 | 6 · 56% / 26% | 5 · 44% / 19% | 6 | 6 |
| 2037–2039, fresh check | 4 · 44% / 30% | 3 · 37% / 22% | 5.5 | 5 |
| NBA 2022–2025 | 3 · 28% / 14% | | 9 | |

The 2026 archive now reaches less often than the historical NBA rate. Across the fresh generated classes, seven of 30 consensus top-ten players slid at least five spots, down from eight. Five fell out of the lottery, down from seven. In the later NBA drafts, the corresponding figures were seven and four out of 40. The fresh classes also exposed a ten-spot reach among the top five that occurred both before and after. The general manager’s rules from pick 15 onward still allow teams to disagree, with different players left to choose from after the lottery.

## Scouting quality and the cost of reaching

I held Toronto’s scout identity and random draws fixed, first at 50 skill and then at 85. Across the nine generated classes and five archive runs, the stronger staff’s average coverage was 83% versus 52%. Its average estimated current-ability miss was 1.0 points versus 3.0. Its potential miss was 3.7 versus 7.3. The grade, rank and coverage on Toronto’s June board matched the reports used by the AI in all 14 runs.

These are average underlying game talent grades. The outcomes comparison uses the game’s ability, potential, floor, ceiling and risk before career development. Each row compares reaches of at least five spots with picks within four spots of the game’s consensus.

| Pick range | Before, reach / near board | After, reach / near board |
|---|---:|---:|
| 1–5 | 65.3 / 73.5 | 65.3 / 73.8 |
| 6–14 | 60.2 / 68.0 | 60.2 / 68.5 |
| 15–30 | 55.1 / 61.4 | 54.9 / 61.7 |
| Second round | 47.1 / 48.1 | 46.8 / 48.4 |

## Speed and verification

On the laptop the cold selection-only draft took a median of 102 ms before and 101 ms after across the nine generated classes. The monthly scouting build took 80 ms before and 79 ms after. The full draft room took 54.9 seconds before and 55.2 seconds after on the same Azure worker. Both are medians of three runs, with ranges of 54.0–59.0 and 55.0–56.6 seconds. Every run applied 59 picks and returned nine trade notices.

All 40 draft tests passed on Azure. The historical evidence build reproduced its checked-in file byte for byte, and the new fitting grid matched its first run byte for byte. The core suite ran 351 tests with no failures and one skip for missing archived trade-salary fixtures. The real-stat replay kept all 18 league metrics in range over 1,230 games.

## Reproduce the checks

Run these commands in the task worktree. The starting revision is `e854fc3b`. For a paired comparison with the same research script, set `GM_LOTTERY_CONSENSUS_SHARE` to zero and use a zero archive board share at every rank. Those two settings reproduced the unmodified starting revision’s 2026 choices and score details in all five runs. The draft-room timing runs on a copied 2029 Toronto lottery save and includes trades and signings.

```sh
mkdir -p output/draft-real-order
PYTHONPATH=src nice -n 10 .venv/bin/python scripts/research/draft_decisions_fit.py \
  --real-order --output output/draft-real-order/after.json
PYTHONPATH=src nice -n 10 .venv/bin/python scripts/research/draft_decisions_fit.py \
  --fit-real-order --output output/draft-real-order/fit.json
PYTHONPATH=src nice -n 10 .venv/bin/python scripts/research/draft_decisions_fit.py \
  --time-live-draft --output output/draft-real-order/live-after.json
```

## Resume state

Task scope is draft scouting, GM selection, the research script, draft tests and this report. The code and comparison are in `codex/draft-real-order`. The paired replays, draft and core tests, real-stat scorecard and live timing are complete. Ready for review. Raw measurements are in `output/draft-real-order/`.
