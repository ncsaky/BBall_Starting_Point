# Cross-review market work — November 2, 2026

**Recommendation: NO-GO for persistent failure caching or a new early-rejection implementation on this evidence.** There is repeated negotiation content, but no demonstrated substantial exact-output reuse. Skipping formerly rejected packages would suppress freshly approved offers. Persisted negotiation memory is therefore a separate market-policy decision, not a performance cache justified by these measurements. No production changes were made.

The compiled experiment's NO-GO stands. October entry is already implemented: `save.new_career_start_date` returns the day before the first regular-season game; the verified current schedule enters **October 20**, before the October 21 opener. `tests/test_new_career_start.py` covers standard/fantasy entry and existing-career preservation. No startup migration, new career, native integration or preview restart was performed in this investigation.

## Bounded evidence and cost

Existing profiles, current review code, archived checkpoints and the previous design/native evidence were inspected first. Archives had endpoints but no complete adjacent-review candidate traces. The existing seed-17 February 3 fixture was therefore exported to a disposable career and advanced only through **February 4–5**, stopping normally at the trade deadline. This exercises two real market reviews, each with league and incoming-offer searches; it does not invoke hypothetical reviews on dates the calendar would skip. Five trades execute on February 4, six on February 5; 15 games and two date events remain in order. Slots, search breadth, approvals, RNG and user offers are unchanged.

External wrappers observe generation, normalized bilateral/multi-team evaluations and rejection stages. Counters retain digests/compact reports, not historical career graphs; the trace is bounded at 18,000 candidates/queries and is 2 MB compressed. An initial observer signature incorrectly supplied class attributes to a helper reading instance fields, producing empty flows. **Its repeat evidence is invalid and excluded.** The same interval was rerun with actual proposal dictionaries and assertions for nonempty directed flows; full proposals are retained for audit. No third interval or benchmark campaign was launched.

Corrected trace: `output/cross-review-investigation/trace.json.gz`; computed results: `summary.json`, `examples.json`. Total diagnostic action time is **31.88 s**, including **1.64 s** measured observer work. The remaining **30.24 s still includes wrapper overhead**, so it is attribution, not a new uninstrumented baseline or claimed speedup.

| Work | February 4 | February 5 |
| --- | ---: | ---: |
| Market, disjoint top-level seconds | 10.108 | 8.381 |
| Generation, contained in market | 2.157 | 1.839 |
| Candidate evaluation, contained in market | 5.424 | 4.407 |
| Generation queries | 638 | 638 |
| Candidate evaluations | 3,903 | 3,043 |
| Distinct ordered flow/terms packages | 3,587 | 2,815 |
| Multi-team evaluations, included above | 128 | 64 |

Generation and candidate evaluation are separate parts of market work; neither is added to the market total. Remaining interval phases, excluding observer: lifecycle/games **4.357 s**, settlement **6.051 s**, persistence **0.276 s**, response **0.764 s**, other dispatch **0.303 s**. Nested participant/roster/premium timers are not added to these totals. Public searches and fresh sequential settlement remain unmodified.

## What repeats, and what is actually identical

Package identity includes ordered directed sender/receiver flows, normalized asset IDs/kinds and the **actual full pending term lists**, including protections, fallback rights and swaps. A matching target or counterpart alone is never a matching package.

The conservative exact key additionally includes the complete prepared public source and audited private planning/control/spatial/entitlement inputs, actual proposal ID/date, seed and config/search arguments. Underlying ownership/financial/league inputs are thereby included. Unknown views would be excluded; none occurred. Whole-source equality is sufficient but deliberately **not claimed to be a minimal dependency key**. Component digests describe where inputs differ; they are not authorized production cache keys.

On February 5:

- **1,010 calls / 976 distinct packages** repeat February 4 flows/terms, costing **1.462 s** of candidate computation.
- **1,008 calls**, costing **1.443 s**, had previously failed. This is an **unsafe skip ceiling**, not available savings.
- **Zero** match the complete exact source/proposal key. All repeated packages have a new date-dependent proposal ID; personality uses `Random(seed:proposal_id:team:personality)` and must be recalculated. No repeated pair has identical complete derived strategy records. League-wide values, pick state and save records also changed after games/trades.
- Among repeated calls, only **134** retain identical full participating-player/roster records; **788** retain identical traits/contracts, **521** retain the forecast's actual availability/return-date inputs, and **1,010** retain front-office records. Full health/plan/wants hashes differ on every call, but those records include dates such as `reviewed_on`; **metadata differences alone are not proof that a calculation changes**.

This does not prove that every deterministic primitive must be recomputed. A correctly factored valuation or neutral feature calculation could survive a changed proposal ID. It does show that previous full decisions cannot be reused, and this trace does not certify a complete narrower cross-date key with substantial time savings. The earlier measured **entire** role-attribute budget was about 0.408 s on a busy action; unchanged traits alone do not establish a multi-second new opportunity there.

Generation has **331 date-free input-query matches**, costing **0.848 s** on the second date. Their direct shortlist is unchanged in **174** calls, costing **0.253 s**; **157** shortlists change. These are only direct-list output fingerprints: repair-frontier `repair_options` side outputs were not captured as equivalent. Identical direct lists therefore do not certify interchangeable generator results. Inputs are not exact across dates, and checking equality after doing the work saves nothing. Do not add 0.848 s to the failed-package ceiling as promised reuse.

## Concrete decisions an old failure would get wrong

There are **four distinct repeated-package approval changes**: two rejected→approved, two approved→rejected (five calls because one package is explored in both searches).

1. **LAL Ziaire Williams ↔ SAC Dylan Cardwell:** LAL net changes **−2.181 → +3.270**, crossing the **0.345** threshold. Recorded incoming/outgoing values and strategic adjustment are unchanged; the bounded personality total changes **−0.587 → +4.864**. Even an unchanged deterministic price is not an unchanged decision. These are approved search evaluations, not a claim that both were settled.
2. **CHI Tre Jones ↔ GSW Brandon Williams:** CHI net changes **−1.785 → +2.670**, threshold **0.820**. The previous rejection cannot be treated as a durable refusal.
3. **BKN Day’Ron Sharpe ↔ PHX Jamaree Bouyea + Jordan Goodwin + a swap:** approval becomes rejection; fresh roster-plan and pick-investment conclusions differ. The swap and its exact terms were included, not collapsed into a generic pick value.

Three additional distinct **new** packages are approved after *all* prior packages for the same seller/buyer/target had failed. One reaches the actual user inbox: February 4's **MIA Kylor Kelley for GSW 2030/2033 seconds** fails (GSW preliminary net **−26.464**); February 5's **Kelley for Georges Niang** is approved and queued `pending_user_review`. A target/buyer blacklist would hide a genuinely fresh offer. The other examples include a new BOS player package for LAC Max Strus and a different pick payment for CHI Buddy Hield; full details are retained in `examples.json`.

## Earlier authoritative checks and remaining small exact reuse

The current implementation already classifies actual player movements with authoritative salary/roster rules before expanding pick variants. Repairable mismatches/overages retain their separate facilitator frontier. `_evaluate_trade_snapshot` then checks legality and the complete-package premium-return safeguard; `evaluate_trade_participants` stops on the first authoritative net/core preliminary failure before roster planning. Completed routes retain full participant checks.

Measured remaining outcomes:

| Existing stopping point | February 4 calls / seconds | February 5 calls / seconds |
| --- | ---: | ---: |
| Illegal | 35 / 0.0667 | 19 / 0.0392 |
| Premium guard, before participants | 7 / 0.0024 | 12 / 0.0045 |
| Preliminary rejection, before roster plans | 3,261 / 2.494 | 2,472 / 1.963 |

Most residual illegal cases are multi-team missing incoming consideration (**28 / 17**); the rest include a few fresh salary/recent-trade/Stepien failures. A topology preflight before pick compilation could avoid some invalid-route preparation, but **all illegal and premium cases together cost only 0.113 s across both dates**. This is not a material next implementation target. No invalid package becomes eligible because it can attract a facilitator, and a salary mismatch/hard cap is not declared terminal.

The large preliminary-failure row is not free waste: its net includes actual incoming/outgoing package prices, strategic/wants adjustments, roster-space credit and current bounded personality. Core protection is conditional on return adequacy; it cannot be moved ahead by categorically excluding a core target. An earlier safe bound would need a proof against these fresh quantities, including exact pick terms and attainable strategic credits. No such cheaper bound with measured net benefit was demonstrated. Rough value scores and last-date failures are not proofs.

Within the **same** immutable review, complete exact duplicates do exist and their recorded scalar/legality outputs match:

- February 4: **316 evaluations / 0.246 s**; **65 generator calls / 0.177 s**.
- February 5: **228 evaluations / 0.188 s**; **64 generator calls / 0.151 s**.

Those disjoint generation/evaluation ceilings sum to **0.423 / 0.339 s per review**, before keys, copies, diagnostics and preservation of repair side outputs. They overlap the cross-date repeat set and must not be added to it. This is a possible small review-local memo task, **not a recommendation for another material latency pass**; ordinary-season budgets can differ between league/incoming searches and may have fewer hits. It does not justify a persistent cache.

## Decision boundary and verification

No implementation is recommended under the unchanged-outcome constraint. If negotiation memory is desired as gameplay, the separate decision is to permit a new policy: bounded records of specific directed packages/terms and refusal reasons, scheduled fresh exploration and invalidation on relevant state changes. It must always allow different offers for the same target, protect facilitator routes, reevaluate after health/contract/ownership/planning/wants/calendar/league changes and use fresh authoritative settlement. Even skipping old packages might simply shift time into replacement exploration; it is not a speedup until measured end to end. That behavioral proposal requires explicit approval and search-quality/discovery-loss tests, not an “exact cache” label.

Any later exact memo proposal should first demonstrate a complete factored dependency key, match intermediate and final reports, preserve ranking/order/RNG/diagnostic accounting, copy all mutable outputs including repairs, remain review-owned/bounded, and show repeated unprofiled app-action savings on busy seeds/month/daily-bulk/reload. A behavior-changing proposal additionally needs counterexamples above, earlier rejected bundles that become valid, fresh alternatives for the same target, protections/swaps, facilitator approvals, expiry/invalidation, and changed-health/contract/league scenarios. None of that production work was begun here.

The corrected and initial observer actions have **identical meaningful state, full response/explanations and all 17 ordered events**; only established revision/disposable-path metadata is normalized. Both preserve the source fixture and stop at `trade_deadline`. All 67 production/data hashes, including the fresh settlement implementation, remain unchanged. No broad suite, additional seeds, season study, native integration or preview action was run; this is one deadline seed and is not evidence about every calendar period. The unchanged verified backend remains **http://127.0.0.1:8796/**.

Reproduce with an unused diagnostic output root (the retained root already contains completed actions), sequentially:

```sh
PYTHONPATH=src:scripts .venv/bin/python output/cross-review-investigation/probe.py
.venv/bin/python output/cross-review-investigation/analyze.py
```

Change diagnostic `ROOT` before rerunning the probe; retain/copy its analyzer and manifest there. The source is `output/pick-investment-2026-10-28/stable17/saves/trade_year.json`, target `2027-02-05`. The analyzer also expects the retained initial capture solely for action parity. No production files are instrumented or cleaned up afterward.
