import os, sys, unittest
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..'))
from PIL import Image, ImageDraw
import product_shots as ps


def shot(**kw):
    d = dict(name='a-1', brand='CreatrGrid', url='https://example.com/x', device='phone')
    d.update(kw)
    return d


class ConfigTests(unittest.TestCase):
    def test_defaults(self):
        s = ps.validate_config([shot()])[0]
        self.assertEqual(s['wait_ms'], 4000)
        self.assertEqual(s['layouts'], ['post', 'story', 'landscape'])
        self.assertEqual(s['scroll_y'], 0)
        self.assertIsNone(s['color_scheme'])

    def test_wrapped_shots_key(self):
        self.assertEqual(len(ps.validate_config({'shots': [shot()]})), 1)

    def test_collects_all_problems(self):
        with self.assertRaises(ps.ConfigError) as cm:
            ps.validate_config([shot(brand='Nope'), shot(name='b', url='ftp://x', device='tablet'),
                                shot(name='c', layouts=['square']), shot(name='d', colour='x')])
        text = '\n'.join(cm.exception.problems)
        for frag in ('brand must be', 'url is required', 'device must be', 'layouts must be', 'unknown key "colour"'):
            self.assertIn(frag, text)

    def test_duplicate_and_bad_name(self):
        with self.assertRaises(ps.ConfigError) as cm:
            ps.validate_config([shot(), shot(), shot(name='../x')])
        text = '\n'.join(cm.exception.problems)
        self.assertIn('duplicate name', text)
        self.assertIn('name is required', text)

    def test_ranges_and_types(self):
        for bad in (dict(wait_ms=-1), dict(wait_ms='4000'), dict(scroll_y=-5), dict(color_scheme='sepia'),
                    dict(sub='x'), dict(headline='h' * 200), dict(layouts=[])):
            with self.assertRaises(ps.ConfigError, msg=str(bad)):
                ps.validate_config([shot(**bad)])

    def test_empty(self):
        with self.assertRaises(ps.ConfigError):
            ps.validate_config([])

    def test_example_config_is_valid(self):
        path = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'shots.example.json')
        shots = ps.load_config(path)
        self.assertTrue(all(s['url'].startswith('https://creatrgrid.com') for s in shots))

    def test_host(self):
        self.assertEqual(ps.url_host('https://creatrgrid.com/creator/alex'), 'creatrgrid.com')
        self.assertEqual(ps.url_host('file:///tmp/x.html'), 'localhost')


class LayoutTests(unittest.TestCase):
    def test_every_combination_fits_and_never_upscales(self):
        for device, dev in ps.DEVICES.items():
            native_w = dev['w'] * dev['scale']
            for layout, (W, H) in ps.LAYOUTS.items():
                for has_text in (False, True):
                    p = ps.plan_layout(device, layout, has_text)
                    f = p['frame']
                    self.assertEqual(p['canvas'], (W, H))
                    self.assertLessEqual(f['sw'], native_w, (device, layout))
                    self.assertGreaterEqual(f['x'], 0)
                    self.assertLessEqual(f['x'] + f['ow'], W, (device, layout, has_text))
                    self.assertGreaterEqual(f['y'], 0, 'top of the page must never be cropped')
                    self.assertEqual(p['text'] is not None, has_text)
                    if layout == 'landscape':  # landscape devices are fully visible
                        self.assertLessEqual(f['y'] + f['oh'], H)
                    if has_text:
                        tx, ty, tw, th = p['text']
                        self.assertLessEqual(tx + tw, W)
                        if layout != 'landscape':
                            self.assertLessEqual(ty + th, f['y'], (device, layout))
                        else:
                            self.assertLessEqual(tx + tw, f['x'])

    def test_aspect_ratios(self):
        d = ps.phone_dims(500)
        self.assertEqual(d['sh'], round(500 * 844 / 390))
        d = ps.desktop_dims(920)
        self.assertEqual(d['sh'], round(920 * 900 / 1440))
        self.assertGreater(d['oh'], d['sh'])

    def test_fit_text_shrinks_for_long_copy(self):
        short = ps.fit_text('One link.', '', 888, 300)[0]
        long_ = ps.fit_text('One link. Every platform you post to, in one place for everyone.', 'And a sub line', 540, 300)[0]
        self.assertGreater(short, long_)
        self.assertGreaterEqual(long_, 36)

    def test_wrap_lines(self):
        self.assertEqual(ps.wrap_lines('aa bb', 10, 1000, .5), 1)
        self.assertGreater(ps.wrap_lines('aa ' * 40, 40, 300, .5), 5)


class BlankTests(unittest.TestCase):
    def test_uniform_is_blank(self):
        self.assertTrue(ps.is_blank(Image.new('RGB', (390, 844), 'white')))
        self.assertTrue(ps.is_blank(Image.new('RGB', (390, 844), (20, 24, 40))))

    def test_nearly_uniform_noise_is_blank(self):
        im = Image.new('RGB', (390, 844), 'white')
        im.putpixel((5, 5), (0, 0, 0))
        self.assertTrue(ps.is_blank(im))

    def test_sparse_error_page_like_is_blank(self):
        im = Image.new('RGB', (390, 844), 'white')
        d = ImageDraw.Draw(im)
        d.rectangle((20, 110, 55, 155), outline=(90, 90, 90), width=4)
        d.rectangle((20, 215, 250, 228), fill=(60, 60, 60))
        d.rectangle((20, 260, 330, 275), fill=(200, 200, 200))
        d.rectangle((20, 290, 250, 300), fill=(200, 200, 200))
        self.assertTrue(ps.is_blank(im))

    def test_real_content_is_not_blank(self):
        im = Image.new('RGB', (390, 844), 'white')
        d = ImageDraw.Draw(im)
        for i, c in enumerate(((124, 58, 237), (236, 72, 153), (14, 165, 233), (245, 158, 11))):
            d.rounded_rectangle((20 + (i % 2) * 180, 100 + (i // 2) * 250, 190 + (i % 2) * 180, 330 + (i // 2) * 250), 16, fill=c)
        self.assertFalse(ps.is_blank(im))

    def test_dark_page_with_content_is_not_blank(self):
        im = Image.new('RGB', (390, 844), (11, 16, 32))
        ImageDraw.Draw(im).rectangle((20, 100, 370, 500), fill=(124, 58, 237))
        self.assertFalse(ps.is_blank(im))


if __name__ == '__main__':
    unittest.main()
