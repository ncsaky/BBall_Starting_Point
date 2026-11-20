# Keep stars: Bird rights, franchise stars kept, a six-month hold on re-trades (2026-11-20)

_Claude (Opus agent), branch `worktree-agent-adc22238a07d61ff9` (from main at 91e028c). Follows `trade-volume-2.md`.
Status: **review** (committed on the branch, not pushed or merged)._

## TL;DR
- **Denver keeps Nikola Jokić now.** The cause was not the hard cap: re-signing him left Denver $1.7M under the tax
  line, inside the $4M "stay below the line" room a retooling team kept, so the payroll rule refused him.
- **Teams now have Bird rights, as in the real league**: they can re-sign their own players over the cap and the
  hard cap, offer a fifth year and 8% raises; the league's 15 best players (and good young players coming off their
  first deals) are kept almost always, paying tax if needed. The user's re-signing room shows and obeys the same rules.
- **AI teams no longer flip a player they just traded for**: about six months' hold unless he is the centre of a
  salary-matching deal. In the two-season test quick re-trades fell from 4 to 0, and trades held steady (75 -> 76).

## The cause, with proof
Replayed Denver's 2028 offseason from the merged run's draft-day save (`output/tv2/final2-probe/snapshots/draft_2028`,
copied; the original untouched), tracing each AI re-signing decision (`output/ks/debug_resign.py`):

```
RETAIN? Nikola Jokić team_den star_ask 61.8 age 33.0 -> True
HARDCAP Nikola Jokić team_den terms 61800000 2 -> True
PAYROLL Nikola Jokić team_den -> False {"before": 153478342, "after": 213028342, "tax_line": 214700000, "tax": 0.0,
        "ceiling": 210700000.0, "ok": false, "reason": "keeps_room_below_the_line_for_its_phase"}
```

- He was wanted (the "keep the star" rule said yes), his ask was his $61.8M max, and Denver had $86.7M of room under
  the hard cap that day, so the hard cap was **not** the problem in this run (the earlier run's report blamed it).
- The payroll rule from trade volume 1 refused him: Denver was labelled "retooling", and a retooling team keeps
  $4M of room under the tax line when it re-signs a starter (half of $8M). Re-signing Jokić left it $1.7M under the
  line ($213.0M against $214.7M), so the rule said no, although it cost no tax at all.
- He then went to the open market. Denver could not bid him back: outside offers were limited to room under the tax
  line minus the same payroll rule, with no incumbent advantage. Memphis signed him for $43.0M x 4.
- Ruled out: re-signing order (stars already go first), the hard cap, his willingness (the AI re-signing pass does not
  ask the player), options (his contract simply ended in 2027-28), and the user-versus-AI rule (Denver is AI).

## The Bird rules (sources)
Sources: Hoops Rumors glossary "Bird Rights" (March 2026) and "Early Bird Rights" (March 2026; earlier editions show
the 175% figure on Kevin Durant's 2017 deal and the four-year Early Bird limit on Isaiah Hartenstein's 2024 deal),
Larry Coon's CBA FAQ (the site's certificate had expired, so it was read through these summaries).

| Rights | Earned after | First-year salary over the cap | Years | Raises |
|---|---|---|---|---|
| Full Bird | 3 seasons with the team (trades keep the clock; changing teams as a free agent resets it) | up to his max | up to 5 | 8% |
| Early Bird | 2 seasons | greater of 175% of last salary or 105% of the league average salary, never above the max | 2-4 | 8% |
| Non-Bird | 1 season or less | 120% of last salary (or of the minimum) | up to 4 | 5% |
| Any other team | | needs room | up to 4 | 5% |

- Re-signing with Bird rights never triggers a hard cap in the real CBA, so a team may go past the second apron (the
  game's hard cap for trades and outside signings) to keep its own player. Above his Bird limit a team needs real room.
- The task brief said "105% of the previous salary" for Early Bird; the real rule is the 175% / 105%-of-average one
  above, which is what the game uses. The league average salary is an estimate (8% of the cap, about $12.5M for
  2025-26), marked uncertain in `cap_rules.py`; it only matters for Early Bird players on small salaries.
- Restricted free agency (a team matching offers for its young players coming off rookie deals) is not in the game.
  A regular (24+ minutes) coming off his rookie deal (four seasons or fewer in the league, 25 or younger) is treated
  like a franchise star instead, which gives the same result: his team keeps him, at the better of his star price and
  his researched market price (the research file already marks these players "restricted"). Found in the first
  two-season attempt: Brandon Miller (24, Charlotte's 29th-best player league-wide) had no star-tier price, so the old
  dice roll decided, he left, and Charlotte was not even among his open-market bidders.

### How the game tracks it
- Each player's "Bird clock" starts when he signs with a team as a free agent or is drafted, keeps running through
  trades, re-signings and extensions with the same team (`save["bird_clocks"]`), and starts again with any new team.
- Players on opening-day rosters get it from their real seasons (ESPN career data): seasons counted back from 2025-26
  while each season shares a team with the next. Jokić, Antetokounmpo, Dončić, Brunson, Gilgeous-Alexander: full Bird.
  Approximations: an offseason trade before 2025-26 ends the count, and summer-2026 free-agent moves are known only for
  the 48 contracts in `data/research/free_agent_contracts_2025_2026.json`.

## What changed
- **AI re-signing** (`save.py`):
  - Franchise stars: the league's 15 best players by current on-court value (and young regulars off their rookie
    deals) are kept at any age, unless the team is rebuilding and he is 31 or older. Stars and young regulars are
    settled first, by price.
  - Re-signing within Bird rights skips the hard-cap check.
  - Stars' contracts: five years for a 27-or-younger star with full Bird rights, four through 30, three through 33;
    8% raises with full or Early Bird rights (5% otherwise). Before: 4 years or the usual rule, 3.5% raises.
- **Payroll discipline** (`payroll_plan.py`): keeping a franchise star skips the "room below the line" rule and is
  worth up to $100M of tax plus lost payout for the season, divided by the owner's money factor (about $71M-$143M).
  Golden State's real 2022-23 tax bill was about $170M. A ruinous bill (for example a $45M star on a payroll already
  near the line, about $120M of tax) is still refused.
- **Open market** (`play.py`): a team still holding its free agent's rights bids with Bird rights (over the cap, a
  fifth year for a young player) and the payroll rule treats it as a re-signing. Players value staying a little more:
  +3 interest for the team that drafted them and +3 for a winning team (60%+), on top of the existing +8 for their own
  team. For a regular (24+ minutes) the team holding his rights bids first.
- **User's team** (`app_actions.py`, `play.py` text room, `gui/app.js`): the same rules. The offer builder shows a
  line such as "Full Bird rights (4 seasons with you): you can go over the cap and the hard cap to re-sign him for up
  to $42.7M a year, 5 years, 8% raises. Other teams can offer at most 4 years with 5% raises." The salary slider goes
  up to his Bird limit, the cap check allows it, and five-year offers are only open with full Bird rights (the engine
  now refuses five years to anyone else).
- **Re-trade hold** (`transactions.py`, `trade_targets.py`): an AI team does not trade a player it acquired by trade
  in the last 182 days, unless he is its highest-paid outgoing player and at least half his salary comes back in
  players. Held players are never filler in a buyer's package or a salary dump. The real CBA only bars aggregating a
  newly acquired player's salary for 60 days (the game's existing rule); the six months is a front-office habit, not a
  league rule. Trades with the user's team keep the real rules.

## Results
### Replay of the 2028 offseason (same draft-day save)
Replay of `draft_2028` on the final rules (`output/ks/replay.py`), compared with the merged run's real outcome:

| Player (league rank) | Merged run | This branch |
|---|---|---|
| Nikola Jokić (2), Denver | **left**: Memphis, $43.0M x 4 | **stays**: $61.8M x 3, 8% raises |
| Giannis Antetokounmpo (3), Miami | stays, $46.9M x 2 | stays, $46.9M x 3 |
| Karl-Anthony Towns (12), New York | stays, $21.3M x 2 | stays, $21.3M x 2 |
| Donovan Clingan (22, 24 years old), Portland | stays, $33.0M x 4 | stays, $33.0M x 5 (fifth year) |
| Ja Morant (36), Portland | stays, $27.5M x 4 | stays, $27.5M x 4 |

Denver re-signing Jokić leaves it at $213.0M, $1.7M under the tax line: no tax. (This replay ran before the
restricted-free-agent rule below; the two-season test includes it.)

### Two-season probe (seed 17, Golden State hands-off)
Final code (commit 939b4ff), 94-input ratings, 2026-10-20 to 2028-11-01, against the merged confirmation run
(`output/tv2/final2-probe`). The brief quoted 80 trades / deadline 16 and 7-9 / draft 9 and 7; those are the
trade-volume-2 "after" run. The merged confirmation run, which includes the September market, is the fair comparison.

**Top-30 players with expiring contracts** (rank by current on-court value on draft day; `scripts/expiring_star_outcomes.py`):

| Summer | Player (rank, age) | Merged run | This branch |
|---|---|---|---|
| 2027 | Brandon Miller (29, 24), Charlotte | **left**: Milwaukee, $29.2M x 4 | **stays**: $28.8M x 5 |
| 2027 | Jimmy Butler (30, 38), Golden State (hands-off user team) | Cleveland, minimum | Boston, minimum |
| 2028 | Nikola Jokić (2, 33), Denver | **left**: Memphis, $43.0M x 4 | **stays**: $61.8M x 3 |
| 2028 | Giannis Antetokounmpo (3, 33), Miami | stays, $46.9M x 2 | stays, $47.3M x 3 |
| 2028 | Karl-Anthony Towns (12, 32), New York | stays, $21.3M x 2 | stays, $23.3M x 2 |
| 2028 | Donovan Clingan (22, 24), Portland | stays, $33.0M x 4 | stays, $33.1M x 5 |
| 2028 | Kristaps Porziņģis (27, 33), Golden State (hands-off user team) | New York, $12.3M x 3 | New York, $12.3M x 3 |
| 2028 | Anthony Davis (30, 35), Washington | retired | retired |

Every AI team kept every top-30 player whose contract ran out. The two who moved belonged to the hands-off user team,
which the probe never re-signs. Ranks 31-60 in 2028: Ja Morant stays ($27.3M x 4), Paul George and Ivica Zubac stay;
older players moved on the market (Kyrie Irving 36 to the Lakers $30.3M x 2, Kevin Durant 40 to Indiana $30.9M x 1).

**Trades and payrolls:**

| Measure | Merged run | This branch | Real |
|---|---:|---:|---:|
| Trades, whole run (2026-27 / 2027-28 / summer and Oct 2028) | 75 (32/31/12) | **76** (32/34/10) | ~110-140 |
| ... deadline week, per season | 16 / 7 | **16 / 10** | 23-28 |
| ... draft, per draft | 9 / 9 | 9 / 9 | 8-11 on draft night |
| ... summer 2027 / summer and October 2028 | 10 / 12 | 10 / 10 | |
| Three-team trades | 6 | 10 | ~8 a season |
| Players traded twice | 13 | **11** | |
| ... traded again within 6 months | 4 (Tyler Kolek after 74 days, Dylan Faulkner 141, Emanuel Sharp 151, Jarred Vanderbilt 178) | **0** (shortest gap 213 days) | rare |
| Trades with both teams' reasons stated | 74 of 75 | **76 of 76** | |
| Young starters moved / rebuild sales | 1 / 10 | 0 / 5 | |
| Teams over the tax line entering deadline week -> season end, 2027 | 13 -> 11 | 13 -> 11 | 14 -> 7 (2026) |
| ... 2028 | 9 -> 8 | 12 -> 9 | 7-14 -> 6-8 |
| Payout per team under the line, 2026-27 / 2027-28 | $4.8M / $2.4M | $4.8M / $3.6M | $4.9M-$11.5M |
| 2028-29 payrolls over the line on Nov 1, 2028 (over the second apron) | 5 (1) | 6 (1): Denver now among them at $220M | |
| 2028 summer: re-signings / market signings / waiver claims | 36 / 90 / 13 | 38 / 74 / 8 | |
| CPU seconds, whole run (2027 deadline; 2028 deadline) | 1,136 (59; 79) | 1,115 (56; 81) | |

How to read it:
- **Stars stay.** Every AI franchise player and every good young player coming off his rookie deal re-signed, at
  prices in the real range (Jokić at his 35% max; Miller and Clingan at $29-33M for five years, like real rookie-scale
  extensions).
- **No hot-potato trades.** Nobody was re-traded within six months (was 4), without losing trades: 76 against 75,
  deadline weeks 16 and 10 (was 16 and 7). Re-trades still happen after the hold, as in the real league (Toumani
  Camara after 215 days, Vít Krejčí after 213).
- **Taxpayers stay in the real range.** Keeping stars adds about one taxpayer (Denver in 2028-29, $5M over).
- Rebuild sales fell from 10 to 5 and three-team trades rose from 6 to 10. Both are one run on a different league path
  (stars staying changes who sells), not a rule change: the selling and three-team rules are untouched. Worth watching
  in the next probe.
- Speed unchanged.

## Tests
- New `tests/test_keep_stars.py` (12 tests): Bird levels, limits, years and raises; the Bird clock (new team, re-signing,
  real history for opening rosters); re-signing over the hard cap within Bird rights and not above them; the signing
  check for incumbents; franchise star kept through the payroll room and the tax budget (and a ruinous bill refused);
  retention by age and phase; young regulars off rookie deals kept at their market price, five years; the incumbent's
  fifth year and 8% raises; the offer screen's years rule; the re-trade hold (dump refused, centre of a matching deal
  allowed, expires after six months, never applies with the user's team).
- 39 trade, contract, free-agency, waiver, lifecycle and foundation modules (including `test_trade_volume`,
  `test_trade_volume_2` and the new file): 618 tests OK (15 skipped), on the final code.
- `bash scripts/run_core_tests.sh`: 337 OK.
- `node --test tests/*.test.cjs`: 282 of 283; the startup-movie test needs the ignored movie file, as on main.
- Odds check (`validate-season-probabilities --runs 20`, 1,231 games): output byte-identical to main at 91e028c (Brier 0.2009, log loss 0.5911); this task changes no game simulation. The real-stat targets are untouched for the same reason.

## What's left
- **Mid-market prices still come from minutes** (from trade volume 2). Karl-Anthony Towns (12th best) re-signed for
  $21.3M and Zach Edey for the minimum in the replay; a real price model for everyone below the star tier is still
  the next free-agency task.
- **Restricted free agency** is approximated (young starters kept), not modelled: no offer sheets, no matching.
- **Player mood** does not enter the AI re-signing decision: the team decides, and the player agrees at his market
  price. Unhappy stars forcing their way out is not modelled.
- Hard-cap triggers (using the mid-level or a sign-and-trade) are not tracked; the game keeps its single hard cap for
  trades and outside signings, and Bird re-signings are exempt from it.

## Files
- `cap_rules.py`: Bird levels, salary limits, years and raises.
- `contract_ai.py`: the Bird clock (`opening_bird_since`, `bird_clock_since`, `keep_bird_clock`, `bird_rights`,
  `bird_rights_text`); contracts applied with the team holding his rights keep the clock.
- `save.py`: `annotate_star_asks` (Bird rights, rank, phase), `is_franchise_star`, `should_ai_retain_expiring_player`,
  `star_re_signing_years`, `ai_re_signing_contract_terms`, `ai_re_signing_fits_hard_cap`, the payroll call, Bird clock on
  AI re-signings and extensions.
- `payroll_plan.py`: `franchise_star` in `payroll_check`, `STAR_RETENTION_TAX_BUDGET`.
- `play.py`: `signing_cap_check(bird=...)`, `incumbent_bird_rights`, `drafted_by_team`, AI bids and acceptances with
  Bird rights, loyalty, the text re-signing room.
- `app_actions.py`: Bird rights on candidates, the five-year rule on offers.
- `gui/app.js`: the offer builder's cap check, years and slider follow Bird rights; the rights line.
- `transactions.py`, `trade_targets.py`: the re-trade hold.
- `scripts/expiring_star_outcomes.py` (new): where the top expiring players went, and for how much.
- `tests/test_keep_stars.py` (new, 12 tests).

## Resume state
- **Done**: code, tests, the 2028 replay, the two-season test with metrics, this report and the board row. All committed
  on the branch (last commit after 939b4ff adds the report and board). Not pushed or merged.
- **Local outputs** (git-ignored, in this worktree's `output/ks/`; copy to main's `output/` before removing the worktree
  if wanted): `probe/` (the two-season run with snapshots), `results/` (metrics, trade list, star outcomes),
  `replay1/` (2028 replay), `replay.py`, `debug_resign.py` (traces AI re-signing decisions), `look.py`, `retrades.py`,
  `payrolls.py`.
- **Worktree symlinks** (`.venv`, `data/research/barttorvik/raw`, the canonical database and injury file, ignored BBI
  files, `output/settlement-materialization-pass`, `output/tv2`) are untracked or ignored and were not committed.
