# Trade 2b: rebuild sales, tax savings, young starters, phase labels, draft-night prices (2026-11-19)

_Claude (Opus agent), branch `worktree-agent-a3655cd6755db5f27`. Follows `trade-step2-targets.md`; the five fixes the
user approved there._

(Report in progress.)

## Resume state
- Done: code for all five fixes (`trade_tax.py` new; `transactions.py`, `trade_targets.py`, `trade_ownership.py`,
  `team_planning.py`, `play.py`, `schema.py` one field), `tests/test_trade_2b.py` (22 tests), probe metrics extended
  (`scripts/trade_probe_metrics.py`) and a deadline phase snapshot in `scripts/two_season_league_probe.py`.
- Baseline probe (branch base, code copied to `output/trade2b/base_src`): `output/trade2b/base_inputs_v1/` (done).
- Next: focused tests, checkpoint commit, after-probe into `output/trade2b/after_inputs_v1/`, metrics, report.
