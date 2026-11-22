# Social asset generator

Turns rows in the **Social posts** sheet into finished carousels (PNG) and text videos (MP4).
No AI is involved: the sheet is the only input, and the same row always gives the same asset.

## What it makes

| Sheet format | Output |
|---|---|
| `Graphic / carousel` | `slide_01.png` … at 1080x1350 |
| `Text-on-screen video` | `video.mp4` at 1080x1920, plus every frame as a PNG |

Brands supported: AdoptDontShop, ideaSquared, CreatrGrid. Rows with any other brand or format are skipped.

## Run it

You need Python 3.10+, Pillow, Google Chrome or Chromium, and ffmpeg.

```
pip install pillow
python render.py posts.csv --out out
```

Get `posts.csv` from the sheet: open the Social posts tab, then File > Download > Comma-separated values.

Useful options:

- `--only ADS-C01,CG-V03` renders just those Asset IDs.
- `--new-only` skips rows where "Assets made" is already filled in.
- Set the `CHROME` environment variable if Chrome is not on your PATH.

## How to write a row

The script reads these columns: Brand, Title, Content, Asset ID, Pillar, Format, Assets made.

**Text video** (Content cell):

```
Hook: The opening line.
Beats:
- First point
- Second point
Close: The closing line.
Footnote on asset: Source: where the figure came from.

Caption: anything from here down is ignored by the script
```

**Carousel** (the Title column is the cover headline):

```
Sub: The line under the cover headline.
Slides:
1. Heading: Body text for this slide.
2. Another heading: More body text.
End: Text for the last slide.
Footnote on asset: optional

Caption: ignored by the script
```

Rules that matter:

- A slide is split into heading and body at the **last** colon followed by a space, so don't put ": " in the body text.
- "Footnote on asset" is optional. When present it appears small at the bottom of every frame.
- Text sizes shrink automatically for long lines, but keep beats under about 12 words.

## Run it on GitHub instead

`.github/workflows/render.yml` renders everything and attaches a zip to the workflow run.
Add one repository secret, `SHEET_CSV_URL`, holding a CSV link to the Social posts tab
(File > Share > Publish to web > Social posts > CSV). That link is public to anyone who has it,
so use the manual download above if you'd rather not publish the tab.

## Changing the look

Each brand's templates are plain functions near the top of `render.py`
(`ads_*`, `isq_*`, `cg_*`). Colours and fonts come from each brand's design system.
Fonts are bundled in `fonts/`.
