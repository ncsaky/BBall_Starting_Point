# Offensive Roles V9

Published baseline: `2026-10-27-interior-offense-v9`.

## Scope

This is an offensive role/shot-profile change, not another league-talent pass.
All player records, numeric traits, overall formulas, prospect classes,
development, injuries, contracts and picks are unchanged from V8. The extra
minute-based scoring penalties are deliberately unchanged at the user's request.
Fewer minutes still reduce production through the existing formulas.

The model activates only with canonical `meta.offense_model_version == 1`.
Existing careers remain on their immutable baseline and keep the old behavior.
New saves use V9. No playable save was advanced, overwritten or migrated.
The development server was not restarted. An already-running Python preview
needs a normal restart to load new backend code; do that in the UI chat when
it is idle. A browser refresh alone cannot reload Python modules.

## Components And Evidence

`offense.py` supplies one shared current-ability profile:

- **Post creation:** current rim pressure, versatility, handling and size,
  cautiously informed by available post frequency and efficiency.
- **Assisted finishing:** rim ability, size and mobility, supported by available
  two-point shooting and roll-man evidence. Teammate passing affects allocation.
- **Screening:** a modeled size, scheme-IQ and conditioning proxy. It is not
  measured screen assists, strength testing or film-coded screen-setting skill.
- **Offensive rebounding:** the existing distinct offensive-rebounding skill,
  explicitly included in the offensive contribution profile rather than
  assuming rebounding and post creation are interchangeable.

There are no new potential-driven ratings or additional development bonuses.
Generated players derive the components from their current diverse trait
profiles. Imported evidence is anchored to entry traits; actual growth or
regression changes the profile instead of permanently freezing historical
shooting percentages and style.

NBA samples come from the existing identity-checked ESPN NBA season cache,
restricted to the two completed seasons before the 2026 start. Source URLs,
seasons and trait anchors are frozen in canonical metadata. No network or
filesystem requests occur per player/game to obtain these profiles.

Missing data is not a zero rating. Known zero attempts indicate a nonshooting
role, not 0% latent three-point accuracy. Three-point and two-point percentages
have sample shrinkage; recent volume is weighted by minutes. Historical shots
are not treated as a mandate to reproduce exact box scores in every lineup.

The existing raw play-type snapshot lacks possession counts and sometimes PPP.
Its efficiency influence is capped at 35%, reduced further for short recent
samples; frequency influence is also sample-limited. PPP is not a complete
measure of creation difficulty, passing, matchup quality or role portability.
The component ratings remain estimates, not authoritative scouting grades.

This separation follows [Synergy's play-type definitions](https://support.synergysports.com/support/solutions/articles/77000572558-glossary),
which distinguish post-ups, rolls, cuts and different big-man roles. The numeric
weights are our modeling choices, not weights prescribed by Synergy. Edey's
screening/spacing context is also illustrated in [Michael Pina's film analysis](https://www.theringer.com/2025/04/15/nba/nba-play-in-preview-playoffs-warriors-grizzlies).

## Simulation And Valuation

The old shooting-line branch remains intact for old careers. V9 reconstructs
two-point, three-point and free-throw lines separately while preserving the
already assigned point total exactly. There is no universal three-point attempt
floor. Actual nonshooters stay near zero; generated nonshooters can be true
nonshooters too. Two-point efficiency is no longer a broad total-FG% scalar
that makes an interior finisher look like a low-percentage perimeter shooter.

The same profile informs spatial shot frequency, paint efficiency and spacing.
Very low actual shooting volume cannot keep providing normal perimeter spacing
solely because an old subjective range input was moderate. Finisher/feeder
complementarity, post touches, screening and putback ability affect offense.
These are bounded adjustments to the existing model, not a new possession-level
engine. Generic team offensive-rebounding efficiency bonuses were not doubled;
existing possession-extension/rebound behavior remains.

OFF adds a bounded interior-contribution blend to the older shooting/creation
summary, weighted by size/role and shooting volume. It does not simply give all
centers a high offense grade. Overall is unchanged. AI on-court valuation gets
a bounded marginal component for post, finishing, screening and offensive
rebounding, while retaining contract, age, health, fit and scarcity consumers.
Correcting falsely implied spacing can offset extra interior credit.

Player-card/league payloads expose the shared OFF value and separate component
ratings. Team signals consume the new offensive contribution. Frontend files
were initially left to the concurrent UI chat; the completed follow-up is below.

## Controlled Results

Each row holds teammates fixed, target at 30 minutes, and team scoring at 114
points; 256 seeded trials. These are role tests, not a prediction that a player
must reproduce these numbers on his real team. The earlier headline OFF is the
35/32/18/15 derived formula; legacy UI paths used other formulas in some places.

| Player | OFF Before / After | 3PA Before / After | FG% Before / After |
| --- | ---: | ---: | ---: |
| Edey | 61.5 / 70.9 | 2.92 / 0.92 | 42.2 / 58.1 |
| Allen | 71.1 / 75.4 | 3.42 / 0.11 | 42.3 / 63.6 |
| Gobert | 68.8 / 77.5 | 3.31 / 0.02 | 42.3 / 65.0 |
| Zubac | 74.3 / 80.6 | 3.51 / 0.01 | 42.9 / 60.0 |
| Ayton | 53.8 / 65.2 | 2.31 / 0.19 | 43.9 / 62.1 |
| Sengun | 83.5 / 85.1 | 3.86 / 1.51 | 43.4 / 51.2 |
| Jokic | 94.5 / 95.5 | 5.36 / 3.93 | 47.4 / 57.8 |
| Turner | 64.7 / 66.2 | 4.90 / 5.54 | 42.1 / 45.6 |

The first candidate gave finishers too much extra scoring credit. Before
publication, that was reduced to a smaller correction around their existing
rim-pressure benefit, with bounded feeding/post/putback differences. The final
Edey probe scores about 14.0 points versus 12.7 before; Gobert 14.3 versus 13.1;
Jokic remains about 29.1. This is not a blanket removal of creation limitations.

In two real seven-day windows, league team FG% is about 46.6-46.7%, FGA about
85, 3PA about 31.5 and PPG about 115-116. These short windows do not establish
full-season calibration. FTA is still high at about 29.5 per team-game; the
fixed-point shooting architecture and its free-throw/parity handling remain a
separate limitation, not a claimed completed fix.

## Verification

- 408 replayed games across two seeds, including a month boundary.
- Daily versus bulk and exported/restored midway produce identical meaningful
  state, including scores, health, transactions, rosters and development.
- Repeating a request at the reached date produces no extra activity.
- V8 career replay through V8 and V9 entry points is identical.
- Frozen legacy player features, attributes, all asset valuations and nine
  player-line samples match exactly. Forty-eight legacy team simulations match
  the pre-change simulator exactly.
- The broad focused run passed 110 tests. Additional targeted tests cover the
  corrected replay guard and actual generated-class diversity without changing
  generated overall ratings.
- Existing saved careers and older baseline archive bytes were unchanged.
  The registry was extended only to register the new baseline.
- No new multi-season runs, no server interruption, no release packaging.

The first replay attempt stopped on a test-harness issue: its old file-access
guard treated SQLite `file:` URIs as workspace-relative paths. The failed
attempt was preserved. The scoped verification script now uses a proper URL
parser for that guard, and all successful replays used identical game-model
inputs. This was not a save corruption or gameplay failure.

Artifacts in `output/interior-offense-v9-2026-10-27` include
`controlled-review-final.json`, `gameplay-shot-totals.json`, `verification.json`,
`publication.json`, and the frozen legacy golden results. The disposable replay
runtime remains under `~/.cache/nba-gm-audits/interior-offense-v9-2026-10-27`.

## UI Handoff

No redesign is required to consume the data. New player-card `ratings` keys:
`offense`, `post_creation`, `assisted_finishing`, `screening`,
`offensive_rebounding`. Existing `oreb` remains the same underlying rebounding
skill. Matching quartiles and league means are provided. The payload also has
`offensive_contributions`, containing labeled, explicitly modeled ratings.

The follow-up now adds Post creation, Assisted finishing and Screening through
the existing rating-bar renderer. Offensive rebounding stays a single bar.
The three columns contain 8/8/11 rows: Offense, Defense (including athleticism),
then Interior & Rebounding plus Mind, Body & Coach. Existing artwork is retained.
No CSS, bar size, row height, font, spacing, card dimensions or page count changed.
Old payloads retain their original arrangement; scouting locks remain intact.
`rating(row, 'offense')` now prefers explicit OFF before the legacy fallback.

Five focused JavaScript tests pass. Real Chromium renders at 1647x1000,
1440x900, 1024x768 and 390x844 verify no ratings-page scrolling and identical
existing bar geometry, fills and league-average markers. Evidence and screenshots
are in `output/player-ratings-v9-ui`; the checker renders real UI code and styles
with a read-only V9 player fixture, without loading or changing playable saves.
The older `player_pages.test.cjs` harness already failed before this edit because
its broad source slice executes a document listener without a DOM; it is not
being presented as passing or repaired by this focused change.

Next balance step: test contrasting lineups/AI decisions and more specialist
types using fast controlled games. Do not infer a need for another rookie
nerf, new star quota or long daytime season batch from these changes alone.
