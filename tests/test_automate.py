"""Tests for automate.py: what it decides to render, what it writes back, and that a failed step stops the run."""
import datetime, json, os, sys, tempfile, unittest
from pathlib import Path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import automate

HEADER = ['Week / day', 'Brand', 'Platform', 'Format', 'Asset ID', 'Pillar', 'Title', 'Content', 'Assets made']


def table(*rows):
    return [HEADER] + [list(r) for r in rows]


CAROUSEL = ['Week 1 Tue', 'ideaSquared', 'LinkedIn', 'Graphic / carousel', 'ISQ-C01', 'Studio', 'A title', 'Slides:\n1. One: two']
VIDEO = ['Week 1 Wed', 'ideaSquared', 'TikTok', 'Text-on-screen video', 'ISQ-V01', 'Studio', 'A video', 'Hook: hi']
TEXT = ['Week 1 Mon', 'ideaSquared', 'LinkedIn', 'Text post', 'ISQ-L01', 'Studio', 'A post', 'Hello']


class FakeResponse:
    def __init__(self, data=None, error=None): self.data, self.error = data or {}, error
    def json(self): return self.data
    def raise_for_status(self):
        if self.error: raise self.error


class FakeSession:
    def __init__(self, values, post_error=None): self.values, self.post_error, self.posts, self.gets = values, post_error, [], []
    def get(self, url, timeout=None): self.gets.append(url); return FakeResponse({'values': self.values})
    def post(self, url, json=None, timeout=None): self.posts.append((url, json)); return FakeResponse(error=self.post_error)


class FakeRun:
    """Stands in for subprocess.run: records each script call and pretends render.py wrote a manifest."""
    def __init__(self, out, fail=None): self.out, self.fail, self.calls = Path(out), fail, []
    def __call__(self, cmd, cwd=None):
        script, args = Path(cmd[1]).name, cmd[2:]
        self.calls.append((script, args))
        if script == 'render.py':
            mp = self.out / 'manifest.json'
            man = json.loads(mp.read_text()) if mp.is_file() else []
            for aid in args[args.index('--only') + 1].split(','):
                folder = self.out / 'ideaSquared' / f'{aid}_x'; folder.mkdir(parents=True, exist_ok=True)
                man.append({'asset': aid, 'folder': f'ideaSquared/{aid}_x'})
            mp.write_text(json.dumps(man))
        return type('R', (), {'returncode': 1 if script == self.fail else 0})()
    def scripts(self): return [c[0] for c in self.calls]


ENV = {'SHEET_ID': 'abc', 'GOOGLE_CREDENTIALS': '/nowhere.json'}
DAY = datetime.date(2026, 11, 23)


class Pure(unittest.TestCase):
    def test_ragged_rows_are_padded_to_the_header(self):
        rows = automate.read_rows(automate.table_to_csv(table(CAROUSEL)))
        self.assertEqual(rows[0]['Asset ID'], 'ISQ-C01')
        self.assertEqual(rows[0]['Assets made'], '')
        self.assertEqual(rows[0]['Content'], 'Slides:\n1. One: two')

    def test_column_letters(self):
        self.assertEqual([automate.column_letter(i) for i in (0, 16, 25, 26, 27)], ['A', 'Q', 'Z', 'AA', 'AB'])

    def test_text_posts_and_text_only_rows_are_not_rendered(self):
        rows = automate.read_rows(automate.table_to_csv(table(CAROUSEL, VIDEO, TEXT, CAROUSEL[:4] + ['Text only'] + CAROUSEL[5:])))
        self.assertEqual(automate.plan(rows, {}, [])[0], ['ISQ-C01', 'ISQ-V01'])

    def test_only_rows_whose_asset_text_changed_are_rendered(self):
        rows = automate.read_rows(automate.table_to_csv(table(CAROUSEL, VIDEO)))
        _, hashes = automate.plan(rows, {}, [])
        made = [{'asset': 'ISQ-C01'}, {'asset': 'ISQ-V01'}]
        self.assertEqual(automate.plan(rows, hashes, made)[0], [])
        edited = automate.read_rows(automate.table_to_csv(table(CAROUSEL[:6] + ['A new title'] + CAROUSEL[7:], VIDEO)))
        self.assertEqual(automate.plan(edited, hashes, made)[0], ['ISQ-C01'])
        moved = automate.read_rows(automate.table_to_csv(table(['Week 9 Fri'] + CAROUSEL[1:], VIDEO)))
        self.assertEqual(automate.plan(moved, hashes, made)[0], [])            # a new date is not a new asset
        self.assertEqual(automate.plan(rows, hashes, made[:1])[0], ['ISQ-V01'])   # missing from disk: render again

    def test_fingerprint_ignores_assets_made(self):
        a = automate.read_rows(automate.table_to_csv(table(CAROUSEL)))
        b = automate.read_rows(automate.table_to_csv(table(CAROUSEL + ['2026-11-23'])))
        c = automate.read_rows(automate.table_to_csv(table(['Week 2 Tue'] + CAROUSEL[1:])))
        self.assertEqual(automate.fingerprint(a), automate.fingerprint(b))
        self.assertNotEqual(automate.fingerprint(a), automate.fingerprint(c))

    def test_write_back_cells(self):
        rows = automate.read_rows(automate.table_to_csv(table(TEXT, CAROUSEL, VIDEO)))
        got = automate.made_updates(HEADER, rows, {'ISQ-V01'}, "Bob's posts", '2026-11-23')
        self.assertEqual(got, [{'range': "'Bob''s posts'!I4", 'values': [['2026-11-23']]}])
        self.assertEqual(automate.made_updates(HEADER[:-1], rows, {'ISQ-V01'}, 'Social posts', 'x'), [])

    def test_drop_assets_never_deletes_outside_the_output_folder(self):
        with tempfile.TemporaryDirectory() as d:
            out = Path(d) / 'out'; (out / 'b' / 'A_x').mkdir(parents=True); keepme = Path(d) / 'keepme'; keepme.mkdir()
            man = [{'asset': 'A', 'folder': 'b/A_x'}, {'asset': 'B', 'folder': '../keepme'}, {'asset': 'C', 'folder': ''}, {'asset': 'D', 'folder': 'b/D'}]
            left = automate.drop_assets(out, man, {'A', 'B', 'C'})
            self.assertEqual([m['asset'] for m in left], ['D'])
            self.assertFalse((out / 'b' / 'A_x').exists())
            self.assertTrue(keepme.is_dir()); self.assertTrue(out.is_dir())


class Runs(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(); self.out = Path(self.tmp.name) / 'out'
        self.addCleanup(self.tmp.cleanup)

    def go(self, values, **kw):
        session = kw.pop('session', None) or FakeSession(values)
        run = kw.pop('run', None) or FakeRun(self.out)
        return automate.run_once(self.out, env=kw.pop('env', ENV), run=run, session=session, today=DAY, **kw), session, run

    def test_first_run_renders_everything_and_fills_in_assets_made(self):
        status, session, run = self.go(table(TEXT, CAROUSEL, VIDEO))
        self.assertEqual(status['rendered'], ['ISQ-C01', 'ISQ-V01'])
        self.assertEqual(run.scripts(), ['claims_check.py', 'render.py', 'visual_check.py', 'postprocess.py', 'gallery.py', 'package.py'])
        self.assertIn('Social%20posts', session.gets[0])
        (url, body), = session.posts
        self.assertTrue(url.endswith('/abc/values:batchUpdate'))
        self.assertEqual([u['range'] for u in body['data']], ["'Social posts'!I3", "'Social posts'!I4"])
        self.assertEqual(body['data'][0]['values'], [['2026-11-23']])

    def test_unchanged_sheet_does_nothing_even_after_the_write_back(self):
        self.go(table(CAROUSEL))
        status, session, run = self.go(table(CAROUSEL + ['2026-11-23']))
        self.assertFalse(status['changed']); self.assertEqual(run.calls, []); self.assertEqual(session.posts, [])

    def test_a_schedule_change_repackages_without_rendering(self):
        self.go(table(CAROUSEL))
        status, session, run = self.go(table(['Week 5 Mon'] + CAROUSEL[1:]))
        self.assertEqual(status['rendered'], [])
        self.assertEqual(run.scripts(), ['claims_check.py', 'gallery.py', 'package.py'])
        self.assertEqual(session.posts, [])

    def test_an_edited_row_is_rendered_again_and_a_deleted_row_is_removed(self):
        self.go(table(CAROUSEL, VIDEO))
        status, _, run = self.go(table(CAROUSEL[:7] + ['Slides:\n1. New: text']))
        self.assertEqual(status['rendered'], ['ISQ-C01'])
        self.assertEqual(run.calls[1][1][-1], 'ISQ-C01')
        self.assertFalse((self.out / 'ideaSquared' / 'ISQ-V01_x').exists())
        self.assertEqual([m['asset'] for m in json.loads((self.out / 'manifest.json').read_text())], ['ISQ-C01'])

    def test_a_failed_check_stops_before_rendering_and_is_retried(self):
        with self.assertRaises(automate.Failed):
            self.go(table(CAROUSEL), run=FakeRun(self.out, fail='claims_check.py'))
        self.assertFalse((self.out / '.state.json').exists())
        status, _, run = self.go(table(CAROUSEL))
        self.assertEqual(status['rendered'], ['ISQ-C01'])

    def test_a_failed_image_check_does_not_mark_the_rows_made(self):
        session = FakeSession(table(CAROUSEL))
        with self.assertRaises(automate.Failed):
            self.go(None, session=session, run=FakeRun(self.out, fail='visual_check.py'))
        self.assertEqual(session.posts, [])

    def test_write_back_can_be_turned_off_and_its_failure_is_not_fatal(self):
        _, session, _ = self.go(table(CAROUSEL), env=dict(ENV, SHEET_WRITE_BACK='0'))
        self.assertEqual(session.posts, [])
        status, _, _ = self.go(None, session=FakeSession(table(VIDEO), post_error=PermissionError('secret detail')), force=True)
        self.assertTrue(status['ok']); self.assertIn('Editor', status['message']); self.assertNotIn('secret detail', status['message'])

    def test_force_renders_everything_again(self):
        self.go(table(CAROUSEL))
        status, _, _ = self.go(table(CAROUSEL), force=True)
        self.assertEqual(status['rendered'], ['ISQ-C01'])

    def test_missing_settings_and_empty_tabs_fail_clearly(self):
        with self.assertRaisesRegex(automate.Failed, 'SHEET_ID'):
            automate.run_once(self.out, env={})
        with self.assertRaisesRegex(automate.Failed, 'not found'):
            automate.run_once(self.out, env=ENV)
        with self.assertRaisesRegex(automate.Failed, 'empty'):
            self.go([])


if __name__ == '__main__':
    unittest.main()
