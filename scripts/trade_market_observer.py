"""Audit-only observers around unchanged production transaction application."""
from contextlib import ExitStack
from copy import deepcopy
import json
import gzip
from pathlib import Path
from unittest.mock import patch

from nba_gm_data import transactions as tx, play
from nba_gm_data.app_actions import load_app_canonical
from nba_gm_data.save import canonical_with_save, player_display_attribute_summary, team_cap_summary


def context_snapshot(canonical, saved, team_ids, assets):
    # Normalization may seed missing rotation fields; never let observation
    # change the authoritative save or canonical input.
    active = tx.with_transaction_context(canonical_with_save(canonical, deepcopy(saved)))
    states = {s['team_id']: s for s in active.get('team_strategic_states', [])}
    values = {v['player_id']: v for v in active.get('player_asset_valuations', [])}
    players = {p['id']: p for p in active.get('players', [])}
    contracts = {c['player_id']: c for c in active.get('contracts', [])}
    neutral = {'meta': dict(active.get('meta') or {}), '_allow_internal_caches': True,
               'players': [dict(p, minutes_projection=24) for p in active.get('players', [])],
               'traits': active.get('traits', [])}
    season = play.contract_start_season_for_signing(saved)
    teams = {}
    for tid in team_ids:
        state = states.get(tid, {})
        plan = saved.get('team_plans', {}).get(tid, {})
        roster = [p for p in players.values() if p.get('team_id') == tid and not p.get('_inactive_player')]
        top = sorted(roster, key=lambda p: (-float(values.get(p['id'], {}).get('on_court_value') or 0), p['id']))[:8]
        cap = team_cap_summary(active, saved, tid, season=season)
        teams[tid] = {'abbrev': next((t['abbrev'] for t in active.get('teams', []) if t['id'] == tid), tid),
            'window_phase': state.get('window_phase'), 'route': plan.get('route'),
            'league_rank': state.get('league_rank'), 'contention_strength': state.get('contention_ceiling'),
            'window_trend': state.get('window_trend'), 'core_age': state.get('core_age'),
            'youth_pipeline': state.get('youth_pipeline'), 'needs': state.get('needs'),
            'excesses': state.get('excesses'), 'core_ids': plan.get('core_ids', []),
            'owned_core_ids': [pid for pid in plan.get('core_ids', []) if players.get(pid, {}).get('team_id') == tid],
            'commit_until': plan.get('commit_until'), 'review_exception': plan.get('review_exception'),
            'roster_count': len(roster), 'top8_quality': round(sum(float(values.get(p['id'], {}).get('on_court_value') or 0) for p in top), 3),
            'payroll_millions': cap['salary_total_millions'], 'dead_salary_millions': cap['waived_salary_millions'],
            'financial_season': season}
    details = []
    for asset in assets:
        if asset.get('kind') != 'player':
            details.append(deepcopy(asset))
            continue
        pid = asset['id']
        player, value = players.get(pid, {}), values.get(pid, {})
        contract = contracts.get(pid, {})
        remaining = [deepcopy(r) for r in contract.get('seasons', []) if r['season'] >= season]
        details.append({'kind': 'player', 'id': pid, 'name': player.get('name', asset.get('label', pid)),
            'team_id': player.get('team_id'), 'age': player.get('display_age', player.get('age')),
            'position': player.get('position'), 'minutes': player.get('minutes_projection'),
            'overall': player_display_attribute_summary(active, pid).get('overall'),
            'neutral_role_overall': player_display_attribute_summary(neutral, pid).get('overall'),
            'on_court_value': value.get('on_court_value'), 'player_value': value.get('player_value'),
            'contract_surplus': value.get('contract_surplus'), 'upside': value.get('development_upside'),
            'remaining_contract': remaining,
            'remaining_salary_millions': round(sum(float(r.get('salary') or 0) for r in remaining)/1e6, 3)})
    return {'date': saved.get('state', {}).get('current_date'), 'teams': teams, 'assets': details}


def classify_trade(before, after, candidate):
    players = [a for a in before['assets'] if a.get('kind') == 'player']
    peak = max((float(p.get('neutral_role_overall') or 0) for p in players), default=0)
    kind = 'picks_only' if not players else 'star' if peak >= 90 else 'starter' if peak >= 80 else 'rotation_or_depth'
    context = candidate.get('free_agency_context') or {}
    dump_teams = []
    for tid, team in before['teams'].items():
        new = after['teams'][tid]
        expensive_departure = any(a.get('team_id') == tid and float(a.get('contract_surplus') or 0) < 0 for a in players)
        if team['payroll_millions']-new['payroll_millions'] >= 5 and expensive_departure:
            dump_teams.append(tid)
    return {'quality_class': kind, 'salary_dump_candidate_teams': dump_teams,
            'explicit_market_context': deepcopy(context), 'max_neutral_overall': peak}


class MarketObserver:
    def __init__(self, root, output, capture_players=()):
        self.root, self.output = Path(root), Path(output)
        self.stack = ExitStack()
        self.canonical = None
        self.original = tx.apply_trade_to_state
        self.path = self.output/'market-events.jsonl'
        self.capture_players = set(capture_players)

    def __enter__(self):
        self.output.mkdir(parents=True, exist_ok=True)
        self.stack.enter_context(patch.object(tx, 'apply_trade_to_state', self.apply))
        self.stack.enter_context(patch.object(play, 'apply_trade_to_state', self.apply))
        return self

    def __exit__(self, *args):
        return self.stack.__exit__(*args)

    def write(self, record):
        with self.path.open('a') as handle:
            handle.write(json.dumps(record, sort_keys=True)+'\n')

    def apply(self, saved, proposal_id, *args, **kwargs):
        candidate = next((r for r in saved.get('pending_trade_proposals', [])
                          if (r.get('proposal') or r).get('id') == proposal_id), None)
        if not candidate:
            return self.original(saved, proposal_id, *args, **kwargs)
        proposal = candidate.get('proposal') or candidate
        parties = tx.trade_team_ids(proposal)
        assets = tx.trade_assets(proposal)
        canonical = kwargs.get('canonical')
        if canonical is None:
            if self.canonical is None:
                self.canonical = load_app_canonical(self.root)
            canonical = self.canonical
        before = context_snapshot(canonical, saved, parties, assets)
        phase = saved.get('state', {}).get('phase')
        # Capture metadata before production consumes the pending proposal.
        original_candidate = deepcopy(candidate)
        frozen = None
        if proposal.get('transfers') or self.capture_players.intersection(a.get('id') for a in assets if a.get('kind') == 'player'):
            frozen = tx.with_transaction_context(canonical_with_save(canonical, deepcopy(saved)))
            frozen = {k: v for k, v in frozen.items() if not k.startswith('_')
                      or k in {'_strategy_model_version', '_human_team_ids'}}
        result = self.original(saved, proposal_id, *args, **kwargs)
        if result.get('status') == 'applied':
            after = context_snapshot(canonical, saved, parties, assets)
            self.write({'kind': 'trade', 'proposal_id': proposal_id, 'phase': phase,
                        'date': kwargs.get('date') or proposal.get('date') or saved.get('state', {}).get('current_date'),
                        'proposal': deepcopy(proposal), 'evaluations': original_candidate.get('evaluations', []),
                        'classification': classify_trade(before, after, original_candidate),
                        'before': before, 'after': after})
            if frozen is not None:
                import hashlib
                name = 'context-'+hashlib.sha256(proposal_id.encode()).hexdigest()[:16]+'.json.gz'
                with gzip.open(self.output/name, 'wt') as handle:
                    json.dump({'canonical': frozen, 'candidate': original_candidate,
                               'date': saved.get('state', {}).get('current_date')}, handle)
                self.write({'kind': 'frozen_context', 'proposal_id': proposal_id, 'file': name})
        else:
            self.write({'kind': 'trade_application_rejected', 'proposal_id': proposal_id,
                        'date': saved.get('state', {}).get('current_date'), 'result': result})
        return result
