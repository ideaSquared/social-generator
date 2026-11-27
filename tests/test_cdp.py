"""Tests for cdp.py: the WebSocket framing, and (when Chrome is installed) a real capture at phone size."""
import io, os, shutil, sys, tempfile, unittest
from pathlib import Path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from PIL import Image
import cdp
from render import CHROME

FIXTURE = Path(__file__).parent / 'fixtures' / 'centred.html'
HAVE_CHROME = bool(CHROME and (os.path.isfile(CHROME) or shutil.which(CHROME)))


def decode(frame):
    stream = io.BytesIO(frame)
    return cdp.read_frame(stream.read)


class Frames(unittest.TestCase):
    def test_round_trip_at_each_length_encoding(self):
        for n in (0, 5, 125, 126, 65535, 65536):
            payload = bytes(i % 251 for i in range(n))
            self.assertEqual(decode(cdp.encode_frame(payload, mask=b'\x01\x02\x03\x04')), (True, 0x1, payload))

    def test_client_frames_are_masked(self):
        frame = cdp.encode_frame(b'hello', mask=b'\x01\x02\x03\x04')
        self.assertEqual(frame[1] & 0x80, 0x80)
        self.assertNotIn(b'hello', frame)

    def test_reads_an_unmasked_server_frame(self):
        self.assertEqual(decode(b'\x81\x02hi'), (True, 0x1, b'hi'))
        self.assertEqual(decode(b'\x01\x02hi'), (False, 0x1, b'hi'))        # not the final frame

    def test_opcode_is_kept(self):
        self.assertEqual(decode(cdp.encode_frame(b'p', 0xA, mask=b'abcd'))[1], 0xA)


class Settings(unittest.TestCase):
    def test_metrics_set_the_screen_to_the_device_size(self):
        m = cdp.metrics(390, 844, 3, True)
        self.assertEqual((m['width'], m['height'], m['screenWidth'], m['deviceScaleFactor'], m['mobile']),
                         (390, 844, 390, 3, True))

    def test_launch_does_not_depend_on_a_window_size(self):
        args = cdp.launch_args('chrome', '/tmp/p')
        self.assertFalse(any(a.startswith('--window-size') for a in args))
        self.assertIn('--user-data-dir=/tmp/p', args)


@unittest.skipUnless(HAVE_CHROME, 'Chrome is not installed')
class Capture(unittest.TestCase):
    def capture(self, **kw):
        with tempfile.TemporaryDirectory() as tmp:
            out = os.path.join(tmp, 'a.png')
            laid_out = cdp.screenshot(CHROME, os.path.join(tmp, 'profile'), FIXTURE.as_uri(), out, 390, 844, 1,
                                      mobile=True, wait_ms=200, **kw)
            with Image.open(out) as im:
                return laid_out, im.convert('RGB')

    def red_box(self, im):
        px = im.load()
        xs = [x for x in range(im.width) for y in range(0, im.height, 4) if px[x, y] == (255, 0, 0)]
        ys = [y for y in range(im.height) if px[im.width // 2, y] == (255, 0, 0)]
        return min(xs), max(xs), (min(ys) if ys else None)

    def test_phone_width_page_is_laid_out_at_phone_width_and_centred(self):
        laid_out, im = self.capture()
        self.assertEqual(laid_out, 390)
        self.assertEqual(im.size, (390, 844))
        left, right, top = self.red_box(im)
        self.assertEqual((left, right, top), (95, 294, 100))                # 200 wide, equal space each side

    def test_scroll_and_dark_mode(self):
        _, im = self.capture(scroll_y=60, color_scheme='dark')
        self.assertEqual(self.red_box(im)[2], 40)
        self.assertEqual(im.getpixel((5, 5)), (0, 0, 0))

    def test_a_page_that_cannot_load_is_an_error(self):
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaises(cdp.CDPError):
                cdp.screenshot(CHROME, os.path.join(tmp, 'profile'), 'http://127.0.0.1:9/', os.path.join(tmp, 'a.png'),
                               390, 844, 1, wait_ms=0)


if __name__ == '__main__':
    unittest.main()
