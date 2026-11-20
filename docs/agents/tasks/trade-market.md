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
- Baseline probe (branch start, frozen copy `output/trade-market/base-src`) started 17:41 with `--snapshots`;
  log `output/trade-market/base.log`, pid in `base.pid`, results in `base-src/output/probe`.
- Reputation research (sonnet subagent): `output/trade-market/fo_reputation_research.json` (30 teams, 20 sources,
  25 with a widely held finding).
- Next: front_office.py traits + personality terms replacing the per-proposal dice in
  `transactions.personality_trade_adjustment`.
