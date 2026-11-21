# Codex task queue

Paste one prompt into a **fresh** Codex chat. One task per chat keeps it from drifting after context compaction. Each prompt is self-contained. Claude reviews the result and updates `BOARD.md`.

Current priority (2026-11-21, early): OFFSEASON-DECISIONS-EVIDENCE now, ODDS-COACH after TRADE-MARKET's long runs. GUI tasks are parked at the bottom.

---

## Ready now (2026-11-21, afternoon): HEADSHOT-GEN-PILOT (fresh chat; needs image generation)

### HEADSHOT-GEN-PILOT: AI-generated fictional faces that age through a career

Suggested settings: GPT-6.2 Sol, Medium, fresh chat (one with image generation available).

```
Read AGENTS.md and docs/agents/BOARD.md first. You own task HEADSHOT-GEN-PILOT (its board row exists; set it to
"in progress (Codex)"). Background: the game needs faces for made-up players and staff. The user wants real-looking
photos of FICTIONAL people (no cartoons), and each person should change over their career (rookie photo, later a beard
or new haircut, grey hair at the end), with the changes not uniform across people. This is a pilot to judge quality,
identity consistency, speed and cost before making a full library.

Setup: your own git worktree:
  git worktree add ../BBall_codex_headshots -b codex/headshot-gen-pilot HEAD
Commit on that branch; never push, never commit to main. Nothing under src/, gui/ or tests/. Images go in
output/headshots-gen-pilot/ (git-ignored); commit only the script, the manifest and the report.

Hard rules:
- Fictional people only. Never put a real person's name, a real photo, or "looks like <celebrity/player>" in any prompt.
- No logos, team names, real jersey designs, brand marks or readable text in images.
- Adults only (players 19+).
- Don't spend money or use API keys. If you cannot generate images in this environment, stop and report which route
  would work (ChatGPT app, OpenAI API with an estimated cost per image, other) instead of improvising.

Make 12 people:
- 6 players (men, varied ethnicities, builds and face shapes), 4 stages each: rookie (~20), prime (~26),
  veteran (~31), late career (~35).
- 6 staff (4 men, 2 women, varied ethnicities), 3 stages each: ~38, ~50, ~62.
First write a short plan per person: which stage changes what (beard grows or goes, haircut, braids/locs/shaved head,
hairline, greying, a little weight, glasses for staff). Vary it: some people barely change, some change a lot, and the
changes come at different stages.
Style for every image: realistic photo, head and upper chest, facing the camera, plain light-grey studio background,
even lighting, square. Players wear a plain generic sleeveless jersey (no number); staff a suit, polo or quarter-zip,
all without logos. Keep each person recognisably the same person: make stage 1 from text, then each later stage by
editing the previous image ("same person, about 6 years older, ...").

Output:
- output/headshots-gen-pilot/<person_id>/stage<N>.png
- data/research/headshot_gen_pilot_manifest.json: id, gender, role (player/staff), per stage {age, file, changes},
  the exact prompts, the tool/model and the date.
- output/headshots-gen-pilot/contact_sheet.html: one row per person, stages left to right, also a greyscale copy of
  each row (the game shows headshots in greyscale).
- docs/agents/tasks/headshot-gen-pilot.md: plain-language TL;DR first (5 lines); how often the same person stayed
  recognisable (your honest rating per person); failures (wrong age, logos, odd hands, drift); time per image; how many
  images your plan allows per day; what a full library would take (about 400 players x 4 stages and 300 staff x 3
  stages); the image tool's terms on using outputs in a game (paraphrased, with the link).
Commit after each few people so a usage limit loses nothing. Set the board row to "review" and stop.
```

---

## Ready now (2026-11-21, midday): DEVELOPMENT-EVIDENCE (fresh chat)

### DEVELOPMENT-EVIDENCE: how real NBA players develop and decline

Suggested settings: GPT-6.2 Sol, High, fresh chat.

```
Read AGENTS.md and docs/agents/BOARD.md first. You own task DEVELOPMENT-EVIDENCE (its board row already exists; set it to "in progress (Codex)").
Read docs/agents/tasks/ten-season-findings.md (the game's development curve and a hidden ceiling on stars) and
docs/agents/tasks/offseason-decisions-evidence.md (your format: rules fitted on some seasons, tested on held-out ones).

Setup: your own git worktree:
  git worktree add ../BBall_codex_development -b codex/development-evidence HEAD
Symlink .venv and the git-ignored data/research/bbi/ files from the main checkout (Basketball Index's LEBRON and
progression tables are in data/research/bbi/tools/, e.g. progression_player_seasons.csv.gz). Commit on that branch;
never push, never commit to main. Research only: nothing under src/, gui/ or tests/.

Goal: the game's player development needs an evidence target. Build, from about 2005-2026 public data (Basketball
Reference advanced stats, box plus-minus / VORP, minutes; Basketball Index LEBRON where available; draft position), with
sources recorded:
1. Development curves: average year-over-year change in an all-in-one impact measure by age, overall and by starting
   level (e.g. bottom/middle/top of the league at that age), with the spread (10th-90th percentile). Peak age. How
   steeply players decline after 30, and how that differs for stars.
2. Star formation: of players at each level at ages 19-23, what share become top-10 / top-25 / top-50 players later,
   and when. Same by draft slot (1-3, 4-10, 11-30, second round, undrafted).
3. How many genuine superstar-level players (top-5 impact) exist in a typical season, how long they stay there, and how
   often a new one appears (the game's league slowly lost its superstars; we need the real replacement rate).
4. Late bloomers and busts: shares and examples.
Fit simple rules where the data allow and test them on held-out seasons. Output:
data/research/development_evidence.json, scripts/research/development_evidence_fit.py,
docs/agents/tasks/development-evidence.md (plain-language TL;DR first, 5 lines; tables; named examples; gaps).
Paraphrase sources. Save and commit after each part so a usage limit loses nothing. Set the board row to "review"
and stop.
```

---

## Ready now (2026-11-21, overnight): INJURY-HISTORY-2023-25 (fresh chat; long but light)

### INJURY-HISTORY-2023-25: complete injury records for 2023-24 and 2024-25, the way 2025-26 was done

Suggested settings: GPT-6.2 Sol, High, fresh chat.

```
Read AGENTS.md and docs/agents/BOARD.md first. You own task INJURY-HISTORY-2023-25 (its board row already exists; set it to "in progress (Codex)").
Read docs/agents/tasks/injury-history-2025-26.md (your own earlier work), docs/agents/tasks/star-injuries.md
(especially "What's left" item 1) and docs/agents/tasks/injuries-2.md.

Setup: your own git worktree:
  git worktree add ../BBall_codex_injury_history_2 -b codex/injury-history-2023-25 HEAD
Symlink from the main checkout: .venv, every git-ignored file under data/research/bbi/ (including tools/), and
output/injuries-2 (its nba_pdf/ cache). Commit on that branch; never push, never commit to main. Raw Basketball Index
data stays local; never commit it.

Goal: the injury model's league-wide level is anchored on the Basketball Index tracker for 2021-25, but your 2025-26
work showed the tracker misses many injuries that cost games (about 40-43 entries per 1,000 games in 2023-25 against
about 52 in the complete 2025-26 record). Build the same complete record for 2023-24 and 2024-25 so the model can be
anchored to complete counts.
1. Box scores: the repo has 2025-26 only. Fetch 2023-24 and 2024-25 regular-season and playoff box scores from ESPN's
   public API (the same endpoints your 2025-26 builder used), politely (small delays, cache everything under
   output/injury-history-2023-25/, never refetch). Who missed which team games while rostered.
2. Reasons: the NBA's official injury report PDFs for each game day (same parser; the filename pattern changed in
   December 2025, check what it was in 2023-25).
3. Build data/research/injury_history_2023_24.json and injury_history_2024_25.json in the same format as 2025-26, with
   the same reason categories and the same comparison against the tracker (matched entries, additions, entries per
   1,000 games, with and without injury-management-only and opener-carryover stretches).
4. Extend scripts/research/injury_history_2025_26.py (or a sibling script) so all three seasons rebuild the same way.
This is network-heavy but CPU-light: no simulations. Save and commit after each season so a usage limit loses nothing.
Do NOT change the injury model, health.py or the git-ignored evidence files; the coordinator plugs the files in.
Report in docs/agents/tasks/injury-history-2023-25.md: plain-language TL;DR first (3 lines), coverage, the tracker
comparison per season (all three seasons side by side), examples, gaps. Set the board row to "review" and stop.
```

---

## Ready now (2026-11-21, late night): README-REFRESH (fresh chat)

Docs only; light.

### README-REFRESH: bring the GitHub README up to date

Suggested settings: GPT-6.2 Sol, Medium, fresh chat.

```
Read AGENTS.md and docs/agents/BOARD.md first. You own task README-REFRESH (its board row already exists; set it to "in progress (Codex)").
Setup: your own git worktree: git worktree add ../BBall_codex_readme -b codex/readme-refresh HEAD . Commit on that
branch; never push, never commit to main. Change only README.md (and, if needed, links to existing docs).

The user says README.md is badly out of date. Rewrite it to describe the game as it is now, for a friend or a new
contributor, in plain everyday language (AGENTS.md section 3). Read the "done" rows of docs/agents/BOARD.md and these
reports for what exists now: docs/PLAYTEST_GUIDE_2026_11_20.md, docs/agents/tasks/fa-real-slice1.md,
fa-real-slice2.md, trade-market.md, trade-followups.md, trade-deadline-counters.md, keep-stars.md, injuries-2.md,
draft-boards (see the board), slideshows.md, tables-icons.md, analyst-first.md, defense-ratings.md, odds-coach.md.
Check every claim against the code or a report; drop anything that is no longer true (e.g. old calendar dates, old
contract rules, "minutes x $0.48M" prices, the lottery stop).
Structure: what the game is (one paragraph); what you can do (seasons, the offseason's four stops, free agency with Bird
rights/options/qualifying offers/cap holds and exceptions, trades with front-office personalities, negotiations, bidding
wars and the Trade Market board, the draft and scouting, injuries and rest, minutes and the coach, player ratings and
where they come from, awards and season slideshows); how to install and run the GUI and CLI; how to run tests
(scripts/run_core_tests.sh, scripts/run_tests_parallel.py, the two scorecards); how the project is organised (src/
modules at a high level, data/, docs/agents/ coordination, AGENTS.md); current status (private friends-and-family
beta; Mac builds via scripts/build_macos_beta.sh; known gaps from the playtest guide); data and privacy (paid
Basketball Index data stays local and is never committed; the game ships without private data).
Keep it under about 250 lines. Do not include personal details, the user's name or email, machine addresses, or
anything from output/. Paraphrase; no long copied passages.
When done, set the board row to "review" and stop.
```

---

## Ready now (2026-11-21): ROSTER-EDGE-EVIDENCE (fresh chat)

Laptop rule: at most two heavy jobs at once. One is running now (the betting-test agent). This task is research only: light.

### ROSTER-EDGE-EVIDENCE: how real teams use two-way contracts, camp deals, roster cuts and sign-and-trades

Suggested settings: GPT-6.2 Sol, High, fresh chat.

```
Read AGENTS.md and docs/agents/BOARD.md first. You own task ROSTER-EDGE-EVIDENCE (its board row already exists; set it to "in progress (Codex)").
Read docs/agents/tasks/fa-realism-plan.md (slice 4), docs/agents/tasks/fa-realism-research.md (the rules you already
researched: two-ways, Exhibit 10, waivers, sign-and-trades) and docs/agents/tasks/offseason-decisions-evidence.md
(your format: rules fitted on three summers, tested on the fourth).

Setup: your own git worktree:
  git worktree add ../BBall_codex_roster_edge -b codex/roster-edge-evidence HEAD
Commit on that branch; never push, never commit to main. Research only: no files under src/, gui/ or tests/.

Goal: free agency's slice 4 builds two-way contracts, Exhibit 10 camp deals, the 21-to-15 roster cutdown and
sign-and-trades. AI teams need measured rules for these decisions, from the 2023, 2024, 2025 and 2026 offseasons and
seasons (sourced rows: RealGM/Hoops Rumors/Spotrac/NBA.com/team releases; record URL and date). One evidence collection
per decision, plus a short fit where the data allow:
1. Two-way contracts: who gets them (draft slot or undrafted, age, G League production, prior two-way), how many teams
   fill all 3 slots and when, how many two-ways reach the 50-game limit, and conversions to standard deals (how many per
   season, when, which players: production, injuries on the NBA roster).
2. Exhibit 10 deals: how many per team each camp, how many convert to two-ways before opening night, how many earn the
   G League bonus, how many make the opening roster.
3. The camp cutdown: how many players each team carries into camp (up to 21), who gets cut (guarantees, age, draft
   status, camp invite vs signed), waiver claims of camp cuts (how many, by whom).
4. Sign-and-trades: every one in 2023-2026 (your earlier research found 3, 11, 4 and 4), with the reason each side
   did it (the receiving team over the cap, the sending team getting value for a departing free agent, base-year
   compensation cases), the contract terms, and whether the receiving team was hard-capped.
5. Late free agency and overseas: veterans who signed after August 1 or in camp, and players who left for overseas,
   by age and prior role, so the game's late market is thin in the right way.
For each: counts per season, the rule teams seem to follow and its held-out accuracy where a fit is possible, named
examples, and gaps.

Output: data/research/roster_edge_2023_2026.json (rows plus sources), scripts/research/roster_edge_fit.py,
docs/agents/tasks/roster-edge-evidence.md. Report: plain-language TL;DR first (5 lines, no jargon; define each term
simply), then one section per decision. Paraphrase sources; don't copy long passages. Save and commit after each
decision so a usage limit loses nothing. Set the board row to "review" and stop.
```

---

## Ready now (2026-11-21): INJURY-HISTORY-2025-26 (fresh chat)

Laptop rule: at most two heavy jobs at once (FA-REAL slice 2 and a coordinator test run are the two now). Keep this task light: fetching and parsing only, no season simulations.

### INJURY-HISTORY-2025-26: a complete 2025-26 injury record for every real player

Suggested settings: GPT-6.2 Sol, High, fresh chat.

```
Read AGENTS.md and docs/agents/BOARD.md first. You own task INJURY-HISTORY-2025-26 (its board row already exists; set it to "in progress (Codex)").
Read docs/agents/tasks/top30-games.md (especially "What's left" item 1), docs/agents/tasks/injuries-2.md and
docs/agents/tasks/injury-followups.md.

Setup: your own git worktree:
  git worktree add ../BBall_codex_injury_history -b codex/injury-history-2025-26 HEAD
Symlink from the main checkout: .venv, every git-ignored file under data/research/bbi/ (including tools/), and
output/injuries-2 (its nba_pdf/ cache of official injury reports). Commit on branch codex/injury-history-2025-26; never
push, never commit to main. Raw Basketball Index data stays local; never commit it.

Problem: the injury model starts every real player from his recorded injury history. Its source, the Basketball Index
tracker, is missing about two-thirds of 2025-26 (18.5 entries per 1,000 games played against 50-55 in 2023-25). The
game's stars therefore start with too little history and play too many games.

Build data/research/injury_history_2025_26.json: every 2025-26 absence stretch for every player in the game's real
pool, from:
- the 2025-26 box scores already in the repo (data/research/game_boxscores_2025_26.json): who missed which of his
  team's games while on the roster;
- the NBA's official injury report for each game day (the PDFs; scripts/research/opening_night_injuries.py already
  fetches and parses them, standard library only; reuse its parser and cache, and fetch politely with small delays):
  the listed reason (injury/illness with body part and diagnosis, rest, personal, G League, suspension, not with team).
For each stretch: player, team, first and last game missed, games missed, reason category, body part and diagnosis
where listed, and sources. Separate injuries and illness from rest, personal, G League and suspensions. Then compare
with the tracker's 2025-26 entries: how many tracker entries you match, how many new injury stretches you add, and
the resulting entries per 1,000 games played (target: in line with 2023-25's 50-55 if real).
Write a small script scripts/research/injury_history_2025_26.py that rebuilds the file.

Do NOT change the injury model, health.py, or the git-ignored data/canonical/injury_player_evidence_v2.json. Another
agent reads it right now; the coordinator plugs your file in later. Do NOT touch src/, gui/ or tests/ beyond one test
for your parser if you change it.
Report in docs/agents/tasks/injury-history-2025-26.md: a plain-language TL;DR first (3 lines), then coverage numbers,
the comparison with the tracker, examples (e.g. a star's 2025-26 record before and after), gaps, and how to plug the
file into scripts/build_injury_model.py. Set the board row to "review" and stop.
```

---

## Ready now (2026-11-21, early): OFFSEASON-DECISIONS-EVIDENCE (fresh chat); ODDS-COACH still waits

Running now: TRADE-MARKET, FA-REAL slice 1 and TOP30-GAMES (Claude agents). This task is data research only and touches no code they own.

### OFFSEASON-DECISIONS-EVIDENCE: how real players and teams decide options, qualifying offers, extensions and offer sheets

Suggested settings: GPT-6.2 Sol, High, fresh chat.

```
Read AGENTS.md and docs/agents/BOARD.md first. You own task OFFSEASON-DECISIONS-EVIDENCE (its board row already exists; set it to "in progress (Codex)").
Read docs/agents/tasks/fa-realism-plan.md (slices 2 and 3 need this evidence) and docs/agents/tasks/fa-realism-research.md (your earlier research; reuse its sources).

Setup: your own git worktree:
  git worktree add ../BBall_codex_offseason_evidence -b codex/offseason-decisions-evidence HEAD
Symlink .venv and data/canonical/universe_2026_27_offseason.sqlite from the main checkout if you need the game's player
values. Commit on branch codex/offseason-decisions-evidence; never push, never commit to main.
This is research only: no engine or GUI changes.

Goal: AI teams and players in the realistic free-agency rebuild will make these decisions. Each needs a measured rule
grounded in what really happened in the 2023, 2024, 2025 and 2026 offseasons. Build one evidence file per decision, with
every row sourced (Spotrac/RealGM/Hoops Rumors/NBA.com/team releases; record URL and date), plus a short fit of what
drives the decision:
1. Player options: opt in vs opt out (or opt out and re-sign). For each: age, option salary, the player's market value
   at the time (use the game's on-court value where the player exists in the game, or a public value measure), injury,
   team context. What predicts opting out?
2. Team options (veteran and rookie-scale third/fourth year): exercised vs declined, against value and salary.
3. Qualifying offers: tendered vs not, for every eligible player, against value, the QO amount and team payroll. Then
   the outcomes: re-signed before July, re-signed later, signed an offer sheet (matched or not), accepted the QO,
   renounced.
4. Rookie-scale extensions (before the October deadline): who extended, at what share of the cap, and who didn't and
   then became restricted.
5. Offer sheets: which teams gave them, to whom, the terms (incl. backloading), whether matched, and the bidder's cap
   situation (room or exception).
6. Early terminations and declined options that led to a same-team re-sign.
For each: counts per summer, the rule a front office or player seems to follow (e.g. "opt out when the expected market
salary exceeds the option by more than X% for players under 31"), and its accuracy on the four summers (fit on three,
test on the fourth).

Output:
- data/research/offseason_decisions_2023_2026.json (rows plus sources)
- scripts/research/offseason_decisions_fit.py (reproduces the fits)
- docs/agents/tasks/offseason-decisions-evidence.md
Report: a plain-language TL;DR first (5 lines, no jargon; define each contract term simply), then one section per
decision with counts, the rule and its accuracy, named examples, and gaps in the evidence. Paraphrase sources; don't
copy long passages. Set the board row to "review" and stop.
Do NOT touch any file under src/, gui/ or tests/.
```

---

## Ready now (2026-11-20, late night): DEFENSE-RATINGS (fresh chat); ODDS-COACH after TRADE-MARKET's long runs

Running now: TRADE-MARKET (Claude agent: trade files, trade window, assistant phone) and FA-REAL slice 1 (Claude agent: cap rules, contract AI, free-agency paths). DEFENSE-RATINGS touches neither.

### DEFENSE-RATINGS: do team-defense ratings match analysts and the data? (starting with Kuminga)

Suggested settings: GPT-6.2 Sol, High, fresh chat.

```
Read AGENTS.md and docs/agents/BOARD.md first. You own task DEFENSE-RATINGS (its board row already exists; set it to "in progress (Codex)").
Read docs/agents/tasks/analyst-first.md, docs/agents/tasks/ratings-consensus.md and
docs/agents/tasks/overnight-ratings-oddities.md: they show how ratings are built (scripts/build_player_inputs.py,
analyst_evidence.py, bbi_evidence.py, data/research/bbi/bbi_input_mapping.json, data/research/analyst_claims_2026.json)
and the user's evidence order. Analysts (the Nerd Sesh hosts, Basketball Index writers, Taylor Metrics-style analysts)
come first. Impact numbers come second, read in their context. Never change a rating to hit a game outcome (AGENTS.md
rules 1, 3, 7). Every correction needs independent evidence with its own attribution and goes through the build
pipeline, never typed by hand.

Setup: your own git worktree:
  git worktree add ../BBall_codex_defense_ratings -b codex/defense-ratings HEAD
Symlink the git-ignored data from the main checkout: .venv, data/research/barttorvik/raw,
data/canonical/universe_2026_27_offseason.sqlite, data/canonical/injury_player_evidence_v2.json, every git-ignored file
under data/research/bbi/ (including tools/), output/settlement-materialization-pass. Then run
gunzip -kf data/canonical/player_inputs_2026_27.json.gz. Commit on branch codex/defense-ratings; never push, never
commit to main. Raw Basketball Index data stays local; never commit it.

Trigger: the user says Jonathan Kuminga is a poor team defender. In their view he's physically gifted but not a smart
or capable defender, which is part of why he never fit next to Curry's system. The game's defensive ratings put him
about average (around 63). Check whether that's a rating problem:
1. Kuminga first: list every defensive input (the containment, navigation, interior, anticipation, steal,
   interception, foul control and communication skills; the effort and help tendencies) with its value and where it
   came from (which BBI measure, which analyst claim, which weight). Then gather independent evidence: analyst claims
   (search the Nerd Sesh transcripts/claims we have; Basketball Index writeups), BBI defensive measures and their
   year-to-year repeatability, on/off and other impact numbers in context (role, teammates, minutes).
2. Then the same check league-wide for team defense: the 40 rotation players whose defensive ratings disagree most
   with the analyst consensus or with the repeatable data. Classify each as a measurement problem (fix the mapping or
   weights for everyone), sample/role context (no change), or genuine analyst disagreement (add an attributed claim to
   analyst_claims_2026.json with episode/article, date and timestamp where possible, then let the normal analyst step
   apply it).
3. Apply only well-evidenced fixes. Rebuild through scripts/build_player_inputs.py. Show who moved (before -> after,
   rotation percentile).

Checks: tests for any mapping or claim change (follow tests/test_overnight_ratings.py), bash scripts/run_core_tests.sh,
tests.test_bbi_evidence, tests.test_overnight_ratings. Both scorecards, since ratings change game results:
- PYTHONPATH=src .venv/bin/python scripts/calibration_report.py --games 1230 --mode replay-real-minutes (18/18)
- PYTHONPATH=src .venv/bin/python -m nba_gm_data.cli validate-season-probabilities --runs 20 --seed 1, before and after;
  report Brier, log loss, spread error and totals error. The user prefers short runs.
Other agents run long simulations on this laptop: run one heavy job at a time, and wait on your own process ID, never on
a grep loop.

Files you may touch: data/research/bbi/bbi_input_mapping.json, data/research/analyst_claims_2026.json,
src/nba_gm_data/analyst_evidence.py, src/nba_gm_data/bbi_evidence.py, scripts/build_player_inputs.py,
data/canonical/player_inputs_2026_27.json.gz (rebuilt by the script only), tests, docs/agents/tasks/defense-ratings.md.
Do NOT touch transactions.py, trade_*.py, contract_ai.py, cap_rules.py, play.py, save.py, sim.py or gui/.

Report in docs/agents/tasks/defense-ratings.md: a plain-language TL;DR first (3 lines, no jargon or skill codes), then
Kuminga's breakdown and verdict, the league table with each player's kind, what changed and the evidence, who moved,
both scorecards, and "What's left". Set the board row to "review" and stop.
```

---

## Ready now (2026-11-20, night): INJURY-FOLLOWUPS (fresh chat)

FA-PRICES and FA-REALISM-RESEARCH are done. ODDS-COACH still waits for the trade agent's long runs. TRADE-DEADLINE (Claude agent) owns the trade files. Claude will design the free-agency rebuild from the research next.

### INJURY-FOLLOWUPS: the leftovers from INJURIES-2

Suggested settings: GPT-6.2 Sol, High, fresh chat.

```
Read AGENTS.md and docs/agents/BOARD.md first. You own task INJURY-FOLLOWUPS (its board row already exists; set it to "in progress (Codex)").
Then read docs/agents/tasks/injuries-2.md fully, especially "What's left". Also read docs/agents/tasks/injury-overhaul.md.

Setup: your own git worktree:
  git worktree add ../BBall_codex_injury_followups -b codex/injury-followups HEAD
Symlink the git-ignored data from the main checkout: .venv, data/research/barttorvik/raw,
data/canonical/universe_2026_27_offseason.sqlite, data/canonical/injury_player_evidence_v2.json, the git-ignored
files under data/research/bbi/ (including tools/; link each one), output/settlement-materialization-pass, and
output/injuries-2 (the measurement scripts and before/after runs). Then run
gunzip -kf data/canonical/player_inputs_2026_27.json.gz. Commit on branch codex/injury-followups; never push, never
commit to main.

Do these in order:
1. The "~Ng" games-left label (save.py, around line 8179, the Minutes + Availability label) estimates games left as
   calendar days / 2.4. Count the team's remaining scheduled games before the return date instead, the same way
   health.injury_return_date counts them, so the label matches the engine exactly (AGENTS.md rule 4). Add a test.
2. Fantasy-draft careers apply the real opening-night injury list before the draft, so an injured player keeps his
   real return DATE on whatever team drafts him. Make his absence follow the games count instead (games missed on his
   new team's schedule, using the record's games-missed fields). Add a test.
3. The main job: injuries-2.md "What's left" item 1. The injury-rate fit (scripts/build_injury_model.py ->
   data/canonical/injury_model_v2.json) pools seasons whose Basketball Index tracker coverage differs four- to eightfold,
   so a single league scale (now 1.52) leaves the minutes and age slopes biased: the 20-30 minute group runs 10-15% above
   the tracker and players under 10 minutes below it. Refit with a separate base rate per season (season fixed
   effects), so the workload and age slopes come from within-season comparisons. Then set the league level from the
   well-covered seasons, as INJURIES-2 did.
   Measure before and after with output/injuries-2's scripts and scripts/research/injury_season_check.py (fixed rosters,
   2 seeds):
   - rate by minutes band and age band against the tracker;
   - the length bands;
   - injuries per team;
   - heavy-minute and top-30 players' games played (real: heavy 68, top-30 median 64.5).
   Rule 1 applies: fit to the evidence, never to a games-played target. Report what moved and why.
   Rebuild injury_model_v2.json only through its script.
4. Only if time allows: injuries-2.md item 2, heavy-minute players' single-game absences (2.7-2.8 a season against 2.4
   real). It comes from the rest model's split by minutes (rest_model.py). Measure from the same real box-score data the
   smart-rest work used (docs/agents/tasks/ and output/smart-rest/ if present). Change it only if the evidence supports
   it. If not done, write what you found.

Files you may touch: save.py (only the injury label function and the fantasy-draft injury hook), health.py,
injury_model.py, scripts/build_injury_model.py, data/canonical/injury_model_v2.json (via the script), rest_model.py
(item 4 only), new research scripts, tests, docs/agents/tasks/injury-followups.md.
Do NOT touch transactions.py, trade_*.py, multi_team_trades.py, play.py, contract_ai.py, cap_rules.py, gui/app.js
(other work owns them now).

Checks: focused tests; bash scripts/run_core_tests.sh; tests.test_injuries_2, tests.test_injury_model,
tests.test_overnight_tv_rest, tests.test_smart_rest, tests.test_fatigue_rest, tests.test_new_career_start; and the
real-stat scorecard once at the end (PYTHONPATH=src .venv/bin/python scripts/calibration_report.py --games 1230 --mode
replay-real-minutes, 18/18). Another agent runs long simulations on this laptop: run one heavy job at a time, and wait
on your own process ID, never on a grep loop.
Report in docs/agents/tasks/injury-followups.md: a plain-language TL;DR first (3 lines, no jargon), then before/after
tables, what changed and the evidence, speed (the health sim is about 0.4 s per simulated month), tests, and "What's
left". Set the board row to "review" and stop.
```

---

## Ready now (2026-11-20, evening): FA-REALISM-RESEARCH (fresh chat)

FA-PRICES is done (under review). ODDS-COACH still waits for the trade agent's long runs. This task is research plus reading code only, so it is light on the laptop.

### FA-REALISM-RESEARCH: the real NBA offseason, rule by rule, against what the game does

Suggested settings: GPT-6.2 Sol, High, fresh chat.

```
Read AGENTS.md and docs/agents/BOARD.md first. You own task FA-REALISM-RESEARCH (its board row already exists; set it to "in progress (Codex)").
This is a research and code-reading task. Change NO code. Your only output is one document,
docs/agents/tasks/fa-realism-research.md, plus your board row. Work in your own git worktree so you don't disturb
the shared checkout:
  git worktree add ../BBall_codex_fa_research -b codex/fa-realism-research HEAD
(Symlink .venv from the main checkout if you want to run read-only Python. No data symlinks are needed.) Commit the
document on that branch; never push, never commit to main.

Goal: the user wants free agency to be completely realistic but easy to understand, played through clear sequential
phases. That means Bird rights and restricted free agency (qualifying offers, offer sheets, matching) made explicit,
"and anything else I may not be aware of". Claude will design the feature from your document, so it must be complete,
precise and sourced.

Part 1: the real rules and calendar (2023 CBA, as it applies in the 2026 offseason). Every rule with a primary source
(CBA article and section; the NBA's official cap/calendar pages) or a well-known secondary source (Larry Coon's CBA FAQ,
Spotrac, Hoops Rumors' glossary). Cover at least:
- The offseason calendar in order, with 2026 dates: end of season, draft, the qualifying-offer deadline, option
  decisions (player, team, early termination), the negotiation window (moratorium) and when signings become official,
  the restricted free agency timeline (offer sheets, the matching window and its length under the 2023 CBA), summer
  league, waiver periods, two-way and Exhibit 10 deadlines, training camp, the opening-night roster cutdown, and the
  October rookie-scale extension deadline.
- Restricted free agency: who qualifies, qualifying-offer amounts, offer-sheet rules (minimum terms, what can and can't
  be in one, the Arenas provision for first- and second-round picks, the "poison pill" effect, cap room or exceptions
  needed to sign one), matching rules, what happens if not matched, signing the qualifying offer, rescinding.
- Bird, Early Bird and Non-Bird rights: who has which, maximum raises and lengths, and cap holds (amounts by type,
  renouncing them, how they block cap room).
- Exceptions: the non-taxpayer, taxpayer and room mid-level exceptions; bi-annual; the minimum exception; the
  rookie exception; traded player exceptions (only as far as free agency uses them). Amounts for 2026-27 and who can use
  which (aprons).
- Aprons and hard caps: which moves hard-cap a team at the first or second apron, and second-apron restrictions that
  touch free agency (sign-and-trades, aggregation, mid-level use).
- Sign-and-trades, contract options (player, team, early termination), guarantees and partial guarantees, the stretch
  provision, waivers and claims, two-way contracts, Exhibit 10 deals, max contracts (25/30/35% plus designated rookie
  and supermax criteria), and the minimum salary scale.
- How often things really happen (2023-2026 offseasons): offer sheets signed and matched per summer, restricted free
  agents who signed their qualifying offer, sign-and-trades, mid-level usage, players who went unsigned or overseas, and
  the share of free agents re-signing with their own team. Name real examples.

Part 2: what the game does today (read the code; give file:line references). Trace a full offseason in a save:
- the phases and dates (save.py phase_for_date, legal_actions_for_phase);
- the re-signing window (play.py own_expiring_re_signing_room);
- the AI's exclusive re-signings;
- Bird rights (contract_ai.bird_rights and related, from the KEEP-STARS task: docs/agents/tasks/keep-stars.md);
- the free-agency room and AI bids (play.py process_ai_free_agency_offers_for_day_state, manual_save_pool_signing);
- how restricted free agents are handled now ("teams simply keep good young players");
- cap rules (cap_rules.py: cap, tax, aprons, max salary, minimum scale);
- exceptions, roster repair, waivers and two-ways, and the GUI's free-agency room (gui/app.js, gui/free-agency.css).
Note anything that's wrong or contradicts the real rules.

Part 3: the gap table. For every real rule or step: real behavior | the game today | gap (none / partial / missing /
wrong) | how much it matters for realism and for what the user would feel | rough size to build (S/M/L). Then a
suggested sequence of in-game phases for a complete, easy-to-understand offseason (each phase: dates, what the user can
do, what AI teams do, what the user sees), keeping it playable, with no tedious steps that nobody would miss.

Writing: plain everyday language for the user (AGENTS.md section 3). Start with a 5-line TL;DR. Define every cap term
the first time it appears. Paraphrase sources; don't copy long passages.
When done, set the board row to "review" and stop.
```

---

## Ready now (2026-11-20, afternoon): FA-PRICES first, ODDS-COACH later (one fresh chat each)

Two Claude agents are running at the same time in their own worktrees: TRADE-DEADLINE (trade files) and INJURIES-2 (health and injury files). Codex works in **its own git worktree** for these tasks so merges don't collide with the shared checkout. Run FA-PRICES now. Start ODDS-COACH only after TRADE-DEADLINE's long test seasons finish, or overnight, because its betting runs are heavy.

### FA-PRICES: a real price model for free agents below the starter tier

Suggested settings: GPT-6.2 Sol, Medium, fresh chat.

```
Read AGENTS.md and docs/agents/BOARD.md first. You own task FA-PRICES (its board row already exists; set it to "in progress (Codex)").

Setup: work in your own git worktree so you don't disturb the shared checkout:
  git worktree add ../BBall_codex_fa_prices -b codex/fa-prices HEAD
Then symlink the git-ignored data from the main checkout into it: .venv, data/research/barttorvik/raw,
data/canonical/universe_2026_27_offseason.sqlite, data/canonical/injury_player_evidence_v2.json, the git-ignored files
under data/research/bbi/ (link each one), output/settlement-materialization-pass. Then run
gunzip -kf data/canonical/player_inputs_2026_27.json.gz. Commit on branch codex/fa-prices in that worktree; never push,
never commit to main.

Problem: after the opening summers (which use precomputed market research), every free agent below the starter tier
asks minutes x $0.48M (src/nba_gm_data/play.py free_agency_initial_ask and with_star_market_ask). Starters and stars
already ask a contract-market price (contract_ai.star_market_ask_millions, a floor on the old ask). Minutes are a role
outcome, not value: a young player stuck behind starters is underpriced and a veteran on a bad team overpriced. Earlier
finding (docs/agents/tasks/trade-volume-2.md, "What's left"): the existing contract-market formula is too flat to use for
everyone. It underprices stars by about a third and overprices the middle (many $6M young bench players came out at
$16.6M on the 2027 class).

Step 1 (evidence): fit salary as a share of the cap against the game's own player value, age, role tier, years of
service and contract length, on the 84 real 2025-2026 contracts in data/research/free_agent_contracts_2025_2026.json
(some marked uncertain; the 2025 half is weaker, so weight it down and say how). Add league-wide cap room as a market
factor if the data supports it. Hold out a subset and report the error against the minutes rule and the existing
formula. Show 15 named examples (real vs new vs old).
Step 2 (in the game): use the fitted price for free agents below the starter tier, in a new function in contract_ai.py,
called from play.py's ask path. Leave star_market_ask_millions and the precomputed opening-summer research unchanged.
Respect the real minimum salary scale and the max-salary rule (cap_rules.py). The user's offers are judged by the same
rule as the AI bids', so the price you add must flow through the existing offer-acceptance path, not a second copy (rule 4:
what the user sees must be what the engine uses).

Files you may touch: contract_ai.py (new function plus small helpers), play.py (only the ask functions above and their
direct callers), a new data/canonical/ or data/research/ fit file, a new scripts/research/ fit script, tests,
docs/agents/tasks/fa-prices.md. Do NOT touch transactions.py, trade_*.py, multi_team_trades.py, app_actions.py trade
actions, health.py, injury_model.py, sim.py, or save.py season-start code (other agents own them right now). If you think
you need one of those, stop and write it in your report instead.

Acceptance:
- Held-out error better than both the minutes rule and the existing formula.
- One simulated offseason from a fresh save (scripts/two_season_league_probe.py can stop after the first free agency, or
  write a short driver): the distribution of signed salaries by tier against real 2025-26 signings, how many free agents go
  unsigned, and teams' cap room after free agency. No team blows past the hard cap; stars unchanged.
- Focused tests (the price function, minimum and maximum bounds, the user offer uses the same price).
  bash scripts/run_core_tests.sh passes.
- Report in docs/agents/tasks/fa-prices.md: a plain-language TL;DR first (3 lines, no jargon), then the fit, the named
  examples, the offseason table and "What's left" (restricted free-agent offer sheets are out of scope; note them).
  Set the board row to "review" and stop.
```

### ODDS-COACH: give the betting test the same coach model the saves use

Suggested settings: GPT-6.2 Sol, Medium, fresh chat. Start after TRADE-DEADLINE's probes finish, or overnight.

```
Read AGENTS.md and docs/agents/BOARD.md first. You own task ODDS-COACH (its board row already exists; set it to "in progress (Codex)").

Setup: your own git worktree, as in FA-PRICES, but on branch codex/odds-coach (../BBall_codex_odds_coach), with the same
data symlinks and the gunzip step. Commit on that branch only; never push, never commit to main.

Problem: the betting-odds test (python -m nba_gm_data.cli validate-season-probabilities) replays the real 2025-26 season.
docs/agents/tasks/overnight-game-context-margins.md ("What's left", item 1b) found that coach effects measure only about
half-strength in it, because the test uses the older coach formula (sim.py coach_ratings, around line 490) while saves use
the newer staff model (sim.py "Save staff (coaching overhaul 2026-11-18)", around line 3579, every head-coach and
coordinator rating with its own effect). The test should use the same model the game uses, with the real 2025-26
staffs (head coaches and, where public, coordinators), so the betting scorecard judges the real engine (AGENTS.md rule 9).

Step 1: confirm the gap with file:line references. List which coach effects the save path applies that the test path
doesn't, and which staff the test currently uses (the 2026-27 staffs or the 2025-26 ones).
Step 2: build data/research/staffs_2025_26.json (public sources, each recorded) and make the replay path use the save
staff model with those staffs. A save's game results must not change: prove it with a seeded save game compared field by
field before and after.
Step 3: measure. validate-season-probabilities --runs 20 with seeds 1001 and 2001, before and after (Brier, log loss,
spread error, totals error), plus the real-stat scorecard
(PYTHONPATH=src .venv/bin/python scripts/calibration_report.py --games 1230 --mode replay-real-minutes, 18/18 expected).
Run one heavy job at a time (other agents share this laptop). Wait on your own process ID, never on a grep loop.
Do not refit coach effect sizes to the betting test. If the evidence suggests a size is wrong, report it with the
numbers instead.

Files you may touch: sim.py (only the replay/validation coach plumbing and the save-staff functions it reuses), a new
data/research/staffs_2025_26.json, tests, docs/agents/tasks/odds-coach.md. Do NOT touch health.py, injury_model.py,
transactions.py, trade_*.py, contract_ai.py, play.py.

Acceptance: the before/after table on both seeds, the save-game identity check, focused tests, bash
scripts/run_core_tests.sh passes, and a report in docs/agents/tasks/odds-coach.md with a plain-language TL;DR first. Set
the board row to "review" and stop.
```

---

## Ready now (2026-11-19, evening): ROT-OUTLIERS, then BLOWOUT-MINUTES, one fresh chat each

ROT-SHAPE and JS-TESTS are done and merged. These two build on ROT-SHAPE (`docs/agents/tasks/rot-shape.md`).

### ROT-OUTLIERS: deep-bench players still get starter-like minutes

Suggested settings: GPT-6.2 Sol, Medium, fresh chat.

```
Read AGENTS.md and docs/agents/BOARD.md first. You own task ROT-OUTLIERS. Add a board row and mark it "in progress (Codex)".

Context: ROT-SHAPE (docs/agents/tasks/rot-shape.md, merged 2026-11-19) fixed the league-wide rotation shape: role-group
minutes now land within about 1 mpg of Basketball Index healthy-rotation minutes. Individual outliers remain because
their starting minutes_projection is far too high: Bruce Brown NYK (game target 25.1, plays ~19.9, Basketball Index 4.5)
and Luke Kennard PHX (21.1, plays 17.4, BBI 5.0); Jordan Poole NOP (24.5 -> 10.2 after ROT-SHAPE, BBI 8.2) shows the
coach can correct when the inputs allow it.

Step 1 (measure, read-only): over 2 seeds of one headless regular season (AI coaches, canonical 2026-27 rosters), list
the 25 players whose played minutes exceed Basketball Index healthy_rotation_mpg the most, and the 25 who fall shortest
(data/research/bbi/tools/minutes_players.json, local only, never commit). For each, find why: the starting
minutes_projection, the depth/role builder (save.py around the role builder ROT-SHAPE changed), position slotting (a
backup slot forced onto a weak player), or the coach's game model. Give file:line references.
Step 2 (fix): make the depth chart follow each team's real talent order and positional needs, so a clearly weaker
player is not handed rotation minutes because he fills a position slot. Do not copy Basketball Index minutes into the
game and do not change any player ratings; the coach model must produce the minutes. Keep the user's rough minutes
targets driving their own team (AGENTS.md rule 8) and keep ROT-SHAPE's role-group results.

Files you may touch: save.py rotation/depth/role code, the coach minutes helpers in sim.py (another agent may edit
sim.py for player value; keep your edits contained to minutes/rotation functions), tests, docs/agents/tasks/rot-outliers.md.
Do not touch transactions.py, trade_*.py, draft.py, real_prospects.py, impact_value.py.
Acceptance: the outlier lists before/after (Brown and Kennard within about 5 mpg of their reference unless you show the
coach has a sound reason), ROT-SHAPE's role-group table still within 1.5 mpg, focused tests, both scorecards
(calibration_report.py replay-real-minutes in inputs mode 18/18; validate-season-probabilities --runs 100 with
NBA_GM_RATINGS_MODEL=inputs_v1: Brier and log loss not worse than 0.1945 / 0.5750) and bash scripts/run_core_tests.sh.
Leave changes uncommitted; write the report and set the board row to review.
```

### BLOWOUT-MINUTES: the coach should rest players in blowouts and react to foul trouble

**Absorbed by HEAVY-MINUTES (Claude, 2026-11-19); do not dispatch.** See `docs/agents/tasks/heavy-minutes.md`.

Suggested settings: GPT-6.2 Sol, Medium, fresh chat. Start only after ROT-OUTLIERS is reviewed.

```
Read AGENTS.md and docs/agents/BOARD.md first. You own task BLOWOUT-MINUTES. Add a board row and mark it "in progress (Codex)".

Goal (AGENTS.md rule 8): the modeled coach decides actual playing time game by game and in-game: foul trouble, fatigue,
hot or cold hands, blowouts, matchups. ROT-SHAPE found that the current game path has no blowout substitution step and
that personal fouls are assigned after minutes and scoring are decided (docs/agents/tasks/rot-shape.md, "Where the
flatness came from": sim.py:550, sim.py:616, sim.py:1006).

Step 1 (measure): from real 2025-26 data the repo already has (box scores under data/research, see
docs/obsidian-vault or grep for boxscore loaders), measure how starters' minutes fall with the final margin (e.g. by
margin buckets 0-5, 6-10, 11-20, 21+) and how foul counts relate to minutes. Report the real curves.
Step 2 (fix): add a blowout-rest effect and a foul-trouble effect to the coach's in-game minutes, fitted to those real
curves, keeping each team's total at 240 (overtime aside) and keeping game-to-game variation realistic. Bench players
gain the minutes starters lose. Keep it deterministic under the seed and cheap (speed budget AGENTS.md rule 10).

Files you may touch: the coach/minutes code in sim.py (keep edits contained; another agent may edit sim.py for player
value), tests, docs/agents/tasks/blowout-minutes.md. Do not change player ratings.
Acceptance: before/after starter-minutes-by-margin table vs real, both scorecards (as in ROT-OUTLIERS: 18/18;
Brier/log loss not worse than 0.1945 / 0.5750), bash scripts/run_core_tests.sh. Leave changes uncommitted; report; board row to review.
```

---

## Done (2026-11-19): ROT-SHAPE and JS-TESTS (merged; kept for reference)

### ROT-SHAPE: AI coach rotation shape vs Basketball Index minutes projections

Suggested settings: GPT-6.2 Sol, Medium, fresh chat.

```
Read AGENTS.md and docs/agents/BOARD.md first. You own task ROT-SHAPE. Add a board row and mark it "in progress (Codex)".

Goal: the AI coach's rotations are too flat. Compared with Basketball Index's 2026-27 healthy-rotation minutes
(data/research/bbi/tools/minutes_players.json, local only: never commit it), the game's starting minutes targets
(players' minutes_projection) give stars about 2 fewer minutes per game and back-of-rotation players about 7 more.
Several deep-bench players get about 20 minutes against about 5 (Bruce Brown NYK, Mitchell Robinson BOS, Luke
Kennard PHX, Jordan Poole NOP). Overall correlation is 0.81 over 329 matched players.

Step 1 (measure, read-only): sim one regular season headlessly (canonical 2026-27 rosters, AI coaches for all 30 teams,
2-3 seeds) and compare actual minutes per game played with healthy_rotation_mpg by Basketball Index rotation_role
(Star / Key / Starter / Rot). Find where the flatness comes from: the starting minutes_projection, the coach's
game-by-game minutes model, fatigue or foul handling, or blowout rest. Give file:line references.
Step 2 (fix): tune the rotation shape where the cause lives so the role-group means land within about 1.5 minutes per
game of Basketball Index. Keep the team total at 240 and keep realistic game-to-game variation (project rule 8: the
user's rough targets still drive their own team). Do not change any player ratings. Do not copy Basketball Index
minutes into the game as data; the shape must come from the coach model.

Files you may touch: the minutes and rotation code you identify (likely sim.py and coach/rotation helpers), tests, and
docs/agents/tasks/rot-shape.md. Do not touch health.py, staff.py, injury_model.py, court_influence.py or spatial.py:
the coordinator has uncommitted, under-test changes in health.py, staff.py and three development tests
(test_foundation, test_prospect_development, test_prospect_learning). Leave those files alone.
Acceptance: focused tests, both scorecards (calibration_report.py replay-real-minutes in inputs mode: 18/18 in range;
validate-season-probabilities --runs 100: Brier and log loss not worse than 0.1960 / 0.5790), and the core tests
(bash scripts/run_core_tests.sh). Report the before/after role-group table.

When done: plain-language summary (TL;DR first) in docs/agents/tasks/rot-shape.md. Set the board row to "review". Do
not commit.
```

### JS-TESTS: repair the eight stale browser-interface tests

Suggested settings: GPT-6.2 Sol, Medium, fresh chat.

```
Read AGENTS.md and docs/agents/BOARD.md first. You own task JS-TESTS. Mark its board row "in progress (Codex)".

Goal: eight Node tests under tests/*.test.cjs fail on the committed code. They are not part of the Python suite, so
nobody noticed. They fail for stale reasons, not because the game is broken:
  first_hour_ui (playerRustMarkup / captureTeamSignalBars not defined), gui_simulation_motion (expects
  season-opponent-result-header), player_pages (document is not defined; also expects the text "Health risk", which
  the player card now shows as "Injury risk" plus a body map), postseason_ui (expects an old
  card-board.css?v=... version string in index.html), seasonal_clipboard (origin markers not found; async
  "action is not defined"), starter_workspace (two boolean expectations), startup_video (cloneNode not a function in
  the test's fake DOM), ui_product_audit (extensionCapRows not defined).
Run each with: node tests/<name>.test.cjs

For each test: find why it fails (renamed helper, moved markup, stale version string, incomplete fake DOM, or a real
bug). Update the test so it checks the same user-facing behavior against today's code. Don't delete checks to make
them pass. Don't pin cache-busting version strings; match the pattern instead. If a failure is a real bug in
src/nba_gm_data/gui/app.js, do not fix it: describe it in your report.

Files you may touch: tests/*.test.cjs only (and test helper files they load). No changes to src/.
Acceptance: all tests/*.test.cjs pass (for f in tests/*.test.cjs; do node "$f" || echo FAIL $f; done), and the
Python GUI guards still pass (PYTHONPATH=src .venv/bin/python -m unittest tests.test_gui_concept71).
Report: docs/agents/tasks/js-tests.md, plain language first: one line per test (cause, fix, any real bug found). Set
the board row to "review". Do not commit.
```

---

## Done: (2026-11-18, late night): DEV-TUNE (reviewed 2026-11-19)

### DEV-TUNE: player aging and development curves to match Basketball Index

Suggested settings: GPT-6.2 Sol, Medium (High if it stalls), fresh chat or the DEV chat.

```
Read AGENTS.md, docs/agents/BOARD.md and your own report docs/agents/tasks/dev-growth-vs-bbi.md first. You own DEV-TUNE;
add a board row "in progress (Codex)".

GOAL: retune development so the game's age curve and year-to-year spread match Basketball Index (your report):
growth strongest at 19-22, broad peak ~23-26, decline starting by 27-30 (offense earlier than defense), steeper late
decline; and realistic spread around each player's expected change (BBI overall 80% band ~ -1.1..+0.8 of its scale,
measured relative to starting spread as in your report).

SCOPE: src/nba_gm_data/health.py monthly_trait_delta and its aging/growth/noise constants (and the development config
values they read), plus development_outlook.py if its expected-change helper needs the same constants. Do NOT edit
health.development_staff_modifiers or health.coach_development_by_team (Claude is rewiring coach/staff effects), the
injury functions in health.py (injury model v2 just landed), sim.py, staff.py or staff_lifecycle.py.
RULES: ratings-first (do not change any player's starting ratings); keep both rating sets working (legacy and
inputs_v1); determinism (seeded); no clipping at 100. Spread should come mostly from season-level shocks (role, health,
breakouts), not month-to-month noise that averages out.
CHECKS: re-run your DEV comparison (age-by-band medians and spread bands, both rating sets) and show before/after
tables; tests/test_development_outlook.py, tests/test_prospect_development.py, tests/test_development_coverage.py,
bash scripts/run_core_tests.sh; and the real-stat scorecard is unaffected at season start (development only changes
ratings over time) — say so if you confirm it.
REPORT: append "DEV-TUNE results" to docs/agents/tasks/dev-growth-vs-bbi.md, plain language first. Board row to
"review". Do not commit. Don't poll long runs more than every 20-30 minutes.
```

---

## Done: (2026-11-18, night): STAFF-LIFE and BBX-2, one fresh chat each

Suggested settings: GPT-6.2 Sol, Medium. Claude is rebuilding the injury engine: do NOT edit src/nba_gm_data/health.py,
sim.py, schema.py, or the health/injury functions in save.py, app_actions.py and gui/app.js. Don't poll long runs more
than every 20-30 minutes.

### STAFF-LIFE: staff age, change over time, retire, and a refilled coach pool

```
Read AGENTS.md, docs/agents/BOARD.md and docs/agents/tasks/coaching-overhaul.md (audit + user decisions) first. You own
STAFF-LIFE; add a board row "in progress (Codex)". This is the lifecycle part of the coaching overhaul; Claude will later
rewire the rating EFFECTS, so do not change how ratings affect games, development, injuries or scouting.

BUILD (new module src/nba_gm_data/staff_lifecycle.py; edits to staff.py; one call from the season rollover):
1. Every staff member gets an age and years of experience. Real staff: use experience/records from the existing sources
   (data/research/coaches_espn_2026.json, staff_*_team_pages_2026.json) where present; otherwise seeded plausible values
   by role (deterministic from save seed + person id). Generated staff likewise.
2. Yearly change at season rollover: each skill and personality rating drifts by age and experience (younger staff tend
   to improve, older staff decline; experience grows game-management-type skills), with seeded noise. Keep the 20-96
   scale; no clipping at 100 issues (rule 3). Write the change log per person (season, rating deltas) so the GUI can
   show it later.
3. Retirement: probability rising with age (and after being fired late in a career). Retired staff leave the market.
4. Pool refill each offseason: new generated candidates enter (young assistants, promoted coordinators becoming head
   coach candidates), so the free-agent pool never runs dry and its quality distribution stays realistic (include some
   strong candidates; today's best generated head coach is grade 76 vs top real coaches ~93).
5. Reputation: a stored reputation that moves with results vs expectations (team wins vs pre-season expectation, playoff
   success); job security follows reputation and results instead of staying static.
6. Determinism: all randomness seeded from the save seed + season + person id; same save + seed = same result.

HOOK: call your rollover function from save.age_staff_contracts (the season rollover step that already ages contracts).
Keep that edit to a single call; do not touch other save.py functions.
TESTS: new tests/test_staff_lifecycle.py (aging direction by age, retirement, pool refill keeps a healthy distribution,
determinism, reputation moves with results). Run bash scripts/run_core_tests.sh and the staff tests in tests/test_foundation.py.
REPORT: docs/agents/tasks/staff-life.md, plain language first. Board row to "review". Do not commit.
```

### BBX-2: tidy tables from the new raw Basketball Index captures

```
Read AGENTS.md, docs/agents/BOARD.md, docs/agents/tasks/bbx-tool-extract.md and docs/agents/tasks/bbi-full-capture.md.
You own BBX-2; add a board row. Data only: do not edit src/ or tests/.

Extend scripts/bbi_extract_tools.py (or add scripts/bbi_extract_captures.py) to turn these raw captures (git-ignored,
under data/research/bbi/captures/) into documented, reproducible tables in data/research/bbi/tools/ (each <= ~5 MB,
gzip larger CSVs), matching players to our ids (report match rates; never guess):
- fanspo_tools/progression/bbi_progression_all.json.gz: per player-season x 164 measures (impact metrics EPM/RAPM/DRIP/
  DPM/RAPTOR/BPM, talent grades, usage...) plus roles, age, minutes; keep the league distributions as a separate file.
- fanspo_tools/playoff_talent/bbi_playoff_talent_3yr.json.gz: 3-year playoff windows x 386 measures.
- fanspo_tools/lineup_explorer/bbi_lineup_explorer_2013_2026.json.gz: 61,037 lineups (players, minutes, ratings, role
  mix, 24 talent grades).
- fanspo_tools/xpoints/bbi_xpoints_lineups_2025_26.json.gz: per-team lineups with exact possessions and expected points.
- tools/role_labs/bbi_role_labs.json.gz: per-player role entries and the model coefficients (document what fields mean
  from the data and the saved Role Lab pages in captures/tools/).
REPORT: append a "BBX-2" section to docs/agents/tasks/bbx-tool-extract.md, plain language first. Board row to "review".
Do not commit.
```

---

## Done: (2026-11-18, evening): two read-only engine-vs-evidence comparisons, one fresh chat each

Suggested settings: GPT-6.2 Sol, Medium. Both READ-ONLY for src/ and data/canonical (Claude is working there). Scripts in
scripts/research/, outputs in output/<task>/. Don't poll long runs more than every 20-30 minutes.

### DEV: Our development and aging vs Basketball Index's growth curve

```
Read AGENTS.md, docs/agents/BOARD.md and docs/agents/tasks/bbx-tool-extract.md first. You own DEV; add a board row.

Evidence: data/research/bbi/tools/growth_*.json / .csv.gz (Basketball Index's talent age-growth model: actual vs
1-year-ahead projection by age and role, forward projections, development vs expectation, per-coach development).
Our engine: player development runs monthly in src/nba_gm_data/health.py (monthly_trait_delta; aging, staff/coach effects,
ceilings); development_outlook.expected_rating_changes gives the expected 12-month change with no noise.

QUESTIONS (plain-language answers with tables):
1. Age curve: for each age 19..36, what is Basketball Index's typical one-year change in offensive, defensive and overall
   talent (median and spread, by minutes band)? What does our engine's expected 12-month change give for the same ages,
   for players of similar level (use expected_rating_changes on the 2026-27 league; both rating sets if practical)?
   Where do the curves disagree (peak age, decline start, decline speed, young growth size)?
2. Spread: how much do real players vary around the typical change (their 50/80/90% bands) vs our engine's variation
   (simulate a season with seeds, or use the monthly noise the engine applies)?
3. Coaches: how big are Basketball Index's per-coach development effects (players' actual minus projected), and how
   big is our staff/coach development effect? Is ours in a realistic range?
4. Propose concrete parameter changes (which constants, by how much) with expected effect. Don't change src/.

REPORT: docs/agents/tasks/dev-growth-vs-bbi.md, plain language first. Board row to "review". Do not commit.
```

### INJ: Our injuries vs Basketball Index's injury tracker

```
Read AGENTS.md, docs/agents/BOARD.md and docs/agents/tasks/bbx-tool-extract.md first. You own INJ; add a board row.

Evidence: data/research/bbi/tools/injury_*.json (time out by diagnosis/body part with return-day percentiles,
recurrence, short- and long-term aftermath, player histories, durability, games missed per 82).
Our engine: injuries are generated in src/nba_gm_data/health.py (injury model config, durations, recurrence, rust).

QUESTIONS (plain-language answers with tables):
1. Simulate one or more full seasons headless (an existing soak or quick-sim script; seeded) and compare our league:
   injuries per team-season, games missed per 82 by role/age, the distribution of days out (25/50/75/90th percentiles)
   overall and for the most common body parts, share of season-ending injuries, recurrence within a season.
2. Short-term aftermath: Basketball Index shows minutes and shooting after return (injury_short_term.json). Compare with
   our rust penalty (sim.rust_penalty_points; ~0.08 per rust point, capped at 4) and how long it lasts.
3. Propose concrete parameter changes with expected effect. Don't change src/.

REPORT: docs/agents/tasks/inj-injuries-vs-bbi.md, plain language first. Board row to "review". Do not commit.
```

---

## Done: (2026-11-18, afternoon): BBX, extract the saved Basketball Index tool pages

### BBX: Turn the saved Growth Curve, Injury Tracker and Minutes/Talent pages into clean tables

Suggested settings: GPT-6.2 Sol, Medium, fresh chat.

```
Read AGENTS.md and docs/agents/BOARD.md first. You own task BBX; add a board row "in progress (Codex)".

Basketball Index tool pages were saved (signed-in, personal-use subscription) as self-contained HTML in
data/research/bbi/captures/tools/ (git-ignored): bbi_tool_growth_curve.html (~7 MB), bbi_tool_injuries.html (~5.5 MB),
bbi_tool_minutes_talent_2026_27.html, bbi_tool_offensive_role_lab.html, bbi_tool_defensive_role_lab.html.
Their data is embedded in the pages (JSON/JS arrays inside <script>). Do NOT fetch anything from the web.

GOAL: extract every embedded table into tidy, documented files under data/research/bbi/tools/ (tracked, compact JSON or
CSV; keep each under ~5 MB, gzip if larger), plus a parser script scripts/bbi_extract_tools.py (standard library only,
reproducible: rerunning gives identical files).
1. Growth Curve (priority): per player x season x talent metric: actual value, the model's 1-year-ahead projection, and
   the 50/80/90% intervals; forward projections; the "development vs expectations" per player; the per-coach table
   (players' actual minus projected under each head coach). Also save the methodology text verbatim (it is short).
2. Injury Tracker: per injury type/body part: typical days missed, the range, recurrence/aftermath and durability fields,
   and any per-player injury history tables it embeds.
3. Minutes/Talent 2026-27: per player projected games missed, MPG, role/talent grid fields; per-team tables.
4. Role Labs: whatever per-player tables they embed (role, estimated impact of role changes).
For each output, document fields, units, row counts and the player identifier used (name/team/ids) in
docs/agents/tasks/bbx-tool-extract.md, and match players to our ids where you can (report the match rate; never guess).

BOUNDARIES: new script, data/research/bbi/tools/, your report. Do not edit src/ or tests/ (Claude is working there).
REPORT: plain language first. Board row to "review". Do not commit. Don't poll long runs more than every 20-30 minutes.
```

---

## Done: (2026-11-18): PRO-2, implement the rookie input fix

### PRO-2: Start real 2026 rookies on the estimator's rookie setting

Suggested settings: GPT-6.2 Sol, Medium, fresh chat (or continue the PRO chat if it still has context).

```
Read AGENTS.md, docs/agents/BOARD.md and your own report docs/agents/tasks/pro-prospect-inputs.md first. You own PRO-2;
add a board row "in progress (Codex)". Claude approved section 3's first step ("rookie technique only").

DO:
1. In scripts/build_player_inputs.py, estimate the real 2026 entrants with no completed NBA season (the 53 players your
   audit identified; derive the set from data, don't hard-code names) with the estimator's existing prospect=True setting.
   Keep eligible evidence overlays and the measured-tendency step exactly as they are. Do NOT apply the involvement
   (usage) shift yet; that needs held-out validation first (separate task).
2. Rebuild data/canonical/player_inputs_2026_27.json (+ .gz) with the script. Confirm only those players' technique inputs
   changed (diff summary: players changed, inputs changed, everything else identical).
3. Run, with NBA_GM_RATINGS_MODEL=inputs_v1:
   - PYTHONPATH=src .venv/bin/python scripts/ratings_sniff_report.py  (report Peterson, Boozer, Flagg, Harper ranks)
   - PYTHONPATH=src .venv/bin/python scripts/calibration_report.py --games 1230 --mode replay-real-minutes
   - PYTHONPATH=src .venv/bin/python -m nba_gm_data.cli validate-season-probabilities --runs 100  (~20 min; run in the
     background and check back at most every 20-30 min)
   Compare with the current baseline: replay 18/18 in band, points per-36 mean abs 2.595; odds Brier 0.1950, log loss
   0.5775, spread error 5.223, total error 5.421. Don't regress either scorecard silently; report the numbers.
4. bash scripts/run_core_tests.sh

BOUNDARIES: scripts/build_player_inputs.py, data/canonical/player_inputs_2026_27.json(.gz), new tests, your report.
Claude is editing src/nba_gm_data/history_store.py and save.py (save size) — don't touch src/.
REPORT: append "PRO-2 results" to docs/agents/tasks/pro-prospect-inputs.md, plain language first. Board row to "review". Do not commit.
```

---

## Done: (2026-11-17 night): two read-only research tasks, one fresh chat each

Suggested settings: GPT-6.2 Sol, Medium. Both are READ-ONLY for src/ and data/ (Claude is editing transactions.py,
trait_adapter.py, impact_value fit, sim/box files, and tests). New scripts go in scripts/research/, outputs in output/<task>/.
Don't poll long runs more than every 20-30 minutes.

### PRO: Are draft prospects' estimated inputs inflated? (diagnosis + proposal)

```
Read AGENTS.md and docs/agents/BOARD.md first. You own task PRO; add a board row "in progress (Codex)".

SYMPTOM: under the new ratings (NBA_GM_RATINGS_MODEL=inputs_v1), incoming rookies and generated draftees rank too high.
2026 rookie Darryn Peterson (19) is 15th in the league by overall (scripts/ratings_sniff_report.py), and Cameron Boozer,
Dylan Harper, Aday Mara and Caleb Wilson show up near the top of several input-based ratings. Earlier notes also say
the prospect path's estimated involvement (usage) runs high.

Players without measured input records get inputs from the estimator's prospect path (src/nba_gm_data/input_estimator.py,
called from ratings_model._install_generated_players; tendency inputs are mapped with data/canonical/tendency_scale_map.json).

QUESTIONS:
1. How do prospects' estimated inputs compare with REAL first-season inputs of recent rookies who have measured data
   (e.g. 2023, 2024 and 2025 draftees: their inputs come from Basketball Index evidence)? Compare by draft slot band
   (top 5, 6-14, 15-30, second round) for the skill groups, physical inputs and involvement (T08). Use league percentiles.
2. Which part of the pipeline causes any gap (the estimator's anchors, the scale map, the trait adapter's percentile step,
   or the legacy traits it starts from)? Show the evidence.
3. Propose the smallest fix, with expected effect on where Peterson / Boozer / Flagg (2025 #1, measured) would rank.
   Do NOT implement it in src/ (Claude will); a prototype in scripts/research/ that prints before/after ranks is welcome.

REPORT: docs/agents/tasks/pro-prospect-inputs.md, plain language first, tables for the comparison. Board row to "review". Do not commit.
```

### SAV: Save size after many seasons (analysis + options)

```
Read AGENTS.md and docs/agents/BOARD.md first ("Save size (open, needs user decision)"). You own task SAV; add a board row.

PROBLEM: a career's history database grows ~60 MB per season. At ~8 seasons the save passes the 512 MB portable-export cap
(src/nba_gm_data/save_recovery.py, MAX_EXPANDED_BYTES); local autosaves allow 16 GB, so play continues, but players
can't export/share a long career, and every save step gets slower (validation and backups scale with size).

A real 8-season save exists: output/t2b/checkpoint/current/ (copy it to output/sav/ before reading; a builder is still
writing to output/t2b — never modify anything there).

QUESTIONS:
1. What is stored: break the history SQLite (src/nba_gm_data/history_store.py) and the save JSON down by record kind and
   by season (MB per kind per season). What dominates (box scores? play-by-play? events?)
2. What actually reads each kind: GUI screens, AI, stats pages, awards, records. Which old data is never read after a
   season ends, or only read in summarized form?
3. Options with measured sizes, e.g. compress payloads, store old seasons' box scores as season totals, drop
   play-by-play after N seasons, separate an optional "full archive" from the portable export. For each: projected size at
   10 and 20 seasons, what the player loses, implementation size.
Prototype measurements in scripts/research/ on the copied save are welcome; do not change src/.

REPORT: docs/agents/tasks/sav-save-size.md, plain language first, a short options table for the user. Board row to "review". Do not commit.
```

---

## Done: (2026-11-17 evening)

### PLY: Real playoff performance data (evidence for the "playoff translation" rating)

Suggested settings: GPT-6.2 Sol, Medium, fresh chat.

```
Read AGENTS.md and docs/agents/BOARD.md first. You own task PLY; add a board row "in progress (Codex)".

WHY: the new ratings' hidden "playoff translation" rating is built only from shooting, self-creation and perimeter-defense inputs. It ranks Derrick White 1st, Jokic 101st and Giannis 217th. It feeds the sim's impact number and the AI's superstar trade tier. Claude will refit it to real evidence (ratings-first rule). Your job is ONLY to collect that evidence; do not change ratings, inputs or engine code.

DATA: per-player, per-season regular-season AND playoff box totals for every player in data/research/player_career_stats.json, seasons 2013-14 through 2025-26.
- Reuse scripts/import_player_career_stats.py, which already fetches ESPN's public athlete stats endpoint with seasontype=2 (regular season). Postseason is seasontype=3 on the same endpoint. Write a new script scripts/import_player_playoff_stats.py (standard library only; reuse helpers by import, don't copy-paste large blocks), polite rate limiting (<= 2 requests/second), resumable cache under output/ply/.
- Fields per player-season and season type: games, minutes, points, rebounds (off/def if available), assists, steals, blocks, turnovers, fgm/fga, fg3m/fg3a, ftm/fta, personal fouls if available, team.
- Output: data/research/player_playoff_stats.json (same player keys and style as player_career_stats.json; include source URLs, retrieved_at and coverage counts). Keep it compact: no raw API payloads in data/.

CHECKS: spot-check 5 players against Basketball Reference playoff totals (e.g. Jokic 2023, Giannis 2021, Jamal Murray 2023, Jalen Brunson 2024, SGA 2025) and record the comparison in the report. Report coverage (players with any playoff minutes; player-seasons).

BOUNDARIES: new script, new data file, output/ply/, your report. No other files.
REPORT: docs/agents/tasks/ply-playoff-data.md, plain language first. Board row to "review". Do not commit. Don't poll long runs more than every 20-30 minutes.
```

---

## Done (2026-11-17 afternoon): two bug tasks from the test triage, (BUG-A and BUG-B reviewed)

Suggested settings for both: **GPT-6.2 Sol, Medium**, fresh chat. Do not resume the old TST or T2b chats (TST is committed; Claude finishes T2b).
Rules for both: don't babysit long runs by polling every few minutes (it burns usage). Start long runs in the background, do other work, and check at most every 20-30 minutes. If you can't fix something, say so plainly in the report; never weaken a test to make it pass.
Claude owns: `impact_value.py`, `bbi_evidence.py`, `trait_adapter.py`, `ratings_model.py`, `sim.py`, `offense.py`, trade *valuation* in `transactions.py`, `data/canonical/impact_value_fit.json`, and `scripts/build_mature_fixture.py` / `output/t2b/` (a builder is running; don't touch it). Don't edit those.

### BUG-A: Pick protections and pick-swap trades

```
Read AGENTS.md, docs/agents/BOARD.md and docs/agents/tasks/tst-suite-triage.md first. You own task BUG-A; add a board row "in progress (Codex)".

The test triage quarantined three tests that look like real bugs in draft-pick handling. Each has a unittest.skip("needs review: ...") marker; the report lists the failing check.
1. tests/test_imported_rookie_ratings.py test_pick_protections_are_unchanged_for_both_starting_versions: the current starting version loads ZERO pick protections where the archived data had 85 (e.g. protected first-round picks owed between teams). Find where pick obligations are loaded for a new save (storage/import path) and why they're empty. If real protections are being dropped from new saves, that is the most important fix here.
2. tests/test_foundation.py test_ai_offer_packages_can_create_pick_swap_sweeteners: AI offer packages never include a pick swap. Find which eligibility rule excludes them.
3. tests/test_foundation.py test_trade_evaluation_uses_team_context_and_legality: the decision comes back as something other than accept/reject. Decide whether the test is stale (a newer counteroffer outcome is intended; cite the commit) or the engine is wrong.

For each: find the cause, fix it in src/ if it's an engine bug (smallest change; keep seeded results unchanged unless the fix requires it, and say so), remove the skip marker, and make the test pass with its original assertion. If the test is stale, update it with a one-line comment citing the evidence.

ALLOWED FILES: pick/draft-pick modules (pick_rules.py, pick_presentation.py, pick-related functions in transactions.py and storage.py), trade offer package generation in transactions.py (NOT player valuation), the three tests above.
CHECKS: the three tests, PYTHONPATH=src .venv/bin/python -m unittest tests.test_foundation tests.test_imported_rookie_ratings, and bash scripts/run_core_tests.sh.
REPORT: docs/agents/tasks/bug-a-picks.md, plain language first (what was wrong, what it meant in the game, what changed). Board row to "review". Do not commit.
```

### BUG-B: Missing heights, staff budget, duplicate draft-class work, social-post evidence

```
Read AGENTS.md, docs/agents/BOARD.md and docs/agents/tasks/tst-suite-triage.md first. You own task BUG-B; add a board row "in progress (Codex)".

Four quarantined tests in tests/test_foundation.py look like real bugs (each has a unittest.skip("needs review: ...") marker; the report lists the failing check):
1. test_rostered_players_have_dashboard_core_data: 11 rostered players have no height (e.g. Tucker DeVries, BOS). Fill the real heights (and weight/wingspan if also missing) from a public source (NBA.com, Basketball Reference, team rosters, combine data). Record each value's source in your report. Put them where the game's other player measurements live; find that path first. Don't invent values.
2. test_staff_queue_keeps_live_strategy_from_raising_budget: the AI's live strategy raises a team's staff budget when the test says it must not. Find the guard and fix it, or show the test is stale (cite a commit).
3. test_future_draft_pick_recommendations_use_generated_class: the generated draft class is built twice instead of once (wasted work). Remove the duplicate computation without changing results.
4. test_extension_social_requires_sim_evidence_for_health_money_position_and_conference_claims: a fan post claiming "durability bet" is accepted when the test expects it to be rejected (injury risk 0.0 with 64 missed games). Fix the evidence check so health claims need matching sim evidence.

For each: fix the cause (smallest change), remove the skip marker, and make the test pass with its original assertion; or, if the test is stale, update it with a one-line comment citing evidence.

ALLOWED FILES: player measurement data for the 11 players, staff budget code, the draft recommendation code path, the social-post validator, and tests/test_foundation.py (these four tests only). If a fix needs a file in Claude's list above, stop and describe it instead.
CHECKS: PYTHONPATH=src .venv/bin/python -m unittest tests.test_foundation, bash scripts/run_core_tests.sh.
REPORT: docs/agents/tasks/bug-b-data-staff.md, plain language first. Board row to "review". Do not commit.
```

---

## Earlier (2026-11-17 morning; SPD and TST done, T2b finishing under Claude)

Run them in separate chats; they touch different files. Claude is meanwhile working on ratings/value files (`bbi_evidence.py`, `impact_value.py`, `trait_adapter.py`, `ratings_model.py`, `sim.py` assist/rebound functions, `transactions.py` valuation, the BBI mapping and `data/canonical/*`). **Do not edit those.**

### SPD: Fewer full league rebuilds per sim day (exact speedup)

Suggested settings: GPT-6.1 Sol, High, fresh chat.

```
Read AGENTS.md and docs/agents/BOARD.md first (see "Speed check (rule 10)"). You own task SPD; mark it "in progress (Codex)" on the board.

GOAL: make simulating a month faster without changing any result.

FACTS (measured 2026-11-17 by Claude):
- A headless mid-season month (Feb 15 -> Mar 15, AI on) takes ~20.6 s; an early-season month (Oct 20 -> Nov 20, fresh save) ~55 s. Target: 10-20 s.
- A cProfile of the month shows save.canonical_with_save (a full league rebuild, ~0.37 s each) is still called about once per sim day from advance_lifecycle_to (save.py), plus extra rebuilds in advance_save_day for ai_canonical and role_active, and in review_ai_releases when rosters change. The game sim itself (sim_game_with_context) is ~27% and is out of scope.
- Claude already made two exact changes: an early exit in process_inseason_released_free_agent_signings, and reuse of the day's lifecycle state for ensure_roster_minimums and the in-season signing check (same reuse rule the code uses for ai_canonical). Read those diffs (git log -p --follow src/nba_gm_data/save.py | head -300) to see the pattern.

WHAT TO TRY (your design; keep it exact):
- Carry the active league state across consecutive days within one advance_save call when the roster, contract and free-agent inputs did not change (refresh_active_runtime_state exists for health/minutes refreshes). advance_lifecycle_to currently resets `active = None` per call.
- Avoid rebuilding role_active when nothing roster-related changed since ai_canonical.
- Anything else the profile shows, as long as results stay identical.

HARNESS (reuse; scripts are in output/overnight-2026-11-17/):
- speed_month.py advances a copy of a seed-103 legacy save (output/overnight-2026-11-17/crash103/s3.json + its .history.sqlite3*; copy both to a scratch folder first, never edit the originals) to a date and prints seconds.
- fresh_month.py creates a fresh BOS seed-55 save and advances it to 2026-11-20.
- Exactness check: run old code and new code from identical starting files and compare the saved JSON after removing meta.save_snapshot_id and history_store.snapshot_id (and history_store.path if file names differ). They must be EQUAL. Also compare the history sqlite tables' row counts.
- Also verify a new-ratings save (create_league_save(..., ratings_model="inputs_v1")) for one month the same way.

BOUNDARIES: edit only src/nba_gm_data/save.py (and a new test file). Do not change formulas, RNG streams, or any file listed at the top of this queue.

ACCEPTANCE:
1. Byte-identical results (as defined above) on: the mid-season legacy month, the fresh early-season month, and one new-ratings month.
2. Report before/after seconds for each (median of 2 runs).
3. bash scripts/run_core_tests.sh passes (329 tests).
4. A short plain-language report in docs/agents/tasks/spd-sim-speed.md; set the board row to "review". Do not commit.
```

### T2b: Fix the 10-season driver and rebuild the 2036 test fixture

Suggested settings: GPT-6.1 Sol, Medium, fresh chat. Long compute (~2 h); start it early.

```
Read AGENTS.md and docs/agents/BOARD.md (task T2 row) first. You own task T2b; mark it "in progress (Codex)".

GOAL: restore the last missing test fixture, output/roster-forecast-pass/fixtures/mature2036.json, which tests/test_roster_forecast_performance.py::test_archived_2036_generated_and_injured_rosters_without_advancing_the_career needs (it currently skips). The test asserts state.current_date == '2036-11-01' and uses the save's players, health states and generated (drafted) players.

FACTS:
- The original generator scripts/prepare_roster_forecast_fixture.py extracted from a 565 MB archived checkpoint that no longer exists.
- scripts/ten_season_soak.py is stale: it dies at the draft-lottery phase (a 2027-06-22 save now needs the `draft_lottery` action). scripts/overnight_market_health.py has a current phase driver you can learn from.
- One simulated month takes ~20-60 s headless, so 10 seasons is roughly 1.5-2.5 h. Run it in the background, check progress, and keep a log.

STEPS:
1. Fix scripts/ten_season_soak.py (or write scripts/build_mature_fixture.py) to drive a fresh seed-17 legacy save through every phase (regular season, playoffs, lottery, draft, re-signing, free agency, preseason) to 2036-11-01, with AI on, saving periodic checkpoints under output/t2b/ so a crash can resume.
2. Produce the fixture. Store it as a tracked, compressed file under tests/fixtures/ (keep only the save fields the test reads, if that is enough; target under 15 MB) and point the test's loader at it, falling back to a skip with a clear message if absent. Do not change any assertion.
3. Report any engine crash with the traceback (don't fix engine code; note it for Claude).

BOUNDARIES: scripts/ten_season_soak.py or a new script, tests/fixtures/, and the fixture-loading lines of tests/test_roster_forecast_performance.py only. Don't edit src/.

ACCEPTANCE: PYTHONPATH=src:scripts:tests .venv/bin/python -m unittest tests.test_roster_forecast_performance runs with 0 skips (or report exactly why not). Short report in docs/agents/tasks/t2b-mature-fixture.md; board row to "review". Do not commit.
```

### TST: Triage and fix stale tests in the full suite (tests only)

Suggested settings: GPT-6.1 Sol, Medium, fresh chat.

```
Read AGENTS.md and docs/agents/BOARD.md ("Test suite health" and "Full-suite leftovers" sections) first. You own task TST; mark it "in progress (Codex)".

GOAL: a full test suite that is green or explicitly quarantined, so real regressions are visible.

STEPS:
1. Run the full suite once: PYTHONPATH=src:scripts:tests .venv/bin/python -m unittest discover -s tests 2>&1 | tee output/tst/full_before.log (takes ~40 min; run in background). Note: some tests need scripts/ on the path; plain src fails their imports.
2. Classify every failure: (a) stale pin, where the game changed on purpose (roster refresh, ratings refresh, new save fields, renamed GUI functions); (b) fixture/path problem; (c) likely real bug.
3. Fix (a) and (b) in tests/ only. For each changed assertion, add a one-line comment saying why the new expectation is right, with evidence (commit, data change, board note). NEVER loosen a tolerance or delete an assertion just to pass; if unsure, mark it with unittest.skip("needs review: <reason>") and list it.
4. Do not fix (c); list each with the failing assertion and your diagnosis for Claude.
Known context: rating-pin tests (test_imported_rookie_ratings, test_player_tuning, test_roster_alignment, test_rotation_profile_calibration) pin legacy-mode values. Check whether the legacy values changed deliberately (git log -S) before updating. Today's engine commits changed box-score steals/blocks/rebounds/free throws (scores unchanged), so tests pinning those box stats may need new expectations: verify they are improvements, not regressions.

BOUNDARIES: tests/ only (including tests/fixtures/). Do not edit src/ or scripts/.

ACCEPTANCE: rerun the full suite; report before/after counts (pass/fail/error/skip), the list of quarantined tests with reasons, and the suspected real bugs. Report in docs/agents/tasks/tst-suite-triage.md; board row to "review". Do not commit.
```

---

## E2b: Stop priors from averaging away elite players (DONE, accepted 2026-11-16)

Suggested settings: GPT-6.1 Sol, High, in a fresh chat.

```
Read AGENTS.md, docs/agents/BOARD.md (the "T3 diagnosis" and "Inputs mode is NOT ready" notes), docs/agents/STAGE1_DESIGN.md and your own E2 report docs/agents/tasks/e2-input-estimator.md first. You own task E2b. Mark it "in progress (Codex)" on the board.

PROBLEM (measured 2026-11-16 by the coordinator)
In the new-ratings mode (NBA_GM_RATINGS_MODEL=inputs_v1), the AI's on-court value compresses stars toward ordinary rotation players. On-court value is computed from the 15 legacy traits that trait_adapter.py derives from your inputs:

| Player | Legacy on-court | Inputs-mode on-court | Market rank, legacy -> inputs |
|---|---|---|---|
| Jokić | 83.7 | 73.9 | 3 -> 28 |
| Wembanyama | 87.5 | 72.4 | 1 -> 40 |
| Giannis | 78.6 | 68.8 | 23 -> 66 |

Reproduce with:

    NBA_GM_RATINGS_MODEL=inputs_v1 PYTHONPATH=src .venv/bin/python scripts/market_sanity_report.py

and compare against the same command without the variable.

Cause: about 86% of input cells are priors. Each prior is a position/role mean plus a small, bounded personal residual. For an elite player most technique inputs have no direct evidence, so they sit near the position average, and the elite signal is averaged away.

FIX (statistically principled, evidence-based, NOT fitted to the market report)
Make priors hierarchical. A player's prior for an unobserved skill should be centred on the position/role mean SHIFTED by that player's general talent level in the related family, estimated from his own evidence: his directly estimated inputs in the same family, provider impact metrics already in the data (Crafted DPM/OPM, LEBRON or similar if present, BBallIQ), minutes/usage, and his legacy traits as weak evidence. Skills are positively correlated, so a player who is excellent on every observed skill is more likely above average on an unobserved one.
- Shrink the shift by sample size and uncertainty.
- Keep it labeled `reason: prior` with honest wide bands.
- Do not use simulation outcomes, the market report, or named-player overrides to set coefficients. Declare the correlation and shift assumptions in code comments and the report.

ACCEPTANCE
1. The adapter-derived on-court values (computed by the engine) for the top 50 legacy on-court players retain a spread comparable to legacy: the standard deviation across those 50 is at least 80% of the legacy SD. Report both.
2. The rank correlation between inputs-mode and legacy on-court across rotation players (minutes_projection >= 15) is at least 0.7. Report it; legacy is not ground truth, so also list the 15 biggest movers with a one-line reason each.
3. The real-stats scorecard does not get worse:

       NBA_GM_RATINGS_MODEL=inputs_v1 PYTHONPATH=src .venv/bin/python scripts/calibration_report.py --games 1230

   Current per-36 average errors: points 3.19, FGA 2.37, 3PA 0.50, REB 1.29, AST 1.02.
4. Existing estimator, BBI and player-model tests pass, and determinism is preserved.

FILES: src/nba_gm_data/input_estimator.py, tests/test_input_estimator.py, regenerate data/canonical/player_inputs_2026_27.json and .json.gz via scripts/build_player_inputs.py, and docs/agents/tasks/e2b-elite-priors.md (report, TL;DR first, plain language). Do not edit trait_adapter.py, ratings_model.py, transactions.py or the GUI.

Set the board row to "review". Do not commit.
```

---

## E2c: Generated players are defined by the generator, not shrunk to priors (DONE, accepted 2026-11-16)

Suggested settings: GPT-6.1 Sol, High, in a fresh chat or continuing the E2b chat if it still has context.

```
Read AGENTS.md, docs/agents/BOARD.md, docs/agents/STAGE1_DESIGN.md (section F) and src/nba_gm_data/ratings_model.py (_install_generated_players) first. You own task E2c.

PROBLEM (measured 2026-11-16)
In a new-ratings save, the 2027 draft class got inputs through `InputEstimator().estimate_player_inputs(player, legacy_traits, prospect=True)`, but their derived display ratings are near the league floor. Pick 1 shows OVR 24.0, pick 3 OVR 3.0, pick 5 OVR 31.4, against a league median of 50. The prospect path treats the draft model's current_ability, potential, archetype and generated traits as "not technique evidence". That is correct for REAL people, but wrong for FICTIONAL generated players: for them, the generator's output DEFINES the player.

FIX
For players with source_kind in ("generated_rookie", "generated_prospect", or any other generated kind you find in draft.py/save.py), build the 94 inputs FROM the generator's definition, deterministically from the player id/seed:
- current_ability (talent level now) and potential.
- The archetype (draft.py archetype weights) for the skill shape: shooter, creator, rim protector, and so on.
- The generated 12 draft traits and/or legacy rookie traits for the per-skill profile.
- height/weight for the physicals.
Unobserved detail within an archetype can vary deterministically per player. Calibrate the mapping on REAL players: choose it so that a generated player with current_ability X and archetype A lands where real players of similar overall and role land in the existing input distribution. Real-player input data is the reference. Simulation outcomes are not.
Label these records clearly, e.g. reason "generated", with evidence source "draft_model". This needs a small, coordinated schema decision; if the schema forbids a new reason, use reason "estimated" plus a distinct evidence method, and propose the schema change in your report.

Keep real prospects (the 2026 real class with college stats) on the current evidence path; that one is correct.

ACCEPTANCE
1. In a new-ratings save carried through a draft, the derived OVR of generated rookies tracks their draft model ability: the top-5 picks' median display OVR is roughly in line with real current NBA rookies/second-year players of similar pick slot. Report the comparison.
2. There are no near-zero display ratings for any lottery pick.
3. Tests pass, and output is deterministic.
   - Test save: copy /private/tmp/claude-501/-Users-noahtyler--claude-spares-spare-kEIEMb/aa8ffa3d-9829-4c0d-b448-e9409427c53d/scratchpad/cycle/inputs_save.* (with its sidecar files, original names) into your own scratch dir.
   - Inspect it with ratings_model + player_profile.

Files: src/nba_gm_data/input_estimator.py (prospect/generated path), tests/test_input_estimator.py, docs/agents/tasks/e2c-generated-players.md. Do not edit ratings_model.py or draft.py without noting it in the report.

Set the board row to "review". Do not commit.
```

---

## BBI: Basketball Index capture pipeline (DONE, accepted 2026-11-16)

Suggested settings: GPT-6.1 Sol, High, in a fresh chat.

```
Read AGENTS.md, docs/agents/BOARD.md, docs/agents/STAGE1_DESIGN.md and docs/ratings-evidence-2026-10-29/BBI_ACQUISITION_PLAN_2026_11_11.md (plus its manifest JSON) first. You own task BBI. Mark it "in progress (Codex)" on the board.

GOAL
The user will buy ONE month of Basketball Index (BBI, $5) and wants to extract every penny of value. That means capturing everything the paid membership legitimately exposes for personal use: all seasons, all metric families, all players, both raw values and percentiles or grades, plus sample sizes where shown. It must stay within the site's terms; no circumventing protections. The subscription has NOT been purchased yet. Your job is to build and test everything BEFORE purchase, so the paid month is spent purely collecting.

DELIVERABLES
1. A capture plan in docs/agents/tasks/bbi-capture-plan.md:
   - Every BBI tool, page and leaderboard that exposes player data (Skills, Leaderboards, LEBRON, Lineups, Rotations, Playtype, Matchup, Shooting, and any others you find).
   - For each: what fields it shows, seasons available, filters, whether it has a CSV/export button, and how many page views or exports a full-league capture needs.
   - Prioritize by value to our 94 inputs, using the existing manifest and docs/PLAYER_OBJECT_THREE_COLUMN_MAP_2026_11_12.md.
   - Estimate total capture time.
   - Identify what can only be done through the user's signed-in browser and give the user a step-by-step day-1 checklist. The user (or Claude driving the user's browser) does the signed-in capture; you do not log in or pay.
   Use only public information (free pages, the public glossary, free demo tools).
2. An importer, src/nba_gm_data/bbi_import.py, that ingests captured exports (CSV and/or saved page HTML/JSON) into a normalized local cache: data/research/bbi/ with raw files preserved plus a normalized JSON. It must:
   - Match players to our canonical ids (ESPN id where available, careful name matching otherwise; report unmatched rows).
   - Keep season, metric name, raw value, percentile or grade, sample size and retrieval date separate.
   - Never relabel provider composites as raw technique.
   Test it end-to-end on whatever free BBI data you can legitimately download now (free leaderboards, LEBRON CSV, demo pages), plus small synthetic fixtures shaped like the paid exports.
3. An evidence source plug-in for the estimator. In src/nba_gm_data/input_estimator.py, add BBI as a source that maps specific BBI metrics to specific inputs (follow the manifest's intended mappings), with shared-evidence ids and sample-size weighting, so that once the cache exists, `scripts/build_player_inputs.py` uses it automatically. When the cache is absent, output must be unchanged (byte-identical); test that.
4. Tests in tests/test_bbi_import.py.

FILES YOU MAY TOUCH: the files above, data/research/bbi/ and docs/agents/tasks/bbi-*.md. Do not edit trait_adapter.py, ratings_model.py, player_profile.py, save.py, sim.py or GUI files.

DELIVER: a plain-language report (TL;DR first) in docs/agents/tasks/bbi-capture-plan.md, including the day-1 checklist. Set the board row to "review". Do not commit.
```

---

## S1-E-inv: Front-office threshold inventory (read-only)

Suggested settings: a mid-tier model, medium effort.

```
Read AGENTS.md, docs/agents/BOARD.md and docs/agents/STAGE1_DESIGN.md section E first. You own task S1-E-inv. This task is READ-ONLY for code. You may only create docs/agents/tasks/s1e-threshold-inventory.md (and scratch files under output/s1e/).

CONTEXT: The AI front office (trades, contracts, extensions, free agency, draft, fantasy draft, waivers, release planning, trade wants) reads player ratings through save.player_attribute_summary / player_display_attribute_summary. That is an OVR/OFF/DEF/subrating formula over the 15 legacy traits, clamped to 1–99, with about 75 call sites. Stage 1 will switch those readers to the new unclipped 50+15z display scale (src/nba_gm_data/player_profile.py). Every hard-coded threshold on the old scale must then be re-expressed, ideally as a league percentile.

PRODUCE a table of EVERY place a rating value from those summaries (or a value computed directly from it) is compared to a constant, or used in a formula with a constant breakpoint. For each row give:
- file:line and function;
- which field (overall, offense, defense, shooting, ...);
- the constant(s) and what decision they drive, in plain language;
- the league percentile that constant corresponds to on the CURRENT old scale. Compute it from data/canonical/universe_2026_27_offseason.json using save.player_display_attribute_summary over all players; report the percentile among rotation players (minutes_projection >= 15) too;
- a suggested replacement expression (e.g. `percentile >= 0.97`).
Also list call sites that only display values (no thresholds), separately.

Group by system (trade valuation, contract/extension, free agency, draft/fantasy, roster/waivers, narrative/UI). End with the 10 thresholds most likely to change AI behavior if mis-converted. Set the board row to "review". Do not commit.
```

---

## E2: League-wide player input estimator v1 (DONE, accepted 2026-11-16)

Suggested settings: your strongest model, high effort. This is the most important task Codex has this month. If usage runs out mid-task, keep the resume state current so a fresh chat can continue.

```
Read AGENTS.md, docs/agents/BOARD.md, docs/agents/ENGINE_ROADMAP.md and docs/agents/STAGE1_DESIGN.md first. You own task E2: component A in STAGE1_DESIGN. Claude is building the adapter (component B) in parallel against your output format, so keep the output schema stable and documented at the top of your report. Mark it "in progress (Codex)" on the board.

GOAL
Every player in the game needs values for the approved 94-input player model (src/nba_gm_data/player_model.py, player_model_registry.py; design in docs/PLAYER_OBJECT_THREE_COLUMN_MAP_2026_11_12.md). Today only 32 players have partial hand-researched inputs (docs/ratings-evidence-2026-10-29/*_INPUTS_*.json packets). Build a deterministic, evidence-based ESTIMATOR that produces inputs for ALL 691 players in data/canonical/universe_2026_27_offseason.json, plus a function for draft prospects.

FILES YOU OWN (create or edit only these)
- src/nba_gm_data/input_estimator.py (new)
- scripts/build_player_inputs.py (new): writes data/canonical/player_inputs_2026_27.json
- tests/test_input_estimator.py (new)
- docs/agents/tasks/e2-input-estimator.md (checkpoint plus final report)
Do NOT edit player_model.py/registry semantics, sim.py, interior_game.py, or any engine module. If the schema needs a change, write the proposal in your report instead.

EVIDENCE SOURCES (local only, no purchases)
- Player Stats/player_skill_input_2025_26.json: Crafted NBA 2025-26, ~526 players. Shooting splits, close-shot efficiency, BLK/STL%, deflections, ORB/DRB%, touches/passes, passer rating, play-type usage and points per possession (P&R handler, roll man, spot-up, iso, post, cut, transition, handoff, off-screen), defended-position shares.
- Player Stats/player_stats.json, Even more stats/*.xlsx, data/research/player_career_stats.json + espn_career_raw/ (ESPN careers, 616 of 691 matched by ESPN id).
- Universe player fields: height_inches, weight_lbs, wingspan_inches (427 present), age, position, roles; the 15 existing traits[] (all 691 players; see src/nba_gm_data/traits.py). Old traits may inform priors but must NOT be relabeled as technique skills.
- docs/ratings-evidence-2026-10-29/PLAYER_MODEL_EVIDENCE_COVERAGE_2026_11_12.md: per-input evidence handles and estimation notes. Follow its "evidence-to-input contract".
- Expert opinion: the Nerd Sesh transcript research in docs/ratings-evidence-2026-10-29/ (claim index, named-player dossiers, rating-change proposals). Treat it as expert evidence that can adjust an estimate, with its own source id. It is not the sole truth, and it is not a reason to override clear stats without saying so.
- Basketball Index data may be added later (BBI_ACQUISITION_PLAN_2026_11_11.md). Design the estimator so a new evidence source can be plugged in per input without rewriting it.
- Known data bug: the historical game-box cache has FGM/FGA = 0 (see HISTORICAL_SHOOTING_DATA_QA_2026_11_13.md). Do not use those fields.

REQUIREMENTS
1. For every player and every one of the 94 inputs, emit a record in the existing PlayerInputs schema: value, uncertainty, status, and source/evidence ids. Statuses must distinguish:
   - "estimated": derived from that player's own evidence.
   - "prior": no player-specific evidence; uses a position/role/physical prior with wide uncertainty.
   The ENGINE needs a usable number for every input, so every input must have a value. "Prior" values must be clearly labeled and must not masquerade as measurements.
2. Method: shrink toward position/role priors, weighted by sample size (minutes, attempts, possessions). Keep passing recognition and execution as separate estimates. Make tendencies conditional on opportunity. Physical families come from measurements where present; otherwise from priors (e.g. wingspan from height by position) with wide uncertainty.
3. Scale: no clipping at 100. Map to the registry's scale by rescaling, so elite players stay distinguishable.
4. Ratings-first: inputs come from evidence only. Never tune estimates toward simulation outcomes. There are no simulation runs in this task.
5. Validation: compare estimator output to the 32 hand-researched players' estimated cells (the packets overlap; use the newest value per cell). Report per-input agreement (mean absolute difference, and how often the hand value falls inside your uncertainty band), plus the 10 biggest disagreements with a one-line explanation each. Hand values are a reference, not ground truth.
6. Prospects: estimate_prospect_inputs(prospect, traits, scouting) for generated and real draft prospects (src/nba_gm_data/draft.py: generate_draft_class_records, prospect_traits_from_row), using the same definitions with wider uncertainty. Don't wire it into draft.py; just provide and test the function.
7. Deterministic: same data gives byte-identical output. Standard library only.
8. Tests: schema validity for all 691 players, determinism, no missing values, no clipping pile-ups at the scale max, prospect function, and a few sanity orderings that are obvious from raw stats (e.g. FT shooting follows FT%). Do not hardcode named-player ranking tests.

DELIVER
Run: PYTHONPATH=src .venv/bin/python scripts/build_player_inputs.py, then the new tests. Write the final report (plain language, TL;DR first) in docs/agents/tasks/e2-input-estimator.md. Include coverage counts (estimated vs prior, per input family), the validation table, known weak spots, and runtime. Keep a "Resume state" section updated while you work. Set the board row to "review". Do not commit.
```

---

## Parked (GUI, after the engine month or if Codex has spare usage)

### Q1: Three small GUI behavior fixes

```
Read AGENTS.md and docs/agents/BOARD.md first. You own task Q1. Mark it "in progress (Codex)" on the board.

Fix three small behaviors in the browser GUI (src/nba_gm_data/gui/app.js, plus styles.css only if needed). Don't touch any other file except new or updated tests.

1. Next Opponent card after a game (backlog U03). After the W/L result animation plays, the card must switch to the actual next opponent. Today it stays on the finished game. Handle "no next game" and playback interrupted mid-animation.
2. Sim shortcut prefix (U04). Pressing S, then E, W or M must work no matter how long the pause between the keys. The S prefix stays armed until the user clicks something else, presses Escape, or focus moves to a text input. Never hijack typing in inputs or browser shortcuts. No timers.
3. Draft lottery grid order (U05). Around app.js:4837 the reveal grid lists picks 14 down to 1. The grid must show pick 1 at top-left and 14 at bottom-right. Keep the reveal timing (14 then 13 ... then 1); only the spatial placement changes.

Match the existing code style. Add or extend tests where GUI JS tests already exist (tests/*.test.cjs).

When done: write a 10-line plain-language summary at docs/agents/tasks/q1-gui-small-fixes.md. Set the board row to "review". Do not commit.
```

### Q2: Draft board diagnosis (read-only)

```
Read AGENTS.md and docs/agents/BOARD.md first. You own task Q2. READ-ONLY for code and data; you may only create docs/agents/tasks/q2-draft-diagnosis.md and scratch files under output/q2/.

The user saw the 2nd-ranked prospect (96 POT / 80 NOW) fall to 15th and asked whether the AI or our rankings are wrong, and whether there should be both a consensus big board and a scouting board. With file:line references (draft.py, prospect_cards.py, talent.py, gui/app.js draft board):
1. How the displayed ranking is computed.
2. How AI GMs score prospects at their pick.
3. Reproduce across about 5 seeds headlessly: how far the top-5 fall, and which term drove each pass.
4. Whether "upside" and "potential" overlap or double-count.
5. A proposed (not implemented) design for consensus vs scouting boards.

Lead with a 5-line plain-language answer. Set the board row to "review". Do not commit.
```
