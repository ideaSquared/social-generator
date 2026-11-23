#!/usr/bin/env python3
"""Sort rendered assets into one folder per post and platform, ready to upload.

    python package.py out --csv posts.csv [--only ADS-C01,CG-X03]

Reads the sheet CSV and render.py's output folder, and writes:

    out/posts/<AssetID>/<Platform>/<AssetID>_<Platform>_...

One folder for every platform a row is posted to (its Platform plus everything in "Also post to").
Each folder holds only what that platform needs, with the caption adjusted for it, so nothing has
to be worked out at posting time. No AI: the same sheet and output always give the same folders.
"""
import argparse, csv, json, re, shutil, sys
from pathlib import Path

from PIL import Image

import postprocess

PLATFORMS = ('Instagram', 'Facebook', 'TikTok', 'LinkedIn', 'X')

# ---------------------------------------------------------------- per-platform caption rules
# hashtags: the most a caption keeps (the sheet lists them most important first).
# links: False where a link in a caption cannot be tapped, so it is swapped for LINK_NOTE.
RULES = {
    'Instagram': dict(hashtags=5, links=False),
    'TikTok': dict(hashtags=4, links=False),
    'Facebook': dict(hashtags=2, links=True),
    'LinkedIn': dict(hashtags=3, links=True),
    'X': dict(hashtags=2, links=True, limit=280),
}
LINK_NOTE = 'Link in bio.'
X_URL_LENGTH = 23           # X counts every link as 23 characters
URL_RE = re.compile(r'(?:https?://)?(?:[a-z0-9-]+\.)+(?:com|co\.uk|org|uk|io|app)(?:/\S*)?', re.I)
TAG_RE = re.compile(r'#\w+')
BLOCK_RE = re.compile(r'(?m)^Caption(?: for (\w+))?:[ \t]*')


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


def captions_in(content, is_text_post):
    """{'': the general caption, 'Instagram': an override, ...} from a Content cell.

    A text post has no Caption: line, because the whole cell is the post."""
    if is_text_post:
        return {'': content.strip()}
    parts = BLOCK_RE.split(content)             # [script, name, text, name, text, ...]
    found = {}
    for name, text in zip(parts[1::2], parts[2::2]):
        found[(name or '').strip()] = text.strip()
    return found


def split_tags(caption):
    """(body, hashtags) where hashtags are the ones on trailing lines made only of hashtags."""
    lines = caption.rstrip().split('\n')
    tags = []
    while lines and lines[-1].strip() and all(t.startswith('#') for t in lines[-1].split()):
        tags = lines.pop().split() + tags
    return '\n'.join(lines).rstrip(), tags


def x_length(text):
    return len(URL_RE.sub('x' * X_URL_LENGTH, text))


def caption_for(platform, captions):
    """The caption to paste on one platform. Returns (text, [warnings])."""
    notes = []
    override = next((v for k, v in captions.items() if k.lower() == platform.lower()), None)
    if override is not None:
        text = override                           # written for this platform: used as it is
    else:
        rule = RULES[platform]
        body, tags = split_tags(captions.get('', ''))
        if not rule['links'] and URL_RE.search(body):
            kept = []
            for line in body.split('\n'):
                stripped = URL_RE.sub('', line).strip()
                if URL_RE.search(line) and not re.search(r'\w', stripped):
                    continue                       # the line was only a link
                kept.append(URL_RE.sub('', line).rstrip() if URL_RE.search(line) else line)
            body = '\n'.join(kept).rstrip()
            if LINK_NOTE.lower() not in body.lower():
                body += '\n\n' + LINK_NOTE
        body = re.sub(r'\n{3,}', '\n\n', body)
        tags = tags[:rule['hashtags']]
        text = body + ('\n\n' + ' '.join(tags) if tags else '')
    limit = RULES[platform].get('limit')
    if limit and x_length(text) > limit:
        notes.append(f'{x_length(text)} characters, over the {limit} limit')
    return text.strip() + '\n', notes


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
    for row in rows:
        aid, kind = (row.get('Asset ID') or '').strip(), kind_of(row.get('Format'))
        if not kind or not aid or aid.lower() == 'text only':
            continue
        if only and aid not in only:
            continue
        platforms = platforms_for(row)
        if not platforms:
            warn(f'{aid}: no platform set, skipped'); skipped += 1; continue
        entry = manifest.get(aid)
        if kind != 'text' and not entry:
            warn(f'{aid}: not rendered yet, skipped'); skipped += 1; continue
        if (root / aid).exists():
            shutil.rmtree(root / aid)              # rebuilt whole, so no stale platform folders remain
        captions = captions_in(row.get('Content') or '', kind == 'text')
        for platform in platforms:
            dest = root / aid / platform
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
            schedule.append({'Week / day': row.get('Week / day', ''), 'Post': f'{aid}/{platform}', 'Brand': row.get('Brand', ''),
                             'Format': row.get('Format', ''), 'Title': row.get('Title', ''), 'Files': len(files) + 1,
                             'Check before posting': row.get('Check before posting', '')})
    if schedule and not only:
        with open(root / 'schedule.csv', 'w', newline='', encoding='utf-8') as f:
            w = csv.DictWriter(f, list(schedule[0])); w.writeheader(); w.writerows(schedule)
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
