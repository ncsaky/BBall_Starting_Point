# Draft boards: consensus big board, your scouts' board, and AI teams that draft without dice

_Claude Opus agent, own worktree branch, started 2026-11-19. Status: **in progress**. Plan: `draft-boards-plan.md`._

## Resume state
- Step 0 done (findings below). Next: step 1 (truthful display).
- Fall-check script: scratchpad `draft_falls.py` (copied to `scripts/research/draft_falls.py` in step 5).
- Real 2015-2025 boards vs picks: `data/research/draft_boards/real_board_vs_pick_2015_2025.csv`.

## Step 0: the earlier diagnosis on current code (2026-11-19)

Fall check, 20 seeded drafts per class type, no saves, no trades (`draft_falls.py 20`):

| | 2027 (real class, a different save seed each draft) | 2030 (generated class) | Real 2015-2025 |
|---|---:|---:|---:|
| Board top 3 picked after 10 | 0 of 60 | 1 of 60 (one went 18th) | 0 of 33 |
| Board top 10 picked after 20 | **26 of 200 (13%)** | **19 of 200 (9.5%)** | 3 of 110 (2.7%) |
| Board No. 1 picked first | 11 of 20 | 11 of 20 | 8 of 11 |
| Median gap, board rank 1-14 vs pick | 3 | 2 | 2 |
| Median gap, board rank 15-30 vs pick | 10 | 8 | 6.5 |
| Worst top-10 fall | pick 48 | pick 38 | pick 31 |

Real boards: one big board per year published in the final week (SI, CBS, Bleacher Report, NBC Sports Boston, HoopsHype
aggregate mock, ClutchPoints, ESPN). Sources per year are in the CSV. Single-outlet boards are a little noisier than a
true consensus, so the real gaps are, if anything, upper bounds.

| # | Finding (q2 diagnosis) | Now |
|---|---|---|
| 1 | Board rank was creation order | **Fixed** (commit 689933a): every class is numbered by the public grade the AI uses; the "top 3" protection reads that rank instead of three 2026 names. **Still true:** the same "Rank" column means the public rank on draft night and your own team's board rank before it. |
| 2 | Hidden upside shown on the board | **Partly fixed.** The card's potential now uses the public number. Still leaking: (a) at 100% scouting the card shows the true current level and true skills; (b) the draft-night board's "Fit" column is computed from the hidden true potential (`live_draft_board_report`); (c) every board payload carries the true `potential`/`ceiling`, and the table falls back to them when the scout value is missing. Every 2027 prospect has a hidden value (60 of 60; true minus public potential: spread 7.2, from -18 to +25). |
| 3 | Three stacked layers of randomness at pick time | **Partly fixed.** The per-pick re-roll is gone (a team's read is now stable), but each pick is still a weighted draw (a coin flip of 54-58% for picks 1-3, then a softmax with a 0.82-1.18 random swing), plus a hidden per-team "uncertainty" of +-3 to +-14 points on top of the scouting noise. The AI's "timeline" bonus reads the **true** potential and ceiling (a second leak, inside AI decisions). |
| 4 | Top-5 prospects fall too often | **Mostly fixed at the very top** (no top 3 past 10 in 2027), **still too often for picks 4-10** (13% and 9.5% of top 10 past 20 vs 2.7% real; falls to the 40s). |
| 5 | Two AI drafting paths | **Still true.** The next class (2027) uses team scouting reports; 2028 and later use one shared public grade with no scouting at all. |
| 6 | Upside double count | **Still true** (small): the timeline term adds upside on top of a grade that already weights potential, and reads true values. |
| 7 | Traded picks not re-chosen | **Fixed** (`play.rechoose_pending_draft_pick`): the new owner picks from its own board. **Still true:** the whole draft is decided when draft night opens; AI picks after the user's pick or a trade do not react to who is gone except by a slot swap. Decision labels now compare with the best player still available (fixed). |
