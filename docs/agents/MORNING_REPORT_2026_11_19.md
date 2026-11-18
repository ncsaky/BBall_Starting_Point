# Morning report: night of Nov 18–19

**TL;DR**
- **Main (yours already):**
  - Injury risk is a body figure everywhere.
  - The playmaking / on-ball / help court charts are built, for players and teams.
  - Codex's aging work is reviewed at your two-thirds spread.
  - Spacing now shows the engine's real number.
  - Eight broken interface tests are fixed, plus two real bugs they exposed.
  - Everything is pushed.
- **Five branches of work you didn't ask for yet,** each checked by me, plus one combined branch. The headline
  surprises:
  - A month simulates **about 4× faster** with identical results.
  - Stars' box scores finally look like stars': Wembanyama 30 points per 36, Jokić 10 assists, Luka 4
    turnovers.
  - Points props went from worse than a coin flip to clearly better.
  - Generated draftees can now become starters and stars.
- **Decide (top of the list below):** merge `claude/overnight-integration`. It holds speed, box scores, lineup chemistry
  and Codex's rotation fix, and beats main on every betting-odds number. Then three branch-specific choices.

## Overnight: what's waiting for you

### Branches (nothing merged into main; all checked by me)
| Branch | What it does | Checked | My call |
|---|---|---|---|
| `claude/month-speed` | A month runs about 4× faster (November 125 s → 31 s, deadline month 549 → 275 s) with identical results | Re-ran its identical-results check myself: identical, 125 → 31 s | Merge |
| `claude/box-star-stats` | Who gets the turnovers, assists, steals, free throws and points (examples below) | Re-ran its real-stat check: numbers match | Merge |
| `claude/lineup-fit` | Lineup chemistry from 12,481 real lineups: the 5th shooter adds less, and each non-shooter beyond two costs defense | Its odds runs; my combined run | Merge |
| `claude/prospect-realism` | Realistic draft classes and growth without NCAA data | Two-season AI league, main vs branch | Merge after your 2 decisions |
| `claude/ratings-audit` | Rim protection no longer flattens; blocks go to real shot-blockers; ratings checked against 6 impact metrics | Its two odds runs per change; I re-ran its tests and real-stat check: they match | Merge if you accept decision 2 |
| `claude/overnight-integration` | main + month-speed + box-star-stats + lineup-fit (+ Codex's rotation fix) | Me: 334 core + focused tests pass; 18/18 in both rating sets; odds Brier 0.1948, log loss 0.5772, spread 4.93, totals 5.41 (all better than main) | Merge this one instead of the three separately |

**Box-score examples** (points per 36 minutes unless noted; sim before → after, then real):
- Wembanyama 20.5 → 29.7 (real 30.8).
- Dort 18.8 → 12.9 (real 11.2).
- Jokić assists 6.5 → 10.1 (real 11.1).
- Luka turnovers 2.4 → 3.8 (real 4.0).
- Average errors per 36: points 2.60 → 1.27, turnovers 0.58 → 0.34, free throws 1.15 → 0.57.
- Points props: Brier 0.273 → 0.220 (0.25 is a coin flip).

**Combined-branch scorecards:**
- Betting odds vs main: Brier 0.1948 vs 0.1955, log loss 0.5772 vs 0.5786, spread 4.93 vs 5.04, totals 5.41 vs
  5.51.
- All 18 stat targets in range in both rating sets; 334 core tests pass.
- Adding Codex's rotation fix changed neither scorecard, because both use real or projected minutes rather than the
  AI coach's choices. The rotation change only shows in actual play.

**To merge the combined branch** (from the project folder; I haven't run it). It doesn't touch the ratings
files, so nothing needs regenerating afterwards:
`git merge claude/overnight-integration`
- **Codex's rotation fix:** the branch carries it as a commit, so after merging, the uncommitted rotation edits in the
  folder are already included. Discard Codex's local copy only after checking they're identical.
- **All branches are local only** (not pushed to GitHub).

### Decisions for you
1. **Prospect realism (`claude/prospect-realism`).**
   - **What it changes:** in the 94-input ratings, growth used to lose about half its size on the way into the
     inputs, so generated draftees never became stars or starters.
   - **The fix touches every player's development** in that rating set: young players grow and veterans decline at
     the size the older set already used.
   - **Its results (year 4, picks 1–3):** starters 7% → 64% (real about 73%).
   - **My two-season league check:**
     - Best generated draftee 56.7 → 65.2 overall.
     - Two draftees reach the league top 100 (was 0).
     - Stars unchanged.
   - **Your calls:**
     - (a) Keep the routing change? I recommend yes.
     - (b) The older rating set now makes too many young stars from picks 4–30, real 2026 rookies included. Accept
       it, since that set is being retired, or tune it separately?
     - (c) Top-3 picks become stars less often than real ones (7% vs about 20–33%). That's probably a rookie-ratings
       follow-up.
2. **Ratings audit (`claude/ratings-audit`).**
   - **Rim protection** follows real rim evidence instead of flattening at the top: Wembanyama +17, Holmgren +15,
     Gobert +14.7. Rim order vs Basketball Index for bigs went from 0.70 to 0.87.
   - **Blocks go to real shot-blockers:** Jokić 2.3 → 0.7 per 36, Jay Huff 1.1 → 2.9.
   - **Brunson's value** moves from 102nd to 42nd (evidence: about 60th).
   - **A bad input proxy was dropped:** attack recognition's only measure rated Westbrook 99th percentile and
     DeRozan 3rd.
   - **It also includes the box-score branch.**
   - **Betting odds vs main:**
     - Brier 0.1942 vs 0.1955, log loss 0.5745 vs 0.5786, spread 4.65 vs 5.04: better.
     - Totals error 5.63 vs 5.51: worse. Per-game scoring environments drift slightly; it didn't tune toward the
       market, on purpose.
   - **Your calls:**
     - (a) Accept the totals cost?
     - (b) It changed what feeds team strength: each player's contribution now comes from the value on his card,
       which is fitted to real impact, instead of a hand-made blend. That fixed an odds regression the rim work
       caused (elite non-rim defenders like Anunoby and Draymond had lost value). I recommend accepting it.
     - (c) Smaller open questions are in its report: rebuilding the older ratings' rim value, energy bigs like
       Diabaté/Queta/Kornet, and evidence for the jump and attack-recognition inputs.
   - **After merging,** run this once so the game picks up the corrected inputs:
     `gunzip -kf data/canonical/player_inputs_2026_27.json.gz`
3. **Lineup chemistry:** a third effect, shooters being worth more next to a ball-dominant creator, is built but
   off.
   - **Evidence:** about +1.6 per 100 possessions in real lineups.
   - **Cost:** it moved the game about 0.1 points away from the betting market on spreads.
   - **Your call:** on or off? The agent also asks whether to download more seasons of real lineup data (NBA.com /
     pbpstats) to settle the open effects.
4. **Codex's rotation fix (ROT-SHAPE).**
   - **What it does:** stars 28 → 33.5 minutes a game, back-of-rotation 22 → 10, all within a minute of Basketball
     Index.
   - **Status:** it's still uncommitted in the main folder; Codex hadn't marked it finished.
   - **Testing:** I tested it inside the combined branch (see the table).
   - **One miss:** Bruce Brown still plays about 20 minutes (Basketball Index projects 4.5).

### Mistakes and fixes overnight (so you know)
- **My mistake: Codex's unfinished rotation edits got committed to main** inside my spacing commit (the second time
  tonight). I took them back out in the next commit; Codex's working copy is untouched. I've saved a rule to check
  shared files before committing.
- **Giannis's trade value fell 94 → 90** because of the new playoff-performer blend; Basketball Index's playoff
  grades rate his recent playoffs lower. He's still 6th among regular players. Say if you'd rather undo the blend.
- **The full test suite earlier caught one failure** from that blend (a market-ranking test). Fixed: the test now
  ranks without LeBron's fixed exception.

### Main changes overnight (already pushed)
- **Injury risk is a body figure everywhere:**
  - Player Finder, trade screens, offers, free agency, the injury report (with the injured part highlighted) and
    contract talks.
  - The number is now labeled as the front office's risk index. It isn't "out of 10"; it can run to about 15.
- **Team court charts** got Playmaking, On the ball and Help views.
- **Spacing** on the card, Player Finder, free agency and team identity now shows the engine's real spacing value.
  The card's "Spacing" used to repeat "Shooting".
- **Aging review:**
  - The good-or-bad-year draw is two-thirds of Basketball Index's spread, measured per rating set.
  - Found and fixed a bug: head coaches' ratings drifted on every save load.
- **Interface tests:** all 29 browser test files pass (Codex), and the two real bugs they found are fixed: the card
  page counter and the startup video retrying on every click.

## What changed in the game

1. **Coaching overhaul.** Each head-coach and coordinator rating now has its own effect on the game:
   - Shot quality and spacing design help the offense. Spacing design is worth more with shooters on the roster.
   - Creator usage helps the offense more when the team has a real primary creator.
   - Coverage design, matchup scheming and discipline help the defense. Discipline also lowers foul rates.
   - Player relations gives a small boost on both ends.
   - Game management adds a playoff-only boost.
   - Rotation management lets the coach pick better matchups and ease injured players back carefully.
   - Player development now uses your save's actual head coach (locker room and communication). The game previously used a fixed table.
   - Coach cards only describe effects the game really uses.
   - Codex's staff lifecycle (coaches improve, decline, retire and get poached) is in too.
2. **Coming back from injury.** A player who missed games plays fewer minutes for the next few games. The cut is based on real return patterns: about 16% fewer minutes in the first game back after missing 6–10 games. Good rotation managers bring players back more slowly. Poor ones rush them back.
3. **AI teams and injury risk.** Trade AI now rates injury risk with the new per-body-part model, blended in the first season with Basketball Index's injury forecasts. Anthony Davis-type players now carry the risk they should.
4. **Box-score swings.** Team shooting from game to game now varies as much as in the real NBA (field-goal percentage spread about ±6 points). Possessions and rebounds stayed on target.
5. **Playoff performers** (committed after the odds check passed). The "who raises their game in the playoffs" ratings now use a blend: half real playoff box-score production and half Basketball Index playoff talent grades. Top 10: Jokić, Shai, Luka, LeBron, Mitchell, Tatum, Haliburton, Reaves, Cade, Kawhi. Brunson is still low (65th) because his underlying skill ratings are low, not because of the playoff formula. That is worth a separate look at his ratings with evidence.

## Your late additions (GUI)
- **Injury body map (built).**
  - **Mini figure:** the injury-risk ring on the player card is now a small body figure that keeps the risk number.
    Hovering it gives a one-line summary.
  - **New card page, "Health & Injury Outlook":** front and back body outlines with colored hotspots. Green means lower
    risk than a typical rotation player, pale is about typical, yellow, orange and red are higher, and deep red with a
    pulse marks a current injury. Bigger spots mean more games at stake.
  - **The table beside it:** expected games missed per body part, against a typical player, and injuries there in the
    last 3 years.
  - **Where the numbers come from:** the same per-body-part injury model the season sim uses.
  - **Normal-role minutes:** a benched or injured player is judged at his normal minutes, so his map describes his
    body rather than this week's rotation.
  - **Checked** in the game on Mike Conley (current knee injury) and Jayson Tatum.
- **Playmaking and defense court charts (built after your OK).** On the player card's Court Influence panel:
  - **Offense court:** switches between Scoring and Playmaking. Playmaking shows how much better or worse his
    teammates shoot, by zone, while he plays (his own shots left out).
  - **Defense court:** switches between Overall, On his man and Help. Help leaves out his own man, as you suggested.
  - **Playmaking's size** is fitted from the game's ratings to Basketball Index's "impact on teammates' shooting"
    (accuracy on unseen players r 0.59; passing reads matter most, then shooting gravity, handle and drives).
  - **The sim uses it:** it is added to each team's zone shooting and measured against the league's own players, so
    league scoring is unchanged. Teams range from about −0.6 to +0.9 points of team FG% from playmaking.
  - **On his man + Help** split the engine's existing zone defense and add up to Overall exactly.
  - **Scorecards unchanged:** 18/18 stat targets; Brier 0.1955, log loss 0.5786.
  - **Noticed:** the engine rates Jokić and Gobert identical at rim protection (+10.8 points each). The rim term seems
    to saturate. Worth an evidence check (not changed).

## Scorecards (after tonight's changes)
- **Real-stat targets:** all 18 league numbers in range, on both rating sets. Pace 102.2, offensive rating 113.2, true shooting .586. One player outlier remains: Jokić averages about 6.5 assists per 36 minutes in the sim against 11.1 in real life.
- **Betting-odds test (100 seasons):** unchanged by tonight's changes. Brier 0.1955 and log loss 0.5786 (before: 0.1954 / 0.5785), still slightly better than the betting market's own 0.1962. Spread error 5.03 points, totals 5.51.
- **Full test suite:** 1,764 tests pass (28 skipped).

## Basketball Index data
- **Captured:**
  - All 664 leaderboard measures
  - Lineup Explorer (61,037 lineups)
  - Lineups and games from the expected-points tools, plus referees and WOWY
  - Team leaderboards
  - Progression (EPM, RAPM, DPM and others by player-season)
  - Growth curves and coach development
  - The full injury tracker
  - 2026–27 minutes and availability projections
  - Playoff talent grades
  - Role Labs
- **Stays on your computer:** everything above lives in git-ignored folders, as you asked. Only fitted game models are committed.
- **Skipped:**
  - Player Profiles, Skills and Career Trends duplicate data we already have.
  - The Similarity tool hung on the server's loading screen. It only compares players' play-type mix, which we can compute from data we already have.
- **NCAA:** blocked on your sign-in (see the queue below).
- **Ideas for the data we don't use yet:** see `docs/agents/DATA_USE_IDEAS_2026_11_19.md`. The top three are lineup chemistry from 61,000 real lineups, player value from several impact metrics instead of one, and realistic draft prospects from NCAA data.

## Fable 5.2 recommendation
Save both resets for now:
1. **One "realism review" once the current overhauls settle.** Give it the scorecards and the player-model docs, and ask where the sim will feel wrong to a Nerd Sesh or Basketball Index viewer, and what evidence would settle each doubt.
2. **The prospect-generator design after the NCAA data is in.** Turning college profiles into NBA prospects and their growth is a hard modeling problem.

## Finding: rotations are too flat (not changed yet)
- **Overall:** the game's starting minutes targets for 2026–27 track Basketball Index's healthy-rotation minutes closely (correlation 0.81 over 329 players).
- **The gap is at the ends:**
  - Stars get about 2 minutes a game fewer than Basketball Index projects.
  - Back-of-rotation players get about 7 more.
  - Some deep-bench players have about 20 minutes in the game against about 5 in Basketball Index's projection: Bruce Brown, Mitchell Robinson, Luke Kennard and Jordan Poole.
- **Some low star numbers are expected:** Kyrie, Lillard and Tatum are coming back from major injuries, while Basketball Index's number assumes a healthy player.
- **Why it matters:** flat minutes blur the difference between stars and role players, which is the point of the player model.
- **Next step:** check the minutes in the two-season test game against these projections and tune the AI coach's rotation shape if they hold. This is a good Codex task.

## Earlier queue items (from the first half of the night)
1. **NCAA sign-in.**
   - If you can sign in at basketball-index.com (a separate site and account from bball-index.com) and your
     membership covers NCAA, I can capture it in minutes.
   - If not, the prospect branch above already works without it.
2. **Old Basketball Index files in git history.** A few early commits pushed Basketball Index-derived tables to
   GitHub before you chose "local only". Leave them (if the repo is private) or rewrite history (a destructive
   force-push).
3. **Done overnight:** Codex's aging work (reviewed, two-thirds spread), the heat maps, the eight browser tests
   (fixed, plus the two bugs they found) and the two-season test game (finished cleanly).
