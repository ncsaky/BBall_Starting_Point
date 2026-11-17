"""Prepare disposable browser fixtures without touching the playable career."""
import json
from pathlib import Path
from nba_gm_data.save_recovery import create_export, restore_export

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'output/live-simulation-2026-10-24'


def main():
    directory = OUT / 'saves'
    directory.mkdir(parents=True,exist_ok=True)
    sources = {
        'playoffs':next((ROOT/'output/playoff-bracket-flow-2026-10-24/saves').glob('memphis-unplayed-*.json')),
        'completed':next((ROOT/'output/postseason-calendar-2026-10-24/saves').glob('menu-modes-*.json')),
        'regular':ROOT/'output/memphis-rotation-fix-2026-10-24/controlled-input.nbagm.zip',
    }
    for name, source in sources.items():
        target = directory / f'{name}.json'
        if target.exists():
            print(f'{name}: existing verification fixture retained',flush=True)
            continue
        archive = source.read_bytes() if source.suffix=='.zip' else create_export(source)
        restore_export(target,archive)
        print(f'{name}: {target}',flush=True)
    (OUT/'fixtures.json').write_text(json.dumps({name:str(directory/f'{name}.json') for name in sources},indent=2))


if __name__=='__main__':
    main()
