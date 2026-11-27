#!/usr/bin/env python3
"""Sort rendered assets into one folder per post and platform, ready to upload.

    python package.py out --csv posts.csv [--only ADS-C01,CG-X03]

Reads the sheet CSV and render.py's output folder, and writes:

    out/posts/<Brand>/<Platform>/<AssetID>/<AssetID>_<Platform>_...

Split by brand, then by platform, so everything for one account sits in one place. A row gets one folder
for every platform it is posted to (its Platform plus everything in "Also post to"). Each folder holds
only what that platform needs, with the caption adjusted for it, so nothing has to be worked out at
posting time. No AI: the same sheet and output always give the same folders.
"""
import argparse, csv, json, re, shutil, sys
from pathlib import Path

from PIL import Image

import gallery
import postprocess

SAFE_ID = re.compile(r'^[A-Za-z0-9][A-Za-z0-9_-]*$')      # one plain folder name: no slashes, dots or drive letters

from captions import PLATFORMS, caption_for, captions_in  # noqa: F401  (re-exported for callers and tests)


def warn(msg):
    print(f'warning: {msg}', file=sys.stderr)


def platforms_for(row):
    """The platforms a row is posted to, main platform first, no repeats."""
    names = [row.get('Platform', '')] + re.split(r'[,;/]', row.get('Also post to', '') or '')
    out = []
    for n in names:
        n = n.strip()
        match = next((p for p in PLATFORMS if p.lower() == n.lower()), None)
        if match and match not in out:
            out.append(match)
    return out


# ---------------------------------------------------------------- files
def kind_of(fmt):
    f = (fmt or '').strip().lower()
    if f.startswith('text-on-screen'):
        return 'video'
    if f.startswith('graphic'):
        return 'carousel'
    if f in ('text card', 'stat card', 'quote card'):
        return 'card'
    if f == 'text post':
        return 'text'
    return None


def write_pdf(slides, dest):
    pages = []
    for p in slides:
        with Image.open(p) as im:
            pages.append(im.convert('RGB'))
    pages[0].save(dest, 'PDF', save_all=True, append_images=pages[1:], resolution=72.0, quality=95)


def package_asset(row, entry, out_dir, dest, platform):
    """Copy what one platform needs into dest. Returns the file names written."""
    aid, kind = row['Asset ID'].strip(), kind_of(row['Format'])
    stem = f'{aid}_{platform}'
    src = out_dir / entry['folder']
    made = []
    if kind == 'video':
        shutil.copyfile(src / 'video.mp4', dest / f'{stem}.mp4'); made.append(f'{stem}.mp4')
        if (src / 'cover.png').is_file():
            shutil.copyfile(src / 'cover.png', dest / f'{stem}_cover.png'); made.append(f'{stem}_cover.png')
    elif kind == 'card':
        shutil.copyfile(src / 'card.png', dest / f'{stem}.png'); made.append(f'{stem}.png')
    else:
        slides = sorted(src.glob('slide_*.png'))
        if not slides:
            raise FileNotFoundError(f'no slides in {src}')
        if platform == 'LinkedIn':                 # LinkedIn carousels are uploaded as one document
            write_pdf(slides, dest / f'{stem}.pdf'); made.append(f'{stem}.pdf')
        else:
            for i, p in enumerate(slides, 1):
                shutil.copyfile(p, dest / f'{stem}_{i:02d}.png'); made.append(f'{stem}_{i:02d}.png')
    (dest / f'{stem}_alt.txt').write_text(postprocess.build_alt(entry), encoding='utf-8')
    made.append(f'{stem}_alt.txt')
    return made


def post_dir(root, brand, platform, aid):
    return root / brand / platform / aid


def is_platform_tree(folder):
    """True for a folder this tool made under posts/: nothing in it but platform folders."""
    return all(c.is_dir() and c.name in PLATFORMS for c in folder.iterdir())


def remove_post(root, aid):
    """Delete every folder a post has, under any brand and platform, so a rebuild leaves nothing stale."""
    if not root.is_dir():
        return
    for brand in root.iterdir():
        if not (brand.is_dir() and SAFE_ID.match(brand.name) and is_platform_tree(brand)):
            continue
        for platform in brand.iterdir():
            if (platform / aid).is_dir():
                shutil.rmtree(platform / aid)


def prune(root, current):
    """A full run mirrors the sheet: remove post folders for rows that have gone, then the folders left empty.

    current is {(brand, platform, asset_id)}. Only folders shaped like this tool's own output are touched:
    a top-level folder that holds nothing but platform folders. That covers a brand that left the sheet and
    the older posts/<AssetID>/<Platform>/ layout."""
    if not root.is_dir():
        return
    for brand in list(root.iterdir()):
        if not (brand.is_dir() and SAFE_ID.match(brand.name) and is_platform_tree(brand)):
            continue
        for platform in list(brand.iterdir()):
            for post in list(platform.iterdir()):
                if post.is_dir() and (brand.name, platform.name, post.name) not in current:
                    shutil.rmtree(post)
                elif post.is_file() and not any(b == brand.name for b, _, _ in current):
                    post.unlink()                  # a file from the older layout, where this was the post folder
            if not any(platform.iterdir()):
                platform.rmdir()
        if not any(brand.iterdir()):
            brand.rmdir()


def run(out_dir, csv_path, only=None):
    """Returns (folders_written, skipped, schedule_rows)."""
    out_dir = Path(out_dir)
    manifest_path = out_dir / 'manifest.json'
    manifest = {e['asset']: e for e in json.loads(manifest_path.read_text(encoding='utf-8'))} if manifest_path.is_file() else {}
    with open(csv_path, newline='', encoding='utf-8-sig') as f:
        rows = list(csv.DictReader(f))
    root = out_dir / 'posts'
    written = skipped = 0
    schedule = []
    seen = set()
    current = set()
    for row in rows:
        aid, kind = (row.get('Asset ID') or '').strip(), kind_of(row.get('Format'))
        if not kind or not aid or aid.lower() == 'text only':
            continue
        if only and aid not in only:
            continue
        # The ID and the brand become folders that are deleted and rebuilt, so each must be a single plain name.
        if not SAFE_ID.match(aid):
            warn(f'{aid!r}: not a usable Asset ID (letters, numbers, - and _ only), skipped'); skipped += 1; continue
        brand = (row.get('Brand') or '').strip()
        if not SAFE_ID.match(brand):
            warn(f'{aid}: {brand!r} is not a usable Brand (letters, numbers, - and _ only), skipped'); skipped += 1; continue
        if aid in seen:
            warn(f'{aid}: Asset ID used by more than one row, later row skipped'); skipped += 1; continue
        seen.add(aid)
        remove_post(root, aid)                     # rebuilt whole, so no stale platform or brand folders remain
        platforms = platforms_for(row)
        if not platforms:
            warn(f'{aid}: no platform set, skipped'); skipped += 1; continue
        entry = manifest.get(aid)
        if kind != 'text' and not entry:
            warn(f'{aid}: not rendered yet, skipped'); skipped += 1; continue
        captions = captions_in(row.get('Content') or '', kind == 'text')
        for platform in platforms:
            dest = post_dir(root, brand, platform, aid)
            if dest.resolve().parent.parent.parent != root.resolve():
                warn(f'{aid}/{platform}: folder would fall outside {root}, skipped'); skipped += 1; continue
            dest.mkdir(parents=True)
            stem = f'{aid}_{platform}'
            try:
                files = [] if kind == 'text' else package_asset(row, entry, out_dir, dest, platform)
            except OSError as e:
                warn(f'{aid}/{platform}: {e}, skipped'); shutil.rmtree(dest); skipped += 1; continue
            text, notes = caption_for(platform, captions)
            name = f'{stem}_post.txt' if kind == 'text' else f'{stem}_caption.txt'
            (dest / name).write_text(text, encoding='utf-8')
            for note in notes:
                warn(f'{aid}/{platform}: {note}')
            written += 1
            current.add((brand, platform, aid))
            schedule.append({'_order': (gallery.parse_week_day(row.get('Week / day', '')), len(schedule)),
                             'Week / day': row.get('Week / day', ''), 'Post': f'{brand}/{platform}/{aid}', 'Brand': brand,
                             'Format': row.get('Format', ''), 'Title': row.get('Title', ''), 'Files': len(files) + 1,
                             'Check before posting': row.get('Check before posting', '')})
    schedule.sort(key=lambda s: s.pop('_order'))   # calendar order; rows on the same day keep sheet order
    if not only:
        # A full run mirrors the sheet: folders for rows that have gone are removed, and the schedule is rewritten.
        prune(root, current)
        sched = root / 'schedule.csv'
        if schedule:
            with open(sched, 'w', newline='', encoding='utf-8') as f:
                w = csv.DictWriter(f, list(schedule[0])); w.writeheader(); w.writerows(schedule)
        elif sched.is_file():
            sched.unlink()
    return written, skipped, schedule


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split('\n')[0])
    ap.add_argument('out_dir', help='render.py output folder (contains manifest.json)')
    ap.add_argument('--csv', required=True, help='sheet CSV export')
    ap.add_argument('--only', default='', help='comma-separated Asset IDs')
    a = ap.parse_args(argv)
    only = {s.strip() for s in a.only.split(',') if s.strip()} or None
    if not Path(a.csv).is_file():
        print(f'error: {a.csv} not found', file=sys.stderr); return 2
    written, skipped, _ = run(a.out_dir, a.csv, only)
    print(f'package: {written} platform folders written to {Path(a.out_dir) / "posts"}, {skipped} skipped')
    return 0


if __name__ == '__main__':
    sys.exit(main())
