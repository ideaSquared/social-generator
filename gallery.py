#!/usr/bin/env python3
"""Build a single-page review gallery from render.py output and the sheet CSV.

    python gallery.py <out_dir> --csv <sheet.csv> [--week N] [--output PATH]

Writes one self-contained index.html (inline CSS and JS, no external
requests). Images and videos are referenced by relative path, so the folder
can be zipped or opened straight from disk.
"""
import argparse
import csv
import html
import json
import os
import re
import sys
from urllib.parse import quote

DAYS = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
DAY_NAMES = {
    "Mon": "Monday", "Tue": "Tuesday", "Wed": "Wednesday", "Thu": "Thursday",
    "Fri": "Friday", "Sat": "Saturday", "Sun": "Sunday",
}
BRAND_CLASS = {
    "adoptdontshop": "ads",
    "ideasquared": "isq",
    "creatrgrid": "cg",
}
UNSCHEDULED = (0, 99)

_WEEK_DAY_RE = re.compile(r"week\s*(\d+)\s*[·\-–—.,:|/]*\s*([A-Za-z]+)?", re.I)
_CAPTION_RE = re.compile(r"^[ \t]*caption[ \t]*:[ \t]*", re.I | re.M)
# "checked"/"confirmed" describe work already done, so they do not flag.
_FLAG_RE = re.compile(r"conflict|\b(?:re-?)?(?:confirm|check)\b|not confirmed", re.I)
_CONFLICT_RE = re.compile(r"conflict", re.I)


# ---------------------------------------------------------------- parsing

def parse_week_day(value):
    """'Week 3 · Tue' -> (3, 1). Unparseable -> (0, 99); no day -> day 99."""
    m = _WEEK_DAY_RE.search(value or "")
    if not m:
        return UNSCHEDULED
    week = int(m.group(1))
    day = 99
    if m.group(2):
        key = m.group(2)[:3].title()
        if key in DAYS:
            day = DAYS.index(key)
    return week, day


def extract_caption(content, fmt=None, asset_id=None):
    """Caption text for a post.

    Text posts (no asset) use the whole Content. Otherwise the caption is the
    text after the first line starting `Caption:`; empty if there is none.
    """
    content = (content or "").replace("\r\n", "\n").replace("\r", "\n").strip()
    is_text = (fmt or "").strip().lower() == "text post" or (
        (asset_id or "").strip().lower() in ("text only", ""))
    if is_text:
        return content
    m = _CAPTION_RE.search(content)
    return content[m.end():].strip() if m else ""


def split_platforms(value):
    return [p.strip() for p in re.split(r"[,;/]", value or "") if p.strip()]


def note_level(note):
    """'conflict', 'flag' or '' for a 'Check before posting' note."""
    if not note:
        return ""
    if _CONFLICT_RE.search(note):
        return "conflict"
    if _FLAG_RE.search(note):
        return "flag"
    return ""


def load_posts(csv_path):
    with open(csv_path, newline="", encoding="utf-8-sig") as fh:
        rows = list(csv.DictReader(fh))
    posts = []
    for i, row in enumerate(rows):
        row = {k: (v or "").strip() for k, v in row.items() if k is not None}
        week, day = parse_week_day(row.get("Week / day", ""))
        asset = row.get("Asset ID", "")
        has_asset = bool(asset) and asset.lower() != "text only"
        posts.append({
            "index": i,
            "week": week,
            "day": day,
            "brand": row.get("Brand", ""),
            "platform": row.get("Platform", ""),
            "also": split_platforms(row.get("Also post to", "")),
            "title": row.get("Title", ""),
            "pillar": row.get("Pillar", ""),
            "format": row.get("Format", ""),
            "asset": asset if has_asset else "",
            "caption": extract_caption(row.get("Content", ""),
                                       row.get("Format", ""), asset),
            "check": row.get("Check before posting", ""),
            "link": row.get("Link", ""),
            "status": row.get("Status", ""),
            "scheduled": row.get("Scheduled for", ""),
        })
    posts.sort(key=lambda p: (p["week"], p["day"], p["index"]))
    return posts


def load_manifest(out_dir):
    path = os.path.join(out_dir, "manifest.json")
    if not os.path.isfile(path):
        return {}
    with open(path, encoding="utf-8") as fh:
        return {m["asset"]: m for m in json.load(fh)}


# -------------------------------------------------------------- rendering

def esc(value):
    return html.escape(str(value), quote=True)


def url_path(out_dir, out_file, *parts):
    """Relative URL from the output file's folder to a file under out_dir."""
    target = os.path.join(out_dir, *parts)
    rel = os.path.relpath(target, os.path.dirname(os.path.abspath(out_file)))
    return quote(rel.replace(os.sep, "/"))


def safe_link(url):
    return url if re.match(r"^https?://", url or "", re.I) else ""


def brand_tag(brand):
    cls = BRAND_CLASS.get((brand or "").replace(" ", "").lower(), "other")
    return '<span class="brand b-%s">%s</span>' % (cls, esc(brand or "No brand"))


def render_media(post, entry, out_dir, out_file):
    """Return (html, status) for the post's asset area."""
    if not post["asset"]:
        return "", "text"
    if not entry:
        return ('<div class="missing" role="note"><strong>Not rendered yet</strong>'
                '<span>%s is in the sheet but not in the manifest.</span></div>'
                % esc(post["asset"])), "missing"
    folder = entry["folder"]
    if not os.path.isdir(os.path.join(out_dir, folder)):
        return ('<div class="missing" role="note"><strong>Not rendered yet</strong>'
                '<span>Folder %s is missing.</span></div>' % esc(folder)), "missing"

    texts = entry.get("text") or []
    is_video = bool(entry.get("video"))
    n = int(entry.get("frames") or len(texts) or 0)
    items = []
    present = 0
    for i in range(1, n + 1):
        rel = ("frames", "frame_%02d.png" % i) if is_video else ("slide_%02d.png" % i,)
        alt = texts[i - 1] if i - 1 < len(texts) else ""
        label = "%s %s %d of %d" % (post["asset"], "frame" if is_video else "slide", i, n)
        alt = "%s: %s" % (label, alt) if alt else label
        if not os.path.isfile(os.path.join(out_dir, folder, *rel)):
            items.append('<div class="thumb gone %s" role="img" aria-label="%s">'
                         '<span>Missing</span></div>'
                         % ("tall" if is_video else "portrait", esc(label + " (file missing)")))
            continue
        present += 1
        src = url_path(out_dir, out_file, folder, *rel)
        items.append(
            '<button type="button" class="thumb %s" data-src="%s" data-alt="%s" '
            'aria-label="Open %s large">'
            '<img src="%s" alt="%s" loading="lazy" decoding="async"></button>'
            % ("tall" if is_video else "portrait", src, esc(alt), esc(label), src, esc(alt)))

    video = ""
    if is_video:
        vpath = os.path.join(out_dir, folder, "video.mp4")
        if os.path.isfile(vpath):
            poster = ""
            if os.path.isfile(os.path.join(out_dir, folder, "frames", "frame_01.png")):
                poster = ' poster="%s"' % url_path(out_dir, out_file, folder, "frames", "frame_01.png")
            video = ('<video class="vid" controls preload="none"%s src="%s" '
                     'aria-label="Video for %s"></video>'
                     % (poster, url_path(out_dir, out_file, folder, "video.mp4"), esc(post["asset"])))
        else:
            video = '<div class="thumb gone tall"><span>No video file</span></div>'
    if not items and not video:
        return ('<div class="missing" role="note"><strong>Not rendered yet</strong>'
                '<span>No frames listed for %s.</span></div>' % esc(post["asset"])), "missing"
    kind = "Video frames" if is_video else "Slides"
    return ('<div class="strip" role="group" aria-label="%s for %s" tabindex="0">%s%s</div>'
            % (kind, esc(post["asset"]), video, "".join(items))), "ok"


def render_post(post, entry, out_dir, out_file):
    media, status = render_media(post, entry, out_dir, out_file)
    platforms = [post["platform"]] + [p for p in post["also"] if p != post["platform"]]
    plat_attr = "|".join(p.lower() for p in platforms if p)
    plat_html = '<span class="plat primary">%s</span>' % esc(post["platform"] or "No platform")
    if post["also"]:
        plat_html += ('<span class="also"><span class="muted">also</span> %s</span>'
                      % esc(", ".join(post["also"])))

    meta = []
    if post["pillar"]:
        meta.append(("Pillar", post["pillar"]))
    if post["format"]:
        meta.append(("Format", post["format"]))
    if post["asset"]:
        meta.append(("Asset", post["asset"]))
    if post["status"]:
        meta.append(("Status", post["status"]))
    if post["scheduled"]:
        meta.append(("Scheduled", post["scheduled"]))
    meta_html = "".join("<div><dt>%s</dt><dd>%s</dd></div>" % (esc(k), esc(v)) for k, v in meta)

    link = safe_link(post["link"])
    link_html = ('<a class="link" href="%s" target="_blank" rel="noopener noreferrer">%s</a>'
                 % (esc(link), esc(link))) if link else ""

    cap_id = "cap-%d" % post["index"]
    if post["caption"]:
        caption = ('<div class="cap-head"><h4 id="%s-h">%s</h4>'
                   '<button type="button" class="btn copy" data-copy="%s" '
                   'aria-label="Copy caption for %s">Copy caption</button></div>'
                   '<div class="caption" id="%s" lang="en-GB">%s</div>'
                   % (cap_id, "Post text" if not post["asset"] else "Caption",
                      cap_id, esc(post["title"]), cap_id, esc(post["caption"])))
    else:
        caption = ('<div class="cap-head"><h4>Caption</h4></div>'
                   '<div class="caption empty">No caption in the sheet.</div>')

    level = note_level(post["check"])
    if post["check"]:
        label = {"conflict": "Conflict, check before posting",
                 "flag": "Check before posting"}.get(level, "Before posting")
        check = ('<div class="check %s" role="note"><h4>%s</h4><div>%s</div></div>'
                 % (level or "plain", label, esc(post["check"])))
    else:
        check = ('<div class="check none"><h4>Check before posting</h4>'
                 '<div class="muted">Nothing noted.</div></div>')

    classes = "post " + ("textcard" if not post["asset"] else "has-asset")
    if status == "missing":
        classes += " is-missing"
    return (
        '<article class="%s" data-brand="%s" data-platforms="%s" data-asset="%s">'
        '<header><div class="tags">%s%s</div>'
        '<h3>%s</h3>%s<dl class="meta">%s</dl></header>'
        '%s'
        '<div class="body"><section class="cap">%s</section>'
        '<section class="chk">%s</section></div></article>'
        % (classes, esc(post["brand"].lower()), esc(plat_attr), esc(post["asset"]),
           brand_tag(post["brand"]), plat_html, esc(post["title"] or "Untitled"),
           ('<p class="linkline">%s</p>' % link_html) if link_html else "",
           meta_html, ('<div class="media">%s</div>' % media) if media else "",
           caption, check))


def build_html(posts, manifest, out_dir, out_file, week=None):
    if week is not None:
        posts = [p for p in posts if p["week"] == week]
    weeks = {}
    for p in posts:
        weeks.setdefault(p["week"], {}).setdefault(p["day"], []).append(p)

    brands = sorted({p["brand"] for p in posts if p["brand"]}, key=str.lower)
    plats = []
    for p in posts:
        for name in [p["platform"]] + p["also"]:
            if name and name.lower() not in [x.lower() for x in plats]:
                plats.append(name)
    plats.sort(key=str.lower)

    def opts(values, all_label):
        return ('<option value="">%s</option>' % esc(all_label)) + "".join(
            '<option value="%s">%s</option>' % (esc(str(v[0])), esc(v[1])) for v in values)

    week_opts = opts([(w, "Week %d" % w if w else "Unscheduled") for w in sorted(weeks)],
                     "All weeks")
    sections = []
    for w in sorted(weeks):
        days_html = []
        for d in sorted(weeks[w]):
            day_name = DAY_NAMES.get(DAYS[d], DAYS[d]) if d < len(DAYS) else "No day set"
            cards = "".join(render_post(p, manifest.get(p["asset"]), out_dir, out_file)
                            for p in weeks[w][d])
            days_html.append(
                '<section class="day"><h3 class="dayh">%s <span class="count"></span></h3>%s</section>'
                % (esc(day_name), cards))
        sections.append(
            '<section class="week" data-week="%d"><h2 class="weekh">%s <span class="count"></span></h2>%s</section>'
            % (w, esc("Week %d" % w if w else "Unscheduled"), "".join(days_html)))

    total = len(posts)
    title = "Post review" + (" · week %d" % week if week is not None else "")
    return PAGE.format(
        title=esc(title),
        css=CSS,
        js=JS,
        total=total,
        brand_opts=opts([(b.lower(), b) for b in brands], "All brands"),
        plat_opts=opts([(p.lower(), p) for p in plats], "All platforms"),
        week_opts=week_opts,
        body="".join(sections) or '<p class="empty-all">No posts found.</p>',
    )


PAGE = """<!DOCTYPE html>
<html lang="en-GB">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta name="color-scheme" content="light dark">
<title>{title}</title>
<style>{css}</style>
</head>
<body>
<a class="skip" href="#posts">Skip to posts</a>
<header class="top">
  <div class="top-in">
    <div class="titleline"><h1>{title}</h1><p class="summary" id="summary" aria-live="polite">{total} posts</p></div>
    <form class="filters" onsubmit="return false" aria-label="Filters">
      <label>Brand<select id="f-brand">{brand_opts}</select></label>
      <label>Platform<select id="f-plat">{plat_opts}</select></label>
      <label>Week<select id="f-week">{week_opts}</select></label>
      <button type="button" class="btn ghost" id="f-reset">Reset</button>
    </form>
  </div>
</header>
<main id="posts">
{body}
<p class="empty-all" id="none" hidden>Nothing matches those filters.</p>
</main>
<div class="lb" id="lb" role="dialog" aria-modal="true" aria-label="Image viewer" hidden>
  <div class="lb-bar"><span id="lb-count" aria-live="polite"></span>
    <button type="button" class="btn" id="lb-close">Close</button></div>
  <button type="button" class="lb-nav prev" id="lb-prev" aria-label="Previous">&#8249;</button>
  <figure><img id="lb-img" alt=""><figcaption id="lb-cap"></figcaption></figure>
  <button type="button" class="lb-nav next" id="lb-next" aria-label="Next">&#8250;</button>
</div>
<div class="toast" id="toast" role="status" aria-live="polite"></div>
<script>{js}</script>
</body>
</html>
"""

CSS = """
:root{--bg:#f6f6f4;--surface:#fff;--surface2:#f0f0ed;--text:#1c1e21;--muted:#5b6068;
--line:#dcdcd6;--accent:#1d4ed8;--accent-fg:#fff;--flag-bg:#fff6dd;--flag-line:#b7791f;--flag-text:#5c3d06;
--conf-bg:#ffe9e7;--conf-line:#c0392b;--conf-text:#6b1a12;--radius:10px;--gap:16px}
@media (prefers-color-scheme:dark){:root{--bg:#121315;--surface:#1b1c1f;--surface2:#25272b;--text:#ececea;
--muted:#a0a4ab;--line:#33363b;--accent:#8ab4ff;--accent-fg:#0b1220;--flag-bg:#2b2410;--flag-line:#d9a441;
--flag-text:#f2dca6;--conf-bg:#33170f;--conf-line:#ef6a58;--conf-text:#ffc9c0}}
*{box-sizing:border-box}
html{-webkit-text-size-adjust:100%}
body{margin:0;background:var(--bg);color:var(--text);line-height:1.5;
font:16px/1.5 system-ui,-apple-system,"Segoe UI",Roboto,"Helvetica Neue",Arial,sans-serif}
h1,h2,h3,h4,p,dl,dd{margin:0}
:focus-visible{outline:3px solid var(--accent);outline-offset:2px;border-radius:4px}
.skip{position:absolute;left:-999px;top:8px;background:var(--surface);padding:8px 12px;z-index:50}
.skip:focus{left:8px}
.muted{color:var(--muted)}
.top{position:sticky;top:0;z-index:20;background:var(--bg);border-bottom:1px solid var(--line)}
.top-in{max-width:1100px;margin:0 auto;padding:12px 16px;display:flex;flex-wrap:wrap;gap:10px 24px;align-items:end;justify-content:space-between}
.titleline h1{font-size:1.15rem;letter-spacing:-.01em}
.summary{color:var(--muted);font-size:.875rem}
.filters{display:flex;flex-wrap:wrap;gap:10px;align-items:end}
.filters label{display:flex;flex-direction:column;gap:2px;font-size:.75rem;color:var(--muted);font-weight:600;text-transform:uppercase;letter-spacing:.04em}
select{min-height:44px;font:inherit;font-size:1rem;color:var(--text);background:var(--surface);border:1px solid var(--line);border-radius:8px;padding:0 10px;min-width:9.5rem}
.btn{min-height:44px;padding:0 16px;font:inherit;font-weight:600;font-size:.9rem;border-radius:8px;border:1px solid var(--accent);background:var(--accent);color:var(--accent-fg);cursor:pointer}
.btn:hover{filter:brightness(1.08)}
.btn.ghost{background:transparent;color:var(--accent)}
.btn.copy{min-height:44px;background:transparent;color:var(--accent)}
.btn.copy.done{background:var(--accent);color:var(--accent-fg)}
main{max-width:1100px;margin:0 auto;padding:8px 16px 64px}
.weekh{font-size:1.6rem;letter-spacing:-.02em;margin:40px 0 4px;padding-bottom:8px;border-bottom:2px solid var(--text)}
.dayh{font-size:.8rem;text-transform:uppercase;letter-spacing:.08em;color:var(--muted);margin:24px 0 10px}
.count{font-weight:400;letter-spacing:0;text-transform:none;margin-left:6px}
.weekh .count{font-size:.9rem;color:var(--muted);font-weight:400}
.post{background:var(--surface);border:1px solid var(--line);border-radius:var(--radius);margin:0 0 var(--gap);overflow:hidden}
.post>header{padding:16px 16px 12px}
.tags{display:flex;flex-wrap:wrap;gap:6px 10px;align-items:center;margin-bottom:8px;font-size:.85rem}
.brand{display:inline-block;padding:2px 9px;border-radius:999px;font-size:.78rem;font-weight:700;letter-spacing:.01em;border:1px solid transparent}
.b-ads{background:#F43F5E;color:#1f0309}
.b-isq{background:#08182a;color:#e8911a;border-color:#e8911a}
.b-cg{background:#7c3aed;color:#fff}
.b-other{background:var(--surface2);color:var(--text);border-color:var(--line)}
.plat{font-weight:600}
.also{color:var(--text)}
.post h3{font-size:1.15rem;line-height:1.3;letter-spacing:-.01em}
.linkline{font-size:.85rem;margin-top:4px;word-break:break-all}
.link{color:var(--accent)}
.meta{display:flex;flex-wrap:wrap;gap:4px 18px;margin-top:10px;font-size:.82rem}
.meta div{display:flex;gap:6px}
.meta dt{color:var(--muted)}
.meta dd{font-weight:600}
.media{background:var(--surface2);border-block:1px solid var(--line);padding:12px 0}
.strip{display:flex;gap:10px;overflow-x:auto;padding:0 16px 6px;scroll-snap-type:x proximity;scroll-padding:0 16px;-webkit-overflow-scrolling:touch;align-items:flex-start}
.strip>*{flex:none;scroll-snap-align:start}
.thumb{display:block;padding:0;border:1px solid var(--line);border-radius:8px;background:var(--surface);overflow:hidden;cursor:zoom-in;height:240px}
.thumb.tall{height:320px}
.thumb.portrait{aspect-ratio:4/5}
.thumb.tall{aspect-ratio:9/16}
.thumb img{display:block;width:100%;height:100%;object-fit:cover}
.thumb.gone{display:flex;align-items:center;justify-content:center;color:var(--muted);font-size:.8rem;cursor:default;border-style:dashed}
.vid{height:320px;aspect-ratio:9/16;border-radius:8px;background:#000;display:block}
.missing{margin:0 16px;padding:14px 16px;border:1px dashed var(--line);border-radius:8px;display:flex;flex-direction:column;gap:2px;color:var(--muted)}
.missing strong{color:var(--text)}
.body{display:grid;grid-template-columns:minmax(0,3fr) minmax(0,2fr);gap:20px;padding:16px}
.cap-head{display:flex;justify-content:space-between;align-items:center;gap:8px;margin-bottom:8px;min-height:44px}
h4{font-size:.75rem;text-transform:uppercase;letter-spacing:.07em;color:var(--muted)}
.caption{white-space:pre-wrap;overflow-wrap:anywhere;font-size:.98rem;line-height:1.55;background:var(--surface2);padding:12px 14px;border-radius:8px}
.caption.empty{color:var(--muted);font-style:italic}
.check{padding:12px 14px;border-radius:8px;border:1px solid var(--line);border-left-width:5px;font-size:.95rem;white-space:pre-wrap;overflow-wrap:anywhere}
.check h4{margin-bottom:6px;white-space:normal}
.check.flag{background:var(--flag-bg);border-color:var(--flag-line);color:var(--flag-text)}
.check.flag h4{color:var(--flag-text)}
.check.conflict{background:var(--conf-bg);border-color:var(--conf-line);color:var(--conf-text)}
.check.conflict h4{color:var(--conf-text)}
.check.plain{background:var(--surface2)}
.check.none{border-style:dashed;background:transparent}
.chk{align-self:start}
.textcard{border-left:4px solid var(--line)}
.is-missing{border-style:dashed}
.empty-all{padding:48px 0;text-align:center;color:var(--muted)}
.lb{position:fixed;inset:0;z-index:100;background:rgba(0,0,0,.92);display:flex;align-items:center;justify-content:center;padding:56px 8px 8px}
.lb[hidden]{display:none}
.lb figure{margin:0;max-width:min(92vw,900px);max-height:100%;display:flex;flex-direction:column;align-items:center;gap:8px}
.lb img{max-width:100%;max-height:calc(100vh - 150px);object-fit:contain;border-radius:6px;background:#000}
.lb figcaption{color:#e6e6e6;font-size:.85rem;max-width:60ch;text-align:center;max-height:4.5em;overflow:auto}
.lb-bar{position:absolute;top:0;left:0;right:0;display:flex;justify-content:space-between;align-items:center;padding:8px 12px;color:#e6e6e6;font-size:.9rem}
.lb .btn{background:#fff;color:#111;border-color:#fff}
.lb-nav{position:absolute;top:50%;transform:translateY(-50%);width:52px;height:72px;border:0;border-radius:10px;background:rgba(255,255,255,.16);color:#fff;font-size:2.4rem;cursor:pointer;line-height:1}
.lb-nav:hover{background:rgba(255,255,255,.28)}
.lb-nav.prev{left:6px}.lb-nav.next{right:6px}
.lb-nav[hidden]{display:none}
.lb :focus-visible{outline-color:#fff}
.toast{position:fixed;left:50%;bottom:20px;transform:translate(-50%,20px);background:var(--text);color:var(--bg);padding:10px 16px;border-radius:8px;opacity:0;pointer-events:none;transition:opacity .2s,transform .2s;z-index:120;font-size:.9rem}
.toast.show{opacity:1;transform:translate(-50%,0)}
@media (max-width:760px){
 .top-in{padding:10px 12px}
 .filters{width:100%;display:grid;grid-template-columns:1fr 1fr;gap:8px}
 .filters select{width:100%;min-width:0}
 .filters .btn{align-self:end}
 main{padding:4px 12px 48px}
 .weekh{font-size:1.35rem;margin-top:28px}
 .body{grid-template-columns:1fr;gap:14px}
 .btn.copy{min-width:9rem}
 .thumb{height:210px}.thumb.tall,.vid{height:280px}
 .strip{padding:0 12px 6px}
 .top{position:static}
}
@media (prefers-reduced-motion:reduce){*{transition:none!important;scroll-behavior:auto!important}}
"""

JS = r"""
(function(){
'use strict';
var $=function(s,r){return (r||document).querySelector(s)};
var $$=function(s,r){return Array.prototype.slice.call((r||document).querySelectorAll(s))};
var fb=$('#f-brand'),fp=$('#f-plat'),fw=$('#f-week');
function apply(){
  var b=fb.value,p=fp.value,w=fw.value,shown=0,total=0;
  $$('.week').forEach(function(wk){
    var wOk=!w||wk.getAttribute('data-week')===w,wc=0;
    $$('.day',wk).forEach(function(day){
      var dc=0;
      $$('.post',day).forEach(function(post){
        var ok=wOk&&(!b||post.getAttribute('data-brand')===b)&&
          (!p||post.getAttribute('data-platforms').split('|').indexOf(p)>-1);
        post.hidden=!ok;if(ok){dc++}
      });
      day.hidden=!dc;wc+=dc;
      $('.count',day).textContent=dc?'('+dc+')':'';
    });
    wk.hidden=!wc;shown+=wc;
    $('.count',wk).textContent=wc?'· '+wc+(wc===1?' post':' posts'):'';
  });
  total=$$('.post').length;
  $('#summary').textContent=(shown===total?total+' posts':shown+' of '+total+' posts');
  $('#none').hidden=shown>0;
}
[fb,fp,fw].forEach(function(el){el.addEventListener('change',apply)});
$('#f-reset').addEventListener('click',function(){fb.value=fp.value=fw.value='';apply()});
apply();

var toastEl=$('#toast'),tt;
function toast(msg){toastEl.textContent=msg;toastEl.classList.add('show');clearTimeout(tt);
  tt=setTimeout(function(){toastEl.classList.remove('show')},1800)}
function fallbackCopy(text){
  var ta=document.createElement('textarea');ta.value=text;ta.setAttribute('readonly','');
  ta.style.position='fixed';ta.style.opacity='0';document.body.appendChild(ta);ta.select();
  var ok=false;try{ok=document.execCommand('copy')}catch(e){}
  document.body.removeChild(ta);return ok}
document.addEventListener('click',function(e){
  var c=e.target.closest('.copy');
  if(c){
    var text=document.getElementById(c.getAttribute('data-copy')).textContent;
    var done=function(ok){
      toast(ok?'Caption copied':'Copy failed: select the text instead');
      if(ok){c.classList.add('done');c.textContent='Copied';
        setTimeout(function(){c.classList.remove('done');c.textContent='Copy caption'},1500)}};
    if(navigator.clipboard&&window.isSecureContext){
      navigator.clipboard.writeText(text).then(function(){done(true)},function(){done(fallbackCopy(text))});
    }else{done(fallbackCopy(text))}
    return;
  }
  var t=e.target.closest('.thumb[data-src]');
  if(t){openLb(t)}
});

var lb=$('#lb'),img=$('#lb-img'),cap=$('#lb-cap'),count=$('#lb-count'),
    prev=$('#lb-prev'),next=$('#lb-next'),items=[],pos=0,opener=null;
function show(i){
  pos=(i+items.length)%items.length;var t=items[pos];
  img.src=t.getAttribute('data-src');img.alt=t.getAttribute('data-alt');
  cap.textContent=t.getAttribute('data-alt');
  count.textContent=(pos+1)+' / '+items.length;
  prev.hidden=next.hidden=items.length<2;
}
function openLb(t){
  opener=t;items=$$('.thumb[data-src]',t.parentNode);
  lb.hidden=false;document.body.style.overflow='hidden';
  show(items.indexOf(t));$('#lb-close').focus();
}
function closeLb(){
  lb.hidden=true;document.body.style.overflow='';img.removeAttribute('src');
  if(opener){opener.focus()}
}
$('#lb-close').addEventListener('click',closeLb);
prev.addEventListener('click',function(e){e.stopPropagation();show(pos-1)});
next.addEventListener('click',function(e){e.stopPropagation();show(pos+1)});
lb.addEventListener('click',function(e){if(e.target===lb||e.target.tagName==='FIGURE')closeLb()});
document.addEventListener('keydown',function(e){
  if(lb.hidden)return;
  if(e.key==='Escape'){closeLb()}
  else if(e.key==='ArrowLeft'){show(pos-1);e.preventDefault()}
  else if(e.key==='ArrowRight'){show(pos+1);e.preventDefault()}
  else if(e.key==='Tab'){
    var f=[$('#lb-close'),prev,next].filter(function(x){return !x.hidden});
    var i=f.indexOf(document.activeElement);
    e.preventDefault();f[(i+(e.shiftKey?-1:1)+f.length)%f.length].focus();
  }
});
var sx=null;
lb.addEventListener('touchstart',function(e){sx=e.touches[0].clientX},{passive:true});
lb.addEventListener('touchend',function(e){
  if(sx===null)return;var dx=e.changedTouches[0].clientX-sx;sx=null;
  if(Math.abs(dx)>50&&items.length>1){show(pos+(dx<0?1:-1))}
});
})();
"""


# ------------------------------------------------------------------- main

def main(argv=None):
    ap = argparse.ArgumentParser(description="Build a review gallery page for a week of posts.")
    ap.add_argument("out_dir", help="render.py output folder (contains manifest.json)")
    ap.add_argument("--csv", required=True, help="sheet CSV export")
    ap.add_argument("--week", type=int, help="only include this week number")
    ap.add_argument("--output", help="HTML path (default: <out_dir>/index.html)")
    args = ap.parse_args(argv)

    out_dir = args.out_dir
    if not os.path.isdir(out_dir):
        ap.error("out_dir not found: %s" % out_dir)
    out_file = args.output or os.path.join(out_dir, "index.html")
    manifest = load_manifest(out_dir)
    if not manifest:
        print("warning: no manifest.json entries in %s; assets will show as not rendered"
              % out_dir, file=sys.stderr)
    posts = load_posts(args.csv)
    page = build_html(posts, manifest, out_dir, out_file, args.week)
    os.makedirs(os.path.dirname(os.path.abspath(out_file)), exist_ok=True)
    with open(out_file, "w", encoding="utf-8") as fh:
        fh.write(page)
    shown = [p for p in posts if args.week is None or p["week"] == args.week]
    print("wrote %s (%d posts)" % (out_file, len(shown)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
