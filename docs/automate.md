# automate.py: run it unattended

`automate.py` does the weekly steps by itself on a timer. Each pass it:

1. Reads the **Social posts** tab.
2. Stops early if nothing in the tab changed since the last good pass.
3. Runs `checks/claims_check.py`. An error stops the pass; nothing is rendered until the row is fixed.
4. Renders only the rows whose asset text changed (Brand, Format, Asset ID, Pillar, Title or Content), plus any row not rendered yet.
   Moving a post to another week, or changing its Status, does not render it again.
5. Runs `checks/visual_check.py`, then makes the PDFs and alt text for the rows it rendered.
6. Rebuilds the review page (`index.html`) and the post folders (`posts/`).
7. Fills in **Assets made** with today's date for the rows it rendered (service account only).

It removes the output of rows you delete from the sheet. It never posts anything and never changes any cell except **Assets made**.

## Settings

| Setting | Meaning |
|---|---|
| `SHEET_ID` | The long part of the sheet's URL, between `/d/` and `/edit` |
| `GOOGLE_CREDENTIALS` | Path to the service account key file. The compose file sets this for you |
| `SHEET_TAB` | Tab to read. Default `Social posts` |
| `SHEET_WRITE_BACK` | `0` stops it filling in "Assets made". Default on |
| `SHEET_CSV_URL` | Use instead of the service account: a "Publish to web" CSV link. Read-only, so "Assets made" is not filled in |

## Options

```
python automate.py --out out               # one pass, then exit (exit code 1 if it failed)
python automate.py --out out --every 60    # keep running, one pass every 60 minutes
python automate.py --out out --force       # render every row again
```

Reading the sheet with a service account needs two extra packages: `pip install -r deploy/requirements.txt`.

## What it leaves in the output folder

| File | What it is |
|---|---|
| `index.html` | The review page |
| `posts/<Asset ID>/<Platform>/` | The files and caption to post, and `posts/schedule.csv` |
| `status.json` | When the last pass ran, whether it worked, and which rows it rendered |
| `posts.csv` | The copy of the tab the last pass used |
| `.state.json` | What it has already rendered. Delete it (or use `--force`) to start again |

## If a pass fails

The log line starts with `FAILED:` and `status.json` has `"ok": false`. The next pass tries again from the start.

| Message | Fix |
|---|---|
| `Checking the sheet failed` | The lines above it name the rows. Fix them in the sheet |
| `Checking the images failed` | A render came out wrong. The lines above it name the asset |
| `service account key not found` | Put the key at `deploy/secrets/service-account.json` |
| `could not fill in "Assets made"` | Share the sheet with the service account as **Editor**, not Viewer |
| `HTTPError while running` or `RefreshError while running` | The sheet is not shared with the service account, the Sheets API is not enabled, or `SHEET_ID` is wrong |

Error messages from Google are not printed in full, because they can include account details.
