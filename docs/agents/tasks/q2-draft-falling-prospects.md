# Q2: Why highly ranked prospects "fall" in the AI draft (D04 / D05)

Read-only diagnosis. No source files were changed. Scratch scripts and saves are in `output/q2-draft-diagnosis/` (git-ignored).

## TL;DR
1. The "rank" on the board is just the order the prospect was created in. It is not computed from any rating. The AI picks by ratings, so rank and AI opinion often disagree.
2. Your 96-POT example most likely was a hidden-upside prospect. In classes from 2028 on, the board shows the secret true potential (96), but the AI is only allowed to see a much lower "public" potential, so it passes on him. In my 60 test classes this happened about once every two classes.
3. Separately, AI picks carry a lot of random noise (about as big as the real gap between prospects at picks 5 to 15), and AI draft trades swap the pick owner without letting the buyer re-choose. Fixes are cheap and bounded; options are at the bottom.

## What I ran
- 3 real saves (seeds 101, 102, 104; BOS/LAL/OKC) simmed headlessly through the 2026-27 season and playoffs to the 2027 draft. Each took about 10 to 12 minutes with 4 running at once. Seed 103 crashed mid-season (see "Side findings").
- For each: traced every top pick (pool, scores, odds), then ran the whole draft with AI trades on.
- Bigger samples without a full season: 60 draft seeds on the 2027 class, and 60 different classes for the 2028+ path. Same draft code the saves use.

## Finding 1: how the board ranking is made
- Prospects are created in a loop `for rank in 1..60` (`draft.py:306-360`). Current and potential are then drawn with random noise around the rank (`draft.py:336`: potential = current + 11 + a bonus for early ranks + random noise of about 5.6). The list is never re-sorted by those ratings afterwards.
- Result: in the 2027 class, rank 3 (Gabe Rhodes) has 64 potential, while rank 11 (Milan Hayes) has 87. In 60 generated 2028+ classes, the rank-1 prospect was the best by true ratings only 13 times (22%).
- During the live draft the board is sorted by this static rank (`app_actions.py` live board, around lines 3711-3760). Before the draft, the board can instead be sorted by your own team's grade for the prospect (`draft_board_report`, `draft.py:613`; the GUI shows `entry.board_rank || prospect.rank`, `gui/app.js:12553`). So the same column means two different things in two phases.
- The only place that rank touches AI picking is a tiny +1.6 bonus for rank 6 or better (`draft.py:1189`, `prospect_priority_tier` at 1204). The "tier 1" list in that function is hard-coded to three 2026-class names, so for any generated class it never fires. The protection it was meant to give top-3 picks (`draft.py:1136-1142`) is effectively dead code.

## Finding 2: how AI teams actually pick
Two different code paths, depending on the year:
- **2027 class (stored in the game data):** `simulate_draft` -> `choose_entry_with_draft_chaos` (`draft.py:787, 825, 1105`). Each team uses its own noisy scouting report (`build_scouting_reports`, `draft.py:1626`; noise from the team's scouting staff). Pick score (`draft_selection_score`, `draft.py:1167`) is:
  team grade (current/potential/floor, plus team fit and cap value) + a "timeline" bonus for rebuilding or contending + small rank bonus + a **random uncertainty term** - bad-fit penalty - medical penalty.
  A candidate pool is then built and one pick is drawn by weighted chance (`draft.py:1150-1165`).
- **2028 and later classes:** `simulate_generated_draft` -> `choose_generated_with_draft_chaos` (`draft.py:1037, 1214`). No scouting noise at all. Teams rank by `generated_bpa_grade` (`draft.py:2354`, potential 56%, current 28%, floor 10%, ceiling 6%) plus fit/cap, then draw by chance from a window of similar grades.
- In both, the actual choice is made **once, when the draft starts** (`play.py:3039`, `ensure_live_draft_state`), not at each pick.

## Finding 3: the randomness is as large as the real differences
Example, seed 101, 2027 draft (traced pick by pick):
- Pick 1, CHI: all 30 teams had Amari Rhodes (consensus #1) first on their board. CHI scored him 79.7 and had a 79% chance to take him. They took the third option, a 6% shot (rank 5, Marinkovic Jallow). Pick 3, CHA took consensus #11 over #1 (29% vs 43%).
- Seed 102: consensus #2 (84 potential) fell to pick 10 because a draw of about 7% landed. The same team gave the same prospect scores of 60 at pick 5 but 67 at pick 8, because the random term is re-rolled for every (team, pick, prospect).
- The random term is up to plus or minus 5 at picks 1-5, about 11 at picks 6-14, about 17 at picks 15-30 (`draft.py:1199`). The real score gap between public #2 and #10 is about 10 to 15. After that comes a second layer: a softmax with a width of 8.5 and a random 0.55x to 1.55x multiplier (`draft.py:1160-1163`). Team scouting noise (about 4 points on potential) is a third layer. So noise is stacked three times.

## Finding 4: how often top-5 prospects fall (no trades; AI trades add a little)
| Test | Top-5 consensus past pick 10 | Past pick 14 |
|---|---|---|
| 2027 class, 60 draft seeds (300 cases) | 27% | 17% |
| 2028+ classes, 60 class seeds (300 cases) | 28% | 17% |
| 3 real saves with AI trades (15 cases) | 5 of 15 | 3 of 15 |

- Consensus #1 in the 2027 class: always top 10, taken first only 40% of the time (24 of 60), top 3 87% of the time.
- Most falls are rational once you look at the ratings: in 2028+ classes, 74 of the 83 top-5 fallers were not top-5 by true grade (many were rank-1 prospects with 62 to 75 potential). The "rank" label is what is wrong.
- The real "irrational" falls are the hidden-upside prospects (next section).

## Finding 5: the hidden-upside mismatch (best match for your 2nd-ranked 96 POT example)
- A few prospects get a secret "upside tail" (`generated_prospect_upside`, `draft.py:1821`). Their true potential jumps to 85+ while a separate public number stays low (`scouting_prior`, `draft.py:337, 381`). The AI deliberately only sees the public number (`prospect_evaluation_value`, `draft.py:1836`).
- But the board display uses the true value: `prospect_cards.py:28-57` falls back to the true potential whenever there is no scouting report. Generated 2028+ classes have no scouting reports, so the board shows the real number.
- Concrete case (class seed 16): Kofi Kimani, public rank 2, board shows 85.5 potential (ceiling 93.5), AI evaluates him at 63.2. He went 49th.
- Over 60 classes: 45 such prospects; 31 of them showed 85+ potential on the board and slid past pick 14 (median pick about 40). That is roughly one visible "gem the AI cannot see" every other class.
- This also breaks product rule 4 (what you see must match what the engine uses) and your own D05 caution (don't show hidden true ratings as scouting knowledge).
- In the 2027 class the board does use your team's noisy scouting estimate when coverage is under 100% (median coverage in the top 60 was 71%), so it is not affected, and that class has no hidden-tail prospects.

## Finding 6: do "upside" and "potential" double count?
Yes, mildly. In the 2027 path, team grade already weights potential at 49% (`estimate_grade`, `draft.py:2044`). Then rebuilding or developing teams add `(ceiling - current) * 0.13 + (potential - 72) * 0.08` (`draft.py:1185`), and ceiling is just potential plus a random 2 to 9. That adds about 2 to 6 points, much smaller than the noise. Note that this term reads the true current, potential and ceiling, not the team's scouted estimate, so it skips scouting noise. The 2028+ path counts ceiling at only 6% and does not double count.

## Finding 7: AI draft trades do not re-choose the pick
`maybe_run_ai_draft_trades_before_pick_state` (`play.py` around 3088) swaps who owns the pick, but the prospect was already chosen for the original owner. `refresh_live_draft_state_ownership` only rewrites the team id (`play.py:3451`). Checked on all three saves: the prospect assigned to each slot was identical before and after trades. So a team that trades up gets what the seller wanted, not what the buyer wanted. Also, the decision label on almost every pick says "bpa_gap_too_large" (`draft.py:1695`) even though the pick went ahead, so the stored reason text is misleading.

## Side findings (not fixed)
- Seed 103's season crashed in the AI trade code: `ValueError: Every draft condition must refer to one selected pick` (`trade_pick_terms.py:48`, via `transactions.py:3607`). Worth a separate ticket.
- The existing GUI saves in `saves/` are from October and not representative; I did not use them.

## D05: consensus board vs your scouting board, using data that already exists
- **Consensus board** = the league's shared view. Build it from what all teams see: the average (or median) of the 30 teams' scouted grades or board ranks. That data exists for the 2027 class (`scouting_reports`, 30 teams x 60 prospects). For 2028+ classes, reports can be generated the same way as for 2027, or use the public (not true) potential. It must never read `potential` directly when a `scouting_prior` exists. Label it "Consensus" and show a spread (best/worst team rank), so a divisive prospect is visibly divisive.
- **Your scouting board** = your team's own estimate: your scouting report (low/mid/high ranges), your coverage percentage (already computed in `play.py` `save_focused_scouted_pct`), your team's fit/need grade, and your change-since-preseason arrow (already stored as `prospect_preseason_ranks`). This is what `enrich_draft_board_scouting` already half-builds. Hidden true values would stay invisible until the prospect becomes a signed player.
- With both columns, the draft room can show "Consensus #2 / Your board #6" and the AI explanation can say "Team X ranked him 14th".

## Fix options (none implemented)
1. **Stop showing hidden values (smallest, do first).** Make the board and card use the same public/scouted potential the AI uses, never `potential` when a scouting estimate or public number exists. Fixes the main complaint and rule 4. Tradeoff: tail prospects stop looking like steals until they develop (that is the design intent).
2. **Make the public rank real.** Sort each class by a public grade after generation (or assign rank from the public grade), and define "consensus" as in D05. Rank 1 will then usually mean best-looking, and falls become meaningful. Tradeoff: changes who is "rank 1" in saved classes; the engine ratings are untouched.
3. **Cut the noise to one layer.** Keep team scouting noise (it is the realistic part), reduce or remove the per-pick random term and the 0.55x-1.55x swing for picks 1 to 10. Decide the target by a measurable goal, for example "consensus top 3 fall past pick 10 under 5% unless injured or very high-volatility". Tradeoff: fewer surprises; keep some in the mid-first round. Needs the betting/calibration scorecards (rule 9) only if rookies' pick slots feed rookie development.
4. **Let trades re-choose.** When a pick changes owner, redraw that one selection from the buyer's board (and re-run later picks only if the pool changed). Tradeoff: small change in `play.py`, but it alters seeded draft results for any trade.

Suggested order: 1 and 2 together (display/truthfulness), then 3 with a numeric target, then 4.
