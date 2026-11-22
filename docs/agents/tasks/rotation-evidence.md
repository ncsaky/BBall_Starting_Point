# NBA rotation and in-game decision evidence, 2023–26

## Resume state

Research for the Stage 2 coach. Fit on 2023–24 and 2024–25 and reserve 2025–26 for testing. Cover regular-season and playoff rotations, game state, timeouts, end-game tactics and named coaching differences. Engine, interface and tests are outside scope.

The repository has 2025–26 regular-season box scores but no tracked substitution feed. The worktree is on `codex/rotation-evidence` with the main checkout's Python environment linked. Next, confirm a public bulk event archive and validate its floor time against independent box scores.

### Rotation checkpoint

The NBA play-by-play archive publishes six season files with five-player lineups at each event. Cached the six files under `output/rotation-evidence/`. The first build passing clock and floor checks contains 3,939 games. One 2023–24 regular-season game failed the clock-order check. The 2025–26 comparison with the repo’s ESPN boxes matched 27,295 player-games. All matched starters and minutes were within the one-minute check, and four personal foul totals differed. One score mismatch and unmatched game dates remain to investigate.

The first build contains stints, first rest and return, minutes by quarter, close and lopsided rotation depth, playoff top-eight minutes and back-to-back comparisons. Opening-stint and first-rest rules have been scored against 2025–26. Next add coach decisions, end-game opportunities and league-wide coach comparisons.

### Game-state checkpoint

Added foul trouble around the actual whistle and permanent fourth-quarter starter exits, with lead, deficit and clock kept separate. A second foul in the first quarter and a third before halftime show a substantial jump in benching. The data include the chance of an immediate exit, bench time if the player returns, and no-return cases. Box-score matching recovers 39 playoff games by matching the exact score and teams one date later.

### Timeout checkpoint

Measured roughly 5.5 logged timeouts per team in a regular-season game. About one in five scoreless runs drew an immediate timeout when the opponent first reached six, eight or ten points. The next scorer was about as likely to stop the run in the games where a timeout was called as in those where play continued. This is a comparison of observed decisions and is affected by when coaches choose to call timeouts.
