# Music under the videos

The text videos have no speech. `render.py` and `motion.py` put one quiet music track under each of them, taken
from a small pool for the brand, so an account sounds consistent without every post sounding the same.

## Set it up

Put each brand's tracks in a folder named after the brand exactly as the **Brand** column writes it:

```
music/ideaSquared/morning-coffee.mp3
music/ideaSquared/vintage.mp3
music/AdoptDontShop/puppy-love.mp3
music/CreatrGrid/blue-skies.mp3
```

`.mp3`, `.m4a`, `.wav`, `.ogg` and `.flac` all work. The repository ships five tracks for each brand; `music/README.md`
lists them with their licences.

The next `render.py` run uses them. A brand with no tracks gets silent videos, and `render.py` prints which brands
those are. To keep the tracks somewhere else, set `MUSIC_DIR` to that folder.

## Which track a video gets

Tracks are taken in turn, in the order the brand's videos are posted (by **Week / day**, then by row):

| Brand's video | Track | Starts at |
|---|---|---|
| 1st | track 1 | its first start point |
| 2nd | track 2 | its first start point |
| ... | ... | ... |
| 6th (with five tracks) | track 1 | its second start point |
| 7th | track 2 | its second start point |

So two videos in a row never share a track, and nothing repeats until every track has been heard from every one
of its start points. With five tracks and about five start points each, that is about 25 videos per brand.

The order is counted over the whole sheet, so a video gets the same audio whether you render everything or only a
few rows with `--only`. One thing to know: adding a post in the middle of the calendar moves every later video of
that brand along by one. The later videos keep the audio they already have until they are rendered again.

`manifest.json` records what each video used, as `music` and `music_start`.

## Start points

A video does not always start its track at the beginning. Each track has a short list of start points in
`music/cuts.json`:

```
"ideaSquared/vintage.mp3": [0.0, 11.998, 24.003, 48.012, 59.994]
```

Every start point other than 0 is the first beat of a four-bar phrase, so a video never comes in halfway through
a beat or a phrase. They are found by beat tracking, not by ear:

```
pip install librosa
python find_cuts.py
```

Run that once after adding or replacing a track. It rewrites `cuts.json` for every track. `librosa` is needed only
for this script; it is not in `requirements.txt`, and `render.py` never needs it. A track with no entry in
`cuts.json` always starts at 0, so the script is optional.

How it decides, and its limits:

- It tracks the beat, then takes the beat with the most low-end weight as beat one of the bar. That choice is a
  best guess. If a start point sounds like it lands on the wrong beat, delete that number from `cuts.json`.
- It assumes four beats to a bar.
- It keeps a start point only if 40 seconds of track follow it, so a video never runs off the end and loops.
- The tracks here are instrumental. A track with singing would need its start points checked by ear, because the
  script knows nothing about words.

You can also edit `cuts.json` by hand: any list of seconds works.

## What the tool does to the track

| Step | Detail |
|---|---|
| Starts at the chosen start point | 0.03 seconds before the beat, so the hit is not clipped |
| Cut to the video's length | A track that runs out loops from its beginning |
| Levelled | Aimed at -18 LUFS, so a loud track and a quiet one come out close to the same |
| Faded | 0.03 seconds in, only to avoid a click; 1 second out |
| Encoded | AAC, 160 kbit/s, 48 kHz |

The level is deliberately low: the words on screen are the message. LinkedIn and Facebook play feed videos muted
until tapped, so nothing may depend on the sound. The numbers sit at the top of `music.py`.

## Leaving one post silent

Put `No` in the **Music** column of the Social posts tab for a post that should have no music, for example a safety
post where a cheerful track would be wrong. An empty cell means yes. A silent post does not take a turn in the rotation.

`motion.py` follows `render.py`: `video_motion.mp4` gets the same track and start point as `video.mp4`, or stays silent.

## After changing the tracks

A video is only rendered again when its row is rendered again. After you add, remove or replace a track, render
that brand's videos again, for example `python render.py posts.csv --out out --only ADS-V01,ADS-V02`.
`automate.py` does not notice changed tracks on its own; it does notice a changed **Music** cell.

## Choosing a track

"Royalty free" is not enough. The licence has to allow:

1. Commercial use: these are brand accounts.
2. Use without credit, or with a credit you are willing to put in every caption.
3. Redistribution, if the file is committed here: this repository is public.

A CC0 track meets all three. Record where each track came from in `music/README.md`.

Some free libraries register their tracks with the platforms' copyright matching. A video using one can be
muted or claimed even though the licence allows it. Post one video as a test before using a new track everywhere.
