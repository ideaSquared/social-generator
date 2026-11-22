#!/usr/bin/env python3
"""Post-process a render.py output folder: LinkedIn PDFs and alt text.

Usage:
    python postprocess.py pdf <out_dir> [--only ID1,ID2]
    python postprocess.py alt <out_dir> [--only ID1,ID2]
    python postprocess.py all <out_dir> [--only ID1,ID2]

Works purely from <out_dir>/manifest.json and the images already rendered.
"""
import argparse
import json
import re
import sys
from pathlib import Path

from PIL import Image

SHORT_LIMIT = 420
# 95 keeps text crisp (Pillow embeds RGB pages as JPEG); a 7-slide PDF is ~1 MB.
PDF_QUALITY = 95


def warn(msg):
    print(f"warning: {msg}", file=sys.stderr)


def load_manifest(out_dir):
    path = out_dir / "manifest.json"
    if not path.is_file():
        raise SystemExit(f"error: {path} not found")
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise SystemExit(f"error: cannot read {path}: {exc}")
    if not isinstance(data, list):
        raise SystemExit(f"error: {path} is not a list")
    return data


def select(manifest, only):
    if not only:
        return manifest
    wanted = {s.strip() for s in only.split(",") if s.strip()}
    found = {e.get("asset") for e in manifest}
    for missing in sorted(wanted - found):
        warn(f"--only: asset {missing} not in manifest")
    return [e for e in manifest if e.get("asset") in wanted]


# ---------------------------------------------------------------- PDF

def make_pdf(out_dir, entry):
    """Write carousel.pdf for one carousel. Returns the path, or None if skipped."""
    folder = out_dir / entry["folder"]
    if not folder.is_dir():
        warn(f"{entry['asset']}: folder {folder} missing, skipped")
        return None
    slides = sorted(folder.glob("slide_*.png"))
    expected = entry.get("frames")
    if not slides:
        warn(f"{entry['asset']}: no slides found, skipped")
        return None
    if expected and len(slides) != expected:
        warn(f"{entry['asset']}: expected {expected} slides, found {len(slides)}, skipped")
        return None
    pages = []
    for p in slides:
        with Image.open(p) as im:
            pages.append(im.convert("RGB"))
    target = out_dir / entry["folder"] / "carousel.pdf"
    # resolution=72 makes one pixel one point, so pages are 1080x1350 pt (4:5).
    pages[0].save(target, "PDF", save_all=True, append_images=pages[1:],
                  resolution=72.0, quality=PDF_QUALITY)
    return target


# ---------------------------------------------------------------- alt text

def clean(text):
    return re.sub(r"\s+", " ", text or "").strip()


def humanise(text):
    """Turn 'Heading / body' into 'Heading: body'."""
    text = clean(text)
    if " / " not in text:
        return text
    head, body = text.split(" / ", 1)
    body = body.replace(" / ", " ")
    head = head.strip()
    if head[-1:] in ".!?:":
        sep = " "
    elif ":" in head:  # avoid "Free: £0: body"
        sep = ". "
    else:
        sep = ": "
    return f"{head}{sep}{body.strip()}"


def sentence(text):
    """Ensure the text ends with sentence punctuation."""
    return text if text[-1:] in ".!?" else text + "."


def strip_end(text):
    return text.rstrip(" .!?")


def build_alt(entry):
    texts = [humanise(t) for t in entry.get("text", []) if clean(t)]
    footnote = clean(entry.get("footnote"))
    if entry.get("video"):
        if not texts:
            body = "Text video."
        else:
            parts = ["Text video.", sentence(texts[0])]
            middle = texts[1:-1]
            if middle:
                parts.append("Then: " + "; ".join(strip_end(t) for t in middle) + ".")
            if len(texts) > 1:
                parts.append("Ends with: " + strip_end(texts[-1]) + ".")
            body = " ".join(parts)
        return body + (" " + sentence(footnote) if footnote else "") + "\n"
    total = len(texts)
    lines = [f"Slide {i} of {total}: {t}" for i, t in enumerate(texts, 1)]
    if footnote:
        lines.append(sentence(footnote))
    return "\n".join(lines) + "\n"


def shorten(text, limit=SHORT_LIMIT):
    """Collapse to one line and cut cleanly: sentence boundary, else word boundary."""
    flat = clean(text)
    if len(flat) <= limit:
        return flat
    window = flat[:limit]
    ends = [m.end() for m in re.finditer(r"[.!?](?=\s|$)", window)]
    if ends and ends[-1] >= limit * 0.4:
        return window[:ends[-1]].rstrip()
    budget = limit - 1  # room for the ellipsis
    cut = flat[:budget]
    if flat[budget] != " ":
        cut = cut.rsplit(" ", 1)[0] if " " in cut else cut
    return cut.rstrip(" ,;:-") + "…"


def make_alt(out_dir, entry):
    folder = out_dir / entry["folder"]
    if not folder.is_dir():
        warn(f"{entry['asset']}: folder {folder} missing, skipped")
        return None
    if not entry.get("text"):
        warn(f"{entry['asset']}: manifest has no text, skipped")
        return None
    alt = build_alt(entry)
    (folder / "alt.txt").write_text(alt, encoding="utf-8")
    (folder / "alt_short.txt").write_text(shorten(alt) + "\n", encoding="utf-8")
    return folder / "alt.txt"


# ---------------------------------------------------------------- driver

def run(out_dir, mode, only=None):
    """Returns (pdfs_written, alts_written, skipped). Raises on real errors."""
    out_dir = Path(out_dir)
    entries = select(load_manifest(out_dir), only)
    pdfs = alts = skipped = 0
    for e in entries:
        if mode in ("pdf", "all") and not e.get("video"):
            if make_pdf(out_dir, e):
                pdfs += 1
            else:
                skipped += 1
        if mode in ("alt", "all"):
            if make_alt(out_dir, e):
                alts += 1
            else:
                skipped += 1
    return pdfs, alts, skipped


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("mode", choices=["pdf", "alt", "all"])
    ap.add_argument("out_dir")
    ap.add_argument("--only", help="comma-separated asset IDs")
    args = ap.parse_args(argv)
    if not Path(args.out_dir).is_dir():
        print(f"error: {args.out_dir} is not a directory", file=sys.stderr)
        return 1
    try:
        pdfs, alts, skipped = run(args.out_dir, args.mode, args.only)
    except SystemExit as exc:
        print(exc, file=sys.stderr)
        return 1
    except (OSError, ValueError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    print(f"postprocess {args.mode}: {pdfs} PDFs, {alts} alt texts written, {skipped} skipped")
    return 0


if __name__ == "__main__":
    sys.exit(main())
