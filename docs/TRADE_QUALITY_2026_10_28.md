# Trade Quality, October 28, 2026

## What Was Wrong

The market could approve a package whose individual asset prices looked attractive even though its final rotation was substantially worse. It also credited incoming players that the receiving team would immediately waive, without consistently pricing the additional cut and remaining guaranteed salary into that trade.

The clearest preserved example is Boston's three-team Norman Powell package. Boston sent Luka Garza, Devin Carter, Neemias Queta, Mitchell Robinson and a first, receiving Powell and two seconds. Its healthy roster-strength estimate fell 1.4173 points and its league rank fell from fourth to twelfth. The old Boston evaluation was positive, +3.084. The same frozen package now scores -2.585 and is rejected for its roster consequences. Boston saved only about $1.11M in current salary; that did not justify the rotation loss.

The historical stress career also shows San Antonio acquiring Jae'Sean Tate and waiving him on the same date. That is evidence of the incoming-filler accounting problem, not proof that every trade followed by a cut is wrong.

## Implemented

- `trade_roster.py` forecasts a healthy final roster using the existing retention scores, roster limit and 240-minute rotation model. User-set minutes are not overwritten.
- Trade evaluations include the before/after rotation change, foregone value of additional cuts, and remaining guaranteed or conservatively reserved salary. Incoming players predicted to be cut receive no retained-player credit. Already-required baseline cuts are not charged twice.
- A competing team rejects a material rotation loss unless it has an existing core-review/injury exception, a materially costly principal contract to exit with meaningful salary relief, or an entering-window exchange for a credible young foundation. Cheap, bad filler cannot excuse trading a healthy premium contributor. Rebuilding teams may deliberately sacrifice present strength.
- A live bilateral application rechecks hard roster objections against the latest save before mutating it. Multi-team settlement continues to reevaluate every AI party. Explicit human consent is not replaced by an AI roster preference.
- Hopeless packages are rejected cheaply before computing expensive final rotations. Forecasts use only relevant roster traits and a bounded runtime cache. The finder inspects more existing package alternatives instead of loosening acceptance to retain its former first few results.

The -0.75 competing-strength guard and cost weights are game policies, not measured NBA championship probabilities. This is not a blanket premium-player price increase.

## Exact Replay

`output/trade-quality-2026-10-28/optimized-replay.json` replays both preserved three-team trades against their original rosters, skills and contracts:

| Package | Result | Final AI evaluations |
| --- | --- | --- |
| Powell to Boston, Robinson to Washington | Rejected | BOS -2.585; CHI +31.604; WAS +25.580 |
| Sabonis to OKC, Hartenstein to Chicago | Still approved | CHI +10.744; OKC +35.860; SAC +14.977 |

The Sabonis package does not face an automatic veto for OKC's small -0.3354 strength change or Sacramento's intentional rebuilding step back. Chicago's and Sacramento's projected additional waiver costs are included.

Of 27 historical delivered offers, 17 remain pending in the final save. Current-state review finds two AI sides with hard roster objections and seven sides whose incoming packages contain predicted cuts. These are final-date inbox checks, not invented offer-time reconstructions. Three pending offers also have other current legality problems. The source career's hash remains unchanged.

Filtering forecast inputs to relevant player traits produced exactly the same frozen-trade and full-inbox decision reports as the unfiltered implementation.

## Normal-Frequency Checks

Both final runs use ordinary production opportunity counts, not the preceding stress test's three-times pressure. Each advances a disposable January 31 career to February 3, 2027, using identical user policy: ignore incoming offers, retain staff and resolve required cutdowns. Engine fingerprints were unchanged throughout each run.

| Seed | Committed trades | Delivered offers | Committed three-team trades | Delivered three-team offers | Seconds |
| --- | --- | --- | --- | --- | --- |
| 17 | 5 | 9 | 1 | 5 | 186.83 |
| 29 | 7 | 10 | 2 | 6 | 193.28 |

Delivered offers include subsequently stale offers; they are not completed transactions. These three-day samples do not establish a full-season frequency target.

Seed 17 still creates a protected first and a swap. Both seeds complete a Sabonis/OKC/Chicago facilitator deal. Seed 29 also completes a Powell/Philadelphia/Detroit/Chicago route. All observed entering/peak teams remain in those respective phases. This does not prove that every price is good.

In seed 17 the actual additional cuts are Jordan Hawkins, Daeqwon Plowden and Tristen Newton, matching the Sabonis package's forecast cut identities. Their salary obligations remain recorded. Seed 29 still has a trade-then-cut case involving Justin Edwards; retaining zero player credit and paying the cut cost can be rational when the rest of the return justifies it. The system intentionally does not ban that sequence.

Evidence: `verified-normal17/`, `verified-normal29/` and `verified-analysis.json` beneath the output directory above. Committed observer events are joined to durable transaction history; request-local attempts alone are not counted.

## Regression Verification

- The final focused 173-test Python suite passes (70.924 seconds). The saved-approval regression covers file application, app application, candidate application and incoming-offer acceptance, with rejected files byte-identical.
- Eleven dedicated roster tests cover competing rotation losses, rebuilding/retool/financial exceptions, credible young returns, cut-player credit, unknown obligations, baseline cuts, bounded caching and invalidation, all-party evaluation and unoverridable roster rejections.
- Final-code real app-action daily versus bulk advancement matches exactly from January 31 to February 3. Both have five trades, nine offers, 24 games, three cuts, two depth signings and three waiver clearances. Full compared business state includes rosters, contracts, health, development and transaction history, excluding incidental timestamps, revisions and storage paths.
- Daily mode took 169.919 seconds; bulk took 166.673 seconds. This is a bounded correctness test, not a claim that long simulation performance is solved. New forecasting has a cost; eligibility pruning, relevant-trait inputs and caching reduce it.
- Scoped whitespace checks and compilation pass. No multiseason run was started. Earlier interrupted disposable runs and runs whose engine fingerprint changed are excluded from final proof.

Parity evidence: `parity-final/verified/report.json`. Existing playable saves, ratings, development and UI were not changed by this task.

The isolated development preview on port 8780 was confirmed idle and restarted on the verified backend. The main preview was not stopped or restarted by this task.

## Remaining Problems

The important next price review is spending draft capital for marginal depth. Seed 17 Cleveland sends Riley Minix and a top-ten-protected 2028 first, with a later first fallback, for Jevon Carter; its modeled strength rises only 0.14. New York spends Drew Eubanks and a second for Trey Lyles without changing its best healthy rotation. Existing bounded-discretion approvals help these packages pass. These are concrete next cases, not resolved by the roster-loss fix or by the absence of automated review flags.

The planner estimates healthy roster strength, not every injury-insurance scenario, succession plan or future championship outcome. Current bilateral application vetoes hard roster objections but does not fully reprice every old offer; multi-team application does perform fresh participant evaluations. Wider annual trade-price and frequency calibration remains separate work.
