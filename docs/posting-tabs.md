# Text for the sheet's posting tabs

```
python posting_tabs.py posts.csv --out out
```

The sheet has one tab per platform: **Post - LinkedIn**, **Post - X**, **Post - Instagram**, **Post - Facebook** and
**Post - TikTok**. Each row on those tabs is one post on that platform. The sheet works out the date, time, account and
upload folder itself. Two cells have to be filled in by hand: the post code in column A, and the green cell with the
text to paste.

`posting_tabs.py` writes both, one file per platform:

```
out/posting-tabs/
  Instagram.csv
  Facebook.csv
  TikTok.csv
  LinkedIn.csv
  X.csv
```

Each file has three columns:

| Column | What it is |
|---|---|
| Post code | The row's **Asset ID** |
| Text | The text to paste on that platform |
| Week / day | The row's **Week / day**, so you can see which rows are new |

Rows are in calendar order. Rows with no **Week / day** (seasonal posts dated in **Scheduled for**) come last.
A row appears in the file for its **Platform** and for each platform in **Also post to**.

It needs only the sheet export, not the rendered assets, so it can be run before `render.py`.

## Putting a new post on a tab

1. Open the platform's file, for example `out/posting-tabs/Instagram.csv`, in a spreadsheet.
2. On the **Post - Instagram** tab, go to the first empty row.
3. Copy the post's **Post code** into column A.
4. Copy its **Text** into the green cell on the same row.
5. Leave every other cell alone. They fill themselves.

Do this for each platform the post goes to. New rows go at the bottom of the tab; the **Schedule now** tab sorts by date.

If a post's text changes later, run the script again and copy the new **Text** into its green cell. The green cell is
fixed text, not a formula, so that it copies out of the sheet without extra quote marks.

## Where the text comes from

The same rules as the caption files `package.py` writes (`captions.py`, described in `docs/package.md`), so the green
cell and `out/posts/<brand>/<platform>/<post>/..._caption.txt` always hold the same text:

| Platform | Links | Hashtags kept |
|---|---|---|
| Instagram | removed, "Link in bio." added | first 5 |
| TikTok | removed, "Link in bio." added | first 4 |
| Facebook | kept | first 2 |
| LinkedIn | kept | first 3 |
| X | kept; a warning if the post is over 280 characters | first 2 |

A `Caption for <Platform>:` block in the Content cell is used exactly as written.

## Options

- `--out out` is the output folder. The files go in `<out>/posting-tabs`.
- `--only ADS-C01,CG-X03` writes just those posts. Files for other platforms are left as they are.

A full run (no `--only`) mirrors the sheet: a platform with no rows left has its file removed.
Asset IDs may only use letters, numbers, `-` and `_`. A second row with the same Asset ID is skipped with a warning.
