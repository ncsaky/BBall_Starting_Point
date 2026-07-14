---
type: history
status: current
reviewed: 2026-07-10
tags:
  - history/failures
  - quality/regressions
  - project/nba-gm
---

# Failure Museum

The purpose of this note is not embarrassment. These bugs reveal where the true domain boundaries are. Each category names the violated invariant and the general lesson.

## 1. Protected Pick Self-Fallbacks

**Symptom:** A label claimed a protected pick would fall back to the exact same pick. Example shape: POR owns a protected CHI first, CHI keeps it in the protected range, and POR “instead receives” that same CHI first.

**Violated invariant:** `primary_pick_id != fallback_pick_id`.

**Root cause:** Startup prose/partial terms were merged without end-to-end structural validation, and different views formatted raw annotations.

**Lesson:** Validate obligations after every creation/load/merge/apply path and generate every label from one structured record. See [[Systems/Pick Obligations and Swaps]].

## 2. Lottery Reveal And Draft Order Disagreed

**Symptom:** The lottery reveal showed one owner at picks 4, 6, or 10 while the live draft selected for another.

**Violated invariant:** reveal, saved order, asset owner, and live queue share one exact pick ID/owner.

**Root cause:** One path refreshed final ownership after protection resolution while another rebuilt state from baseline/team ownership.

**Lesson:** Persist the resolved order once and rebuild all views from it. Add uniqueness/repair guards before display and selection.

## 3. Trading One Draft Pick Moved Two

**Symptom:** Acquiring one current-draft pick changed multiple slots owned by the seller.

**Violated invariant:** ownership mutation targets one exact `pick_id`, never “all picks owned by team.”

**Root cause:** Current-year pick identity was inferred from owner/round and similar assets were deduplicated.

**Lesson:** Identity is not a display label. Include slot/overall-pick identity in current-draft assets. See [[Architecture/Determinism and Identity]].

## 4. Finder Offer Rejected At Apply

**Symptom:** Trade Finder displayed “AI side should accept: yes,” then “Accept and execute” returned `not_applied_rejected`.

**Violated invariant:** a surfaced incoming finder offer has already been accepted by its AI source unless state changes invalidate legality.

**Root cause:** Proposal provenance and accepted response state were lost/recomputed, while apply logic treated every stored proposal like a newly submitted user builder offer.

**Lesson:** Authorization is distinct from legality. Store offer origin and explicit acceptance; apply must validate the contract of the originating workflow.

## 5. Rejected Trades Could Be Applied

**Symptom:** An AI response showed both teams reject but still offered “Apply legal trade now?”

**Violated invariant:** legal does not mean accepted.

**Root cause:** User override behavior intended for the user's own advisor was generalized to partner rejection.

**Lesson:** Separate user-controlled consent, partner consent, advisor recommendation, and mechanical legality.

## 6. Extensions Erased Current Salary

**Symptom:** After a midseason extension, the player's active-season contract showed `-`, while future salary remained.

**Violated invariant:** future extension years append to the active contract rather than replace it.

**Root cause:** A contract override replaced the whole salary table.

**Lesson:** Temporal aggregates need merge semantics. Test the dashboard and trade views after application, not only the negotiation record.

## 7. Retired Players Signed Future Deals

**Symptom:** A player signed an extension or re-signed, then retired before the contract began.

**Violated invariant:** retirement eligibility/timing is resolved before committing incompatible future years.

**Root cause:** Retirement and contract phases were ordered independently.

**Lesson:** Lifecycle ordering is a domain rule. See [[Architecture/Season State Machine]].

## 8. Starting Injuries Destroyed Star Value

**Symptom:** Elite players such as startup-injured stars had trade values around deep-rotation assets because they had 0 MPG and 0 games.

**Violated invariant:** established full-health ability and role remain present during a one-off current injury.

**Root cause:** low-current-minutes guardrails intended for unknown fringe players also capped established stars.

**Lesson:** Separate skill, opportunity, current availability, rust, and recurring durability risk. Validate edge cases at season start before current stats exist.

## 9. Released Free Agent Accumulated Ghost Stats

**Symptom:** A cut player appeared in no team box score but season totals continued to grow while unsigned.

**Violated invariant:** only active players on the game's two rosters receive new logs/stat game IDs.

**Root cause:** downstream stat aggregation trusted a stale rotation/player pool.

**Lesson:** Guard at the write boundary, not only at lineup construction. Preserve historical totals but reject new unrostered lines.

## 10. Strong Released Player Never Signed

**Symptom:** A user could cut a valuable player, and every AI team ignored him during the season.

**Violated product expectation:** meaningful available talent should attract legal AI interest.

**Root cause:** normal free agency handled offseason periods but lacked an in-season released-player market hook.

**Lesson:** User freedom creates rare but legal states; AI lifecycle coverage should include them without forcing signings for replacement players.

## 11. Same-Day Sign-And-Trade

**Symptom:** An AI signed a player and traded him on the same free-agency day.

**Violated invariant:** recently signed players are ineligible until the modeled December threshold.

**Root cause:** trade candidate generation did not share the same legality restriction as apply or did not record signing date soon enough.

**Lesson:** Filter candidates for UX, validate again at apply, and persist restriction metadata atomically.

## 12. Stale Rotation And Starting Five

**Symptom:** Departed/retired players remained in coach minute recommendations or visual lineups; injured manual starters did not substitute correctly.

**Violated invariant:** active recommendations reference current roster members; injury substitution is temporary and reversible.

**Root cause:** display state outlived roster/health state.

**Lesson:** Derived user preferences need prune and restore semantics. A manual lineup is saved intent, while the effective lineup is health-aware output.

## 13. Rookie Of The Year Twice

**Symptom:** The same player won ROTY in multiple seasons.

**Violated invariant:** ROTY eligibility is the first active league season only.

**Root cause:** rookie status was inferred from age/draft recency without a consumed eligibility marker/history check.

**Lesson:** Eligibility is stateful. Archive award/season participation and test across rollover.

## 14. AI Actions Piled Up Until Deadline

**Symptom:** Simulating directly to the trade deadline delayed AI-AI trades so they all applied at the deadline rather than throughout prior months.

**Violated invariant:** action date and decision context reflect the chronological checkpoint where the action occurred.

**Root cause:** long-range sim treated AI operations as one post-range batch.

**Lesson:** A one-click UX can still run hidden chronological checkpoints. Do not skip causal history for convenience.

## 15. Top Draft Pick Too Cheap

**Symptom:** Pick #1 moved for #6 plus only a future second; large move-ups were common.

**Violated product expectation:** top picks have strongly convex value and class-specific scarcity.

**Root cause:** pick curve too flat and package balancing treated a second as sufficient scalar sweetener.

**Lesson:** Test package shapes, not only individual values. Use hard tier requirements for extreme move-ups alongside continuous valuation.

## 16. Unknown Bench Players Had Elite Ratings

**Symptom:** low-evidence deep-bench players ranked among league leaders in multiple traits.

**Violated invariant:** low evidence does not justify elite certainty.

**Root cause:** percentile proxies and sparse sample noise could land at distribution extremes.

**Lesson:** Use confidence-weighted blending and fringe caps. Human calibration should pull known rotation players more than unknown fringe cases.

## 17. Standings Looked Right While Players Looked Wrong

**Symptom:** Yearly team standings were plausible despite absurd individual ratings or stat leaders.

**Violated validation assumption:** aggregate success implies component correctness.

**Root cause:** errors canceled at team level and broad feature averages masked player-level anomalies.

**Lesson:** Validate at league, team, archetype, player, and tail-distribution levels. See [[Systems/Ratings and Traits]].

## 18. Narrative Used Real-World Memory

**Symptom:** Tweets placed players on old teams, discussed unsupported injury histories, mixed conferences, or described real-world roster relationships absent from the save.

**Violated invariant:** generated factual claims are limited to the context packet.

**Root cause:** prompt-only grounding was insufficient; model priors filled context gaps.

**Lesson:** Ground with exact compact facts, validate names/teams/direction/cap/ranks, and fall back on failure. The model is an untrusted renderer.

## 19. Narrative Money And Rank Errors

**Symptom:** The model divided AAV as though it were contract total, called healthy cap space “apron pain,” or treated a team playmaking rank as the player's rank.

**Violated invariant:** numeric claims preserve their semantic labels.

**Root cause:** compact context exposed numbers without enough typed meaning, and validation was initially lexical rather than semantic.

**Lesson:** Context should carry explicit field names/units and validators should compare claims against modeled posture.

## 20. Narrative Fallback Repetition And Truncation

**Symptom:** Many identical canned lines appeared; long evidence was cut mid-word/bracket.

**Violated UX expectation:** users can distinguish fallback and read complete evidence.

**Root cause:** strict validation caused many failures, a small fallback pool repeated, and body text used hard slicing.

**Lesson:** Color/label fallback, wrap instead of slice, cache valid generations, inspect provider errors, and repair missing evidence before discarding otherwise useful text.

## 21. GUI Layout Drift

**Symptom:** Cards overlapped, left awkward gaps, or changed unrelated widths after one local adjustment.

**Violated invariant:** structural neighbors share layout tracks rather than independent pixel offsets.

**Root cause:** rapid CSS iteration used local dimensions and positional fixes instead of a stable grid composition and visual tests.

**Lesson:** Encode relationships with CSS Grid, min/max constraints, and named areas. Use screenshots at defined viewports as regression artifacts. See [[Product/Dashboard Design]].

## 22. Unknown GUI Action After Refresh

**Symptom:** The frontend requested an action name the running backend did not know.

**Violated deployment contract:** frontend and action API versions are compatible.

**Root cause:** stale server process or changed client assets without coordinated backend restart/version check.

**Lesson:** Expose an API/build version in the bootstrap payload, fail with a clear “server update required” message, and automate dev-server restart where possible.

## The General Pattern

Most severe bugs involved duplicate representations of one truth:

- label versus structured pick state;
- current contract versus override;
- cached rotation versus roster;
- reveal order versus draft order;
- generated narrative versus event facts;
- GUI state versus server action version.

The reusable cure is to name one authority, derive all views from it, define invalidation, and test the complete lifecycle.

## Related Notes

- [[Quality/Testing Strategy]]
- [[Architecture/Persistence and Mutation Safety]]
- [[Learning/Interview Defense Guide]]

