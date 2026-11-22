# ROOKIE-FIT: 2026 rookies' starting ratings from college evidence

_Claude Opus agent, worktree branch, 2026-11-21. Status: in progress._

<!-- TLDR -->

## 1. What the evidence says (drafts 2009-2025)

**Data.** Every drafted college player's final college season (Barttorvik tables; 799 players, drafts 2009-2025)
against his first NBA season: Basketball Index LEBRON split into offense and defense (the same impact scale the
game's player value is fitted to) and Basketball Reference box plus-minus and minutes. A player who missed his
whole first season and then played a real one (Griffin, Embiid, Simmons, Holmgren) is judged on that real season.

**Who gets minutes.** Many rookies barely play, so "how good were the rookies who played" flatters late picks. Every
drafted player counts instead: his rookie impact is pulled toward the level of rookies who barely play, more the
fewer minutes he got (a player who never plays sits at that level: -1.5 LEBRON, -3.7 box plus-minus; it takes 750
minutes to count half). Fits on the selected players only are kept in the bundle for comparison (same signs,
larger sizes).

**College inputs.** Box plus-minus split into offense and defense, usage, true shooting, rebound, assist, steal,
block and turnover rates, free-throw rate, three-point share, volume and accuracy (career, shrunk toward typical),
free-throw accuracy, height, age on draft day, team strength (Barttorvik's adjusted efficiency rating), minutes
share, and age x production (offense and defense). Ridge regression; strength picked by leaving one draft out.

**Checks on drafts the fit never saw** (fit 2009-2019, scored on 2020-2025, 274 players; and every draft left
out in turn):

<!-- CHECKS -->

<!-- AGE -->

## 2. How it reaches the game

<!-- METHOD -->

## 3. The 2026 class, before and after

<!-- TABLE -->

## 4. Last season's rookies (2025 class) as a test

<!-- BACKTEST -->

## 5. Gates

<!-- GATES -->

## 6. Files and how to refresh

- `scripts/research/rookie_fit.py`: the fit and the 2026 projections -> `data/research/rookie_translation_2026.json`
  (fit, checks, age tables, each 2026 rookie's college line, skill-evidence profile and projection).
  `--backtest-2025` fits on 2009-2024 only and projects the 2025 class (scratch file in `output/rookie-fit/`).
  `--no-interactions` is the sensitivity run without the age x production terms.
- `scripts/research/rookie_fit_check.py`: `snapshot` (display overall / impact / ranks of every rostered player),
  `table` (2026 class before vs after), `backtest` (2025 class as of its draft, old vs college method).
- `src/nba_gm_data/input_estimator.py`: `load_rookie_college`, `estimate_player_inputs(..., college=...)`, the
  projection as family context (`_projection_context`), `apply_rookie_involvement`.
- `scripts/build_player_inputs.py`: uses the college path for 2026 rookies with a college season.
- `tests/test_rookie_fit.py`.

Sources: Barttorvik player and team tables (barttorvik.com, local raw CSVs); Basketball Index LEBRON by season
(fanspo.com BBI role explorer, cached under `data/research/bbi/captures/fanspo_tools/lebron/`); Basketball Reference
advanced tables and draft pages (`data/research/development_evidence.json`).

## Resume state
- Done: fit + bundle, estimator college path, builder wiring, tests (7 OK), check script.
- Next: rebuild inputs (builder to output/rookie-fit first, diff veterans), snapshots, table, backtest, gates.
