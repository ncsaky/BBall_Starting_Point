# DRAFT-LOTTERY-FIELD: only teams that missed the playoffs enter the draft lottery

Progress: 5/6 - full test suite running on the cloud machines

Owner: Claude (side session, worktree `fervent-antonelli-db66e4`, branch `claude/fervent-antonelli-db66e4`).
Found by SEASON-ALMANAC (item 1 of `docs/agents/tasks/season-almanac.md`).

## TL;DR
- Fixed: the lottery is now exactly the 14 teams that missed the playoffs after the play-in. The 16 playoff teams pick
  15th to 30th, worst record first.
- Seasons where the 16 best records make the playoffs come out the same as before.
- **For you to decide:** the real 2027 draft uses a new 16-team lottery. The game still uses the old one. Under the
  new real rules the Lakers in the example season *would* be in the lottery (with the smallest odds).

## What was wrong and what changed
The game took the 14 worst records and never looked at who made the playoffs. Now, once the play-in is over, the saved
playoff bracket decides who is in.

- `save.py`: `playoff_field_team_ids` reads the 16 first-round teams; `save_standings_for_draft` marks each team.
- `draft.py`: `split_lottery_field` splits the lottery and playoff teams using that mark.
- This covers the May lottery, the draft-room odds preview and the manual reveal. The year-end slides already used
  the real playoff field.
- Unchanged: odds table, draw, second-round order (record order for all 30), pick ownership, protections and swaps
  (they resolve against the new slots).
- Before the play-in is over, or with projected standings, the 14 worst records still stand in, as before.
- Random draws are unchanged. A season only comes out differently when a play-in winner had a worse record than a
  team that missed.
- An order already saved in a career is not redrawn.

## Check on the almanac season (same save, same lottery seed)
The old rule reproduces that run's saved order exactly. With the new rule only two first-round slots change:

| Pick | Before | After |
|---|---|---|
| 4 | Lakers (40-42, playoffs) | Orlando (41-41, missed) |
| 15 | Orlando (41-41, missed) | Lakers (40-42, playoffs) |

## Tests
- New `tests/test_draft_lottery_field.py` (4 tests): play-in winner with a worse record than two eliminated teams,
  over 40 lottery seeds; unchanged order in a normal season; record order before the play-in ends; a protected,
  traded pick resolving on its new slot. Two of them fail under the old rule.

## Decision for you: switch to the real 2027 "3-2-1" lottery?

Source: [NBA announcement, May 28, 2026](https://pr.nba.com/nba-board-of-governors-approves-new-draft-lottery-system-to-address-tanking/).
It applies to the 2027, 2028 and 2029 drafts; 2030 onward is undecided.

### The rules
| Group | Teams | Balls each | Chance at No. 1 each (my arithmetic, 37 balls) |
|---|---|---|---|
| Miss the playoffs and the play-in, except the three worst | 7 | 3 | 8.1% |
| Three worst records ("relegated") | 3 | 2 | 5.4% |
| Play-in 9th and 10th seeds | 4 | 2 | 5.4% |
| Losers of the 7th-vs-8th play-in game | 2 | 1 | 2.7% |

- All 16 lottery picks are drawn. The three worst records can fall no lower than 12th.
- No team's own pick can be No. 1 two years running, or top five three years running (even if traded).
- New trades cannot protect a pick top-12, top-13, top-14 or top-15.
- The league can also cut a team's odds or move its picks as a tanking penalty.

In the almanac season, the Lakers and Charlotte (7th-vs-8th losers who then made the playoffs) would each hold 1
ball, and Orlando, New York, Dallas and Golden State (9th and 10th seeds) would hold 2.

### What it would take
1. **Lottery engine** (`draft.py`, `data/overrides/draft_model_config.json` and the built-in default there): groups
   from records plus play-in results (the save already holds both), 16 drawn picks, the 12th-pick floor, rules
   chosen by draft year, and 14 playoff teams picking 17th to 30th.
2. **Repeat-winner limits:** read earlier years' orders (the save keeps them) and define what happens to a blocked
   team's draw.
3. **Pick protections:** refuse new top-12 to top-15 protections in the trade room, the AI's offers and the
   validation (`pick_rules.py`, `transactions.py`).
4. **Screens:** the draft room assumes 14 teams and four drawn picks (`app_actions.py` `draft_lottery_view`,
   `gui/app.js` lottery cards and footer, `play.py` `print_lottery`, `season_slides.py` `lottery_view`).
5. **AI pick values** (`transactions.py` `future_adjusted_pick_slot` and what uses it): a worse record would no
   longer mean much better odds, so projected pick slots need re-fitting. Trade results will shift.
6. **Tests** that expect 14 lottery teams.

Rough size: one focused session for items 1, 2, 4 and 6; items 3 and 5 are a second one.

Open questions the announcement summary does not settle (the odds sheet it links was not opened): how a blocked
repeat winner is handled, whether 2025 and 2026 results count toward the limits, what applies from 2030, whether
existing protected picks are grandfathered, and tie-breaks. I would skip the penalty powers.

## Follow-up noticed, not fixed
The unattended draft (`save.py` `ensure_draft_processed`, used by command-line quick sim and by a rollover when no
draft was run) ignores the saved lottery order. On the almanac save of June 17, its top 14 did not match the saved
order. The in-game draft room applies the saved order correctly.
