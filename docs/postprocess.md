# Post-processing: PDF carousels and alt text

`postprocess.py` works on an existing output folder (the one `render.py`
wrote, containing `manifest.json`). It never re-renders anything and needs
only Python 3 and Pillow.

```
python postprocess.py pdf <out_dir>     # carousel.pdf per carousel
python postprocess.py alt <out_dir>     # alt.txt and alt_short.txt per asset
python postprocess.py all <out_dir>     # both
python postprocess.py all <out_dir> --only ADS-C04,CG-V05
```

## PDF

LinkedIn carousels are uploaded as a PDF document, not as an image set.
`carousel.pdf` is written next to the slides of every carousel: one slide per
page, in order, 1080x1350 pt (4:5, the same shape as the PNGs). Videos are
ignored. A 7-slide carousel comes to roughly 0.8 MB, well under LinkedIn's
limits.

## Alt text

- `alt.txt`: carousels get one line per slide (`Slide 2 of 6: Heading: body`);
  videos get one short paragraph (`Text video. ... Then: ...; .... Ends with: ....`).
  The footnote, if any, is added once at the end. The ` / ` heading/body
  separator in the manifest becomes `Heading: body`.
- `alt_short.txt`: the same text on one line, cut at a sentence (or word)
  boundary to at most 420 characters, for platforms with tight limits.

Slide numbers in alt text count every slide in the folder, including the
cover and the call-to-action slide.

## Behaviour

Assets whose folder or slides are missing are skipped with a warning on
stderr. The exit code is non-zero only for real errors (missing or unreadable
manifest, bad output folder, write failures). A one-line summary is printed
at the end. Generated PDFs and text files should not be committed.
