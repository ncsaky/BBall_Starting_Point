# Real college prospects in the first future drafts (2027-2029)

_Branch: agent worktree `worktree-agent-a422154b21942215f` (Claude subagent, 2026-11-18). Status: **review**. Not pushed._

**TL;DR**
- A new save's 2027 draft now has 47 real college players (8 of the top 10, 25 of the top 30), placed where a model of
  past drafts says they will go. The 2028 class has 11 real players and the 2029 class 6; every other slot is a
  generated prospect, so class size, levels by pick and the position mix stay as before. Drafts after 2029 are unchanged.
- Each real prospect's skills come from his college numbers: free-throw and three-point shooting, usage and
  unassisted scoring, assists, turnovers, blocks, steals and rebounding all point the right way in the new ratings
  (correlation 0.6-0.9 between the college number and the entry skill, except ball security at -0.34 as expected).
- The prospect card shows his college team, conference, class and recruiting grade, his real college seasons and a
  "College Profile" strip (usage, assist and turnover rates, shooting, rebounding, blocks, steals, plus-minus).

## 1. What changed for the player

1. **Real names on the board.** The 2027 class (stored in the starting universe, the same in every save) holds the
   current college players most likely to be drafted in June 2027, e.g. Bruce Branch III (BYU), Tyran Stokes
   (Kansas), Cameron Williams (Duke), Caleb Holt (Arizona), Jason Crowe Jr. (Missouri), Patrick Ngongba (Duke).
   The 2028 and 2029 classes (built per save from its seed) start with players who are too young for 2027 or
   likely to stay in school (Marcus Spears Jr., Joaquim Boumtje Boumtje, Nikola Kusturica; Na'jai Hines in 2029).
2. **Gaps are filled by generated players.** College data cannot see next year's high-school recruits or
   international and G League prospects, so those slots keep the generated prospect made for that slot. That is why
   the 2028 and 2029 top fives are generated.
3. **Same scale as generated prospects.** A real prospect's level and upside come from his projected pick (the
   generator's slot profile), his age (younger = less now, more upside), his college production (box plus-minus,
   offensive rating and minutes move current ability up to about the generator's own spread) and his recruiting
   grade (elite recruits get a little more public upside). The board, AI teams and the card see the same public
   numbers in every save; the hidden upside tail and the scouting miss still differ by save seed, so a real
   prospect can still boom or bust.
4. **No invented medical history** for real players (neutral durability, no injuries).
5. **Card.** Identity line: college team, coach (once coach data lands), draft class. Season line: his real college
   seasons (pick a season from the menu). The invented game logs are replaced by the College Profile strip; the
   strip's tooltip says these are the projected draft-season numbers the game reads his skills from (rule 4).

## 2. Method

**Draft projection** (`scripts/research/real_prospects.py`). College player-seasons 2008-2026 (Barttorvik), one model
per horizon (drafted in this spring's draft, next year's, the year after): a logistic regression for the chance of
being drafted that year and a regression on log pick if drafted. Features: recruit rating (and elite / freshman
interactions), age on draft day (Barttorvik's placeholder 15-October birthdays treated as unknown), class year,
offensive and defensive box plus-minus shrunk by minutes, minutes share, usage, height, team strength (Barthag),
last season's plus-minus and the gain since, block / assist / steal rates, three-point rate, free-throw percentage,
true shooting. The NBA age rule is applied (19 in the draft's calendar year); a draft a player is too young for
passes its chance to the next one.

**Current players.** 2026-27 is 3-6 games old, so each player's level is this season's games blended with last
season (moved forward by the typical one-year change for his class, weighted 0.6 x last season's minutes) or, for
freshmen, the average freshman of his recruiting band (worth about 8 games). Shooting uses career makes and attempts,
shrunk toward typical college shooting (60 free throws, 100 threes). Each player joins the class he is most likely to
be drafted in, only if that chance is at least 15%. Within a class players are ranked by chance x value of the
expected pick; the k-th real player gets the pick the k-th college draftee visible that many years ahead has
historically gone at (2010-2026). The number of real players per class is the model's expected count of drafted
college players for that year, capped by the historical count.

**College to skills.** Final college seasons (plus half the season before) of 230 players drafted 2019-2025 paired
with their current 94 inputs, one small regression per input adjusted for years in the league and draft slot:

| Input (examples) | College numbers | Correlation of the college part |
| --- | --- | ---: |
| Free throws | career FT% | 0.64 |
| Catch-and-shoot / movement threes | 3P%, three rate, threes per 40, FT% | 0.52 / 0.40 |
| Release, range | FT%, 3P%, volume | 0.67 / 0.46 |
| Dribble moves, separation, drives | usage, unassisted rim+mid makes, assists, FT rate | 0.44 / 0.40 / 0.49 |
| Handle security | turnover rate (negative), usage, assists | 0.45 |
| Passing reads and delivery (18 inputs) | assist rate, assist-to-turnover | 0.49-0.64 |
| Offensive / defensive rebounding technique | OREB%, DREB% | 0.62 / 0.21-0.78 |
| Interior positioning, contests | block rate, height | 0.62 / 0.72 |
| Anticipation, on-ball steals, interceptions | steal rate | 0.52-0.60 |
| Dunks, layups, contact finishing, foul drawing | dunks/rim attempts per 40, rim %, FT rate | 0.67 / 0.43 / 0.29 / 0.20 |
| Offensive involvement | usage | 0.28 |

(In-sample fits with 1-4 college terms on 230 players; read them as direction and size, not precision.)

In the game, a drafted real prospect takes the same route into the 94 inputs as generated rookies (the 24 nearest
real players at his level and trait shape), then each college-informed input is blended with its fitted entry value:
weight = 0.2 + 0.5 x the correlation above (at most 0.6) x sample reliability (minutes / (minutes + 300)), so
roughly 30-55%. Blends are eased into 0-100 without clipping. The broad draft traits (shooting, creation, rim
pressure, passing, defense, rim protection, rebounding, feel, athleticism, size, motor, readiness) are standard scores
of weighted college rates against drafted players' final seasons, 16 trait points per standard score (so a real
prospect's traits spread about as much as a generated prospect's: 10 vs 12 points within a player), softly bounded
to 5-95. The older trait ratings use these draft traits through the existing conversion, so both rating sets work.

## 3. Out-of-sample results (fit on drafts up to 2021, scored on 2022-2026)

| Draft | Ranks drafted vs not (AUC) | Rank vs actual pick (Spearman) | Actual top 10 in model's top 10 | Model top 30 drafted / first-rounders | Lottery picks in model's top 20 |
| --- | ---: | ---: | ---: | ---: | ---: |
| Same spring | 0.986 | 0.62 | 5.8 of 10 | 17.6 / 14.8 | 7.8 of 11 |
| One year ahead | 0.92 | 0.31 | 0.8 | 4.4 / 2.8 | 1.0 of 3 |
| Two years ahead | 0.90 | 0.21 | 0.2 | 2.4 / 1.0 | 0.2 of 1.4 |

Per draft (same spring): 2022 Spearman 0.42, 2023 0.58, 2024 0.56, 2025 0.74, 2026 0.79; expected vs actual count of
drafted college players 41/43, 39/46, 41/43, 48/45, 56/53. A "chained" alternative (apply this-spring model to a
projected next season) was worse a year or two ahead (AUC 0.84 / 0.83) and is not used. Who will be drafted two
years from now is genuinely hard to name (many leave early, transfer or stay); that is why the 2028/2029 lists are
short and require a 15% chance.

## 4. Coverage per class

| Class | Real players | in top 10 | top 30 | top 60 | Expected drafted college players (model) | Historical |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| 2027 | 47 | 8 | 25 | 47 | 47.2 | 47.6 |
| 2028 | 11 | 2 | 11 | 11 | 12.1 (among players assigned to 2028) | 31.4 |
| 2029 | 6 | 1 | 6 | 6 | 17.4 (mostly long shots under 15%) | 21.9 |

## 5. Checks

- `tests/test_real_prospects.py` (18 tests): bundle shape and one class per player; out-of-sample and fit directions
  recorded; soft bounds; real players at projected picks with every other slot identical to the generated class;
  same seed same class, real board shared across saves; **2030, 2031, 2036 identical with and without real
  prospects** (both rating sets); prospect-realism shape on mixed classes (ages by pick, position mix, level and
  upside by pick, real and generated at the same scale, scouting misses); college profile shapes draft traits and
  entry 94 inputs (shooters, rim protectors, creators, passers, rebounders, steals; turnovers lower handle security);
  college estimates move inputs toward the fitted value and leave other inputs alone; card payload uses real seasons;
  stored 2027 class and source registration.
- Runs: `tests.test_real_prospects` 18/18; draft, prospect, development, talent, estimator and lifecycle modules
  (19 modules, 178 tests) all pass (`test_draft_year_gate` needs `scripts:tests` on the path); core suite
  `scripts/run_core_tests.sh` 334 OK; draft/prospect/universe tests in `test_foundation` + `test_league_health_audit`:
  one failure, `test_actual_selection_slot_and_team_are_used_instead_of_prospect_rank`, which fails the same way on
  the base commit. `test_hidden_upside` has one failure that also fails on the base commit. Both scorecards not run
  (opening-day ratings unchanged).
- GUI checked in the browser: new save, Upcoming Prospects card lists Branch III / Stokes / Ekezie with college
  logos; his card shows "BYU · 2027 draft class", the real 4-game college season and the College Profile strip.
- Sanity read: `PYTHONPATH=src .venv/bin/python scripts/research/real_prospects_check.py [--year 2028 --seed 1]`.
- Sample, 2027 board (entry 94-input grades; college numbers in the projected draft season):

  | Board | Player | Team | Age | Now / upside | FT% -> FT | 3P% -> C&S 3 | Usage -> creation | AST% -> passing | BLK% -> contests |
  | ---: | --- | --- | ---: | --- | --- | --- | --- | --- | --- |
  | 1 | Bruce Branch III (PF) | BYU | 19 | 61 / 91 | .67 -> 55 | .338 -> 41 | 24 -> 51 | 13 -> 52 | 3.5 -> 52 |
  | 3 | Tyran Stokes (PF/SF) | Kansas | 20 | 61 / 85 | .70 -> 58 | .350 -> 46 | 25 -> 51 | 14 -> 52 | 3.5 -> 50 |
  | 4 | Toni Bryant (C) | Missouri | 19 | 53 / 86 | .72 -> 58 | .362 -> 42 | 19 -> 43 | 12 -> 50 | 4.8 -> 58 |
  | 5 | Jason Crowe Jr (PG/SG) | Missouri | 19 | 53 / 86 | .76 -> 66 | .340 -> 51 | 26 -> 58 | 18 -> 56 | 2.6 -> 42 |
  | 6 | Caleb Holt (SG) | Arizona | 20 | 56 / 83 | .73 -> 64 | .329 -> 47 | 24 -> 57 | 12 -> 55 | 2.8 -> 45 |
  | 8 | Obinna Ekezie Jr. (C/PF) | Louisville | 19 | 54 / 84 | .69 -> 52 | .341 -> 40 | 20 -> 43 | 11 -> 47 | 3.6 -> 59 |
  | 9 | Cameron Williams (C) | Duke | 20 | 58 / 82 | .68 -> 51 | .335 -> 39 | 23 -> 46 | 13 -> 49 | 5.7 -> 67 |
  | 10 | Baba Oladotun (SF/PF) | Maryland | 19 | 51 / 82 | .65 -> 50 | .319 -> 40 | 22 -> 48 | 14 -> 50 | 3.6 -> 51 |
  | 11 | Quentin Coleman (SG/PG) | Illinois | 19 | 55 / 79 | .70 -> 63 | .343 -> 48 | 23 -> 58 | 16 -> 57 | 1.7 -> 40 |
  | 12 | Anthony Thompson (SF/PF) | Ohio St. | 19 | 52 / 78 | .72 -> 56 | .321 -> 43 | 23 -> 46 | 12 -> 49 | 2.9 -> 49 |
  | 13 | Christian Collins (PF) | USC | 20 | 53 / 75 | .70 -> 55 | .332 -> 43 | 23 -> 48 | 14 -> 50 | 4.2 -> 51 |
  | 14 | Patrick Ngongba (C) | Duke | 21 | 55 / 72 | .68 -> 44 | .306 -> 35 | 24 -> 45 | 19 -> 53 | 7.6 -> 69 |
  | 15 | Dylan Mingo (PG/SG) | Baylor | 19 | 51 / 76 | .67 -> 57 | .325 -> 42 | 23 -> 57 | 17 -> 55 | 2.6 -> 41 |
  | 16 | Flory Bidunga (C) | Louisville | 22 | 54 / 73 | .64 -> 41 | .325 -> 32 | 20 -> 45 | 10 -> 49 | 8.4 -> 67 |
  | 17 | Jeremy Fears Jr. (PG) | Michigan St. | 22 | 54 / 73 | .80 -> 69 | .329 -> 54 | 28 -> 57 | 54 -> 69 | 0.2 -> 38 |

  Sanity read: the shot-blocking bigs (Ngongba, Bidunga, Williams) are the best contest grades and the worst
  shooters; the passers (Fears 54% assist rate, Crowe) lead passing; the high-usage guards (Crowe, Holt, Coleman,
  Mingo) lead creation; the best free-throw shooters (Fears, Crowe, Holt) lead shooting. Freshmen with only 4-5
  games still lean on their recruiting band, so their profiles are flatter than seniors' until more games are in.

## 6. Known gaps and open decisions

- **Next year's high-school class and international / G League prospects are not in college data**, so the 2028 and
  2029 top ends are generated. A hand-entered list of top recruits would fill this (no download done here).
- **Coaches**: `data/research/barttorvik/raw/coaches.json` was not there yet. The builder reads it when present
  (fields team, year, coach_name); re-run the builder and `--apply-universe` and the card shows the coach.
- **Stored 2027 class rebuilt.** The 2027 class lives in `data/canonical/universe_2026_27_offseason.json`. It was
  still the pre-prospect-realism generated class; `--apply-universe` rebuilt it with the current generator plus real
  players (only the five draft collections and the new source record change; ~200k-line diff). Existing saves pick
  it up unless they are mid-draft.
- **Class strength for real years**: real players ignore the save's random strong/weak-class draw (they are who they
  are in every save); the draw still shapes the generated slots and the hidden upside tail. An evidence-based
  strength for the real pool (how good this college crop looks vs past ones) is a possible follow-up.
- **Order quirks**: the model ranks partly on four games of 2026-27 data (Branch III ahead of Stokes; Jordan Smith Jr.
  at 31, a 6-2 guard with a slow start). Refreshing later in the season will settle this.
- **Development not re-measured for real rookies.** They enter on the generated scale at their slot, so the
  prospect-realism year-4 bands should hold, but that four-season run was not repeated with real classes.
- `tests/test_hidden_upside.py::test_future_generation_preserves_every_current_trait_and_unaffected_capacity` fails
  on the base commit too (scouting miss vs the old upside check); not touched here.
- Windows packaging copies every `.csv` under `data/`; if `data/research/barttorvik/raw` exists locally on the build
  machine, the raw tables would be bundled (same as other local research data today).

## 7. How to refresh (later in the college season)

```bash
PYTHONPATH=src .venv/bin/python scripts/research/real_prospects.py                    # refit, rewrite the bundle
PYTHONPATH=src .venv/bin/python scripts/research/real_prospects.py --apply-universe   # also rebuild the stored 2027 class
PYTHONPATH=src .venv/bin/python scripts/research/real_prospects_check.py              # sanity read
PYTHONPATH=src .venv/bin/python -m unittest tests.test_real_prospects
```
Needs the local Barttorvik tables (re-download the current season's `players_2027.csv` and
`teams/team_results_2027.csv` first). The bundle carries only derived values. Changing `CURRENT_SEASON` in the
builder rolls the window forward a year.

## Files

- `scripts/research/real_prospects.py` (builder), `scripts/research/real_prospects_check.py` (sanity read)
- `data/canonical/real_prospects.json` (derived bundle, committed)
- `src/nba_gm_data/real_prospects.py` (bundle reader, positions/archetypes, draft traits, 94-input estimates, card)
- `src/nba_gm_data/draft.py` (`generate_draft_class_records(..., real_prospects=True)`, class assembly, real
  prospect records, rookie `college_profile`; mixed classes ranked as a whole; config `real_prospects.enabled`)
- `src/nba_gm_data/input_estimator.py` (college blend for drafted real prospects; involvement on the estimator scale)
- `src/nba_gm_data/app_actions.py`, `prospect_cards.py`, `gui/app.js`, `gui/card-board.css` (card)
- `src/nba_gm_data/ingest.py` (source record), `data/canonical/universe_2026_27_offseason.json` (2027 class)
- `tests/test_real_prospects.py`

## Resume state

Done: builder, bundle, assembly, college-shaped traits and inputs, card, stored 2027 class, tests, this note.
Remaining for the coordinator: review, run both scorecards if wanted (opening-day ratings are unchanged; only
future draftees differ), decide on the open items above.
