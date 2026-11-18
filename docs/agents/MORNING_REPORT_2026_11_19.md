# Morning report: night of Nov 18–19

**TL;DR**
- Coaches now matter rating by rating, players ease back after injuries, and AI teams judge injury risk with the new body-part model. All of it is committed and pushed, and the full test suite passes (1,764 tests).
- Box scores now swing game to game like real NBA box scores. "Playoff performers" are now judged half on real playoff box scores and half on Basketball Index's playoff talent grades.
- New, from your late message: injury risk is now a body map with hotspots (new Health page on the player card). The playmaking and defense heat maps are designed and waiting on your OK.
- Things that need you are listed at the bottom: NCAA sign-in, old Basketball Index files in git history, Codex's aging work and the heat-map plan.

## What changed in the game

1. **Coaching overhaul.** Each head-coach and coordinator rating now has its own effect on the game:
   - Shot quality and spacing design help the offense. Spacing design is worth more with shooters on the roster.
   - Creator usage helps the offense more when the team has a real primary creator.
   - Coverage design, matchup scheming and discipline help the defense. Discipline also lowers foul rates.
   - Player relations gives a small boost on both ends.
   - Game management adds a playoff-only boost.
   - Rotation management lets the coach pick better matchups and ease injured players back carefully.
   - Player development now uses your save's actual head coach (locker room and communication). The game previously used a fixed table.
   - Coach cards only describe effects the game really uses.
   - Codex's staff lifecycle (coaches improve, decline, retire and get poached) is in too.
2. **Coming back from injury.** A player who missed games plays fewer minutes for the next few games. The cut is based on real return patterns: about 16% fewer minutes in the first game back after missing 6–10 games. Good rotation managers bring players back more slowly. Poor ones rush them back.
3. **AI teams and injury risk.** Trade AI now rates injury risk with the new per-body-part model, blended in the first season with Basketball Index's injury forecasts. Anthony Davis-type players now carry the risk they should.
4. **Box-score swings.** Team shooting from game to game now varies as much as in the real NBA (field-goal percentage spread about ±6 points). Possessions and rebounds stayed on target.
5. **Playoff performers** (committed after the odds check passed). The "who raises their game in the playoffs" ratings now use a blend: half real playoff box-score production and half Basketball Index playoff talent grades. Top 10: Jokić, Shai, Luka, LeBron, Mitchell, Tatum, Haliburton, Reaves, Cade, Kawhi. Brunson is still low (65th) because his underlying skill ratings are low, not because of the playoff formula. That is worth a separate look at his ratings with evidence.

## Your late additions (GUI)
- **Injury body map (built).**
  - **Mini figure:** the injury-risk ring on the player card is now a small body figure that keeps the risk number.
    Hovering it gives a one-line summary.
  - **New card page, "Health & Injury Outlook":** front and back body outlines with colored hotspots. Green means lower
    risk than a typical rotation player, pale is about typical, yellow, orange and red are higher, and deep red with a
    pulse marks a current injury. Bigger spots mean more games at stake.
  - **The table beside it:** expected games missed per body part, against a typical player, and injuries there in the
    last 3 years.
  - **Where the numbers come from:** the same per-body-part injury model the season sim uses.
  - **Normal-role minutes:** a benched or injured player is judged at his normal minutes, so his map describes his
    body rather than this week's rotation.
  - **Checked** in the game on Mike Conley (current knee injury) and Jayson Tatum.
- **Playmaking and defense heat maps (design only).** See `docs/agents/tasks/court-heatmaps-design.md`.
  - **The catch:** the season sim doesn't play out individual shots, lineups or defensive assignments. It adjusts team
    shot quality by zone. A true on/off chart would show numbers the game never uses.
  - **Recommendation:** modeled "projected" charts (Playmaking, On-ball D, Help D) sized against Basketball Index's
    real "impact on teammate shot quality" and "impact on opponent shot quality" numbers. The same terms get wired
    into the sim so the charts are honest.
  - **Your question about help defense:** yes, leave out his own matchup's shots, mirroring the playmaking chart.
  - **Needs your OK** because it includes a small engine change.

## Scorecards (after tonight's changes)
- **Real-stat targets:** all 18 league numbers in range, on both rating sets. Pace 102.2, offensive rating 113.2, true shooting .586. One player outlier remains: Jokić averages about 6.5 assists per 36 minutes in the sim against 11.1 in real life.
- **Betting-odds test (100 seasons):** unchanged by tonight's changes. Brier 0.1955 and log loss 0.5786 (before: 0.1954 / 0.5785), still slightly better than the betting market's own 0.1962. Spread error 5.03 points, totals 5.51.
- **Full test suite:** 1,764 tests pass (28 skipped).

## Basketball Index data
- **Captured:**
  - All 664 leaderboard measures
  - Lineup Explorer (61,037 lineups)
  - Lineups and games from the expected-points tools, plus referees and WOWY
  - Team leaderboards
  - Progression (EPM, RAPM, DPM and others by player-season)
  - Growth curves and coach development
  - The full injury tracker
  - 2026–27 minutes and availability projections
  - Playoff talent grades
  - Role Labs
- **Stays on your computer:** everything above lives in git-ignored folders, as you asked. Only fitted game models are committed.
- **Skipped:**
  - Player Profiles, Skills and Career Trends duplicate data we already have.
  - The Similarity tool hung on the server's loading screen. It only compares players' play-type mix, which we can compute from data we already have.
- **NCAA:** blocked on your sign-in (see the queue below).
- **Ideas for the data we don't use yet:** see `docs/agents/DATA_USE_IDEAS_2026_11_19.md`. The top three are lineup chemistry from 61,000 real lineups, player value from several impact metrics instead of one, and realistic draft prospects from NCAA data.

## Fable 5.2 recommendation
Save both resets for now:
1. **One "realism review" once the current overhauls settle.** Give it the scorecards and the player-model docs, and ask where the sim will feel wrong to a Nerd Sesh or Basketball Index viewer, and what evidence would settle each doubt.
2. **The prospect-generator design after the NCAA data is in.** Turning college profiles into NBA prospects and their growth is a hard modeling problem.

## Finding: rotations are too flat (not changed yet)
- **Overall:** the game's starting minutes targets for 2026–27 track Basketball Index's healthy-rotation minutes closely (correlation 0.81 over 329 players).
- **The gap is at the ends:**
  - Stars get about 2 minutes a game fewer than Basketball Index projects.
  - Back-of-rotation players get about 7 more.
  - Some deep-bench players have about 20 minutes in the game against about 5 in Basketball Index's projection: Bruce Brown, Mitchell Robinson, Luke Kennard and Jordan Poole.
- **Some low star numbers are expected:** Kyrie, Lillard and Tatum are coming back from major injuries, while Basketball Index's number assumes a healthy player.
- **Why it matters:** flat minutes blur the difference between stars and role players, which is the point of the player model.
- **Next step:** check the minutes in the two-season test game against these projections and tune the AI coach's rotation shape if they hold. This is a good Codex task.

## Speed note
A month of game time takes about 60–90 seconds in the test builder, which matches the baseline from two days ago. Tonight's runs shared the computer with the test suite and the odds check, so they ran slower. The 10–20 second target is still a separate project, mostly about AI trade-market speed. Nothing tonight made it clearly worse.

## Your queue (in order)
1. **NCAA sign-in.**
   - Sign in at basketball-index.com, a separate site and account from bball-index.com, in the app's browser pane. Then check whether your membership covers NCAA; the page shows its own "Subscribe" button.
   - When signed out, the site shows only a 3-player preview.
   - Once you're in, I can capture all NCAA player and team data in minutes.
2. **Old Basketball Index files in git history.**
   - Before you chose "local only", a few commits pushed Basketball Index-derived tables to GitHub: the normalized leaderboard files, the first tool extraction, and early injury-model files with per-player history.
   - Removing them from GitHub's history means a force-push rewrite, which is destructive.
   - Decide whether to leave them (is the repo private?) or rewrite the history.
3. **Codex's aging work (still running).**
   - Its findings so far: the game starts aging players too late. Basketball Index shows declines starting around 27 and the game around 31.
   - Young rotation players also grow too little, and development years are too similar from player to player.
   - Look over its proposed tuning before I commit it.
4. **Approve the heat-map plan** (route A in `docs/agents/tasks/court-heatmaps-design.md`).
5. **Eight browser-interface tests were already failing** before tonight (stale style-version strings and helpers
   that were renamed). They aren't part of the main test suite. This is a good small Codex cleanup task.
6. **A two-season test game with all of tonight's changes.** Results are in `output/night1118/two_season.log`; I'll report anything it turned up. (The longer test script stops at the draft lottery. That is a known limit of the script, not a game bug.)
