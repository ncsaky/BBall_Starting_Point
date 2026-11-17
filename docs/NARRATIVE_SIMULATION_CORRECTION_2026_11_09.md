# Historical narrative correction and minutes/OVR audit — November 9, 2026

Follow-up status: the separately approved released-free-agent correction is now implemented and verified in [its bounded handoff](RELEASED_FA_OPPORTUNITY_CORRECTION_2026_11_09.md). The diagnosis and pre-edit evidence below remain the record of this earlier pass.

Implemented Task A in `src/nba_gm_data/sim.py`. Historical preseason prose no longer adjusts numerical game features. Task B is diagnosis only: a reproducible stale-minutes asymmetry exists in the released-free-agent retention comparison; it was **not** corrected in this pass. No ratings, development, market/search policy, GUI, packaging or dependencies changed. Preview servers were left running with their existing loaded code; this correction is verified in source/disposable processes, not deployed to a refreshed preview.

Evidence and a frozen pre-edit Python backend are under `output/narrative-correction-2026-11-09/`. All saves used by the probes are disposable restored copies. The original checkpoint hash is checked after each action campaign.

## Cause and correction

The observed real call chain is:

`dispatch_app_action('advance_save') → dispatch_save_action → advance_action → advance_with_checkpoints → advance_save → advance_save_day → load_sim_context → sim_game_with_context → game_team_features → apply_manifesto_feature_adjustments`.

`load_sim_context` reads `Pre-Season manifestos/*.txt` by team abbreviation. The former modifier matched substrings without identifying time, the subject, negation, or conditional language. An affirmative **“lead creator”** mention caused a creator penalty. A hypothetical **“top 10 defense”** caused a defensive bonus. Expectations such as “clear favorites,” “dead last,” added shooting, and prioritizing health modified impact, defense, spacing and stamina. This persisted after roster replacement and into a later-season snapshot.

Both `sandbox-sim` and `replay-real-minutes` reach the shared feature hook. Root-backed playoff simulation also delegates to `sim_game_with_context`; the separate `root=None` deterministic playoff fallback never used this hook. The runtime action probe records a TOR feature call through the actual dispatcher and simulates eight league games on October 31. Before correction, changing only TOR prose changes persisted scores, player box lines and fan confidence. For example, the negative variant changes POR–TOR from **99–130 to 100–128** in this fixture. Some milder variants alter player/stat state without changing the displayed score; exact full state, not just wins, was inspected.

The smallest correction retains both old helper names/signatures as documented no-ops. `apply_manifesto_feature_adjustments` returns the live feature vector unchanged, and `apply_manifesto_expectation_adjustments` mutates neither features nor notes. This prevents old callers from reintroducing the invalid prose interpretation. It adds no cache, tuning system, compensation or team-specific adjustment. Report keys `manifesto_feature_adjustments` remain available and report zero; `manifesto_context` and the write-ups remain intact.

No necessary basketball effect was identified exclusively in the prose layer:

| Removed interpretation | Existing live calculation retained |
| --- | --- |
| Creator/passing/spacing weakness or acquisition bonus | Trait-derived player vectors; current minutes-weighted lineup, top creators and offensive summaries; spatial/offensive-role features |
| Defensive identity/contender bonus | Current defenders, weak links, defensive anchor/rim features and defensive summaries |
| Rebuild/win-expectation strength | Current talent, lineup quality and actual roster depth; a preseason forecast is not another skill measurement |
| Old-age/health stamina drag | Current weighted ages, stamina traits, sandbox availability/fatigue/rust and replacement/dependency checks |

The old keyword layer duplicated or overrode these inputs. Removing it intentionally changes numerical outcomes and downstream career results. No old/new outcome-parity claim is made. Current personnel/health, coaches, rotations, strategy, RNG seeding and normal decision rules retain their calculations.

## Bounded paired games and runtime

One TOR-home matchup, game `401809946`; seeds **17, 29, 41, 53, 67, 79**, identical live inputs within each pair. Each text variant is tested with the same six seeds. Values are sample means, not season predictions or recalibration evidence.

| TOR historical prose | Sandbox mean TOR–opponent before | TOR margin before → after | Replay margin before → after |
| --- | ---: | ---: | ---: |
| Empty/neutral | 124.17–107.33 | 16.83 → 16.83 | 6.33 → 6.33 |
| Shipped TOR text | 124.33–106.67 | 17.67 → 16.83 | 7.17 → 6.33 |
| Positive | 124.83–106.67 | 18.17 → 16.83 | 8.83 → 6.33 |
| Negative | 121.67–108.17 | 13.50 → 16.83 | 7.50 → 6.33 |
| Negated | 123.83–106.50 | 17.33 → 16.83 | 6.83 → 6.33 |
| Hypothetical acquisition | 124.33–106.67 | 17.67 → 16.83 | 7.17 → 6.33 |

After correction **every complete seeded game result**, not merely these averages, equals its neutral-text result in both modes. Replay after correction averages **119.83–113.50**. Tiny samples and seeded discrete score generation do not imply that every old penalty monotonically reduced every score/margin.

The 36 sandbox game calls total **0.421 → 0.421 s**; the 36 replay calls total **0.354 → 0.372 s**, excluding context setup and separately measured feature extraction. This is a correctness pass, with no demonstrated speedup. Setup costs are separately recorded: sandbox **0.600 / 0.550 s**, replay **23.265 / 0.578 s**. The isolated first replay setup outlier is unattributed; it is not claimed as optimization savings. Real one-day dispatcher probes take roughly 1.5–2.3 seconds, with diagnostic wrappers and output serialization outside the clock; they are not a paired performance campaign.

## Regression gates

- Final **five new tests** produce **13 subtest/assertion failures against the frozen pre-edit backend**, then all pass after correction. They cover positive/negative/negated/hypothetical/shipped prose, both sim modes, empty-pool fallback, full roster exchange, changed ages plus a synthetic **2028–29 / January 2029** snapshot, and non-mutation. Live fatigue/rust still lowers impact/creation; improved live shooting/creation changes features and an actual seeded score. A substantial roster change still changes results.
- **45 relevant tests passed** across narrative, simulation calendar/consistency, progress, spatial matchups, human rotations and talent balance. The final enhanced five-test narrative suite then passed independently after its additional mutation/score assertions.
- **12 of 13 selected foundation checks pass before and after.** The existing `test_replay_real_minutes_sim_is_deterministic` passes its repeated-result equality but fails its fixed rebound lower bound: **33 < 35 before, 29 < 35 after**. This pre-existing range assertion was not relaxed or hidden. The numerical change is expected; there are no other failures in that selection. The former foundation assertion expecting prose buffs was changed to assert unchanged features/notes, consistent with the dedicated regression tests.
- Five real one-day app actions with different TOR prose have identical complete meaningful save state, normalized full response and ordered event payloads **after** correction. Before correction the same variants change meaningful state. The complete event **structure/order** (kinds, dates, game IDs) remains unchanged across before/after; numerical payloads may intentionally differ. Only existing disposable response path/dashboard revision metadata is normalized.
- Real dispatcher advancement **Oct 30 → Nov 1**, bulk versus two daily actions versus midpoint export/reload, matches complete meaningful saved state and all **16 ordered events** exactly. It includes normal games, health, monthly development and market work; no AI/animation suppression. Observed action totals are **7.302 / 6.024 / 5.896 s**, one observation per mode, not speed-comparison evidence.
- Real cutdown fixture rejects with “GSW has 16 players. Cut to 15 before opening night.” State/date remain unchanged and zero progress events occur. Existing deterministic tests also cover deadline confirmation and phase stops.

No browser animation implementation changed, and the normal progress listener was used. No full season, data refresh, live career mutation, server restart or external installation was performed.

## Task B — minutes/OVR consumers, read-only findings

`save._uncached_player_attribute_summary` builds engine OVR from current trait categories plus **min(6, MPG / 7)**. With the talent model, the role-sensitive component is blended in, retaining that same workload bonus. `player_display_attribute_summary` subsequently maps it to the presentation scale; the GUI number is not the AI's raw ability input. Established trait-based game `impact` itself has no OVR workload bonus. Workload additionally affects usage and minutes-weighted contribution; these are distinct from intrinsic skill.

| Consumer | Actual dependency and guard |
| --- | --- |
| AI roles / starting five | `reassess_ai_roles` explicitly constructs a **24-MPG neutral skills view** before `ai_role_targets`; priors and an 80/20 target/prior blend provide deliberate inertia. `starting_slot_score` also consumes minutes/OVR where supplied. This audit does not demonstrate an unbounded role-refresh loop. |
| Actual rotations / health | `apply_save_rotation_projection` restores persistent baselines before grading, preventing repeated projections from grading their previous outputs. Human overrides are honored; protected teams do not receive AI reassessment. Unavailability uses zero real minutes while retaining a healthy trade-value projection. |
| Trade forecasts / cuts | `strategic_rotation_view`, `ForecastSnapshot`, oversized-roster `trade_roster.roster_projection` and contract signing-cutdown projections neutralize old team MPG before selecting roles. Expected minutes then legitimately measure destination contribution/retention. The actual healthy projected roster is recomputed; no rewrite is made. |
| Standard trade price | `build_player_asset_valuations → player_feature_vector → player_on_court_value` uses trait impact and basketball features, **not display OVR**. Usage is workload-dependent (9% of base on-court value); development-upside also has a minutes condition. Fallback valuations explicitly use ability/overall/minutes proxies where complete traits are unavailable. These are not proof that display OVR is blindly subtracted twice. |
| Contract market / normal FA | `contract_ai.build_player_contract_market_profiles` uses fresh valuations/features, role tiers and comps; negotiations apply financial/participant rules. Contract-protection roster consideration computes a neutral incoming+incumbent role view. Simple `free_agent_team_score`, salary fallback and auto-fill paths still use old MPG as an expected-contribution proxy. |
| Roster retention | `ai_roster_retention_score = OVR + min(32, MPG) × .20 + age/upside/priority terms`; `roster_retention_context` uses a healthy roster to avoid injury-driven automatic cuts. `roster_cut_score` also combines OVR and MPG for initial roster trimming. Minutes therefore have more than one contribution weight; that alone does not establish an invalid circular ability calculation. |
| Development | `health.advance_development → monthly_trait_delta` reads traits, age, minutes, staff, health and stable prospect capacity/ability/potential. Role factor is bounded and includes a low-minutes practice floor. It does **not** consume headline/display OVR as current talent. No ratings/development change is made. |

### Reproducible comparison defect: released free agents

`save.released_free_agent_destination` compares a free agent against a full team's cut candidate using one `roster_retention_context`. Incumbents receive a healthy team rotation, but the unattached free agent keeps **old MPG**, since it belongs to no team. Consequently the comparison can credit a new player's past opportunity as both higher OVR and another retention term, without checking its role on the destination team.

`ovr_probe.py` builds a full destination with strong two-deep positional coverage and weak deep depth. Only the incoming free agent's old minutes change; traits, age, position, team roster and seed stay fixed. Financial eligibility, cap space and waiver cost are held fixed by explicit diagnostic mocks, isolating the basketball comparison. Actual retention-context and destination functions execute normally.

| Incoming old MPG | Intrinsic impact / shooting / creation / defense | Engine OVR | Retention score | Upgrade over cut candidate | Destination result |
| --- | --- | ---: | ---: | ---: | --- |
| 0 | 50 / 50 / 50 / 50 | 47.0 | 47.0 | 0.0 | Reject |
| 42 | 50 / 50 / 50 / 50 | 53.0 | 59.4 | 12.4 | Select team A |

The incumbent cut candidate has OVR/retention **47.0**, MPG **0**, and the same skill values. The existing strategic forecast gives the incoming player **zero destination minutes** after that cut/signing. Thus the 12.4-point “upgrade” exceeds the 8-point gate solely through stale old opportunity: **6 OVR + 6.4 extra retention credit**. This is a demonstrated comparison/selection defect, not proof of an infinite career loop or a complete legally executed signing under real contracts. It is also distinct from the already protected normal contract-signing counterfactual path.

A follow-up could compare both sides under one hypothetical destination roster, but that changes signing discovery/decisions and is outside Task B. No OVR formula, signing rule, development or rating was edited. The script and exact outputs are retained for a separate bounded correction decision.

## Reproduction / handoff

Use an unused evidence directory or change output names in the scripts; retained action/checkpoint runners intentionally reject existing folders. Frozen reference: `output/narrative-correction-2026-11-09/reference/src`. Reproduction commands (run heavy checks sequentially):

```sh
PYTHONPATH=src:tests .venv/bin/python -m unittest test_narrative_simulation -v
PYTHONPATH=src:tests .venv/bin/python -m unittest \
  test_simulation_consistency test_simulation_progress test_spatial \
  test_user_rotation_roster test_talent_balance -v
PYTHONPATH=src:tests .venv/bin/python output/narrative-correction-2026-11-09/test_selected.py
PYTHONPATH=src:tests .venv/bin/python output/narrative-correction-2026-11-09/probe.py --version NEW
PYTHONPATH=src:tests .venv/bin/python output/narrative-correction-2026-11-09/probe.py --version NEW --mode replay-real-minutes
PYTHONPATH=src:tests .venv/bin/python output/narrative-correction-2026-11-09/ovr_probe.py
```

To test old behavior, substitute `PYTHONPATH=output/narrative-correction-2026-11-09/reference/src:tests` for the current source. `actions.py` and `checkpoints.py` retain the exact real-action restore/dispatch recipes, seed handling, equality assertions and guards. The observer never edits prose files; it substitutes the normal loader return in its disposable process.

`verification.json` records production changes (only `sim.py`), unchanged GUI/write-ups, action/partition parity, intentionally changed results and the source manifests. All prior performance work and unrelated edits are retained. Stop after this correction and read-only audit; no signing correction or follow-on rating pass was begun.
