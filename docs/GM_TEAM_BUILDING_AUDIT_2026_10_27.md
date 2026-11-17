# GM Team-Building Audit

Implementation update: the source-timeline override, stale strategy/contract
cache reuse and fixed-year near-term pick counting were repaired in the bounded
live-strategy pass. See `LIVE_STRATEGY_V2_2026_10_27.md`. The findings below
describe the audited pre-fix behavior. Guarantee negotiations and waiver
accounting are now covered by `CONTRACT_PROTECTION_2026_10_27.md`; the first
persistent planning and roster-space trade pass is described in
`GM_PLANNING_V1_2026_10_27.md`. Neither is a claim that the entire proposed
championship-window optimizer or complete waiver/buyout system is finished.

## Agreed Product Direction

The goal is championship opportunity across multiple seasons, not merely
maximizing the current sum of player values or reaching the playoffs repeatedly.
The user approved **commitment with exceptions**: after a major star acquisition,
normally build around the resulting core through a meaningful season, while
allowing reassessment for a serious injury, a trade demand or an exceptional
offer. These exceptions should trigger a reasoned review, not automatically
force a teardown.

Keep the **21-player offseason allowance**. Signing a better player before
releasing inferior depth is legitimate. The problem is not a roster count above
15; it is paying for a player the team already has good reason to discard,
promising a nonexistent role, or dropping a core without a coherent change of
direction. This audit makes **no AI strategy/bidding/trade/cutdown changes**.

## What Already Exists

| Area | Existing mechanism | Code |
| --- | --- | --- |
| Team direction | Phase, contention index, core age, youth, picks, health, salary posture, needs and excesses | `transactions.py:244` |
| GM differences | Competence, discipline, star preference, patience/pressure and bounded discretion | `transactions.py:147`, `transactions.py:3814` |
| Player value | Current impact, age curve, upside, salary surplus, health, scarcity and playoff value | `transactions.py:294` |
| Trading fit | Phase/age compatibility, needs, role concentration, destination minutes and spatial fit | `transactions.py:3557`, `transactions.py:3699` |
| Acquisition protection | 60-day re-trade exclusion and a decaying 60-to-180-day acquisition premium | `transactions.py:1194`, `transactions.py:3647` |
| Free agency | Salary/roster legality, team needs and fit, player money/role/winning preferences, competing bids | `play.py:4940`, `contract_ai.py:1337` |
| Roster cuts | Healthy rotation projection, current value, age, youth/upside and contract cost | `save.py:1034`, `save.py:1056` |
| Released-player upgrades | Compare a released player against low-role incumbent depth before a replacement signing | `save.py:8765` |

This is not an AI with no basketball logic. There are useful components to
reuse, especially the released-free-agent replacement comparison. The missing
piece is agreement between those components about **what the team is building**.

## Verified Gaps

### 1. A Classification Is Not A Persistent Plan

`build_team_strategic_states` recomputes a classification from current inputs.
It does not record the chosen core, why it was assembled, what the team paid,
which seasons constitute its intended window, or what evidence should trigger a
review. There is no shared saved plan consumed by block placement, signing,
cutdown and retention decisions.

The current acquisition premium is not a substitute: it expires after 180
calendar days and affects package pricing rather than defining the core. A
player can appear on the inferred block even while the separate re-trade
exclusion would prevent execution. Starting-roster acquisitions have no trade
log establishing their original intent, so transaction-only memory cannot
reconstruct every opening core.

### 2. Source Timelines Can Override The Actual League

`classify_team_phase` returns immediately for profile timelines containing
`contending` or `rebuild`. Controlled calls reproduced:

- `timeline=rebuilding`, contention index 90 -> **rebuilding**.
- `timeline=contending`, contention index 40 -> **contending**.
- Without an explicit timeline, those same indices classify dynamically.

Eleven current source team profiles contain explicit contending timelines;
the remaining 19 are research-pending. These research profiles are not a saved,
dated decision to keep that direction indefinitely. Treating them as eternal
orders risks old contenders never pivoting, while unlabelled teams can switch
direction too readily around a threshold.

### 3. Contention Is A Useful Index, Not Championship Probability

`contention_ceiling` blends current lineup impact, star power, defense, creation
and depth. It is not a measured title probability or a multi-year forecast. The
strategy builder selects core ages from the top market-valued players, not an
explicit chosen basketball core. It does not directly consider postseason
failure, the time spent trying a core, or an actual alternative roster's
championship chances before reclassifying the team.

Needs and fit exist, but usually as additive thresholds/bonuses. They do not
jointly answer whether this acquisition plus its outgoing players and picks
improves the core's title window enough to justify the cost. The trade evaluator
already has role/concentration penalties, so this should be improved in place,
not replaced with an entirely new trade engine.

### 4. Signing, Role Expectations And Cuts Disagree

`play.py:4976` reserves up to 21 camp slots and cap commitments. Its signing
admission loop does not test a prospective final-roster plan. Role expectations
in `free_agency_offer_context_score` are estimated separately from actual
post-signing minutes. Cutdown later ranks a different objective.

The saved V9 cases show 29/137 summer FA signees cut by their signing team on
October 1. Looney and Ayton received multi-year deals whose offer contexts
estimated roughly 21-23 MPG, then were projected at zero before cutdown. All
four investigated V9 cut teams had 21 September players before reducing to 15.
This behavior existed in V8 as well.

This does **not** mean every signing later waived was irrational: injuries,
development, another acquisition, non-guaranteed contracts and honest scouting
mistakes can justify it. Those reasons should be observable and tested rather
than all churn being automatically declared either valid or a bug.

### 5. Roster Fringes And Rotation Decisions Are Not The Same Objective

An effective 13th-15th man can provide injury coverage or uncertain future value
without a large current minutes projection. Current cut scores include OVR's
minute term and another projected-minutes bonus. A role loss can therefore feed
back into the retention decision despite stable underlying skills.

This is not an argument to change the user's existing scoring/minute penalties,
grant veterans immunity, or force minutes onto late picks. The appropriate
comparison is marginal team value after filling the core and rotation, with
remaining spots considering inexpensive insurance, positional coverage,
development opportunities, options and flexibility.

### 6. Some Long-Horizon Inputs Are Still Date-Insensitive

`team_pick_inventory` counts near-term firsts using literal 2026/2027/2028 years.
`salary_posture` uses literal dollar bands rather than cap-relative spending.
Other cap-legality code is separate and season-aware; this finding is about
strategic labels and fit, not a claim that every signing uses those fixed caps.
These inputs can become misleading over a long career even if initial-season
behavior looks plausible.

## Miami Example: What Is And Is Not Reproduced

In today's V9 starting canonical league, Giannis, Bam and Wiggins are already
on Miami. A freshly built transaction context classifies Miami as **contending**
with contention index **68.35**. None of those three appears on its inferred
trade block. Therefore this review **does not claim to reproduce the user's
older save's exact failure** or attribute it to one proven line of code.

Potential failure routes exist: phase changes, negative contract value,
positional surplus, health and stalled-extension pressure can increase block
scores, while the protection differs between inferred listing and execution.
Identifying which applied in that older save requires its dated context or
transaction/block reasons, not guessing from today's roster.

## Recommended Incremental Design

### First: Give Teams A Small, Saved Plan

Store a versioned plan with core IDs, broad objective/window, adoption date,
adoption reason, acquisition investment, intended review point and explanatory
reason codes. Seed existing careers conservatively from their current known
core; do not invent historical trades or imply real-world facts from our custom
starting roster. Keep unknown provenance explicit.

After a major acquisition, make a meaningful-season commitment the default,
not an absolute untradeable flag. Review at dated simulation milestones,
offseason reviews or major events. Core continuity should survive a bad week or
temporary availability change. A genuine core upgrade can still be accepted.
Give GM personality and owner pressure bounded influence, not arbitrary resets.

Use only available/scouted information when estimating future players. Do not
read hidden eventual development outcomes to give GMs perfect foresight.

### Second: Make Decisions Ask The Same Questions

For trades, paid FA signings, extensions and cuts:

1. Does the move help this core during its plausible window, or establish a
   better future core? Evaluate the resulting roster, not just incoming assets.
2. Which actual player/role is upgraded or replaced? How much future flexibility
   and draft/development value is sacrificed?
3. For depth, does this buy needed insurance, a realistic development opportunity
   or an asset worth retaining? Is there a credible path to the final roster?
4. Does it violate a recent commitment? If so, is there a recorded exception
   strong enough to justify the pivot?

Keep 21 camp slots. A team at 15 must still be allowed to sign an upgrade and
cut its weakest player. A team at 20 should not pay another redundant veteran
merely because slot 21 is legal. Distinguish inexpensive/non-guaranteed tryouts
from paid multi-year commitments according to actual contract support.

Start with a cheap prospective healthy-rotation/replacement check using existing
helpers. Do not run multi-season simulations for every signing or falsely label
an uncalibrated surrogate as exact championship odds.

### Third: Make Pivots Earn Their Evidence

A young improving middle-of-the-pack team can be progressing rather than
trapped. A veteran core with repeated healthy failures may need a targeted
retool before a full rebuild. Assess trajectory, supporting cast and confidence
in the core, not one fixed win threshold or age alone. A championship objective
must not turn every nonfavorite into an automatic tanker.

Preserve existing transaction mechanics initially. A strategy-memory layer and
consistent admission/replacement checks are a bounded first implementation;
accurately forecasting multi-year championships is a larger later project.

For a real-world illustration of building around rather than dismantling a
core: Boston exchanged depth and picks for Holiday to strengthen its established
core. [Celtics acquisition account](https://www.nba.com/celtics/news/sidebar-preseason-20231001-holidays-addition-gives-celtics-a-potentially-lethal-top-6).
That example motivates the design; it does not establish universal GM behavior.

## Acceptance Scenarios Before Tuning

- Major star acquisition commits to a coherent core; a weak month does not
  trigger a fire sale. A clearly superior core upgrade remains possible.
- Significant long-term injury or a real demand permits a reasoned review,
  while a short injury does not automatically redefine the team's direction.
- Old research timelines cannot force a rebuilt elite roster to keep selling
  stars or an exhausted roster to pretend it is permanently contending.
- A weak team with cap room can sign an appropriate young starter; a full team
  can sign a clear upgrade and cut inferior depth. Camp limit remains 21.
- Duplicate paid depth without a credible role/replacement plan is avoided,
  without imposing a blanket no-waivers or no-veterans rule.
- Current rotation and fringe insurance/development spots are evaluated
  distinctly, preserving user-controlled rotations and decisions.
- Plans, exceptions, projected roles and the reason for each rejection/cut are
  inspectable. Same-date repeat calls, daily/bulk advancement and save/reload
  cannot reset commitment periods or duplicate a plan review.
- Date-aware picks and strategic cap labels remain correct several years later
  without needing another all-day career run to test those pure calculations.

The next AI implementation should be this bounded plan/admission pass, not a
wholesale rewrite of trade values, player ratings or prospect development.
