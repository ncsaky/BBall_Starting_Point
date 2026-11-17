# Isolated compiled role-DP experiment — November 2, 2026

**Recommendation: NO-GO for production integration as the next material latency improvement.** Native execution works for this bounded kernel and saves **0.408 seconds / 2.73%** between three-sample backend action medians. This is a real, packing-inclusive gain, not a multi-second solution. The remaining cross-platform, frozen-app and sanitizer work is disproportionate to this kernel's measured ceiling. A smaller optional acceleration could be reconsidered separately; no production integration is authorized or implemented here. This experiment does not establish a result for other kernels.

All code, source, binary and evidence are under `output/compiled-hotpath-experiment/`. All **67 pre-edit production/canonical hashes remain identical**. No `src`, public API, GUI, canonical data, policy, quota, RNG, animation, runtime dependency or preview was changed. Playable source saves were preserved. No other chat was asked to stop or provide a research probe.

## Boundary and measured budget

The preceding [algorithm design](SIMULATION_ALGORITHM_DESIGN_2026_11_02.md) measured 1.171 seconds inclusive for all role assignments, within a 14.709-second diagnostic action. That was already a small ceiling. The compiled experiment selects only the **five-slot exact assignment DP**, inside `save.ai_role_targets`, rather than porting roster construction, features, contract/pick logic or participant approval.

A separate real-action audit measured all **1,074 role calls**, comparing native and current Python intermediate/final results:

| Reference role work | Diagnostic seconds |
| --- | ---: |
| Attribute extraction | 0.408 |
| Positional score construction | 0.249 |
| DP updates | **0.490** |
| Whole role function, inclusive | 1.205 |

These are nested attribution, not additive to whole-action clocks. The remaining role work includes ordering and minutes allocation. The complete DP budget is approximately **3.3% of the measured current action**, even if its replacement were free. Native numeric packing **0.0211 s**, FFI/computation **0.0119 s**, and numeric output reconstruction **0.0035 s** total **0.0365 s** over 2,148 group calls. That excludes outer Python validation/orchestration, which remains included in the wall comparisons below. The audit executes both implementations and is not a timing baseline.

The C input is an ordered `n × 5` binary64 score matrix. Outputs are five int32 row indexes, the winning score and mask. Python retains fresh feature extraction, both original positional-scoring passes, quality arithmetic, player ordering, the second-group removal rule, minutes/rounding and all safeguards. **No invariant-score hoisting was mixed into the native action experiment.** Health, plans, wants, pending terms and authoritative settlement decisions stay on their existing paths. No search approval is reused.

The C implementation snapshots each player's prior states, retains mask insertion order, uses strict `>` updates and performs the same ordered double additions. It uses about 2 KiB of stack, no heap allocation, global mutable state or retained input pointer. The adapter makes two synchronous `ctypes.PyDLL` calls per role function, retaining the GIL. Inputs above the prototype's 128-row limit use the full current Python implementation.

## Net measurements

One existing busy seed-17 fixture, February 3–4, was restored outside each timer through the existing disposable export/restore runner. Three sequential pairs alternate order: Python/native, native/Python, Python/native. These are **real backend app-dispatch actions**, including computation/persistence/response preparation, not HTTP/browser/playback timings. No profiler or stage clocks run in these samples. Initial library load/build is reported separately. No season study or worker pool was used.

| Backend | Median seconds | Range |
| --- | ---: | ---: |
| Current optimized production Python | **14.938** | 14.937–15.090 |
| Test-only native DP adapter | **14.530** | 14.409–14.584 |

Difference between medians: **0.408 s / 2.73%**. Individual paired savings: **0.354, 0.529, 0.559 s**, median 0.529 s. This small sample establishes a modest benefit on this fixture, not a universal platform/workload guarantee. Its scale agrees with the ~0.490-second DP budget. None of the market/settlement profile's larger overlapping totals is claimed as native saving.

A separate fresh-input microbenchmark includes input copying, captured-attribute lookup/copy, score generation, packing, FFI and minutes/output reconstruction. It does not repeat a cached solver result: each call owns new inputs and there is no native result cache. Actual canonical attribute extraction is omitted equally for all micro variants; it remains in the real actions.

| 248 diverse calls per sample, five alternating samples | Median seconds | Range |
| --- | ---: | ---: |
| Current Python role function | 0.2427 | 0.2397–0.2537 |
| Prior dense Python prototype, secondary comparison | 0.1838 | 0.1828–0.1862 |
| Native DP, retaining both scoring passes | 0.1319 | 0.1306–0.1335 |

The large micro percentage extrapolates to only ~0.480 seconds over 1,074 calls. The actual action results above take precedence. The secondary dense prototype is not the production baseline and also hoists invariant scores; its entire micro saving is not attributable to compilation.

Build took **0.097 s** on the installed toolchain. First observed dylib load took **0.595 s**; subsequent fresh-process observations were about **0.00085–0.00167 s**. The first observation was not reproduced with artificial cache purging and is not called a universal penalty. It could offset the first action's saving if loading were deferred into that action. Build/load is excluded from already-loaded action timings, not hidden inside a speedup claim.

## Exactness, ownership and limits

- **71 roster cases:** 31 captured real cases plus ties, adjacent floats, empty/short/oversized/center-heavy rosters, malformed inputs, NaN and infinity. Captured membership includes 19 injury-tagged cases, seven oversized cases and a human team's hypothetical forecast. Both matching exception types/messages are checked for the two malformed cases.
- **90 numeric group cases / 702 prefix-winner checks:** compare masks, assignments and IEEE double bits, including signed zero, subnormals, extreme finite values, overflow, infinities and distinct quiet-NaN payloads. Full groups/final minutes match. Invalid FFI sizes/pointers fail before output writes; the full >128-player fallback matches.
- **96 captured participant evaluations** match completely, including 46 pending-pick-state cases and 13 swap asset occurrences; ten involve human teams. This preserves the captured roster/pick-investment/acceptance outcomes. It is finite sampled coverage, not a full settlement/cross-platform certification.
- Actual role-commit test matches for **28 AI teams**, while human GSW and explicit-override ATL retain all **30 protected player baselines**. Neither protected team enters the native kernel. Input state is unchanged.
- All **seven real-action results** (one audit plus six timed actions) match the previously verified meaningful state, complete response/explanations and eight ordered events. Only established incidental revision/disposable-path metadata is normalized. No mismatches were accepted.

Sixty-four sampled ctypes input/output objects all release **before GC**. Three 400-call batches in one process discard responses and use fresh inputs, without GC between batches. Native traced live allocations are **48.4, 49.3, 49.6 KB**, then **1.3 KB** after final diagnostic GC; Python is **31.4, 33.0, 33.3 KB**, then **1.6 KB**. Small ctypes/type/diagnostic allocations plateau in this bounded series; this is not proof about whole-career RSS. Native batch RSS fluctuates ~36–38 MiB; whole probe peak is 50.7 MiB. No production GC or cache was added.

Whole-action process peaks overlap: Python **586–622 MiB**, native **590–603 MiB**. These independent short processes do not demonstrate a consistent memory reduction or resolve the pre-existing long-lived server RSS question. The original memory diagnostic overlapped the stalled sanitizer initialization; it is retained separately and excluded in favor of the sequential rerun.

UBSan's standalone harness passes **516 numeric cases plus bad-argument checks**. **ASan is not passed:** the installed runtime stalled before `main`, sampled inside shadow-memory/malloc initialization with a spin mutex. The owned process was terminated; stack evidence is retained. Its cause remains unresolved. No sanitizer, OS or compiler environment was updated. A bounded reproduction script limits future sanitizer runs to ten seconds. This gap must be closed before native release approval.

## Toolchain and production gates

Default `/usr/bin/clang` and the Homebrew GCC driver hit the unaccepted Xcode-license gate. No license was accepted or bypassed by modifying configuration. The independently installed **Command Line Tools Apple clang 17** compiler/linker works when selected explicitly with its existing SDK. Its retained build command uses `-O3`, no fast-math/associative math, `-ffp-contract=off`, rounding-aware compilation and standard precision. The binary is 33,552-byte **arm64 Mach-O**, loaded by **CPython 3.14.4**, with a plain C ABI and no Python headers. It links only libSystem, but this experimental artifact has an absolute install name and **macOS 15.4 minimum/SDK**; it is not a redistributable macOS-11 beta artifact. No dependencies or toolchains were installed.

**Untested:** Intel Mac/Rosetta, packaged macOS Python 3.12, Windows x64/Python 3.13, frozen-app library discovery/signing/loading, platform NaN/denormal/rounding behavior, and Windows symbol exports. A portable release would need per-architecture signed/bundled binaries with the supported minimum OS, an explicit private ABI/version check, validated loading paths, input guards and complete Python fallback selected before using an unavailable/incompatible library. Do not treat `ctypes` alone as release portability.

Any separate production proposal must close ASan/platform gaps and run both busy seeds/month-boundary, daily/bulk/reload, actual human rotations and settlement safeguards against the current full fallback. This experiment did not repeat that broad campaign because production remains byte-identical. It offers no measured multi-second next kernel and does not justify porting the entire market or changing search policy to manufacture one. **Stop at this experiment handoff.**

Reproduction, run sequentially from repository root:

```sh
.venv/bin/python output/compiled-hotpath-experiment/build.py
PYTHONPATH=src:output/compiled-hotpath-experiment .venv/bin/python output/compiled-hotpath-experiment/differential.py
PYTHONPATH=src:output/compiled-hotpath-experiment .venv/bin/python output/compiled-hotpath-experiment/human_boundary.py
PYTHONPATH=src:output/compiled-hotpath-experiment .venv/bin/python output/compiled-hotpath-experiment/microbench.py
PYTHONPATH=src:scripts:output/compiled-hotpath-experiment .venv/bin/python output/compiled-hotpath-experiment/run_action.py --mode audit --output UNUSED_DISPOSABLE_DIRECTORY
PYTHONPATH=src:scripts:output/compiled-hotpath-experiment .venv/bin/python output/compiled-hotpath-experiment/run_pairs.py
PYTHONPATH=src:output/compiled-hotpath-experiment .venv/bin/python output/compiled-hotpath-experiment/memory_probe.py
.venv/bin/python output/compiled-hotpath-experiment/sanitize.py
.venv/bin/python output/compiled-hotpath-experiment/verify.py
```

`run_pairs.py` skips completed leaves: use a fresh artifact root for new measurements. Source fixture is the existing `stable17/saves/trade_year.json`; it is never advanced in place. Optional `sanitize.py --asan` has the timeout and records a non-pass if initialization stalls. `comparison.json`, `microbench.json`, `differential.json`, `human-boundary.json`, `memory.json`, build reports and source retain exact results. Preview **http://127.0.0.1:8796/** remains the unchanged production backend; no experiment code is loaded there and no server was restarted.
