# Card formats, video covers and story versions

## Single-image cards

Set the sheet's Format column to `Text card`, `Stat card` or `Quote card`. Each row needs an Asset ID. Each renders one `card.png` (1080x1350) into `out/<Brand>/<AssetID>_<slug>/`.

**Text card**: the Content cell is the post text. Everything from a `Caption:` line down is ignored. Aim for 280 characters or fewer; longer text shrinks to fit. Blank lines make paragraphs.

```
Rescue dogs aren't broken. They're on day one.

Caption: ignored by the script
```

**Stat card**:

```
Stat: 34,819
Label: dogs rehomed by ADCH members in 2024
Footnote on asset: Source: ADCH annual report 2024
```

**Quote card**:

```
Quote: A rescue dog needs a patient home.
By: Sam, volunteer at a Cheshire rescue
```

`Footnote on asset` is optional on every card.

## Video cover

Every `Text-on-screen video` also gets `cover.png` (1080x1920), a copy of `frames/frame_01.png`.

## Story versions of carousels

```
python render.py posts.csv --out out --stories
```

Each `Graphic / carousel` also gets `stories/story_01.png` onwards at 1080x1920, with headers and footers moved clear of the story app's top and bottom bars. The normal 1080x1350 slides are unchanged.

## Manifest

`manifest.json` entries gain `"cover": true` (videos), `"stories": N` (carousels, with `--stories`) and `"card": true` (cards).
