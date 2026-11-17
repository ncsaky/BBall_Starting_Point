"""Build the fully offline startup montage from reviewed local footage.

Requires Python 3.11+, NumPy, Pillow and ffmpeg/ffprobe on the authoring machine.
No download/generative step. All settings and editorial choices are in settings.json.
Run from any directory; --action-source and --kings-source accept other local copies.
"""
import argparse
import hashlib
import json
import math
from pathlib import Path
import subprocess
import tempfile

import numpy as np
from PIL import Image, ImageFilter, ImageDraw

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent


def sha256(path):
    with path.open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def probe(path):
    return json.loads(subprocess.check_output([
        'ffprobe', '-v', 'error', '-show_streams', '-show_format', '-of', 'json', str(path)]))


class DotPress:
    """Fixed staggered lattice, changing dot AREA driven by local photographic tone.

    Antialiased circular ink marks are the image, rather than an overlay on a photo.
    Fixed exposure, no random seed/noise, fixed phase, gentle tone smoothing; a small
    high-frequency residual restores net strings, eyes and jersey lettering.
    """
    def __init__(self, width, height, settings):
        self.s = settings
        pitch = settings['pitch_pixels']
        rows, cols = math.ceil(height / pitch) + 1, math.ceil(width / pitch) + 1
        cy, cx = np.indices((rows, cols), dtype=np.float32)
        cx = (cx + .5 + (cy % 2) * .5) * pitch
        cy = (cy + .5) * pitch
        self.sample_x = np.clip(cx.astype(int), 0, width - 1).ravel()
        self.sample_y = np.clip(cy.astype(int), 0, height - 1).ravel()
        y, x = np.indices((height, width), dtype=np.float32)
        nearest = np.full((height, width), np.inf, np.float32)
        self.owner = np.zeros((height, width), np.int32)
        for offset in (-1, 0, 1):
            row = np.clip(np.floor(y / pitch).astype(int) + offset, 0, rows - 1)
            col = np.clip(np.rint(x / pitch - .5 - (row % 2) * .5).astype(int), 0, cols - 1)
            distance = np.sqrt((x - cx[row, col])**2 + (y - cy[row, col])**2)
            closer = distance < nearest
            self.owner[closer] = (row * cols + col)[closer]
            nearest = np.minimum(nearest, distance)
        self.distance = nearest
        # Calibrate radius against coverage on the actual raster, including AA.
        radii = np.linspace(0, pitch, 512, dtype=np.float32)
        sample = nearest[20:320, 20:620].ravel()
        coverage = np.array([np.clip((r - sample) / settings['antialias_pixels'] + .5, 0, 1).mean() for r in radii])
        self.radius = np.interp(np.linspace(0, 1, 1024), coverage, radii).astype(np.float32)
        self.previous = None
        self.paper = np.array(settings['paper_rgb'], np.float32)
        self.ink = np.array(settings['ink_rgb'], np.float32)

    def render(self, rgb, reset=False):
        gray_image = Image.fromarray(rgb).convert('L')
        gray = np.asarray(gray_image, dtype=np.float32) / 255
        blurred = np.asarray(gray_image.filter(ImageFilter.GaussianBlur(self.s['sample_blur_pixels'])), dtype=np.float32) / 255
        tone = blurred[self.sample_y, self.sample_x]
        if self.previous is not None and not reset:
            weight = self.s['previous_tone_weight']
            tone = tone * (1 - weight) + self.previous * weight
        self.previous = tone
        celltone = tone[self.owner]
        density = np.clip(1 - celltone, self.s['minimum_density'], self.s['maximum_density'])
        radius = self.radius[(density * 1023).astype(int)]
        ink_coverage = np.clip((radius - self.distance) / self.s['antialias_pixels'] + .5, 0, 1)
        printed = self.paper + ink_coverage[:, :, None] * (self.ink - self.paper)
        # Only fine detail residual; broad tone is entirely carried by dot area.
        printed += (gray - celltone)[:, :, None] * 255 * self.s['detail_residual_weight']
        return np.clip(printed, 0, 255).astype(np.uint8)


def read_clip(path, clip, settings):
    x, y, w, h = clip['crop_xywh']
    vf = (f"crop={w}:{h}:{x}:{y},scale={settings['width']}:{settings['height']}:"
          f"force_original_aspect_ratio=decrease,pad={settings['width']}:{settings['height']}:(ow-iw)/2:(oh-ih)/2,"
          f"setsar=1,fps={settings['fps']}")
    data = subprocess.check_output(['ffmpeg', '-v', 'error', '-xerror', '-ss', str(clip['source_start']),
        '-i', str(path), '-frames:v', str(clip['frames']), '-an', '-vf', vf, '-pix_fmt', 'rgb24', '-f', 'rawvideo', '-'])
    expected = clip['frames'] * settings['width'] * settings['height'] * 3
    if len(data) != expected:
        raise RuntimeError(f"{clip['id']}: incomplete decode ({len(data)} != {expected})")
    return np.frombuffer(data, np.uint8).reshape(clip['frames'], settings['height'], settings['width'], 3).copy()


def suppress_camera_flashes(frames):
    """Hold nearest unaffected real frame only for isolated exposure spikes.

    Source sports photographers flash during the dunk. Detect isolated luminance
    spikes against a five-frame median, never cuts (clips decoded separately).
    This introduces at most a brief frame hold, no synthetic person/ball imagery.
    """
    luminance = np.array([frame.mean(dtype=np.float64) for frame in frames])
    baseline = np.array([np.median(luminance[max(0, i - 2): min(len(frames), i + 3)]) for i in range(len(frames))])
    flagged = np.where(luminance - baseline > 9)[0]
    bad = set(flagged.tolist())
    for index in flagged:
        candidates = [j for j in range(max(0, index - 3), min(len(frames), index + 4)) if j not in bad]
        if not candidates:
            raise RuntimeError('Sustained source exposure spike needs editorial review')
        nearest = min(candidates, key=lambda j: abs(j - index))
        frames[index] = frames[nearest]
    return flagged.tolist()


def television_transition(outgoing, incoming, settings, transition_index):
    """Same interference family across moving shoulders and the 600ms burst.

    A half-second smoothstep ramp corrupts the actual outgoing frames; the same
    strength joins the central burst, then settles over actual incoming frames.
    Every source frame remains in place, including the payoff and landing.
    One deterministic random stream carries the chaotic structure across all
    three regions; broad exposure follows the photographic frame underneath.
    """
    height, width = outgoing.shape[1:3]
    x = np.arange(width)
    output = []
    low, high = settings['static_luma_range']
    seed = settings['noise_seed'] + transition_index * 1000
    rng = np.random.default_rng(seed)
    shoulder = settings['shoulder_frames']
    core = settings['frames']
    peak = settings['shoulder_peak_strength']
    total = shoulder * 2 + core
    bursts = rng.uniform(*settings['static_mix_range'], total)
    bursts[shoulder + 3:shoulder + 7] = np.clip(bursts[shoulder + 3:shoulder + 7] + .12, 0, .9)
    bursts[shoulder + 10:shoulder + 13] = np.clip(bursts[shoulder + 10:shoulder + 13] - .12, .3, .9)
    # Light smoothing removes abrupt jumps in the AMOUNT of interference while
    # its streak locations, tracking errors and color still change chaotically.
    bursts = np.convolve(np.pad(bursts, (1, 1), mode='edge'), [.2, .6, .2], mode='valid')
    def ease(value):
        return value * value * (3 - 2 * value)

    def field(rows, cols):
        values = rng.uniform(-1, 1, (rows, cols)).astype(np.float32)
        image = Image.fromarray(values).resize((width, height), Image.Resampling.BILINEAR)
        return np.asarray(image, dtype=np.float32)

    strengths = []
    for i in range(total):
        if i < shoulder:
            edge = peak * ease(i / (shoulder - 1))
            base = outgoing[-shoulder + i]
            picture_mean = base.mean()
        elif i >= shoulder + core:
            j = i - shoulder - core
            edge = peak * ease(1 - j / (shoulder - 1))
            base = incoming[j]
            picture_mean = base.mean()
        else:
            j = i - shoulder
            progress = j / (core - 1)
            edge = peak + (1 - peak) * ease(min(1., j / settings['edge_ramp_frames'],
                                                (core - 1 - j) / settings['edge_ramp_frames']))
            base = outgoing[-1] if progress < .5 else incoming[0]
            blend = ease(progress)
            picture_mean = outgoing[-1].mean() * (1 - blend) + incoming[0].mean() * blend
        strengths.append(edge)
        if edge == 0:
            output.append(base.copy())
            continue
        # Unequal scan groups snap out of horizontal sync, rather than waving.
        offsets = np.zeros(height, dtype=np.int32)
        row = 0
        while row < height:
            group = int(rng.integers(4, 43))
            displacement = int(rng.integers(-settings['max_horizontal_tear_pixels'],
                                           settings['max_horizontal_tear_pixels'] + 1) * edge)
            offsets[row:row + group] = displacement
            row += group
        offsets += np.rint(rng.normal(0, 2.2, height) * edge).astype(int)
        roll = round(rng.uniform(-1, 1) * settings['max_vertical_roll_pixels'] * edge)
        yy = np.mod(np.arange(height) - roll, height)[:, None]
        xx = np.clip(x[None, :] - offsets[:, None], 0, width - 1)
        picture = base[yy, xx].astype(np.float32)
        # Intermittent channel separation, strongest along torn scan groups.
        split = round(settings['rgb_split_pixels'] * edge * rng.uniform(.3, 1))
        picture[:, :, 0] = base[yy, np.clip(xx - split, 0, width - 1), 0]
        picture[:, :, 2] = base[yy, np.clip(xx + split, 0, width - 1), 2]
        # Multiple changing scales form dirty lateral streaks and clotted snow.
        fine = rng.normal(0, 1, (height, width)).astype(np.float32)
        streaks = field(int(rng.integers(100, 260)), int(rng.integers(26, 78)))
        clouds = field(int(rng.integers(9, 22)), int(rng.integers(13, 38)))
        snow = 112 + fine * 12 + streaks * 102 + clouds * 28
        snow = np.clip(snow, low, high)
        static = np.stack([snow - 5, snow + 2, snow + 6], axis=2)
        # Ragged rainbow fringing, inspired by the supplied analogue-TV reference.
        chroma = field(int(rng.integers(38, 110)), int(rng.integers(7, 20)))
        activity = np.clip(np.abs(streaks) * 1.8, 0, 1)
        amplitude = settings['chroma_breakup_strength'] * edge
        static[:, :, 0] += chroma * activity * amplitude
        static[:, :, 1] -= chroma * activity * amplitude * .8
        static[:, :, 2] += np.roll(chroma, int(rng.integers(3, 20)), axis=1) * activity * amplitude
        mix = float(bursts[i]) * edge
        result = picture * (1 - mix) + static * mix
        # Dropouts appear at unrelated positions/sizes; no clean moving stripe.
        count = int(rng.integers(settings['dropout_bands_per_frame'][0],
                                 settings['dropout_bands_per_frame'][1] + 1))
        for _ in range(count):
            top = int(rng.integers(0, height))
            band_height = int(rng.integers(settings['dropout_band_height_pixels'][0],
                                          settings['dropout_band_height_pixels'][1] + 1))
            band = slice(top, min(height, top + band_height))
            tear = int(rng.integers(-140, 141))
            corrupted = np.roll(static[band], tear, axis=1)
            corrupted += rng.uniform(-32, 26)
            dropout_mix = edge * rng.uniform(.6, .98)
            result[band] = result[band] * (1 - dropout_mix) + corrupted * dropout_mix
        # Sparse short signal scratches, with variable lengths and positions.
        for _ in range(int(rng.integers(12, 28))):
            y = int(rng.integers(0, height)); left = int(rng.integers(0, width))
            length = int(rng.integers(25, 340)); thickness = int(rng.integers(1, 4))
            band = (slice(y, min(height, y + thickness)), slice(left, min(width, left + length)))
            gray = rng.uniform(36, 186)
            tint = np.array([gray + rng.uniform(-28, 28), gray, gray + rng.uniform(-28, 28)])
            result[band] = result[band] * (1 - .7 * edge) + tint * .7 * edge
        # Broad exposure changes smoothly, even while fine interference is erratic.
        target_mean = picture_mean * (1 - .5 * edge) + 112 * .5 * edge
        current_mean = float(result.mean())
        result += np.clip(target_mean - current_mean, -35, 35)
        output.append(np.clip(result, 0, 255).astype(np.uint8))
    output = np.stack(output)
    return output[:shoulder], output[shoulder:shoulder + core], output[shoulder + core:], strengths



def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--settings', type=Path, default=HERE / 'startup_video_settings.json')
    parser.add_argument('--action-source', type=Path, help='Override the reviewed local NBA source')
    parser.add_argument('--clips', type=Path, help='Override the cached source directory')
    parser.add_argument('--output', type=Path, default=ROOT / 'src/nba_gm_data/gui/assets/startup/video')
    parser.add_argument('--evidence', type=Path, default=ROOT / 'output/startup-video-refresh/full')
    args = parser.parse_args()
    s = json.loads(args.settings.read_text())
    args.output.mkdir(parents=True, exist_ok=True)
    args.evidence.mkdir(parents=True, exist_ok=True)
    sources, audit = {}, {}
    for key, source in s['sources'].items():
        path = (ROOT / source['path']).resolve()
        if key == 'action' and args.action_source:
            path = args.action_source.resolve()
        elif key != 'action' and args.clips:
            path = (args.clips / path.name).resolve()
        if not path.is_file():
            parser.error(f'Missing reviewed local footage: {path}')
        # Never trust container metadata alone, especially an incomplete .part.
        subprocess.run(['ffmpeg', '-nostdin', '-v', 'error', '-xerror', '-i', str(path),
                        '-map', '0:v:0', '-an', '-f', 'null', '-'], check=True)
        sources[key] = path
        audit[key] = {**source, 'local_source_path': str(path), 'sha256': sha256(path),
                      'duration_seconds': float(probe(path)['format']['duration']), 'full_decode': 'passed'}
    fps, shoulder, core = s['fps'], s['transition']['shoulder_frames'], s['transition']['frames']
    segments, transitions, cursor = [], [], 0
    comparison_dir = args.evidence / 'comparisons'
    comparison_dir.mkdir(exist_ok=True)
    originals = {}
    # Disk-backed clip frames bound memory regardless of montage length. Scratch
    # files are owned by this build and removed on completion/failure.
    with tempfile.TemporaryDirectory(prefix='startup-video-') as scratch_dir:
        scratch = Path(scratch_dir)
        paths = []
        press = DotPress(s['width'], s['height'], s['halftone'])
        for index, clip in enumerate(s['clips']):
            source = audit[clip['source_key']]
            if clip['frames'] < 2 * shoulder + 1:
                raise RuntimeError(f'{clip["id"]}: shoulders would overlap')
            if clip['file_start'] + clip['frames']/fps > source['duration_seconds']:
                raise RuntimeError(f'{clip["id"]}: source is incomplete')
            frames = read_clip(sources[clip['source_key']], {**clip, 'source_start': clip['file_start']}, s)
            sample = clip['comparison_local_frame']
            original_path = comparison_dir / f'{clip["id"]}-original.jpg'
            Image.fromarray(frames[sample]).save(original_path, quality=95)
            originals[index] = original_path
            flash_frames = suppress_camera_flashes(frames)
            npy = scratch / f'clip-{index:02}.npy'
            processed = np.lib.format.open_memmap(npy, mode='w+', dtype=np.uint8, shape=frames.shape)
            for n, frame in enumerate(frames):
                processed[n] = press.render(frame, reset=n == 0)
                if n % 90 == 0:
                    print(f'{index+1}/{len(s["clips"])} {clip["id"]}: {n}/{len(frames)}', flush=True)
            processed.flush()
            del processed, frames
            paths.append(npy)
            segment = {**clip, 'source_end_exclusive': clip['source_start'] + clip['frames']/fps,
                       'file_end_exclusive': clip['file_start'] + clip['frames']/fps,
                       'duration': clip['frames']/fps, 'montage_start': cursor/fps,
                       'montage_start_frame': cursor, 'source_sha256': source['sha256'],
                       'local_source_path': source['local_source_path'],
                       'suppressed_camera_flash_local_frames': flash_frames, 'source_excerpt_full_decode': 'passed'}
            segments.append(segment)
            cursor += clip['frames'] + core
        tr_paths = []
        # Compute all effects against untreated dot-press frames, then apply the
        # moving shoulders. No repeated filtering or accidental loop feedback.
        for index, path in enumerate(paths):
            next_index = (index+1) % len(paths)
            outgoing = np.load(path, mmap_mode='r')
            incoming = np.load(paths[next_index], mmap_mode='r')
            leading, burst, trailing, envelope = television_transition(outgoing, incoming, s['transition'], index)
            tr_path = scratch / f'transition-{index:02}.npy'
            np.save(tr_path, np.concatenate([leading, burst, trailing]))
            tr_paths.append(tr_path)
            start = segments[index]['montage_start_frame'] + segments[index]['frames']
            next_start = segments[next_index]['montage_start_frame']
            transitions.append({**s['transition'], 'type': 'baked analogue-TV interference with moving-picture lead-in and recovery',
                'montage_start_frame': start, 'montage_start_seconds': start/fps,
                'cut_frame': start + core//2, 'cut_seconds': (start + core//2)/fps,
                'outgoing_clip': segments[index]['id'], 'incoming_clip': segments[next_index]['id'],
                'boundary_kind': segments[index]['boundary_to_next'] if next_index else 'loop',
                'actual_source_cut_seconds': segments[index]['actual_source_cut_after_seconds'],
                'loop_boundary': next_index == 0,
                'outgoing_distortion_frames': [start-shoulder, start-1],
                'incoming_distortion_frames': [next_start, next_start+shoulder-1],
                'outgoing_source_local_frames': [segments[index]['frames']-shoulder, segments[index]['frames']-1],
                'incoming_source_local_frames': [0, shoulder-1], 'strength_envelope': envelope,
                'shoulder_method': 'Actual advancing source frames; smoothstep 0 to 45% distortion and 45% to 0; no trim, overlap or freeze of source action'})
            del outgoing, incoming, leading, burst, trailing
        for index, tr_path in enumerate(tr_paths):
            next_index = (index+1) % len(paths)
            effect = np.load(tr_path, mmap_mode='r')
            outgoing = np.load(paths[index], mmap_mode='r+')
            incoming = np.load(paths[next_index], mmap_mode='r+')
            outgoing[-shoulder:] = effect[:shoulder]
            incoming[:shoulder] = effect[shoulder+core:]
            outgoing.flush(); incoming.flush()
            del effect, outgoing, incoming
        movie = args.output / 'front-office.mp4'
        enc = s['encoding']
        command = ['ffmpeg', '-nostdin', '-v', 'error', '-y', '-f', 'rawvideo', '-pix_fmt', 'rgb24',
            '-s', f'{s["width"]}x{s["height"]}', '-r', str(fps), '-i', '-', '-an', '-c:v', 'libx264',
            '-preset', enc['preset'], '-crf', str(enc['crf']), '-pix_fmt', enc['pixel_format'],
            '-profile:v', enc['profile'], '-level:v', enc['level'], '-g', str(enc['gop']),
            '-movflags', '+faststart', '-threads', '4', '-map_metadata', '-1', '-metadata',
            'comment=Real footage: NBA S6cSohNkms4; Sacramento Kings OW-rtBy7RFo; Denver Nuggets ErrVf5TFGzk. Private friends testing; no public-distribution clearance.', str(movie)]
        encoder = subprocess.Popen(command, stdin=subprocess.PIPE)
        try:
            for index, path in enumerate(paths):
                processed = np.load(path, mmap_mode='r')
                for frame in processed:
                    encoder.stdin.write(frame.tobytes())
                effect = np.load(tr_paths[index], mmap_mode='r')
                for frame in effect[shoulder:shoulder+core]:
                    encoder.stdin.write(frame.tobytes())
                del processed, effect
                print(f'Encoded shot {index+1}/{len(paths)}', flush=True)
        finally:
            encoder.stdin.close()
        if encoder.wait() != 0:
            raise RuntimeError('H.264 encoding failed')
    subprocess.run(['ffmpeg', '-nostdin', '-v', 'error', '-xerror', '-i', str(movie), '-an', '-f', 'null', '-'], check=True)
    subprocess.run(['ffmpeg', '-nostdin', '-v', 'error', '-y', '-ss', '4.3', '-i', str(movie),
                    '-frames:v', '1', str(args.output/'poster.jpg')], check=True)
    for index, clip in enumerate(s['clips']):
        n = segments[index]['montage_start_frame'] + clip['comparison_local_frame']
        processed_path = comparison_dir / f'{clip["id"]}-processed.png'
        subprocess.run(['ffmpeg', '-nostdin', '-v', 'error', '-y', '-i', str(movie),
                        '-vf', f'select=eq(n\\,{n})', '-frames:v', '1', str(processed_path)], check=True)
        original = Image.open(originals[index]).convert('RGB')
        processed = Image.open(processed_path).convert('RGB')
        sheet = Image.new('RGB', (s['width']*2, s['height']+30), '#17212a')
        sheet.paste(original, (0,30)); sheet.paste(processed, (s['width'],30))
        draw = ImageDraw.Draw(sheet)
        draw.text((12,10), f'Original {clip["id"]} | source {clip["source_start"]+clip["comparison_local_frame"]/fps:.3f}s', fill='white')
        draw.text((s['width']+12,10), f'Final encoded montage | {n/fps:.3f}s | tone-dependent ink dots', fill='white')
        sheet.save(comparison_dir/f'{clip["id"]}-matched.jpg', quality=95)
    metadata = {'format':'silent H.264 High@3.1, yuv420p, 1280x720, 30fps, faststart',
        'duration_seconds': cursor/fps, 'frames': cursor, 'bytes': movie.stat().st_size, 'sha256':sha256(movie),
        'poster_sha256':sha256(args.output/'poster.jpg'), 'logical_clip_count':len({c['logical_clip_id'] for c in s['clips']}),
        'segments':segments, 'sources':audit, 'transitions':transitions,
        'treatment':{**s['halftone'], 'method':'Photographic tone changes antialiased circular ink-dot area on a fixed staggered lattice; 16% tone smoothing and 14% fine-detail residual. Baked into the MP4; no grayscale photo beneath a static screen or runtime dots.'},
        'build':{'script':'scripts/build_startup_video.py','settings':'scripts/startup_video_settings.json',
                 'script_sha256':sha256(Path(__file__)), 'settings_sha256':sha256(args.settings),
                 'ffmpeg':subprocess.check_output(['ffmpeg','-version'],text=True).splitlines()[0],
                 'numpy_version':np.__version__, 'pillow_version':Image.__version__},
        'audience':'Supplied local footage assumed authorized for private friends testing; attribution is not public-distribution clearance.',
        'source_exclusions':[{'path':'.cache/startup-video/ErrVf5TFGzk.mp4.part','reason':'Container probe succeeds but full decode fails; only complete Nuggets cached excerpts used.'},
                             {'source':'Washington Capitals','reason':'NBA footage available for all office slots; use Kings/Nuggets front-office scenes in the NBA montage.'}]}
    (args.output/'manifest.json').write_text(json.dumps(metadata,indent=2)+'\n')
    (args.evidence/'probe.json').write_text(json.dumps(probe(movie),indent=2)+'\n')
    print(json.dumps({'movie':str(movie),'seconds':cursor/fps,'bytes':metadata['bytes']}),flush=True)

if __name__ == '__main__':
    main()
