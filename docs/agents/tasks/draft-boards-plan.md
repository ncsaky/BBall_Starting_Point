# Draft boards: consensus big board and your scouts' board (plan)

_Plan written 2026-11-19 by Claude (coordinator). Not started. Starts once TRADE-2B (re-pricing draft picks, `draft.py` pick values) merges._

## TL;DR
- Two boards, clearly labelled. **Consensus** is what the league as a whole believes about each prospect. **Your board** is what your own scouts believe, with their uncertainty. Neither one ever shows a prospect's hidden true ratings.
- AI teams draft from their own scouts' boards, so falls come from scouting disagreement and team needs. Stacked random rolls stop being the cause, but surprises in the middle of round one stay.
- Scouting staff quality changes how accurate a team's board is. The real 2027-29 prospects keep their real scouting consensus.

## Why (the user's words and the earlier diagnosis)
- The user, 2026-10-29: "Are our rankings based on just our scouts knowledge or like a big board ranking? I feel like both should exist." They also wrote that the AI looked too random, while noting that "it might be the case that the GMs are actually making great selections, our rankings are just absurd." Backlog items D04 and D05 ask for both boards, and for hidden true ratings never to be shown as scouting knowledge.
- The earlier diagnosis (`docs/agents/tasks/q2-draft-falling-prospects.md`) found five problems:
  1. The board "rank" was only the order in which prospects were created.
  2. Prospects with hidden upside showed their secret true potential on the board while the AI saw a lower public number. This broke rule 4.
  3. AI picks stacked three layers of randomness: team scouting noise, a per-pick random roll, and a 0.55x–1.55x swing.
  4. When a draft pick was traded, the new owner could not choose again.
  5. The draft code had two different paths: 2027 used scouting reports, 2028+ did not.
- Since that diagnosis, part of this has already been fixed:
  - Generated prospects now get a public potential from a slot profile anchored to the real 2026 class, with a "scouting miss" to their true potential (commit 73a33ea).
  - The 2027-29 classes now hold real players with a real consensus (`real_prospects.py`).
  - Trade step 2 made draft-night trades target "the prospect it would actually take".

  **Step 0 below re-checks each finding on current code before anything is changed.**

## Definitions

| | Consensus big board | Your scouts' board |
|---|---|---|
| **Meaning** | Where the league as a whole ranks the prospect | What your own scouts believe |
| **2027-29 real players** | The real consensus from public big boards and mocks, already built in `real_prospects.consensus_board`. It then moves during the season with the 30 teams' scouting reports and college games. | Your scouting report: low/mid/high ranges plus coverage %. Your scouting lead's quality sets how wide the ranges are and how biased they are. |
| **Generated players (2030+)** | The median of the 30 teams' scouted grades. | Same as for real players. |
| **Shows** | Consensus rank, plus a spread (best and worst team rank), so a divisive prospect looks divisive. | Your rank, your grade range, your coverage %, the change since preseason, and fit with your roster (need and timeline). |
| **Never shows** | Hidden true ratings | Hidden true ratings: they appear only once the player is signed and playing |

On the draft-night board, both columns sit side by side, e.g. "Consensus #2 · Your board #6". The prospect card shows both and explains the gap: "Your scouts are lower on his shooting."

## How AI teams draft
- Each AI team ranks prospects from **its own scouting report**, the same kind as yours, for every class. Generated classes get reports too, so the 2027 and 2028+ code paths become one. Each team then applies its own fit, timeline (rebuilding vs contending) and medical adjustments.
- **Randomness becomes one realistic layer.** The noise comes from each team's scouting, sized by its scouting lead's quality and how much it has scouted the prospect. The per-pick random roll and the 0.55x–1.55x swing are removed or greatly reduced at the top of the draft. Some team-specific taste stays in the middle and late first round. The target needs to be measurable:
  - a consensus top-3 prospect falls past pick 10 in under about 5% of drafts, unless he is injured or very volatile;
  - a top-10 consensus prospect falls past pick 20 rarely, but not never;
  - check both against real drafts from 2015 to 2025, comparing consensus big board rank with actual pick. Collect public mock and big-board data, and record the source.
- **Picks are re-chosen when traded.** When a pick changes owner, the new owner picks from its own board. The draft-night trade target from step 2 should already line up with this; verify it.
- **Explanations** on each pick: "PHX took Smith Jr. (consensus #4, their board #2): needs a wing; their scouts rate his defense highly."

## Scouting staff
- The quality of the scouting lead slot (staff ratings, `draft.py` reads the `scouting_lead` slot) sets how wide a team's ranges are and how far its board strays from the truth. Coverage % grows with in-season scouting.
- Your scouts can be wrong. Hidden true values show up later in development, as they do now. This makes a good scouting lead worth hiring.

## Steps (one agent, its own worktree)
0. **Re-verify the earlier diagnosis on current code.** For each of findings 1–7: still true, partly fixed, or fixed. Run 20 seeded drafts per class type with no saves, to keep it light.
1. **Truthful display (do first).** Board and card use only the public or scouted numbers the AI uses. Hidden true values are never shown before signing. Write tests that fail if `potential` is shown while a public or scouted value exists.
2. **The two boards.** Consensus (with spread) and your scouts' board, in the draft-night board and the Upcoming Prospects window. Use the existing table style (rule 12) and the existing card layout.
3. **One AI drafting path with one noise layer**, sized by scouting staff, measured against the target above and against real drafts.
4. **Re-choose on traded picks,** and add pick explanations.
5. **Checks:**
   - how often top-3 and top-10 prospects fall, before and after, compared with real drafts;
   - the two-season probe's draft results, to confirm no new oddities;
   - both scorecards unchanged (draft position feeds rookie development only through pick slot, so check it);
   - the full draft tests;
   - the real-prospects tests;
   - the browser tests;
   - a run through the GUI's draft night in the browser.

## Files
`draft.py`, `prospect_cards.py`, `real_prospects.py`, `play.py` (draft-night live state), `app_actions.py` (draft board payloads), `gui/app.js` and its CSS (draft board, prospect card), and tests.

Must wait for: TRADE-2B, which edits `draft.py` pick values and `play.py` draft-night trades.

## Open questions for the user (ask when starting)
1. Should the consensus board for the real 2027-29 classes keep following the real public boards as they update (prospect refresh in Jan/Feb), or freeze at the save's start date?
2. How much surprise on draft night? The proposed target is a top-3 consensus prospect falling past pick 10 in under 5% of drafts. Is that about right?
