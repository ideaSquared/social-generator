"""Tests for posting_tabs.py: the post code and paste-ready text for each platform tab in the sheet."""
import csv, os, sys, tempfile, unittest
from pathlib import Path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import package
import posting_tabs

HEAD = 'Brand,Platform,Also post to,Format,Asset ID,Title,Content,Week / day,Check before posting\n'
ROWS = (
    'AdoptDontShop,TikTok,"Instagram, Facebook",Text-on-screen video,ADS-V01,T,"Hook: h\nBeats:\n- b\nClose: c\n\nCaption: Cap.\nhttps://ideasquared.co.uk\n\n#A #B #C #D #E #F",Week 2 · Fri,\n'
    'ideaSquared,LinkedIn,,Text post,ISQ-L01,T,"A post.\n\nSecond line.",Week 1 · Mon,\n'
    'AdoptDontShop,Instagram,,Graphic / carousel,ADS-C13,T,"Sub: s\nSlides:\n1. A: b\n\nCaption: Seasonal.",,\n'
    'CreatrGrid,Instagram,X,Text post,CG-P01,T,See it: creatrgrid.com/creator/alex,Week 1 · Tue,\n'
)


class PostingTabs(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(); self.out = Path(self.tmp.name)
        self.csv = self.out / 's.csv'
        self.csv.write_text(HEAD + ROWS, encoding='utf-8')

    def tearDown(self):
        self.tmp.cleanup()

    def read(self, platform):
        with open(self.out / 'posting-tabs' / f'{platform}.csv', newline='', encoding='utf-8-sig') as f:
            return list(csv.DictReader(f))

    def test_one_file_per_platform_in_use(self):
        files, written, notes = posting_tabs.run(self.csv, self.out)
        self.assertEqual((files, written, notes), (5, 7, []))
        self.assertEqual(sorted(p.name for p in (self.out / 'posting-tabs').iterdir()),
                         ['Facebook.csv', 'Instagram.csv', 'LinkedIn.csv', 'TikTok.csv', 'X.csv'])

    def test_rows_are_in_calendar_order_with_undated_posts_last(self):
        posting_tabs.run(self.csv, self.out)
        self.assertEqual([r['Post code'] for r in self.read('Instagram')], ['CG-P01', 'ADS-V01', 'ADS-C13'])
        self.assertEqual([r['Week / day'] for r in self.read('Instagram')], ['Week 1 · Tue', 'Week 2 · Fri', ''])

    def test_text_matches_the_caption_package_writes(self):
        posting_tabs.run(self.csv, self.out)
        caps = package.captions_in('Hook: h\n\nCaption: Cap.\nhttps://ideasquared.co.uk\n\n#A #B #C #D #E #F', False)
        for platform in ('TikTok', 'Instagram', 'Facebook'):
            row = next(r for r in self.read(platform) if r['Post code'] == 'ADS-V01')
            self.assertEqual(row['Text'], package.caption_for(platform, caps)[0].rstrip('\n'))
        self.assertEqual(self.read('TikTok')[0]['Text'], 'Cap.\n\nLink in bio.\n\n#A #B #C #D')
        self.assertEqual(self.read('Facebook')[0]['Text'], 'Cap.\nhttps://ideasquared.co.uk\n\n#A #B')

    def test_a_text_post_is_the_whole_cell(self):
        posting_tabs.run(self.csv, self.out)
        self.assertEqual(self.read('LinkedIn')[0]['Text'], 'A post.\n\nSecond line.')
        self.assertEqual(self.read('X')[0]['Text'], 'See it: creatrgrid.com/creator/alex')

    def test_over_the_x_limit_is_reported(self):
        self.csv.write_text(HEAD + 'CreatrGrid,X,,Text post,CG-X99,T,' + 'word ' * 70 + ',Week 1 · Tue,\n', encoding='utf-8')
        _, _, notes = posting_tabs.run(self.csv, self.out)
        self.assertEqual(len(notes), 1)
        self.assertIn('CG-X99/X', notes[0])

    def test_only_keeps_other_files(self):
        posting_tabs.run(self.csv, self.out)
        files, written, _ = posting_tabs.run(self.csv, self.out, {'ISQ-L01'})
        self.assertEqual((files, written), (1, 1))
        self.assertTrue((self.out / 'posting-tabs' / 'TikTok.csv').is_file())

    def test_full_run_removes_a_platform_no_longer_used(self):
        posting_tabs.run(self.csv, self.out)
        self.csv.write_text(HEAD + ROWS.split('ideaSquared,LinkedIn')[0], encoding='utf-8')     # only ADS-V01 left
        posting_tabs.run(self.csv, self.out)
        self.assertEqual(sorted(p.name for p in (self.out / 'posting-tabs').iterdir()),
                         ['Facebook.csv', 'Instagram.csv', 'TikTok.csv'])

    def test_duplicate_and_unsafe_ids_are_skipped(self):
        self.csv.write_text(HEAD + 'CreatrGrid,X,,Text post,CG-X01,T,One,Week 1 · Tue,\n'
                            + 'CreatrGrid,X,,Text post,CG-X01,T,Two,Week 1 · Wed,\n'
                            + 'CreatrGrid,X,,Text post,../x,T,Three,Week 1 · Thu,\n', encoding='utf-8')
        _, written, notes = posting_tabs.run(self.csv, self.out)
        self.assertEqual((written, len(notes)), (1, 2))
        self.assertEqual(self.read('X')[0]['Text'], 'One')

    def test_package_full_run_does_not_delete_the_files(self):
        posting_tabs.run(self.csv, self.out)
        package.run(self.out, self.csv)
        self.assertTrue((self.out / 'posting-tabs' / 'X.csv').is_file())


if __name__ == '__main__':
    unittest.main()
