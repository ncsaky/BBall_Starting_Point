# Bidding-war price floor and rare lower winners (BIDWAR-PRICE)

_Claude (Opus agent), branch `worktree-agent-a8228294602623cc8`. Status: **in progress**._

## Objective
User decision (2026-11-21): "The winner should pay at least what the second best bid was worth. Although sometimes it
might be interesting if a slightly lower offer wins. Not sure if that happens in real life... Could be interesting
every once in a while. But rarely."

1. Price floor: a bidding war's winner pays at least the second-best bid, in the seller's textbook value.
2. Rare lower winner: only for a stated, persistent, evidence-based seller reason; well under 1 in 5 wars; no dice.
3. The user's side: the trade window and the Trade Market board say why a bid won or lost, matching the engine.

## Boundaries
- May touch: `trade_market.py`, `trade_counters.py`, `front_office.py` (wording only), trade-window and board text in
  `gui/app.js`, tests, this file.
- Not: `transactions.py`, `save.py`, `play.py`, `offseason_decisions.py`, `offer_sheets.py`, `cap_ledger.py`,
  `health.py`, `injury_model.py`. Textbook acceptance rules unchanged.

## Resume state
- Baseline probe (HEAD 9e493aa + measurement-only price recording in war records): source copy
  `output/bidwar-price/base-src`, run `output/bidwar-price/base-src/output/probe` (with snapshots), log
  `output/bidwar-price/base.log`. Make a runnable copy with the scratch script `root_copy.sh <name>`
  (copies src and scripts, links everything else).
- Base run done (98 trades; 11 war days, 2 winners below the second-best price). Results:
  `output/bidwar-price/results/trade_metrics_base.json`, `output/bidwar-price/wars_base.json` (`analyze.py`).
- Final run: `output/bidwar-price/final-src/output/probe` (code at 8a7ca9f), log `output/bidwar-price/final.log`.
  Then: `analyze.py <probe> final`, `trade_probe_metrics.py --label final`, tests, scorecard, report.
- Snapshot tools: `output/bidwar-price/replay.py` (one market day's wars), `exercise_floor.py` (asset additions).
- Design: rounds and the floor use the seller's textbook price (its net minus its personality terms, minus its
  threshold). The seller's stated preferences decide only between bids, and a lower bid wins only within a slight gap.
