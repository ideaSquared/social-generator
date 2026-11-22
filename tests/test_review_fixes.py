"""Regression tests for review findings on the card formats and config validation."""
import json, os, sys, tempfile, unittest
from pathlib import Path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'checks'))
from PIL import Image
import claims_check, visual_check, gallery, postprocess, product_shots


def row(**kw):
    r = {'Brand': 'CreatrGrid', 'Platform': 'Instagram', 'Title': 'T', 'Content': '', 'Format': 'Text post',
         'Asset ID': 'Text only', 'Check before posting': 'source'}
    r.update(kw); return r


def rules(r, seen=None):
    return [x[1] for x in claims_check.check_row(r, set() if seen is None else seen)]


class ClaimsCards(unittest.TestCase):
    def test_card_needs_asset_id(self):
        self.assertIn('missing-asset-id', rules(row(Format='Stat card', Content='Stat: 5\nLabel: things')))

    def test_card_duplicate_id(self):
        seen = set()
        r = row(Format='Quote card', **{'Asset ID': 'CG-Q01'}, Content='Quote: Hi\nBy: Me')
        self.assertNotIn('duplicate-asset-id', rules(r, seen))
        self.assertIn('duplicate-asset-id', rules(r, seen))

    def test_card_required_content(self):
        self.assertIn('card-no-label', rules(row(Format='Stat card', **{'Asset ID': 'A'}, Content='Stat: 5')))
        self.assertIn('card-no-quote', rules(row(Format='Quote card', **{'Asset ID': 'B'}, Content='By: Me')))
        self.assertIn('card-no-text', rules(row(Format='Text card', **{'Asset ID': 'C'}, Content='Caption: hi')))

    def test_x_limit_uses_caption_for_assets(self):
        long = 'word ' * 70
        ok = row(Platform='X', Format='Text card', **{'Asset ID': 'D'}, Content=long + '\n\nCaption: short')
        self.assertNotIn('x-post-too-long', rules(ok))
        bad = row(Platform='X', Format='Text-on-screen video', **{'Asset ID': 'E'},
                  Content='Hook: a\nBeats:\n- b\nClose: c\n\nCaption: ' + long)
        self.assertIn('x-post-too-long', rules(bad))
        self.assertIn('x-post-too-long', rules(row(Platform='X', Content=long)))


class CardOutputs(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(); self.out = self.tmp.name
        folder = os.path.join(self.out, 'CreatrGrid', 'CG-S01_x'); os.makedirs(folder)
        Image.new('RGB', (1080, 1350), (20, 20, 30)).save(os.path.join(folder, 'card.png'))
        self.entry = {'asset': 'CG-S01', 'brand': 'CreatrGrid', 'title': 'x', 'folder': 'CreatrGrid/CG-S01_x',
                      'frames': 1, 'video': False, 'card': True, 'text': ['34,819 / dogs rehomed'], 'footnote': 'Source: X'}
        Path(self.out, 'manifest.json').write_text(json.dumps([self.entry]))

    def tearDown(self):
        self.tmp.cleanup()

    def test_visual_check_finds_card(self):
        self.assertEqual(len(visual_check.list_images(os.path.join(self.out, self.entry['folder']), False, True)), 1)

    def test_postprocess_skips_pdf_and_writes_alt(self):
        pdfs, alts, skipped = postprocess.run(self.out, 'all')
        self.assertEqual(pdfs, 0); self.assertEqual(skipped, 0)
        self.assertNotIn('Slide 1 of 1', postprocess.build_alt(self.entry))

    def test_gallery_uses_card_png(self):
        csvp = os.path.join(self.out, 's.csv')
        Path(csvp).write_text('Brand,Platform,Title,Content,Week / day,Asset ID,Format,Check before posting,Also post to\n'
                              'CreatrGrid,Instagram,x,"Stat: 34,819\nLabel: dogs",Week 1 · Mon,CG-S01,Stat card,src,\n', encoding='utf-8')
        outf = os.path.join(self.out, 'index.html')
        html = gallery.build_html(gallery.load_posts(csvp), gallery.load_manifest(self.out), self.out, outf)
        self.assertIn('card.png', html); self.assertNotIn('<span>Missing</span>', html)


class ShotConfig(unittest.TestCase):
    def test_bad_types_are_config_errors(self):
        base = {'name': 'a', 'brand': 'CreatrGrid', 'url': 'https://example.com'}
        for extra in ({'device': ['phone']}, {'device': 'phone', 'layouts': [['post']]}, {'device': 'phone', 'layouts': [{}]},
                      {'device': {}, 'brand': []}):
            with self.assertRaises(product_shots.ConfigError):
                product_shots.validate_config([dict(base, **extra)])


if __name__ == '__main__':
    unittest.main()
