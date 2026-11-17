"""Render reviewed franchise highlights and shared, real front-office scenes.

Each franchise has six reviewed plays from several games, in three two-play
chapters. Shared front-office scenes alternate with those chapters at playback.
The original Random-team montage is never rebuilt or replaced by this script.
"""
import argparse, concurrent.futures, json, subprocess, tempfile
from pathlib import Path
import numpy as np
from PIL import Image
from build_startup_video import DotPress, television_transition
ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / 'src/nba_gm_data/gui/assets/startup/video/teams'

def encode(path, frames, settings):
    partial = path.with_name(path.stem + '.rendering.mp4')
    encoder = subprocess.Popen([
        'ffmpeg', '-nostdin', '-v', 'error', '-y', '-f', 'rawvideo', '-pix_fmt', 'rgb24',
        '-s', f'{settings["width"]}x{settings["height"]}', '-r', str(settings['fps']),
        '-i', '-', '-an', '-c:v', 'libx264', '-preset', 'medium', '-crf', '28',
        '-pix_fmt', 'yuv420p', '-profile:v', 'high', '-level:v', '3.1', '-g', '60',
        '-movflags', '+faststart', '-threads', '2', str(partial)], stdin=subprocess.PIPE)
    try:
        for frame in frames: encoder.stdin.write(frame.tobytes())
    finally:
        encoder.stdin.close()
    if encoder.wait(): raise RuntimeError(f'Encode failed: {path}')
    partial.replace(path)

def decoded_frames(source, clip, settings):
    """Decode one frame at a time; never allocate a whole RGB clip in RAM."""
    width, height = settings['width'], settings['height']
    vf = (f"scale={width}:{height}:force_original_aspect_ratio=decrease,"
          f"pad={width}:{height}:(ow-iw)/2:(oh-ih)/2,setsar=1,fps={settings['fps']}")
    decoder = subprocess.Popen(['ffmpeg', '-nostdin', '-v', 'error', '-xerror',
        '-ss', str(clip['source_start']), '-i', str(source), '-frames:v', str(clip['frames']),
        '-an', '-vf', vf, '-pix_fmt', 'rgb24', '-threads', '1', '-f', 'rawvideo', '-'], stdout=subprocess.PIPE)
    try:
        size = width * height * 3
        for _ in range(clip['frames']):
            frame = decoder.stdout.read(size)
            if len(frame) != size: raise RuntimeError(f'Incomplete source decode: {source}')
            yield np.frombuffer(frame, np.uint8).reshape(height, width, 3)
        if decoder.wait(): raise RuntimeError(f'Source decode failed: {source}')
    finally:
        decoder.stdout.close()
        if decoder.poll() is None: decoder.terminate(); decoder.wait()

def pressed_frames(source, clip, settings, press):
    # Same isolated-flash detection as the original renderer, with scalar means
    # retained from pass one and just seven real frames buffered in pass two.
    means = np.array([frame.mean(dtype=np.float64) for frame in decoded_frames(source, clip, settings)])
    baseline = np.array([np.median(means[max(0, i-2):min(len(means), i+3)]) for i in range(len(means))])
    bad = set(np.where(means - baseline > 9)[0].tolist())
    replacements = {}
    for index in bad:
        candidates = [j for j in range(max(0, index-3), min(len(means), index+4)) if j not in bad]
        if not candidates: raise RuntimeError('Sustained source exposure spike needs editorial review')
        replacements[index] = min(candidates, key=lambda j: abs(j-index))
    source_frames = iter(decoded_frames(source, clip, settings)); buffer = {}; decoded = -1
    for index in range(clip['frames']):
        while decoded < min(clip['frames']-1, index+3):
            decoded += 1; buffer[decoded] = next(source_frames)
        yield press.render(buffer[replacements.get(index, index)], reset=index == 0)
        for old in [key for key in buffer if key < index-2]: del buffer[old]
    # Exhaust the generator to check the decoder's exit status and close its pipe.
    next(source_frames, None)

def render_shots(movie, shots, settings, seed, processed=False):
    if movie.exists(): return
    press = None if processed else DotPress(settings['width'], settings['height'], settings['halftone'])
    shoulder = settings['transition']['shoulder_frames']
    with tempfile.TemporaryDirectory(prefix='startup-reviewed-') as scratch:
        paths = []
        for index, clip in enumerate(shots):
            source = ROOT / clip['path']
            path = Path(scratch) / f'{index}.npy'
            printed = np.lib.format.open_memmap(path, mode='w+', dtype=np.uint8,
                shape=(clip['frames'], settings['height'], settings['width'], 3))
            stream = decoded_frames(source, clip, settings) if processed else pressed_frames(source, clip, settings, press)
            for frame_index, frame in enumerate(stream): printed[frame_index] = frame
            printed.flush(); paths.append(path)
            del printed
        effects = []
        for index, path in enumerate(paths):
            effects.append(television_transition(np.load(path, mmap_mode='r'), np.load(paths[(index + 1) % len(paths)], mmap_mode='r'), settings['transition'], seed + index)[:3])
        for index, path in enumerate(paths):
            printed = np.load(path, mmap_mode='r+')
            printed[-shoulder:] = effects[index][0]
            printed[:shoulder] = effects[(index - 1) % len(paths)][2]
            printed.flush()
            if index == 0:
                Image.fromarray(printed[min(60, len(printed)-1)]).save(movie.with_suffix('.jpg'), quality=87)
        def frames():
            for index, path in enumerate(paths):
                yield from np.load(path, mmap_mode='r')
                yield from effects[index][1]
        encode(movie, frames(), settings)

def front_office(settings):
    original = json.loads((OUTPUT.parent / 'manifest.json').read_text())
    identifiers = ['kings-draft-room-applause', 'nuggets-scout-interview', 'nuggets-draft-room']
    scenes = []
    for index, identifier in enumerate(identifiers):
        segment = next(row for row in original['segments'] if row['id'] == identifier)
        # Remove the old transition shoulders; no preceding team's picture enters a shared scene.
        clip = {'path': 'src/nba_gm_data/gui/assets/startup/video/front-office.mp4',
                'source_start': segment['montage_start'] + .5, 'frames': segment['frames'] - 30}
        movie = OUTPUT / f'office-v2-{index + 1}.mp4'
        render_shots(movie, [clip], settings, 700 + index * 5, processed=True)
        scenes.append({'src': f'/assets/startup/video/teams/{movie.name}',
                       'poster': f'/assets/startup/video/teams/{movie.with_suffix(".jpg").name}',
                       'kind': 'front-office', 'action': identifier, 'frames': clip['frames'] + 18})
    return scenes

def render_team(job):
    team, entry, settings, offices, ordinal = job
    playlist = []
    checkpoint = OUTPUT / f'{team}-v2.json'
    if checkpoint.exists():
        previous = json.loads(checkpoint.read_text())
        if previous.get('source') != entry['source'] or [(clip['source_start'], clip['frames']) for clip in previous.get('clips', [])] != [(clip['source_start'], clip['frames']) for clip in entry['clips']]:
            # An edited source/interval must not silently reuse an obsolete movie.
            archive = ROOT / 'output/startup-team-correction/replaced-exports'
            archive.mkdir(parents=True, exist_ok=True)
            for old in OUTPUT.glob(f'{team}-v2*'):
                old.replace(archive / old.name)
    if len(entry['clips']) != 6: raise ValueError(f'{team}: exactly six reviewed highlights required')
    if any(clip['team'] != team for clip in entry['clips']): raise ValueError(f'{team}: highlight tagged for another team')
    if len({clip['opponent'] for clip in entry['clips']}) < 3: raise ValueError(f'{team}: at least three opponents required')
    for part in range(3):
        clips = entry['clips'][part * 2:part * 2 + 2]
        movie = OUTPUT / f'{team}-v2-{part + 1}.mp4'
        render_shots(movie, [{**clip, 'path': entry['source']['path']} for clip in clips], settings, ordinal * 20 + part * 3)
        playlist.append({'src': f'/assets/startup/video/teams/{movie.name}',
                         'poster': f'/assets/startup/video/teams/{movie.with_suffix(".jpg").name}',
                         'kind': 'basketball', 'team': team, 'clips': clips,
                         'frames': sum(clip['frames'] + 18 for clip in clips)})
        playlist.append(offices[part])
    result = {'playlist': playlist, 'source': entry['source'], 'clips': entry['clips'],
              'duration_seconds': sum(scene['frames'] for scene in playlist) / settings['fps']}
    (OUTPUT / f'{team}-v2.json').write_text(json.dumps(result, indent=2) + '\n')
    return team, result

def main():
    parser = argparse.ArgumentParser(); parser.add_argument('--teams', nargs='*'); parser.add_argument('--workers', type=int, default=2)
    args = parser.parse_args()
    settings = json.loads((ROOT / 'scripts/startup_video_settings.json').read_text())
    catalog = json.loads((ROOT / 'scripts/startup_team_video_settings.json').read_text())
    OUTPUT.mkdir(parents=True, exist_ok=True)
    offices = front_office(settings)
    jobs = [(team, entry, settings, offices, index) for index, (team, entry) in enumerate(sorted(catalog['teams'].items())) if not args.teams or team in args.teams]
    with concurrent.futures.ProcessPoolExecutor(max_workers=args.workers) as executor:
        for team, _ in executor.map(render_team, jobs): print(f'Rendered reviewed reel {team}', flush=True)
    # Publish only a complete reviewed catalog, never mix old and corrected reels.
    if len(catalog['teams']) == 30 and all((OUTPUT / f'{team}-v2.json').exists() and json.loads((OUTPUT / f'{team}-v2.json').read_text()).get('clips') == entry['clips'] for team, entry in catalog['teams'].items()):
        manifest = {'version': 2, 'teams': {team: json.loads((OUTPUT / f'{team}-v2.json').read_text()) for team in sorted(catalog['teams'])}}
        temporary = OUTPUT / 'manifest.pending.json'; temporary.write_text(json.dumps(manifest, indent=2)+'\n'); temporary.replace(OUTPUT / 'manifest.json')
        print('Published 30 reviewed franchise playlists', flush=True)
if __name__ == '__main__': main()
