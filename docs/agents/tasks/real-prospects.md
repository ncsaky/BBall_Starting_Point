# Real prospects in the first future drafts (2027-2029)

_Second pass (REAL-PROSPECTS-2), Claude Opus agent, 2026-11-18, own worktree branch. Status: **review**. Not pushed._

**TL;DR**
- **2027 now follows the scouts.** Eight public big boards and mocks (ESPN, FanSided, Bleacher Report, CBS, ClutchPoints,
  SI, Tankathon) set the order; the college stats model only gets a say as games pile up (about 15% now, half by
  20 games). Stokes, Joksimovic (Baskonia), Smith Jr., Holt and Branch III head every save's 2027 board when they declare.
- **2028 and 2029 now start with real names**: the 247Sports top 50 (class of 2027) and top 40 (class of 2028)
  high-school recruits, about 25 international prospects, and the college players likely to wait a year or two.
  Across 20 save seeds real players hold the whole 2027 top 10, about 8 of 2028's top 10 and 7 of 2029's.
- **Players declare at different times, and each save is different.** Every real player has a chance of going in
  2027, 2028, 2029 (or later). Each save draws once per player from its seed: top prospects nearly always go at once,
  borderline ones often go back to school and reappear a year older and a year more developed. Same seed, same
  classes; drafts from 2030 on are unchanged.

## 1. What changed for the player

1. **Scout-led 2027 board.** The order follows the consensus of the boards (Stokes, Joksimovic, Jordan Smith Jr.,
   Holt, Branch III, Coleman, Krivas, Ngongba II, Kharchenkov, Mullins, ...). Players on the boards without games
   this season are real prospects too: internationals (Joksimovic, Yimga Moukouri, Dash Daniels, Niang, ...),
   Brandon McCoy Jr. (Michigan, out for the season with a torn ACL; half the usual chance of going in 2027), and
   players whose only college numbers are from last season (David Mirkovic, JT Toppin, Solo Ball, ...).
2. **Recruits and internationals in 2028 and 2029.** Beckham Black, CJ Rosser, DeMarcus Henry, Cayden Daughtry,
   AJ Williams and the rest of the 247Sports top 50 (class of 2027) can enter the 2028 draft after a college year;
   the class of 2028 (Kamagate, Hiller, Touray, ...) the 2029 draft. Reclassified freshmen already in college
   (Boumtje Boumtje at Duke, Kusturica at UCLA, Musis at Florida Atlantic) take the college path with their scouting
   notes added. Internationals follow the age rule (19 during the draft year).
3. **Declaration timing.** A returner shows up in a later class one year older, with his college profile projected
   one more season (minutes, rates and shooting move by the typical one-year change for his class), so his skills and
   level change with him.
4. **Card.** Every real prospect shows the scouting view: "Consensus #6 · 8 draft boards" (hover: each outlet's rank)
   or "Recruit · class of 2027: 247Sports #1 · ESPN #1", the scouts' strengths and concerns ("Scouts like: ... ·
   Concerns: ..."), and his chance of being drafted in each year ("each save draws when he declares"). High-school and
   international players show school or club, country and commitment instead of a college season (no games are
   invented for them). College players keep the College Profile strip; in the prospect card it now sits on the right
   instead of covering the Court Influence charts (a layout bug from the first pass).

## 2. Method

### 2027: consensus board blended with the college model
- **Consensus rank** (`consensus_board`): weighted geometric mean of each player's ranks. A board's weight halves every
  90 days before 19 November (ESPN 5 Nov 0.90, B/R August board 0.52, SI June list 0.32); mocks count 0.75 of a big
  board (they mix in team need); Tankathon's undated live board 0.8. A player missing from a list of length L is
  placed at L + max(5, 0.3 L) (130 for a 100-deep board, 39 for a 30-pick mock).
- **Chance of going in 2027** = w x model chance + (1 - w) x scouts' chance for his rank, with **w = games / (games +
  20)**. With 3-6 games played w is 0.13-0.23. Reasoning: the model's same-spring accuracy (rank vs pick 0.62, AUC
  0.99) is measured on full seasons, and early-season samples are noise; boards already fold in high-school, summer
  and last-season evaluation. At 20 games (mid-January) the two count equally. A college player on no board gets at
  most the scouts' chance for rank 150 (never more than the model says).
- **Scouts' chance by rank** comes from history (drafts 2010-2026): the share of the k-th ranked college player
  (ranked by the model's draft value) drafted that June: ranks 1-10 84%, 11-20 57%, 21-30 52%, 31-45 40%,
  46-60 25%, 61-100 14-22%, 101-150 8%. The misses at the top are real returns (Sullinger, Barnes, Smart, Zeller,
  Bridges, Edey, Clingan, Filipowski). Scouts rank better than the model, so these are a floor for a board rank.
- **Expected pick** = log-blend of the consensus rank and the model's expected pick with the same w. The k-th declared
  player is anchored to slot k (the boards cover the whole draft); level, upside and age then follow the slot exactly
  as for generated prospects. For the scouts' share of a player's order, age only splits "now" versus "upside" without
  moving his overall grade, and production, recruiting grade and the public random spread do not move it again (the
  scouts' rank already prices them in).
- **Later years** for a player who does not go in 2027: the model's own split of what is left, blended (same w) with
  the history of ranked players who returned (ranked 1-10 and not drafted: 61% drafted the next year, 44% of the rest
  the year after; ranks 11-30: 41% / 15%; 31-60: 30% / 18%; 61-100: 19% / 16%), never below this year's chance for
  his rank (a returner who keeps his board rank faces the same choice next spring; without this floor a consensus
  top-3 player went undrafted through 2029 in about 1 save in 20). Seniors cannot return.
- Names are matched by a normalized key (accents, punctuation, Jr./II/III removed) plus a small alias map (JoJo ->
  Joseph Tugler, Rueben -> Ruben Prey) and the team when two players share a name (Cameron Williams of Duke, not
  Kent State). 124 board players matched the college tables; Dylan and Kayden Mingo stay separate.

### High-school recruits: timing and pick from history
Freshmen 2008-2022 with a Barttorvik recruiting rating, ranked within their season (the k-th highest rating ~ the
k-th recruit of his class), and when they were drafted:

| Recruit rank in class | Players | Drafted after 1 year | 2 years | 3 years | 4 years | Not drafted within 4 | Typical pick after 1 year |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| 1-5 | 75 | **88%** | 7% | 1% | 0% | 4% | **5** (median 4) |
| 6-10 | 75 | 52% | 17% | 4% | 1% | 25% | 18 (median 20) |
| 11-20 | 150 | 26% | 21% | 7% | 5% | 41% | 18 (median 21) |
| 21-30 | 150 | 10% | 11% | 8% | 9% | 61% | 16 |
| 31-50 | 300 | 6% | 7% | 7% | 4% | 77% | 18 |
| 51-100 | 750 | 1% | 4% | 3% | 4% | 88% | 19 |

(Typical pick: geometric mean shrunk toward the band's overall mean with three pseudo-picks; medians in the bundle.)
So a top-5 recruit is one-and-done 88% of the time and typically goes around pick 4-5; a 6-10 recruit about half the
time. A 247 rank k maps onto the k-th row; within a band the better-ranked recruit goes first. Caveat: recruits who
skipped college (G League Ignite, Overtime Elite, NBL) are not freshmen in these tables, so in 2021-2023 the k-th
freshman was slightly lower ranked than the k-th recruit.

### 2028-2029 slots
Declared players are ordered by expected pick; the k-th goes to the average pick of the k-th draftee among players
visible that far ahead in history (drafts 2012-2026: college players in the season h years before plus the top 50 /
40 recruits of the classes still to arrive). E.g. 2028: 1.2, 2.5, 3.8, 5.1, 6.4, 7.5, 9.0, 10.3, ...; 2029: 1.2,
2.5, 3.9, 5.8, 7.3, 8.6, 10.5, ... The gaps belong to generated prospects (players nobody can see yet).

### Internationals without a board rank
No local history exists for them, so a stated judgement prior: all-tournament / award players 25% in their first
eligible draft and 10% the next, expected pick 40; others 10% / 5%, pick 50. Ages from FIBA birth years; first
eligible draft by the age rule.

### Skills without college numbers
Start from the typical drafted college player at his position (e.g. a centre's rim protection and rebounding, a point
guard's passing), size from his listed height, then the scouts' tags: a strength about +1 standard deviation on the
skill(s) it names, a concern about -1 (a tag naming two skills splits it), totals eased to at most about 1.5. College
players get half a standard deviation per tag on top of their college numbers. Level: a board rank fixes a player's place (no extra spread, age only splits now vs
upside); a recruiting rank or tournament note is a looser signal, so half of the usual age, pedigree and public-spread
terms still apply. The keyword map is in
`TAG_RULES` (builder). The draft traits, older trait ratings and 94 inputs then follow the same route as every other
prospect (no college input estimates for these players).

## 3. How declaration timing works in the game
- `real_prospects.declaration_year(entry, seed)`: one uniform draw per save and player (`Random(f"{seed}:{id}:declare_v1")`)
  against his chances 2027 -> 2029; the rest of the probability means later or never.
- `real_prospects.class_entries(year, seed)`: the players whose draw is that year, ordered by expected pick, with
  their slot; at most 60 (any extra go undrafted that year). `draft.generate_draft_class_records(..., real_prospects=True)`
  builds the class around them; generated prospects keep every other slot.
- **The stored 2027 class** in `universe_2026_27_offseason.json` is the draw for seed 2027 (the draft-year seed it
  always used). A save with another seed gets its own 2027 class, scouting reports and team boards:
  `draft.draft_class_for_save` (hooked into `save.canonical_with_save`) builds them once per process and seed from the
  untouched starting universe (about 1.1-1.7 s the first time, then cached as the same object, so the per-advance
  baseline copy stays cached). To make that affordable, a team board build now computes each team's and each
  prospect's court profile once instead of once per pair (5.7 s -> 1.6 s, identical output). 2028 and 2029 are built
  per save seed as before.

## 4. Coverage across 20 save seeds (real players on the public board)

| Class | in top 10 | in top 30 | in top 60 | Expected real draftees (pool) |
| --- | --- | --- | --- | ---: |
| 2027 | 10 (10-10) | 30 (30-30) | 50 (42-60) | 53.5 |
| 2028 | 8 (6-9) | 24 (22-26) | 48 (39-48) | 51.9 |
| 2029 | 7 (4-8) | 21 (19-22) | 44 (31-45) | 40.8 |

(median, min-max; `scripts/research/real_prospects_check.py --coverage 20`.) Pool: 534 college players, 90
high-school recruits, 30 internationals, 1 board player without college data.

## 5. Checks
- `tests/test_real_prospects.py` (33 tests): pool shape and chances; consensus leads 2027 and source weights; model
  weight = games / (games + 20); board players without college data; name and team matching; consensus imputation;
  tag-to-skill map; age notes and the age rule; recruit timing table; recruits enter after a college year; reclassed
  freshmen take the college path; declaration draws deterministic per seed, different across seeds, one class per
  save; returners a year older with a developed profile; slots and generated fill; 2027 order follows the scouts;
  2030/2031/2036 identical with and without real prospects (both rating sets); prospect-realism shape on mixed classes;
  college numbers and tags shape traits; drafted real prospects' 94 inputs (college estimates for college players
  only); card blocks and payloads (college, high school, generated); stored class = seed-2027 draw with both sources;
  a save's own 2027 class (same object per seed, boards complete).
- Related modules and core suite: see the final report of this pass.
- GUI: fresh save in the browser: Upcoming Prospects shows that save's draw; Joksimovic's card shows "Baskonia ·
  Slovenia", "Consensus #2 · 8 draft boards" and the tags; Coleman's card shows the college strip with the consensus
  rank and tags beside the courts.

## 6. Known gaps and open decisions
- **An unseen (generated) prospect is the public No. 1 of 2028 in 12 of 40 saves and of 2029 in 17 of 40.** Generated
  prospects in the gap slots keep the generator's wide upside spread, while real recruits follow their rank (half of
  the usual spread, `RECRUIT_SCOUT_SHARE = 0.5`). History says the best visible player went about pick 1.2, i.e. the
  No. 1 pick was visible in most drafts. Option: narrow the generated prospects' public spread in the real years.
- **Return rate for ranks 11-40 may be high.** The 2027 chances come from how often the model's k-th ranked player was
  drafted that June (57% for 11-20). Scouts rank better, so the real rate for a November board rank is probably
  higher; in some seeds 5-7 of the board's top 17 go back to school. A knob: raise the scouts' curve (for example
  to 75% for 11-30) if that looks wrong in play.
- **No 2028/2029 boards.** ESPN's early note calls Boumtje Boumtje the early 2028 favourite; the model has him around
  pick 14. Only the top recruits' history and the college model speak to 2028/2029.
- **Internationals without a board rank use a judgement prior** (25% / 10%, pick 40-50): no local evidence.
- **Recruit ratings in the level formula are the typical rating of the k-th freshman**, not the recruit's own grade.
- **McCoy's injury factor (0.5)** is a judgement; no medical record is attached (real players keep a neutral medical
  profile).
- **New saves with a non-2027 seed spend about 1.5 s once** (per process and seed) building their own 2027 boards.
- `scripts/research/real_prospects.py` still evaluates the chained model (unused) for the record.
- Strengths/weaknesses are paraphrased from the outlets; ranks are facts.

## 7. How to refresh (later in the college season)
```bash
# 1. re-download the current season's Barttorvik players_2027.csv and teams/team_results_2027.csv (local only)
# 2. update data/research/prospect_scouting/draft_2027_boards.json with newer boards (ranks per source, dates)
#    and recruits_2028_2029.json with new recruiting ranks
PYTHONPATH=src .venv/bin/python scripts/research/real_prospects.py --apply-universe   # refit, rewrite bundle + stored 2027 class
PYTHONPATH=src .venv/bin/python scripts/research/real_prospects_check.py --coverage 20
PYTHONPATH=src .venv/bin/python scripts/research/real_prospects_check.py --year 2027 --seed 7
PYTHONPATH=src .venv/bin/python -m unittest tests.test_real_prospects
```
As games accumulate the model weight rises automatically (games / (games + 20)). Changing `CURRENT_SEASON` in the
builder rolls the window forward a year (the board file names and `SCOUT_AS_OF` then need updating too).

## Files
- `data/research/prospect_scouting/draft_2027_boards.json`, `recruits_2028_2029.json` (scouting inputs, committed)
- `scripts/research/real_prospects.py` (builder: projection, consensus, curves, recruit timing, pool),
  `scripts/research/real_prospects_check.py` (sanity read, `--coverage`)
- `data/canonical/real_prospects.json` (derived bundle v2: pool with chances by year and per-year views; one line per player)
- `src/nba_gm_data/real_prospects.py` (declaration draws, class entries, skills, scouting and card blocks)
- `src/nba_gm_data/draft.py` (class assembly, real prospect records for all kinds, `draft_class_for_save`, seed in
  `build_draft_context`, faster board build), `src/nba_gm_data/spatial.py` (optional per-build cache),
  `src/nba_gm_data/save.py` (one hook), `src/nba_gm_data/ingest.py` (scouting source)
- `src/nba_gm_data/app_actions.py`, `prospect_cards.py`, `gui/app.js`, `gui/card-board.css` (card)
- `data/canonical/universe_2026_27_offseason.json` (stored 2027 class = seed-2027 draw; scouting source registered)
- `tests/test_real_prospects.py`

## Resume state
Done: scouting data, builder, bundle v2, per-save declaration draws, stored class, save hook, card, tests, this note.
Remaining for the coordinator: review, decide the open items above, run the scorecards if wanted (opening-day ratings
are unchanged; only future draftees differ).

---

## First pass (2026-11-18, summary)
The first pass put real college players into the 2027-2029 drafts from the Barttorvik college tables: one model per
horizon (chance of being drafted, expected pick; out of sample on 2022-2026: same-spring AUC 0.986, rank vs pick
0.62; one year ahead 0.92 / 0.31; two years ahead 0.90 / 0.21), a current-player blend (this season's games with last
season or the freshman recruiting band), and fitted college -> 94-input relationships on 230 players drafted
2019-2025 (free throws 0.64, threes 0.40-0.52, passing 0.49-0.64, rebounding 0.62-0.78, contests 0.72, steals
0.52-0.60, ball security -0.34). Drafted real college prospects blend those estimates into their entry inputs
(weight 0.2 + 0.5 x correlation, at most 0.6, times minutes / (minutes + 300)). Draft traits are standard scores of
college rates against drafted players' final seasons, 16 trait points per standard score, softly bounded to 5-95.
All of that is unchanged here.
