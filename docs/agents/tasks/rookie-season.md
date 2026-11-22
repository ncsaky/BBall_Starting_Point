# ROOKIE-SEASON: rookies in the simulated season

_Owner: Claude (Opus agent, worktree branch `worktree-agent-a9faafaa376e62df1`). Started 2026-11-22. Status: in progress._

## Objective
1. In-season growth: rookies (and young players) improve through the season like real ones. Measure real first-half
   vs second-half change (2015-2025), split into real improvement vs role/minutes, then reshape when the game hands
   out growth within the year (DEV-CURVE fitted the yearly totals; do not double count).
2. Top rookies' scoring per minute: find what holds it down (usage tendency mapping, coach role, shot creation) and
   fix the engine/mapping, not ratings. Veterans' scoring unchanged (scorecard 18/18).
3. Development minutes: measure top-10 picks' minutes on rebuilding vs contending teams relative to impact; add a
   team-phase development priority to the coach model. Contenders barely change.

## Boundaries
- May edit: `health.py` (monthly growth), coach minutes / rotation code (`save.py` rotation functions,
  `game_minutes.py`), sim usage/scoring for rookies, research scripts, tests.
- Not: `scripts/build_player_inputs.py`, `input_estimator.py`, `data/canonical/` (RATINGS-AUDIT-GSW), `draft.py`,
  `draft_scouting.py` (Codex).
- No Azure. Laptop: max two heavy jobs, `nice -n 10`, check `uptime` (load < 20) before heavy jobs.

## Findings so far
- **Scoring per minute (task 2):** the points fit itself is right for rookies (Acuff raw fit 24.8 per 36 vs real
  24.8) but the shot blend (`box_rates.shot_points_blend`) pulls it down 15-20% because players with no NBA shooting
  record get 2-3 threes per 36 from the old shooting-range formula (Acuff 2.3 vs real 9.3). Fix in
  `offense.offensive_profile`: such players' three volume comes from their inputs (`input_three_volume`: T02 three
  share x attempts implied by the points fit). On veterans with a record: r 0.97 vs 0.81 old. Side effect: the game's
  value of rookies rises ~+0.29 per 100 (+0.9 card overall) because impact_value reads the shot profile and the input
  builder had leveled rookies against the old profile -> builder needs a re-level (RATINGS-AUDIT-GSW owns it).
- **Development minutes (task 3), real:** top-10 picks years 1-2 get +6.8 mpg over a veteran of the same team rank and
  impact on rebuilding teams, +2.2 middle, +1.4 contending (`scripts/research/rookie_dev_minutes.py`). Season-one sim
  already matches on rebuilding teams (+6.8) thanks to the draft-slot opening workload (24 picks 1-5, 18 picks 6-14,
  phase-blind); middle +3.5, contending -2 (n=2). Waiting on a two-season baseline to see year two and made-up draftees.
- **In-season growth (task 1):** first partial real data: rookies' box impact +0.77 first half -> second half (veterans
  +0.04), summer +0.38; sim rookies -0.09. Hook added: `health.INPUTS_IN_SEASON_SHARE` (0.5 = unchanged) and
  `development_month_weight`; set once the full real data is in.

## Resume state
- 2026-11-22 16:30: read reports; Basketball Reference disallows game-log/split pages in robots.txt, so real halves
  come from ESPN's public game-log API (`scripts/research/rookie_halves_fetch.py`, cached in
  `output/rookie-season/espn/`, ~1,670 logs, 3.1 s apart, running in background). `output/rookie-fit-2` is a symlink
  to the main checkout's folder (Basketball Reference season pages).
