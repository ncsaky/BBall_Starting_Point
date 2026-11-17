# Multi-Team Market, October 28, 2026

## Delivered

- Directed asset transfers for connected three-to-six-team packages. Each GM evaluates its complete incoming/outgoing package, not a sequence of bilateral trades.
- Atomic settlement on a private save copy. Current ownership, salary, roster counts, conditional rights, recent transactions and all non-human approvals are checked again before committing. One transaction records every leg. Failure leaves the authoritative save unchanged.
- The existing multi-team builder can evaluate and execute these packages. All receiving teams, player evidence, GM decisions and payroll changes are displayed. Incoming three-team offers use the same settlement path and require explicit user acceptance.
- Automatic facilitator search can redirect a matching player, or send an additional non-core contract to a third team. The third team must genuinely want the player or approve being compensated for the contract. Returns include firsts, seconds and paired seconds; no acceptance thresholds were loosened.
- Automatic top-four/top-ten first-round protections use a real, later first as fallback. The compiler, pricing, collateral reservations and live settlement retain the actual obligation.
- Search is bounded to 16 near-miss team pairs, four additional outgoing-player options per original team, five potential facilitators per route, 16 full evaluations per near-miss and 64 total per search call. Cheap financial/roster checks prune impossible routes first.
- A materially better joint agreement can replace one weaker, conflicting tentative bilateral proposal. Joint proposals compete for date-level execution slots on approved combined value instead of always sitting at the end of the queue. Completed transactions are never replaced.

No ratings, development parameters, annual trade-opportunity schedule or acceptance thresholds changed in this pass.

## Observed Market Activity

`output/multi-team-2026-10-28/final-actions17/` advances an existing disposable seed-17 career from January 31 to February 3 through the real app-action path. Test-only pressure is three times the ordinary opportunity count, with search depth three. This is a stress test, not a target for normal season frequency.

The unchanged-engine run completed in 251.79 seconds, with 15 committed trades and 27 delivered offers. Two committed trades have three participants:

1. February 2: Sacramento sends Domantas Sabonis to Oklahoma City. Oklahoma City sends Nikola Topic, Kenrich Williams, Alex Caruso and its 2027 first to Sacramento; Isaiah Hartenstein goes to Chicago. Chicago sends its 2032 first to Oklahoma City. All three current evaluations approve.
2. February 3: Chicago sends Norman Powell to Boston. Boston sends Luka Garza, Devin Carter, Neemias Queta and its 2028 first to Chicago; Mitchell Robinson goes to Washington. Washington sends two 2027 seconds to Boston. All three current evaluations approve.

The same career contains 11 delivered three-team user offers, including subsequently stale offers. These are not 11 extra completed trades. Normal asset-conflict invalidation still applies.

Two newly created top-ten protections were actually committed: Minnesota's 2027 first, held by Phoenix, with Phoenix's 2028 first as fallback; and Utah's 2029 first with Utah's 2030 first as fallback. Two new swap grants also committed. The summary's three protected-pick transfers include existing protected rights, so that count is not the number of newly created protections.

The saved-career read-only probe independently found an Atlanta/Boston/Chicago agreement involving Nickeil Alexander-Walker and Mitchell Robinson. Settlement of that exact proposal succeeded on an isolated copy. No source career was written. A separate July-1 seed-29 probe found four automatic protection candidates but no all-party-approved facilitator package. Search must be allowed to fail.

All-party approval establishes consistency with the game's current GM model, not proof that every price is realistic. The substantive quality of these returns still merits review.

## Verification

- 147 focused Python tests pass, covering multi-team settlement, salary boundaries, premium returns, pick rules, presentation, offer handling, waivers, release planning and simulation consistency.
- 56 JavaScript tests pass for workspace navigation, routing, pick terms, profiles, payroll, projections, declines and phone notifications.
- Twelve dedicated multi-team tests cover salary aggregation, facilitator discovery, atomic commit, replay, stale ownership/salary, forged approval, explicit human consent, serialization/reload, protected rights, new swap grants, injected mid-settlement failure, connected four/six-team graphs and real app-action persistence.
- Final production-configuration daily versus bulk runs both reach February 3 from January 31, seed 17. Business-state comparisons match exactly: five trades, nine offers, 24 games, roster cuts, signings, waivers, rosters, contracts, development and remaining compared state. An earlier two-seed check also matched before the final proposal-priority adjustment; it is not substituted for the final-code comparison.
- The browser test evaluates a real three-team package, checks three payroll projections, verifies desktop/1024/390px layouts, explicitly executes it, checks every destination and verifies exactly one durable transaction. Final run has no page errors.
- No full-year or multiseason simulation was started. Every new career used for this work is under the evidence output directory.

Principal evidence: `final-summary.json`, `final-actions17/market-events.jsonl`, `final-actions17/saves/trade_year.json`, `deadline17-final-probe.json`, `parity-final/final/report.json` and `browser.json` beneath `output/multi-team-2026-10-28/`.

## Supporting Repairs

- Exact player IDs now win over substring name matches. Previously a synthetic ID such as `b1` could select `b10`, which is unacceptable for a routed settlement.
- A locked, unresolved imported pick obligation can be displayed as unavailable without crashing the entire team's asset list. It remains untradeable; no missing terms were invented.
- Fixed an existing malformed template literal that prevented the assistant-phone script from loading.
- Kept three-team decision panels compact and responsive using the existing trade-window styling.

## Limits

- Automatic search creates three-team facilitator packages, not arbitrary four-to-six-team negotiations. The builder supports those larger graphs.
- The ordinary finder remains primarily bilateral; this is not exhaustive multi-team optimization for every requested asset.
- Packages involving more than one human-controlled team fail closed pending a proper shared-consent workflow.
- Existing simplified financial/Stepien rules remain the game's rules. This does not implement every NBA trade exception, cash route, automatic pre-trade cut, buyout or stretch arrangement.
- Facilitators currently exchange a single diverted/additional player for draft compensation. More involved player-for-player facilitator routes remain possible future work.
- Normal-frequency annual calibration and broader price/return-quality review remain separate from this bounded stress validation.

The main preview on port 8776 was observed running a simulation and was not interrupted. The isolated preview on port 8780 uses only this task's disposable saves.
