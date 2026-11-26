# AI-TRADES-SENSE: AI trades a sharp fan finds believable

Progress: 8/8 - done, ready for the coordinator's review

Owner: Claude (side session, worktree `ai-trades-sense-bf964d`, branch `claude/ai-trades-sense-bf964d`).

## Report

**TL;DR**
- AI front offices no longer spend first-round picks on end-of-bench players, flip pick rights within weeks, pay full
  price for a player out for the season, give a useful player away, or sell a champion's core to save tax.
- Hard-capped teams no longer sign their way into a short roster (four short teams on one test season, one after).
- Trade volume and speed are unchanged (52/52 trades before, 50/52 after; a month takes the same time); full suite green.

**What changed, in game terms**
1. *Champions run it back.* A team that won two or more playoff rounds stays a contender through the summer and
   the first 25 games, unless its core is genuinely old. A contender sending out one of its three best players gets
   no credit for the tax it saves, so the deal must stand on basketball value. Replayed on the season review's own
   June 30 save, Cleveland now rejects Evan Mobley for Cam Spencer (it was +4 before, now -38) and is labelled a
   contender instead of "exiting".
2. *A first buys a real player.* Giving up a first-round pick or first-round swap right now needs a player who will
   play 20+ minutes and already plays 15+, a young player with real upside, or a salary dump the first pays for.
   Seconds and pick-for-pick deals are untouched. A pick or swap right an AI team just traded for stays with it for
   90 days (AI-to-AI deals only; your own trades keep the real rules).
3. *Injured players cost less.* A buyer takes the time a player will miss off his price: out for the rest of the
   season, a contender pays about 45% of his price, a rebuilder about 80%; missing next season costs more. The seller's own value of
   his player is unchanged, and the buyer's rotation projection counts him only for the games he will play.
4. *No free useful players.* A two-team AI deal where one side gets nothing back is refused when the player sent is
   worth something real to either team. Dumping a contract with negative value already needed picks attached.
5. *Hard caps.* An AI team under a hard cap (or using a mid-level or bi-annual that would trigger one) keeps room
   for minimum contracts up to 14 players, in signings and in trades. At camp, if a veteran's minimum doesn't fit, the
   best free agent whose (smaller) minimum fits is signed instead.

**Before and after** (one season each; full lists in `docs/agents/tasks/ai-trades-sense-trades.md`)

| | Seed 20261126 before | after | Seed 20261127 before | after |
|---|---|---|---|---|
| AI trades | 52 | 50 | 52 | 52 |
| First-round right for a player who then played under 15 min | 4 | 0 | 1 | 2 |
| Pick moved again within 90 days | 1 | 0 | 6 | 0 |
| Player out for the season bought for real value | 0 | 0 | 1 (Porzingis) | 0 |
| Finals-run team selling a top-three player | 0 | 0 | 1 (Allen) | 0 |
| Hard-capped team short at opening night | 0 | 0 | 4 (MIN 11, PHI 12, DET 13, HOU 13) | 1 (PHI 13) |

Fan's-eye verdicts on the odd ones:
- *Before, 20261126:* Washington gives a 2030 first-round swap right for Adem Bona (13 minutes) - "a first for a
  backup big?" Washington again for Tyrese Proctor (15 minutes), Charlotte for Gary Payton II at 33 (8 minutes),
  New Orleans sends DeAndre Jordan and a 2027 first-round right for Nikola Topic (10 minutes) - "eye-roll". Gone
  after.
- *Before, 20261127:* Detroit takes Kristaps Porzingis, out through June, for John Collins and three seconds - "why
  pay for a guy who can't play?" Cleveland, fresh off the Finals, sends Jarrett Allen and a second for Cam Spencer on
  July 2 - "breaking up a Finals team for a role player". Six second-round picks flipped within days. All gone after.
- *After, still there:* Washington's 2030 swap right for 20-year-old Carter Bryant (11 minutes) - "a bet on a kid,
  fine" (also in the before run). San Antonio's conditional 2030 right in a three-team deal for Gui Santos (14.5
  minutes) - "borderline". Phoenix sends Jonathan Isaac to Memphis for nothing in September - he had become a
  4-minute player worth about 10 to both teams, "a fringe contract moved to a team with room, believable". The
  Lakers take Marcus Smart's injured expiring deal for Quinten Post and Dalton Knecht to save $13M of tax, valuing
  him at 12 rather than 37 - "classic tax trim". Philadelphia opens with 13 players under a hard cap (13 is legal for two
  weeks in the real league; not traced). In the first after run it was Golden State, after its restricted free agent
  Brandin Podziemski took his $13.9M qualifying offer in August.

**Checks**
- Month speed (laptop, Oct 20 - Nov 30, same seed): 21.2 s per 30 days before, 21.6 after (noise). Azure season runs:
  about 400 s of game days per season before and after on both seeds.
- Tests: new `tests/test_ai_trades_sense.py` (14 tests); focused trade, cap, free-agency and offseason modules pass;
  full suite on Azure: 2690 tests OK (71 skipped).
- Determinism: outcomes change (by design) wherever an AI decision changes.

**Not done / for later**
- One hard-capped team per test season can still open a player short (Golden State after a late qualifying-offer
  acceptance; Philadelphia not traced). Camp doesn't shed salary by trade to make room.
- Washington declining Bona's option is handled by not buying him with a first; option decisions themselves
  (`offseason_decisions.py`) were not changed.
- `cap_ledger.py` and `save.py` (`auto_fill_rosters`) sit just outside the trade files; both changes are AI-only.

## Objective
Fix the front-office eye-rolls from the hands-off season review (`docs/agents/tasks/season-almanac.md`, items 10-14):
1. Champions and contenders keep their core (no Mobley-for-Spencer tax trade; no "exiting" label after a title).
2. First-round picks buy rotation players or real upside; pick rights don't bounce between teams within weeks.
3. Long injuries lower what a buyer pays and how much the player counts in its rotation.
4. Salary dumps cost something; a useful player isn't given away for nothing.
5. No AI move leaves a hard-capped team unable to fill 13-14 players; camp fills short rosters where it can.

Keep: textbook trade rules, LeBron's exception, number of offers.

## Boundaries
Trade, trade-market, tax, team-planning and camp roster code, tests, this file. Not `sim.py`, `offense.py`,
`box_variation.py`, `draft.py`, `gui/`, `stage2/`, or the board.

Files touched: `team_planning.py`, `trade_tax.py`, `trade_roster.py`, `trade_injury.py` (new), `transactions.py`,
`cap_ledger.py` (signing quote: hard-cap roster reserve for AI teams), `save.py` (`auto_fill_rosters` only),
`tests/test_ai_trades_sense.py` (new).

## Rules as built
1. `team_planning.latest_postseason_rounds` + window guard: a team that won 2+ rounds in the latest postseason, with
   half its core still there, stays "peak" through the summer and its first 25 games unless its top five's age trend
   is -2.0 or worse. `trade_tax.contender_core_outgoing`: a contender (peak, or 2+ rounds) sending out one of its three
   best players gets no tax credit.
2. `trade_roster.first_round_pick_purpose`: sending a first (pick or swap right) with no first back needs an incoming
   player projected for 20+ minutes who already plays 15+ in his current role, young upside of 8+, or a money purpose (tax value 10+ or $8M relief).
   `transactions.re_trade_hold_picks`: an AI team can't trade a pick or swap right it got by trade in the last 90 days
   (all-AI trades; also kept out of its offer packages).
3. `trade_injury.injury_discount`: AI buyer's price for a non-owned player out 30+ days drops by
   (window share 0.2-0.55) x (share of the rest of the season missed) + 0.25 x (share of next season missed), at most
   85%. The incoming player's projected rotation gain is scaled by the share he plays.
4. `transactions.useful_player_for_nothing`: a two-team AI deal where one side gets nothing back and sends only
   players is refused if the player is worth 12+ to either side.
5. `cap_ledger.quote`: under a hard cap (existing or triggered by the route), an AI team keeps room for rookie
   minimums up to 14 players. `transactions.salary_matching_issue`: same reserve for trades by a hard-capped AI team.
   `save.auto_fill_rosters`: when a veteran's minimum doesn't fit, the best free agent whose minimum fits is signed.

## Working notes
- Month speed (local, Oct 20 - Nov 30, same seed): 21.2 s per 30 days before, 21.6 after (noise).
- Seed 20261126: 52 trades before, 50 after; firsts for bench 4 -> 0; pick bounces 1 -> 0.
- Seed 20261127: 52 before, 55 after; injured star bought (Porzingis to Detroit) gone; finalist Cleveland's Jarrett
  Allen-for-Cam Spencer gone; pick bounces 6 -> 0; firsts for bench 1 -> 3 (Kornet, Vince Williams: projected 20+
  minutes, 12-13 now) -> rule tightened (current role 15+), rerun as after2-*.
- Hard-capped short rosters at opening night: seed 20261127 four teams (MIN 11, PHI 12, DET 13, HOU 13) -> one (GSW
  13, after its restricted free agent took his qualifying offer in August); seed 20261126 none either way.

## Resume state
- Done. Run outputs in `output/trades-sense/` (before-*, after-* = first rule version, after2-* = final), tools in
  `output/trades-sense/tools/`, launch logs `output/trades-sense/launch-*.log`.
