"""Tests for package.py: one folder per post and platform, with platform-specific captions."""
import json, os, sys, tempfile, unittest
from pathlib import Path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from PIL import Image
import package

HEAD = 'Brand,Platform,Also post to,Format,Asset ID,Title,Content,Week / day,Check before posting\n'


class Captions(unittest.TestCase):
    CAP = {'': 'Hello there.\n\nRead more.\nhttps://ideasquared.co.uk\n\n#One #Two #Three #Four #Five #Six'}

    def test_instagram_swaps_link_and_keeps_five_tags(self):
        text, notes = package.caption_for('Instagram', self.CAP)
        self.assertNotIn('ideasquared.co.uk', text)
        self.assertIn('Link in bio.', text)
        self.assertTrue(text.rstrip().endswith('#One #Two #Three #Four #Five'))
        self.assertEqual(notes, [])

    def test_tiktok_keeps_four_tags(self):
        self.assertTrue(package.caption_for('TikTok', self.CAP)[0].rstrip().endswith('#One #Two #Three #Four'))

    def test_linkedin_and_facebook_keep_the_link(self):
        for platform, tags in (('LinkedIn', '#One #Two #Three'), ('Facebook', '#One #Two')):
            text, _ = package.caption_for(platform, self.CAP)
            self.assertIn('https://ideasquared.co.uk', text)
            self.assertNotIn('Link in bio', text)
            self.assertTrue(text.rstrip().endswith(tags))

    def test_link_inside_a_sentence_is_removed_cleanly(self):
        text, _ = package.caption_for('Instagram', {'': 'Start free at creatrgrid.com today.'})
        self.assertNotIn('creatrgrid.com', text)
        self.assertIn('Link in bio.', text)

    def test_no_link_means_no_link_note(self):
        self.assertNotIn('Link in bio', package.caption_for('TikTok', {'': 'Save this.\n\n#A'})[0])

    def test_override_is_used_untouched(self):
        caps = package.captions_in('Hook: a\n\nCaption: general https://x.com\n\nCaption for TikTok: short one creatrgrid.com #a #b #c #d #e #f', False)
        self.assertEqual(package.caption_for('TikTok', caps)[0], 'short one creatrgrid.com #a #b #c #d #e #f\n')
        self.assertIn('general', package.caption_for('Facebook', caps)[0])

    def test_x_over_limit_is_reported(self):
        _, notes = package.caption_for('X', {'': 'word ' * 70})
        self.assertEqual(len(notes), 1)
        self.assertEqual(package.caption_for('X', {'': 'Short. creatrgrid.com'})[1], [])

    def test_platforms_for(self):
        self.assertEqual(package.platforms_for({'Platform': 'TikTok', 'Also post to': 'Instagram, facebook, TikTok'}), ['TikTok', 'Instagram', 'Facebook'])
        self.assertEqual(package.platforms_for({'Platform': '', 'Also post to': ''}), [])


class Folders(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(); self.out = Path(self.tmp.name)
        car = self.out / 'ideaSquared' / 'ISQ-C01_x'; car.mkdir(parents=True)
        for i in (1, 2):
            Image.new('RGB', (108, 135), (10, 20, 30)).save(car / f'slide_{i:02d}.png')
        vid = self.out / 'AdoptDontShop' / 'ADS-V01_x'; vid.mkdir(parents=True)
        (vid / 'video.mp4').write_bytes(b'mp4'); (vid / 'cover.png').write_bytes(b'png')
        manifest = [
            {'asset': 'ISQ-C01', 'brand': 'ideaSquared', 'title': 'x', 'folder': 'ideaSquared/ISQ-C01_x', 'frames': 2, 'video': False, 'text': ['A', 'B'], 'footnote': ''},
            {'asset': 'ADS-V01', 'brand': 'AdoptDontShop', 'title': 'x', 'folder': 'AdoptDontShop/ADS-V01_x', 'frames': 2, 'video': True, 'text': ['A', 'B'], 'footnote': ''},
        ]
        (self.out / 'manifest.json').write_text(json.dumps(manifest))
        self.csv = self.out / 's.csv'
        self.csv.write_text(HEAD
            + 'ideaSquared,LinkedIn,"Instagram, Facebook",Graphic / carousel,ISQ-C01,T,"Sub: s\nSlides:\n1. A: b\n\nCaption: Cap.\nhttps://ideasquared.co.uk\n\n#A #B #C #D",Week 1 · Wed,src\n'
            + 'AdoptDontShop,TikTok,Instagram,Text-on-screen video,ADS-V01,T,"Hook: h\nBeats:\n- b\nClose: c\n\nCaption: Cap.",Week 1 · Fri,\n'
            + 'CreatrGrid,X,,Text post,CG-X01,T,One link. creatrgrid.com,Week 1 · Tue,\n'
            + 'CreatrGrid,Instagram,,Graphic / carousel,CG-C99,T,"Sub: s\nSlides:\n1. A: b",Week 1 · Wed,\n', encoding='utf-8')

    def tearDown(self):
        self.tmp.cleanup()

    def names(self, *parts):
        return sorted(p.name for p in (self.out / 'posts').joinpath(*parts).iterdir())

    def test_one_folder_per_platform_with_the_right_files(self):
        written, skipped, schedule = package.run(self.out, self.csv)
        self.assertEqual((written, skipped), (6, 1))        # CG-C99 is not rendered
        self.assertEqual(self.names('ISQ-C01'), ['Facebook', 'Instagram', 'LinkedIn'])
        self.assertEqual(self.names('ISQ-C01', 'LinkedIn'), ['ISQ-C01_LinkedIn.pdf', 'ISQ-C01_LinkedIn_alt.txt', 'ISQ-C01_LinkedIn_caption.txt'])
        self.assertEqual(self.names('ISQ-C01', 'Instagram'), ['ISQ-C01_Instagram_01.png', 'ISQ-C01_Instagram_02.png', 'ISQ-C01_Instagram_alt.txt', 'ISQ-C01_Instagram_caption.txt'])
        self.assertEqual(self.names('ADS-V01', 'TikTok'), ['ADS-V01_TikTok.mp4', 'ADS-V01_TikTok_alt.txt', 'ADS-V01_TikTok_caption.txt', 'ADS-V01_TikTok_cover.png'])
        self.assertEqual(self.names('CG-X01', 'X'), ['CG-X01_X_post.txt'])
        self.assertEqual([s['Post'] for s in schedule][:3], ['ISQ-C01/LinkedIn', 'ISQ-C01/Instagram', 'ISQ-C01/Facebook'])
        self.assertTrue((self.out / 'posts' / 'schedule.csv').is_file())

    def test_captions_differ_by_platform(self):
        package.run(self.out, self.csv)
        read = lambda p: (self.out / 'posts' / 'ISQ-C01' / p / f'ISQ-C01_{p}_caption.txt').read_text(encoding='utf-8')
        self.assertIn('https://ideasquared.co.uk', read('LinkedIn'))
        self.assertIn('Link in bio.', read('Instagram'))
        self.assertEqual((self.out / 'posts' / 'CG-X01' / 'X' / 'CG-X01_X_post.txt').read_text(encoding='utf-8'), 'One link. creatrgrid.com\n')

    def test_rerun_clears_a_platform_that_was_removed(self):
        package.run(self.out, self.csv)
        self.csv.write_text(self.csv.read_text(encoding='utf-8').replace('"Instagram, Facebook"', 'Instagram'), encoding='utf-8')
        package.run(self.out, self.csv)
        self.assertEqual(self.names('ISQ-C01'), ['Instagram', 'LinkedIn'])

    def test_only(self):
        written, _, _ = package.run(self.out, self.csv, {'CG-X01'})
        self.assertEqual(written, 1)
        self.assertEqual(self.names(), ['CG-X01'])


if __name__ == '__main__':
    unittest.main()
