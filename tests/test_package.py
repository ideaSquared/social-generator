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
        # Split by brand, then platform, then post.
        self.assertEqual(self.names(), ['AdoptDontShop', 'CreatrGrid', 'ideaSquared', 'schedule.csv'])
        self.assertEqual(self.names('ideaSquared'), ['Facebook', 'Instagram', 'LinkedIn'])
        self.assertEqual(self.names('AdoptDontShop'), ['Instagram', 'TikTok'])
        self.assertEqual(self.names('ideaSquared', 'LinkedIn'), ['ISQ-C01'])
        self.assertEqual(self.names('ideaSquared', 'LinkedIn', 'ISQ-C01'), ['ISQ-C01_LinkedIn.pdf', 'ISQ-C01_LinkedIn_alt.txt', 'ISQ-C01_LinkedIn_caption.txt'])
        self.assertEqual(self.names('ideaSquared', 'Instagram', 'ISQ-C01'), ['ISQ-C01_Instagram_01.png', 'ISQ-C01_Instagram_02.png', 'ISQ-C01_Instagram_alt.txt', 'ISQ-C01_Instagram_caption.txt'])
        self.assertEqual(self.names('AdoptDontShop', 'TikTok', 'ADS-V01'), ['ADS-V01_TikTok.mp4', 'ADS-V01_TikTok_alt.txt', 'ADS-V01_TikTok_caption.txt', 'ADS-V01_TikTok_cover.png'])
        self.assertEqual(self.names('CreatrGrid', 'X', 'CG-X01'), ['CG-X01_X_post.txt'])
        # Calendar order (Tue, Wed, Fri), not sheet order; platforms keep their order within a post.
        self.assertEqual([s['Post'] for s in schedule], ['CreatrGrid/X/CG-X01', 'ideaSquared/LinkedIn/ISQ-C01', 'ideaSquared/Instagram/ISQ-C01',
                                                         'ideaSquared/Facebook/ISQ-C01', 'AdoptDontShop/TikTok/ADS-V01', 'AdoptDontShop/Instagram/ADS-V01'])
        self.assertTrue((self.out / 'posts' / 'schedule.csv').is_file())

    def test_captions_differ_by_platform(self):
        package.run(self.out, self.csv)
        read = lambda p: (self.out / 'posts' / 'ideaSquared' / p / 'ISQ-C01' / f'ISQ-C01_{p}_caption.txt').read_text(encoding='utf-8')
        self.assertIn('https://ideasquared.co.uk', read('LinkedIn'))
        self.assertIn('Link in bio.', read('Instagram'))
        self.assertEqual((self.out / 'posts' / 'CreatrGrid' / 'X' / 'CG-X01' / 'CG-X01_X_post.txt').read_text(encoding='utf-8'), 'One link. creatrgrid.com\n')

    def test_rerun_clears_a_platform_that_was_removed(self):
        package.run(self.out, self.csv)
        self.csv.write_text(self.csv.read_text(encoding='utf-8').replace('"Instagram, Facebook"', 'Instagram'), encoding='utf-8')
        package.run(self.out, self.csv)
        self.assertEqual(self.names('ideaSquared'), ['Instagram', 'LinkedIn'])

    def test_only(self):
        written, _, _ = package.run(self.out, self.csv, {'CG-X01'})
        self.assertEqual(written, 1)
        self.assertEqual(self.names(), ['CreatrGrid'])
        self.assertEqual(self.names('CreatrGrid', 'X'), ['CG-X01'])

    def test_unsafe_asset_ids_never_touch_other_folders(self):
        victim = self.out / 'victim'; victim.mkdir(); (victim / 'keep.txt').write_text('x')
        self.csv.write_text(HEAD + 'CreatrGrid,X,,Text post,../victim,T,Hello,Week 1 · Tue,\n'
                            + 'CreatrGrid,X,,Text post,/tmp/abs,T,Hello,Week 1 · Tue,\n'
                            + 'CreatrGrid,X,,Text post,..,T,Hello,Week 1 · Tue,\n', encoding='utf-8')
        written, skipped, _ = package.run(self.out, self.csv)
        self.assertEqual((written, skipped), (0, 3))
        self.assertTrue((victim / 'keep.txt').is_file())

    def test_full_run_removes_posts_that_left_the_sheet(self):
        package.run(self.out, self.csv)
        self.assertTrue((self.out / 'posts' / 'schedule.csv').is_file())
        lines = self.csv.read_text(encoding='utf-8').split('\nCreatrGrid,X')
        self.csv.write_text(lines[0] + '\n', encoding='utf-8')            # CG-X01 and CG-C99 rows removed
        package.run(self.out, self.csv)
        self.assertEqual(self.names(), ['AdoptDontShop', 'ideaSquared', 'schedule.csv'])
        self.csv.write_text(HEAD, encoding='utf-8')                        # nothing left
        package.run(self.out, self.csv)
        self.assertEqual(self.names(), [])

    def test_only_leaves_other_posts_alone(self):
        package.run(self.out, self.csv)
        package.run(self.out, self.csv, {'CG-X01'})
        self.assertEqual(self.names('ideaSquared', 'LinkedIn'), ['ISQ-C01'])

    def test_row_that_lost_its_platforms_is_cleared(self):
        package.run(self.out, self.csv)
        self.csv.write_text(self.csv.read_text(encoding='utf-8').replace('CreatrGrid,X,,Text post,CG-X01', 'CreatrGrid,,,Text post,CG-X01'), encoding='utf-8')
        package.run(self.out, self.csv)
        self.assertNotIn('CreatrGrid', self.names())

    def test_a_post_that_changes_brand_moves_and_leaves_nothing_behind(self):
        package.run(self.out, self.csv)
        self.csv.write_text(self.csv.read_text(encoding='utf-8').replace('CreatrGrid,X,,Text post,CG-X01', 'ideaSquared,X,,Text post,CG-X01'), encoding='utf-8')
        package.run(self.out, self.csv, {'CG-X01'})                         # even a partial run clears the old brand's copy
        self.assertEqual(self.names('ideaSquared', 'X'), ['CG-X01'])
        self.assertFalse((self.out / 'posts' / 'CreatrGrid' / 'X' / 'CG-X01').exists())

    def test_full_run_removes_the_older_layout(self):
        old = self.out / 'posts' / 'ISQ-C01' / 'LinkedIn'; old.mkdir(parents=True)
        (old / 'ISQ-C01_LinkedIn_caption.txt').write_text('old')
        package.run(self.out, self.csv)
        self.assertEqual(self.names(), ['AdoptDontShop', 'CreatrGrid', 'ideaSquared', 'schedule.csv'])

    def test_folders_this_tool_did_not_make_are_left_alone(self):
        mine = self.out / 'posts' / 'notes'; mine.mkdir(parents=True); (mine / 'keep.txt').write_text('x')
        deep = self.out / 'posts' / 'drafts' / 'Instagram'; deep.mkdir(parents=True)
        (self.out / 'posts' / 'drafts' / 'readme.txt').write_text('x'); (deep / 'keep.txt').write_text('x')
        package.run(self.out, self.csv)
        self.assertTrue((mine / 'keep.txt').is_file())
        self.assertTrue((deep / 'keep.txt').is_file())

    def test_a_row_with_an_unusable_brand_is_skipped(self):
        victim = self.out / 'victim'; victim.mkdir(); (victim / 'keep.txt').write_text('x')
        self.csv.write_text(HEAD + '../victim,X,,Text post,CG-X01,T,Hello,Week 1 · Tue,\n'
                            + ',X,,Text post,CG-X02,T,Hello,Week 1 · Tue,\n', encoding='utf-8')
        written, skipped, _ = package.run(self.out, self.csv)
        self.assertEqual((written, skipped), (0, 2))
        self.assertTrue((victim / 'keep.txt').is_file())

    def test_text_post_override(self):
        self.csv.write_text(HEAD + 'CreatrGrid,X,LinkedIn,Text post,CG-X01,T,"General text.\nCaption: still text\n\nCaption for X: Short text",Week 1 · Tue,\n', encoding='utf-8')
        package.run(self.out, self.csv)
        read = lambda p: (self.out / 'posts' / 'CreatrGrid' / p / 'CG-X01' / f'CG-X01_{p}_post.txt').read_text(encoding='utf-8')
        self.assertEqual(read('X'), 'Short text\n')
        self.assertEqual(read('LinkedIn'), 'General text.\nCaption: still text\n')


class Urls(unittest.TestCase):
    def strip(self, text):
        return package.caption_for('Instagram', {'': text})[0]

    def test_query_strings_and_fragments_go_with_the_link(self):
        self.assertNotIn('utm', self.strip('Read it.\nhttps://ideasquared.co.uk?utm_source=instagram#top'))
        self.assertNotIn('utm', self.strip('See creatrgrid.com/pricing?utm=x for more.'))

    def test_other_domains_and_word_boundaries(self):
        self.assertNotIn('example.net', self.strip('Go to example.net now.'))
        self.assertIn('acme.company', self.strip('The acme.company file.'))
        self.assertNotIn('Link in bio', self.strip('The acme.company file.'))

    def test_trailing_punctuation_stays(self):
        self.assertEqual(self.strip('Start at creatrgrid.com.'), 'Start at .\n\nLink in bio.\n')

    def test_x_counts_a_long_link_as_23(self):
        import captions
        self.assertEqual(captions.x_length('a https://example.com/' + 'p' * 80), 2 + 23)


class SharedCaptionRules(unittest.TestCase):
    CONTENT = 'Hook: a\nBeats:\n- b\nClose: c\n\nCaption: ' + 'word ' * 70 + '\n\nCaption for X: Short.'

    def test_claims_check_uses_the_x_override(self):
        sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'checks'))
        import claims_check
        row = {'Brand': 'CreatrGrid', 'Platform': 'X', 'Title': 'T', 'Format': 'Text-on-screen video', 'Asset ID': 'CG-V99',
               'Content': self.CONTENT, 'Check before posting': 'src'}
        self.assertNotIn('x-post-too-long', [f[1] for f in claims_check.check_row(row, set())])
        row['Content'] = self.CONTENT.replace('Caption for X: Short.', '')
        self.assertIn('x-post-too-long', [f[1] for f in claims_check.check_row(dict(row, **{'Asset ID': 'CG-V98'}), set())])

    def test_gallery_copies_only_the_general_caption(self):
        import gallery
        cap = gallery.extract_caption('Sub: s\n\nCaption: General one.\n\nCaption for TikTok: Other one.', 'Graphic / carousel', 'A-1')
        self.assertEqual(cap, 'General one.')


if __name__ == '__main__':
    unittest.main()
