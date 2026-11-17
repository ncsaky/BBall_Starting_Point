"""Short replay checks and guarded publication after the bounded comparison."""
import argparse
from copy import deepcopy
import json
from pathlib import Path

from nba_gm_data.app_actions import dispatch_app_action
from nba_gm_data.ingest import build_universe
from nba_gm_data.save import load_save, set_save_date_phase, write_save
from nba_gm_data.save_recovery import create_export, restore_export
from nba_gm_data.schema import to_plain
from nba_gm_data.storage import write_outputs
from compare_rotation_profiles import BATCH, OUT, VERSION, sha, write, read_gzip
from verify_imported_skills import advance, START
from verify_simulation_consistency import differences, digest
from verify_roster_alignment import archive_candidate

ROOT = Path(__file__).resolve().parents[1]
RUNTIME = BATCH/'runtime'


def inputs():
    manifest = json.loads((BATCH/'manifest.json').read_text())
    assert all(sha(Path(p))==v for p,v in manifest['protected_files'].items())
    for name in ('draft.py','health.py','talent.py','save.py','sim.py','app_actions.py'):
        path = Path('src/nba_gm_data')/name
        assert sha(ROOT/path)==manifest['source_hashes'][str(path)], name
    candidate = json.loads((OUT/'candidate/universe_2026_27_offseason.json').read_text())
    return manifest,candidate


def fresh(canonical, directory, seed):
    created = dispatch_app_action('create_save',{'team':'GSW','seed':seed,'save_name':'verification'},
        root=RUNTIME,save_dir=directory,canonical=deepcopy(canonical))
    path = Path(created['save_path'])
    saved = load_save(path)
    assert saved['meta']['starting_data_version']==canonical['meta']['starting_data_version']
    set_save_date_phase(saved,START)
    write_save(path,saved)
    return create_export(path)


def smoke():
    import nba_gm_data
    assert Path(nba_gm_data.__file__).resolve().is_relative_to(RUNTIME), 'Run smoke with the frozen runtime src first on PYTHONPATH'
    manifest,candidate = inputs()
    directory = OUT/'smoke'
    directory.mkdir(exist_ok=False)
    report = {'cases':[]}
    for seed in (29,913):
        archive = fresh(candidate,directory/f'{seed}-source',seed)
        states = {}
        for mode in ('bulk','daily'):
            path = directory/f'{seed}-{mode}/career.json'
            restore_export(path,archive)
            state,metrics = advance(deepcopy(candidate),path,seed,mode,root=RUNTIME)
            states[mode] = state
            report['cases'].append({'seed':seed,'mode':mode,**metrics})
        assert not differences(states['bulk'],states['daily']), differences(states['bulk'],states['daily'])
    old = read_gzip(ROOT/'data/canonical/baselines/2026-10-26-imported-skills-v7.json.gz')
    archive = fresh(old,directory/'legacy-source',29)
    states = {}
    for label,canonical in (('original',old),('new-entry',candidate)):
        path = directory/f'legacy-{label}/career.json'
        restore_export(path,archive)
        state,metrics = advance(deepcopy(canonical),path,29,'bulk',root=RUNTIME)
        states[label] = state
        report['cases'].append({'legacy':label,**metrics})
    assert not differences(states['original'],states['new-entry']), differences(states['original'],states['new-entry'])
    report.update(status='passed',daily_bulk_both_seeds_identical=True,legacy_v7_identical=True,
                  legacy_digest=digest(states['original']),games_checked=sum(c['games'] for c in report['cases']))
    inputs()
    write(OUT/'smoke-verification.json',report)
    print(json.dumps({k:v for k,v in report.items() if k!='cases'}),flush=True)


def publish():
    manifest,candidate = inputs()
    assert json.loads((BATCH/'status.json').read_text())['status']=='completed'
    review = json.loads((OUT/'two-season-review.json').read_text())
    assert set(review['cases'])=={'29','913'} and review['seasons']==2
    smoke_report = json.loads((OUT/'smoke-verification.json').read_text())
    assert smoke_report['status']=='passed'
    universe = build_universe(ROOT)
    assert to_plain(universe)==candidate, 'Candidate changed since comparison'
    archive_candidate(candidate)
    registry_path = ROOT/'data/canonical/baselines/registry.json'
    registry = json.loads(registry_path.read_text())
    assert VERSION not in registry['versions'], 'Never replace a published version'
    registry['versions'][VERSION] = f'{VERSION}.json.gz'
    write(registry_path,registry)
    write_outputs(universe,ROOT/'data/canonical')
    inputs()
    assert read_gzip(ROOT/f'data/canonical/baselines/{VERSION}.json.gz')==candidate
    write(OUT/'publication.json',{'status':'published','version':VERSION,'protected_files_unchanged':True,
        'two_season_comparison_completed':True,'smoke_games':smoke_report['games_checked'],
        'scope':{'changed_players':len({c['player_id'] for c in manifest['changes']}),
                 'changed_traits':len(manifest['changes'])}})
    print(f'Published {VERSION}',flush=True)


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('mode',choices=('smoke','publish'))
    args=parser.parse_args()
    smoke() if args.mode=='smoke' else publish()
