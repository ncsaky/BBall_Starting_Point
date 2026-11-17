# Minimum Completion Backlog and Coordination

Recorded October 29, 2026. This is the user's minimum known completion list, not a claim that the game has no other bugs or release requirements. Nothing below is waived merely because it is grouped with another item.

Original notes are preserved verbatim in `USER_COMPLETION_NOTES_2026_10_29.txt`. The original attachment was `/Users/noahtyler/.codex/attachments/3e3bd9a6-a3d7-47bc-93c5-4e8f3bd6908f/Pasted text.txt`.

## Status Rules

- Open: reported or requested; not yet verified in current code.
- Investigating: assigned with a bounded question and evidence target.
- Implemented, awaiting verification: not done.
- Verified, awaiting user approval: functional evidence exists; visual/product approval remains.
- Accepted: verified and, where necessary, approved by the user.
- Deferred by user: remains in the minimum list unless explicitly removed.

Every future update should name the item ID, exact scope, evidence path, preview URL/build, and next decision. A prior chat's completion claim alone does not close an item. No product items in this list are accepted yet. There is no promise of zero failures; small scopes, differential tests and approval checkpoints reduce risk and rework.

## Performance: Active, Do Not Lose

Owner: existing performance implementation chat. Model recommendation: GPT-6.1 Sol, High; no Ultra.

Completed before this checklist: compact trade decision/presentation separation; review-local reuse; exact package shortlist optimization; salary-aware search; roster forecast indexing/reuse. Latest reported roster-pass medians: 22.10 seconds seed 17 busy day, 20.51 seconds seed 29, 19.96 seconds month boundary. Unprofiled peak RSS pair rose from approximately 598 to 690 MB. Snapshot release checks passed, but this does not resolve the memory increase.

Latest completed assignment, user report checked against repository notes: fresh context construction and long-lived memory investigation. Medians are now 20.03 seconds seed 17 busy day, 19.55 seconds seed 29, and 18.41 seconds month boundary. The pass bounded a pre-existing dashboard read-context cache to two careers; retained allocations stabilized in the measured multi-career probes. Six-action peak RSS fell approximately 993 to 829 MB. The earlier isolated 598-to-690 MB change remains partly unexplained. Reported 345 tests and exact state/event/API parity passed. Evidence: `output/context-demand-pass/` and the performance notes. This is not user acceptance of overall simulation speed.

October 30: end-to-end latency investigation completed; coordinator read `SIMULATION_LATENCY_2026_10_30.md`. Ordinary warm actions receive results in 1.54-1.65 s and unlock controls around 2.8 s. Busy market: 18.95 s result / 20.53 s controls; month: 17.91 / 19.18 s. Playback already overlaps computation; no new animation queue justified. Two post-result wants reads add about 1 s of control locking. Ten duplicate settlement overlays across five trades cost 1.53 s, an addressable upper bound rather than a promised improvement. Initial 33.50 s first-use sample remains unattributed and excluded from equivalent-state comparisons. Diagnostic servers stopped and UI was explicitly released by the performance chat per its report. New quiet windows must be bounded, not indefinite holds on other lanes.

Next proposed assignment (NOT yet dispatched): one private, fresh materialization shared within each bilateral settlement validation, with full fallback and normalization/ownership tests; no reuse across applied trades. Separately track the duplicate wants-read/control-tail fix for U/P coordination AFTER exact visual baseline restoration. Preserve acquisition reminders and decision-stop behavior.

Latest recorded new-code isolated preview: `http://127.0.0.1:8781/`. Playable `8780` was deliberately not restarted and may run older backend code. These are historical reports, not a live server-health check.

Evidence: `SIMULATION_SPEED_2026_10_29.md`; `output/roster-forecast-pass/`. Continue speed work based on the current task's results, not this checklist's distractions. Persistent negotiation memory and computation/playback overlap remain proposed later work, not implemented promises.

## Work Lanes and Ownership

| Lane | Chat | Model / effort | Scope now | Restrictions |
| --- | --- | --- | --- | --- |
| P | Existing performance chat | GPT-6.1 Sol / High | Latency investigation complete; settlement materialization pass proposed | Sole simulation/market backend writer when resumed; bounded quiet windows |
| U | UI completion chat, launched per user | GPT-6 Luna / High | First prototype REJECTED by user; restore exact established Next Opponent baseline before any incremental work | Prior latency hold released; preserve other chats' changes |
| R | Ratings evidence chat, launched per user | GPT-6 Luna / High | Source index and selected excerpts delivered; broaden evidence, no production edits | Research documents only; no production data changes |
| D | Later draft/metric diagnosis chat | GPT-6.1 Sol / High | Distinguish rankings, scouting, potential and selection logic | Initially read-only; schedule code changes after P's benchmark checkpoint |
| C | This coordination chat | Current model for short reviews only | Scope, acceptance, next prompts, conflict resolution | Do not repeatedly rerun implementation audits here |

Use the current local project, preserving existing dirty changes. Do not assume a new worktree contains uncommitted optimizations; establish its baseline before using it. Parallelism is safe only with explicit file ownership. U commonly touches `src/nba_gm_data/gui/app.js` and `styles.css`; P may touch `app_actions.py`, `save.py`, `transactions.py`, `sim.py`, `trade_roster.py` and related modules. Actual files must be checked by the implementer. R owns separate research documents. No other lane changes shared performance notes or this coordinator checklist concurrently without coordination.

Only one heavy benchmark/simulation/browser test workload at a time. Lightweight editing and transcript research can continue while P runs; U must not run competing heavy tests during measured timings. Do not simulate or alter the user's active save to obtain screenshots. Use existing snapshots/disposable saves and report which preview has which code.

## Inventory

All entries below start OPEN. Suggested visual solutions and tentative theories are not automatically final design requirements.

### U1: Table Consistency

Apply to Minutes + Availability, Player Development, Coaching Staff tables, Standings, and Next Opponent. Establish one approved reference before propagating.

| ID | Requirement | Acceptance |
| --- | --- | --- |
| T01 | Sorting where meaningful | Explicit per-column inventory; numeric/string/missing-value sorts correct, deterministic ties, keyboard-accessible headers and aria-sort. Preserve true standings rank; sorting must not rewrite seeding. |
| T02 | Whole-row hover highlight | Highlight follows row, not isolated cells; does not obscure injury indicators, selection or sliders. |
| T03 | Alternating white/slightly gray rows | Consistent across five tables, including hover and selection combinations. |
| T04 | Sorted-column emphasis | Subtle distinguishable fill, visible together with striping/hover and active-team state. |
| T05 | Unified bar width and unfilled-bar darkness | Reuse established payroll/player/table conventions appropriate to the metric; do not normalize away meaningful scales or introduce overflow. |

Record a five-table by five-requirement matrix: present / missing / intentionally inapplicable with reason. Do not declare a global CSS change correct without testing each table. Preserve slider focus and pointer capture; no row teleporting mid-drag. Keep established font sizes, dense layout, double header separation and dark labels. Broad abstractions are not required.

### U2: Small Presentation and Interaction Items

| ID | Requirement | Acceptance / clarification |
| --- | --- | --- |
| U01 | Fix card-gallery previews | Representative non-glitched previews; established button style; no need for live accurate previews. |
| U02 | Tab-switcher icons | Distinct readable icons/consistent fallback for all window types; approve first icon set before rollout. |
| U03 | Next Opponent after W/L animation | Result stays associated with completed opponent, then changes to actual next opponent; handle no next game and interrupted playback. |
| U04 | Simulation shortcut prefix | After S, E/W/M remains available regardless of pause until another click as requested. Decide cancellation on unrelated key, Escape and focus change; never hijack text entry or browser shortcuts. No real-time timeout. |
| U05 | Draft lottery ordering | Pick 1 top-left, 14 bottom-right. Preserve reverse 14-to-1 reveal timing; spatial ordering is not reveal ordering. |
| U06 | Positional average markers | Draft prospect player-card rating bars show appropriate positional comparison, not league average. Define multiposition and unavailable sample behavior; do not alter ratings to change markers. |

### M: Ratings and Metric Clarity

| ID | Requirement | Acceptance / dependency |
| --- | --- | --- |
| M01 | Make active injury rating reductions visible | Show baseline versus temporarily effective OVR/OFF/DEF wherever affected values appear. Small red delta/down arrow is user's proposed treatment, pending visual approval. Exact backend baseline is required; do not infer permanent talent loss or invent deltas. |
| M02 | Clarify trade valuation breakdowns | Inspect current task-1 explanations before duplicating work. Explain neutral versus team-context value, role/upside contributions, acceptance thresholds and vetoes in plain language without removing charts. |
| M03 | Clarify development net growth, potential and remaining upside | Establish actual definitions, time windows and displayed/hidden values; use consistent labels and examples. Do not silently change development formulas. |
| M04 | Investigate fit | Trace actual inputs, consumers and units, distinguish descriptive roster fit from valuation adjustments and game impact. Propose changes only after audit. |
| M05 | Possible contextual second tutorial | User suggests a trade-entry tutorial also explaining development. Decide after M02/M03 whether concise contextual help suffices; do not build redundant tutorial infrastructure first. Any tutorial remains skippable and consistent with existing controls. |

M01-M04 are diagnosis plus presentation, not permission to make unexplained backend tuning changes. Prototype one injury indicator and one explanation surface before applying everywhere.

### PO: Playoff Cards

| ID | Requirement | Acceptance |
| --- | --- | --- |
| PO01 | Replace playoff league leaders with Playoff Stats | Real playoff table, points default sort, other stats sortable; accurate competition scope, no mixed regular-season denominators. Use double header border, small bold headings, stripes, whole-row hover, sorted-column emphasis and correctly sized bottom-aligned headshots. |
| PO02 | Playoff entry layout | Playoff Stats and Minutes + Availability open automatically alongside bracket. User's latest request supersedes the older bracket-only layout. Clarify one-time entry versus reload so manual closures are respected. |
| PO03 | Playoff active-injuries card | Proposed by user as useful additional popup: table default OVR sort with OVR/OFF/DEF bars. Confirm automatic-open preference, league versus user-team scope, and interaction with PO02 before building. |

### D: Draft and Prospects

| ID | Requirement | Acceptance / dependency |
| --- | --- | --- |
| D01 | Draft-night prospect board redesign | Match extended regular-season Upcoming Prospects design, enlarged appropriately. Coordinate with table foundation and injury/ratings fields. |
| D02 | Draft-night window layout | Center and arrange cards together without overlap or needless whitespace across supported viewports. Respect saved user layout after initial entry where applicable. |
| D03 | Per-selection animation | Each revealed pick animates once; preserve bulk ordered reveals, trades/phone flow, user-pick stops, skip/reduced-motion behavior. No redundant duplicate playback. |
| D04 | Diagnose apparently irrational falling prospects | Reproduce with archived/user checkpoint if available. Trace public board rank, user scouting uncertainty, NOW/POT/upside, health, fit, GM evaluations, draft availability and randomness. A ranked-2, 80 NOW/96 POT prospect falling to 15 is evidence to investigate, not proof randomness must be reduced. |
| D05 | Consensus board versus user scouting board | User wants both concepts. Define source/ranking semantics, then expose clearly; do not present hidden true ratings as scouting knowledge. Connect to M03 and D04 before tuning AI. |
| D06 | Prospect injury history visibility | Verify existing generated/imported history and distinguish history, current injury and projected risk. Surface available evidence on prospect board; do not fabricate histories. |

Fix truthful rankings/explanations before deciding whether draft-selection logic needs calibration. Preserve justified surprises, busts/gems and medical concerns. Research and backend decisions precede the final draft UI pass.

### FA: Offseason Workspaces

| ID | Requirement | Acceptance / dependency |
| --- | --- | --- |
| FA01 | Free agency UI/UX redesign | Prototype one actual usable screen using existing negotiation/player-card language, dense rows and established window/button chrome. Preserve offers, guarantees, cap implications, sorting/filtering, decisions and app-action permissions. User approval before full rebuild. |
| FA02 | Mandatory roster cutdown card redesign | Use approved table system; clearly show keep/release choice, required roster count and existing contract/waiver costs without inventing rules. Preserve mandatory stop and safe confirmation. |

These are two bounded redesigns, not one giant UI prompt. Prototype with real data and keyboard/mobile constraints, not just an attractive screenshot.

### B: Assistant GM Briefings

| ID | Requirement | Acceptance / clarification |
| --- | --- | --- |
| B01 | Year-end recap slideshow | Stat leaders, awards, final standings, user's team stats and team MVP, biggest trade, biggest coaching change, top 5/10 upcoming free agents. Define selection criteria and retain season-end data before rollover. |
| B02 | Preseason outlook slideshow | Power rankings, continuity graphic, relevant prior leaders, prospect/contract context. User invites further useful ideas; approve slide outline first. |
| B03 | Minutes-weighted continuity comparison | For each team, segment by prior-season minutes; green returning, red departed. Use prior-season team stints, a defined competition scope and current ownership cutoff; all teams comparable. Handle rookies/new saves/missing history honestly. |

Use arrow-page navigation like the established player extension. Do not precompute heavy slideshow data every simulation day. Build summaries at the appropriate boundary or on request from retained data. Gold/fancy presentation is not a license for a new visual language. Slideshow size, automatic-open behavior and optional extra slides need approval.

### R: Imported Ratings and Contracts

| ID | Requirement | Acceptance |
| --- | --- | --- |
| R01 | Broad NerdSesh transcript evidence pass | All 11 user links accounted for with access status, title/date, speaker/timestamps, claims and reasons; disagreement, rhetoric, injuries and future projections distinguished. |
| R02 | League-wide imported-rating proposals | Map evidence to existing trait semantics and league calibration. Use NerdSesh as expert opinion, not sole truth; cross-check material claims with independent reporting/data. Preserve prospect/development baseline unless a separate flaw is demonstrated. |
| R03 | Dame contract correction | Verify contract, season, guarantees/options and provenance against reputable sources. Separate real-world current terms from the game's starting-date snapshot and existing saved careers. |
| R04 | Dylan Harper OVR concern | Research proposed upward correction, not automatic approval of a buff; show current traits and supported changes. |
| R05 | Sochan overrated concern | Research proposed downward correction with the same evidence and calibration standard. |
| R06 | Luka underrated concern | Research proposed upward correction; distinguish health-adjusted effective ratings from healthy ability. |

No ratings or contract mutations while P is running comparative benchmarks. Research may proceed now. Obtain user approval of calibration date and a small example patch before broad edits. Apply versioned imported-data corrections without resetting development, injuries, ownership or negotiated contracts in existing careers. Later verify combined league/role distribution and bounded gameplay, not only named-player OVR.

The original notes file preserves all 11 URLs, including query strings. Research must acknowledge unavailable transcripts rather than infer opinions from titles/snippets. This coordinator has not reviewed the videos and makes no claims about their content.

## Sequence and Approval Gates

1. Now: P's context/memory task is complete; next proposed performance assignment is end-to-end latency attribution. U and R are launched per user: ONE reference table and TWO representative transcript extractions respectively. No extra backend writer. These chat states are user reports, not live tool monitoring.
2. User approves reference table and research extraction/calibration approach. U propagates table rules and handles small UI fixes in bounded batches. R completes remaining evidence without production edits.
3. At a clean P checkpoint: D traces draft-ranking/potential/fit/injury-display semantics from existing snapshots, read-only initially. Obtain concrete diagnosis before authorizing logic changes.
4. U implements metric clarity and playoff/draft cards using approved semantics. Implement data/API additions serially with P, not by racing shared Python files.
5. U prototypes free agency, then cutdown, with user approval for each. R/Sol proposes a versioned ratings batch for approval after performance reference preservation.
6. Briefing outline and data availability audit, then one end-to-end slide prototype, then the remaining approved slides. Final integration check across season/playoffs/draft/free agency/rollover and representative desktop/mobile layouts.

This sequence groups work; it does not delete any requested feature. PO03, M05 and proposed graphic treatments remain approval questions, not silently rejected scope.

## Queuing Policy

Latest user feedback: the first UI prototype was unacceptable. The current approved visual reference is the existing clipboard Next Opponent card EXACTLY, not the failed prototype and not a reinterpretation based on Team Block. Baseline recovery must selectively undo only that chat's unwanted edits, preserving concurrent work; no whole-file reset. Obtain before/after confirmation before propagating any visual changes. Performance latency measurement currently takes priority over GUI writes or browser automation.

The coordinator read R's `SOURCE_INDEX.md` and `FIRST_EXTRACTIONS.md`. The extraction method separates present ability/ceiling/health appropriately, but covers only selected segments, not complete episodes. Stable Panelist A/B attribution across an episode is not justified by undiarized captions alone. Verify caption-to-video provenance (including the top-10 team video's excerpt discussing rank 14) rather than assuming an inconsistency proves a wrong source. Dame/Harper/Sochan/Luka research was explicitly not performed and remains open. Retain source dates and defer the July-start versus later-evidence calibration choice; further research does not need to wait for that choice.

Research follow-up received and read: `NAMED_PLAYER_DOSSIERS.md` and `COVERAGE_AND_GAPS.md` now contain dated named-player/contract findings; speaker labels and selected-passage coverage were corrected. No production changes. R03 has a concrete apparent active-contract versus former-team dead-salary aggregation issue to verify at import and app-action boundaries. R04-R06 remain hypotheses: the dossier's direct canonical-summary values (Harper 59.5, Sochan 56.9, Luka 71.3) must be reconciled with actual new-save/API/display paths before using them for tuning. This is a verification need, not a confirmed display bug. Nine sources remain without extraction; the two retained sources still have only passage-level coverage. Rate-limited source retrieval must not become the only route forward while usable local captions remain. No ratings item is accepted or implemented.

October 30 follow-up: coordinator read `DISPLAY_VALUE_TRACE.md` and `CONTRACT_IMPORT_FINDING.md`. The low dossier numbers are internal engine summaries; static card-scale OVR/OFF/DEF is Luka 88.9/96.0/67.5, Harper 79.5/80.0/81.5, Sochan 76.9/72.8/87.1, Lillard 86.8/93.5/65.4. These are BEFORE save rotation projection; exact new-save action values remain unverified. The existing minutes contribution to OVR is a separate design question, not automatically a bug or authorization to modify the formula. R03 source tracing identifies a POR-tagged schedule already aggregated with MIL stretched salary; importer selects it, while clean-save MIL dead obligation seeding is absent. Corrective implementation must separate ledgers, preserve unknown set-off status and prevent duplicate seeding, including reload/migration scenarios. No correction implemented. Full draft-caption extraction was delivered per research-chat report; team episode remains passage-level. Research can continue without changing performance benchmark inputs; a short runtime probe should use an explicitly released measurement window, not indefinite assumed blocking.

- Good queue: after an approved table prototype, propagate the exact approved style to specified remaining tables, test, capture screenshots, then stop.
- Good queue: after a verified transcript-extraction format, extract the remaining sources into that same format; flag gaps instead of guessing.
- Bad queue: redesign free agency, change draft logic, tune ratings and add briefings without review.
- A queued message is not a dependency scheduler. It can arrive before approval; include explicit stop conditions, and do not queue implementation across a pending approval gate.
- Run one writer per shared module family. Use separate file prefixes for research outputs. No autonomous ten-season studies, installations or broad cleanup for a small UI task.
- Escalate models for a concrete unresolved reasoning problem, not because a task ran for a long time. Use Luna High for focused UI and extraction, Sol High for cross-system semantics/algorithm changes; use this chat for short decisions, not duplicate work.

## Ready-to-Paste First UI Assignment

```text
You own the UI completion lane, not the simulation backend. Read docs/MINIMUM_COMPLETION_BACKLOG_2026_10_29.md and docs/USER_COMPLETION_NOTES_2026_10_29.txt. Preserve all existing edits. Performance work is active in another chat.

Task: inventory T01-T05 across Minutes + Availability, Player Development, Coaching Staff, Standings and Next Opponent, then implement ONE small reference prototype on Next Opponent. Use the existing Team Block/player-card tables as style evidence, not a new design language. Report what is already correct before editing.

Use exact established toolbar button borders, black hover text and clipboard window chrome. Retain current typography, bar dimensions and dense spacing. Add consistent striped rows, whole-row hover, sorted-column emphasis, and accessible stable sorting for meaningful visible columns. Do not make the table wider/taller or add scrolling without demonstrating why it is unavoidable. Do not change what next opponent data represents, backend ordering or any simulation behavior. Keep true rank/seed semantics on other tables untouched.

Only edit GUI files and focused frontend tests. Do not edit Python, ratings, contracts or performance notes. If required data is missing, report the backend dependency instead of inventing values or crossing ownership boundaries. Do not change the other four tables yet.

Verify keyboard sorting, numeric/missing values, ties, selection/hover contrast, unchanged W/L playback hooks and desktop/mobile rendering. Obtain a quiet test window before heavy browser tests so you do not contaminate the performance chat's benchmark timings. Use an isolated preview/disposable fixture, not a live game. Do not restart the performance or playable servers.

Write the five-by-five coverage matrix and before/after screenshot paths to docs/UI_COMPLETION_TABLE_REVIEW.md. Include preview URL, data fixture and tests. Stop for user approval of this one table before propagating styles. Do not mark the backlog accepted yourself.
```

## Ready-to-Paste First Research Assignment

```text
You own the research-only ratings lane. Read docs/MINIMUM_COMPLETION_BACKLOG_2026_10_29.md and docs/USER_COMPLETION_NOTES_2026_10_29.txt. Follow R01-R06, but do not edit any game code, production data, ratings or saves. Another chat is benchmarking the engine.

Create docs/ratings-evidence-2026-10-29/ outputs only. Inventory all 11 supplied NerdSesh videos: exact URL, title, publication date, transcript availability and provenance. Obtain legitimately accessible transcripts/captions where possible. Never claim to have heard/read content you could not access; flag missing sources. Do not install a large toolchain or download whole videos just to bypass missing transcripts.

For the first bounded deliverable, extract TWO representative accessible videos. Record timestamped speaker attribution, player/rank/trait claims, reasons, disagreement, uncertainty, injury context and whether claims concern current ability or future ceiling. Paraphrase; do not reproduce long copyrighted transcripts in the final report. Keep the source index so later work does not repeatedly fetch the same evidence.

Inspect repository data enough to identify the intended starting-season/date and existing imported-rating scale/version. Do not treat October 2026 commentary as automatically applicable to every game snapshot. Flag that calibration-date choice for user approval.

Separately verify Dame's contract provenance and gather initial evidence for Dylan Harper, Sochan and Luka. Distinguish the user's hypotheses from supported findings and seek independent corroboration. Do not turn podcast ranking positions directly into OVR or change the prospect/development system.

Deliver the full 11-source access ledger, the two evidence extractions, a proposed evidence-to-trait mapping with explicit uncertainty, named-player/contract findings and questions needed before the broader pass. Stop for review of the method. Do not change the coordinator checklist or claim any ratings correction is implemented.
```

## Completion Evidence

Code/test completion and user approval are separate. Every UI batch needs representative real-data screenshots, keyboard checks, no new horizontal overflow, and the correct running backend/build. Backend changes need targeted tests and bounded gameplay proof; ratings changes need sourced reasoning and calibration checks. Required minimum features do not replace a final regression/release check. Preserve unresolved older concerns (for example simulation speed and any still-open box-score/league-health issues) separately rather than declaring this notes list exhaustive.
