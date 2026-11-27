# motion.py

Adds gentle motion to the text videos that `render.py` produced. It only reads the existing
`frames/frame_NN.png` files and uses ffmpeg filters, so nothing is re-rendered.

    python motion.py <out_dir> [--only ID1,ID2] [--style calm|lively]

For every video asset in `<out_dir>/manifest.json` it writes `video_motion.mp4` next to
`video.mp4` (1080x1920, 30 fps, H.264, yuv420p, faststart). It has the same music as `video.mp4`, or none if
that was rendered silent (see `docs/music.md`). Frame durations use the
same formula as `render.py` (title 2.8 s, end 3.4 s, beats `max(2.4, min(5.2, 1.4 + 0.3 * words))`).

## What it adds

- Progress bar: 10 px along the top edge in the brand accent colour (AdoptDontShop #dc1a45,
  ideaSquared #e8911a, CreatrGrid #7c3aed) over a faint white track, filling across the whole video.
- Push-in: each frame scales from 100% to 103% about its centre. The frame is supersampled 2x and
  scaled with a per-frame time expression, then cropped and downsampled, which avoids zoompan jitter.
  Content within about 30 px of the edge can be trimmed; render.py keeps text and the footnote well inside that.
- Transitions: `calm` is a 0.35 s fade; `lively` alternates `slideup` and `smoothleft` at 0.3 s.

## Notes

- Encoding is CPU heavy because of the 2x supersampling: expect a few minutes per video on a shared
  2-CPU machine. Run `--only` for a few assets at a time.
- On a full-bleed accent background (such as a rose title card) the bar is the same colour as the
  background, so only the faint track edge shows until the card changes.
- Tests: `python -m unittest discover -s tests` (no ffmpeg needed).
