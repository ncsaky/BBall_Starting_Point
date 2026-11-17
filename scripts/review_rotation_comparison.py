"""Read-only cohort review of the bounded imported-profile comparison."""
from collections import defaultdict
import argparse
import gzip
import hashlib
import json
from pathlib import Path
import statistics

from nba_gm_data.save import presentation_rating_value
from ten_season_soak import distribution
from audit_replacement_calibration import profile_rows

ROOT = Path(__file__).resolve().parents[1]
BATCH = Path.home()/'.cache/nba-gm-audits/rotation-profiles-v8-2026-10-26'
OUT = ROOT/'output/rotation-profiles-v8-2026-10-26'


def read(path):
    with gzip.open(path,'rt') as handle:
        return json.load(handle)


def sha(path):
    with path.open('rb') as handle:
        return hashlib.file_digest(handle,'sha256').hexdigest()


def value(row):
    return presentation_rating_value(row['fixed24_engine'])


def roster_metrics(snapshot, baseline_ids):
    rows = [p for p in snapshot['players'] if p['rostered']]
    ages = defaultdict(list)
    for p in rows:
        ages[str(int(float(p.get('age') or 0)))].append(value(p))
    return {'date':snapshot['date'],'count':len(rows),'fixed24_overall':distribution(value(p) for p in rows),
            'by_age':{a:distribution(v) for a,v in sorted(ages.items(),key=lambda item:int(item[0]))},
            'imported_count':sum(p['id'] in baseline_ids for p in rows),
            'generated_count':sum(p['id'] not in baseline_ids for p in rows),
            'over_90':sum(value(p)>=90 for p in rows),
            'roster_counts':snapshot['roster_counts_by_team'],
            'retired_count':snapshot['retired_count'],'league_exit_count':snapshot['league_exit_count']}


def retained_cohort(start, end, cohort):
    initial = {p['id']:p for p in start['players'] if p['id'] in cohort and p['rostered']}
    final = {p['id']:p for p in end['players'] if p['rostered']}
    common = initial.keys() & final.keys()
    return {'initial_count':len(initial),'retained_count':len(common),
            'retained_fraction':round(len(common)/len(initial),4) if initial else None,
            'initial_ids':sorted(initial),'retained_ids':sorted(common),
            'retained_names':sorted(final[pid]['name'] for pid in common),
            'lost_names':sorted(initial[pid]['name'] for pid in initial.keys()-final.keys()),
            'continuing_player_fixed24_change':distribution(value(final[p])-value(initial[p]) for p in common)}


def floor_decomposition(start, end):
    a = {p['id']:value(p) for p in start['players'] if p['rostered']}
    b = {p['id']:value(p) for p in end['players'] if p['rostered']}
    common = a.keys() & b.keys()
    total = statistics.fmean(b.values())-statistics.fmean(a.values()) if a and b else 0
    growth = sum(b[p]-a[p] for p in common)/len(b) if b else 0
    return {'mean_change':round(total,4),'continuing_player_rating_component':round(growth,4),
            'composition_residual':round(total-growth,4),'entry_count':len(b.keys()-a.keys()),
            'departure_count':len(a.keys()-b.keys()),
            'note':'Exact mean identity; composition residual includes entry/exit mix and changing roster size. Not a causal decomposition of p10.'}


def draft_band(pick):
    return '1-3' if pick<=3 else '4-14' if pick<=14 else '15-30' if pick<=30 else '31+'


def season_metrics(snapshot, history, metadata, baseline_ids, cohort):
    stats = history['player_season_stats']
    ratings = {p['id']:p for p in snapshot['players']}
    groups = defaultdict(list)
    unknown = []
    for pid,s in stats.items():
        if not s.get('games'):
            continue
        p = metadata.get(pid)
        if not p:
            unknown.append(pid)
            continue
        games, minutes = int(s['games']), float(s['minutes'])
        entry = {'id':pid,'name':s.get('player_name',p['name']),'games':games,'minutes':minutes,
                 'mpg':minutes/games,'qualifying_rotation':games>=20 and minutes/games>=16,
                 'fixed24':value(ratings[pid]) if pid in ratings else None}
        groups['all'].append(entry)
        groups['imported' if pid in baseline_ids else 'generated'].append(entry)
        if pid in cohort:
            groups['corrected_profiles'].append(entry)
        if pid not in baseline_ids:
            pick = int(p.get('overall_pick') or p.get('draft_position') or 60)
            groups['generated_'+draft_band(pick)].append(entry)
    total_minutes = sum(p['minutes'] for p in groups['all'])
    result = {}
    for key,rows in groups.items():
        result[key] = {'players_with_games':len(rows),'qualifying_rotation_count':sum(p['qualifying_rotation'] for p in rows),
                       'players_missing_end_rating':sum(p['fixed24'] is None for p in rows),
                       'minutes':round(sum(p['minutes'] for p in rows),2),
                       'share_of_league_minutes':round(sum(p['minutes'] for p in rows)/total_minutes,5) if total_minutes else 0,
                       'rotation_quality':distribution(p['fixed24'] for p in rows if p['qualifying_rotation'] and p['fixed24'] is not None)}
    return {'season':history['season'],'snapshot_date':snapshot['date'],'league_games':snapshot['regular_games'],
            'groups':result,'unknown_player_metadata':unknown}


def career(batch, arm, seed, cohort):
    root = batch/'runtime'
    out = root/f'output/comparison/{arm}'
    canonical = read(out/'canonical.json.gz')
    directory = out/f'career-{seed}'
    run = json.loads((directory/'run.json').read_text())
    assert run['status']=='completed' and run['endpoint']=='2028-10-01' and run['complete_seasons']==2
    path = Path(run['save_path'])
    assert path.resolve().is_relative_to(directory.resolve())
    saved = json.loads(path.read_text())
    assert len(saved['season_history'])==2
    snapshots = [read(p) for p in sorted((directory/'observations').glob('*.json.gz'))]
    start = next(s for s in snapshots if s['date']=='2026-10-01')
    end = snapshots[-1]
    assert end['date']=='2028-10-01'
    base = {p['id'] for p in canonical['players']}
    metadata = {p['id']:p for p in [*canonical['players'],*saved['generated_players']]}
    seasons = []
    for history in saved['season_history']:
        final = next(s for s in snapshots if s['season']==history['season'] and s['regular_games']==1230)
        assert len(history['team_records'])==30
        assert all(r['wins']+r['losses']==82 for r in history['team_records'].values())
        seasons.append(season_metrics(final,history,metadata,base,cohort))
    initially_weak = {p['id'] for p in start['players'] if p['rostered'] and p['id'] in base and value(p)<70}
    mature = {p['id'] for p in start['players'] if p['rostered'] and p['id'] in base and float(p.get('age') or 0)>=27}
    entry = defaultdict(list)
    generated = {p['id']:p for p in saved['generated_players']}
    for t in saved['generated_traits']:
        assert abs(t['value']-t['components']['career_capacity']['entry_value'])<.011
    entries = profile_rows({'meta':canonical['meta'],'players':saved['generated_players'],
                            'traits':saved['generated_traits']})
    for row in entries:
        entry[row['draft_year']].append(row)
    return {'baseline':roster_metrics(start,base),'endpoint':roster_metrics(end,base),'seasons':seasons,
            'corrected_profile_retention':retained_cohort(start,end,cohort),
            'initially_under70_retention':retained_cohort(start,end,initially_weak),
            'age27plus_retention':retained_cohort(start,end,mature),
            'mean_decomposition':floor_decomposition(start,end),
            'draft_entry_overall':{str(y):{'all':distribution(p['overall'] for p in rows),
                'by_pick':{band:distribution(p['overall'] for p in rows if draft_band(int(p['pick'] or 60))==band)
                           for band in ('1-3','4-14','15-30','31+')}} for y,rows in sorted(entry.items())},
            'generated_count':len(generated),'actions':len(run['actions']),
            'current_season_development_months':len(saved['applied_development_months']),
            'observed_development_months':sorted({m for s in snapshots for m in s.get('new_development_months',[])}),
            'save_sha256':sha(path), 'save_path':str(path)}


def main(batch):
    assert json.loads((batch/'status.json').read_text())['status']=='completed'
    manifest = json.loads((batch/'manifest.json').read_text())
    assert all(sha(batch/'runtime'/name)==v for name,v in manifest['source_hashes'].items())
    assert all(sha(Path(name))==v for name,v in manifest['protected_files'].items())
    cohort = {p['player_id'] for p in manifest['changes']}
    report = {'scope':manifest['scope'],'policy':manifest['policy'],'seasons':2,'cases':{},
              'limits':'Two paired seeds, shared initial 2027 draft class. Short transition evidence only; not proof of long-term equilibrium or causal attribution of individual corrections.'}
    for seed in manifest['seeds']:
        report['cases'][str(seed)] = {arm:career(batch,arm,seed,cohort) for arm in ('control','candidate')}
        case = report['cases'][str(seed)]
        shared = set(case['control']['corrected_profile_retention']['initial_ids']) & set(case['candidate']['corrected_profile_retention']['initial_ids'])
        for arm in ('control','candidate'):
            retained = set(case[arm]['corrected_profile_retention']['retained_ids']) & shared
            case[arm]['shared_initial_corrected_retention'] = {'initial_count':len(shared),'retained_count':len(retained),
                'fraction':round(len(retained)/len(shared),4) if shared else None}
    target = OUT/'two-season-review.json'
    assert not target.exists(), 'Preserve existing review'
    write_text = json.dumps(report,indent=2,sort_keys=True)+'\n'
    target.write_text(write_text)
    print(json.dumps({seed:{arm:{'floor_start':c['baseline']['fixed24_overall']['p10'],
             'floor_end':c['endpoint']['fixed24_overall']['p10'],
             'retained_corrected':c['corrected_profile_retention']['retained_count'],
             'initial_corrected':c['corrected_profile_retention']['initial_count']}
             for arm,c in case.items()} for seed,case in report['cases'].items()}),flush=True)


if __name__=='__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--batch',type=Path,default=BATCH)
    main(parser.parse_args().batch)
