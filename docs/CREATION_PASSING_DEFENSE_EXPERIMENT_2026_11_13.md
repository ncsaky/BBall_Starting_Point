# Creation/passing versus containment/help — November 13, 2026

Milestone 4's bounded backend chain is implemented and verified, **default OFF**, and ready for coordinator review. The shared event kernel now resolves drive → containment → help → read → delivery/receive or finish. F03 roll feeds, F04 lobs and F06 same-side kicks have separate recognition and execution effects. Roll/lob use explicit supplied route contexts; this is not a screen/route/coaching implementation or calibrated NBA gameplay.

All 94 approved input dimensions, 37 derived definitions and 22 role/output definitions remain intact. The authoritative model map, coordinator status document, production ratings, canonical data, app advancement, UI, saves and servers were not changed. No settlement work, live activation, broad research request or long simulation was performed.

## Recovery audit and implementation

The recovery checkpoint and applicable repository-instruction locations were checked before source changes; no AGENTS.md was found. The incoming implementation was treated as unverified. Current-file copies, SHA256 hashes and diffs were captured under `output/creation-passing-defense-2026-11-13/recovery-audit/`. The earlier `interior_game.py`, `offense_response.py`, `shot_geometry.py` and `sim.py` reference artifacts match their recorded pre-edit hashes; current `sim.py` is identical to its reference. The workspace contains extensive unrelated edits; none were restored or rewritten.

The audit found that the partial branch already reached the shared kernel but had no dedicated suite. It granted help openings to unrelated receivers, allowed inconsistent matchups, could credit an interceptor without lane proximity, applied catch losses to self-created shots, omitted receiving preparation effects, and lacked loss/assist/FT ledger reconciliation. Those defects are corrected. An additional availability gate prevents a zero-availability anchor from acting as a helper/interceptor.

| Mechanism | Implemented behavior and boundary |
|---|---|
| Drive and containment | S16 manipulation and S19 driving craft change attack execution time; dimensional P05/P06 movement competes with S33/S34 containment, S41 anticipation and P07 lateral recovery. S17 changes pressure/exposure loss risk, not physical speed or a second finishing bonus. S20 changes decision delay, finish recognition and choice error. This is partial C06/C08/C23, not complete separation/contact/POA defense. |
| Handling security | One explicit handling-loss gate replaces the selected action's generic turnover roll. Pressure, handling exposure and S17 affect it. A handling loss can credit the assigned on-ball defender when S42 is known; unknown S42 disables that credit without inventing a grade. |
| Help and recovery | S38/S44 gate recognition; T15 gates commitment. S39 changes route distance; P05 acceleration and the lower of P06/P07 constrain movement. Notice, commitment and timely arrival remain separate. Actual movement away from an assignment costs that receiver's coverage; flight/catch/preparation time allows recovery. One-to-one supplied matchups must agree with the helper assignment. |
| Reads and choice | Each F03/F04/F06 recognition rating gates its own available window. S20 choice errors, T07 risk and a reset alternative then govern selection. A missed read or bad choice need not be a turnover. A contained drive can pass or reset/re-probe, and does not receive a free interior finish. |
| Delivery | Only the selected family's execution rating controls placement dispersion alongside dimensional distance, pressure and the receiving window. Placement controls accuracy, quality and catch delay; distance controls flight time. Recognition and execution are not averaged. F04 replaces the alternative F03 feed on a selected supplied roll opportunity; the two full talents never stack. |
| Roll and lob | Explicit roll endpoint/window, supplied receiver coverage gap and setup screen displacement create the opportunity. F04 requires sufficient P03 + P10 reach; an expired window before arrival prevents selection, and expiry during the sampled catch delay produces a separately labeled `late_delivery` loss. S12/S13 and existing receiving/finishing responses resolve the available lob. A self-created finish cannot be a self-lob. |
| Receiving and shot | S14 and actual placement affect one catch gate and preparation time. Preparation reuses the existing shooting/contest response. Self-created finishes have reception probability 1. Incoming quality does not create an extra shooting talent. Existing layup/contact/floater/dunk/lob skills, reach geometry, interior contests and FT conversion remain in the same planner/kernel. |
| Disruption and credit | Delivery errors credit only the modeled helper within wingspan distance of the actual pass segment, with known S43. Off-lane or unavailable helpers receive no steal; unknown S43 stays unknown. There is no general interception/deflection engine. Assists require the actual passer, an eligible catch-to-shot window and a made FG. FT points and self-finishes receive no assist. |
| Clock and continuation | Explicit possession/reset/rebound clock controls bound repeated resets. Every loss is charged once; catch failures charge the receiver, placement/timing failures the passer, handling/clock losses the current creator. Offensive rebounds start a new chain with no inherited assist credit. |

The creation path bypasses the old generic turnover gate, gifted paint access, fixed delivery quality, externally fixed POA/help arrival, random assist assignment and automatic rim-avoidance outlet. Defensive contest/avoidance readouts still exist; no second avoidance roll redirects a completed creation decision. C36 remains a readout of the same interior response, with no added game bonus.

## Dedicated verification

Final command:

```sh
PYTHONPATH=src:tests:.:scripts .venv/bin/python -m unittest test_creation_passing test_offense_interior_interaction test_interior_defense_experiment test_player_model_schema test_defensive_alignment test_narrative_simulation test_historical_shooting_parser test_guarantee_research -q
```

**123 tests passed in 5.482 seconds:** 28 dedicated milestone-4 tests plus all 95 prior checks. The final log is `output/creation-passing-defense-2026-11-13/verified/tests.txt`.

The dedicated suite exercises the actual resolver and game entry point. It isolates F03/F04/F06 notice versus execution, craft versus containment, pressure versus security, help recognition versus movement/arrival, abandoned-assignment recovery, delivery distance/quality, receiving preparation, finish skill, risk choice, contained-drive alternatives, late roll delivery, physical lob gates, unknown disruption and unavailable helpers. It distinguishes missed reads, bad choices, handling losses, inaccurate deliveries, late deliveries, catch failures and clock losses. Ledger checks reconcile player/team points, FG/FT, shooting fouls, blocks, rebounds, turnovers, steals and assists; resets create no FGA or rebound.

Revision tests cover input, setup, clock and coefficient changes. JSON input reconstruction reproduces complete results at the Python game boundary. Returned input documents and diagnostic-ledger mutations do not leak into later calls. Conflicting authoritative offense/defense/interaction snapshots, missing dependencies, wrong units/scales, duplicate/stale matchups and inconsistent helper assignments are rejected. Lowering every legacy trait and changing the bypassed fixed controls leaves the new player lines and attack ledger unchanged.

The bounded evidence runner is reproducible offline:

```sh
PYTHONPATH=src:tests:.:scripts .venv/bin/python scripts/run_creation_passing_experiment.py --output output/creation-passing-defense-2026-11-13/verified
```

Use a different `--output` to preserve this retained run. It performs no network calls, app actions, server operations or save writes.

Actual retained results:

- Eight synthetic short games, 16 regulation possessions per team, across seeds 17/29 and all-actions/F03-only/F04-only/F06-only controls. Every requested family, finish and reset is exercised. Handling losses, inaccurate deliveries, catch failures, FGs, shooting fouls and shot-clock losses occur. Sample scores are intentionally uncalibrated and often low; high delivery-loss rates are not accepted NBA balance.
- Four additional near-help games, seeds 17/29, compare commitment 0 versus 1 under the same explicit nearby assignment and movement controls. The committed cases produce 4 and 9 timely-help events; the uncommitted cases produce none. The wider reference geometry has no timely emergency help, so this added fixture prevents a false claim based on an unexercised branch. Separate action tests verify that timely help changes the actual interior finish contest and that leaving an assignment changes kick coverage/shot quality at a relevant preparation boundary.
- Fourteen single-input control games retain the same action kernel and declare participant/axis ownership. These are small mechanism exposures, not estimates of player rank, stable statistical effect sizes or league balance.
- Eight **complete-result exact** default-off comparisons on real SAS/MIN and GSW/BOS rosters, seeds 17/29, both existing modes, against the authenticated pre-milestone `sim.py` reference.
- Eight **complete-result exact** prior interior-only/coupled-mode comparisons, seeds 17/29 and both existing modes, against the pre-milestone event-kernel **and offensive-planner** references (the reference run substitutes the frozen offensive module, rather than sharing the current planner). The dedicated suite adds its own synthetic disabled/prior-mode differentials.

The current entry remains opt-in through `InteriorExperiment.offense` and `CombinedOffense.creation`; both default to `None`. No app caller was wired. Python reconstruction and engine differentials do **not** establish calendar/daily-bulk/career-reload/browser playback/live economic parity for the new gameplay, and none is claimed.

## Research and input ownership

The delivered `CREATION_PASSING_DEFENSE_INPUTS_2026_11_13.md/.json` packet was used unchanged. Its source section and 17 synthetic sections validate. All 17 source-independent synthetic interaction actors compile with their exact declared technique/movement protocols. Their S42/S43 remain unknown; steal attribution is disabled rather than filled. All 12 sparse named-player documents are rejected as complete interaction actors because required action inputs remain unknown. All **964 source unknowns are preserved**; no generic skill values were silently inserted into named players.

The ten-player game fixtures are separately labeled synthetic controls, completed using explicit mechanism assumptions and the prior synthetic shooting/interior fixture. They are not those researched players. No researched range is treated as a measured coefficient, exact success rate or calibrated rank. The skill scale, physical-unit protocols, explicit setup and input revisions remain inspectable in `configuration.json` and `research-scenario-responses.json`.

## Bounded cost and release measurements

Five warm sequential samples on the same prepared ten-player short fixture; tracing and serialization are outside game timing. Game calls **include diagnostic construction and accounting checks**. There is no separately instrumented kernel-without-reports claim.

| Path | Game-call median / range (ms) | Full JSON preparation (ms) | Core-only JSON preparation (ms) | Full / core bytes |
|---|---:|---:|---:|---:|
| Ordinary default | 6.422 / 5.900–6.762 | 0.233 | 0.149 | 7,444 / 7,444 |
| Prior interior only | 0.804 / 0.765–1.017 | 1.007 | 0.106 | 44,358 / 4,981 |
| Prior coupled | 2.995 / 2.898–3.301 | 7.013 | 0.108 | 336,694 / 4,981 |
| Creation/passing | 8.762 / 8.263–8.930 | 7.797 | 0.107 | 375,018 / 4,973 |

Core-only measurement filters diagnostics **before** plain conversion/serialization. Creation diagnostics add 370,045 bytes in this fixture, largely raw-input/spatial reports and detailed ledgers. No live payload reduction is implemented or implied. The ordinary path uses its existing full-game budget; experimental paths use 16 regulation possessions per side. These are local cost observations for different behavior/budgets, not equivalent-outcome speed comparisons, HTTP latency, cold-start or long-season estimates. Samples and exact scope are retained in `timings-and-payload.json`.

Six warm same-process calls create fresh configs, profiles and input snapshots. All **36 probed roots** release before diagnostic GC, with zero live roots in each sample. Traced peak is 1,586,294 bytes (~1.51 MiB), current before final diagnostic GC 65,161 bytes and after 9,001 bytes, including probe bookkeeping. RSS spans 231,424–233,312 KiB (~226.00–227.84 MiB); this short window does not establish long-term server memory stability. No production GC or global experimental cache was added. Evidence is in `memory-release.json`.

## Remaining assumptions and review boundary

Screen effectiveness, legal screen execution, re-screen/slip/roll timing, receiver routes, touch/usage assignment, one-to-one matchups, receiver-defender route gap, rebound support and clock/reset policies remain **explicit experimental setup controls**. No coaching or dynamic five-player rotation/switching engine was added. Partial-minute anchor availability retains the prior exposure-weight convention rather than establishing real on-court lineups. Help is limited to the configured anchor; full weak-side chains, multiple helpers and communication are unimplemented.

F07 cross-court passes are explicitly disabled, including kicks crossing the modeled side boundary. F01/F02/F05/F08/F09 are stored but unconsumed here. S18 separation craft, complete C06/C07/C08/C23–C29/C37, T06 persistence, T14 disruption appetite, full physical/contact decomposition, screen/route inputs and other approved families remain unfinished; none was deleted. Recognition/choice, placement distributions, flight speed, catch-preparation effects and window constants are exploratory. The conservative failed-delivery/catch policy treats these failures as terminal losses; retained deflections/bobbles, offensive/nonshooting fouls, and-ones, full perimeter contests, fatigue workload, plus-minus and foul-out substitutions remain unsupported.

Changed source is confined to `creation_passing.py`, `offense_response.py` and `interior_game.py` relative to the recovery snapshot, plus the new synthetic fixture, suite and runner. The audited incoming `shot_geometry.py` arrival override is retained and covered by prior-mode parity. `source-manifest.json` and the recovery hashes preserve provenance; no unrelated existing source/test/docs file changed outside the two owned report/checkpoint files. The coordinator-owned status file and approved architecture are unchanged.

Stop here for coordinator review. The bounded backend mechanism is ready to review; activation, full-model player/role calibration, app/calendar integration and downstream economic/AI/development validation remain outside this milestone.
