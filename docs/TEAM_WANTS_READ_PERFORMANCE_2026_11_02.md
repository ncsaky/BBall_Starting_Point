# Team Wants read-path performance — November 2, 2026

Implemented one narrow backend change: **Team Wants reads use the existing revision-owned dashboard/transaction read context**. The two requests after a real streamed action now take **0.046 s versus 0.806 s median**, saving approximately **0.760 s of HTTP request tail**. Browser control-unlock time was not measured in this pass and is not claimed as a saving.

Production scope is only `src/nba_gm_data/app_actions.py`. Shared GUI files, market/search policy, RNG, rotations, ratings, quotas, fresh settlement checks, October entry, Lillard import data, native/build dependencies and playable saves were preserved. No cross-date negotiation cache or new cache was added.

## Reproduction and ownership audit

The earlier [latency investigation](SIMULATION_LATENCY_2026_10_30.md) identified two requests from `wireTeamWants` and `maybeShowWantReminder` after final rendering. The current baseline still performs, independently for each read:

1. Dispatcher save load/baseline selection.
2. Another load/default normalization inside `team_wants_action`.
3. Full `canonical_with_save` overlay, including private normalized rotation/health inputs.
4. Full transaction valuations, league-relative strategy and trade-block construction.
5. Wants entries, suggestions, acquisition reminder, requested asset matches and permissions.

After an already-prepared dashboard, two pre-edit direct app reads took **0.424 / 0.401 s**. Their nested clocks included **0.298 s overlay**, **0.435 s transaction enrichment** (containing **0.326 s full context construction**), but only **0.00074 s Wants payload work**. These inclusive rows overlap; they are not added together.

The dashboard already owns the same full materialization and derived league context. An external prototype matched complete Wants responses for three teams before production was edited. The implementation now calls `dashboard_read_context` and `transaction_read_active` for **reads only**. Cache misses still perform the complete original overlay and transaction build; no derived fields or checks are omitted. Set/acknowledge actions retain fresh privately owned validation inputs and existing permissions/revision checks.

The existing owner uses resolved save path, file revision and canonical/baseline identity, validates history components on cache hits, and is limited to **two LRU careers**. Normal atomic writes/restores and changed baseline identity replace/invalidate that owner. Every mutable dependency—ownership, contracts/dead salary, injuries, rotations, plans/wants, date and control permissions—continues to come from the complete save materialization. The server's baseline source is immutable for the request lifetime; no player-ID/date-only cache key was introduced.

The cached save has already undergone overlay normalization, so copied-save and cached-save use was checked rather than presumed equivalent. Full-response tests cover the cached path both before and after dashboard preparation. Wants reads build deterministic display suggestions but do not publish AI wants, refresh saved plans, search the market, write saves or emit simulation events.

`team_wants` also joins the existing per-save read-lock group, keeping shared projections coherent with mutations. Returned `matches` lists are copied: `asset_matches` internally memoizes mutable lists, and returning those directly from a shared owner would let a Python caller poison later responses. Entries/reminders/suggestions/roster/team lists were audited for caller ownership. The default team now comes from the already-loaded normalized save, using the same metadata/fallback as the old duplicate lookup.

## Real HTTP measurements

Evidence: `output/team-wants-read-pass/`. The full Python pre-edit reference is retained; verified unchanged resource files are shared by the reference. One ephemeral authenticated loopback server at a time used normal session/token/origin checks, `restore_save`, action and streaming endpoints. All restores/setup were outside timing, used fresh disposable paths/revisions, and did not inject stale contexts. Versions ran sequentially with no competing simulation benchmarks. No GUI/browser was opened or edited.

Three samples per warm case, seconds to complete response bytes; ranges in parentheses:

| Request/sequence | Before | After |
| --- | ---: | ---: |
| First process Wants read, one observation | 0.647 | 0.637 |
| Subsequent cold context, two restored samples | 0.389 (0.363–0.414) | 0.388 (0.384–0.393) |
| Repeated read, same revision | 0.379 (0.363–0.387) | **0.019 (0.019–0.021)** |
| Two reads after dashboard | 0.787 (0.758–0.794) | **0.040 (0.039–0.043)** |
| Two reads after real streaming action | 0.806 (0.798–0.819) | **0.046 (0.042–0.049)** |
| Real action receipt + both reads | 2.257 (2.189–2.555) | **1.567 (1.440–1.984)** |

The action is the existing ordinary off-day fixture, October 30–31: eight games, normal simulation/events. Advancement itself was **1.460 → 1.521 s median**, not improved by this change; the first action in each server process was slower than subsequent actions. The measured benefit is the post-result read work. Cold Wants reads still need full construction, including after an edit when no fresh dashboard has been prepared.

Separate attribution servers, not used as wall samples, confirm **two overlays/two full builds → zero** for the post-dashboard pair. Warm updated reads still perform one dispatcher load each (~13–14 ms), history validation and payload work (~0.3–0.5 ms). HTTP response size remains **3,529 bytes**, with exact response equality. Client JSON decoding is about **0.04 ms**. HTTP measurements include loopback transport/server serialization; no precise network/serialization split or frontend animation/control timing is inferred from them.

## Regression and memory gates

**24 selected tests pass**, including new cache/ownership/locking tests, existing Wants rules, missing-history validation and existing LRU eviction checks. A separate **25-case real-fixture differential** invokes the complete pre-edit read implementation through the normal dispatcher and compares every response field:

- Cold/default/team selection and dashboard-prepared reads.
- Wants edits/reordering, stale edit revisions, edit permissions and acknowledgement tokens.
- Departed upgrade targets, acquired players/picks and reminders.
- Contract salary, injury, plan and date/horizon changes written through normal save revisions, without manually invalidating the cache.
- Alternating careers, different human control, malformed requests and caller mutation of returned results.

Reads leave save bytes and meaningful save data, RNG and progress events unchanged; guards confirm they do not invoke AI planning/market actions. All **18 HTTP Wants responses** match without incidental exclusions. All **three streamed action responses**, saved-state digests and nine ordered date/game events match the frozen backend; only established action revision/disposable-path metadata is normalized.

Memory diagnostics run separately in one process: three batches of 30 reads hold **two cache entries** throughout. With ordinary unwrapped production objects, new traced live allocations after warm-up are **33.3, 36.5, 37.6 KB**. A separate ownership probe uses weak dictionary wrappers. Revision replacement releases the prior raw/derived roots before GC; eviction releases the next four; all **10 sampled roots** release after clearing the cache. Weak dictionary wrappers are diagnostic only and can rebuild internal owner-ID indexes; wall timings use ordinary production objects. No forced GC runs between batches or was added to production.

Final tracked allocation after clear/diagnostic GC is **10.7 KB** for ordinary objects (**9.5 KB** in the separate weak-wrapper probe). The first memory probe itself retained a setup save variable (~4.7 MB); it was corrected and rerun, and its raw report is excluded. Unwrapped repeated-batch RSS varied **473 → 453 → 330 MiB**; revision/eviction work peaked around **206 MiB of traced allocations**. Those are diagnostic observations, not an incremental cache-size or whole-server RSS reduction claim. A cold Wants request now occupies one existing read slot; on the intended post-dashboard path the slot already exists. The prior broader RSS high-water question remains unresolved.

## Remaining work and server status

The frontend still issues both reads and maintains its busy counter. A narrow UI-owned follow-up could share one revision-matched Wants response between the surface and reminder, then remeasure final-result receipt → controls usable. This pass does **not** edit that flow or promise a control-unlock reduction from backend times alone. The remaining warm backend cost is primarily dispatcher save/baseline validation; cold construction remains ~0.39 s. No further cache framework is proposed.

All ephemeral measurement servers were stopped. Their URLs are recorded in the reports; they are not previews. Existing **http://127.0.0.1:8796/** was left running and **still has the pre-change backend loaded**. The updated source was verified on the isolated servers, not deployed by restarting a shared preview.

Reproduce sequentially with unused output folders (the runners deliberately reject overwriting measurements):

```sh
PYTHONPATH=src:tests .venv/bin/python -m unittest \
  test_trade_wants test_team_wants_read_context \
  test_save_recovery.SaveRecoveryTests.test_cached_dashboard_does_not_hide_newly_missing_history \
  test_context_demand_performance.ContextDemandPerformanceTests.test_read_cache_is_lru_bounded_and_evicted_graphs_release -v
PYTHONPATH=src .venv/bin/python output/team-wants-read-pass/verify_reads.py
PYTHONPATH=scripts .venv/bin/python output/team-wants-read-pass/measure_http.py --version before
PYTHONPATH=scripts .venv/bin/python output/team-wants-read-pass/measure_http.py --version after
PYTHONPATH=scripts .venv/bin/python output/team-wants-read-pass/measure_http.py --version before --diagnostic
PYTHONPATH=scripts .venv/bin/python output/team-wants-read-pass/measure_http.py --version after --diagnostic
PYTHONPATH=src .venv/bin/python output/team-wants-read-pass/memory_probe.py
PYTHONPATH=src .venv/bin/python output/team-wants-read-pass/memory_probe.py --unwrapped
.venv/bin/python output/team-wants-read-pass/summarize.py
```

For another measurement campaign, change the diagnostic `OUT`/case folders while retaining the original reference; do not rerun `inspect_read.py` over its pre-edit snapshot. `comparison.json`, `production.patch`, `regression.json`, `memory.json`, `memory-unwrapped.json` and test/HTTP logs record the gates. Only `app_actions.py` differs among the 67 recorded production/data files; all other completed optimizations remain intact.
