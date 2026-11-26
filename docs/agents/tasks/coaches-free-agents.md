# COACHES-FREE-AGENTS: fair coach firings, loyal free agents, stated reasons

Progress: 7/7 - done, ready for the coordinator's review

Owner: Claude (side session, worktree `coaches-free-agents-0514f0`, branch `claude/coaches-free-agents-0514f0`).
From the season review's "Smaller" notes and the user's comments on them (2026-11-26). Not pushed.

## TL;DR
- Coaches are now judged against what their roster should have won, allowing for injuries; champions get patience.
  Six seeded seasons on the final rules: 4, 4, 4, 6, 4 and 7 head coaches fired (average 4.8). Kerr's 38-44 season
  can no longer fire Kerr.
- Loyal players and franchise icons lean strongly to their own team. With a home offer, 32 of 33 stayed (the one
  who left got a much bigger contract), and all 6 icon free agents in those runs re-signed.
- Signings that take a free agent away now say why. Training-camp deals and sign-and-trades still do not.

## Coaches
- Before: every team was expected to win 37-44 games (Oklahoma City 43.5 in a 73-win season), and firing was a
  small random chance that ignored titles, tenure and injuries.
- Now: expected wins come from each healthy roster's strength at the season's first review, on the spread of real
  preseason win totals. Missing key players (injury or departure), above or below the league's typical amount, moves it.
- Odds rise with the miss; short stays without results, a second poor season and a change of direction add to them.
  A title this year is safe. A franchise legend (two titles there, or one and six seasons) is safe unless 10 or more
  wins per 82 short (15 in season), and rarely fired even then. The firing reason says all of this in the news.
- Replaying the review season: Golden State was about 6 wins short of 44 expected, inside Kerr's protection.

## Free agents
- Why Lillard left in the review run: Portland bid its legal maximum twice and the owner's tax rule threw both out;
  loyalty was worth very little. Now an icon's team gets the same tax allowance as for a franchise star, bids first,
  may bid down to 65% of the price, and the player weighs years there and icon standing.
- A computer team's loyal player takes his team's offer over a higher-rated outside one unless there is a clear
  motive: title chase, much more money, bigger role, poor fit, rebuild. Your own offers are judged as the offer
  screen shows them (loyalty counts there as interest).
- A veteran without a ring can leave to chase one ("leaving MIN chasing his first championship", Rudy Gobert in the
  check run); a ringless veteran icon on a non-contender tests the market about half the time.
- Review-season offseason with all 15 icons forced to expire: Curry retired, 13 stayed, Vucevic moved.
- Most stated reasons are "with no offer to stay": the old team made no bid.

## Checks
- All 256 test modules passed on Azure (2,688 tests, no failures), run in pieces because a worker is killed when one
  process holds a third of the suite (seen by other sessions too). That was before the last small edits (firing odds,
  late fill-in reason, two data fields, own-team rule); related and new tests were rerun locally and pass.
- Final rules, seed 20261126, 3 seasons (`output/cfa-final-a`): firings 4/4/4 (in season 2/2/3). Every standard
  signing departure had a reason; camp-deal departures (56/42/27) had none. The season audit's 2 "errors" are the
  old stale checks.
- Final rules, seed 7101, 3 seasons (`output/cfa-final-b`): firings 6/4/7 (in season 3/3/2). Again every standard
  signing departure had a reason; camp-deal departures (58/24/22) had none.

## Follow-ups (files this task does not own)
- GUI (`gui/app.js`): signing wire (`freeAgencySigningWirePanel`) show `move.departure_text` (now only in the hover
  headline); `signingDayRecap` append `departed[].departure_text`. Both fields are already sent.
- `camp.py` camp signings and `sign_and_trade.py`: add `franchise_ties.departure(...)` to the log assets and text.
- Odd, not touched: stars such as Antetokounmpo signing for about $16M in free agency.

## Notes for merging
- Outcomes change by design (firings, signings, staff reputations). Existing saves pick it up from their next
  season review and offseason. New save keys: `franchise_ledger`, `free_agent_origins`, `staff_titles`,
  `staff_season_expectations`, `staff_season_review`.
- Shared files touched: `save.py`, `play.py`, `app_actions.py`, `scripts/season_almanac_run.py` (`--seasons`).
- New data: `data/research/nba_champions.json`, `head_coach_standing_2026_27.json` (real coaches' years and titles,
  from general knowledge; only the 2026 Knicks title was checked online).

## Resume state
Done and committed (not pushed). All Azure runs of this task have finished.
