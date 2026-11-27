#!/usr/bin/env python3
"""Background music for the text videos: a small pool of tracks per brand, rotated, mixed in quietly.

Put each brand's tracks in a folder named after the brand exactly as the sheet writes it:

    music/ideaSquared/morning-coffee.mp3
    music/ideaSquared/vintage.mp3
    music/AdoptDontShop/puppy-love.mp3
    ...

render.py and motion.py then put one of the brand's tracks under each of its videos, taking them in turn so
that videos posted one after another do not sound the same. A brand with no tracks gets silent videos. To
leave one post silent, put No in a "Music" column on its row. See docs/music.md.

No AI and no network: the same sheet and the same tracks always give the same audio.
"""
import json
import os
import re
from pathlib import Path

EXTS = ('.mp3', '.m4a', '.wav', '.ogg', '.flac')
OFF = {'no', 'n', 'off', 'none', 'false', '0', 'silent'}
SAFE_NAME = re.compile(r'^[A-Za-z0-9][A-Za-z0-9_-]*$')
CUTS_FILE = 'cuts.json'     # {"<Brand>/<file>": [start seconds, ...]}, written by find_cuts.py
VIDEO_FORMAT = 'text-on-screen'
_WEEK_DAY = re.compile(r'week\s*(\d+)(?:\D+([A-Za-z]{3}))?', re.I)
_DAYS = ('mon', 'tue', 'wed', 'thu', 'fri', 'sat', 'sun')

LUFS = -18          # loudness aimed for: a bed under on-screen text, not a feature
TRUE_PEAK = -2
FADE_IN = 0.03      # seconds: only long enough to avoid a click, so the first beat still lands
FADE_OUT = 1.0
BITRATE = '160k'
SAMPLE_RATE = 48000


def music_dir():
    """The folder the tracks live in: MUSIC_DIR if set, else music/ next to this file."""
    return Path(os.environ.get('MUSIC_DIR') or Path(__file__).resolve().parent / 'music')


def wants_music(row):
    """False when the row's "Music" cell says no. An empty cell, or no such column, means yes."""
    return (row.get('Music') or '').strip().lower() not in OFF


def tracks_for(brand, folder=None):
    """The brand's tracks, as paths relative to the music folder, in name order. Empty when it has none.

    Tracks live in <folder>/<Brand>/. A single <folder>/<Brand>.<ext> also counts, as a pool of one."""
    brand = (brand or '').strip()
    if not SAFE_NAME.match(brand):
        return []
    folder = Path(folder) if folder else music_dir()
    pool = folder / brand
    found = sorted(f'{brand}/{p.name}' for p in pool.iterdir() if p.is_file() and p.suffix.lower() in EXTS) if pool.is_dir() else []
    if not found:
        found = [f'{brand}{ext}' for ext in EXTS if (folder / f'{brand}{ext}').is_file()][:1]
    return found


def load_cuts(folder=None):
    """{track: [start seconds]} from cuts.json. A missing or unreadable file means every track starts at 0."""
    path = (Path(folder) if folder else music_dir()) / CUTS_FILE
    try:
        data = json.loads(path.read_text(encoding='utf-8'))
    except (OSError, ValueError):
        return {}
    return data if isinstance(data, dict) else {}


def cuts_for(track, cuts):
    """The usable start times for one track, in order. Always at least [0.0]."""
    found = cuts.get(track) if isinstance(cuts, dict) else None
    if not isinstance(found, list):
        return [0.0]
    clean = sorted({float(c) for c in found if isinstance(c, (int, float)) and not isinstance(c, bool) and c >= 0})
    return clean or [0.0]


def pick(tracks, cuts, n):
    """(track, start) for the brand's n-th video, counting from 0. (None, 0.0) when the brand has no tracks.

    Tracks are taken in turn. Once every track has been used, the round starts again from each track's next
    start point, so nothing repeats until every track has been heard from every one of its start points."""
    if not tracks:
        return None, 0.0
    track = tracks[n % len(tracks)]
    starts = cuts_for(track, cuts)
    return track, starts[(n // len(tracks)) % len(starts)]


def _calendar_key(week_day):
    """Sort key for a "Week 3 · Tue" label. A row with no week sorts after every dated row."""
    m = _WEEK_DAY.search(week_day or '')
    if not m:
        return (1, 0, 0)
    day = (m.group(2) or '').lower()
    return (0, int(m.group(1)), _DAYS.index(day) if day in _DAYS else 99)


def rotation(rows):
    """{Asset ID: n}: each music video's place in its brand's posting order, counting from 0.

    Counted over the whole sheet, in calendar order then sheet order, so a video gets the same track whether
    render.py is run on every row or on a few with --only. Adding a post in the middle moves the posts after
    it along by one; they keep their old audio until they are rendered again."""
    order = []
    for index, row in enumerate(rows):
        aid = (row.get('Asset ID') or '').strip()
        brand = (row.get('Brand') or '').strip()
        fmt = (row.get('Format') or '').strip().lower()
        if aid and brand and fmt.startswith(VIDEO_FORMAT) and wants_music(row):
            order.append((_calendar_key(row.get('Week / day')), index, brand, aid))
    counts, places = {}, {}
    for _, _, brand, aid in sorted(order):
        if aid in places:
            continue                               # a repeated Asset ID keeps its first place
        places[aid] = counts.get(brand, 0)
        counts[brand] = places[aid] + 1
    return places


def choose(row, places, folder=None, cuts=None):
    """(absolute path, relative name, start) of the track for this row's video, or (None, None, 0.0) for silence."""
    aid = (row.get('Asset ID') or '').strip()
    if not wants_music(row) or aid not in places:
        return None, None, 0.0
    folder = Path(folder) if folder else music_dir()
    track, start = pick(tracks_for(row.get('Brand'), folder), load_cuts(folder) if cuts is None else cuts, places[aid])
    if not track:
        return None, None, 0.0
    return str(folder / track), track, start


def resolve(name, folder=None):
    """Absolute path of a track recorded in the manifest, or None if it is no longer there."""
    if not name or not isinstance(name, str):
        return None
    folder = Path(folder) if folder else music_dir()
    path = (folder / name).resolve()
    if folder.resolve() not in path.parents or not path.is_file():
        return None
    return str(path)


def input_args(track):
    """ffmpeg input arguments for the track. It loops, so a short track still covers a long video."""
    return ['-stream_loop', '-1', '-i', track]


def audio_filter(index, total, start=0.0):
    """The filter that turns input number `index` into [a].

    Takes `total` seconds beginning `start` seconds into the track, levels them, and fades them in and out."""
    if total <= 0:
        raise ValueError('the video has no length')
    if start < 0:
        raise ValueError('the start cannot be negative')
    fade_in = min(FADE_IN, total / 4)
    fade_out = min(FADE_OUT, total / 2)
    return (f'[{index}:a]atrim=start={start:.3f}:end={start + total:.3f},asetpts=PTS-STARTPTS,'
            f'loudnorm=I={LUFS}:TP={TRUE_PEAK}:LRA=11,aresample={SAMPLE_RATE},'
            f'afade=t=in:st=0:d={fade_in:.3f},afade=t=out:st={total - fade_out:.3f}:d={fade_out:.3f}[a]')


def output_args(total):
    """ffmpeg output arguments that map [a] and stop the file at the video's length."""
    return ['-map', '[a]', '-c:a', 'aac', '-b:a', BITRATE, '-t', f'{total:.3f}']
