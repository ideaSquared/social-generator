import os, sys, unittest
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..'))
import render

class ParseTests(unittest.TestCase):
    def test_stat(self):
        d = render.parse("Stat: 34,819\nLabel: dogs rehomed by ADCH members in 2024\nFootnote on asset: Source: ADCH\n\nCaption: ignored")
        self.assertEqual(d['stat'], '34,819')
        self.assertEqual(d['label'], 'dogs rehomed by ADCH members in 2024')
        self.assertEqual(d['footnote'], 'Source: ADCH')
    def test_quote(self):
        d = render.parse("Quote: Patience wins.\nBy: Sam, volunteer")
        self.assertEqual((d['quote'], d['by']), ('Patience wins.', 'Sam, volunteer'))
    def test_text_card_ignores_caption(self):
        d = render.parse("First line.\n\nSecond para.\n\nCaption: not this", 'Text card')
        self.assertEqual(d['text'], 'First line.\nSecond para.')
    def test_text_card_footnote(self):
        d = render.parse("Hello there.\nFootnote on asset: Src", 'Text card')
        self.assertEqual((d['text'], d['footnote']), ('Hello there.', 'Src'))
    def test_existing_formats_unchanged(self):
        d = render.parse("Hook: H\nBeats:\n- a\n- b\nClose: C")
        self.assertEqual((d['hook'], d['beats'], d['close']), ('H', ['a', 'b'], 'C'))

class FrameTests(unittest.TestCase):
    def test_cards_are_single_1080x1350(self):
        for content, fmt, key in (("Some text", 'Text card', 'tcard'), ("Stat: 5\nLabel: x", '', 'scard'), ("Quote: q\nBy: b", '', 'qcard')):
            fr, w, h = render.frames('T', render.parse(content, fmt))
            self.assertEqual(([f[0] for f in fr], w, h), ([key], 1080, 1350))
    def test_carousel_and_story_sizes(self):
        d = render.parse("Sub: s\nSlides:\n1. A: b\n2. C: d\nEnd: e")
        fr, w, h = render.frames('T', d); self.assertEqual((len(fr), w, h), (4, 1080, 1350))
        fr, w, h = render.frames('T', d, story=True); self.assertEqual((len(fr), w, h), (4, 1080, 1920))
    def test_video_size(self):
        fr, w, h = render.frames('T', render.parse("Hook: H\nBeats:\n- a\n- b\nClose: C"))
        self.assertEqual((len(fr), w, h), (4, 1080, 1920))
    def test_every_brand_has_card_templates(self):
        for b in render.T:
            for k in ('tcard', 'scard', 'qcard'): self.assertIn(k, render.T[b])
if __name__ == '__main__': unittest.main()
