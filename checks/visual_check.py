#!/usr/bin/env python3
"""Validate rendered output against its manifest.json.

Usage:  python checks/visual_check.py <out_dir> [--skip-video] [--skip-mtime]

Needs Pillow, and ffprobe for the video checks.  Exit code 1 on any FAIL;
warnings (WARN) never fail.  Output lines look like
    FAIL <asset> <check>: <detail>
"""
import argparse
import collections
import json
import os
import shutil
import subprocess
import sys

from PIL import Image

# =====================================================================
# Thresholds: edit here.
# =====================================================================
SLIDE_SIZE = (1080, 1350)
FRAME_SIZE = (1080, 1920)
VIDEO_SECONDS = (6.0, 60.0)
MTIME_SLACK = 1.0               # seconds a video may appear older than its newest frame
EDGE_INSET = 4                  # sample the column this many px in from the right edge
EDGE_LIGHT_LUMA = 200           # a frame is "light" if the dominant edge colour is at least this bright
EDGE_FLAT_SHARE = 0.55          # ...and that colour fills at least this share of the column (else patterned: skipped)
EDGE_DIFF = 150                 # summed |RGB| difference that counts as "strongly different"
EDGE_MIN_PIXELS = 12            # flag the frame when at least this many pixels differ strongly
CG_TILE_HEIGHT = 470            # CreatrGrid cover/title frames: decorative tiles bleed off the top-right
# =====================================================================


class Report:
    def __init__(self):
        self.items = []

    def fail(self, asset, check, detail):
        self.items.append(('FAIL', asset, check, detail))

    def warn(self, asset, check, detail):
        self.items.append(('WARN', asset, check, detail))

    @property
    def failed(self):
        return any(i[0] == 'FAIL' for i in self.items)


def luma(c):
    return 0.299 * c[0] + 0.587 * c[1] + 0.114 * c[2]


def white_corner(im):
    """The render glitch: bottom-right pixel pure white while bottom-left is not."""
    w, h = im.size
    return im.getpixel((w - 3, h - 3)) == (255, 255, 255) and im.getpixel((3, h - 3)) != (255, 255, 255)


def edge_text_pixels(im, skip_top=0):
    """Count strongly-different pixels in a column near the right edge.

    Returns (count, skipped_reason).  Dark or patterned frames are skipped."""
    w, h = im.size
    x = w - EDGE_INSET
    col = [im.getpixel((x, y)) for y in range(skip_top, h)]
    if not col:
        return 0, 'empty'
    # Quantise the dominant colour so anti-aliasing noise does not split it.
    common, n = collections.Counter(col).most_common(1)[0]
    if luma(common) < EDGE_LIGHT_LUMA:
        return 0, 'dark background'
    if n / len(col) < EDGE_FLAT_SHARE:
        return 0, 'patterned background'
    bad = sum(1 for p in col if sum(abs(a - b) for a, b in zip(p, common)) >= EDGE_DIFF)
    return bad, None


def ffprobe(path):
    r = subprocess.run(['ffprobe', '-v', 'error', '-select_streams', 'v:0',
                        '-show_entries', 'stream=width,height:format=duration', '-of', 'json', path],
                       capture_output=True, text=True, timeout=60)
    if r.returncode:
        raise RuntimeError(r.stderr.strip() or 'ffprobe failed')
    j = json.loads(r.stdout)
    s = j['streams'][0]
    return int(s['width']), int(s['height']), float(j['format']['duration'])


def list_images(folder, video, card=False):
    if card:
        p = os.path.join(folder, 'card.png')
        return [p] if os.path.isfile(p) else []
    d = os.path.join(folder, 'frames') if video else folder
    pre = 'frame_' if video else 'slide_'
    if not os.path.isdir(d):
        return []
    return sorted(os.path.join(d, f) for f in os.listdir(d) if f.startswith(pre) and f.endswith('.png'))


def check_asset(entry, out_dir, rep, skip_video=False, skip_mtime=False):
    asset = entry['asset']
    folder = os.path.join(out_dir, entry['folder'])
    video = bool(entry.get('video'))
    if not os.path.isdir(folder):
        rep.fail(asset, 'missing-folder', entry['folder'])
        return
    imgs = list_images(folder, video, bool(entry.get('card')))
    if len(imgs) != entry['frames']:
        rep.fail(asset, 'frame-count', f"manifest says {entry['frames']}, found {len(imgs)}")
    want = FRAME_SIZE if video else SLIDE_SIZE
    for k, p in enumerate(imgs, 1):
        name = os.path.basename(p)
        try:
            im = Image.open(p).convert('RGB')
        except Exception as e:                      # unreadable or truncated PNG
            rep.fail(asset, 'unreadable', f'{name}: {e}')
            continue
        if im.size != want:
            rep.fail(asset, 'size', f'{name} is {im.size[0]}x{im.size[1]}, expected {want[0]}x{want[1]}')
            continue
        if white_corner(im):
            rep.fail(asset, 'white-corner', f'{name}: bottom-right pixel is pure white, bottom-left is not')
        skip_top = CG_TILE_HEIGHT if entry.get('brand') == 'CreatrGrid' and k == 1 else 0
        bad, why = edge_text_pixels(im, skip_top)
        if not why and bad >= EDGE_MIN_PIXELS:
            rep.fail(asset, 'right-edge-text', f'{name}: {bad} pixels at x={want[0] - EDGE_INSET} differ from the background (text clipped?)')
    if video:
        mp4 = os.path.join(folder, 'video.mp4')
        if not os.path.isfile(mp4):
            rep.fail(asset, 'video-missing', 'video.mp4')
        elif not skip_video:
            try:
                w, h, dur = ffprobe(mp4)
            except Exception as e:
                rep.fail(asset, 'video-unreadable', str(e))
            else:
                if (w, h) != FRAME_SIZE:
                    rep.fail(asset, 'video-size', f'{w}x{h}, expected {FRAME_SIZE[0]}x{FRAME_SIZE[1]}')
                if not VIDEO_SECONDS[0] <= dur <= VIDEO_SECONDS[1]:
                    rep.fail(asset, 'video-duration', f'{dur:.1f}s, expected {VIDEO_SECONDS[0]:g} to {VIDEO_SECONDS[1]:g}s')
        if os.path.isfile(mp4) and imgs and not skip_mtime:
            newest = max(os.path.getmtime(p) for p in imgs)
            if os.path.getmtime(mp4) + MTIME_SLACK < newest:
                rep.fail(asset, 'video-stale', 'video.mp4 is older than its frames')


def find_orphans(out_dir, manifest, rep):
    known = {os.path.normpath(e['folder']) for e in manifest}
    for brand in sorted(os.listdir(out_dir)):
        bp = os.path.join(out_dir, brand)
        if brand.startswith('.') or not os.path.isdir(bp):
            continue
        for sub in sorted(os.listdir(bp)):
            rel = os.path.normpath(os.path.join(brand, sub))
            if os.path.isdir(os.path.join(out_dir, rel)) and rel not in known:
                rep.warn(sub.split('_')[0], 'not-in-manifest', rel)


def run(out_dir, skip_video=False, skip_mtime=False, stream=None):
    stream = stream or sys.stdout
    rep = Report()
    mp = os.path.join(out_dir, 'manifest.json')
    if not os.path.isfile(mp):
        print(f'FAIL - manifest: {mp} not found', file=stream)
        return 1
    with open(mp, encoding='utf-8') as f:
        manifest = json.load(f)
    if not skip_video and any(e.get('video') for e in manifest) and not shutil.which('ffprobe'):
        print('FAIL - ffprobe: not installed (use --skip-video to skip video checks)', file=stream)
        return 1
    for e in manifest:
        check_asset(e, out_dir, rep, skip_video, skip_mtime)
    find_orphans(out_dir, manifest, rep)
    for level, asset, check, detail in rep.items:
        print(f'{level} {asset} {check}: {detail}', file=stream)
    fails = sum(i[0] == 'FAIL' for i in rep.items)
    print(f'{len(manifest)} assets checked: {fails} failure(s), {len(rep.items) - fails} warning(s)', file=stream)
    return 1 if rep.failed else 0


def main(argv=None):
    ap = argparse.ArgumentParser(description='Validate rendered output against manifest.json.')
    ap.add_argument('out_dir')
    ap.add_argument('--skip-video', action='store_true', help='do not run ffprobe on videos')
    ap.add_argument('--skip-mtime', action='store_true', help='do not compare video and frame timestamps (e.g. after a download or unzip)')
    a = ap.parse_args(argv)
    return run(a.out_dir, a.skip_video, a.skip_mtime)


if __name__ == '__main__':
    sys.exit(main())
