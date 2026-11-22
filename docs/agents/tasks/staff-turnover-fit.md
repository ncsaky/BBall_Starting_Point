# AI staff turnover

## TL;DR

- AI teams kept 7 of 9 expiring neutral coordinators across the two-season probe. The starting rules kept 0 of 14.
- Under the new rules, 21% of coordinator slots changed with a returning head coach and 88% with a new one. The NBA bench shares were 17% and 79%.
- Each simulated season had two in-season head-coach firings and four summer firings. The NBA averages were two and just under three.

## Scope and old rules

This work covers AI head coaches, offensive and defensive coordinators, and reviews of the three modeled support roles. The game models front offices as team strategy profiles. General manager and president employment are outside the six modeled staff jobs.

| Decision | Before the fit |
|---|---|
| Calendar and limits | Staff bundle on month changes, February 5, and during training camp, offseason, lottery, draft, re-signing and free agency. Processing allows 8 recommendations per bundle and one firing or direct hire per team/slot/season, with a permanent hire allowed after an interim. Permanent head-coach firing ceilings were 3 in season and 6 cumulatively for the season by summer. The summer recommendation mix aimed for 4 head-coach reviews minus prior firings. The executor skipped the human team. |
| Record and injury context | Estimated win percentage was .25 + contention ceiling ÷ 170, bounded .25–.72. After 20 games, a .12 miss added pressure and a .06 miss added head-coach pressure. Both required fewer than 18 projected minutes currently injured. Skid lookback was 17 games. |
| Shared firing score | Threshold 28 on February 5, September 1, October 1 and in summer phases, 36 otherwise. Interim +32, expired deal +22, grade below 56 +8 and .85 per point below 56, grade below 72 +.20 per point below 72, non-interim grade 86+ −5.5. Security 72+ subtracted up to 7 at .28 per point and security 48 or lower added up to 7 at .32 per point. Underperformance added 8 plus .10 per pressure point above 65. Pressure 76+ added 5. Contenders added 3, rebuilders/developers added 4 for development and scouting, and calendar checkpoints added 3. Non-head slots took −6. A previously fired slot now held by an interim added 9. |
| Head-coach firing score | Underperformance added 9, a .06 miss added 5.5, and 8 losses over at least 12 recent games added .85 per loss, capped at 13, with the injury guard. Ten recent losses added 1.15 per loss, capped at 18, with the same guard. The seasonal review added 8 for missing expectations, below .42 winning percentage, or grade below 72. A second seasonal bonus of 9 applied with fewer than 4 firings/reviews and a miss, below .44 winning percentage, or grade below 74. Ordinary reviews added 5 with fewer than 2 firings/reviews and a .12 miss or 9 recent losses. A grade-82+ head coach lost 8 firing points if a weak coordinator was present and the team had 8 recent losses. With no candidate, firing alone needed another 12 points. |
| Coordinator firing score | Eight losses over at least 12 recent games added 12 if the assistant trailed the head coach by more than 7 and the injury guard cleared. The weaker coordinator picked up another 7 for underperformance or 7 recent losses if their grade was at most 72 and more than 6 below the head coach. |
| Support-staff firing score | Seasonal reviews added 13 for below-target development and 12 each for poor draft return or at least 170 injury games missed. Development needed at least 12 events and positive trait gains below max(1.2, .075 × events). Poor draft return meant every tracked top-20 rookie was below 45 current ability and 66 potential. |
| Market and offers | Considered the first 18 per role. Current grade ≤68 with market grade ≥82 added 10 to firing pressure. A market grade ≥88 with a 7-point upgrade added 8. Current grade ≤76 and an available grade ≥82 with a 6-point upgrade added 5.5. Required an upgrade of 7 for permanent heads or 5 otherwise, eased to 3 for an 82+ candidate replacing a grade ≤68. Candidates could ask up to 108% of the recommendation budget. Ranked by upgrade plus .12 × salary headroom capped at 8, with ±1.5 seeded noise on the recommendation score. Negotiation separately required the authoritative budget, a hiring score ≥−1.5, and 100% of ask or 96% for free agents. A 7-point gain to grade 80+ received a better-replacement reason. |
| Staff pay and term | The team budget ranged from $27M to $47M. Role salaries started at $8M head, $3.4M coordinators, $2.4M development and $2.2M each for scouting and performance, plus $0.12M per grade point above 60 and seeded noise of ±$0.18M. The temporary salary was 35% of the role base for one year. Former employees asked 95% of the calculated salary and new generated candidates asked 108%. The market used two-year offers or three at grade 68+, with new head-coach candidates always asking for three. |
| Contract expiry | Strong grade was 76 for coaches and coordinators, 72 for support. The stable-fit floor was 68 for all roles, with no missed team expectation or unresolved failure. After 30 games, falling more than .10 short of the strategy forecast vetoed retaining a coach/coordinator below 88. A role-specific failure vetoed retention below 82. The offer aimed for the greater of 103.5% of old pay and 97% of the market contract, with budget exceptions only for grade 88+ and room for 96% of old pay. Renewal lasted 2 years or 3 at grade 78+. |
| Career exits and market supply | Annual retirement chance after age 55 was (age − 55)² ÷ 625, with 1.8 percentage points per year after 57 for fired staff, capped at 100%. At 80 it was automatic. The yearly pool intake added at least two per role and targeted a floor of 20 head coaches and 16 per other role. Each refill could promote one coordinator aged 34–59 with grade 70+ and at least eight years of experience. The promotion ranked grade plus seeded noise of ±3. |

Sources and real-world targets are in [NBA staff turnover evidence](staff-turnover-evidence.md) and [the underlying data](../../../data/research/staff_turnover_evidence.json).

## Fitted rules

- Each AI team gets one head-coach review on monthly crossings from November through April once it has played 15 games. The chances per review are 2.4%, 1.8%, 1.1% and 0.6% for gaps below −8, −8 to below −3, −3 through +3, and above +3 wins per 82. The NBA evidence gives the annual rate and typical pace at dismissal. The monthly probabilities are gameplay estimates.
- At rollover, the summer uses the completed regular-season record and the saved preseason forecast. It gives eligible permanent coaches a 14%, 11%, or 4% chance of dismissal for gaps below −3, within ±3, or above +3. The one-change-per-slot rule still applies. A scheduled retirement counts as a head change for bench review. An interim appointed in season has a one-in-three chance of being retained in summer. Head-coach renewals follow the summer decision and an affordable contract.
- Coordinators qualify for renewal at grade 60, or with neutral average skills when personality pulls the overall grade below 60. Renewal uses their role ratings and the staff budget. During the season, a coordinator can still be replaced at grade below 55 after a substantial skid and underperformance, when there is a credible market upgrade. The sample had no reliable role-specific rate for that exception.
- At the end of the year, the chance of changing zero, one or two coordinators is 71% / 24% / 5% under a returning head coach and 8% / 27% / 65% under a different one. Earlier departures, expiring below-bar jobs and upcoming retirements count toward that target. Grades and a seeded tie-break determine which slot moves first. The probabilities represent all assistant departures in the NBA bench sample. The game records a deliberate replacement as a firing.
- Preseason vacancies use existing market candidates and negotiation. A replacement needs an affordable offer and cannot be the just-dismissed incumbent. The new season's staff change allowance opens in full after a preseason vacancy fill. Role-specific support-staff review, natural retirement and the human teams' manual contract decisions keep their existing paths.
- The new rolls use the save seed, season, team and decision name. The career retirement stream retains its draw order. Trade reviews can exit early, so the staff review now runs before those exits. Head and coordinator identities can change how games play out in a career, and future standings and decisions can therefore diverge with the same save seed. The historical 2025–26 replays install the staff for those actual coaching dates.

## Measurement setup

The controlled league probe uses seed 17, the current 94-input ratings, and Golden State as the human team. It runs the standard game simulation for all 1,230 regular-season games per year and verifies 82 games per team. It runs each revision's staff policy at the monthly checkpoints, in summer and at rollover. Coach ratings feed the simulated games. Fixed, healthy player rosters isolate staff decisions from trades, injuries and development. The probe excludes playoffs and uses the same summer checkpoints on each revision.

Opening snapshots use person IDs and compare the same jobs across years. The assistant comparison uses the share of both coordinator slots that changed, grouped by whether the head coach changed. Raw NBA assistant counts come from larger benches. The test counts an interim as a personnel change and tracks open interim slots separately.

Run on starting commit `9e0009b` and the fitted branch, using the same probe scripts on both. The direct commands are:

```sh
env PYTHONPATH=src:scripts nice -n 10 .venv/bin/python scripts/research/staff_turnover_season_probe.py --out output/staff-fit
env PYTHONPATH=src:scripts .venv/bin/python scripts/research/staff_turnover_probe_summary.py output/staff-fit
```

## Two-season results

The seasons are 2026–27 and 2027–28, with 29 AI teams in each run. The NBA head-coach counts cover all 30 clubs in the 17-season evidence sample. The bench comparison uses the comparable 2023–25 NBA sample. [NBA staff turnover evidence](staff-turnover-evidence.md)

| Measure | Before, by season | Fitted, by season | NBA evidence |
|---|---:|---:|---|
| Head coaches fired in season | 3 / 3 | 2 / 2 | 2.0 per season |
| Head coaches fired in summer | 3 / 3 | 4 / 4 | 2.8 per season |
| Coordinator slots that changed by next opening | 1 / 15 | 21 / 21 | The NBA sources group coordinators with the rest of the bench |
| Mean changes in the two coordinator slots, returning head coach | 0.04 / 0.59 | 0.52 / 0.32 | 1.1 on the full bench, or 17% |
| Mean changes in the two coordinator slots, different head coach | 0.00 / 0.29 | 1.50 / 2.00 | 5.5 on the full bench, or 79% |
| Expiring originally neutral coordinators kept | 0 of 14 | 7 of 9 | No role-specific renewal series |

With a returning head coach the pooled coordinator change rate was 14 of 92 slots before and 19 of 90 after. With a different head coach it was 2 of 24 before and 23 of 26 after. The fit increases league-wide coordinator movement and places most of it with incoming coaches. The expiring groups differ because decisions before expiry change who is still in those jobs. The sample is two seasons from one seed. The four summer firings in each season and complete bench turnover under all seven new heads in the second year both ran above the corresponding historical rates.

Development, scouting and performance changed 0 / 1 / 1 positions in the first season on both revisions. Second-year changes in those roles were 5 / 5 / 5 before and 5 / 6 / 5 after. Trainer directories give a proxy for medical continuity, while league-wide development and scouting turnover are largely undocumented. The game models front-office strategy profiles and has no executive employment slots to count.

## Scorecards and tests

Both historical scorecard JSON files matched byte for byte across the two revisions. The real-minutes replay covered 1,230 games and reached all 18 league target bands. The betting replay used seed 1001 and 20 simulations per game. It covered 1,231 games, with market lines on 1,018, and returned a Brier score of 0.2041, log loss of 0.5975, spread error of 4.097 points and totals error of 5.513 points on each revision.

All 37 focused staff and coaching tests passed. The core suite ran 338 tests with two skips on macOS and Azure. The older weak-coordinator test inherited Atlanta's opening-night injury burden, so its fixture now explicitly supplies a healthy team and a non-firing head-coach draw. The updated test passed locally.

The full Azure Python suite ran 2,381 tests with 25 skips, one failure from the old weak-coordinator fixture, and 20 errors from missing data and release assets. The corrected coaching test passed on both macOS and Azure. With the available fixtures in place, the targeted reruns passed six experiment tests, ten Basketball Index estimator tests with one skip, and a second group of 26 experiment and rating tests. Both Windows inventory checks passed in the primary checkout, which has the startup movie and the same packaging code.

Eight experimental classes still stop at setup for the missing archived mixed-possession and expanded-cohort references. The starting commit reproduced all eight setup errors. The archives are outside the staff task. Full-suite and targeted logs are under `output/staff-fit-suite`, `output/staff-fit-retest`, `output/staff-fit-input-fixture` and `output/staff-fit-tests`.

## Resume state

Ready for review on `codex/staff-turnover-fit`. Both controlled probes and both scorecard comparisons are complete. The report, final probe setup and revised test fixture are in the working tree for the coordinator under the current repo rules.
