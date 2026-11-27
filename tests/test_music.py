"""Tests for music.py, find_cuts.py and the places they are wired in: a rotated pool of tracks per brand."""
import json, os, shutil, subprocess, sys, tempfile, unittest
from pathlib import Path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import find_cuts
import motion
import music
import render

FFMPEG = shutil.which('ffmpeg') and shutil.which('ffprobe')
REPO_MUSIC = Path(__file__).resolve().parent.parent / 'music'


def video(aid, brand='ideaSquared', week='Week 1 · Mon', **extra):
    return {'Asset ID': aid, 'Brand': brand, 'Format': 'Text-on-screen video', 'Week / day': week, **extra}


class Switch(unittest.TestCase):
    def test_music_is_on_unless_the_row_says_no(self):
        self.assertTrue(music.wants_music({}))
        self.assertTrue(music.wants_music({'Music': ''}))
        self.assertTrue(music.wants_music({'Music': 'Yes'}))
        for value in ('No', ' no ', 'OFF', 'none', 'Silent'):
            self.assertFalse(music.wants_music({'Music': value}), value)


class Pool(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(); self.dir = Path(self.tmp.name)

    def tearDown(self):
        self.tmp.cleanup()

    def add(self, *names):
        for name in names:
            path = self.dir / name; path.parent.mkdir(parents=True, exist_ok=True); path.write_bytes(b'x')

    def test_a_brand_with_no_tracks_has_an_empty_pool(self):
        self.assertEqual(music.tracks_for('ideaSquared', self.dir), [])

    def test_the_pool_is_the_brand_folder_in_name_order(self):
        self.add('ideaSquared/b.mp3', 'ideaSquared/a.wav', 'ideaSquared/notes.txt', 'CreatrGrid/z.mp3')
        self.assertEqual(music.tracks_for(' ideaSquared ', self.dir), ['ideaSquared/a.wav', 'ideaSquared/b.mp3'])

    def test_a_single_file_named_after_the_brand_is_a_pool_of_one(self):
        self.add('ideaSquared.mp3')
        self.assertEqual(music.tracks_for('ideaSquared', self.dir), ['ideaSquared.mp3'])

    def test_a_brand_that_is_not_a_plain_name_never_reaches_the_disk(self):
        self.add('ideaSquared/a.mp3')
        self.assertEqual(music.tracks_for('../' + self.dir.name + '/ideaSquared', self.dir), [])
        self.assertEqual(music.tracks_for('', self.dir), [])

    def test_resolve_stays_inside_the_music_folder(self):
        self.add('ideaSquared/a.mp3')
        outside = self.dir.parent / 'outside.mp3'; outside.write_bytes(b'x')
        try:
            self.assertEqual(music.resolve('ideaSquared/a.mp3', self.dir), str((self.dir / 'ideaSquared/a.mp3').resolve()))
            self.assertIsNone(music.resolve('../outside.mp3', self.dir))
            self.assertIsNone(music.resolve('ideaSquared/gone.mp3', self.dir))
            self.assertIsNone(music.resolve(None, self.dir))
        finally:
            outside.unlink()

    def test_cuts_come_from_the_file_and_default_to_the_start(self):
        self.assertEqual(music.load_cuts(self.dir), {})
        (self.dir / 'cuts.json').write_text('not json')
        self.assertEqual(music.load_cuts(self.dir), {})
        (self.dir / 'cuts.json').write_text(json.dumps({'ideaSquared/a.mp3': [12.5, 0, 12.5, -3, 'x', True]}))
        cuts = music.load_cuts(self.dir)
        self.assertEqual(music.cuts_for('ideaSquared/a.mp3', cuts), [0.0, 12.5])       # sorted, no repeats, no nonsense
        self.assertEqual(music.cuts_for('ideaSquared/other.mp3', cuts), [0.0])


class Rotation(unittest.TestCase):
    TRACKS = ['B/a.mp3', 'B/b.mp3', 'B/c.mp3']
    CUTS = {'B/a.mp3': [0, 10, 20], 'B/b.mp3': [0, 15], 'B/c.mp3': [0]}

    def test_tracks_are_taken_in_turn_then_from_their_next_start_point(self):
        got = [music.pick(self.TRACKS, self.CUTS, n) for n in range(9)]
        self.assertEqual(got, [('B/a.mp3', 0.0), ('B/b.mp3', 0.0), ('B/c.mp3', 0.0),
                               ('B/a.mp3', 10.0), ('B/b.mp3', 15.0), ('B/c.mp3', 0.0),
                               ('B/a.mp3', 20.0), ('B/b.mp3', 0.0), ('B/c.mp3', 0.0)])

    def test_two_videos_in_a_row_never_share_a_track_when_the_pool_has_more_than_one(self):
        picks = [music.pick(self.TRACKS, self.CUTS, n)[0] for n in range(40)]
        self.assertTrue(all(a != b for a, b in zip(picks, picks[1:])))

    def test_no_tracks_means_silence(self):
        self.assertEqual(music.pick([], {}, 3), (None, 0.0))

    def test_places_follow_the_calendar_per_brand_not_the_sheet_order(self):
        rows = [video('I3', week='Week 2 · Tue'), video('A1', 'AdoptDontShop', 'Week 1 · Wed'), video('I1', week='Week 1 · Mon'),
                video('I2', week='Week 1 · Fri'), video('A2', 'AdoptDontShop', 'Week 9 · Mon'), video('I4', week='')]
        self.assertEqual(music.rotation(rows), {'I1': 0, 'I2': 1, 'I3': 2, 'I4': 3, 'A1': 0, 'A2': 1})

    def test_only_music_videos_take_a_place(self):
        rows = [video('V1'), video('V2', Music='No'), {'Asset ID': 'C1', 'Brand': 'ideaSquared', 'Format': 'Graphic / carousel', 'Week / day': 'Week 1 · Mon'},
                video('', week='Week 1 · Tue'), video('V3', week='Week 1 · Wed'), video('V1', week='Week 5 · Mon')]
        self.assertEqual(music.rotation(rows), {'V1': 0, 'V3': 1})

    def test_choose_gives_the_file_the_name_and_the_start(self):
        with tempfile.TemporaryDirectory() as t:
            t = Path(t); (t / 'ideaSquared').mkdir()
            for name in ('a.mp3', 'b.mp3'):
                (t / 'ideaSquared' / name).write_bytes(b'x')
            (t / 'cuts.json').write_text(json.dumps({'ideaSquared/a.mp3': [0, 12]}))
            rows = [video('V1'), video('V2', week='Week 1 · Tue'), video('V3', week='Week 1 · Wed'), video('V4', Music='No')]
            places = music.rotation(rows)
            self.assertEqual(music.choose(rows[0], places, t), (str(t / 'ideaSquared/a.mp3'), 'ideaSquared/a.mp3', 0.0))
            self.assertEqual(music.choose(rows[1], places, t)[1:], ('ideaSquared/b.mp3', 0.0))
            self.assertEqual(music.choose(rows[2], places, t)[1:], ('ideaSquared/a.mp3', 12.0))     # second time round
            self.assertEqual(music.choose(rows[3], places, t), (None, None, 0.0))                   # the row said No
            self.assertEqual(music.choose(video('V1', 'CreatrGrid'), places, t), (None, None, 0.0))  # no tracks for that brand


class Filter(unittest.TestCase):
    def test_cut_to_length_levelled_and_faded(self):
        f = music.audio_filter(4, 12.35)
        self.assertTrue(f.startswith('[4:a]atrim=start=0.000:end=12.350,'))
        self.assertIn('loudnorm=I=-18:TP=-2', f)
        self.assertIn('afade=t=in:st=0:d=0.030', f)
        self.assertIn('afade=t=out:st=11.350:d=1.000', f)
        self.assertTrue(f.endswith('[a]'))

    def test_a_start_point_moves_the_window_not_the_fades(self):
        f = music.audio_filter(4, 12.35, 24.003)
        self.assertIn('atrim=start=24.003:end=36.353,asetpts=PTS-STARTPTS', f)
        self.assertIn('afade=t=out:st=11.350:d=1.000', f)

    def test_fades_shrink_for_a_very_short_video(self):
        self.assertIn('afade=t=out:st=0.500:d=0.500', music.audio_filter(1, 1.0))

    def test_bad_lengths_are_errors(self):
        with self.assertRaises(ValueError):
            music.audio_filter(1, 0)
        with self.assertRaises(ValueError):
            music.audio_filter(1, 5, -1)

    def test_the_track_loops_and_the_output_stops_at_the_video_length(self):
        self.assertEqual(music.input_args('t.mp3'), ['-stream_loop', '-1', '-i', 't.mp3'])
        self.assertEqual(music.output_args(9.5), ['-map', '[a]', '-c:a', 'aac', '-b:a', '160k', '-t', '9.500'])


class CutFinding(unittest.TestCase):
    """The parts of find_cuts.py that need no audio library."""

    def test_beat_one_is_the_heaviest_beat_of_the_bar(self):
        self.assertEqual(find_cuts.choose_phase([1, 1, 9, 1, 1, 1, 8, 1, 1, 1, 9, 1]), 2)
        self.assertEqual(find_cuts.choose_phase([]), 0)

    def test_double_time_tracking_counts_eight_to_the_bar(self):
        self.assertEqual(find_cuts.beats_per_bar(81), 4)
        self.assertEqual(find_cuts.beats_per_bar(172), 8)

    def test_phrases_start_every_sixteen_beats_from_beat_one(self):
        beats = [i * 0.75 for i in range(80)]
        self.assertEqual(find_cuts.phrase_starts(beats, 2), [1.5, 13.5, 25.5, 37.5, 49.5])

    def test_cuts_are_spread_out_start_at_zero_and_leave_room_for_a_video(self):
        boundaries = [3 + 12 * i for i in range(9)]                       # 3, 15, ... 99
        cuts = find_cuts.pick_cuts(boundaries, duration=100, need=40, count=5)
        self.assertEqual(cuts[0], 0.0)
        self.assertEqual(cuts, sorted(set(cuts)))
        self.assertTrue(all(c + 40 <= 100 for c in cuts))
        self.assertTrue(all(any(abs(c + find_cuts.PRE_ROLL - b) < 1e-6 for b in boundaries) for c in cuts[1:]))
        self.assertGreaterEqual(len(cuts), 4)

    def test_a_track_too_short_for_a_second_start_only_starts_at_zero(self):
        self.assertEqual(find_cuts.pick_cuts([12, 24, 36], duration=45, need=40, count=5), [0.0])
        self.assertEqual(find_cuts.pick_cuts([], duration=100, need=40, count=5), [0.0])


class CommittedTracks(unittest.TestCase):
    """The tracks and cut points that ship in music/."""

    def test_every_brand_has_at_least_five_tracks(self):
        for brand in ('ideaSquared', 'AdoptDontShop', 'CreatrGrid'):
            self.assertGreaterEqual(len(music.tracks_for(brand, REPO_MUSIC)), 5, brand)

    def test_cuts_json_matches_the_files(self):
        cuts = music.load_cuts(REPO_MUSIC)
        files = {t for brand in ('ideaSquared', 'AdoptDontShop', 'CreatrGrid') for t in music.tracks_for(brand, REPO_MUSIC)}
        self.assertEqual(set(cuts), files)
        for track, starts in cuts.items():
            self.assertEqual(starts[0], 0.0, track)
            self.assertEqual(starts, sorted(set(starts)), track)

    def test_every_track_is_recorded_with_its_licence(self):
        readme = (REPO_MUSIC / 'README.md').read_text(encoding='utf-8')
        for brand in ('ideaSquared', 'AdoptDontShop', 'CreatrGrid'):
            for track in music.tracks_for(brand, REPO_MUSIC):
                self.assertIn(f'`{track}`', readme)

    @unittest.skipUnless(FFMPEG, 'needs ffprobe')
    def test_every_start_point_leaves_room_for_the_longest_video(self):
        cuts = music.load_cuts(REPO_MUSIC)
        for track, starts in cuts.items():
            length = float(subprocess.run(['ffprobe', '-v', 'error', '-show_entries', 'format=duration', '-of', 'csv=p=0', str(REPO_MUSIC / track)],
                                          check=True, capture_output=True, text=True).stdout)
            self.assertLessEqual(starts[-1] + 35, length, track)          # the longest video so far is about 26 seconds


class Wiring(unittest.TestCase):
    PNGS, DURS = ['a.png', 'b.png', 'c.png'], [2.8, 3.0, 3.4]

    def test_render_without_a_track_is_silent(self):
        cmd = render.video_cmd((self.PNGS, self.DURS, 'v.mp4', None, 0.0))
        self.assertNotIn('-stream_loop', cmd); self.assertNotIn('[a]', cmd)
        self.assertEqual(cmd[-3:], ['-movflags', '+faststart', 'v.mp4'])

    def test_render_with_a_track_adds_it_after_the_frames_from_its_start_point(self):
        cmd = render.video_cmd((self.PNGS, self.DURS, 'v.mp4', 't.mp3', 12.0))
        self.assertEqual(cmd[cmd.index('-stream_loop'):cmd.index('-stream_loop') + 4], ['-stream_loop', '-1', '-i', 't.mp3'])
        fc = cmd[cmd.index('-filter_complex') + 1]
        self.assertIn('[3:a]atrim=start=12.000:end=21.550', fc)            # 2.8 + 3.0 + 3.4 + the 0.35 fade
        self.assertEqual(cmd[cmd.index('-t', cmd.index('-filter_complex')) + 1], '9.550')
        self.assertIn('aac', cmd)

    def test_motion_is_silent_without_a_track_and_has_audio_with_one(self):
        self.assertIn('-an', motion.build_command(self.PNGS, self.DURS, 'm.mp4', '#fff'))
        cmd = motion.build_command(self.PNGS, self.DURS, 'm.mp4', '#fff', 'calm', 't.mp3', 12.0)
        self.assertNotIn('-an', cmd); self.assertIn('aac', cmd)
        self.assertIn('[3:a]atrim=start=12.000:end=21.550', cmd[cmd.index('-filter_complex') + 1])

    def test_motion_uses_the_track_and_start_that_render_recorded(self):
        with tempfile.TemporaryDirectory() as t:
            tracks = Path(t) / 'music'; (tracks / 'ideaSquared').mkdir(parents=True); (tracks / 'ideaSquared' / 'a.mp3').write_bytes(b'x')
            base = {'brand': 'ideaSquared', 'frames': 2, 'video': True, 'text': ['a', 'b']}
            man = [dict(base, asset='A', folder='ideaSquared/A', music='ideaSquared/a.mp3', music_start=12.0),
                   dict(base, asset='B', folder='ideaSquared/B'),                                    # its row said No
                   dict(base, asset='C', folder='ideaSquared/C', music='ideaSquared/gone.mp3')]      # the track was removed since
            (Path(t) / 'manifest.json').write_text(json.dumps(man))
            old = os.environ.get('MUSIC_DIR'); os.environ['MUSIC_DIR'] = str(tracks)
            try:
                jobs = motion.load_jobs(t)
            finally:
                os.environ.pop('MUSIC_DIR') if old is None else os.environ.__setitem__('MUSIC_DIR', old)
            self.assertEqual([(j[4], j[5]) for j in jobs], [(str((tracks / 'ideaSquared/a.mp3').resolve()), 12.0), (None, 0.0), (None, 0.0)])


@unittest.skipUnless(FFMPEG, 'needs ffmpeg and ffprobe')
class RealVideo(unittest.TestCase):
    """Runs ffmpeg for real, on a generated tone, so the filter is known to work and not only to look right."""

    def probe(self, path):
        out = subprocess.run(['ffprobe', '-v', 'error', '-show_entries', 'stream=codec_type,codec_name:format=duration',
                              '-of', 'json', str(path)], check=True, capture_output=True, text=True).stdout
        data = json.loads(out)
        return {s['codec_type']: s['codec_name'] for s in data['streams']}, float(data['format']['duration'])

    def test_a_short_track_loops_under_a_longer_video_even_from_a_late_start(self):
        from PIL import Image
        with tempfile.TemporaryDirectory() as t:
            t = Path(t)
            pngs = []
            for i, colour in enumerate(((20, 40, 60), (60, 40, 20), (20, 60, 40))):
                p = t / f'f{i}.png'; Image.new('RGB', (108, 192), colour).save(p); pngs.append(str(p))
            track = t / 'tone.wav'                                        # 2 seconds, far shorter than the video
            subprocess.run(['ffmpeg', '-y', '-loglevel', 'error', '-f', 'lavfi', '-i', 'sine=frequency=440:duration=2', str(track)], check=True)
            durs = [1.0, 1.0, 1.0]
            for name, job_track, start, want in (('start.mp4', str(track), 0.0, {'video': 'h264', 'audio': 'aac'}),
                                                 ('late.mp4', str(track), 1.5, {'video': 'h264', 'audio': 'aac'}),
                                                 ('silent.mp4', None, 0.0, {'video': 'h264'})):
                render.video((pngs, durs, str(t / name), job_track, start))
                streams, length = self.probe(t / name)
                self.assertEqual(streams, want, name)
                self.assertAlmostEqual(length, 3.35, delta=0.15, msg=name)          # the video's length, not the track's


if __name__ == '__main__':
    unittest.main()
