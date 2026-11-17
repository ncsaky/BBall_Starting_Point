"""Bounded reuse owned by one synchronous, immutable market review."""
from collections import Counter
import hashlib
import json


class MarketReview:
    """Revalidate source inputs at each search boundary; never reuse at settlement."""
    def __init__(self):
        self.signature = None
        self.active = None
        self.stats = Counter()

    def prepare(self, source, config=None):
        from . import transactions as tx
        # Include all public state, plus private planning and control inputs.
        # Derived memo tables are deliberately excluded. The digest retains no
        # career graph, and also detects in-place edits between the two searches.
        inputs = {k: v for k, v in source.items() if not k.startswith('_') or
                  k in ('_human_team_ids', '_trade_planning_save', '_strategy_model_version')}
        signature = hashlib.sha256(json.dumps([inputs, config], sort_keys=True,
                                              separators=(',', ':')).encode()).digest()
        if self.active is not None and signature == self.signature:
            self.stats['context_hits'] += 1
            return self.active
        if self.active is not None:
            self.stats['invalidations'] += 1
            # A caller changed authoritative state without regenerating derived
            # context. Rebuild indexes and strategic baselines as well as memos.
            source = {k: v for k, v in source.items() if not k.startswith('_') or
                      k in ('_human_team_ids', '_trade_planning_save')}
            source = {k: v for k, v in source.items() if k not in
                      ('team_strategic_states', 'player_asset_valuations', 'trade_block_entries')}
        self.signature = signature
        self.active = tx.trade_search_context(tx.with_spatial_fit_context(tx.with_transaction_context(source, config)))
        self.active['_trade_search_pick_previews'] = {}
        self.active['_market_review_stats'] = self.stats
        self.stats['context_builds'] += 1
        return self.active

    def close(self):
        self.active = None
        self.signature = None
