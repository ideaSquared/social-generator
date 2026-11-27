"""Tests for music.py and the places it is wired in: one track per brand under the text videos."""
import json, os, shutil, subprocess, sys, tempfile, unittest
from pathlib import Path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import motion
import music
import render

FFMPEG = shutil.which('ffmpeg') and shutil.which('ffprobe')


class Switch(unittest.TestCase):
    def test_music_is_on_unless_the_row_says_no(self):
        self.assertTrue(music.wants_music({}))
        self.assertTrue(music.wants_music({'Music': ''}))
        self.assertTrue(music.wants_music({'Music': 'Yes'}))
        for value in ('No', ' no ', 'OFF', 'none', 'Silent'):
            self.assertFalse(music.wants_music({'Music': value}), value)


class Tracks(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(); self.dir = Path(self.tmp.name)

    def tearDown(self):
        self.tmp.cleanup()

    def test_a_brand_with_no_file_has_no_track(self):
        self.assertIsNone(music.track_for('ideaSquared', self.dir))

    def test_the_file_is_named_after_the_brand(self):
        (self.dir / 'ideaSquared.mp3').write_bytes(b'x'); (self.dir / 'CreatrGrid.wav').write_bytes(b'x')
        self.assertEqual(music.track_for('ideaSquared', self.dir), str(self.dir / 'ideaSquared.mp3'))
        self.assertEqual(music.track_for(' CreatrGrid ', self.dir), str(self.dir / 'CreatrGrid.wav'))
        self.assertIsNone(music.track_for('AdoptDontShop', self.dir))

    def test_mp3_wins_when_a_brand_has_two_files(self):
        (self.dir / 'ideaSquared.wav').write_bytes(b'x'); (self.dir / 'ideaSquared.mp3').write_bytes(b'x')
        self.assertTrue(music.track_for('ideaSquared', self.dir).endswith('.mp3'))

    def test_a_brand_that_is_not_a_plain_name_never_reaches_the_disk(self):
        (self.dir.parent / 'escape.mp3').write_bytes(b'x')
        try:
            self.assertIsNone(music.track_for('../escape', self.dir))
            self.assertIsNone(music.track_for('', self.dir))
        finally:
            (self.dir.parent / 'escape.mp3').unlink()

    def test_music_dir_can_be_moved_with_an_environment_variable(self):
        old = os.environ.get('MUSIC_DIR'); os.environ['MUSIC_DIR'] = str(self.dir)
        try:
            self.assertEqual(music.music_dir(), self.dir)
        finally:
            os.environ.pop('MUSIC_DIR') if old is None else os.environ.__setitem__('MUSIC_DIR', old)


class Filter(unittest.TestCase):
    def test_cut_to_length_levelled_and_faded(self):
        f = music.audio_filter(4, 12.35)
        self.assertTrue(f.startswith('[4:a]atrim=0:12.350,'))
        self.assertIn('loudnorm=I=-18:TP=-2', f)
        self.assertIn('afade=t=in:st=0:d=0.400', f)
        self.assertIn('afade=t=out:st=11.350:d=1.000', f)
        self.assertTrue(f.endswith('[a]'))

    def test_fades_shrink_for_a_very_short_video(self):
        f = music.audio_filter(1, 1.0)
        self.assertIn('afade=t=in:st=0:d=0.250', f)
        self.assertIn('afade=t=out:st=0.500:d=0.500', f)

    def test_no_length_is_an_error(self):
        with self.assertRaises(ValueError):
            music.audio_filter(1, 0)

    def test_the_track_loops_and_the_output_stops_at_the_video_length(self):
        self.assertEqual(music.input_args('t.mp3'), ['-stream_loop', '-1', '-i', 't.mp3'])
        self.assertEqual(music.output_args(9.5), ['-map', '[a]', '-c:a', 'aac', '-b:a', '160k', '-t', '9.500'])


class Wiring(unittest.TestCase):
    PNGS, DURS = ['a.png', 'b.png', 'c.png'], [2.8, 3.0, 3.4]

    def test_render_without_a_track_is_unchanged_and_silent(self):
        cmd = render.video_cmd((self.PNGS, self.DURS, 'v.mp4', None))
        self.assertNotIn('-stream_loop', cmd); self.assertNotIn('[a]', cmd)
        self.assertEqual(cmd[-3:], ['-movflags', '+faststart', 'v.mp4'])

    def test_render_with_a_track_adds_it_after_the_frames(self):
        cmd = render.video_cmd((self.PNGS, self.DURS, 'v.mp4', 't.mp3'))
        self.assertEqual(cmd[cmd.index('-stream_loop'):cmd.index('-stream_loop') + 4], ['-stream_loop', '-1', '-i', 't.mp3'])
        fc = cmd[cmd.index('-filter_complex') + 1]
        self.assertIn('[3:a]atrim=0:9.550', fc)             # 2.8 + 3.0 + 3.4 + the 0.35 fade
        self.assertIn('-t', cmd); self.assertEqual(cmd[cmd.index('-t', cmd.index('-filter_complex')) + 1], '9.550')
        self.assertIn('aac', cmd)

    def test_motion_is_silent_without_a_track_and_has_audio_with_one(self):
        self.assertIn('-an', motion.build_command(self.PNGS, self.DURS, 'm.mp4', '#fff'))
        cmd = motion.build_command(self.PNGS, self.DURS, 'm.mp4', '#fff', 'calm', 't.mp3')
        self.assertNotIn('-an', cmd); self.assertIn('aac', cmd)
        self.assertIn('[3:a]atrim=0:9.550', cmd[cmd.index('-filter_complex') + 1])

    def test_motion_follows_what_render_recorded(self):
        with tempfile.TemporaryDirectory() as t:
            tracks = Path(t) / 'music'; tracks.mkdir(); (tracks / 'ideaSquared.mp3').write_bytes(b'x')
            man = [{'asset': 'A', 'brand': 'ideaSquared', 'folder': 'ideaSquared/A', 'frames': 2, 'video': True, 'text': ['a', 'b'], 'music': 'ideaSquared.mp3'},
                   {'asset': 'B', 'brand': 'ideaSquared', 'folder': 'ideaSquared/B', 'frames': 2, 'video': True, 'text': ['a', 'b']}]
            (Path(t) / 'manifest.json').write_text(json.dumps(man))
            old = os.environ.get('MUSIC_DIR'); os.environ['MUSIC_DIR'] = str(tracks)
            try:
                jobs = motion.load_jobs(t)
            finally:
                os.environ.pop('MUSIC_DIR') if old is None else os.environ.__setitem__('MUSIC_DIR', old)
            self.assertEqual([j[4] for j in jobs], [str(tracks / 'ideaSquared.mp3'), None])     # B's row said No


@unittest.skipUnless(FFMPEG, 'needs ffmpeg and ffprobe')
class RealVideo(unittest.TestCase):
    """Runs ffmpeg for real, on a generated tone, so the filter is known to work and not only to look right."""

    def probe(self, path):
        out = subprocess.run(['ffprobe', '-v', 'error', '-show_entries', 'stream=codec_type,codec_name:format=duration',
                              '-of', 'json', str(path)], check=True, capture_output=True, text=True).stdout
        data = json.loads(out)
        return {s['codec_type']: s['codec_name'] for s in data['streams']}, float(data['format']['duration'])

    def test_a_short_track_loops_under_a_longer_video(self):
        from PIL import Image
        with tempfile.TemporaryDirectory() as t:
            t = Path(t)
            pngs = []
            for i, colour in enumerate(((20, 40, 60), (60, 40, 20), (20, 60, 40))):
                p = t / f'f{i}.png'; Image.new('RGB', (108, 192), colour).save(p); pngs.append(str(p))
            track = t / 'tone.wav'                                        # 2 seconds, far shorter than the video
            subprocess.run(['ffmpeg', '-y', '-loglevel', 'error', '-f', 'lavfi', '-i', 'sine=frequency=440:duration=2', str(track)], check=True)
            durs = [1.0, 1.0, 1.0]
            with_music, silent = t / 'music.mp4', t / 'silent.mp4'
            render.video((pngs, durs, str(with_music), str(track)))
            render.video((pngs, durs, str(silent), None))
            streams, length = self.probe(with_music)
            self.assertEqual(streams, {'video': 'h264', 'audio': 'aac'})
            self.assertAlmostEqual(length, 3.35, delta=0.15)             # the video's length, not the track's
            streams, length = self.probe(silent)
            self.assertEqual(streams, {'video': 'h264'})
            self.assertAlmostEqual(length, 3.35, delta=0.15)


if __name__ == '__main__':
    unittest.main()
