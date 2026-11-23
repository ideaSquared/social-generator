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
    """`later` is what the sheet returns from the second read on (someone edited it while rendering ran)."""
    def __init__(self, values, post_error=None, later=None):
        self.values, self.post_error, self.later, self.posts, self.gets = values, post_error, later, [], []
    def get(self, url, timeout=None):
        self.gets.append(url)
        return FakeResponse({'values': self.later if self.later is not None and len(self.gets) > 1 else self.values})
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
                (folder / 'slide_01.png').write_text('png')
                man.append({'asset': aid, 'folder': f'ideaSquared/{aid}_x', 'frames': 1, 'video': False})
            mp.write_text(json.dumps(man))
        if script == 'gallery.py' and script != self.fail:
            (self.out / 'index.html').write_text('page')
        if script == 'package.py' and script != self.fail:
            (self.out / 'posts' / 'P' / 'LinkedIn').mkdir(parents=True, exist_ok=True)
            (self.out / 'posts' / 'P' / 'LinkedIn' / 'P_LinkedIn_caption.txt').write_text('caption')
            (self.out / 'posts' / 'schedule.csv').write_text('schedule')
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

    def test_write_back_cells_come_from_the_rows_given_and_skip_edited_rows(self):
        rows = automate.read_rows(automate.table_to_csv(table(TEXT, CAROUSEL, VIDEO)))
        pending = {'ISQ-V01': automate.row_hash(rows[2]), 'ISQ-C01': 'hash of older text'}
        got, done = automate.made_updates(rows, pending, "Bob's posts", '2026-11-23')
        self.assertEqual(got, [{'range': "'Bob''s posts'!I4", 'values': [['2026-11-23']]}])
        self.assertEqual(done, {'ISQ-V01'})
        no_column = [{k: v for k, v in r.items() if k != 'Assets made'} for r in rows]
        self.assertEqual(automate.made_updates(no_column, pending, 'Social posts', 'x'), ([], set()))

    def test_an_asset_with_any_media_file_missing_is_planned_again(self):
        rows = automate.read_rows(automate.table_to_csv(table(CAROUSEL)))
        _, hashes = automate.plan(rows, {}, [])
        with tempfile.TemporaryDirectory() as d:
            man = [{'asset': 'ISQ-C01', 'folder': 'i/C', 'frames': 2, 'video': False}]
            self.assertEqual(automate.plan(rows, hashes, man, d)[0], ['ISQ-C01'])        # no folder
            (Path(d) / 'i' / 'C').mkdir(parents=True)
            self.assertEqual(automate.plan(rows, hashes, man, d)[0], ['ISQ-C01'])        # empty folder
            (Path(d) / 'i' / 'C' / 'slide_01.png').write_text('x')
            self.assertEqual(automate.plan(rows, hashes, man, d)[0], ['ISQ-C01'])        # one slide of two
            (Path(d) / 'i' / 'C' / 'slide_02.png').write_text('x')
            self.assertEqual(automate.plan(rows, hashes, man, d)[0], [])

    def test_a_video_with_a_frame_missing_is_planned_again(self):
        rows = automate.read_rows(automate.table_to_csv(table(VIDEO)))
        _, hashes = automate.plan(rows, {}, [])
        with tempfile.TemporaryDirectory() as d:
            man = [{'asset': 'ISQ-V01', 'folder': 'i/V', 'frames': 2, 'video': True, 'cover': True}]
            folder = Path(d) / 'i' / 'V'; (folder / 'frames').mkdir(parents=True)
            for name in ('video.mp4', 'cover.png', 'frames/frame_01.png', 'frames/frame_02.png'):
                (folder / name).write_text('x')
            self.assertEqual(automate.plan(rows, hashes, man, d)[0], [])
            (folder / 'frames' / 'frame_02.png').unlink()
            self.assertEqual(automate.plan(rows, hashes, man, d)[0], ['ISQ-V01'])

    def test_expected_media_files_per_kind(self):
        self.assertEqual(automate.asset_files({'folder': 'b/V', 'video': True, 'cover': True, 'frames': 2}),
                         ['b/V/video.mp4', 'b/V/cover.png', 'b/V/frames/frame_01.png', 'b/V/frames/frame_02.png'])
        self.assertEqual(automate.asset_files({'folder': 'b/Q', 'video': False, 'card': True, 'frames': 1}), ['b/Q/card.png'])
        self.assertEqual(automate.asset_files({'folder': 'b/C', 'video': False, 'frames': 2}), ['b/C/slide_01.png', 'b/C/slide_02.png'])
        self.assertEqual(automate.asset_files({'folder': ''}), [])

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
        self.assertIsNone(json.loads((self.out / '.state.json').read_text())['sheet'])
        status, _, run = self.go(table(CAROUSEL))
        self.assertEqual(status['rendered'], ['ISQ-C01'])

    def test_a_failed_image_check_does_not_mark_the_rows_made(self):
        session = FakeSession(table(CAROUSEL))
        with self.assertRaises(automate.Failed):
            self.go(None, session=session, run=FakeRun(self.out, fail='visual_check.py'))
        self.assertEqual(session.posts, [])

    def test_write_back_can_be_turned_off(self):
        _, session, _ = self.go(table(CAROUSEL), env=dict(ENV, SHEET_WRITE_BACK='0'))
        self.assertEqual(session.posts, [])

    def test_a_failed_write_back_is_not_fatal_and_is_retried_without_rendering(self):
        status, _, _ = self.go(None, session=FakeSession(table(VIDEO), post_error=PermissionError('secret detail')))
        self.assertTrue(status['ok']); self.assertIn('Editor', status['message']); self.assertNotIn('secret detail', status['message'])
        status, session, run = self.go(table(VIDEO))
        self.assertEqual(run.calls, [])
        self.assertEqual([u['range'] for u in session.posts[0][1]['data']], ["'Social posts'!I2"])
        self.assertIn('filled in', status['message'])
        _, session, _ = self.go(table(VIDEO))
        self.assertEqual(session.posts, [])                                   # done once, not every pass

    def test_write_back_follows_rows_that_moved_while_rendering(self):
        session = FakeSession(table(CAROUSEL, VIDEO), later=table(TEXT, VIDEO, CAROUSEL))    # sorted meanwhile
        self.go(None, session=session)
        self.assertEqual(sorted(u['range'] for u in session.posts[0][1]['data']), ["'Social posts'!I3", "'Social posts'!I4"])
        self.assertEqual(len(session.gets), 2)

    def test_write_back_skips_a_row_edited_or_moved_to_another_column_layout_while_rendering(self):
        edited = CAROUSEL[:6] + ['Changed title'] + CAROUSEL[7:]
        session = FakeSession(table(CAROUSEL, VIDEO), later=[['Assets made'] + HEADER[:-1], [''] + edited, [''] + VIDEO])
        self.go(None, session=session)
        self.assertEqual([u['range'] for u in session.posts[0][1]['data']], ["'Social posts'!A3"])   # only the video, in the column's new place

    def test_relative_output_folder_is_made_absolute_for_the_steps(self):
        here = os.getcwd(); os.chdir(self.tmp.name); self.addCleanup(os.chdir, here)
        run = FakeRun(Path(self.tmp.name).resolve() / 'out')
        automate.run_once('out', env=ENV, run=run, session=FakeSession(table(CAROUSEL)), today=DAY)
        for script, args in run.calls:
            for a in args:
                if 'out' in Path(a).parts or a.endswith('posts.csv'):
                    self.assertTrue(os.path.isabs(a), (script, a))

    def test_missing_output_is_rebuilt_even_when_the_sheet_is_unchanged(self):
        self.go(table(CAROUSEL))
        import shutil; shutil.rmtree(self.out / 'ideaSquared')
        status, _, _ = self.go(table(CAROUSEL))
        self.assertEqual(status['rendered'], ['ISQ-C01'])
        (self.out / 'index.html').unlink()
        _, _, run = self.go(table(CAROUSEL))
        self.assertEqual(run.scripts(), ['claims_check.py', 'gallery.py', 'package.py'])

    def test_a_deleted_slide_is_rendered_again_on_an_unchanged_sheet(self):
        self.go(table(CAROUSEL))
        (self.out / 'ideaSquared' / 'ISQ-C01_x' / 'slide_01.png').unlink()
        status, _, _ = self.go(table(CAROUSEL))
        self.assertEqual(status['rendered'], ['ISQ-C01'])

    def test_deleted_post_folders_are_rebuilt_on_an_unchanged_sheet_including_text_only_sheets(self):
        import shutil
        for sheet in (table(CAROUSEL), table(TEXT)):
            self.go(sheet)
            _, _, run = self.go(sheet)
            self.assertEqual(run.calls, [])
            (self.out / 'posts' / 'P' / 'LinkedIn' / 'P_LinkedIn_caption.txt').unlink()      # one file
            _, _, run = self.go(sheet)
            self.assertEqual(run.scripts(), ['claims_check.py', 'gallery.py', 'package.py'])
            shutil.rmtree(self.out / 'posts')                                                # the whole folder
            _, _, run = self.go(sheet)
            self.assertEqual(run.scripts(), ['claims_check.py', 'gallery.py', 'package.py'])

    def test_a_failed_forced_pass_is_retried_in_full(self):
        self.go(table(CAROUSEL, VIDEO))
        with self.assertRaises(automate.Failed):
            self.go(table(CAROUSEL, VIDEO), force=True, run=FakeRun(self.out, fail='visual_check.py'))
        status, _, _ = self.go(table(CAROUSEL, VIDEO))
        self.assertEqual(status['rendered'], ['ISQ-C01', 'ISQ-V01'])

    def test_a_sheet_of_text_posts_still_gets_a_review_page_and_a_removed_asset_leaves_it(self):
        _, _, run = self.go(table(TEXT))
        self.assertEqual(run.scripts(), ['claims_check.py', 'gallery.py', 'package.py'])
        self.go(table(TEXT, CAROUSEL))
        _, _, run = self.go(table(TEXT))
        self.assertIn('gallery.py', run.scripts())

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


class Status(unittest.TestCase):
    def test_a_cleared_failure_stops_showing(self):
        with tempfile.TemporaryDirectory() as d:
            idle = {'ok': True, 'changed': False, 'rendered': [], 'message': 'sheet unchanged, nothing to do'}
            automate.save_status(d, {'ok': False, 'changed': True, 'rendered': [], 'message': 'URLError while running'})
            automate.save_status(d, idle)
            self.assertTrue(json.loads(Path(d, 'status.json').read_text())['ok'])
            automate.save_status(d, {'ok': True, 'changed': True, 'rendered': ['A'], 'message': '1 rendered, 0 removed'})
            automate.save_status(d, idle)
            got = json.loads(Path(d, 'status.json').read_text())
            self.assertEqual(got['rendered'], ['A']); self.assertIn('checked', got)


if __name__ == '__main__':
    unittest.main()
