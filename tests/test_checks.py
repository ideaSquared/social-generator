import io
import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, 'checks'))

from PIL import Image, ImageDraw  # noqa: E402

import claims_check as cc  # noqa: E402
import visual_check as vc  # noqa: E402


# ---------------------------------------------------------------- claims
def row(**kw):
    r = dict(Brand='ideaSquared', Platform='LinkedIn', Title='T', Content='Plain text.', Format='Text post',
             **{'Asset ID': 'Text only', 'Check before posting': ''})
    for k, v in kw.items():
        r[k.replace('_', ' ')] = v
    return r


def rules(r, seen=None, level=None):
    return [(lv, rule) for lv, rule, _ in cc.check_row(r, set() if seen is None else seen) if level in (None, lv)]


VIDEO = "Hook: A hook.\nBeats:\n- One\n- Two\nClose: Bye."
CAROUSEL = "Sub: Sub.\nSlides:\n1. Head one: Body one.\n2. Head two: Body two.\nEnd: Bye."


def video(**kw):
    kw.setdefault('Asset_ID', 'V1'); kw.setdefault('Content', VIDEO)
    return row(Format='Text-on-screen video', **kw)


def carousel(**kw):
    kw.setdefault('Asset_ID', 'C1'); kw.setdefault('Content', CAROUSEL)
    return row(Format='Graphic / carousel', **kw)


class FigureRule(unittest.TestCase):
    def flagged(self, text, **kw):
        return ('ERROR', 'unevidenced-figure') in rules(row(Content=text, **kw))

    def test_positive_cases(self):
        for text in ['Up 40% this month', 'We have 1,200 users', 'Over 500 rescues', 'Costs £5 a month',
                     'Raised $2m', 'A 10x faster site', 'Done by 2030', 'A 2030 target', 'About 12k followers',
                     'Costs €3.50', 'Before 2028 we ship']:
            with self.subTest(text):
                self.assertTrue(self.flagged(text))

    def test_negative_cases(self):
        for text in ['1. First step\n2. Second step', 'Slide 1 of 5', 'Shot in 16:9, 9:16 and 1:1',
                     '#Top100 #2026 tags', 'See https://example.com/page/12345 now', 'Visit creatrgrid.com/2024',
                     'Planned for early 2027', 'Q1 2027 beta', 'Updated 22 Nov 2026', 'Three days, 3 weeks, 3 months',
                     'AGPL-3.0 licence', 'A 16x9 crop', '- 3. a bullet']:
            with self.subTest(text):
                self.assertFalse(self.flagged(text))

    def test_footnote_or_check_cell_clears_it(self):
        self.assertFalse(self.flagged('Up 40%\nFootnote on asset: Source X, 2026.'))
        self.assertFalse(self.flagged('Up 40%', Check_before_posting='ADCH 2024 summary'))
        self.assertTrue(self.flagged('Up 40%', Check_before_posting='   '))

    def test_caption_is_scanned(self):
        r = carousel(Content=CAROUSEL + '\n\nCaption: Now 5,000 strong.')
        self.assertIn(('ERROR', 'unevidenced-figure'), rules(r))

    def test_title_is_scanned(self):
        self.assertIn(('ERROR', 'unevidenced-figure'), rules(row(Title='100% free')))


class BannedPhrases(unittest.TestCase):
    def test_each_phrase(self):
        for p in cc.BANNED_PHRASES:
            with self.subTest(p):
                self.assertIn(('ERROR', 'banned-phrase'), rules(row(Content=f'We have a {p.upper()} here.')))

    def test_whole_words_only(self):
        self.assertNotIn(('ERROR', 'banned-phrase'), rules(row(Content='Pilots rescue animals; a 110x idea; waitlisting')))

    def test_plural_waitlists(self):
        self.assertIn(('ERROR', 'banned-phrase'), rules(row(Content="We won't quote waitlists.")))

    def test_allow_override(self):
        r = row(Content='We removed the waitlist claim.', Check_before_posting='allow: waitlist')
        self.assertEqual(rules(r, level='ERROR'), [])
        r = row(Content='A waitlist and 10x.', Check_before_posting='D13. allow: waitlist')
        self.assertEqual([x for x in cc.check_row(r, set()) if x[1] == 'banned-phrase' and '10x' in x[2]][0][0], 'ERROR')

    def test_allow_multiple(self):
        r = row(Content='A waitlist and Pairflix.', Check_before_posting='allow: waitlist, Pairflix')
        self.assertEqual(rules(r, level='ERROR'), [])

    def test_allow_must_name_the_phrase(self):
        r = row(Content='A waitlist.', Check_before_posting='allow: Pairflix')
        self.assertIn(('ERROR', 'banned-phrase'), rules(r))

    def test_pairflix(self):
        self.assertIn(('ERROR', 'parked-venture'), rules(row(Content='Pairflix is great')))
        self.assertIn(('ERROR', 'parked-venture'), rules(row(Title='pairflix')))
        self.assertNotIn(('ERROR', 'parked-venture'), rules(row(Content='Hello', Check_before_posting='Pairflix not named')))
        self.assertNotIn(('ERROR', 'parked-venture'), rules(row(Content='Pairflix', Check_before_posting='allow: Pairflix')))


class Structure(unittest.TestCase):
    def test_valid_rows_are_clean(self):
        self.assertEqual(rules(video()), [])
        self.assertEqual(rules(carousel()), [])

    def test_video_parts(self):
        self.assertIn(('ERROR', 'video-no-hook'), rules(video(Content="Beats:\n- a\nClose: x")))
        self.assertIn(('ERROR', 'video-no-beats'), rules(video(Content="Hook: h\nClose: x")))
        self.assertIn(('ERROR', 'video-no-close'), rules(video(Content="Hook: h\nBeats:\n- a")))

    def test_carousel_parts(self):
        self.assertIn(('ERROR', 'carousel-no-slides'), rules(carousel(Content='Sub: s\nEnd: e')))
        self.assertIn(('ERROR', 'empty-slide-body'), rules(carousel(Content="Slides:\n1. Head:\n2. B: ok\nEnd: e")))

    def test_asset_ids(self):
        self.assertIn(('ERROR', 'missing-asset-id'), rules(video(Asset_ID='')))
        self.assertIn(('ERROR', 'missing-asset-id'), rules(video(Asset_ID='Text only')))
        seen = set()
        self.assertNotIn(('ERROR', 'duplicate-asset-id'), rules(video(), seen))
        self.assertIn(('ERROR', 'duplicate-asset-id'), rules(carousel(Asset_ID='v1'), seen))
        self.assertEqual(rules(row()), [])      # text posts need no ID

    def test_brand(self):
        self.assertIn(('ERROR', 'unknown-brand'), rules(row(Brand='Pairflix2')))
        self.assertIn(('ERROR', 'unknown-brand'), rules(row(Brand='')))

    def test_x_length(self):
        self.assertIn(('ERROR', 'x-post-too-long'), rules(row(Platform='X', Content='a' * 281)))
        self.assertNotIn(('ERROR', 'x-post-too-long'), rules(row(Platform='X', Content='a' * 280)))
        self.assertNotIn(('ERROR', 'x-post-too-long'), rules(row(Platform='LinkedIn', Content='a' * 400)))
        long_url = 'https://example.com/' + 'a' * 200
        self.assertNotIn(('ERROR', 'x-post-too-long'), rules(row(Platform='X', Content='Read ' + long_url)))

    def test_parse_matches_render(self):
        sys.path.insert(0, ROOT)
        try:
            import render
        except Exception as e:                       # render.py needs lib.py and Pillow only, but stay safe
            self.skipTest(f'render.py not importable: {e}')
        for content in (VIDEO, CAROUSEL + '\nFootnote on asset: src\n\nCaption: hi\nHook: ignored'):
            a, b = render.parse(content), cc.parse(content)
            self.assertEqual(a['beats'], b['beats'])
            self.assertEqual(a['slides'], b['slides'])


class Warnings(unittest.TestCase):
    def test_long_beat_and_heading(self):
        self.assertIn(('WARNING', 'long-beat'), rules(video(Content="Hook: h\nBeats:\n- " + 'word ' * 15 + "\nClose: c")))
        self.assertNotIn(('WARNING', 'long-beat'), rules(video(Content="Hook: h\nBeats:\n- " + 'word ' * 14 + "\nClose: c")))
        self.assertIn(('WARNING', 'long-slide-heading'), rules(carousel(Content="Slides:\n1. " + 'w ' * 9 + ": body\nEnd: e")))
        self.assertNotIn(('WARNING', 'long-slide-heading'), rules(carousel(Content="Slides:\n1. " + 'w ' * 8 + ": body\nEnd: e")))

    def test_hashtags(self):
        self.assertIn(('WARNING', 'too-many-hashtags'), rules(carousel(Content=CAROUSEL + '\n\nCaption: x\n' + ' '.join(f'#t{i}' for i in range(7)))))
        self.assertNotIn(('WARNING', 'too-many-hashtags'), rules(carousel(Content=CAROUSEL + '\n\nCaption: x\n' + ' '.join(f'#t{i}' for i in range(6)))))

    def test_emoji_only_for_isq_and_cg(self):
        self.assertIn(('WARNING', 'emoji'), rules(row(Brand='ideaSquared', Content='Nice \U0001F680')))
        self.assertIn(('WARNING', 'emoji'), rules(row(Brand='CreatrGrid', Content='Nice \U0001F389')))
        self.assertNotIn(('WARNING', 'emoji'), rules(row(Brand='AdoptDontShop', Content='Nice \U0001F43E')))
        self.assertNotIn(('WARNING', 'emoji'), rules(row(Brand='ideaSquared', Content='Arrow → and ’ quote')))

    def test_american_spelling(self):
        for w in ['color', 'Organization', 'favorites', 'behavior', 'center', 'analyze']:
            with self.subTest(w):
                self.assertIn(('WARNING', 'american-spelling'), rules(row(Content=f'The {w} matters.')))
        for ok in ['colour', 'organisation', 'favourite', 'behaviour', 'centre', 'analyse', 'concentrate']:
            with self.subTest(ok):
                self.assertNotIn(('WARNING', 'american-spelling'), rules(row(Content=f'The {ok} matters.')))
        self.assertNotIn(('WARNING', 'american-spelling'), rules(row(Content='See https://example.com/color and #color')))

    def test_unresolved_check(self):
        self.assertIn(('WARNING', 'unresolved-check'), rules(row(Check_before_posting='CONFLICT: homepage differs')))
        self.assertIn(('WARNING', 'unresolved-check'), rules(row(Check_before_posting='Price is NOT confirmed')))
        self.assertNotIn(('WARNING', 'unresolved-check'), rules(row(Check_before_posting='Confirmed on 22 Nov')))


class CsvRun(unittest.TestCase):
    HEADER = 'Brand,Platform,Title,Content,Check before posting,Asset ID,Format\n'

    def run_csv(self, body, strict=False):
        with tempfile.TemporaryDirectory() as d:
            p = os.path.join(d, 's.csv')
            with open(p, 'w', encoding='utf-8') as fh:
                fh.write(self.HEADER + body)
            buf = io.StringIO()
            code = cc.run(p, strict, buf)
        return code, buf.getvalue()

    def test_exit_codes_and_format(self):
        code, out = self.run_csv('ideaSquared,LinkedIn,Hi,Up 40%,,Text only,Text post\n')
        self.assertEqual(code, 1)
        self.assertRegex(out, r'^ROW 2 Hi: ERROR unevidenced-figure: ')
        code, out = self.run_csv('ideaSquared,LinkedIn,Hi,Fine,,Text only,Text post\n')
        self.assertEqual(code, 0)

    def test_strict(self):
        body = 'ideaSquared,LinkedIn,Hi,Fine,CONFLICT: x,Text only,Text post\n'
        self.assertEqual(self.run_csv(body)[0], 0)
        self.assertEqual(self.run_csv(body, strict=True)[0], 1)


# ---------------------------------------------------------------- visual
def make_img(path, size, color=(248, 250, 252)):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    Image.new('RGB', size, color).save(path)


class VisualBase(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.tmp, True)

    def build(self, asset='ISQ-C01', brand='ideaSquared', frames=3, video=False, color=(248, 250, 252)):
        folder = f'{brand}/{asset}_x'
        size = vc.FRAME_SIZE if video else vc.SLIDE_SIZE
        for k in range(1, frames + 1):
            name = f'frames/frame_{k:02d}.png' if video else f'slide_{k:02d}.png'
            make_img(os.path.join(self.tmp, folder, name), size, color)
        entry = dict(asset=asset, brand=brand, title='t', folder=folder, frames=frames, video=video, text=[], footnote='')
        with open(os.path.join(self.tmp, 'manifest.json'), 'w') as fh:
            json.dump([entry], fh)
        return entry, os.path.join(self.tmp, folder)

    def run_check(self, **kw):
        buf = io.StringIO()
        code = vc.run(self.tmp, stream=buf, **kw)
        return code, buf.getvalue()


class VisualChecks(VisualBase):
    def test_clean(self):
        self.build()
        self.assertEqual(self.run_check()[0], 0)

    def test_missing_manifest(self):
        self.assertEqual(self.run_check()[0], 1)

    def test_missing_folder(self):
        _, f = self.build()
        shutil.rmtree(f)
        code, out = self.run_check()
        self.assertEqual(code, 1)
        self.assertIn('missing-folder', out)

    def test_frame_count(self):
        _, f = self.build()
        os.remove(os.path.join(f, 'slide_03.png'))
        code, out = self.run_check()
        self.assertEqual(code, 1)
        self.assertIn('frame-count', out)

    def test_wrong_size(self):
        _, f = self.build()
        make_img(os.path.join(f, 'slide_02.png'), (1080, 1349))
        self.assertIn('size', self.run_check()[1])
        self.assertEqual(self.run_check()[0], 1)

    def test_white_corner(self):
        _, f = self.build(color=(20, 30, 40))
        p = os.path.join(f, 'slide_01.png')
        im = Image.open(p)
        ImageDraw.Draw(im).rectangle((1070, 1340, 1079, 1349), fill=(255, 255, 255))
        im.save(p)
        code, out = self.run_check()
        self.assertEqual(code, 1)
        self.assertIn('white-corner', out)

    def test_white_everywhere_is_not_the_glitch(self):
        self.build(color=(255, 255, 255))
        self.assertEqual(self.run_check()[0], 0)

    def draw_edge_text(self, path, n=6, fill=(15, 23, 42)):
        im = Image.open(path)
        d = ImageDraw.Draw(im)
        for i in range(n):
            d.rectangle((1050, 500 + i * 40, 1079, 520 + i * 40), fill=fill)
        im.save(path)

    def test_right_edge_text_on_light_frame(self):
        _, f = self.build()
        self.draw_edge_text(os.path.join(f, 'slide_02.png'))
        code, out = self.run_check()
        self.assertEqual(code, 1)
        self.assertIn('right-edge-text', out)

    def test_dark_frame_is_skipped(self):
        _, f = self.build(color=(8, 24, 42))
        self.draw_edge_text(os.path.join(f, 'slide_02.png'), fill=(247, 246, 242))
        self.assertEqual(self.run_check()[0], 0)

    def test_patterned_frame_is_skipped(self):
        _, f = self.build()
        p = os.path.join(f, 'slide_02.png')
        im = Image.open(p)
        d = ImageDraw.Draw(im)
        for y in range(0, 1350, 20):                    # stripes covering the whole edge column
            d.rectangle((1000, y, 1079, y + 9), fill=(124, 58, 237))
        im.save(p)
        self.assertEqual(self.run_check()[0], 0)

    def test_creatrgrid_tiles_on_cover_are_ignored_but_not_elsewhere(self):
        _, f = self.build(asset='CG-C01', brand='CreatrGrid')
        cover = os.path.join(f, 'slide_01.png')
        im = Image.open(cover)
        ImageDraw.Draw(im).rectangle((918, 0, 1079, 440), fill=(124, 58, 237))   # tile bleeding off the top-right
        im.save(cover)
        self.assertEqual(self.run_check()[0], 0)
        im = Image.open(cover)
        ImageDraw.Draw(im).rectangle((1050, 600, 1079, 700), fill=(15, 23, 42))  # text below the tiles
        im.save(cover)
        self.assertEqual(self.run_check()[0], 1)
        # The same tiles on a later slide are not excused.
        _, f = self.build(asset='CG-C01', brand='CreatrGrid')
        later = os.path.join(f, 'slide_02.png')
        im = Image.open(later)
        ImageDraw.Draw(im).rectangle((918, 0, 1079, 440), fill=(124, 58, 237))
        im.save(later)
        self.assertEqual(self.run_check()[0], 1)

    def test_orphan_folder_warns_only(self):
        self.build()
        os.makedirs(os.path.join(self.tmp, 'ideaSquared', 'ISQ-C99_stray'))
        os.makedirs(os.path.join(self.tmp, '.html'))
        code, out = self.run_check()
        self.assertEqual(code, 0)
        self.assertIn('WARN ISQ-C99 not-in-manifest', out)
        self.assertNotIn('.html', out)


@unittest.skipUnless(shutil.which('ffprobe') and shutil.which('ffmpeg'), 'ffmpeg/ffprobe not installed')
class VideoChecks(VisualBase):
    def make_video(self, path, seconds, size='1080x1920'):
        subprocess.run(['ffmpeg', '-y', '-loglevel', 'error', '-f', 'lavfi', '-i',
                        f'color=c=white:s={size}:d={seconds}:r=5', '-pix_fmt', 'yuv420p', '-c:v', 'libx264',
                        '-preset', 'ultrafast', path], check=True)

    def video_case(self, seconds=8, size='1080x1920'):
        _, f = self.build(asset='ISQ-V01', frames=2, video=True)
        self.make_video(os.path.join(f, 'video.mp4'), seconds, size)
        later = time.time() + 5
        os.utime(os.path.join(f, 'video.mp4'), (later, later))
        return f

    def test_good_video(self):
        self.video_case()
        self.assertEqual(self.run_check()[0], 0)

    def test_missing_video(self):
        _, f = self.build(asset='ISQ-V01', frames=2, video=True)
        code, out = self.run_check()
        self.assertEqual(code, 1)
        self.assertIn('video-missing', out)

    def test_duration_limits(self):
        for secs in (3, 70):
            with self.subTest(secs):
                self.video_case(seconds=secs)
                code, out = self.run_check()
                self.assertEqual(code, 1)
                self.assertIn('video-duration', out)

    def test_wrong_video_size(self):
        self.video_case(size='720x1280')
        self.assertIn('video-size', self.run_check()[1])

    def test_stale_video(self):
        f = self.video_case()
        os.utime(os.path.join(f, 'video.mp4'), (1e9, 1e9))
        code, out = self.run_check()
        self.assertEqual(code, 1)
        self.assertIn('video-stale', out)
        self.assertEqual(self.run_check(skip_mtime=True)[0], 0)


if __name__ == '__main__':
    unittest.main()
