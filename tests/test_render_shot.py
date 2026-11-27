"""Tests for render.shot: a Chrome that hangs or fails is tried again, and a real failure is reported clearly."""
import os, subprocess, sys, tempfile, unittest
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from PIL import Image
import render


class Shot(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.html = os.path.join(self.tmp.name, 'a.html'); open(self.html, 'w').write('<p>x</p>')
        self.png = os.path.join(self.tmp.name, 'a.png')
        self.calls = []

    def tearDown(self):
        self.tmp.cleanup()

    def chrome(self, *behaviours):
        """A stand-in for subprocess.run that does one thing per call: 'ok', 'hang', 'crash' or 'half'."""
        todo = list(behaviours)

        def run(cmd, **kw):
            self.calls.append(cmd)
            what = todo.pop(0)
            if what == 'hang':
                raise subprocess.TimeoutExpired(cmd, kw['timeout'])
            if what == 'crash':
                raise subprocess.CalledProcessError(1, cmd)
            Image.new('RGB', (40, 30) if what == 'ok' else (20, 30), '#123456').save(self.png)
        return run

    def test_a_hang_is_tried_again(self):
        render.shot((self.html, self.png, 40, 30), run=self.chrome('hang', 'crash', 'half', 'ok'))
        self.assertEqual(len(self.calls), 4)
        self.assertTrue(render.shot_ok(self.png, 40, 30))

    def test_each_try_has_its_own_profile_and_it_is_removed(self):
        render.shot((self.html, self.png, 40, 30), run=self.chrome('hang', 'ok'))
        profiles = [a.split('=', 1)[1] for c in self.calls for a in c if a.startswith('--user-data-dir=')]
        self.assertEqual(len(set(profiles)), 2)
        self.assertFalse(any(os.path.exists(p) for p in profiles))

    def test_the_page_is_passed_as_a_file_url(self):
        render.shot((self.html, self.png, 40, 30), run=self.chrome('ok'))
        self.assertTrue(self.calls[0][-1].startswith('file:///'))

    def test_giving_up_names_the_file_and_the_reason(self):
        with self.assertRaises(RuntimeError) as cm:
            render.shot((self.html, self.png, 40, 30), run=self.chrome(*['hang'] * render.SHOT_TRIES))
        self.assertIn('a.png', str(cm.exception))
        self.assertIn('60 seconds', str(cm.exception))

    def test_a_wrong_size_picture_is_not_accepted(self):
        with self.assertRaises(RuntimeError):
            render.shot((self.html, self.png, 40, 30), run=self.chrome(*['half'] * render.SHOT_TRIES))


if __name__ == '__main__':
    unittest.main()
