# Overnight report, Nov 17, 2026

**TL;DR**
- Basketball Index capture ran all night with no clicks needed from you. All 664 raw stats for every player-season since 2013-14 are in the project, and the new ratings were rebuilt from them. **With the rebuilt ratings, the sim's game-by-game win probabilities now score as well as the betting market** (Brier 0.1957 vs the market's 0.1962; the old ratings scored 0.2144).
- Fixed a crash that could stop a season mid-sim (AI three-team trades with a pick swap), plus three places where the game showed you numbers the engine doesn't use: draft "potential", the player development chart, and prospect rating markers.
- Diagnosed why top draft prospects "fall" (three separate causes) and audited the development/upside labels. Each needs a short decision from you (listed at the bottom).

Everything below is committed and pushed to both branches. No save dialogs were opened.

## 1. Basketball Index data

- **Leaderboards (the main source):** all 664 stats, 10 at a time, for all 6,804 player-seasons since 2013-14, in raw values. Files land in Downloads, and a background importer moves and imports them automatically.
  - Overnight fixes: the page sometimes ignored a "Run" click (it now re-clicks, and a watchdog kicks it after 4 idle minutes); the importer's file search silently matched nothing in this shell (fixed); one file had blank column titles from a background-tab redraw (the importer now rebuilds them only when the layout matches exactly).
  - I stopped before the optional extra display modes (season percentile/grade/"Value+"). After about 2:20 AM, the browser pane's downloads began landing as hidden temporary files in Downloads (`.Q6L2SF6YDW.com.anthropic.claudefordesktop.*`) instead of finishing. I recovered the data from the page's memory, but stopped rather than risk piling up save prompts. **You may see pending download prompts in the app**; cancel them, since the data is already saved. The hidden temp files in Downloads can be deleted.
- **Fanspo tools:** Value Trends (582 players, 4 time windows) and Shooting Talent daily projections with uncertainty ranges (908 players, about two-thirds of the list). Not captured yet: Player Trends (one player at a time), shot maps, lineups, play-by-play.

## 2. Ratings (Stage 1)

- **Evidence overlay v2:** Basketball Index now feeds tendencies too (what players choose to do), not just skills. Examples: usage, dribble-holding, shot difficulty, the shoot/drive/pass/post mix, catch-and-shoot vs pull-up. Each tendency keeps its existing scale, and Basketball Index only re-ranks players within it. Inputs backed only by weak proxies (like straight-line speed from average tracked speed) move less than ones with direct measures.
- **Fake plateau removed:** about 1,100 old ratings were placeholder 50s for players with no data. They made Jokić, Cade and Wembanyama tie at exactly the same shooting-range value. They're now excluded from the converter.
- **Rebuild results (new-ratings mode, which is still opt-in; normal saves are unchanged):**

  | | Old ratings | New, before BBI | New, with BBI |
  |---|---|---|---|
  | Betting odds: Brier (market 0.1962) | 0.2144 | 0.2038 | **0.1957** |
  | Betting odds: log loss (market 0.574) | 0.632 | 0.601 | **0.580** |
  | Average point-spread miss vs market | 6.63 | 5.46 | **5.08** |
  | Real stats: league metrics in range (of 18) | 12 | 13 | **14** |
  | Real stats: points per 36 error | 2.89 | 3.11 | 2.92 |
  | Real stats: assists per 36 error | 1.11 | 1.08 | 1.26 (worse) |

  - **Top 12 by overall now:** SGA, Cade, Derrick White, Jalen Williams, Haliburton, Luka, Reaves, Curry, Donovan Mitchell, Jokić, Jamal Murray, Kawhi. That's much closer to how analysts rank guards and wings.
  - **Still wrong: big men.** Gobert ranks 324th overall, Sabonis 212th, Giannis 52nd. The overall number averages skills with heavy weight on shooting and creation, gives no weight to rebounding, and its defense number is 60% perimeter mobility and only 40% rim protection. The old hand-set ratings hid this by inflating bigs' perimeter ratings. I tested two formula tweaks (more rim protection in defense, 8% rebounding in overall): Jokić moves to #3, Mobley #11, Davis #47, but Gobert only to #233. A real fix probably means basing the overall number on impact, not a skill average. **Your call.**
  - **Assists got worse** because the sim's assist formula has steep hand-set cutoffs tuned to the old ratings. For example, big men are capped unless their passing is at least 88; Jokić's passing came out 86.4, so his assists halved. This needs an engine retune (tune the engine around the ratings, per your rule), not a ratings change.
  - Three Basketball Index mappings were corrected during the rebuild, because they measured volume instead of skill. Turnover counts are now divided by touches. Pass "execution" no longer uses Basketball Index at all: every available stat ranked Trae Young, Chris Paul and Harden below Gobert. The converter's "scheme IQ" was rebalanced to half offense, half defense, matching how the old rating was defined.
- **Finding for Stage 1:** the trade and contract AI does **not** read the overall rating. It uses its own "on-court value" built from game features. The overall rating drives rotations, free agency, awards and trade wants. So fixing the hidden ratings themselves fixes both at once. See `docs/agents/tasks/s1e-quality-sources-2026-11-17.md`.
- **Experiment:** if the AI's quality numbers used skill-only ratings (no "how often he shoots threes" mixed in), Jokić's offense rank would go from 72nd to 20th. Worth deciding after the rebuild.

## 3. Bugs fixed

- **Too many free throws (every save).** Box scores gave every player about one extra free-throw attempt per game no matter how they play (a biased rounding step), so the league shot 34 free throws per 100 possessions against the NBA's 23. Fixed without changing any game score. After this and a small personal-foul calibration, the real-stats scorecard has **all 18 of 18 league stats in the realistic range** with the new ratings (17 of 18 with the old ones; only true shooting % is slightly high). It was 12 of 18 at the start of the night.

- **Steals and blocks went to the wrong players (every save).** After each game the sim rescales steals, blocks, assists and rebounds to realistic team totals. Leftover units always went to the same players, decided by a fixed alphabetical-ish ID order. Seventeen players, all with first names A–D (Sengun, Podziemski, Gillespie, Bruce Brown, Sexton…), simulated zero steals all season. Fixed. Real-stat error for steals fell by more than half (0.65 → 0.30 per 36 min) and blocks by half (0.59 → 0.28), in both rating modes.

- **Season crash:** an AI three-team trade carrying a pick swap could crash a whole sim day ("Every draft condition must refer to one selected pick"). Reproduced on a real season and fixed. That season now runs through the trade deadline.
- **Draft potential:** for draft classes from 2028 on, the board showed a prospect's secret true potential, while every AI team only sees the public scouting number. "96-potential" prospects then seemed to fall for no reason. The board now shows the same public number the AI uses.
- **Development chart:** "Net growth" showed an estimate about 4 times larger than the real rating change (a young riser +2.6 shown vs +0.6 real). It now shows the engine's real change, and the axis fits the data.
- **Prospect rating bars:** prospect cards drew a made-up "league average 50" marker. They now mark the average for the prospect's position (e.g., the SF/PF average).
- **Draft boards:** prospect injury history, any current injury and projected injury risk are now visible (from the engine's existing medical profiles; nothing invented).

## 4. Decisions for you (short)

0. **Big men and assists (above):** (a) base the overall number on impact, or tweak the skill-average formula; (b) OK to retune the sim's assist formula for the new ratings?

1. **Injured players' ratings (M01):** injuries don't lower displayed ratings at all today. After a return, the sim applies a temporary "rust" penalty in games. Options: (a) a small red "rust" marker with games left, or (b) a computed "effective OVR". I'd recommend (a).
2. **Draft randomness:** top-5 prospects fall past pick 10 about 27% of the time, mostly from stacked random draws. Want a target such as "consensus top 3 rarely (under 5%) fall past 10"?
3. **Draft board rank:** "rank" is just the order prospects were generated, not a grade. Should it become a real public ranking?
4. **Draft-day trades:** a team that trades up gets the player the seller wanted. Should the buyer re-choose? (This changes seeded draft results.)
5. **Development labels (M03):** "Upside remaining" is really a 0–5 market index (0 for everyone 27+), not potential. Proposed renames and tooltips are in `docs/agents/tasks/m03-development-definitions.md`.
6. **Basketball Index renewal:** auto-renews Dec 16. Your call whether to keep it.

## 5. Still to check visually

The new draft-board injury column, the positional markers on prospect cards, the development chart's new scale, and the earlier small GUI fixes (next opponent, S shortcut, lottery grid, playoff stats table).
