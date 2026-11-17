# Released free-agent destination opportunity — November 9, 2026

Implemented the bounded signing correction in `save.py`, preserving the completed narrative correction and all prior performance work. The verified isolated development preview is **http://127.0.0.1:8796/**, PID **73225**, source-manifest revision **`e3972b59c718253acfd4199eec12aa164eb081720f0108430850e4569f63257d`**. A real authenticated dashboard read succeeds at the verified November 1 endpoint. This is a source-manifest identifier, not a Git commit. Startup source/bytecode fingerprints confirm that both fixes are loaded.

Evidence and the fresh pre-edit reference, **including the narrative fix**, are under `output/released-fa-opportunity-2026-11-09/`. Only `src/nba_gm_data/save.py` changes among the recorded production/GUI files. No ratings, intrinsic traits, development, market quotas, thresholds, human rotations, GUI, research data or dependencies changed.

## Cause and implementation

`released_free_agent_destination` formerly compared incumbents given healthy roster projections against an unattached player who retained previous-team MPG. Old opportunity became both extra headline OVR and another retention bonus. A player could clear the unchanged eight-point upgrade gate while earning zero destination minutes.

The new small `released_free_agent_rotation_view` uses existing `ai_role_targets` and the private `ForecastSnapshot` indexes/memos. Every player starts at neutral **24 MPG** for role selection. It then calculates a healthy destination rotation with the actual players/positions and grades expected opportunity:

1. Forecast the destination roster **before** the contemplated cut. Keep the existing low-minute cut eligibility, retention scoring, priorities and deterministic cut tie-break.
2. Forecast that roster **after** replacing the chosen cut with the incoming player. Grade the incoming player at its resulting destination minutes, using the proposed current-season fully guaranteed contract, rather than an old employer's obligation.
3. Compare incoming-after retention against outgoing-before retention. Keep the **8-point** upgrade gate and **8 + remaining waiver cost × .22** gate, plus existing authoritative financial eligibility.

This is still a bounded single-cut comparison, not exploration of every possible replacement. Healthy forecasts preserve the existing protection against cutting an injured starter. Intrinsic skill/upside and priority terms still permit genuine upgrades and useful depth/insurance; no blanket zero-minute or depth-signing ban was added. Hypothetical roles never overwrite real rotations.

Each private review context owns one forecast index and at most one before-roster view per inspected team. Each candidate/team comparison gets one after-roster view. The existing caller discards that owner after every applied signing/cut, so the next candidate sees fresh ownership/contracts. No snapshot enters saves, offers, responses or a global cache. The actual cut/signing continues through the existing waiver and contract ledger paths.

## Before/after counterexample

Financial eligibility is **real**, with the signing salary held at $1.9M in the direct comparison. No financial or settlement mocks are used in the new regression fixtures. Skills, age, positions, roster, contracts and seed stay fixed; only incoming prior MPG changes. Fourteen strong incumbents cover the rotation; incoming and the weak cut candidate have identical 50-valued skills.

| Incoming prior MPG | Before apparent upgrade | Before decision | After projected destination MPG | After upgrade | After decision |
| ---: | ---: | --- | ---: | ---: | --- |
| 0 | -1.371 | Reject | 0 | -0.228 | Reject |
| 30 | 8.929 | Sign/cut | 0 | -0.228 | Reject |
| 42 | 11.029 | Sign/cut | 0 | -0.228 | Reject |

The residual -0.228 is the actual contract-retention difference: the incumbent has two guaranteed years while the proposed incoming deal has one. It is constant across old workloads. Current skill and destination opportunity no longer manufacture an upgrade from past minutes. `counterexample-before/after.json` retain the raw OVR, minutes and retention values.

## Legal integration and deterministic actions

**Eleven new regression tests** cover the counterexample, real upgrades at 0/30/42 old MPG, redundant declines, injury cover without cutting the out starter, development/core priorities, guaranteed cut cost, old-employer contract isolation, input non-mutation, bounded baseline reuse and snapshot release. The initial seven-test set fails against the frozen reference with **five failures**; all final checks pass with the correction.

A full-roster integration fixture invokes the real `process_inseason_released_free_agent_signings` without mocking eligibility, forecast or settlement. A genuine 96-skill upgrade signs at every tested old workload, the weak incumbent is waived, ownership changes correctly and the destination remains at **15 players**. The new contract is fully guaranteed; the outgoing **$3.8M** two-year obligation survives on the waiver/dead-salary ledger. Current cap charges equal old payroll plus the actual new salary, without double-counting the cut. The cut remains on waivers rather than immediately entering the free-agent pool. Repeating resolution adds no duplicate signing/cut. A separate two-signing regression executes both real agreements and distinct cuts, verifies that the second forecast sees the first cut, and confirms two fresh retention owners and a final roster of 15. Human rotation overrides are unchanged.

The existing salary fallback still uses prior minutes; consequently this integration's actual salaries differ between the old-workload cases. Tests calculate and verify those real terms, rather than pretending they are fixed. The separate direct comparison above holds financial facts fixed. Candidate meaningfulness/ordering, salary fallback, generic fit and news proxies are outside this correction; this is not a claim that every use of old MPG was removed from the market.

A real canonical checkpoint replay restores the October 30 career and marks existing pooled **Cam Thomas** available in its disposable fixture. Through normal app actions he signs with **UTA for $15.83M**, which waives **Trey Alexander**. This legitimate signing, salary and cut remain the same before/after; its evaluation score changes **44.15 → 44.41** under the corrected opportunity/contract comparison. The synthetic redundant signing is intentionally lost. Old/new global signing parity is not claimed.

Within the new implementation, **Oct 30 → Nov 1** bulk, daily, and midpoint export/reload all have identical meaningful state, transactions and **16 ordered full progress events**. The real required-cutdown fixture still rejects advancement without changing state or emitting events. Existing tests protect user teams, sequential candidate refresh, contract guarantees, waiver claims/clearance and deterministic phase/deadline stops.

**119 relevant unittest checks pass**, followed by all **11 final opportunity regressions**, including the additional sequential real-settlement case. The relevant suite covers the new tests plus roster retention, contract protection, waivers, free-agency bids, simulation consistency, AI roles and the narrative correction. No pre-existing failures were encountered in this selection. The unrelated rebound-range assertion documented in the prior narrative pass was not rerun or fixed here. Early ownership-test attempts were corrected: recording `Mock` arguments retained the diagnostic context, and an overbroad serialized-string search matched ordinary transaction IDs. The final non-recording weak-reference/key-based test passes without forced GC; those earlier logs remain exploratory evidence, not production leak findings.

## Cost, ownership and limits

Five short sequential uninstrumented three-rejection batches, with fresh inputs and no games:

| Batch | Median | Range |
| --- | ---: | ---: |
| Pre-edit | 2.831 ms | 2.667–4.868 ms |
| Corrected | 6.331 ms | 5.948–12.118 ms |

The correction adds roughly **3.5 ms** in this small fixture; it is not a performance improvement. Separate diagnostic counters show **one** active materialization and **one** healthy retention-context build on both versions. Corrected code adds **four** neutral-role forecasts: one shared destination baseline and one after roster per each of three candidates, not a new league/context rebuild for each candidate. Open roster slots and financially ineligible teams still skip replacement forecasts. The snapshot is bounded by its private owner; weak references release after settlement, and JSON/key checks prove no forecast objects enter the save.

Real corrected action totals are **7.948 / 7.910 / 8.011 s** for bulk/daily/reload (one sample each). The first reference action was **13.546 s**; process warm-up and desktop activity are uncontrolled, and that difference is **not** attributed to this correction. No browser latency, whole-server RSS stabilization, cross-platform or long-season claim is made.

## Preview and reproduction

The previous 8796 process was confirmed as this task's known development server. Fresh socket/thread/stack samples showed only the polling listener and sleeping multiplayer clock; no connected request or simulation worker. It was gracefully replaced with the same binary, port, flags and save directory. Other previews were preserved. Only a new disposable completed career was restored and read; playable careers were not advanced or edited.

`preview.json`, `loaded-backend.json` and `verified-source.json` retain the actual command, PID, full source hashes and in-process function identities. Loaded `save.py` SHA-256 is **`6ea0211d5ea8b881c5304a0d368379d07fe6592d6a3ae1a60fd1ef29ec0ba0e7`**; the loaded `sim.py` still contains the verified prose no-op correction. The startup hook only records identity; it does not instrument requests or decisions. Do not rerun the old-PID refresh script.

Run checks sequentially, using new output labels/directories:

```sh
PYTHONPATH=src:tests .venv/bin/python -m unittest \
  test_released_fa_opportunity test_roster_retention test_contract_protection \
  test_waivers test_free_agency_bids test_simulation_consistency \
  test_ai_roles test_narrative_simulation -v
PYTHONPATH=src:tests .venv/bin/python \
  output/released-fa-opportunity-2026-11-09/counterexample.py --version NEW
PYTHONPATH=src:tests .venv/bin/python \
  output/released-fa-opportunity-2026-11-09/measure.py --version NEW
PYTHONPATH=src:scripts .venv/bin/python \
  output/released-fa-opportunity-2026-11-09/checkpoints.py \
  --version after --output output/released-fa-opportunity-new-checkpoints
```

For old behavior substitute `PYTHONPATH=output/released-fa-opportunity-2026-11-09/reference/src:tests` (or `:scripts` for actions) and a fresh output label/directory. Reference and current code both retain the narrative fix. No full season, broader AI redesign, ratings research/edit, data refresh, packaging or follow-on task was started.
