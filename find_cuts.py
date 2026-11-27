#!/usr/bin/env python3
"""Find clean places to start each music track, and write them to music/cuts.json.

    pip install librosa
    python find_cuts.py [--music music] [--count 5] [--need 40]

Run this once after adding or replacing a track. render.py never runs it: it only reads cuts.json, so
rendering stays fast and needs nothing beyond ffmpeg.

A video does not always start its track at the beginning. To give more variety from the same tracks, it can
start at any of that track's cut points. A cut point is the first beat of a four-bar phrase, found by beat
tracking, so a video never comes in halfway through a beat or a phrase. The start of the track is always one
of them. See docs/music.md.

librosa is only needed here. It is not in requirements.txt.
"""
import argparse, json, subprocess, sys
from pathlib import Path

import music

RATE = 22050
PRE_ROLL = 0.03      # start this long before the beat, so the hit itself is not clipped
BEATS_PER_BAR = 4
BARS_PER_PHRASE = 4
DOUBLE_TIME = 120    # a tracker that reports more beats a minute than this has usually counted every half beat


def choose_phase(strengths, period=BEATS_PER_BAR):
    """Which beat of the bar is beat one: the offset whose beats carry the most low-end weight on average."""
    if not strengths:
        return 0
    best, best_score = 0, None
    for phase in range(min(period, len(strengths))):
        picked = strengths[phase::period]
        score = sum(picked) / len(picked)
        if best_score is None or score > best_score:
            best, best_score = phase, score
    return best


def beats_per_bar(tempo):
    """How many tracked beats make one bar: 4, or 8 when the tracker has counted in double time."""
    return BEATS_PER_BAR * 2 if tempo > DOUBLE_TIME else BEATS_PER_BAR


def phrase_starts(beats, phase, per_bar=BEATS_PER_BAR, bars=BARS_PER_PHRASE):
    """Times of the first beat of each phrase."""
    return list(beats[phase::per_bar * bars])


def pick_cuts(boundaries, duration, need, count, pre_roll=PRE_ROLL):
    """Up to `count` start times, spread across the usable part of the track. 0 is always the first.

    A start is usable only if `need` seconds of track follow it, so a video never runs off the end."""
    latest = duration - need
    usable = sorted(round(b - pre_roll, 3) for b in boundaries if pre_roll < b - pre_roll <= latest)
    cuts = [0.0]
    if count <= 1 or not usable:
        return cuts
    step = latest / (count - 1)
    for k in range(1, count):
        target = k * step
        nearest = min(usable, key=lambda t: abs(t - target))
        if nearest - cuts[-1] >= step / 2 and nearest not in cuts:      # keep them apart, and never twice
            cuts.append(nearest)
    return cuts


def decode(path):
    """The track as mono samples at RATE, decoded by ffmpeg exactly as render.py will read it."""
    import numpy as np
    raw = subprocess.run(['ffmpeg', '-v', 'error', '-i', str(path), '-ac', '1', '-ar', str(RATE), '-f', 'f32le', '-'],
                         check=True, capture_output=True).stdout
    return np.frombuffer(raw, dtype='<f4')


def analyse(path, count, need):
    """(cuts, tempo in beats a minute, number of beats found) for one track."""
    import librosa
    import numpy as np
    y = decode(path)
    duration = len(y) / RATE
    tempo, frames = librosa.beat.beat_track(y=y, sr=RATE)
    beats = librosa.frames_to_time(frames, sr=RATE)
    # Low end only (kick and bass), where beat one of a bar is usually the heaviest.
    mel = librosa.feature.melspectrogram(y=y, sr=RATE, n_mels=64, fmax=8000)
    low = librosa.onset.onset_strength(S=librosa.power_to_db(mel[:6]), sr=RATE)
    strengths = [float(low[min(f, len(low) - 1)]) for f in frames]
    tempo = float(np.atleast_1d(tempo)[0])
    per_bar = beats_per_bar(tempo)
    phase = choose_phase(strengths, per_bar)
    cuts = pick_cuts(phrase_starts(list(beats), phase, per_bar), duration, need, count)
    return cuts, tempo * BEATS_PER_BAR / per_bar, len(beats)


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split('\n')[0])
    ap.add_argument('--music', default=None, help='the tracks folder (default: music/, or MUSIC_DIR)')
    ap.add_argument('--count', type=int, default=5, help='the most cut points to keep for one track')
    ap.add_argument('--need', type=float, default=40, help='seconds of track that must follow a cut point')
    a = ap.parse_args(argv)
    folder = Path(a.music) if a.music else music.music_dir()
    try:
        import librosa  # noqa: F401
    except ImportError:
        print('error: this script needs librosa: pip install librosa', file=sys.stderr); return 2
    tracks = sorted(p for p in folder.rglob('*') if p.is_file() and p.suffix.lower() in music.EXTS)
    if not tracks:
        print(f'error: no tracks under {folder}', file=sys.stderr); return 2
    cuts = {}
    for path in tracks:
        key = path.relative_to(folder).as_posix()
        found, tempo, beats = analyse(path, a.count, a.need)
        cuts[key] = found
        print(f'{key}: {tempo:.0f} beats a minute, {beats} beats tracked, starts at {", ".join(f"{c:g}" for c in found)}')
    (folder / music.CUTS_FILE).write_text(json.dumps(cuts, indent=1, sort_keys=True) + '\n', encoding='utf-8')
    print(f'wrote {folder / music.CUTS_FILE}')
    return 0


if __name__ == '__main__':
    sys.exit(main())
