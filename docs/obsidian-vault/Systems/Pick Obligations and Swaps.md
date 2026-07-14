---
type: system
status: current
reviewed: 2026-07-10
tags:
  - system/draft-picks
  - gameplay/trades
  - project/nba-gm
---

# Pick Obligations And Swaps

Draft assets forced the project to move from descriptive strings to structured future rights.

## Why A Pick Label Is Not Enough

Text such as “top-10 protected” does not answer:

- Who owns the primary rights now?
- Who keeps the pick if it lands in the protected range?
- What exact fallback transfers instead?
- Is that fallback locked from another trade?
- Can the primary right be retraded?
- What happens if the sender reacquires it?
- When and against which lottery order is it resolved?

Using prose as state produced self-referential fallbacks, unsupported swap language, ownership mismatches, and labels that disagreed with resolution.

## Protected Pick Model

A structured protected-pick obligation ties together:

- primary pick ID;
- sender/original team;
- beneficiary/current rights holder;
- protection range;
- same-round, same-or-later fallback pick ID;
- status and resolution history.

The validator rejects:

- fallback equal to primary;
- round mismatch;
- fallback earlier than primary;
- missing or duplicate fallback;
- locked collateral;
- malformed teams or ranges.

Startup data with incomplete terms is repaired deterministically when a valid fallback exists. If not, gameplay correctness is favored over deceptive prose: audit the problem and treat the asset as unprotected rather than promise an impossible fallback.

## Resolution

After lottery/draft order is known:

- If the primary lands outside the protected range, it conveys to the current rights holder.
- If it lands inside the protected range, the original sender keeps it and the current rights holder receives the fallback.
- If the sender reacquires the right before resolution, the obligation can be safely collapsed and collateral unlocked.
- If the right is retraded, the beneficiary follows the current rights holder.

Fallback collateral is hidden from normal tradeable asset lists and illegal if selected before resolution.

## Pick Swap Model

A swap is not a full pick. It is the right to exchange positions if the counterparty's pick is better. The v1 model stores:

- type `pick_swap`;
- season and round;
- both underlying pick IDs;
- original and current rights holder;
- counterparty;
- direction: who may receive the better pick;
- status and transfer history.

Swaps must pair the same season and round so “better” is meaningful. Swap rights can be retraded as their own asset; underlying picks remain visible but labeled as subject to the swap.

At resolution, current owners and the current rights holder are used. The rights holder receives the more favorable slot and the other side the less favorable slot.

## Valuation

A swap right is worth the expected value of moving up, not the value of either full pick:

`expected swap value ~= probability(counterparty pick is better) * expected slot-value gain`

Uncertainty, team quality, season distance, and rights direction bound that estimate. Granting the other team upside is a negative obligation cost. Multiple swaps can matter cumulatively without becoming equivalent to multiple unprotected firsts.

## Human-Readable Labels

One shared display helper should generate every asset list, trade, event, and lottery label from structured state. A good protected label conveys all outcomes; a good swap label names who may receive the better pick and who gets the worse pick.

Example style:

`2030 R1 DAL (owned by GSW); top-20 protected; DAL keeps it in the protected range; GSW instead receives 2032 R1 DAL.`

`2030 R1 swap right: MIA may receive the better of MIA/MIL; the other team receives the less favorable pick.`

The exact prose can evolve, but it must never add a trailing “to DEN” detached from its clause or claim that the fallback is the primary itself.

## Identity And Live Draft State

Current-year picks need exact `pick_id` and `overall_pick` identity. Lottery reveal, draft summary, asset list, and selection queue must all read the same saved order after protections and swaps resolve. Repair guards detect duplicate or stale IDs before display or advancement.

## Invariants

1. Primary and fallback IDs are always different.
2. Protected fallback round matches the primary round.
3. Fallback year is not earlier than the primary year.
4. Locked fallback collateral cannot be traded by either side.
5. A pick cannot be both protected and a swap in one trade term.
6. Swap subject picks share year and round and are different IDs.
7. Labels and resolution read the same obligation record.
8. A current draft pick can be transferred at most once after selection and never selected twice.

## Why This System Deserves Its Own Boundary

Pick obligations have creation, transfer, lock, display, value, resolution, repair, and history behavior. Treating them as optional pick fields hides that lifecycle. A future refactor should move this lifecycle into a dedicated module with explicit state transitions and property-based tests.

## Related Notes

- [[Decisions/ADR-005 Structured Pick Obligations]]
- [[Systems/Draft Lottery and Scouting]]
- [[Architecture/Determinism and Identity]]
- [[History/Failure Museum]]

