# Social asset generator

Turns rows in the **Social posts** Google Sheet into finished carousels, cards and text videos.
No AI is involved: the sheet is the only input, and the same row always gives the same asset.

Brands supported: AdoptDontShop, ideaSquared, CreatrGrid.

So far it has only been run on Linux. The Windows and macOS steps below are the expected ones but are untested.

## Set up (once)

### 1. Install the four things it needs

| Needs | Check it is installed | Install |
|---|---|---|
| Python 3.10 or newer | `python --version` | [python.org](https://www.python.org/downloads/) (on Windows, tick "Add Python to PATH") |
| Pillow | `python -c "import PIL"` | `pip install -r requirements.txt` |
| Google Chrome or Chromium | open it | [google.com/chrome](https://www.google.com/chrome/) |
| ffmpeg | `ffmpeg -version` | Windows: `winget install ffmpeg`. macOS: `brew install ffmpeg`. Ubuntu: `sudo apt install ffmpeg` |

On Windows, use `py` in place of `python` if `python` is not found.

### 2. Get the code

```
git clone https://github.com/ideaSquared/social-generator.git
cd social-generator
pip install -r requirements.txt
```

If you set up your machine with `eng`, steps 1 and 2 are mostly done for you: `eng setup` clones this repo into
`~/ideasquared/social-generator` and installs `requirements.txt` into a `.venv` folder inside it. Use that Python
for every command below: `.venv/bin/python` on macOS and Linux, `.venv\Scripts\python` on Windows.
`eng doctor` tells you if Python or ffmpeg is missing; eng does not install those two, or Chrome.

### 3. Tell it where Chrome is (only if step 5 says it cannot find Chrome)

The tool looks for `google-chrome` or `chromium` on your PATH. If Chrome is somewhere else, set `CHROME` to its full path first.

```
# Windows (PowerShell)
$env:CHROME = "C:\Program Files\Google\Chrome\Application\chrome.exe"

# macOS
export CHROME="/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
```

### 4. Check the install

```
python -m unittest discover -s tests
```

This should end with `OK`. It does not need Chrome or the sheet.

### 5. Do a first render of one asset

1. Open the sheet, go to the **Social posts** tab, then File > Download > Comma-separated values.
2. Save the file as `posts.csv` in the `social-generator` folder.
3. Run:

```
python render.py posts.csv --out out --only ADS-C01
```

You should get `out/AdoptDontShop/ADS-C01_.../slide_01.png` and so on. If that works, setup is done.

`posts.csv` and `out/` are ignored by git, so they are never committed.

## Each week

```
python checks/claims_check.py posts.csv          # 1. catch missing sources and broken rows
python render.py posts.csv --out out --new-only  # 2. make assets for rows where "Assets made" is empty
python checks/visual_check.py out                # 3. catch wrong sizes, clipped text, stale videos
python gallery.py out --csv posts.csv            # 4. open out/index.html to review the week
python package.py out --csv posts.csv            # 5. sort everything into out/posts/<post>/<platform>/
```

Post from `out/posts`. Each post has one folder per platform, for example `out/posts/ADS-C01/Instagram/` and
`out/posts/ADS-C01/Facebook/`, holding the files that platform needs and a caption adjusted for it
(see `docs/package.md`). `out/posts/schedule.csv` lists every post in calendar order.

Then, in the sheet, type `Yes` in **Assets made** for the rows you rendered, and paste each live link into **Posted URL**.

Useful `render.py` options:

- `--only ADS-C01,CG-V03` renders just those Asset IDs.
- `--new-only` skips rows where "Assets made" is filled in.
- `--stories` also makes a 9:16 story version of every carousel.
- `--dry-run` reads the sheet and reports what it would make, without rendering.

## Posting

Posting is done by hand, in one sitting a week, using each platform's own scheduler. Nothing in this repo posts for you.

1. Open `out/posts/schedule.csv`. It lists every post in the sheet in calendar order, by "Week / day" label, not by date.
   It does not know what is approved or already live, so pick this week's rows yourself and skip any that still need a check
   or already have a **Posted URL** in the sheet.
2. For each post you picked, open its folder, for example `out/posts/ADS-C01/Instagram/`. What is in it:

   | File | What to do with it |
   |---|---|
   | `_01.png`, `_02.png`, ... or one `.png` | Upload as the post's images, in number order |
   | `.pdf` (LinkedIn carousels) | Upload as a document post |
   | `.mp4` | Upload as the video |
   | `_cover.png` (videos only) | Optional: set it as the video's cover. Do not add it as an extra image |
   | `_caption.txt` | Paste as the caption. Do not upload it |
   | `_alt.txt` | Paste into the platform's alt text box, if it has one. Do not upload it |
   | `_post.txt` (text posts) | Paste as the post. There is nothing to upload |

3. Set the date and time in that platform's scheduler.
4. When a post is live, paste its link into **Posted URL** in the sheet.

## What it makes

| Sheet format | Output in `out/<Brand>/<AssetID>_<title>/` |
|---|---|
| `Graphic / carousel` | `slide_01.png` onwards at 1080x1350 |
| `Text-on-screen video` | `video.mp4` at 1080x1920, every frame as a PNG, and `cover.png` |
| `Text card`, `Stat card`, `Quote card` | one `card.png` at 1080x1350 |
| `Text post` | nothing (the text is the post) |

## The sheet

The **Start here** tab in the sheet explains every column and has a copyable Content template for each format.
The tool finds columns by their header name, so columns can be reordered but not renamed.

| Column | Used by | What it does |
|---|---|---|
| Brand | all | Picks the design |
| Format | all | Picks what gets made |
| Asset ID | all | Unique name for the post and its folder. Text posts have one too (`ISQ-L01`, `CG-X01`) |
| Title | render | Carousel cover headline |
| Content | all | The script, then the caption |
| Pillar | render | Small label on the asset |
| Assets made | render | `--new-only` skips rows where this is filled |
| Platform, Also post to, Week / day | gallery, checks | Grouping, filters and the X length check |
| Check before posting | gallery, checks | Source for each claim; `allow:` overrides |
| Ready? | you | Filled in by the sheet: `OK`, or what is missing |

### How to write the Content cell

**Text video**:

```
Hook: The opening line.
Beats:
- First point
- Second point
Close: The closing line.
Footnote on asset: Source: where the figure came from.

Caption: anything from here down is not put on the asset
```

**Carousel** (the Title column is the cover headline):

```
Sub: The line under the cover headline.
Slides:
1. Heading: Body text for this slide.
2. Another heading: More body text.
End: Text for the last slide.
Footnote on asset: optional

Caption: not put on the asset
```

**Cards**: see `docs/card-formats.md`.

Rules that matter:

- A slide is split into heading and body at the **last** colon followed by a space, so don't put ": " in the body text.
- "Footnote on asset" is optional. When present it appears small at the bottom of every frame.
- Text sizes shrink automatically for long lines, but keep beats under about 12 words.

## All the tools

Each is a separate script with its own notes in `docs/`.

| Script | What it does | Notes |
|---|---|---|
| `render.py posts.csv --out out` | Carousels, cards, videos, covers, story versions | `docs/card-formats.md` |
| `package.py out --csv posts.csv` | One folder per post and platform, with the right files and a per-platform caption | `docs/package.md` |
| `postprocess.py all out` | One PDF per carousel (LinkedIn document posts) and alt text per asset | `docs/postprocess.md` |
| `motion.py out` | A `video_motion.mp4` per video with a progress bar, slow push-in and transitions. Slow: a few minutes per video | `docs/motion.md` |
| `gallery.py out --csv posts.csv` | One review page showing each week's posts, captions and check notes | `docs/gallery.md` |
| `brandkit.py --out out` | Banners, avatars, highlight covers and link preview images per brand | `docs/brandkit.md` |
| `product_shots.py shots.example.json --out out/product-shots` | Screenshots of your own pages in phone or browser frames. Needs internet access | `docs/product-shots.md` |
| `checks/claims_check.py posts.csv` | Flags figures with no source, banned phrases and rows that would not render | `docs/checks.md` |
| `checks/visual_check.py out` | Flags wrong sizes, unpainted corners, text at the edge and stale videos | `docs/checks.md` |
| `automate.py --out out --every 60` | Does all the weekly steps on a timer, rendering only rows that changed | `docs/automate.md` |

## Run it on GitHub instead (optional)

`.github/workflows/render.yml` does the weekly steps on GitHub and attaches a zip of the assets to the workflow run.

This repo is public. That means the zip and the run's log (which prints text from the sheet) are open to everyone before you post: anyone can read the log, and anyone with a GitHub account can download the zip.
Use this only if that is acceptable; running it on your own computer keeps drafts private.

1. In the sheet: File > Share > Publish to web. Choose the **Social posts** tab and **Comma-separated values**, then Publish. Copy the link.
   That link is readable by anyone who has it, so skip this section if you would rather not publish the tab.
2. In the GitHub repo: Settings > Secrets and variables > Actions > New repository secret. Name it `SHEET_CSV_URL` and paste the link.
3. Actions > Render social assets > Run workflow. Leave "only" blank to render every row where "Assets made" is empty.
4. When it finishes, download `social-assets` from the run's Artifacts section.

It only runs when you start it; there is no timer. `.github/workflows/checks.yml` runs the tests on every pull request.

## Run it on an always-on box (optional)

The normal way to use this tool is on your own computer, with the steps under "Each week".
This section is only for running it unattended.

`automate.py` does the weekly steps on a timer and serves the review page, so the only manual jobs left are
approving and posting. It runs in Docker on any always-on Linux box. Details are in `docs/automate.md`.

Rendering is heavy on the processor (headless Chrome and ffmpeg). On a low-power mini PC the first pass, which renders
every row, can be too slow to be useful. You can also run one pass on your own computer instead of the weekly steps:
`python automate.py --out out` (see `docs/automate.md` for the settings it needs).

This has been tested by running `automate.py` on Linux. The Docker image and compose file have not been built or run yet.

**One-time set-up**

1. Make a Google service account (this is what lets the box read the sheet without publishing it):
   1. Go to [console.cloud.google.com](https://console.cloud.google.com), create a project, and enable the **Google Sheets API**.
   2. IAM & Admin > Service accounts > Create service account. No roles are needed.
   3. Open the account > Keys > Add key > JSON. A key file downloads.
   4. In the sheet, click Share and add the service account's email address as **Editor**.
2. On the box, get the code. The repo is public, so no key or login is needed:
   ```
   git clone https://github.com/ideaSquared/social-generator.git
   cd social-generator/deploy
   ```
3. Put the key file at `deploy/secrets/service-account.json` and make it readable by the container: `chmod 644 secrets/service-account.json`.
4. Copy the settings file and fill in `SHEET_ID`:
   ```
   cp .env.example .env
   ```
5. Start it:
   ```
   docker compose up -d --build
   ```
6. Point your reverse proxy at port `8087` on the box, for example as `social.home.example.com`.

`.env` and the key file are ignored by git. Never commit them: this repo is public, so anything committed is visible to everyone.

**Day to day**

- Edit the sheet. Within an hour the review page and `posts/` folders update. Only rows whose text changed are rendered again.
- Open the review page, approve, and post from `posts/<Asset ID>/<Platform>/`.
- "Assets made" is filled in for you. "Posted URL" is still yours to paste.
- `docker compose logs -f runner` shows what it did. `<review page>/status.json` shows the last result.
- To update the code: `git pull && docker compose up -d --build`.

The review page shows unpublished drafts. Keep it on your home network, or put a login in front of it.

## Changing the look

Each brand's templates are plain functions near the top of `render.py`
(`ads_*`, `isq_*`, `cg_*`). Colours and fonts come from each brand's design system.
Fonts are bundled in `fonts/`.

## If something goes wrong

| Problem | Fix |
|---|---|
| "Chrome not found" or blank images | Set `CHROME` (set-up step 3) |
| `ffmpeg: command not found` | Install ffmpeg (set-up step 1) and reopen the terminal |
| A row is skipped | Check its **Ready?** cell in the sheet, then run `checks/claims_check.py` |
| `--new-only` makes nothing | Every row has "Assets made" filled in. Clear the cell for rows you want remade |
| `visual_check.py` says a video is stale after unzipping | Add `--skip-mtime` |
