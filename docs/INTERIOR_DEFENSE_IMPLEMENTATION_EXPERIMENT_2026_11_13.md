# Interior-defense implementation experiment — November 13, 2026

**Implemented, isolated and default OFF.** New interior inputs now reach a real event-accounted scoring branch. This is introductory mechanism implementation, not final interior-defense calibration against the old offense. No player was tuned to a named rank or OVR. No production inputs, rotations, market policy, GUI or server were changed.

The authority remains `PLAYER_OBJECT_THREE_COLUMN_MAP_2026_11_12.md`. All 94 inputs, 37 capabilities and 22 role/output definitions are preserved. This experiment does not claim those 59 derived objects are complete. The new offense, spacing, creation, passing and remaining defense must be evaluated together before final league calibration.

## Runnable implementation

| Area | Implemented behavior |
|---|---|
| `src/nba_gm_data/interior_defense.py` | Validated scenario compilation; immutable coefficients/profile/context; C27 responses; an interior C32 slice; named C36 readout; explicitly partial R18 reporting. |
| `src/nba_gm_data/interior_game.py` | Possession/attack consumer, points from resolved shots/FTs, coupled blocks/fouls/rebounds, analytic controlled environment and accounting assertions. |
| `src/nba_gm_data/sim.py: sim_game_with_context` | Optional keyword `interior_experiment`, default `None`. One guarded branch after normal availability/minute preparation. Ordinary scoring and RNG remain on the full existing path. |
| `experiments/interior_defense/fixtures.py` | Unnamed synthetic fixtures. No canonical population or save writes. |
| `experiments/interior_defense/consumers.py` | Read-only probes of current on-court value, contract quotes, offer scores and unwired retention. |
| `scripts/run_interior_defense_experiment.py` | Reproducible research/scenario, interaction, game, parity, consumer, timing, attribution and ownership evidence. |

Enable only by explicitly passing an `InteriorExperiment` to `sim_game_with_context`. Every participating team must have an explicit anchor or an explicit no-anchor control; there is no automatic unknown-player fallback. Adding the dormant input section alone cannot activate anything. No app action, environment variable, save flag or GUI enables this mode. There is no global experimental cache.

For example, the synthetic helpers can construct `InteriorExperiment((Anchor('team_a', scenario_profile('team_a_4')),), ('team_b',))`, then pass it as `interior_experiment=` with `game_fixture()` and game ID `interior_fixture`. The script uses current real rosters in two clearly labeled exhibition fixtures, with research scenario inputs, without advancing careers.

## Mechanism and replacement boundary

S36 changes positioning-related travel and contest alignment. P05 supplies dimensional acceleration for travel; a declared recognition delay and opportunity window determine timely arrival. S37 controls a reachable contest. Standing reach P03 plus jump gain P10 determine vertical access, with separately declared P08/P09 capacity controls. Height/span are not added again after the supplied reach. S45 changes legal contest risk, independently of T16's jump/conservative/stay-down mixture.

The response exposes conversion reduction, block probability, foul probability and attempted-shot avoidance. C32 records those responses for rim/short-paint regions plus declared timing/coverage context. The perimeter response is zero for this interior slice. C36 summarizes the same conditional conversion/block response and avoidance; it never feeds back into scoring. R18 has **no overall role grade**: C21 collection, C22 box-out support, full C29 responsibility/communication and full C32 remain unfinished.

The experimental branch replaces the corresponding old interior contribution by bypassing the legacy team-rating score formula, old rim shot-diet suppression/spatial penalty, old block/rebound texture, box variation and post-score reconstruction. It consumes no old `rim_deterrence`, impact, anchor, usage or defensive spatial feature in its scoring weights/probabilities. An exact test changes every legacy rim input to 1 and obtains identical complete experimental results. The old model remains intact when the explicit keyword is absent.

Availability and regulation minutes come from existing game preparation. The branch precedes matchup-specific rotation adjustment; it does not change actual team/user rotations. Anchor exposure is a minute-weighted opportunity approximation, not a tracked five-player lineup. Current fatigue/rust provide an explicitly provisional capacity adjustment; absence gates availability to zero and changed ownership rejects stale deployment. This does not implement P11/P12 physiology or the complete helper family. S38 influences only a declared scenario-delay sensitivity; S39/S40/S41/S44/S46/T15 remain unwired new inputs.

## Attempts and possession accounting

There is no fixed team score to decorate. For each possession, the kernel resolves a turnover or an attack; a prospective rim attack may be redirected; a shooting foul, block, make or miss then follows. Only made field goals and made free throws add points. An unsuccessful shooting-foul attempt has no counted FGA. A block is an opponent FGA miss. A missed field goal or missed final FT creates one rebound opportunity; an offensive rebound creates another attack in that possession. Defensive rebounds end the possession. Assists occur only on made FGs, and steals only on opponent turnovers. Overtime uses the same event path without forcing a winner.

The ledger retains probabilities, expected points before rebounds, shooter, action zone, redirection, shot/foul/block outcomes and rebound ownership. Tests require player/team sums, point identities, 3PM≤FGM, 3PA≤FGA, blocks versus opponent misses, assists versus FGM, steals versus turnovers and complete rebound conservation. No score reconciliation or block normalization follows resolution.

This is a deliberately limited test environment: selected legacy spacing/creation/rim-pressure/passing/OREB features supply offense, attempt ownership and rebound support. There is no complete new C31, passing chain, live assignment model, and-one/bonus/nonshooting-foul system, foul-out rotation response or plus-minus tracking. Baseline shooting-foul volume is low in these fixtures; their scores and FT totals are not evidence of NBA balance. Fixed regulation possession budgets and coarse region/timing responses are experimental controls, not new market or live game policy. Crowded/spaced and strong/weak POA parameters are declared context sensitivities, not proof that those new skill families are implemented.

## Evidence, uncertainty and revisions

Read both the November 12 calibration packet and the November 13 research input packet. The latter preserves 328 explicit unknown source records and eight separate synthetic scenarios. All nine sections validate. **All 96 scenario/player documents compile and retain their exact raw documents**; the incomplete source player documents fail compilation rather than receiving invented defaults. Known reports, scouting judgments, unvalidated reach hypotheses, dimensional fixtures and unknowns remain distinct.

The compiler accepts only explicitly supported scenario metrics/protocols and declared scales. The research fixture contract is opt-in: its force/balance values are synthetic controls, not physical tests inferred from scouting. Their provisional conversion constants are recorded alongside every report. Unknown physical facts do not become observed values or exact 50s. No scenario was written into a player, save or canonical file.

Profiles include input/formula/coefficient revisions. Results distinguish the hypothesis/specification revision from an evaluation revision incorporating consumed offensive inputs, current participation/health and deployed context. Fresh game calls recalculate from those inputs; nothing is retained between games. Returned reports contain private JSON data, not a save or profile object. `consumer-coverage.json` tracks all 94 inputs, with production inactive and the actual experimental reach stated explicitly. Source QA's historical FGM/FGA parser defect was read and left untouched; no historical game-cache shooting fields calibrate this mechanism.

## Actual game changes

Four paired 96-possession exhibition cases use seeds 17/29. “Control” means the **same experimental event environment with no interior anchors**, not the old production simulator. These tiny samples demonstrate causal/accounting reach; they establish no player ordering or calibrated effect magnitude.

| Exhibition / seed | Control score, listed team order | Experimental score |
|---|---:|---:|
| SAS–MIN / 17 | 101–96 | 96–90 |
| SAS–MIN / 29 | 87–94 | 85–94 |
| GSW–BOS / 17 | 93–84 | 89–84 |
| GSW–BOS / 29 | 99–101 | 98–96 |

For SAS–MIN seed 17, rim FGA change 33/43→29/40, makes 44/43→41/39, FT attempts 2/2→2/6, and team rebounds 55/46→60/47. MIN records two blocks while SAS records none; scoring still changes on both sides through avoidance/contests/fouls. Seed 29 has no recorded blocks on either side, yet SAS points change 87→85 and both teams' attempts/fouls change. Blocks are an outcome, not the required route to defensive impact. Full game/attack evidence is retained under the output directory.

## Sensitivity findings and limits

The 32-case matrix varies crowding/spacing, rim versus perimeter threat, POA support, anchor availability and help timing. In one unnamed rim-heavy fixture, crowded/timely coverage changes expected scoring by −6.86 points/100 possessions with weak POA support, versus −15.02 with strong support. Spaced/strong-POA coverage changes it by −7.10; the spaced/weak-POA case has no timely contest and a tiny +0.006 foul cost. These are provisional coefficient/context effects, not estimates of real defensive impact. Drawn-away and sufficiently remote/late defenders have exactly zero effect. A pure perimeter-attack fixture is unchanged. Near-late aggressive arrivals can incur fouls without a useful contest.

The 96 research scenarios, 96 independent ±25% coefficient cases and 24 ±10cm reach cases show why final tuning would be premature. Across eight scenario assumptions, the available-reference expected scoring ranges overlap widely: Wembanyama 99.41–108.07, White 99.70–108.19, Gobert 100.51–108.58 and Curry 101.64–110.24 per 100 controlled possessions. Those are **scenario outcomes, not player forecasts or rankings**. Some high-reach cases saturate the single-release-height access calculation; the prototype does not yet represent the full horizontal/angle/threat coverage distribution. Help at a near-boundary window is highly timing-sensitive, and a shorter window can remove virtually every cohort contest. Nothing was tuned to erase those findings or force a named hierarchy.

The robust findings are narrower: technique and positioning have distinct effects; tools can make a contest unreachable; correct recognition cannot overcome insufficient arrival time; choice and legal execution differ; availability matters; C36 adds no second boost; changed outcomes conserve possessions and points. Relative magnitudes, cohort ordering and league impact are not robust calibration findings.

## Exact consumer reach

`reference_report` exposes raw inputs, conditions, response details, C36 and partial R18 for future presentation and AI use. Ordinary cards/DEF/OVR and live economic builders remain unchanged.

The read-only economic probe replaces only the explicit rim term in `player_on_court_value`, using a clearly arbitrary diagnostic bridge: 50 conditional conversion points prevented/100 reference rim FGA maps to 100. It feeds the resulting value into current contract role/AAV functions and same-offer player/team scores. Legacy impact composites, scarcity, full comps and league-relative plans remain frozen. This bridge is **not** an adopted DEF/R18 scale or a full economic cutover.

For Turner, that diagnostic gives on-court value 59.77→55.72, model AAV $20.06m→$19.28m and a changed same-offer player score. Wembanyama's quote stays capped at $62m despite the changed explicit term. Gobert's quote moves $27.23m→$27.75m while the value falls, because the existing role changes from elite specialist to high-end starter with different multipliers; Zubac shows a similar boundary. These are dependency/legacy-policy findings, not proposed player prices or permission to tune abilities to preserve prices.

All twelve retention scores are unchanged when only the new input section is supplied. This proves retention remains unwired; it is not evidence of correct new-model retention. Actual negotiation actions, trade approvals, settlement, development, prospects and live contract generation are unconverted. No participant approval was bypassed or exercised by these read-only quote probes.

## Verification and cost

**56 focused checks pass**, including 21 new experiment tests, all 16 schema tests and relevant existing defensive/narrative regressions. Eight full real-roster default-off responses match the frozen pre-edit simulator across two exhibitions, two seeds and both existing modes. Separate synthetic differentials also pass. Accounting, overtime, raw-source preservation, protocol errors, health/ownership changes, input/response isolation and snapshot release are covered.

The experiment never reaches app advancement. **No experimental daily/bulk/midpoint career-reload or animation/UI parity is claimed.** Input JSON reconstruction and repeated game-sequence equality pass; those are narrower checks. Ordinary app behavior is protected by the unchanged default path, full result differentials and untouched GUI. Live activation would require the full action/calendar/reload/event tests before release.

Five sequential warm samples, prepared unchanged SAS–MIN inputs:

| Path | Median / range | JSON preparation median |
|---|---:|---:|
| Experimental no-anchor control | 3.15 ms / 3.11–3.21 | 2.00 ms |
| Experimental anchors | 3.84 ms / 3.54–3.98 | 3.83 ms |
| Ordinary default, disabled experiment | 9.00 ms / 8.49–9.20 | 1.03 ms |

Validating/owning/compiling two research scenario profiles separately costs 1.44 ms median over seven short samples. These are local warm engine observations, **not HTTP latency, cold startup, equivalent-outcome speedups or a production performance claim**. The experiment bypasses substantial unimplemented behavior and returns different reports. Profile attribution is separate from these wall samples. An initial prototype spent ~75 diagnostic milliseconds repeatedly decoding IDs; reading two IDs once per game removes that accidental work without a persistent cache. Final profiling has four input-document decodes, with event sampling/RNG setup the largest remaining nested kernel costs. Cumulative rows are not added together.

Eight same-process warm games retain zero of 32 probed result/config/profile roots. RSS spans roughly 297.0→297.3 MiB in the recorded run; traced peak incremental allocations are ~367 KiB. Current traced allocations are ~39 KiB before diagnostic GC and ~18 KiB after, including probe bookkeeping. GC is diagnostic only. This short fixed-input window does not settle whole-server memory behavior or prove long-career stability. No production GC, new global cache, whole-career snapshot or response batch retention was introduced.

Only `sim.py` changes among the fresh tracked pre-existing source/GUI/canonical/approval files, by the optional signature and seven-line guard. All previous optimizations remain. No research output, approved map, coordinator status/backlog, playable save or preview was edited/restarted.

## Reproduction and next boundary

From the repository root:

```sh
PYTHONPATH=src:tests:. .venv/bin/python -m unittest test_interior_defense_experiment test_player_model_schema test_defensive_alignment test_narrative_simulation -v
PYTHONPATH=src:. .venv/bin/python scripts/run_interior_defense_experiment.py --output output/interior-defense-experiment-recheck
```

The runner uses disposable in-memory exhibition contexts, does not write a save or start a server, and needs the retained research packet and frozen reference under `output/interior-defense-experiment-2026-11-13/`. `games.json`, individual ledgers, reference responses, cohort/matrix/coefficient/geometry results, economic probes, timings, profile and memory observations are retained. `verification.json` records source/packet hashes and completed gates. Source protocol/version changes should fail explicitly and receive a reviewed mapping rather than being silently normalized.

Stop here for mechanism review. The next implementation boundary is a **combined opportunity/response experiment** covering new spacing, creation, passing and POA/help/interior defense on the same event accounting, with explicit geometry/arrival/choice responsibilities and no duplicate summary bonuses. Test powerful finishers, rollers/lobs and pull-up threats across lineup spacing and assignments before calibrating this family against real player/league outcomes. Then carry the same reference/profile meanings through complete AI value, contract/negotiation/retention and development consumers, followed by real daily/bulk/reload/event and performance gates. Do not finalize league calibration or force role/OVR ordering from this isolated family.
