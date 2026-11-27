#!/usr/bin/env python3
"""Write the text for the sheet's posting tabs: one CSV per platform.

    python posting_tabs.py posts.csv --out out [--only ADS-C01,CG-X03]

The sheet has one tab per platform ("Post - Instagram" and so on). Each row there needs two things typed in:
the post code in column A and the text to paste in the green cell. This writes both, per platform, to

    out/posting-tabs/<Platform>.csv

The text comes from the same rules as package.py's caption files, so the sheet and out/posts never disagree.
It does not need the rendered assets, only the sheet CSV. No AI: the same sheet always gives the same files.
"""
import argparse, csv, sys
from pathlib import Path

import gallery
from captions import PLATFORMS, caption_for, captions_in
from package import SAFE_ID, kind_of, platforms_for

HEADER = ('Post code', 'Text', 'Week / day')


def warn(msg):
    print(f'warning: {msg}', file=sys.stderr)


def build(rows, only=None):
    """{platform: [{'Post code', 'Text', 'Week / day'}]} in calendar order, and the warnings raised."""
    tabs = {p: [] for p in PLATFORMS}
    notes = []
    seen = set()
    for index, row in enumerate(rows):
        aid, kind = (row.get('Asset ID') or '').strip(), kind_of(row.get('Format'))
        if not kind or not aid or aid.lower() == 'text only':
            continue
        if only and aid not in only:
            continue
        if not SAFE_ID.match(aid):
            notes.append(f'{aid!r}: not a usable Asset ID (letters, numbers, - and _ only), skipped'); continue
        if aid in seen:
            notes.append(f'{aid}: Asset ID used by more than one row, later row skipped'); continue
        seen.add(aid)
        platforms = platforms_for(row)
        if not platforms:
            notes.append(f'{aid}: no platform set, skipped'); continue
        captions = captions_in(row.get('Content') or '', kind == 'text')
        week_day = (row.get('Week / day') or '').strip()
        order = gallery.parse_week_day(week_day)
        # Rows with no week (seasonal posts dated in "Scheduled for") go last, as they do on the sheet's tabs.
        key = (order == gallery.UNSCHEDULED, order, index)
        for platform in platforms:
            text, found = caption_for(platform, captions)
            notes.extend(f'{aid}/{platform}: {n}' for n in found)
            tabs[platform].append((key, {'Post code': aid, 'Text': text.rstrip('\n'), 'Week / day': week_day}))
    return {p: [entry for _, entry in sorted(items, key=lambda item: item[0])] for p, items in tabs.items()}, notes


def run(csv_path, out_dir, only=None):
    """Returns (files_written, rows_written, warnings)."""
    with open(csv_path, newline='', encoding='utf-8-sig') as f:
        rows = list(csv.DictReader(f))
    tabs, notes = build(rows, only)
    dest = Path(out_dir) / 'posting-tabs'
    dest.mkdir(parents=True, exist_ok=True)
    files = written = 0
    for platform in PLATFORMS:
        path = dest / f'{platform}.csv'
        entries = tabs[platform]
        if not entries:
            if path.is_file() and not only:
                path.unlink()                      # a full run mirrors the sheet
            continue
        # utf-8-sig so a spreadsheet opens the emoji and the non-ASCII punctuation correctly.
        with open(path, 'w', newline='', encoding='utf-8-sig') as f:
            w = csv.DictWriter(f, HEADER); w.writeheader(); w.writerows(entries)
        files += 1; written += len(entries)
    return files, written, notes


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split('\n')[0])
    ap.add_argument('csv', help='sheet CSV export of the Social posts tab')
    ap.add_argument('--out', default='out', help='output folder; files go in <out>/posting-tabs')
    ap.add_argument('--only', default='', help='comma-separated Asset IDs')
    a = ap.parse_args(argv)
    only = {s.strip() for s in a.only.split(',') if s.strip()} or None
    if not Path(a.csv).is_file():
        print(f'error: {a.csv} not found', file=sys.stderr); return 2
    files, written, notes = run(a.csv, a.out, only)
    for note in notes:
        warn(note)
    print(f'posting tabs: {written} rows in {files} files written to {Path(a.out) / "posting-tabs"}')
    return 0


if __name__ == '__main__':
    sys.exit(main())
