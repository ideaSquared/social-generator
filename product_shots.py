#!/usr/bin/env python3
"""Real product visuals without recording or photography.

Screenshots pages you own with headless Chrome, then places each capture in a
phone or browser frame on a brand background (AdoptDontShop, ideaSquared or
CreatrGrid) for post, story and landscape layouts. No AI, no invented content:
the only text on a graphic is the optional headline/sub from the config, the
page host in the browser URL pill, and the brand lock-up.

    python product_shots.py shots.example.json --out out/product-shots [--only NAME]

See docs/product-shots.md for the config format.
"""
import argparse, collections, json, math, os, re, shutil, subprocess, sys, tempfile
import urllib.error, urllib.request
from concurrent.futures import ThreadPoolExecutor
from urllib.parse import urlparse

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

LAYOUTS = {'post': (1080, 1350), 'story': (1080, 1920), 'landscape': (1600, 900)}
DEVICES = {
    'phone': dict(w=390, h=844, scale=3,
                  ua='Mozilla/5.0 (iPhone; CPU iPhone OS 17_5 like Mac OS X) AppleWebKit/605.1.15 '
                     '(KHTML, like Gecko) Version/17.5 Mobile/15E148 Safari/604.1'),
    'desktop': dict(w=1440, h=900, scale=2, ua=None),
}
BRANDS = ('AdoptDontShop', 'ideaSquared', 'CreatrGrid')
SCHEMES = ('light', 'dark')
ALLOWED_KEYS = {'name', 'brand', 'url', 'device', 'wait_ms', 'scroll_y', 'color_scheme',
                'headline', 'sub', 'layouts', 'check_blank'}
DEFAULT_WAIT_MS = 4000
MAX_SCROLL_Y = 20000

# A capture is rejected when it is nearly uniform: very low variance, or when
# almost every pixel is the single background colour (a Chrome error page is
# about 3% "ink", a real page is normally far above this).
MIN_STDDEV = 2.5
MIN_INK = 0.06


class ConfigError(Exception):
    def __init__(self, problems):
        self.problems = list(problems)
        super().__init__('; '.join(self.problems))


class CaptureError(Exception):
    pass


# ---------------------------------------------------------------- config
def validate_config(data):
    """Return a list of normalised shot dicts, or raise ConfigError listing every problem."""
    if isinstance(data, dict) and 'shots' in data:
        data = data['shots']
    if not isinstance(data, list) or not data:
        raise ConfigError(['config must be a non-empty list of shots (or {"shots": [...]})'])
    problems, shots, seen = [], [], set()
    for i, raw in enumerate(data):
        label = f'shot {i + 1}'
        if not isinstance(raw, dict):
            problems.append(f'{label}: must be an object')
            continue
        name = raw.get('name')
        if isinstance(name, str) and name:
            label = f'shot "{name}"'
        errs = []
        for k in raw:
            if k not in ALLOWED_KEYS:
                errs.append(f'unknown key "{k}" (allowed: {", ".join(sorted(ALLOWED_KEYS))})')
        if not isinstance(name, str) or not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_-]*', name or ''):
            errs.append('name is required: letters, digits, "-" and "_" only (used in file names)')
        elif name in seen:
            errs.append('duplicate name')
        else:
            seen.add(name)
        if not isinstance(raw.get('brand'), str) or raw.get('brand') not in BRANDS:
            errs.append(f'brand must be one of {", ".join(BRANDS)}')
        url = raw.get('url')
        if not isinstance(url, str) or not re.match(r'^(https?|file)://\S+$', url):
            errs.append('url is required and must start with http://, https:// or file://')
        device = raw.get('device')
        if not isinstance(device, str) or device not in DEVICES:
            errs.append('device must be "phone" or "desktop"')
        wait = raw.get('wait_ms', DEFAULT_WAIT_MS)
        if isinstance(wait, bool) or not isinstance(wait, int) or not 0 <= wait <= 60000:
            errs.append('wait_ms must be an integer from 0 to 60000')
        scroll = raw.get('scroll_y', 0)
        if isinstance(scroll, bool) or not isinstance(scroll, int) or not 0 <= scroll <= MAX_SCROLL_Y:
            errs.append(f'scroll_y must be an integer from 0 to {MAX_SCROLL_Y}')
        scheme = raw.get('color_scheme')
        if scheme is not None and (not isinstance(scheme, str) or scheme not in SCHEMES):
            errs.append('color_scheme must be "light" or "dark"')
        for k in ('headline', 'sub'):
            v = raw.get(k)
            if v is not None and (not isinstance(v, str) or len(v) > 160):
                errs.append(f'{k} must be a string of at most 160 characters')
        if raw.get('sub') and not raw.get('headline'):
            errs.append('sub needs a headline')
        layouts = raw.get('layouts', list(LAYOUTS))
        if (not isinstance(layouts, list) or not layouts
                or any(not isinstance(l, str) or l not in LAYOUTS for l in layouts) or len(set(layouts)) != len(layouts)):
            errs.append('layouts must be a non-empty list of unique values from post, story, landscape')
        chk = raw.get('check_blank', True)
        if not isinstance(chk, bool):
            errs.append('check_blank must be true or false')
        if errs:
            problems.extend(f'{label}: {e}' for e in errs)
            continue
        shots.append(dict(name=name, brand=raw['brand'], url=url, device=device, wait_ms=wait,
                          scroll_y=scroll, color_scheme=scheme,
                          headline=(raw.get('headline') or '').strip(), sub=(raw.get('sub') or '').strip(),
                          layouts=list(layouts), check_blank=chk))
    if problems:
        raise ConfigError(problems)
    return shots


def load_config(path):
    try:
        with open(path, encoding='utf-8') as f:
            data = json.load(f)
    except (OSError, json.JSONDecodeError) as e:
        raise ConfigError([f'cannot read config {path}: {e}'])
    return validate_config(data)


def url_host(url):
    return urlparse(url).hostname or 'localhost'


# ---------------------------------------------------------------- blank detection
def image_stats(im):
    """(greyscale stddev, ink fraction) measured on a small copy of the image.
    Ink is the share of pixels that differ visibly from the most common colour."""
    from PIL import Image, ImageStat
    im = im.convert('RGB')
    im.thumbnail((300, 650), Image.BOX)
    std = ImageStat.Stat(im.convert('L')).stddev[0]
    total = im.size[0] * im.size[1]
    cols = im.getcolors(maxcolors=total) or []
    mode = max(cols)[1] if cols else (0, 0, 0)
    far = sum(c for c, p in cols if max(abs(a - b) for a, b in zip(p, mode)) > 12)
    return std, far / total


def is_blank(im):
    std, ink = image_stats(im)
    return std < MIN_STDDEV or ink < MIN_INK


# ---------------------------------------------------------------- capture
def chrome_args(shot, out_png, profile):
    dev = DEVICES[shot['device']]
    s = dev['scale']
    args = [CHROME, '--headless=new', '--no-sandbox', '--disable-gpu', '--hide-scrollbars',
            '--no-first-run', '--disable-extensions', f'--user-data-dir={profile}',
            f'--force-device-scale-factor={s}',
            # taller window when scrolling; the top scroll_y CSS px are cropped afterwards
            f'--window-size={dev["w"]},{dev["h"] + shot["scroll_y"]}',
            f'--virtual-time-budget={shot["wait_ms"]}',
            '--run-all-compositor-stages-before-draw',
            f'--screenshot={out_png}']
    if dev['ua']:
        args.append(f'--user-agent={dev["ua"]}')
    if shot['color_scheme']:
        # Chrome's blink enum: 0 = dark, 1 = light
        args.append(f'--blink-settings=preferredColorScheme={0 if shot["color_scheme"] == "dark" else 1}')
    args.append(shot['url'])
    return args


def preflight(url):
    """Cheap reachability check so a network failure is reported as such, not as a blank image."""
    if not url.startswith(('http://', 'https://')):
        return
    req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0 product-shots'})
    try:
        urllib.request.urlopen(req, timeout=15).close()
    except urllib.error.HTTPError as e:
        raise CaptureError(f'{url} answered HTTP {e.code} (use --no-preflight if the page is fine in a browser)')
    except Exception as e:  # URLError, timeouts, TLS, proxy failures
        reason = getattr(e, 'reason', e)
        raise CaptureError(f'{url} is unreachable from this machine ({reason})')


def capture(shot, raw_dir, do_preflight=True):
    """Screenshot the page to raw/<name>.png at device size x scale. Raises CaptureError."""
    from PIL import Image
    if do_preflight:
        preflight(shot['url'])
    dev = DEVICES[shot['device']]
    s = dev['scale']
    out_png = os.path.join(raw_dir, shot['name'] + '.png')
    if os.path.exists(out_png):
        os.remove(out_png)
    profile = tempfile.mkdtemp(prefix='psh-')
    try:
        try:
            r = subprocess.run(chrome_args(shot, out_png, profile), stdout=subprocess.DEVNULL,
                               stderr=subprocess.PIPE, text=True,
                               timeout=shot['wait_ms'] / 1000 + 90)
        except subprocess.TimeoutExpired:
            raise CaptureError('Chrome timed out')
        except FileNotFoundError:
            raise CaptureError(f'Chrome not found ({CHROME}); set the CHROME environment variable')
    finally:
        shutil.rmtree(profile, ignore_errors=True)
    if r.returncode != 0 or not os.path.exists(out_png):
        tail = (r.stderr or '').strip().splitlines()[-1:] or ['no output']
        raise CaptureError(f'Chrome failed (exit {r.returncode}): {tail[0][:200]}')
    im = Image.open(out_png).convert('RGB')
    want_w, want_h = dev['w'] * s, (dev['h'] + shot['scroll_y']) * s
    if im.size != (want_w, want_h):
        raise CaptureError(f'unexpected capture size {im.size}, expected {(want_w, want_h)}')
    if shot['scroll_y']:
        im = im.crop((0, shot['scroll_y'] * s, want_w, want_h))
    im.save(out_png)
    if shot['check_blank'] and is_blank(im):
        std, ink = image_stats(im)
        raise CaptureError(f'capture is blank or nearly uniform (stddev {std:.1f}, content {ink * 100:.1f}%): '
                           'the page did not render, or Chrome showed an error page. '
                           f'Raw capture kept at {out_png} for inspection')
    return out_png


# ---------------------------------------------------------------- layout planning
def phone_dims(sw):
    b = max(8, round(sw * 0.035))
    sh = round(sw * DEVICES['phone']['h'] / DEVICES['phone']['w'])
    return dict(sw=sw, sh=sh, b=b, ow=sw + 2 * b, oh=sh + 2 * b, bar=0)


def desktop_dims(sw):
    bar = round(sw * 0.045)
    sh = round(sw * DEVICES['desktop']['h'] / DEVICES['desktop']['w'])
    return dict(sw=sw, sh=sh, b=0, ow=sw, oh=sh + bar, bar=bar)


def phone_sw_for_height(oh):
    sw = oh / (DEVICES['phone']['h'] / DEVICES['phone']['w'] + 0.07)
    return int(sw)


def plan_layout(device, layout, has_text):
    """Pure geometry for one device/layout. Returns dict with canvas, lock, text rect
    (x, y, w, h) or None, and frame (x, y plus outer/screen dims)."""
    W, H = LAYOUTS[layout]
    phone = device == 'phone'
    if layout == 'post':
        lock = (96, 84)
        if phone:
            d = phone_dims(500 if has_text else 560)
            y = 520 if has_text else 200
        else:
            d = desktop_dims(920)
            y = 600 if has_text else (H - desktop_dims(920)['oh']) // 2 + 40
        x = (W - d['ow']) // 2
        text = (96, 190, 888, 300) if has_text else None
    elif layout == 'story':
        lock = (96, 150)
        if phone:
            d = phone_dims(640 if has_text else 660)
            y = 820 if has_text else 330
        else:
            d = desktop_dims(920)
            y = 860 if has_text else (H - desktop_dims(920)['oh']) // 2
        x = (W - d['ow']) // 2
        text = (96, 290, 888, 480 if phone else 500) if has_text else None
    else:  # landscape
        if phone:
            d = phone_dims(phone_sw_for_height(780))
            y = (H - d['oh']) // 2
            x = 1280 - d['ow'] // 2 if has_text else (W - d['ow']) // 2
            lock = (96, 748) if has_text else (96, 64)
        else:
            if has_text:
                d = desktop_dims(860)
                x, y = W - 80 - d['ow'], (H - d['oh']) // 2
                lock = (96, 748)
            else:
                d = desktop_dims(980)
                x, y = (W - d['ow']) // 2, 140 + (720 - d['oh']) // 2
                lock = (80, 56)
        text = (96, 120, 540 if not phone else 780, 560) if has_text else None
    return dict(canvas=(W, H), lock=lock, text=text, frame=dict(x=x, y=y, **d))


def wrap_lines(text, size, width, em):
    """Greedy word wrap using an average character width of em * size."""
    cw = size * em
    lines, cur = 1, 0.0
    for word in text.split():
        wl = len(word) * cw
        if cur and cur + cw + wl > width:
            lines += 1
            cur = wl
        else:
            cur = cur + cw + wl if cur else wl
    return lines


def fit_text(headline, sub, width, height, em=0.56):
    """Largest headline size (with proportional sub) whose estimated height fits the box."""
    for hs in (84, 76, 68, 60, 54, 48, 42, 36):
        ss = max(26, round(hs * 0.46))
        hh = wrap_lines(headline, hs, width, em) * hs * 1.08
        sh = (wrap_lines(sub, ss, width, 0.52) * ss * 1.35 + 28) if sub else 0
        if hh + sh <= height:
            return hs, ss
    return 36, 26


# ---------------------------------------------------------------- composing
def brand_parts(brand, w, h, uid):
    import render as R
    if brand == 'AdoptDontShop':
        return dict(css=R.ADS_CSS, bg=R.ads_bg('rose', w, h), h1='#ffffff', sub='#ffffff', rule=None,
                    lock=lambda: f'<div style="background:#fff;border-radius:18px;padding:10px 20px 10px 12px;display:inline-block">{R.ads_lock(48, 30, "#be123c")}</div>',
                    h1css='font-weight:700;letter-spacing:-.02em', subcls='s', em=0.56, tc=True)
    if brand == 'ideaSquared':
        return dict(css=R.ISQ_CSS, bg=R.isq_bg(True, w, h), h1='#f7f6f2', sub='#c3c9d2', rule='#e8911a',
                    lock=lambda: R.isq_lock(56, 34, '#f7f6f2', True),
                    h1css='font-weight:500;letter-spacing:-.025em', subcls='s', em=0.5, tc=False)
    glow = ('<div style="position:absolute;left:-10%;right:-10%;top:-25%;height:75%;background:radial-gradient('
            'ellipse at 50% 0%,rgba(124,58,237,.22),rgba(236,72,153,.08) 45%,rgba(248,250,252,0) 70%)"></div>')
    return dict(css=R.CG_CSS, bg=R.cg_bg() + glow, h1='#0f172a', sub='#64748b', rule=None,
                lock=lambda: R.cg_lock(52, 38, uid),
                h1css='font-weight:700;letter-spacing:-.02em', subcls='s', em=0.56, tc=False)


def phone_html(f, img):
    sw, sh, b, ow, oh = f['sw'], f['sh'], f['b'], f['ow'], f['oh']
    r = round(sw * 0.13) + b
    btn = 'position:absolute;width:5px;border-radius:3px;background:#1b2029'
    side = (f'<div style="{btn};left:-4px;top:{round(oh*.17)}px;height:{round(oh*.035)}px"></div>'
            f'<div style="{btn};left:-4px;top:{round(oh*.24)}px;height:{round(oh*.07)}px"></div>'
            f'<div style="{btn};right:-4px;top:{round(oh*.27)}px;height:{round(oh*.11)}px"></div>')
    return (f'<div style="position:absolute;left:{f["x"]}px;top:{f["y"]}px;width:{ow}px;height:{oh}px">{side}'
            f'<div style="position:absolute;inset:0;border-radius:{r}px;background:#0d1017;padding:{b}px;'
            'box-shadow:0 0 0 2px #2b303b,0 50px 90px -10px rgba(2,6,23,.45),0 18px 36px rgba(2,6,23,.25)">'
            f'<div style="width:{sw}px;height:{sh}px;border-radius:{r - b}px;overflow:hidden;background:#fff">'
            f'<img src="file://{img}" width="{sw}" height="{sh}" style="display:block"></div></div></div>')


def desktop_html(f, img, host, dark):
    import html as H
    sw, sh, bar = f['sw'], f['sh'], f['bar']
    dot = round(bar * 0.3)
    bg, pill, ptx = ('#232834', '#14181f', '#aab3c2') if dark else ('#eceef2', '#ffffff', '#4b5563')
    dots = ''.join(f'<span style="width:{dot}px;height:{dot}px;border-radius:50%;background:{c};display:block"></span>'
                   for c in ('#ff5f57', '#febc2e', '#28c840'))
    return (f'<div style="position:absolute;left:{f["x"]}px;top:{f["y"]}px;width:{sw}px;height:{f["oh"]}px;'
            f'border-radius:{round(sw * 0.014) + 6}px;overflow:hidden;background:{bg};'
            'box-shadow:0 0 0 1px rgba(15,23,42,.18),0 50px 90px -10px rgba(2,6,23,.40),0 18px 36px rgba(2,6,23,.22)">'
            f'<div style="height:{bar}px;display:flex;align-items:center;padding:0 {round(bar * .45)}px;position:relative">'
            f'<div style="display:flex;gap:{round(dot * .7)}px">{dots}</div>'
            f'<div style="position:absolute;left:50%;top:50%;transform:translate(-50%,-50%);width:40%;height:{round(bar * .62)}px;'
            f'border-radius:999px;background:{pill};display:flex;align-items:center;justify-content:center;'
            f'font:500 {round(bar * .36)}px Inter,sans-serif;color:{ptx};white-space:nowrap;overflow:hidden">{H.escape(host)}</div></div>'
            f'<img src="file://{img}" width="{sw}" height="{sh}" style="display:block"></div>')


def compose_html(shot, layout, screen_png, uid='psh'):
    """Build the full page HTML for one layout. Returns (html, plan)."""
    import render as R
    import lib
    W, H = LAYOUTS[layout]
    has_text = bool(shot['headline'])
    plan = plan_layout(shot['device'], layout, has_text)
    P = brand_parts(shot['brand'], W, H, uid)
    f = plan['frame']
    body = P['bg']
    if has_text:
        head = lib.typo(shot['headline'])
        if P['tc']:
            head = R.tc(head)
        sub = lib.typo(shot['sub']) if shot['sub'] else ''
        tx, ty, tw, th = plan['text']
        hs, ss = fit_text(head, sub, tw, th, P['em'])
        rule = f'<div style="width:96px;height:6px;border-radius:999px;background:{P["rule"]};flex:none"></div>' if P['rule'] else ''
        subh = (f'<p class="{P["subcls"]}" style="font-size:{ss}px;line-height:1.35;color:{P["sub"]};font-weight:400;text-wrap:pretty">{R.esc(sub)}</p>' if sub else '')
        body += (f'<div style="position:absolute;left:{tx}px;top:{ty}px;width:{tw}px;height:{th}px;display:flex;'
                 f'flex-direction:column;justify-content:{"center" if layout == "landscape" else "flex-start"};gap:28px">'
                 f'<h1 style="font-size:{hs}px;line-height:1.08;color:{P["h1"]};{P["h1css"]};text-wrap:balance">{R.esc(head)}</h1>{rule}{subh}</div>')
    body += f'<div style="position:absolute;left:{plan["lock"][0]}px;top:{plan["lock"][1]}px;z-index:3">{P["lock"]()}</div>'
    if shot['device'] == 'phone':
        body += phone_html(f, screen_png)
    else:
        body += desktop_html(f, screen_png, url_host(shot['url']), shot['color_scheme'] == 'dark')
    return R.page_html(P['css'], body, W, H), plan


def prepare_screen(raw_png, f, device, dest):
    """Resize the capture to its exact displayed size. Never upscales; high quality downscale only."""
    from PIL import Image
    im = Image.open(raw_png).convert('RGB')
    if f['sw'] > im.size[0] or f['sh'] > im.size[1]:
        raise CaptureError(f'frame {f["sw"]}x{f["sh"]} would upscale capture {im.size}')
    if (f['sw'], f['sh']) != im.size:
        im = im.resize((f['sw'], f['sh']), Image.LANCZOS)
    im.save(dest)
    return dest


def compose(shot, raw_png, out_dir, tmp_dir):
    """Render every requested layout. Returns list of output paths."""
    import render as R
    from PIL import Image
    outs = []
    for layout in shot['layouts']:
        W, H = LAYOUTS[layout]
        plan = plan_layout(shot['device'], layout, bool(shot['headline']))
        screen = prepare_screen(raw_png, plan['frame'], shot['device'],
                                os.path.join(tmp_dir, f'{shot["name"]}_{layout}_screen.png'))
        html_doc, _ = compose_html(shot, layout, screen, uid=f'{shot["name"][:8]}{layout[0]}')
        hp = os.path.join(tmp_dir, f'{shot["name"]}_{layout}.html')
        with open(hp, 'w', encoding='utf-8') as fh:
            fh.write(html_doc)
        png = os.path.join(out_dir, f'{shot["name"]}_{layout}.png')
        R.shot((hp, png, W, H))
        size = Image.open(png).size
        if size != (W, H):
            raise CaptureError(f'{png} rendered at {size}, expected {(W, H)}')
        outs.append(png)
    return outs


# ---------------------------------------------------------------- CLI
def run(shots, out, do_preflight=True):
    """Process shots; returns {name: ('ok', [paths]) | ('error', message)}."""
    raw_dir = os.path.join(out, 'raw')
    tmp_dir = os.path.join(out, '.html')
    os.makedirs(raw_dir, exist_ok=True)
    os.makedirs(tmp_dir, exist_ok=True)

    def one(shot):
        try:
            raw = capture(shot, raw_dir, do_preflight)
            return shot['name'], ('ok', compose(shot, raw, out, tmp_dir))
        except CaptureError as e:
            return shot['name'], ('error', str(e))
        except (subprocess.CalledProcessError, subprocess.TimeoutExpired, OSError) as e:
            return shot['name'], ('error', f'{type(e).__name__}: {e}')
    with ThreadPoolExecutor(min(3, len(shots))) as ex:
        return dict(ex.map(one, shots))


def main(argv=None):
    ap = argparse.ArgumentParser(description='Screenshot your own product pages and compose branded device-frame graphics.')
    ap.add_argument('config', help='JSON config: a list of shots (see docs/product-shots.md)')
    ap.add_argument('--out', default='out/product-shots', help='output directory (default out/product-shots)')
    ap.add_argument('--only', default='', help='only this shot name (comma-separated for several)')
    ap.add_argument('--no-preflight', action='store_true', help='skip the Python reachability check before Chrome')
    a = ap.parse_args(argv)
    try:
        shots = load_config(a.config)
    except ConfigError as e:
        print('Config errors:', file=sys.stderr)
        for p in e.problems:
            print(f'  - {p}', file=sys.stderr)
        return 2
    if a.only:
        want = {x for x in a.only.split(',') if x}
        unknown = want - {s['name'] for s in shots}
        if unknown:
            print(f'--only: no shot named {", ".join(sorted(unknown))}', file=sys.stderr)
            return 2
        shots = [s for s in shots if s['name'] in want]
    out = os.path.abspath(a.out)
    res = run(shots, out, not a.no_preflight)
    bad = 0
    for s in shots:
        kind, val = res[s['name']]
        if kind == 'ok':
            print(f'OK    {s["name"]}: {", ".join(os.path.basename(p) for p in val)}')
        else:
            bad += 1
            print(f'ERROR {s["name"]}: {val}', file=sys.stderr)
    print(f'{len(shots) - bad} ok, {bad} failed -> {out}')
    return 1 if bad else 0


# Imported lazily-safe: render.py defines CHROME and is safe to import.
from render import CHROME  # noqa: E402

if __name__ == '__main__':
    sys.exit(main())
