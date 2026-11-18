# Trade AI survey vs the user's framework (2026-11-19)

Read-only survey of the current AI trade system against `docs/agents/TRADE_AI_DIRECTION.md`. File references are to
`src/nba_gm_data/` at commit `7aaa672`; the evaluation counts are estimates from reading code (the deadline-speed
task measures the real numbers).

## How a trade happens today
1. Each sim day `queue_ai_recommendations` (save.py:5612) asks `trade_calendar.market_day` for a number of AI-to-AI
   trade slots (Poisson-like, mean rising to 15 on deadline day, capped at 24) and 0-4 offers to the human team.
2. `simulate_ai_trades` (transactions.py:818) takes the top 120 trade-block players by `trade_block_score`
   (points table: rebuilding team + age 29+ gives +42, bad contract +22, position surplus +12, ...), removes
   core-committed players, adds human wants and (deadline week) up to 2 random "private targets" per team.
3. For each target it ranks buyers by `team_fit_for_player` (keeps fit >= 3), tries 6 or 12 buyers, and for each
   buyer builds 1-3 player combos x pick variants (seconds, firsts, swaps, protections, new swap grants), keeps the
   5 or 12 closest to the target's value, and runs a full two-sided evaluation on each. The expensive part is the
   roster projection (two rotation simulations per evaluation).
4. Acceptance: every side's net value above its threshold, plus roster-plan and pick-investment gates. If that fails,
   "bounded discretion" can still approve (each side's net >= -9 and the sum >= -2).
5. Greedy pick of non-conflicting accepted trades up to the day's slots, then `apply_trade_to_state`.
   Ceiling estimate: 120 targets x 12 buyers x 12 packages ~ 17,000 evaluations on a deadline-week day.

## The three layers today
**Value.** One number per player, the same for every team: on-court value + age curve + development + contract
surplus (scaled by quality) + role scarcity + playoff value - health risk, then star/rookie floors and the market
shape (transactions.py:332, 2846, 2913). Picks: slot tables, a flat -1.18 per year of distance, x1.18 for
rebuilders and x0.88 for contenders, protections, ranked-pool Monte Carlo (:5304, :5222). Swaps have a fixed
optionality value.

**Context.**
- Fit: a hand-tuned points table on phase, age and team needs (`team_fit_for_player` :4681, `team_needs_and_excesses`
  :4569), the same number on both sides; the giving team's loss is only indirect.
- Role: destination rank -> expected minutes -> value multiplier (:4824, :4879); roster before/after projection
  (`trade_roster.py`) blocks contenders from weakening themselves.
- Succession: only for premium players (credible young return); no "who takes his minutes" for ordinary players.
- Tenure: essentially absent (recently-traded 60-day block, a one-year core commitment after big acquisitions, a
  +5..+16 premium for players acquired 60-180 days ago).
- Team phase: `window_assessments` (team_planning.py:13) peak / entering / exiting / rebuilding, core plans,
  retool candidates.
- Investment: only pick spending (`pick_investment_outlook`, trade_roster.py:119). Nothing records "traded up to draft
  him" or "recent first-round pick"; the Clifford case is not caught.
- Cap/tax: legality and salary posture; little "save the tax" motive.
- Wants (`trade_wants.py`): the closest thing to need-driven search, but only ordering plus a credit of at most 4.

**Front-office personality.** Profiles exist (competence, patience, risk tolerance, aggressiveness, asset discipline,
star chasing, ...; hash-based around ~56-58 plus research keywords), but the trade effect is a seeded +/-8 adjustment
and a threshold shift. Difficulty (`AI_DIFFICULTIES`) is not used in trades, `max_bad_gm_overpay` is unused,
the `gm_modifier` ledger line is always 0, and there are no player-specific opinions.

**Explanations.** Each evaluation records values, a component breakdown, decision and reason strings, phase, fit and
personality. Not recorded: the motive (why the seller listed him, the buyer's need), the successor, or the
alternatives considered.

## Biggest gaps (ranked)
1. No "does each team have a reason" step before evaluation: brute-force value matching, then discretion lets
   near-fair deals through on value alone. Source of both the volume and the odd trades.
2. Investment and tenure missing (draft trade-ups, recent firsts, recent signings, years with the team).
3. Succession and role change only for premium players.
4. Personality thin and partly cosmetic (difficulty unused, no player opinions, savvy affects only noise/threshold).
5. Team-agnostic value apart from fit points; flat pick multipliers.
6. Search not need-driven (wants only reorder).
7. Trade records store verdicts, not motives or alternatives.
8. Pick valuation not calibrated to real 2025-27 prices.
