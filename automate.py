"""Run the weekly steps unattended: fetch the sheet, check it, render what changed, build the review page and the post folders.

Made for a small always-on box (see docs/automate.md and deploy/). It renders a row again whenever the text that
goes on the asset changes, so there is no need to clear "Assets made" by hand. Nothing here posts to a platform.

Settings come from the environment:

  SHEET_ID            the sheet's ID (from its URL). Needs GOOGLE_CREDENTIALS.
  GOOGLE_CREDENTIALS  path to a Google service account key (JSON). The sheet must be shared with that account.
  SHEET_TAB           tab to read. Default "Social posts".
  SHEET_WRITE_BACK    "0" to stop it filling in "Assets made". Default on when a service account is used.
  SHEET_CSV_URL       instead of the two above: a "Publish to web" CSV link. Read-only, so no write-back.
"""
import argparse, csv, datetime, hashlib, io, json, os, shutil, subprocess, sys, time, urllib.parse, urllib.request
from pathlib import Path

HERE = Path(__file__).resolve().parent
API = 'https://sheets.googleapis.com/v4/spreadsheets'
SCOPE_READ = 'https://www.googleapis.com/auth/spreadsheets.readonly'
SCOPE_WRITE = 'https://www.googleapis.com/auth/spreadsheets'
RENDER_FIELDS = ('Brand', 'Format', 'Asset ID', 'Title', 'Content', 'Pillar')   # what ends up on the asset
MADE = 'Assets made'
CARDS = ('text card', 'stat card', 'quote card')


class Failed(Exception):
    """A step failed; the run stops and is tried again next time."""


def log(msg):
    print(f'[{datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")}] {msg}', flush=True)


# ---- the sheet ------------------------------------------------------------------------------------------------

def table_to_csv(values):
    """Sheets API rows (ragged: trailing blanks are dropped) -> CSV text with every row as wide as the header."""
    if not values:
        return ''
    width = len(values[0])
    buf = io.StringIO()
    w = csv.writer(buf, lineterminator='\n')
    for row in values:
        w.writerow((list(row) + [''] * width)[:width])
    return buf.getvalue()


def read_rows(csv_text):
    return list(csv.DictReader(io.StringIO(csv_text.lstrip('﻿'))))


def google_session(credentials_path, write):
    try:
        from google.oauth2 import service_account
        from google.auth.transport.requests import AuthorizedSession
    except ImportError:
        raise Failed('reading the sheet with a service account needs: pip install -r deploy/requirements.txt')
    creds = service_account.Credentials.from_service_account_file(
        credentials_path, scopes=[SCOPE_WRITE if write else SCOPE_READ])
    return AuthorizedSession(creds)


def fetch_table(session, sheet_id, tab):
    url = f'{API}/{sheet_id}/values/{urllib.parse.quote(tab, safe="")}?valueRenderOption=FORMATTED_VALUE'
    r = session.get(url, timeout=60)
    r.raise_for_status()
    return r.json().get('values', [])


def fetch_csv_url(url):
    with urllib.request.urlopen(url, timeout=60) as r:   # noqa: S310 - the URL is the owner's own setting
        return r.read().decode('utf-8-sig')


def column_letter(index):
    """0 -> A, 25 -> Z, 26 -> AA."""
    s = ''
    index += 1
    while index:
        index, rem = divmod(index - 1, 26)
        s = chr(65 + rem) + s
    return s


def made_updates(rows, pending, tab, value):
    """-> (cells to fill in "Assets made", asset IDs they cover).

    `rows` must be freshly read: positions come from them, by Asset ID. A row whose asset text no longer matches
    what was rendered (`pending` maps asset ID -> hash) is left alone; it will be rendered again next pass.
    """
    header = list(rows[0]) if rows else []
    if MADE not in header:
        return [], set()
    col = column_letter(header.index(MADE))
    quoted = "'" + tab.replace("'", "''") + "'"
    updates, done = [], set()
    for n, row in enumerate(rows, 2):            # sheet rows 2, 3, ... in order
        aid = (row.get('Asset ID') or '').strip()
        if aid in pending and aid not in done and renderable(row) and row_hash(row) == pending[aid]:
            updates.append({'range': f'{quoted}!{col}{n}', 'values': [[value]]})
            done.add(aid)
    return updates, done


def write_back(session, sheet_id, updates):
    r = session.post(f'{API}/{sheet_id}/values:batchUpdate', json={'valueInputOption': 'USER_ENTERED', 'data': updates},
                     timeout=60)
    r.raise_for_status()


# ---- what needs doing -----------------------------------------------------------------------------------------

def renderable(row):
    fmt = (row.get('Format') or '').strip()
    aid = (row.get('Asset ID') or '').strip()
    return bool(aid) and aid.lower() != 'text only' and (
        fmt.lower() in CARDS or fmt.startswith('Text-on-screen') or fmt.startswith('Graphic'))


def row_hash(row):
    return hashlib.sha256(json.dumps([row.get(k) or '' for k in RENDER_FIELDS], ensure_ascii=False).encode()).hexdigest()


def fingerprint(rows):
    """Hash of the whole tab, ignoring "Assets made" so this tool's own write-back does not look like an edit."""
    data = [[k, v or ''] for row in rows for k, v in sorted(row.items(), key=lambda kv: str(kv[0])) if k != MADE]
    return hashlib.sha256(json.dumps(data, ensure_ascii=False, default=str).encode()).hexdigest()


def asset_files(entry):
    """The media files render.py writes for a manifest entry, relative to the output folder."""
    folder = entry.get('folder') or ''
    if not folder:
        return []
    count = int(entry.get('frames') or 0)
    if entry.get('video'):                       # the review page shows the frames, so they count too
        names = ['video.mp4'] + (['cover.png'] if entry.get('cover') else []) + ['frames/frame_%02d.png' % k for k in range(1, count + 1)]
    elif entry.get('card'):
        names = ['card.png']
    else:
        names = ['slide_%02d.png' % k for k in range(1, count + 1)]
    return [f'{folder}/{n}' for n in names]


def asset_complete(out, entry):
    files = asset_files(entry)
    return bool(files) and all((Path(out) / f).is_file() for f in files)


def packaged_files(out):
    """Every file package.py left under posts/, relative to the output folder."""
    root = Path(out) / 'posts'
    return sorted(str(p.relative_to(out)).replace(os.sep, '/') for p in root.rglob('*') if p.is_file()) if root.is_dir() else []


def plan(rows, hashes, manifest, out=None):
    """-> (asset IDs to render, {asset ID: hash} for every renderable row). First row wins for a repeated ID.

    With `out`, an asset with any of its image or video files missing from disk counts as not rendered."""
    current = {}
    for row in rows:
        if renderable(row):
            current.setdefault(row['Asset ID'].strip(), row_hash(row))
    made = {m['asset'] for m in manifest if out is None or asset_complete(out, m)}
    todo = sorted(a for a, h in current.items() if hashes.get(a) != h or a not in made)
    return todo, current


def inside(path, root):
    path, root = Path(path).resolve(), Path(root).resolve()
    return root in path.parents


def drop_assets(out, manifest, asset_ids):
    """Delete the rendered folders of these assets and return the manifest without them."""
    keep = []
    for m in manifest:
        if m['asset'] not in asset_ids:
            keep.append(m); continue
        folder = Path(out) / m.get('folder', '')
        if m.get('folder') and inside(folder, out) and folder.is_dir():
            shutil.rmtree(folder)
    return keep


# ---- one run --------------------------------------------------------------------------------------------------

def load_json(path, default):
    try:
        return json.loads(Path(path).read_text(encoding='utf-8'))
    except (OSError, ValueError):
        return default


def step(name, script, *args, run=subprocess.run):
    log(f'{name}...')
    code = run([sys.executable, str(HERE / script), *map(str, args)], cwd=str(HERE)).returncode
    if code:
        raise Failed(f'{name} failed (exit {code}). The lines above say which rows.')


def read_sheet(session, sheet_id, tab, url):
    return table_to_csv(fetch_table(session, sheet_id, tab)) if session else fetch_csv_url(url)


def flush_pending(session, sheet_id, tab, rows, pending, value):
    """Fill in "Assets made" for rendered rows. -> (what is still pending, a note for the status message)."""
    updates, _ = made_updates(rows, pending, tab, value)
    if not updates:
        return {}, ''            # edited or deleted since: nothing to stamp, the next pass renders them again
    try:
        write_back(session, sheet_id, updates)
    except Exception as e:       # the assets are made either way; a read-only share is the usual cause
        return pending, (f'; could not fill in "{MADE}" ({type(e).__name__}), will try again. '
                         'If this keeps happening, share the sheet with the service account as Editor.')
    return {}, f'; filled in "{MADE}" for {len(updates)} row(s)'


def run_once(out, env=os.environ, force=False, run=subprocess.run, session=None, today=None):
    """One pass. Returns a status dict; raises Failed if a step fails."""
    out = Path(out).resolve(); out.mkdir(parents=True, exist_ok=True)   # absolute: the steps run from the repo folder
    sheet_id, creds, url = env.get('SHEET_ID'), env.get('GOOGLE_CREDENTIALS'), env.get('SHEET_CSV_URL')
    tab = env.get('SHEET_TAB') or 'Social posts'
    can_write = bool(sheet_id and creds) and env.get('SHEET_WRITE_BACK', '1') != '0'
    if sheet_id and creds:
        if session is None and not Path(creds).is_file():
            raise Failed(f'service account key not found at {creds}')
        session = session or google_session(creds, can_write)
    elif url:
        session = None
    else:
        raise Failed('set SHEET_ID and GOOGLE_CREDENTIALS, or SHEET_CSV_URL')
    csv_text = read_sheet(session, sheet_id, tab, url)
    rows = read_rows(csv_text)
    if not rows or 'Asset ID' not in rows[0]:
        raise Failed(f'the "{tab}" tab came back empty or without an "Asset ID" column')

    state_path, manifest_path = out / '.state.json', out / 'manifest.json'
    state = load_json(state_path, {})
    pending = dict(state.get('pending') or {}) if can_write else {}
    stamp = (today or datetime.date.today()).isoformat()
    manifest = load_json(manifest_path, [])
    todo, current = plan(rows, {} if force else state.get('rows') or {}, manifest, out)
    gone = {m['asset'] for m in manifest} - set(current)
    mark = fingerprint(rows)

    posts = state.get('posts')

    def save(sheet, hashes):
        state_path.write_text(json.dumps({'sheet': sheet, 'rows': hashes, 'pending': pending, 'posts': posts}), encoding='utf-8')

    # Nothing to do only if the sheet is the same AND everything the last pass made is still on disk.
    intact = (out / 'index.html').is_file() and posts is not None and all((out / f).is_file() for f in posts)
    if state.get('sheet') == mark and not todo and not gone and intact:
        note = ''
        if pending:              # a write-back that failed earlier: try again without rendering anything
            pending, note = flush_pending(session, sheet_id, tab, rows, pending, stamp)
            save(mark, current)
        return {'ok': True, 'changed': bool(note), 'rendered': [], 'message': 'sheet unchanged, nothing to do' + note}

    # From here on the output is being changed, so forget "this sheet is done" until the pass finishes.
    save(None, {a: h for a, h in (state.get('rows') or {}).items() if a not in todo})
    csv_path = out / 'posts.csv'
    csv_path.write_text(csv_text, encoding='utf-8')
    step('Checking the sheet', 'checks/claims_check.py', csv_path, run=run)

    if todo or gone:
        manifest = drop_assets(out, manifest, set(todo) | gone)   # old folders go, including ones named after an old title
        manifest_path.write_text(json.dumps(manifest, indent=1, ensure_ascii=False), encoding='utf-8')
    if todo:
        only = ','.join(todo)
        step(f'Rendering {len(todo)} asset(s)', 'render.py', csv_path, '--out', out, '--only', only, run=run)
        step('Checking the images', 'checks/visual_check.py', out, run=run)
        step('PDFs and alt text', 'postprocess.py', 'all', out, '--only', only, run=run)
    step('Building the review page', 'gallery.py', out, '--csv', csv_path, run=run)
    step('Sorting into post folders', 'package.py', out, '--csv', csv_path, run=run)

    if can_write:
        pending.update({a: current[a] for a in todo})
    posts = packaged_files(out)
    save(mark, current)
    status = {'ok': True, 'changed': True, 'rendered': todo, 'message': f'{len(todo)} rendered, {len(gone)} removed'}
    if pending:
        # Rendering takes minutes and the sheet may have been sorted or edited meanwhile, so read it again and
        # find each row by Asset ID before writing.
        try:
            fresh = read_rows(read_sheet(session, sheet_id, tab, url))
        except Exception as e:
            status['message'] += f'; could not re-read the sheet to fill in "{MADE}" ({type(e).__name__}), will try again'
        else:
            pending, note = flush_pending(session, sheet_id, tab, fresh, pending, stamp)
            status['message'] += note
            save(mark, current)
    return status


def save_status(out, status):
    status = dict(status, at=datetime.datetime.now().astimezone().isoformat(timespec='seconds'))
    if status.get('changed') is False:            # keep the last real run's details, just note the check
        last = load_json(Path(out) / 'status.json', {})
        if last.get('ok'):                        # a failure that has since cleared must not keep showing
            status = dict(last, checked=status['at'])
    Path(out, 'status.json').write_text(json.dumps(status, indent=1), encoding='utf-8')


def attempt(out, force=False):
    try:
        status = run_once(out, force=force)
    except Failed as e:
        status = {'ok': False, 'changed': True, 'rendered': [], 'message': str(e)}
    except Exception as e:
        # Network or API trouble: try again next time. Only the error's type is reported, because the full text of an
        # auth error can include account details.
        status = {'ok': False, 'changed': True, 'rendered': [], 'message': f'{type(e).__name__} while running'}
    log(('OK: ' if status['ok'] else 'FAILED: ') + status['message'])
    try:
        save_status(out, status)
    except OSError as e:
        log(f'could not write status.json: {e}')
    return status['ok']


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split('\n')[0])
    ap.add_argument('--out', default='out', help='output folder (default: out)')
    ap.add_argument('--every', type=float, default=0, metavar='MINUTES', help='keep running, checking the sheet this often')
    ap.add_argument('--force', action='store_true', help='render every row again, even if nothing changed')
    a = ap.parse_args(argv)
    if a.every <= 0:
        return 0 if attempt(a.out, a.force) else 1
    force = a.force
    while True:
        attempt(a.out, force)
        force = False
        time.sleep(a.every * 60)


if __name__ == '__main__':
    sys.exit(main())
