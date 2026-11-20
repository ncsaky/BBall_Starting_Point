# Trade market: front-office personality, negotiations, shopping, bidding wars (TRADE-MARKET)

_Claude (Opus agent), branch `worktree-agent-a8b7bf33bc84c43b3` (from 02ee3d1). Status: **in progress**._

## Objective
Plan: `trade-market-personality-plan.md` (user decisions there). Volume from personality and the market, never by
loosening the textbook acceptance rules. Every personality effect bounded, explained, stated in the trade's reasons;
no dice.

## Boundaries
Files: `front_office.py` (new), `trade_market.py` (new), `transactions.py` (personality term, market hooks),
`trade_targets.py`, `trade_counters.py`, `trade_roster.py` (pick allowance by urgency), `save.py` (market hooks,
traits in the save), `app_actions.py` (market board, hints, final offers), `gui/app.js`, `gui/assistant-phone.js`,
CSS, `data/overrides/front_office_overrides.json` (new `trade_personality` section), tests,
`scripts/trade_probe_metrics.py`.

## Resume state
- Baseline probe done (`output/trade-market/base-src/output/probe`; metrics `output/trade-market/results/trade_metrics_base.json`):
  101 trades, deadline weeks 22 / 21.
- WIP committed 376b6e8 (engine, user side, GUI, tests `tests/test_trade_market.py` 27 OK).
- Probe run1 (frozen copy `output/trade-market/run1-src`, log `run1.log`, pid `run1.pid`) started after the commit.
- Iteration harness: `output/trade-market/advance_eval.py SNAP OUT DATE --daily` on `snaps/dl2027` (2027-01-21);
  `refusals.py SAVE DATE` (one day, no slot limit, why deals fail); `grades.py`, `show_summary.py`, `market_days.py`.
- Findings so far: before deadline day the slot draw binds; on deadline day the supply bound. Deadline-day final
  offers (every motivated side concedes by patience) filled the day; calendar's last two days set to real 2026 (5, 18).
- Next: run1 metrics, hand-read trades, full test suites, GUI screenshots, scorecard, report.
