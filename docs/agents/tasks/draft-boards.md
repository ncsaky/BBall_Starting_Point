# Draft boards: consensus big board, your scouts' board, and AI teams that draft without dice

_Claude Opus agent, own worktree branch `worktree-agent-a07f84a1cf8b1febb`, 2026-11-19. Status: **review** (not pushed,
not merged). Plan: `draft-boards-plan.md`._

**TL;DR**
- **Two boards everywhere:** the league consensus (the median of all 30 teams' scouting, with where most teams rank
  him) sits beside your own scouts' board (talent only, with the change since last month's update). Neither shows a
  prospect's hidden true ratings any more; before, the fully scouted card and the draft-night "Fit" did.
- **AI teams draft in two layers and never roll dice at pick time:** each team's scouts form a talent-only board that
  changes monthly (big moves early, small ones near June), then its GM adds phase, need and price. Surprises come
  from different scouts, different priorities, who is left, and trades.
- **Draft outcomes now look like real drafts:** consensus top-10 players falling past pick 20 went from 10-13% to
  under 1% (real 2.7%); the median gap between board rank and pick matches real drafts at the top (1 and 2) and is
  a little tight in the late first (4 vs 6.5). Both scorecards are unchanged.

## Resume state
- All plan steps done; commits: step 0 (`1d01f6e`), steps 1+3 (`2062ba8`), steps 2+4 (`09aa107`), step 5 checks
  and this report (last commit on the branch). Steps 1 and 3 share a commit because the screen and the AI now read
  one scouting source; the reach price and the label fix landed with steps 2+4.
- Scripts: `scripts/research/draft_falls.py` (seeded drafts vs real), `scripts/research/draft_night_trades_check.py`
  (draft night with AI trades in a scratch save). Real data: `data/research/draft_boards/real_board_vs_pick_2015_2025.csv`.
- Worktree symlinks (`.venv`, Barttorvik raw, universe SQLite, injury evidence, BBI files, settlement output) are
  untracked and were not committed; remove them before deleting the worktree.

## Step 0: the earlier diagnosis on current code

Fall check before any change, 20 seeded drafts per class type, no saves, no trades (consensus = the public rank,
the only board that existed):

| | 2027 (real class, a different save seed each draft) | 2030 (generated class) | Real 2015-2025 |
|---|---:|---:|---:|
| Board top 3 picked after 10 | 0 of 60 | 1 of 60 (one went 18th) | 0 of 33 |
| Board top 10 picked after 20 | **26 of 200 (13%)** | **19 of 200 (9.5%)** | 3 of 110 (2.7%) |
| Board No. 1 picked first | 11 of 20 | 11 of 20 | 8 of 11 |
| Median gap, board rank 1-14 vs pick | 3 | 2 | 2 |
| Median gap, board rank 15-30 vs pick | 10 | 8 | 6.5 |
| Worst top-10 fall | pick 48 | pick 38 | pick 31 |

| # | Finding (q2 diagnosis) | On current code (before this task) |
|---|---|---|
| 1 | Board rank was creation order | **Fixed** (commit 689933a): classes are numbered by the public grade. **Still true:** the same "Rank" column meant the public rank on draft night and your own board rank before it. |
| 2 | Hidden upside shown on the board | **Partly fixed.** The card's potential used the public number, but (a) at 100% scouting the card showed the true current level and true skills; (b) the draft-night "Fit" column was computed from the hidden true potential; (c) every board payload carried the true potential and ceiling, and the table fell back to them. All 60 of the 2027 prospects have a hidden value (true minus public potential: spread 7.2, from -18 to +25). |
| 3 | Three stacked layers of pick-time randomness | **Partly fixed.** The per-pick re-roll was gone, but each pick was still a weighted draw (a 54-58% coin flip at picks 1-3, then a softmax with a random 0.82-1.18 swing) plus a hidden +-3 to +-14 point "uncertainty" per team. The AI's "timeline" bonus read the **true** potential and ceiling (a leak inside AI decisions). |
| 4 | Top prospects fall too often | **Mostly fixed at the very top, still wrong for picks 4-10** (table above). |
| 5 | Two AI drafting paths | **Still true.** The next class used team scouting reports; 2028 and later used one shared public grade with no scouting. |
| 6 | Upside counted twice | **Still true** (small), and it read true values. |
| 7 | Traded picks not re-chosen | **Fixed** (the new owner picks from its own board). **Still true:** the whole draft was decided when draft night opened, so AI picks did not react to the user's picks. |

## What changed

### Scouting (new `draft_scouting.py`): what each team believes, month by month
- **Every class, one path.** For any draft year every team has a report on every prospect: current level, upside,
  ceiling, floor, the 12 draft skills with low/mid/high ranges, coverage %, and a read: "Raw, high upside", "Ready
  now, less growth" or "Some now, some upside". Reports are computed on demand and cached; a 30x60 class takes
  about 0.1 s.
- **Talent only.** The scouts' grade uses upside, current level, downside, volatility and medicals. Team phase,
  needs and fit never enter it (a test changes every team's phase and needs and checks the scouts' boards are
  identical).
- **Why teams differ (all fixed per team, nothing re-rolled):**
  - staff quality: a better scouting lead has less estimation error and sees part of what the consensus misses
    (up to a quarter of the gap to the truth at full coverage);
  - coverage: everyone watches the top of the board; the rest is scouted unevenly; coverage grows through the
    season, faster for better staffs; classes beyond next June are barely scouted;
  - lasting staff taste: each scouting lead weighs skill groups differently (shooting, physical tools, feel,
    defense, motor), and the lead's style matters ("upside evaluator" weighs upside more, "role-player value hunter"
    current level, "risk-balanced drafter" volatility and medicals). Hiring a new lead changes the taste.
- **Monthly updates.** The public view of each prospect drifts through the season (a quarter of what scouts could
  not see at first, plus news nobody could predict). Most of the movement comes in November-January; by June the
  boards are firm. Teams' reports follow the public view and tighten as coverage grows. Real 2027 players start from
  their real consensus.
- **The hidden upside tail stays hidden.** The engine now records it apart from the ordinary scouting miss
  (`scouting_prior.latent_tail`; the stored 2027 class gets it back from a regeneration of the same class), so the
  season and good scouts can reveal part of a prospect's true level but never the tail.
- **Consensus** = the median of the 30 teams' grades, with each prospect's best, worst and middle-half team ranks.

### The GM layer (`draft.gm_rows`): one deterministic choice
At each pick the owner's GM takes the best prospect still on the board by: his scouts' grade, plus phase (rebuilding
and developing teams value upside room; contenders value current level and dislike volatility), plus need and roster
fit (weighs more as the draft goes on), minus a price for reaching (taking a player the league ranks far below the
pick pays this pick's price for a later pick's player). The random draw, the coin flip at the top, the hidden
uncertainty term, the 0.82-1.18 swing and the true-value reads are gone. `simulate_draft` uses this for every class
(the separate generated-class path was removed).

### Live draft night (`play.py`)
- The draft is forecast when draft night opens, as before, but each AI pick is now re-chosen from who is actually
  left right before it is made (after the user's picks and draft-night trades). A traded pick is chosen by its new
  owner. Draft-night trades are otherwise unchanged; a trade-up targets exactly the prospect the buyer's GM would
  take (same function).
- Every pick carries a plain reason, for example: _"CHA took Jordan Smith Jr. (consensus #3, their board #1): the best
  player left on their board; rebuilding, so they bet on his upside; he slid to 7."_ Shown in the draft-order
  tooltip, the pick reveal and a "Why" column in the completed draft summary.

### Screens
- **Draft-night Prospect Board** and **Upcoming Prospects** (expanded): Consensus (with where most teams rank him),
  Your board (with the arrow for the last monthly change), your scouts' Now and Pot, Scouts' read, Scouted %,
  "Fit for us" (the GM's need and fit, clearly separate from the scouts' board), Injury, Status. Shared table style
  (double header rule, small bold headings, stripes, whole-row hover, sorted-column shading). Default sort: consensus.
- **Compact Upcoming Prospects card:** # is now the consensus rank, a new "Yours" column, and "Range" is where most
  teams rank him (it used to be a fixed rank-3 to rank+5 band that meant nothing).
- **Prospect card:** "Consensus #1 · Your board #3", the scouts' read, and why they differ ("Your scouts are lower on
  his athleticism.").
- **What the screens never show before a player is signed:** true potential, true ceiling, true current level or true
  skills. Board payloads carry only consensus numbers; the card and table use your own report at any coverage,
  100% included.

## Before and after against real drafts

Seeded drafts, no saves, no trades (`scripts/research/draft_falls.py 40`; consensus = the June consensus board):

| | 2027 before (20) | 2027 after (40) | 2030 before (20) | 2030 after (40) | Real 2015-2025 |
|---|---:|---:|---:|---:|---:|
| Consensus No. 1 picked first | 55% | 58% | 55% | 60% | 73% (8 of 11) |
| Top 3 picked after 5 | | 9% | | 7.5% | 9% (3 of 33) |
| Top 3 picked after 10 | 0% | 0.8% (one, to 12) | 1.7% | 0% | 0% |
| Top 10 picked after 14 | | 3.3% | | 6% | 5.5% (6 of 110) |
| Top 10 picked after 20 | **13%** | **0.25%** | **9.5%** | **0.25%** | 2.7% (3 of 110) |
| Picks 1-5 used on a player ranked past 14 | | 2% | | 0.5% | 0% (0 of 55) |
| Picks 1-10 used on a player ranked past 20 | | 2.3% | | 1.3% | 3.6% (4 of 110) |
| Median gap: ranks 1-3 / 4-10 / 11-20 / 21-30 | 3 (1-14) / 10 (15-30) | 1 / 2 / 4 / 4 | 2 (1-14) / 8 (15-30) | 1 / 2 / 3 / 4 | 1 / 2 / 4.5 / 6.5 |

- How the settings were found: the first deterministic version was far too orderly (top-10 gaps of 1, late-first
  gaps of 2, nobody falling). Following the plan, I looked for missing logical reasons rather than adding noise: the
  scouting spread was too narrow for prospects few teams had watched, staff tastes were too weak, need mattered too
  little late in the draft, and GMs were reaching too freely (a consensus No. 26 went 5th in one GUI run). The
  coverage, taste, need and reach-price settings above fix those; nothing random was added at pick time.
- **Real data:** one final big board per year, published in draft week, matched to Basketball-Reference picks:
  SI (2015), CBS (2016, 2017), Bleacher Report (2018, 2020), NBC Sports Boston (2019), HoopsHype aggregate mock (2021),
  SI (2022), ClutchPoints (2023, 2024), ESPN (2025). URLs per row in the CSV. Single-outlet boards are a bit noisier
  than a true consensus, so the real late-first gap is if anything an upper bound. Gathered by a research sub-agent
  through page summaries, not raw HTML; treat individual rows as good but not hand-verified.
- **Still off:** the late first is a little too orderly (4 vs 6.5), the consensus No. 1 goes first a bit less often
  (58-60% vs 73%: generated classes often have two near-equal top prospects), and top-10 players almost never fall
  past 20 (real 3 of 110, all with medical or fit stories: Deyonta Davis, Nassir Little, Tyrese Maxey).

## Draft-night trades
`scripts/research/draft_night_trades_check.py` (new saves moved to draft night, seeds 17, 23, 31, Golden State as the
user, whole draft simulated with AI trades; no season played, so the order comes from projected standings):
- **5 trades per draft** in all three (real: about 5; the trade code's own cap is 5 per draft), the same count as the
  trade-2b report.
- **15 of 15 buyers drafted the prospect they traded up for**, each ranked 1st to 8th on their own board. Examples:
  "BOS took Cameron Williams (consensus #14, their board #3)", "MEM took Motiejus Krivas (consensus #7, their board
  #5): ... he slid to 14".
- Each draft took 27-30 s for 60 picks, five trades and the per-pick re-choice (trade evaluation dominates).
- **Still wrong (trade code, not changed here):** all five trades land at picks 11-18 every time, because the
  mid-first market fills the night's budget at the first chances; real draft-night trades spread over the whole
  draft. Some trade-ups are for clear reaches by the consensus (Chinyelu, consensus #26, at 15), since a buyer
  trades up for what its own board says. Both belong to the planned draft-night chains (trade step 4).

## Boards in the running app
GUI server on port 8782 with a scratch save folder. The season was **not** played: new saves (Charlotte, seed 17) were
moved by date to mid-January 2027 and to draft night (26 June 2027). Checked:
- **January, Upcoming Prospects (expanded):** consensus # with the middle-half team range, "Yours" with monthly
  arrows (e.g. Jason Crowe Jr. "#22 ▼1", Davis Fogle "#23 ▲3"), scouted bars. The top of the board did not move
  between the December and January updates; 30 of 60 prospects did.
- **Prospect card (Tyran Stokes):** "Consensus #1 · Your board #3 / Some now, some upside / Your scouts are lower on
  his athleticism." Scouted 93.5%.
- **Draft night board** before the first pick (text of the first rows):
  `#1 (1-3) | #3 | Tyran Stokes | Some now, some upside | 100%`,
  `#3 (2-4) | #1 | Jordan Smith Jr. | Raw, high upside`, `#9 (8-23) | #7 | Dame Sarr | 63%`.
- **Sim to my pick, my pick, then the rest of the draft** (the last part through the same app action from a script,
  because the app's mandatory roster cut-down window, caused by skipping the season with full rosters, blocks the
  screen): all 60 picks have reasons; examples in "What changed". Five draft-night trades.
- Not checked in the browser: the lottery reveal screens (unchanged code), a full season into the draft.

## Checks run
- Real-stat scorecard (`calibration_report.py --games 1230 --mode replay-real-minutes`): **18/18**.
- Betting-odds scorecard (`validate-season-probabilities --runs 100`): **Brier 0.1963, log loss 0.5796**, identical
  to main (the draft does not enter the replayed season; rookies' development is unchanged, only who drafts whom).
- Not run: the two-season probe (two full seasons; too heavy alongside three other agents). Seeded drafts and three
  scratch-save draft nights were used instead, as the brief allowed.
- Tests: new `tests/test_draft_boards.py` (9: no hidden ratings in board payloads; the card uses the report at 100%;
  scouts' board ignores phase and needs; need fit never reads true potential; the tail stays hidden; boards move more
  early than late; coverage grows and ranges narrow; a better lead sees more of the truth; drafts are deterministic
  and explained). Updated: `test_draft_fixes` (GM pick has no dice), `test_prospect_rating_parity` (full coverage now
  shows the report, not the signed ratings), `test_dashboard_metrics`, `test_prospect_identifiers`,
  `test_hidden_upside`, `test_player_lifecycle` (medical discount via the scouts' grade).
- Results: core suite (`scripts/run_core_tests.sh`) 337 OK; draft, prospect and real-prospect modules plus the 21
  draft tests in `test_foundation` 160 OK; all 29 `tests/*.test.cjs` pass. The full suite was not run.
- `scripts/screen_hidden_upside_drafts.py` now calls `simulate_draft` (the separate generated-draft function is gone).

## What's left
1. **Draft-night trade timing** (trade code): all five trades happen at picks 11-18. Belongs to trade step 4.
2. **Late-first spread a little tight** (median gap 4 vs 6.5 real) and top-10 falls past 20 rarer than real. The
   logical lever left is team focus: teams scout their own pick range harder (the old display had this; the new
   reports do not, because the pick order is unknown until the lottery). Worth trying after the lottery reveal.
3. **"Fit for us" is flat for many teams** (often 49-53): positional need only fires for the four need tags teams
   carry. A richer need model (roster minutes by position, contract timelines) would make it more useful.
4. **Explanations repeat "their scouts are higher on his upside"**: true by selection (the team that takes a player
   is usually the one highest on him), but repetitive. Could be shown only when the gap is large.
5. **Prospect card upside ring** still unlocks at 100% scouting; with reports that never reach the truth this is a
   scouts' estimate, not a reveal. Rename or rethink with the user.
6. **Real-board data** is single-outlet per year; a true consensus (for example an aggregate board) would be a better
   target if one can be captured.

## Files
`src/nba_gm_data/draft_scouting.py` (new), `draft.py`, `play.py` (draft live state and reasons), `prospect_cards.py`,
`app_actions.py` (draft and prospect payloads only), `gui/app.js` (draft board, prospects card, prospect card,
draft summary), `gui/card-board.css`, tests listed above, `scripts/research/draft_falls.py`,
`scripts/research/draft_night_trades_check.py`, `scripts/screen_hidden_upside_drafts.py`,
`data/research/draft_boards/real_board_vs_pick_2015_2025.csv`.
