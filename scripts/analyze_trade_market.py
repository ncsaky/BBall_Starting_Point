"""Join trade-time observations to durable history and explain team directions."""
import argparse
from collections import Counter
import json
from pathlib import Path

from nba_gm_data.history_store import load_history_records
from nba_gm_data.save import load_save


def all_logs(path, saved):
    rows = {r['id']: r for r in load_history_records(path, saved, 'transaction_logs')}
    rows.update({r['id']: r for r in saved.get('transaction_logs', [])})
    return sorted(rows.values(), key=lambda r: (r.get('date', ''), r['id']))


def direction(event, tid):
    old, new = event['before']['teams'][tid], event['after']['teams'][tid]
    proposal = event['proposal']
    from nba_gm_data.transactions import trade_team_flows
    _, outgoing, incoming = next(row for row in trade_team_flows(proposal) if row[0] == tid)
    sent = {r['id'] for r in outgoing if r['kind'] == 'player'}
    received = {r['id'] for r in incoming if r['kind'] == 'player'}
    details = {r['id']: r for r in event['before']['assets'] if r['kind'] == 'player'}
    picks = sum(r['kind'] in {'pick', 'pick_swap'} for r in incoming)-sum(r['kind'] in {'pick', 'pick_swap'} for r in outgoing)
    current = round(float(new.get('contention_strength') or 0)-float(old.get('contention_strength') or 0), 3)
    depth = round(float(new.get('top8_quality') or 0)-float(old.get('top8_quality') or 0), 3)
    payroll = round(float(new['payroll_millions'])-float(old['payroll_millions']), 3)
    youth = round(float(new.get('youth_pipeline') or 0)-float(old.get('youth_pipeline') or 0), 3)
    evaluation = next((r for r in event.get('evaluations', []) if r.get('perspective_team_id') == tid), {})
    loss, outgoing_value = float(evaluation.get('net_value') or 0), float(evaluation.get('outgoing_value') or 0)
    flags = []
    reasons = []
    if current > .05 or depth > 1:
        reasons.append('improves_current_team')
    if youth > .1 or picks > 0:
        reasons.append('adds_future_assets_or_youth')
    if payroll <= -5:
        reasons.append('creates_material_salary_room')
    if old.get('window_phase') == 'peak' and current < -.2 and not reasons:
        flags.append('contender_weakens_without_measured_future_or_financial_gain')
    if (evaluation.get('decision') == 'accept_bounded_ai_discretion'
            and loss < -1 and outgoing_value > 0 and -loss/outgoing_value > .25):
        flags.append('discretion_accepts_loss_over_quarter_of_outgoing_team_value')
    core_sent = sent & set(old.get('owned_core_ids', []))
    if core_sent and event['date'] <= (old.get('commit_until') or '') and not old.get('review_exception') and loss < max(12, outgoing_value*.2):
        flags.append('core_trial_broken_without_exceptional_return')
    return {'team': old['abbrev'], 'phase_before': old.get('window_phase'), 'phase_after': new.get('window_phase'),
            'stated_route': old.get('route'), 'league_rank_before': old.get('league_rank'), 'league_rank_after': new.get('league_rank'),
            'strength_delta': current, 'top8_delta': depth, 'youth_delta': youth, 'payroll_delta_millions': payroll,
            'net_pick_rights': picks, 'net_evaluation': loss, 'outgoing_team_value': outgoing_value,
            'core_sent': sorted(core_sent), 'measured_effects': reasons, 'review_flags': flags,
            'sent': [details[p] for p in sorted(sent)], 'received': [details[p] for p in sorted(received)]}


def release_destination(entry, wire, logs):
    # A later release overwrites the per-player pool entry. Match the first
    # durable signing in this waiver spell instead of that mutable summary.
    if entry['status'] != 'cleared':
        return {}
    later = [r['date'] for r in wire if r['player_id'] == entry['player_id'] and r['date'] > entry['date']]
    end = min(later, default='9999-12-31')
    signed = [r for r in logs if r.get('transaction_type') in {'free_agency', 'free_agent_signing', 'ai_free_agent_signing'}
              and r.get('assets', {}).get('player_id') == entry['player_id']
              and entry['clearance_date'] <= r.get('date', '') < end and r.get('teams')]
    if not signed:
        return {}
    first = min(signed, key=lambda r: (r['date'], r['id']))
    return {'signed_team': first['teams'][0], 'signed_date': first['date']}


def analyze(directory, year):
    directory = Path(directory)
    report = json.loads((directory/'trade-year.json').read_text())
    path = directory/'saves/trade_year.json'
    saved = load_save(path)
    logs = all_logs(path, saved)
    durable = {r.get('proposal_id'): r for r in logs if r.get('transaction_type') == 'trade'}
    events = [json.loads(s) for s in (directory/'market-events.jsonl').read_text().splitlines()]
    # A request-local observation isn't a committed trade until it appears in
    # the revision-validated durable ledger. Deduplicate retries by proposal ID.
    joined = {r['proposal_id']: r for r in events if r.get('kind') == 'trade' and r['proposal_id'] in durable
              and r.get('date', '').startswith(str(year))}
    trades = []
    for event in joined.values():
        players = [r for r in event['before']['assets'] if r['kind'] == 'player']
        peak = max((float(r.get('overall') or 0) for r in players), default=0)
        label = 'pick_only' if not players else 'star_90_plus' if peak >= 90 else 'starter_80s' if peak >= 80 else 'rotation_or_depth'
        trades.append({'date': event['date'], 'proposal_id': event['proposal_id'], 'phase': event['phase'],
            'quality_class': label, 'players': players, 'context': event['classification']['explicit_market_context'],
            'salary_relief_candidates': event['classification']['salary_dump_candidate_teams'],
            'teams': [direction(event, tid) for tid in event['before']['teams']]})
    pursuits = []
    for trade in trades:
        context = trade['context']
        if context.get('kind') not in {'roster_space_sale', 'cap_dump'}:
            continue
        target = context.get('target') or {}
        prior = next((o for o in saved.get('free_agent_offers', []) if o.get('id') == context.get('offer_id')), {})
        pid, tid = target.get('player_id') or context.get('player_id'), target.get('team_id') or prior.get('team_id')
        bids = [o for o in saved.get('free_agent_offers', []) if o.get('player_id') == pid and o.get('team_id') == tid
                and str(o.get('created_date') or '').startswith(str(year))]
        signed = [r for r in logs if r.get('transaction_type') in {'free_agency', 'free_agent_signing', 'ai_free_agent_signing'}
                  and r.get('assets', {}).get('player_id') == pid and tid in r.get('teams', [])
                  and trade['date'] <= r.get('date', '') <= f'{year}-09-01']
        pursuits.append({'proposal_id': trade['proposal_id'], 'date': trade['date'], 'target_player_id': pid, 'team_id': tid,
                         'bid_statuses': [o['status'] for o in bids],
                         'signed_dates': [r['date'] for r in signed],
                         'outcome': 'signed_target' if signed else 'pursued_without_signing' if bids else 'no_recorded_bid'})
    debts = {r['id']: r for r in saved.get('waived_salary_obligations', [])}
    releases = []
    for entry in saved.get('waiver_wire', []):
        if not entry['date'].startswith(str(year)):
            continue
        debt = debts.get(entry['id'], {})
        signed = release_destination(entry, saved.get('waiver_wire', []), logs)
        releases.append({'player': entry.get('player_name'), 'player_id': entry['player_id'],
            'date': entry['date'], 'waived_by': entry['team_id'], 'status': entry['status'],
            'clearance_date': entry['clearance_date'], 'claimed_by': entry.get('claimed_by_team_id'),
            'buyout': bool(entry.get('buyout')), 'signed_team': signed.get('signed_team'),
            'signed_date': signed.get('signed_date'),
            'cap_schedule': debt.get('seasons'), 'relief_status': debt.get('relief_status'),
            'stretch': debt.get('stretch'),
            'buyout_concession_millions': (entry.get('buyout') or {}).get('savings_millions')})
    annual = [r for r in durable.values() if r.get('date', '').startswith(str(year))]
    offers = [r for r in report.get('all_offers', []) if (r.get('offer_context') or {}).get('created_date', '').startswith(str(year))]
    by_month = lambda rows: dict(sorted(Counter(r['date'][:7] for r in rows).items()))
    return {'seed': report['seed'], 'date': report['date'], 'run_status': report.get('status'),
            'engine_unchanged': report.get('engine_unchanged'), 'seconds': report.get('seconds'),
            'year': year, 'annual_trades': len(annual), 'observed_trades': len(trades),
            'monthly_trades': by_month(annual), 'quality_counts': dict(Counter(r['quality_class'] for r in trades)),
            'monthly_player_trades': by_month([r for r in trades if r['quality_class'] != 'pick_only']),
            'monthly_pick_trades': by_month([r for r in trades if r['quality_class'] == 'pick_only']),
            'monthly_offers': dict(sorted(Counter(r['offer_context']['created_date'][:7] for r in offers).items())),
            'phase_routes': dict(Counter(f"{t['phase_before']}:{t['stated_route']}" for r in trades for t in r['teams'])),
            'phase_transitions': dict(Counter(f"{t['phase_before']}->{t['phase_after']}" for r in trades for t in r['teams'])),
            'review_flags': dict(Counter(flag for r in trades for t in r['teams'] for flag in t['review_flags'])),
            'trades': sorted(trades, key=lambda r: (r['date'], r['proposal_id'])), 'releases': releases,
            'free_agency_pursuits': pursuits,
            'limits': ['Window labels are relative roster assessments, not measured championship probabilities.',
                       'Quality tiers use the actual trade-time displayed OVR; neutral-role ratings are retained separately.',
                       'Salary relief is a flag, not proof of a salary-dump motive. Future pick rights are not valued simply by their count.',
                       'Monthly player/pick and phase detail counts require a matching committed observer record.']}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('directories', type=Path, nargs='+')
    parser.add_argument('--year', type=int, default=2027)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    result = {'runs': [analyze(p, args.year) for p in args.directories]}
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2)+'\n')
    print(json.dumps([{k: v for k, v in r.items() if k not in {'trades', 'releases', 'limits', 'free_agency_pursuits'}} for r in result['runs']], indent=2))


if __name__ == '__main__':
    main()
