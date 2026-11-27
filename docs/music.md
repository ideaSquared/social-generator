# Music under the videos

The text videos have no speech. `render.py` and `motion.py` can put one quiet music track under each of them:
one track per brand, so each account sounds the same from post to post.

## Set it up

Put one audio file per brand in the `music/` folder, named after the brand exactly as the **Brand** column writes it:

```
music/ideaSquared.mp3
music/AdoptDontShop.mp3
music/CreatrGrid.mp3
```

`.mp3`, `.m4a`, `.wav`, `.ogg` and `.flac` all work. If a brand has more than one, the first in that order is used.

That is all. The next `render.py` run adds the track to every video for that brand. A brand with no file gets
silent videos, as before, and `render.py` prints which brands those are.

To keep the tracks somewhere else, set `MUSIC_DIR` to that folder.

## What the tool does to the track

| Step | Detail |
|---|---|
| Starts at the beginning | The track plays from its first second |
| Cut to the video's length | A track shorter than the video loops |
| Levelled | Set to about -18 LUFS, so a loud track and a quiet one come out the same |
| Faded | 0.4 seconds in, 1 second out |
| Encoded | AAC, 160 kbit/s, 48 kHz |

The level is deliberately low: the words on screen are the message. LinkedIn and Facebook play feed videos muted
until tapped, so nothing may depend on the sound. The numbers sit at the top of `music.py`.

## Leaving one post silent

Add a column called **Music** to the Social posts tab. Put `No` in it for a post that should have no music,
for example a safety post where a cheerful track would be wrong. An empty cell means yes.

`motion.py` follows `render.py`: if a row's video was rendered silent, its `video_motion.mp4` is silent too.

## After changing a track

A video is only rendered again when its row is rendered again. After you swap a brand's track, render that
brand's videos again, for example `python render.py posts.csv --out out --only ADS-V01,ADS-V02`.
`automate.py` does not notice a changed track on its own; it does notice a changed **Music** cell.

## Choosing a track

"Royalty free" is not enough. The licence has to allow:

1. Commercial use: these are brand accounts.
2. Use without credit, or with a credit you are willing to put in every caption.
3. Redistribution, if the file is committed here: this repository is public.

A CC0 track meets all three. Record where each track came from in `music/README.md`.

Some free libraries register their tracks with the platforms' copyright matching. A video using one can be
muted or claimed even though the licence allows it. Post one video as a test before using a new track everywhere.
