#!/usr/bin/env python3
"""Background music for the text videos: one track per brand, mixed in quietly.

Put one audio file per brand in the music/ folder, named after the brand exactly as the sheet writes it:

    music/ideaSquared.mp3
    music/AdoptDontShop.mp3
    music/CreatrGrid.mp3

render.py and motion.py then add that track to every video for the brand. A brand with no file gets silent
videos, as before. To leave one post silent, put No in a "Music" column on its row. See docs/music.md.

No AI and no network: the same track and the same row always give the same audio.
"""
import os
import re
from pathlib import Path

EXTS = ('.mp3', '.m4a', '.wav', '.ogg', '.flac')    # tried in this order
OFF = {'no', 'n', 'off', 'none', 'false', '0', 'silent'}
SAFE_NAME = re.compile(r'^[A-Za-z0-9][A-Za-z0-9_-]*$')

LUFS = -18          # loudness of the finished track: a bed under on-screen text, not a feature
TRUE_PEAK = -2
FADE_IN = 0.4       # seconds
FADE_OUT = 1.0
BITRATE = '160k'
SAMPLE_RATE = 48000


def music_dir():
    """The folder the tracks live in: MUSIC_DIR if set, else music/ next to this file."""
    return Path(os.environ.get('MUSIC_DIR') or Path(__file__).resolve().parent / 'music')


def wants_music(row):
    """False when the row's "Music" cell says no. An empty cell, or no such column, means yes."""
    return (row.get('Music') or '').strip().lower() not in OFF


def track_for(brand, folder=None):
    """Path of the brand's track as a string, or None when there is none."""
    brand = (brand or '').strip()
    if not SAFE_NAME.match(brand):
        return None
    folder = Path(folder) if folder else music_dir()
    for ext in EXTS:
        path = folder / f'{brand}{ext}'
        if path.is_file():
            return str(path)
    return None


def input_args(track):
    """ffmpeg input arguments for the track. It loops, so a short track still covers a long video."""
    return ['-stream_loop', '-1', '-i', track]


def audio_filter(index, total):
    """The filter that turns input number `index` into [a]: cut to the video's length, levelled, faded in and out."""
    if total <= 0:
        raise ValueError('the video has no length')
    fade_in = min(FADE_IN, total / 4)
    fade_out = min(FADE_OUT, total / 2)
    return (f'[{index}:a]atrim=0:{total:.3f},asetpts=PTS-STARTPTS,'
            f'loudnorm=I={LUFS}:TP={TRUE_PEAK}:LRA=11,aresample={SAMPLE_RATE},'
            f'afade=t=in:st=0:d={fade_in:.3f},afade=t=out:st={total - fade_out:.3f}:d={fade_out:.3f}[a]')


def output_args(total):
    """ffmpeg output arguments that map [a] and stop the file at the video's length."""
    return ['-map', '[a]', '-c:a', 'aac', '-b:a', BITRATE, '-t', f'{total:.3f}']
