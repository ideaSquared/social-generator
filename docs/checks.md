# Checks

Two deterministic checks, no AI, standard library plus Pillow. Both live in `checks/`.

## Claims check

```
python checks/claims_check.py posts.csv [--strict]
```

Lints the public text (Title, Content and caption) of every row. Output, one line per finding:

```
ROW 36 We cut our own claims: ERROR banned-phrase: "waitlist" in: ...
```

`ROW` is the row number as the sheet shows it (the header is row 1). Exit code 1 if there is any ERROR; warnings fail only with `--strict`. All rules and limits sit in the `RULES` section at the top of `checks/claims_check.py`.

### Errors

- **unevidenced-figure**: a percentage, a money amount (£ $ €), a number with three or more digits or a thousands separator, an abbreviated figure (`12k`, `3m`, `2bn`), an `Nx` multiplier, or a year used as a deadline or target (`by 2030`, `a 2030 target`), in a row with neither a `Footnote on asset:` line nor a non-empty "Check before posting" cell. Ignored: slide and beat numbering, `1 of 5`, ratios such as 16:9 and 1:1, hashtags, URLs and domains, and bare years (`early 2027`, `22 Nov 2026`).
- **banned-phrase**: `waitlist`, `pilot rescue(s)`, `letters of intent`, `most trusted`, `guaranteed for life`, `world-class`, `best-in-class`, `10x`. Whole words, case-insensitive; a plural `s` is tolerated (`waitlists`).
- **parked-venture**: the word `Pairflix`.
- **Structure**: `video-no-hook`, `video-no-beats`, `video-no-close`, `carousel-no-slides`, `empty-slide-body`, `missing-asset-id` and `duplicate-asset-id` (video and carousel rows only; `Text only` counts as missing), `unknown-brand`, and `x-post-too-long` (X posts over 280 characters; each URL counts as 23).

### Warnings

- `long-beat` (over 14 words), `long-slide-heading` (over 8 words), `too-many-hashtags` (over 6 in a caption, or in a text post).
- `emoji` in ideaSquared or CreatrGrid rows.
- `american-spelling`: color, organization, favorite, behavior, center, analyze (and their common forms), outside URLs and hashtags.
- `unresolved-check`: the Check cell contains `CONFLICT` or `NOT confirmed`, so it is not forgotten.

### Allowing a phrase for one row

Put `allow:` followed by the phrase in that row's "Check before posting" cell:

```
allow: waitlist
allow: waitlist, 10x
D13. allow: Pairflix
```

The list runs to the next `;` or line break. The override covers only the phrases named, and only in that row. Use it for a post that talks about a banned claim in order to retract it, and say why elsewhere in the cell. The figure rule is not overridden this way: record the source in the Check cell or add a `Footnote on asset:` line.

## Visual check

```
python checks/visual_check.py out [--skip-video] [--skip-mtime]
```

Validates a render against `out/manifest.json`. Needs Pillow, and `ffprobe` for videos. Exit code 1 on any FAIL; WARN lines never fail. Checks:

- the asset folder exists and the slide or frame count matches the manifest;
- exact sizes: 1080x1350 slides, 1080x1920 frames (and videos);
- the white-corner glitch: the pixel 3 px in from the bottom-right corner is pure white while the one at the bottom-left is not;
- text touching the right edge: on light, flat frames, the column 4 px from the right edge is compared with its dominant colour, and the frame fails if 12 or more pixels differ strongly. Dark and patterned frames are skipped, and so are the top 470 px of CreatrGrid's first frame (decorative tiles);
- videos exist, last 6 to 60 seconds, are 1080x1920, and are not older than their frames (`--skip-mtime` disables this, for example after unzipping an artefact);
- an asset folder on disk that is missing from the manifest (WARN).

The thresholds are constants at the top of the file.

## Tests and CI

```
python -m unittest discover -s tests
```

`.github/workflows/checks.yml` runs the tests on every pull request and on pushes to `main`, and runs the claims check on `posts.csv` only if that file is in the repository. The workflow uses no secrets.
