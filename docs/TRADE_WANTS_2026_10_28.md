# Team Wants

## Delivered

- Separate Team Wants card in the Front Office gallery. Team Block's layout is unchanged.
- Six manually published priorities: custom player conditions, young upside, rotation help, upgrade a roster player, and draft capital. Conditions combine with AND; positions combine with OR; profiles are alternatives.
- Player conditions use Player Finder's displayed ratings, age, height, upside, injury-risk index and current/future contract information. Unknown data cannot satisfy a condition. One small numeric miss may be labeled a near match.
- Pick preferences use rolling upcoming-draft ranges, round, protection tolerance and quality. Actual draft years appear in the card. An existing swap is not advertised as ownership of an unprotected first; locked fallback collateral cannot generate an acquisition reminder.
- User wants start empty. Suggested wants are optional. Editing, reordering and removing require explicit user action. Upgrade requests invite proposals involving the incumbent without changing Team Block or giving permission to trade.
- Users can inspect other teams' wants. Trade workspace asset lists show the owner's wants; incoming and Finder results label backend matches, including multi-team recipients.
- Matching acquisitions produce one dismissible reminder after playback ends or an ordinary decision stop. Reviewing/keeping does not remove wants; dismissal is acknowledged persistently. Stale upgrade targets become inactive, but their saved reference can still recognize the replacement acquisition.

## AI and Pricing

AI wants are derived from the existing window/core plan, not an independent phase classifier. Existing deterministic planning reviews refresh at most three AI priorities; stable priorities retain their order. Core commitments, legality, premium-return rules, final-roster costs and draft-investment checks remain authoritative.

The existing roster produced 22 distinct suggested profile lists across 30 clubs. Suggestions include complementary positions around existing foundations, specific skill deficiencies, youth/succession, injury cover and non-core upgrades. Affordability adjusts the requested quality; final financial approval still uses the established contract and roster checks.

Matching influences buyer routing and the assets considered for a return. Additional willingness to pay is capped at 5% of matched neutral asset value and four valuation points per team/package, after subtracting overlapping existing fit credit, including the rebuilding pick and contender rotation bonuses. Duplicate profiles and duplicate asset appearances do not stack. Quote construction can seek half that extra willingness, but this is neither an automatic charge nor another acceptance bonus. Strong unmatched offers remain possible.

## Center Opportunity Fix

The real Gobert/Zubac check uncovered an inflated forecast: Indiana could be assigned 41 Gobert minutes plus 35 Zubac minutes. The trade forecast now shares 48 minutes between non-spacing, center-only players and reallocates the excess to other rotation players. This is a private forecast, not a change to real rotations, ratings or game simulation.

In the tested starting roster, acquiring Gobert for Nembhard while retaining Zubac changed the estimated strength gain from +1.0942 to +0.2035. The forecast allocates 25.89/22.11 center minutes and identifies the 30 complementary guard minutes lost. It applies a -3.8517 opportunity adjustment. Sending Zubac instead, or covering his injury, avoids that redundancy adjustment. Evidence: `output/trade-wants-2026-10-28/center-scenarios.json`.

## Verification

- 132 focused Python tests cover matching, actions/authorization, revisions, reminders, persistence, core plans, salary boundaries, premium returns, roster impact, multi-team settlement and draft-investment safeguards. Seven separate multiplayer tests pass.
- 51 JavaScript tests pass across wants, trade workspace, profiles, payroll and pick terms, including late-response protection when switching saves.
- Actual browser checks exercised add/edit/reorder, AI read-only browsing, Escape, reload persistence and desktop/mobile sizing. No page errors; the card body measured 618/618 horizontal and 97/97 vertical content/viewport pixels. Hover text remains dark; buttons have no gradient. Screenshots and metrics: `output/trade-wants-2026-10-28/ui/`.
- Real-action parity runner uses seeds 17/29, manually published wants, January 30–February 1, daily advancement with an exported/restored midway save versus bulk advancement. It compares complete business state and repeats the completed endpoint to check duplicates. Both passed after the center fix (`output/trade-wants-2026-10-28/final-roles-parity/report.json`) and again after the final bonus-overlap correction (`verified-offsets/report.json` and `verified-offsets-29/report.json` under the same directory). Seed 17 produced three offers/one trade; seed 29 produced six offers/three trades. Each path played 16 games. Full business state matched exactly, and repeated endpoints added no duplicate activity.
- Earlier five-day October/November comparisons also matched exactly for both seeds, covering 36 games per path.
- Existing-checkpoint market probes after the center fix, before the final bonus-overlap tightening: seed 17 found 23 approved proposals, 13 matching wants; seed 29 found 21, 12 matching wants. Remaining proposals were not suppressed. These are independent read-only market searches, not 44 completed transactions or annual trade counts. Both probes exhausted their bounded facilitator search without an approved three-team deal; no natural multi-team-frequency claim is made. Results: `output/trade-wants-2026-10-28/market-summary.json`.
- Stress searches took approximately 89/68 seconds for 12,809/9,538 package checks. A preliminary same-seed no-wants comparison examined fewer packages; it is not a clean isolated performance benchmark. No transaction quotas were raised.

## Limits and Preview

Wants remain soft preferences, not promises of available assets or proof of a good trade. AI suggestions and the bounded premiums are initial policy, not calibrated championship or draft probabilities. The center forecast correction is narrow, not a complete lineup optimizer. Annual transaction balance and long-term league health were not rerun in this task.

Preview: http://127.0.0.1:8783/ using the normal saves directory. The busy existing server on 8776 was left alone. Verification used only isolated saves. No packaging, ratings edits, heatmap edits or playable-save deletions were performed. Existing whitespace warnings in untouched startup HTML lines remain outside this change.
