# Draft boards: consensus big board and your scouts' board (plan)

_Plan written 2026-11-19 by Claude (coordinator). Not started. Starts once TRADE-2B (re-pricing draft picks, `draft.py` pick values) merges._

## User decisions (2026-11-19, these override anything below that conflicts)
1. **The scouts' board is purely a talent assessment.**
   - Scouts rank who they think the best players are.
   - They may say a prospect is raw, needs time and has more upside, or that another is better now with less growth left, whether because of age or not.
   - They do **not** consider fit, team needs, or whether the team is rebuilding or contending. That is the **general manager's** job.
   - So there are two separate layers: the scouts' board (talent) and the GM's draft decision (talent plus team context).
2. **Consensus boards update monthly through the season.** They move more early in the year and less toward the draft, as scouts form firmer views.
3. **No dice rolls at pick time.** Draft-night surprises must come from logical reasons:
   - teams' different goals and priorities;
   - reacting to who is still available, and at what price;
   - trading up or down.

   The gap between projected and actual draft position should still match real drafts, but as an outcome check, not something tuned by adding randomness.

## TL;DR
- Two boards, clearly labelled. **Consensus** is what the league as a whole believes about each prospect. **Your board** is what your own scouts believe, with their uncertainty. Neither one ever shows a prospect's hidden true ratings.
- Scouts judge talent only. Each AI GM then picks from his scouts' board by his team's phase, needs and the value left on the board, or trades up or down. Surprises come only from those differences; there are no dice at pick time.
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
| **2027-29 real players** | The real consensus from public big boards and mocks, already built in `real_prospects.consensus_board`. It **updates monthly** through the season from the 30 teams' scouting and college games, with bigger moves early and smaller ones near the draft. | Your scouting report: low/mid/high ranges plus coverage %. Your scouting lead's quality sets how wide the ranges are and how biased they are. |
| **Generated players (2030+)** | The median of the 30 teams' scouted grades. | Same as for real players. |
| **Shows** | Consensus rank, plus a spread (best and worst team rank), so a divisive prospect looks divisive. | Your scouts' rank, the grade range and whether he is "raw, high upside" or "ready now", coverage %, and the change since the last monthly update. **No team fit or timeline**: that belongs to the GM. A separate, clearly labelled "Fit for us" note can sit beside it for you as GM. |
| **Never shows** | Hidden true ratings | Hidden true ratings: they appear only once the player is signed and playing |

On the draft-night board, both columns sit side by side, e.g. "Consensus #2 · Your board #6". The prospect card shows both and explains the gap: "Your scouts are lower on his shooting."

## How AI teams draft (scouts assess, the GM decides)
- **Scouts' layer.** Each team has its own scouting report on every prospect, for every class; generated classes get reports too, so the 2027 and 2028+ code paths become one. The report covers talent only:
  - current ability;
  - upside, with its range;
  - development time ("raw, two years away" or "ready now, limited growth");
  - risk factors such as age, medicals and consistency.

  Teams' views differ for reasons that can be explained:
  - the quality of the scouting staff;
  - how much each team watched the prospect (coverage);
  - each staff's lasting taste, for example how heavily it weighs shooting or physical tools.

  A staff's view is formed as it scouts during the season. It is never re-rolled at pick time.
- **GM layer (the actual pick).** The GM turns the scouts' board into a pick using the team's context:
  - phase, i.e. a rebuilding team values upside and a contender values readiness;
  - positional need and roster fit;
  - risk appetite;
  - how much a prospect is worth against what is still on the board when the pick comes up, which is why a falling player gets snapped up;
  - whether trading up or down is better value.

  Given the scouts' board, this step is **deterministic**. The current per-pick random roll and the 0.55x–1.55x weighted draw are removed.
- **Where draft-night surprise comes from:**
  - different scouting views;
  - different GM priorities;
  - reacting to availability;
  - trades up and down.

  Front-office personality (trade step 5) can add more later.
- **Outcome check, not a tuning knob.** Compare how far picks land from consensus rank with real drafts from 2015 to 2025 (big-board rank against actual pick, from public data with recorded sources). Measure how often a consensus top-3 prospect falls past pick 10 and a top-10 prospect past pick 20. If the result is far off, look for a missing logical reason, such as GMs that are too alike or a scouting spread that is too narrow. Never add randomness.
- **Picks are re-chosen when traded.** When a pick changes owner, the new owner picks from its own board. The draft-night trade target from step 2 should already line up with this; verify it.
- **Explanations** on each pick: "PHX took Smith Jr. (consensus #4, their board #2): needs a wing; their scouts rate his defense highly."

## Scouting staff
- The quality of the scouting lead slot (staff ratings, `draft.py` reads the `scouting_lead` slot) sets how wide a team's ranges are and how far its board strays from the truth. Coverage % grows with in-season scouting.
- Your scouts can be wrong. Hidden true values show up later in development, as they do now. This makes a good scouting lead worth hiring.

## Steps (one agent, its own worktree)
0. **Re-verify the earlier diagnosis on current code.** For each of findings 1–7: still true, partly fixed, or fixed. Run 20 seeded drafts per class type with no saves, to keep it light.
1. **Truthful display (do first).** Board and card use only the public or scouted numbers the AI uses. Hidden true values are never shown before signing. Write tests that fail if `potential` is shown while a public or scouted value exists.
2. **The two boards.** Consensus (with spread) and your scouts' board, in the draft-night board and the Upcoming Prospects window. Use the existing table style (rule 12) and the existing card layout.
3. **One AI drafting path.** The scouts' view is formed during the season and sized by staff quality, coverage and staff taste. The GM's pick is deterministic: phase, need, risk appetite, value against what is left on the board, and trading up or down. There is no random draw at pick time. Check the outcome against real drafts.
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

## Open questions for the user
None. Both were answered on 2026-11-19 (see "User decisions" at the top).
