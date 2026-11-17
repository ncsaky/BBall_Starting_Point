# Compact baseline and narrow native repair — milestone 16

Completed November 16, 2026. Accept compact Python as the scoped working default for explicitly enabled experimental recovery. Retain the directly selectable detailed evaluator and detailed selected-action resolution. Ordinary gameplay remains off. Reject arithmetic-only native qualification. Accept guarded native computation equivalence only against the separately opted-in `stable_route_bearing_v2` model; its practical performance qualification fails. Native remains an explicit experimental provider with Python fallback.

The complete records are in `output/compact-baseline-native-repair-2026-11-16/verified/`. `decisions.json`, `summary.json`, `strict-error-table.csv`, `source-hashes.json`, and `handoff-manifest.json` provide the review entry points. No ratings, dimensions, source evidence, research files, tracker, UI, server, seasons, host configuration, or C37 implementation changed.

## Scoped integration and attribution

Before changing geometry, the detailed and new scoped compact paths matched expected points, branch probabilities, scores, and effective choices exactly on all 64 existing scenes. Global function identities remained unchanged. All 349 existing regressions passed at this stage. The verified milestone15 adapter and numeric planner moved into two narrow runtime modules, `compact_recovery.py` and `recovery_numeric_plan.py`; neither imports experiment scaffolding or uses global mock dispatch.

`RecoveryCreationExperiment` defaults to `projection_backend='compact_python_v1'`, with `detailed_python_v1` directly selectable. Historical fixtures explicitly retain detailed mode so archived references remain reproducible. The default bearing stays `legacy_bearing_v1`. Backend/provider selection does not change the physical revision fingerprint; an explicitly changed bearing model does. The optional caller-owned provider has a named revision and a required bearing policy. Its implementation remains under the new experimental directory. Selected actions continue through detailed resolution, including full geometry, pass, alternate-contest, receipt/reset, and event diagnostics.

The pre-edit freeze contains 272 file hashes, twelve runtime reference modules, the previous compact/native prototype sources, and twenty input/result/binary pins. None of those accepted pins changed. Eight existing source/fixture files changed; the integrity table names them. The coordinator-owned tracker and all research/input artifacts remain untouched.

## Arithmetic repair versus shared model correction

The new isolated C copy changes the movement ramp from `.5*a*(v/a)*(v/a)` to ordered `v*v/(2*a)` and preserves `v/a+(d-edge)/v`, matching authoritative Python. Unsafe reassociation, contraction and fast-math remain disabled. Coordinate interpolation and capture-search ordering were audited without changing the search/grid. C `hypot` and Python `math.dist`/`math.hypot` still produce occasional different binary64 results: the raw direct physical maximum is 8.88e-16, with 197 nonbitwise fields per model. Mathematical distance equivalence and compiler flags do not establish bitwise equality.

Arithmetic repair alone still fails the original two Holmgren F04 held-out scenes. The largest expected-points error is 3.582688250092225e-5, branch error 1.7913441250350104e-5, and choice error 6.8386956142973965e-6. The legacy discontinuity test and frozen milestone15 failure evidence remain intact.

The separate shared model revision addresses a direction that is undefined at coincidence. It uses actual defender-minus-shot bearing whenever resolved. Its numerical ambiguity band is `min(1e-10 metres, 32*ulp(max(1, absolute shot/current/relevant route-origin coordinates)))`. This bounds coordinate-rounding ambiguity; it is not a basketball radius or measured tracking tolerance. Its coordinate dependence and cap are tested. At coincidence it uses the last represented actual movement segment: the helper's position before its final receiving leg, the defender's nominal-receipt position, or the actual screen coverage-release origin. Synthetic POA support does not invent a route.

When neither current nor route vector is resolved, directional alignment is explicitly `trailing_quality + (1-trailing_quality)/pi`, the rotation mean of alignment. It is angle-neutral, not a fully marginalized scoring law or a calibrated physical claim. Meaningful current separation takes precedence over any supplied route. This deliberately changes the model and is never presented as exact refactoring or as private native smoothing.

At the documented node, the Python separation is zero and the native separation is 5.55e-17 m. Both corrected paths use the same real route vector of length 1.047 m within a 7.11e-15 m ambiguity band. The legacy basis changes from angle zero to minus pi/2 under roundoff. `known-coincidence-attribution.json` retains detailed selected actions; `known-coincidence-angle-sweep.json` shows the original four angle quadrature nodes and strongest-eligible-contest selection.

Native conditioning recomputes an identical compact-Python node near ill-conditioned defined bearings, source thresholds and clock/window/zone cutoffs; it never modifies angles or probabilities. Original geometry-ambiguity repairs and whole-forecast utility-tie fallback remain visible. Across the 64 qualification scenes, each native variant attempted 13,536 native geometry nodes and performed 1,354 geometry repairs, with eight whole-forecast tie fallbacks. The corrected provider additionally recomputed 366 window-sensitive nodes, requiring 177 additional numeric plans and 213 contests. Candidate-local and discarded-attempt work, including nested repair work, is retained and timed.

## Qualification and deliberate effects

The corrected source, native guard, tests and harness were sealed before corrected held-out qualification; the final independent hash check confirms no later source changes. Probability/choice/TV limits remain 1e-9, physical-field error 1e-10, material omission threshold .005 and normalization tolerance 1e-12.

| Variant versus its own detailed model | Strict scenes passed | Max EP error | Max branch error | Decision |
|---|---:|---:|---:|---|
| Legacy compact Python | 64/64 | 0 | 0 | Exact |
| Legacy arithmetic-only native | 62/64 | 3.58e-5 | 1.79e-5 | Reject |
| Corrected compact Python | 64/64 | 0 | 0 | Exact |
| Corrected guarded native | 64/64 | 0 | 1.08e-19 | Local numerical pass |

Corrected native effective-choice error and TV are zero. There are no material omissions or normalization failures. Each model also has 1,152 exact mapped Python packet comparisons and 576 additional native mapped comparisons, totaling 1,728 within the 2,048-pair allowance; native mapped-field maximum is 4.44e-16. The bounded known-node diagnostics remain below that allowance. Geometric controls total 256: signed zero, coincidence, perturbation directions, resolved nearby separation, coincident route origins, translated/rotated cases, shot angles, and differing defender/capacity/availability contexts.

The deliberate legacy-to-corrected change affects eight of 64 numerical scenes. Its maxima are .000839282 EP, .000419641 branch probability, .000164828 effective choice and .000164828 TV. These are model differences, separate from computation error. The fresh single-use campaign used five qualified variants across four actors, three contexts and two seeds: 960 supplied possessions, 1,550 event attempts and 8.20 active seconds, within caps 1,536/6,144/60 seconds. The failed arithmetic-only variant was excluded. Same-model outcomes, receipt accounting, resets/creator transfers, rebounds and point sequences match. These fixed-seed observations had no paired model point changes; that small paired check does not establish model equivalence or empirical calibration. No optional follow-up budget was used.

All 349 retained plus 18 new regression tests pass. Forty-eight unaffected complete-result/RNG comparisons pass. Twenty-four held actions have identical complete diagnostics across computational backends within each model. Four bounded G8/panels8 controls retain exact detailed/compact parity, but quadrature sensitivity remains: max G4-to-refined EP difference .0007492, branch .01163, choice .05850 and TV .05850. These are reference-grid caveats, not native error, measured basketball truth or a convergence proof. No integration redesign was attempted.

## Cost and ownership

Five sequential warm samples per variant include fresh packing, reconstruction, every repair/discarded attempt and retained diagnostics. Build/load, first-call timing, preparation, profiling, serialization and payload sizes are separate. The same Turner/Jokic supplied16 batches and hard-window baseline were used.

| Working variant | Turner ms | Jokic ms | Speedup versus same-model detailed | Cost versus hard window |
|---|---:|---:|---:|---:|
| Legacy compact Python | 118.99 | 136.26 | 1.51x / 1.63x | 7.09x / 7.19x |
| Corrected compact Python | 121.04 | 141.89 | 1.57x / 1.56x | 7.22x / 7.49x |
| Corrected guarded native | 90.48 | 105.72 | 2.09x / 2.09x | 5.39x / 5.58x |

Hard-window medians are 16.77/18.95 ms. Corrected detailed medians are 189.54/221.29 ms. Guarded native is 1.34x faster than corrected compact Python. It fails both unchanged representative goals: at least 2.5x detailed and at most 4x hard-window on each actor. Its boundary12/fallback12 medians are 47.43/169.47 ms versus corrected compact 62.12/135.89 ms: fallback-heavy native is slower. Held24 remains about 3–4 ms; the three unaffected ordinary kernels are 36.23, 28.92 and 25.88 ms. Full samples, first calls, profiles and payload costs remain in `costs.json` and adjacent profile files.

Build took .483 s and first observed load .425 s. Later fresh-process cached loads were .00031–.00053 s, not a startup guarantee. The raw packet packing+C medians are .170/.164 ms, including .039/.052 ms in FFI+C. Reconstruction including all geometry repairs is .685/.168 ms. The initially reused adapter-only instrumentation patched the old module and incorrectly recorded zero nested FFI duration. That original record is retained; `adapter-costs-corrected-instrumentation.json` contains one bounded five-sample correction bound to the actual new module. Full forecast timings and acceptance inputs were unaffected; no sealed source changed.

Four release cycles free all 52 weakly tracked configuration/input roots. Full-cycle traced peak is 26.64 MB and retained tracing/bookkeeping is about 6 KB; local per-forecast figures are separately recorded. Native owns private numeric arrays and retains only a static code handle, with no retained candidate input/result graph and no runtime GC changes. The existing arm64 CLT build passes 512 standalone UBSan rows, canaries and seven invalid ABI/buffer guards. No ASan retry, installation or host/license change occurred. This is an arm64 macOS prototype with minOS/SDK15.4, an absolute install name and libSystem linkage; portable packaging/Intel/Windows/ASan qualification is not claimed.

## Reproduction and stop

From the repository root, use `PYTHONPATH=src:tests:.:scripts .venv/bin/python scripts/run_compact_baseline_native_repair.py STAGE`. The recorded order is integration; geometry/direct/native-mapped development controls; development; tests; seal; held_out; high_order; parity; mixed; costs; memory; adapter; tests; finalize. Build/sanitize use `experiments.compact_baseline_native_repair.build_native`. Consumed mixed budgets and the seal reject reuse in this output directory; reproduce in a fresh copied campaign directory rather than extending or overwriting the accepted one. The corrected adapter-only observation and extra context/known-node diagnostics are documented in their artifacts.

The bounded pass is complete. The compact baseline is usable within the approved experimental scope. Native has a local corrected-model numerical pass and a failed practical gate. Stop for coordinator review; perimeter-defense/C37 implementation is not started.
