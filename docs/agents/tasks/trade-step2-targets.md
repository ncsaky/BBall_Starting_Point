# Trade AI step 2: targets, willing sellers, offers at the seller's price (2026-11-19)

_Claude (Opus agent), branch `worktree-agent-a27f380f5f89a462b`. Step 3 of the order of work in
`docs/agents/TRADE_AI_DIRECTION.md`; follows `trade-step1-own-value.md`._

## Resume state
- Worktree data symlinked (.venv, bbi files, barttorvik raw, sqlite universe, injury evidence, settlement pass).
- Code done: `trade_targets.py` (new), `transactions.py` (target search, seller-view builder, pick bonus, log
  reasons), `trade_ownership.py` (tax / expiring reasons), `play.py` (draft both-sides), `save.py` (search limit),
  `trade_wants.py`, config override; tests `tests/test_trade_targets.py` (18) + 2 adapted test files.
- Probes running (started ~11:40): `output/probe/{inputs_v1,legacy_traits}` (this branch) and
  `output/base_tree/output/probe/inputs_v1` (HEAD copy, paired CPU baseline). Do not edit `trade_targets.py` until
  they finish (lazily imported). Then: `scripts/trade_probe_metrics.py` on each, write the report, board row, commit.
