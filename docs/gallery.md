# Review gallery

`gallery.py` builds one self-contained `index.html` so a week of posts can be approved in one place, including on a phone.

```
python gallery.py out --csv sheet.csv
python gallery.py out --csv sheet.csv --week 3
python gallery.py out --csv sheet.csv --output /tmp/review/index.html
```

- `out` is the folder `render.py` wrote (it must contain `manifest.json`).
- `--csv` is the sheet export. Rows are matched to assets by Asset ID.
- `--week N` includes only that week. Without it all weeks are included and the page has Brand, Platform and Week filters.
- `--output` defaults to `<out>/index.html`. Image and video paths are relative to the output file, so the page works from disk and the folder can be zipped.

Each post shows brand, platform (plus "Also post to"), pillar, format, Asset ID, the caption with a Copy caption button, and the "Check before posting" note. Notes containing CONFLICT are red; notes containing "confirm" or "check" are amber. Carousels are a scrollable strip of slides; videos have a player plus the frame strip. Click a thumbnail for the lightbox (Escape closes, arrow keys move within the asset). Text-only posts appear as cards. Assets in the sheet but not rendered show "Not rendered yet".

No external requests are made; the only outbound links are those from the sheet's Link column. Standard library only.
