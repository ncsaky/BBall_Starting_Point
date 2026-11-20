# Season slideshows (year-end recap, preseason outlook, continuity graphic)

**TL;DR**
- Two new full-screen slideshows: a 9-slide year-end recap that opens once after the champion screen (before the lottery), and an 8-slide preseason outlook that opens once on Oct 1 (and on a new career's first day). Both can be reopened from Settings or the command palette.
- Awards are now decided when the playoffs end, with four new ones: Finals MVP (from the Finals alone), Sixth Man, Most Improved and three positionless All-NBA teams, all under the real 65-game rule (which the screens already warned about but the old awards ignored).
- Nothing changes game results: the new numbers are counters and summaries of what the sim already produced. Speed cost is about 4 seconds once when the Finals end and about 4 seconds once at the Oct 1 rollover.

Branch: `worktree-agent-a1b83313506b93e39` (committed, not pushed or merged). Outline it implements: `docs/agents/tasks/slideshows-outline.md`.

## What changed

**Engine (`save.py`)**
- Awards move to playoff end: `complete_playoff_champion` calls `generate_league_awards`; the rollover's call finds them and does nothing (it already refused to run twice).
- Each regular-season game now adds four counters to a player's season line (additive fields): games of 20+ minutes, games of 15-20 minutes, games among his team's five highest minutes, games outside them. These feed the 65-game rule and Sixth Man.
- Playoff totals now also keep NBA-Finals-only totals (`nba_finals`). The old "finals" count also counted conference-finals games (their ids contain the word "finals"); it is left as it was and no longer used for the Finals MVP.
- The recap is built when the Finals end (inside the playoff sim paths that know the save file: `advance_save`, `simulate_playoff_round`, `simulate_next_playoff_game`) and stored in `season_slideshows.recaps`; at the rollover it moves into that season's history entry (`season_history[n].recap`). The outlook is built at the end of the rollover. Both builds are wrapped so a failure is logged and can never stop the calendar.
- Home status (`save_status`) gains `season_slideshow`: the slideshow due now (if any) and all that can be reopened.

**New module `season_slides.py`**: the recap and outlook builders, opens-once state, trade and coaching-change ranking, per-stint minutes and the continuity graphic. **New data** `data/canonical/real_season_summary_2025_26.json` (156 KB, built by `scripts/research/build_real_season_summary.py` from the real ESPN box scores already in the repo; the NBA Cup final is left out because it counts in neither standings nor stats): real 2025-26 per-team minutes, records and totals for a new career's first outlook and for Most Improved in the first season.

**App actions (`app_actions.py`, additive)**: `season_slideshow` (returns one slideshow; builds the current season's if the hook has not yet, e.g. a new career's first outlook) and `season_slideshow_seen`.

**Browser**: `gui/season-slideshow.js` + `gui/season-slideshow.css` (new files), a container in `index.html`, and small hooks in `app.js` (open after the champion screen closes or after a sim/load; the first-run tour waits; Settings > Season slideshows; palette "Year-end recap" / "Preseason outlook"). The card reuses the tutorial card's title bar, kicker, arrows and Skip link, at 1180 x 800 over a 90% dark backdrop with the rest of the app made inert. Keys: Right / Enter = next, Left = back, Esc = close; Tab stays inside. Reduced motion: no slide animation (checked: animation name "none" on every slide). Tables use the house values (double header rule, small bold headers, stripes, row hover, sorted-column fill, headshots bottom-aligned). The slideshow does not open by itself in multiplayer sessions (the server would refuse the "seen" write there).

## Award criteria (shown on the awards slide)

The 65-game rule: 65 games of 20+ minutes, plus up to two games of 15-20 minutes (the real rule; the real exception for season-ending injuries is not modelled). Rookie of the Year is exempt, as in the real rule (35 games and 650 minutes, unchanged).

| Award | How it is picked |
|---|---|
| MVP | Unchanged formula: points, assists and rebounds per game, on-court value, team winning percentage, games played. Now under the 65-game rule. |
| Defensive Player | Unchanged formula (defense and rim-protection ratings, effort, screen navigation, blocks, steals, team winning). Now under the 65-game rule. |
| Rookie of the Year | Unchanged. |
| Sixth Man (new) | Must come off the bench in more games than he starts. Box scores do not record starters, so **a game outside his team's five highest minutes counts as off the bench** (defined rule). Then bench scoring first (points x1.0), assists x0.5, rebounds x0.4, on-court value x0.25, team winning. |
| Most Improved (new) | Biggest rise in production per game (points + 0.4 rebounds + 0.7 assists + steals + 0.7 blocks) over last season; needs 25+ games last season and 10+ production now. First season of a new career compares with the real 2025-26 season. |
| All-NBA (new) | 15 players, no positions (as the real vote has been since 2024), ranked by the MVP score: First Team 1-5, Second 6-10, Third 11-15. 65-game rule. |
| Finals MVP (reworked) | The champion's player with the highest total Game Score across the NBA Finals games (Hollinger's Game Score; rebounds count 0.4 each because box scores do not split offensive and defensive rebounds; fouls are not recorded). |

Scratch-save result (seed 17, 2026-27): MVP Jokić, DPOY Wembanyama, ROTY Keaton Wagler, Sixth Man Zach Edey (off the bench in 48 of 77 games), MIP Jalen Smith (14.8 -> 19.0 production), Finals MVP Gilgeous-Alexander (OKC over TOR 4-2).

## Ranking rules

- **Biggest trades (top 3):** two measures from each team's own stored evaluation: value exchanged (sum of what each side received, by its own value) and value swing (sum of how far the deal moved each side, plus or minus). A trade takes the better of its two ranks; ties go to the other rank, then value exchanged. Each side shows what it received, the plain-words reasons stored on the trade, and "after the trade" per-game lines for players with their new team (from the game logs).
- **Biggest coaching changes (top 3):** head coach and coordinator jobs only; a firing is paired with the same team's next hire for that job. Ranked by the league's importance score of the firing plus the hire, then the new coach's grade. Shows the reason, both grades and the head coach's "star workload" style.

## Continuity graphic

Last season's regular-season minutes per team stint, from the player game logs (kept for the current and previous season), so a player traded mid-season counts for each team by the minutes he played there. Green: still on the team; grey: still on the team but out more than 20 games at the start of the season; red: left. The light bar beside it is new arrivals' minutes elsewhere last season (same scale), with a count and how many had no NBA minutes. Sorted by share kept; hover or focus lists the names. A new career uses the real 2025-26 minutes and says so on the slide. Players from the real box scores who are no longer in the league count as gone.

## Slides and screenshots

All screenshots are in `output/slideshows/screenshots/` (not in git), named `<show>-<width>-<NN>-<slide>.png` for widths 1440 x 900 and 1024 x 768, plus a `-1440-reduced-motion-` set. `recap-1440-00-champion-screen.png` shows the champion screen that leads into the recap.

**Year-end recap** (`recap-*`, from the champion checkpoint): 01 champion (champion, Finals result, playoff path, Finals MVP); 02 standings (both conferences, seeds, finish, your team highlighted); 03 awards (five awards with criteria, three All-NBA teams); 04 leaders (points, rebounds, assists, steals, blocks, threes, screen assists; 65-game rule); 05 your season (record, conference place, finish, four team stats with league rank, team MVP with why); 06 trades; 07 coaching changes; 08 top 5 upcoming free agents (ranked by the front offices' expected yearly value); 09 looking ahead (lottery position and odds or draft slot, whose hands your pick is in, consensus top 5, next season's cap).

**Preseason outlook** (`outlook-*` for a second-season Oct 1; `newsave-outlook-*` for a new career): 01 power rankings (Team Signals' overall, change from last season's league-wide finish, one-line roster note); 02 continuity; 03 last season's leaders and award winners, where they play now and their expected role (or injury); 04 your team (coach's planned rotation, Team Signals strengths and weaknesses, cap vs the tax and hard cap, the luxury-tax payout share or tax bill); 05 contracts to watch (your extension-eligible players, biggest expiring deals); 06 prospect watch (consensus top 10, your scouts' rank and coverage, where your pick projects); 07 storylines (biggest move, star in a new uniform, best young group, coach on the hot seat when owner confidence is under 50); 08 the 3 best players expected to miss more than 20 games.

## How it was checked

- Scratch career: new save (seed 17, Warriors, 94-input ratings) simulated through real app actions with `scripts/research/slideshow_scratch_save.py` to the postseason (~9 min), through the playoffs (~1 min) and through the offseason to Oct 1, 2027 (~5 min). Checkpoints in `output/slideshows/checkpoints/`. The fixture `mature2036_seed17` was not usable (no game logs, playoffs or trades in it).
- Browser: each slideshow clicked through end to end with the keyboard (Right arrow and Enter alternately) in headless Chrome (`scripts/research/slideshow_capture.cjs`) at 1440 x 900, 1024 x 768 and 1440 with reduced motion (76 screenshots), plus a manual pass in the app's browser pane at about 800 x 600 (Escape, arrows, Enter, Settings reopen): the recap opened by itself after the champion screen closed; the outlook opened by itself on Oct 1 and on a new career's first day; neither reopened after a reload; both reopened from Settings. On every slide the card fits the window and nothing scrolls sideways; at 1024 the longest slides (standings, awards, trades, power rankings, continuity, leaders revisited) scroll inside the card. Two fixes came out of this pass: the Settings buttons now use one page-level click handler (a re-drawn Settings window had lost them once), and the slideshow's own buttons are no longer greyed out while the game saves the "seen" mark.
- Tests: new `tests/test_season_slides.py` (17: 65-game rule, bench games, Finals-only totals and Finals MVP, Sixth Man, All-NBA eligibility, Rookie exemption, Most Improved, awards once per season, trade ranking, multi-team receipts, coaching-change pairing and ranking, per-stint continuity with a traded player and a rookie, a new save's real 2025-26 minutes, opens-once and reopen-after-rollover) and `tests/season_slideshow.test.cjs` (3: every slide renders, card and keyboard controls, opens-once wiring). Existing: core suite 337 OK (2 skipped); all 31 browser test files 277/277; awards tests in `test_foundation` OK; `test_rollover_history`, `test_schedule_integrity`, `test_postseason_calendar`, `test_playoff_stats_view` OK. One unrelated failure seen in `test_player_lifecycle` (`test_medical_carryover_recovery_and_reload_do_not_reinjure`: `health.py` line 961 uses an undefined name `tuning`); `health.py` is untouched on this branch, so it is pre-existing, likely from the fatigue/rest merges.

## Not checked / limits

- Starters are not recorded by the sim, so Sixth Man uses the top-five-minutes rule. Checked against the real 2025-26 box scores: 81% of real starters are in their team's top five minutes; with the 65-game rule the real season has 8 bench-eligible players by real starts but only 3 by this rule, so the Sixth Man pool is thinner than real (2 players in the scratch season).
- The real 65-game exception for season-ending injuries (62 games) is not modelled.
- Ratings shown on the slides are the same values as the tables and the player finder (engine overall), not the player card's header scale (a known two-scale issue on the board).
- Free-agent "market value" is the contract model's expected yearly salary; rights are described simply (the exclusive re-signing window).
- Multiplayer: slideshows do not auto-open and reopening is refused there.
- Not clicked through on a real 1440 display (headless Chrome at that size instead); not checked in dark mode (the game has none).

## Questions for the user

1. Sixth Man: keep the "outside the top five in minutes" rule, or record starters in the box score (a small sim change owned by the box-score work)?
2. Should the recap open before or after the champion screen? (Now: right after it closes.)
3. The backdrop is 90% dark, so the windows behind are barely visible. Fully opaque instead?
4. All-NBA uses the MVP score. Should defense count more for All-NBA than for MVP?

## Resume state

- Commit on the worktree branch; nothing pushed. Board row SLIDESHOWS set to review.
- Rebuild the real 2025-26 summary: `PYTHONPATH=src .venv/bin/python scripts/research/build_real_season_summary.py`.
- Re-run captures: start a server on a save folder, then `node scripts/research/slideshow_capture.cjs <url> <save.json> output/slideshows/screenshots <label> 1440 900 auto`.
