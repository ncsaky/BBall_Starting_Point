# Elite Trade Market and Decision Explanations

## Scope

Bounded searches of 90+ displayed-OVR players, preserved historical packages, two real-action checkpoint continuations, and a correction of misleading valuation presentation. No player ratings, development, transaction quotas, acceptance limits, premium-return rules or core commitments were changed. Source careers were not written; simulations use exported disposable copies.

## What the checks actually show

- Seed 29: 27 non-user 90+ targets searched from the GSW checkpoint; no approved Finder result. Seed 17: 27 non-OKC elite targets searched with OKC as the alternative buyer, including 92+ players; no approved result.
- The OKC search evaluated 486 proposed packages. Of 972 team evaluations, 944 rejected legality, 14 accepted, eight rejected value and six rejected premium returns. The commonest legality failure was insufficient outgoing salary (435 packages). Therefore zero approved Finder results does NOT establish fair star pricing. It identifies a separate salary-aware package-search limitation.
- Four old packages were repriced without changing their historical player data or recorded manager adjustments: Trae/Grant/Adams, Siakam/Turner/Powell/picks, Kawhi/Bridges/DiVincenzo/Joe, and Kawhi/George/Scheierman/picks. None received consent from everyone. Rebuilding strategic states with the current classifier also left all four rejected.
- The old Toronto/Boston package is especially informative: Toronto's raw aggregate appraisal remains positive, but its rebuilt entering-window state rejects the inadequate premium return. A high additive score is not sufficient to trade a premium contributor. This is why showing only an acceptance meter was misleading.
- Frozen records preserve historical valuations and contracts. They are not a new empirical calibration of today's ratings. Finder samples are proposals, not executed trades, and target only two buyer situations.

## Real-action continuations

Deadline seed 17: February 3 to the February 5 deadline, 163.77 seconds. The observer recorded 15 NEW durable trades, including one three-team trade. The census's 20 February trades includes earlier source history; it must not be called 20 new trades. The three-team exchange involved Detroit, the Clippers and Miami, with players and actual second-round assets moving between them. Every participant sent and received consideration. There were no 90+ players in these new trades.

The deadline continuation created seven incoming-offer entries and the summer continuation created five. Neither set includes a player currently displayed at 90+. This is a limited negative result, not validation of elite incoming-offer pricing.

Summer seed 29: July 1 free-agency continuation, 206.83 seconds. The production `advance_free_agency(mode=end)` action completes the phase and ends September 1, so this was NOT a same-endpoint July 3 comparison. It produced four new player trades, including a missed-free-agent-target fallback, and the final ledger contains four buyout agreements and two waiver claims. No 90+ players moved in those four trades. No new draft simulation was launched; draft frequency is not revalidated here.

One actual summer deal had New Orleans sending Dejounte Murray to Cleveland for Peyton Watson and a first. Cleveland's projected roster strength improved +1.21 but its value ledger was -3.73, so existing bounded negotiation discretion permitted consent. Previously the record still said "rejects" and labeled both GMs as exceptions. The explanation now identifies the exception only for the GM who needed it, without changing whether the trade is permitted.

Small moves also changed some discrete phase labels. Boston went from rank 6 to 8 after a depth consolidation, crossing peak to exiting despite a small measured strength change. This is a warning against presenting phase segments as a precise continuous clock or implying that every phase boundary crossing is intentional. No forced phase-order rule was added.

## Corrections

1. `TradeEvaluation` now carries the actual contextual threshold, window phase, incoming package value, strategic adjustment and explicit rejection reasons. The old payload substituted the generic team threshold for the actual deal threshold.
2. The displayed arbitrary 0–100 acceptance number is replaced with the signed value margin above/below the actual requirement. The diverging asset charts remain. Meeting the value line does not hide a premium-return, core, roster or legality rejection.
3. The receiving-team breakdown now uses the same outgoing-player removal, non-spatial fit, role multiplier, extra health deduction, recent-acquisition premium and concentration adjustment as the package ledger. Age/contract modifiers are no longer added again at package level. Tests reconcile both totals and individual segments.
4. Compact expandable explanations distinguish listed market reference, destination-specific role value, package adjustment, strategic/roster effects and manager lean. The legend explains negative role and age/upside components. Headers name which team values the outgoing assets.
5. All four display phases use rebuilding, entering peak window, peak window and exiting peak window. `retooling` remains an internal compatibility mapping of exiting; it is not a separate fifth classifier. Removing that mapping alone would break existing policy consumers, so it was not deleted.
6. Older saved charts are explicitly labeled archived estimates and offer re-evaluation in the builder. Historical decisions are not silently rewritten using today's roster. Legacy meter thresholds prefer the original decision notes over the old incorrectly substituted payload threshold.
7. A stale decline regression expected a second identical offer to survive rejection. The fixture differs only in ID; it now correctly expects both duplicate entries to resolve, consistent with the approved grouping behavior.

## Verification and Evidence

- 134 focused Python tests pass, including presentation reconciliation, premium/core safeguards, role forecasts, wants, multi-team settlement, salary application, negotiation discretion, pick investment and simulation consistency.
- 57 JavaScript tests pass across explanations, inbox responses, workspace state, payroll, pick terms and rotation/identity previews.
- Playwright renders a preserved real trade's enhanced evidence on desktop and mobile; verifies visible premium-return rejection, expandable explanations, modal width and Escape dismissal. Screenshots were inspected. No page errors.
- Evidence root: `output/elite-market-2026-10-29/`. Main files: `seed29.json`, `seed17-full.json`, `deadline17/market-events.jsonl`, `summer29/market-events.jsonl`, and `ui/report.json`.
- Both checkpoint continuations reported an unchanged engine during their runs. Subsequent changes clarify negotiation metadata and version chart output; they do not change acceptance limits or simulation mechanics. No claim is made of a final full-year frequency calibration or another ten-season study.

## Next Target

Salary-aware elite-package construction deserves a separate bounded pass: prioritize genuinely feasible salaries before truncating candidate lists, while retaining the existing seller safeguards. Also inspect the stability of phase boundaries before adding a before/after circular forecast graphic. This pass does not establish that all 90+ prices are correct, nor justify a blanket star-price increase.
