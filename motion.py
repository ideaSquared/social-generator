#!/usr/bin/env python3
"""Add tasteful motion to the text videos that render.py produced.

Reads <out_dir>/manifest.json and the existing frames/frame_NN.png files and
writes video_motion.mp4 next to each video.mp4. ffmpeg filters only, no
re-rendering.  See docs/motion.md.
"""
import argparse
import json
import os
import subprocess
import sys
import time

W, H, FPS = 1080, 1920, 30
SS = 2                      # internal supersampling factor for the push-in
ZOOM = 0.03                 # 100% -> 103% over each frame's duration
BAR_H = 10
ACCENTS = {'AdoptDontShop': '#dc1a45', 'ideaSquared': '#e8911a', 'CreatrGrid': '#7c3aed'}
DEFAULT_ACCENT = '#dc1a45'
STYLES = {
    'calm': {'duration': 0.35, 'transitions': ['fade']},
    'lively': {'duration': 0.30, 'transitions': ['slideup', 'smoothleft']},
}


def frame_duration(kind, text):
    """Seconds one frame is shown; mirrors render.py (title 2.8, end 3.4, beats by word count)."""
    if kind == 'title':
        return 2.8
    if kind == 'end':
        return 3.4
    return max(2.4, min(5.2, 1.4 + len(text.split()) * 0.3))


def durations(texts):
    """Per-frame durations for a manifest 'text' list (first = title, last = end card)."""
    n = len(texts)
    return [frame_duration('title' if i == 0 else 'end' if i == n - 1 else 'beat', t)
            for i, t in enumerate(texts)]


def accent_for(brand):
    return ACCENTS.get(brand, DEFAULT_ACCENT)


def total_duration(durs, fade):
    return sum(durs) + fade


def build_command(pngs, durs, out_path, accent, style='calm'):
    """Return the ffmpeg argument list (pure function, nothing is executed)."""
    if style not in STYLES:
        raise ValueError(f'unknown style {style!r}')
    if len(pngs) != len(durs) or not pngs:
        raise ValueError('need one duration per frame and at least one frame')
    st = STYLES[style]
    fade = st['duration']
    total = total_duration(durs, fade)
    bw, bh = W * SS, H * SS
    cmd = ['ffmpeg', '-y', '-loglevel', 'error']
    for p, d in zip(pngs, durs):
        cmd += ['-loop', '1', '-framerate', str(FPS), '-t', f'{d + fade:.3f}', '-i', p]
    parts = []
    for i, d in enumerate(durs):
        seg = d + fade
        # Supersample, scale with a per-frame time expression, crop around the
        # centre, then downsample: sub-pixel steps, so no zoompan-style jitter.
        parts.append(
            f"[{i}:v]scale={bw}:{bh}:flags=lanczos,setsar=1,"
            f"scale=w='trunc({bw}*(1+{ZOOM}*t/{seg:.3f})/2)*2':h='trunc({bh}*(1+{ZOOM}*t/{seg:.3f})/2)*2':eval=frame:flags=bicubic,"
            f"crop={bw}:{bh}:'(iw-{bw})/2':'(ih-{bh})/2',"
            f"scale={W}:{H}:flags=lanczos,format=yuv420p,fps={FPS}[s{i}]")
    prev = '[s0]'
    off = 0.0
    for i in range(1, len(pngs)):
        off += durs[i - 1]
        tr = st['transitions'][(i - 1) % len(st['transitions'])]
        parts.append(f"{prev}[s{i}]xfade=transition={tr}:duration={fade}:offset={off:.3f}[x{i}]")
        prev = f'[x{i}]'
    parts.append(f"color=c={accent}:s={W}x{BAR_H}:r={FPS}:d={total:.3f},format=yuv420p[bar]")
    parts.append(f"{prev}drawbox=x=0:y=0:w=iw:h={BAR_H}:color=white@0.18:t=fill[tr]")
    parts.append(f"[tr][bar]overlay=x='-W+W*t/{total:.3f}':y=0:eval=frame:shortest=1,format=yuv420p[v]")
    cmd += ['-filter_complex', ';'.join(parts), '-map', '[v]', '-t', f'{total:.3f}',
            '-c:v', 'libx264', '-preset', 'veryfast', '-crf', '19', '-pix_fmt', 'yuv420p',
            '-r', str(FPS), '-an', '-movflags', '+faststart', out_path]
    return cmd


def load_jobs(out_dir, only=None):
    with open(os.path.join(out_dir, 'manifest.json'), encoding='utf-8') as f:
        man = json.load(f)
    jobs = []
    for m in man:
        if not m.get('video') or (only and m['asset'] not in only):
            continue
        folder = os.path.join(out_dir, m['folder'])
        pngs = [os.path.join(folder, 'frames', 'frame_%02d.png' % k) for k in range(1, m['frames'] + 1)]
        jobs.append((m, pngs, durations(m['text']), os.path.join(folder, 'video_motion.mp4')))
    return jobs


def main(argv=None):
    ap = argparse.ArgumentParser(description='Write video_motion.mp4 (progress bar, push-in, transitions) for each text video.')
    ap.add_argument('out_dir')
    ap.add_argument('--only', default='', help='comma-separated Asset IDs')
    ap.add_argument('--style', choices=sorted(STYLES), default='calm')
    a = ap.parse_args(argv)
    only = {x for x in a.only.split(',') if x}
    jobs = load_jobs(os.path.abspath(a.out_dir), only)
    if not jobs:
        print('no video assets found'); return 1
    for m, pngs, durs, out in jobs:
        missing = [p for p in pngs if not os.path.exists(p)]
        if missing:
            print(f"{m['asset']}: missing {missing[0]}", file=sys.stderr); return 1
        t0 = time.time()
        subprocess.run(build_command(pngs, durs, out, accent_for(m['brand']), a.style), check=True)
        print(f"{m['asset']} ({a.style}) -> {out} in {time.time() - t0:.1f}s")
    return 0


if __name__ == '__main__':
    sys.exit(main())
