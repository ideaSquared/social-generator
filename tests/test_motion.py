import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import motion  # noqa: E402


class DurationTests(unittest.TestCase):
    def test_title_and_end(self):
        self.assertEqual(motion.frame_duration('title', 'anything at all'), 2.8)
        self.assertEqual(motion.frame_duration('end', 'Follow along.'), 3.4)

    def test_beat_clamped(self):
        self.assertEqual(motion.frame_duration('beat', 'one two'), 2.4)
        self.assertAlmostEqual(motion.frame_duration('beat', ' '.join(['w'] * 6)), 3.2)
        self.assertEqual(motion.frame_duration('beat', ' '.join(['w'] * 40)), 5.2)

    def test_durations_positions(self):
        d = motion.durations(['hook words', 'a b c d e f', 'last'])
        self.assertEqual(d[0], 2.8)
        self.assertEqual(d[2], 3.4)
        self.assertAlmostEqual(d[1], 3.2)

    def test_total(self):
        self.assertAlmostEqual(motion.total_duration([2.8, 3.0, 3.4], 0.35), 9.55)


class CommandTests(unittest.TestCase):
    PNGS = ['a.png', 'b.png', 'c.png']
    DURS = [2.8, 3.2, 3.4]

    def graph(self, style):
        cmd = motion.build_command(self.PNGS, self.DURS, 'o.mp4', '#dc1a45', style)
        return cmd, cmd[cmd.index('-filter_complex') + 1]

    def test_inputs_and_output(self):
        cmd, _ = self.graph('calm')
        self.assertEqual(cmd[0], 'ffmpeg')
        self.assertEqual(cmd.count('-i'), 3)
        self.assertEqual(cmd[-1], 'o.mp4')
        for flag in ('-an', '+faststart', 'libx264', 'yuv420p'):
            self.assertIn(flag, cmd)
        self.assertEqual(cmd[cmd.index('-r') + 1], '30')

    def test_calm_uses_fade(self):
        _, g = self.graph('calm')
        self.assertEqual(g.count('xfade=transition=fade:duration=0.35'), 2)
        self.assertIn('offset=2.800', g)
        self.assertIn('offset=6.000', g)

    def test_lively_uses_slides(self):
        _, g = self.graph('lively')
        self.assertIn('transition=slideup:duration=0.3', g)
        self.assertIn('transition=smoothleft:duration=0.3', g)
        self.assertNotIn('transition=fade', g)

    def test_progress_bar_colour_and_height(self):
        _, g = self.graph('calm')
        self.assertIn('color=c=#dc1a45', g)
        self.assertIn('h=10', g)

    def test_input_length_includes_transition(self):
        cmd, _ = self.graph('calm')
        self.assertEqual(cmd[cmd.index('-t') + 1], '3.150')

    def test_bad_input(self):
        with self.assertRaises(ValueError):
            motion.build_command(self.PNGS, [1.0], 'o.mp4', '#fff')
        with self.assertRaises(ValueError):
            motion.build_command(self.PNGS, self.DURS, 'o.mp4', '#fff', 'wild')

    def test_accents(self):
        self.assertEqual(motion.accent_for('ideaSquared'), '#e8911a')
        self.assertEqual(motion.accent_for('CreatrGrid'), '#7c3aed')


if __name__ == '__main__':
    unittest.main()
