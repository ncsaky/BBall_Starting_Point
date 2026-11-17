# Overnight report, Nov 17, 2026

**TL;DR**
- All 664 Basketball Index stats (every player-season since 2013-14) are captured, and the new ratings were rebuilt from them. **The sim's game-by-game win probabilities now score as well as the betting market** (Brier 0.196 vs the market's 0.196; the old ratings scored 0.214).
- Fixed four engine problems that affected every save without changing any game score: steals/blocks went to the wrong players, too many free throws, rebounds ignored height, and a foul rate. **All 18 of 18 league stats are now in the realistic range** (was 12 of 18).
- Also fixed: a crash that could stop a season mid-sim, plus three spots where the game showed numbers the engine doesn't use. Six short decisions for you are at the bottom.

Everything is committed and pushed to both branches. Core tests: 329 pass. No save dialogs were opened by me, but see the note in section 1 about possible leftover download prompts.

## 1. Basketball Index data

- **Leaderboards tool:** all 664 stats for all 6,804 player-seasons, in raw values, imported into the project.
  - Fixed along the way: the page sometimes ignored a "Run" click; the auto-importer silently matched no files; one file had blank column titles.
  - I skipped the optional extra display modes (percentile/grade versions of the same stats). From about 2:20 AM, downloads from the app's browser pane started landing as hidden temporary files instead of finishing. I recovered the data from the page's memory, then stopped rather than risk piling up save prompts.
  - **If you see download prompts in the app, cancel them;** the data is already saved. The hidden files `~/Downloads/.Q6L2SF6YDW.com.anthropic.claudefordesktop.*` can be deleted.
- **Fanspo tools:** Value Trends (582 players, 4 time windows) and Shooting Talent projections with uncertainty ranges (908 players, about two-thirds of the list). Not captured: Player Trends, shot maps, lineups, play-by-play.

## 2. New ratings (Stage 1)

What changed in how the 94 inputs are built:
- Basketball Index now feeds tendencies (usage, dribbling, shot difficulty, shoot/drive/pass mix, catch-and-shoot vs pull-up), not just skills. Each keeps its scale; the data only re-ranks players. Weak evidence moves ratings less than direct evidence.
- Three bad evidence choices were corrected because they measured volume, not skill. Turnover counts are now divided by touches. Pass "execution" no longer uses Basketball Index at all (every available stat ranked Trae Young, Chris Paul and Harden below Gobert). Attack recognition no longer uses half-court shot quality, which is mostly dunks.
- The converter from inputs to the 15 hidden ratings now matches how the old ratings were defined for scheme IQ (half offense, half defense) and passing (skill plus passing volume). About 1,100 placeholder "50" ratings no longer distort it.

Scorecards (new ratings are still opt-in; normal new saves use the old ratings):

| | Old ratings | New, start of night | New, now |
|---|---|---|---|
| Betting odds: Brier (market 0.1962) | 0.2144 | 0.2038 | **0.1961** |
| Betting odds: log loss (market 0.574) | 0.632 | 0.601 | **0.580** |
| Point-spread miss vs market | 6.63 | 5.46 | **5.00** |
| League stats in realistic range (of 18) | 12 → **17** now | 13 | **18** |
| Per-player error per 36 min: points | 2.89 | 3.11 | 2.93 |
| rebounds | 1.35 → 1.20 now | 1.24 | 1.24 |
| assists | 1.11 | 1.08 | 1.19 |
| steals | 0.65 → 0.29 now | 0.66 | **0.26** |
| blocks | 0.59 → 0.28 now | 0.63 | **0.33** |
| free throws | 1.63 → 1.20 now | 1.67 | **1.19** |

**Who's on top (new ratings, overall):** SGA, Cade, Derrick White, Jalen Williams, Haliburton, Luka, Reaves, Curry, Mitchell, Jokić, Murray, Kawhi. Script: `scripts/ratings_sniff_report.py`.

**Still wrong (needs your input):**
- **Big men.** Gobert ranks 324th overall, Sabonis 212th, Giannis 52nd.
  - The overall number is a skill average weighted toward shooting and creation, with no rebounding.
  - Its defense part is 60% perimeter mobility and 40% rim protection.
  - The old hand-set ratings hid this by inflating bigs' perimeter ratings.
  - Formula tweaks I tested help only partly (Jokić to #3, Gobert only to #233). A real fix likely means an impact-based overall.
- **Assists for elite passers.** The sim's assist formula has hard cliffs tuned to the old ratings:
  - Big men are capped unless passing is at least 88, so Jokić (86.4) gets 5 per 36 instead of 11.
  - A big bonus switches on above fixed usage and creation lines, so Jamal Murray and Derrick White get 10–12.
  - Smoothing these is engine work I'd like your OK on.

**Finding:** the trade and contract AI uses its own "on-court value" built from game features, not the overall number. Fixing the hidden ratings improves both. Details: `docs/agents/tasks/s1e-quality-sources-2026-11-17.md`.

## 3. Bugs fixed (all saves unless noted)

- **Steals and blocks went to the wrong players.** Leftover units after scaling to team totals always went to the same players in a fixed ID order. 17 players (Sengun, Podziemski, Gillespie, Bruce Brown, Sexton…) simulated zero steals all season.
- **Too many free throws.** A biased rounding step gave every player about one extra attempt per game (34 per 100 possessions vs the NBA's 23). Fixed with game scores provably unchanged.
- **Rebounds ignored height.** Wembanyama got 7 per 36 against 14 real. Now uses a small fit to real rebounding (rebounding rating plus height).
- **Personal fouls** were set slightly low (17.8 vs 19.4 per 100); now matches the NBA.
- **Season crash:** an AI three-team trade with a pick swap could crash a whole sim day. Reproduced and fixed; that season now runs through the deadline.
- **Draft potential:** for 2028+ draft classes the board showed a prospect's secret true potential while the AI used the public number. That made "96-potential" prospects look like they fell for no reason. Now the board shows the public number.
- **Development chart:** "Net growth" showed about 4x the real change (+2.6 shown vs +0.6 real). Now it shows the engine's real change, and the axis fits the data.
- **Prospect rating bars:** prospect cards drew a made-up "league average 50" marker; now they show the average for the prospect's position (e.g. SF/PF).
- **Draft boards** now show prospect injury history, current injury and projected risk (from existing engine data; nothing invented).
- **Tests:** two lost test fixtures were rebuilt as small tracked files (skipped tests 9 → 3).

Checked in the running game: the development card (real ±0.1 changes) and the prospect card's position markers.

## 4. Decisions for you

1. **Big men and assists:** impact-based overall vs tweaking the skill average; OK to retune the assist formula?
2. **Injured players' ratings:** injuries don't lower displayed ratings today; after a return, the sim applies a temporary "rust" penalty. (a) Small red "rust" marker with games left (my pick), or (b) a computed "effective OVR"?
3. **Draft randomness:** top-5 prospects fall past pick 10 about 27% of the time, mostly from stacked random draws. Set a target, e.g. "consensus top 3 fall past 10 under 5%"?
4. **Draft board rank:** it's just generation order, not a grade. Make it a real public ranking?
5. **Draft-day trades:** a team trading up gets the player the seller wanted. Let the buyer re-choose? (Changes seeded draft results.)
6. **Development labels:** "Upside remaining" is a 0–5 market index (0 for everyone 27+), not potential. Proposed renames are in `docs/agents/tasks/m03-development-definitions.md`.

Also: Basketball Index auto-renews Dec 16 (your call), and a long 10-season test fixture (2036 save, ~2 h to build) is still missing.

Full details: `docs/agents/BOARD.md` ("Overnight plan" section) and the reports in `docs/agents/tasks/`.
