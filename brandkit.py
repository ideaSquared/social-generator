"""Static brand kit per brand: profile banners, avatar, highlight covers, link preview.

    python brandkit.py --out out [--brand NAME]

Writes <out>/<Brand>/brandkit/*.png. Everything is composed from the template
helpers in render.py (marks, lock-ups, backgrounds); nothing is redrawn here.
"""
import os, re, sys, argparse, tempfile
from concurrent.futures import ThreadPoolExecutor

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import render as R

LINES = {
    'AdoptDontShop': ['Find UK Rescue Animals in One Place'],
    'ideaSquared': ['A venture studio that builds in the open.'],
    'CreatrGrid': ['One link.', 'Every platform you post to.'],
}
PILLARS = {
    'AdoptDontShop': ['Know-how', 'Rescues', 'The build'],
    'ideaSquared': ['How we build', 'Updates', 'Notes'],
    'CreatrGrid': ['Why', 'How it works', 'Updates'],
}
CSS = {'AdoptDontShop': R.ADS_CSS, 'ideaSquared': R.ISQ_CSS, 'CreatrGrid': R.CG_CSS}

# Banners: native size, design scale k (design px = native / k), the safe
# rectangle (native px) that stays clear of profile pictures and mobile crops,
# and the block metrics (mark size, wordmark size, line size, gap) in design px.
BANNERS = {
    'linkedin_company_banner.png': dict(w=1128, h=191, k=1, safe=(190, 20, 1088, 171), align='left', s=56, fs=36, lfs=22, gap=14, rule=False, lw=800),
    'linkedin_company_banner@2x.png': dict(w=2256, h=382, k=2, safe=(190, 20, 1088, 171), align='left', s=56, fs=36, lfs=22, gap=14, rule=False, lw=800),
    'linkedin_personal_banner.png': dict(w=1584, h=396, k=1, safe=(360, 56, 1484, 340), align='left', s=92, fs=58, lfs=32, gap=26, rule=True, lw=760),
    'x_header.png': dict(w=1500, h=500, k=1, safe=(340, 90, 1400, 410), align='left', s=100, fs=62, lfs=38, gap=28, rule=True, lw=640),
    'facebook_cover.png': dict(w=1640, h=624, k=1, safe=(400, 100, 1240, 524), align='center', s=116, fs=74, lfs=42, gap=34, rule=True, lw=760),
}
BRAND_BANNERS = {
    'AdoptDontShop': ['facebook_cover.png'],
    'ideaSquared': ['linkedin_company_banner.png', 'linkedin_company_banner@2x.png', 'linkedin_personal_banner.png', 'facebook_cover.png'],
    'CreatrGrid': ['x_header.png'],
}
BRANDS = list(LINES)


def slug(t):
    return re.sub(r'[^a-z0-9]+', '-', t.lower()).strip('-')


def plan(brand):
    """List of (filename, width, height, kind, arg) for one brand. No rendering."""
    items = []
    for n in BRAND_BANNERS[brand]:
        items.append((n, BANNERS[n]['w'], BANNERS[n]['h'], 'banner', n))
    items.append(('avatar.png', 1080, 1080, 'avatar', None))
    items.append(('avatar_circle_preview.png', 1080, 1080, 'circle', None))
    for p in PILLARS[brand]:
        items.append((f'highlight_{slug(p)}.png', 1080, 1920, 'highlight', p))
    items.append(('link_preview.png', 1200, 630, 'link', None))
    return items


# ---------- pieces built from render.py helpers
def lockup(brand, s, fs):
    if brand == 'AdoptDontShop': return R.ads_lock(s, fs, '#FFFFFF', True)
    if brand == 'ideaSquared': return R.isq_lock(s, fs, '#f7f6f2', True)
    return R.cg_lock(s, fs, 'k')


def line_html(brand, fs, maxw, align='left'):
    ta = f'text-align:{align};'
    if brand == 'CreatrGrid':
        txt = '<br>'.join(R.esc(x) for x in LINES[brand])
        return f'<p style="font-weight:500;font-size:{fs}px;line-height:1.25;letter-spacing:-.01em;color:{R.MUT};{ta}">{txt}</p>'
    txt = R.esc(LINES[brand][0])
    if brand == 'AdoptDontShop':
        return f'<p class="d" style="font-weight:500;font-size:{fs}px;line-height:1.22;color:#FFFFFF;max-width:{maxw}px;text-wrap:balance;{ta}">{txt}</p>'
    return f'<p class="d" style="font-weight:400;font-variation-settings:\'WONK\' 0,\'opsz\' 36;font-size:{fs}px;line-height:1.22;letter-spacing:-.01em;color:#f7f6f2;max-width:{maxw}px;text-wrap:balance;{ta}">{txt}</p>'


def ghost(brand, size, left, top):
    if brand != 'AdoptDontShop': return ''   # ideaSquared stays calm: gradient only
    m, op, rot = R.ads_mark(size, '#FFFFFF', '#F43F5E'), .12, 12
    return f'<div style="position:absolute;left:{left}px;top:{top}px;opacity:{op};transform:rotate({rot}deg)">{m}</div>'


def glow(x, y, w, h, a=.22):
    return f'<div style="position:absolute;left:{x}px;top:{y}px;width:{w}px;height:{h}px;background:radial-gradient(ellipse at 50% 50%,rgba(124,58,237,{a}),rgba(236,72,153,{a*.4}) 45%,rgba(248,250,252,0) 70%)"></div>'


def flat_bg(brand):
    if brand == 'AdoptDontShop': return f'<div style="position:absolute;inset:0;background:{R.GRAD}"></div>'
    if brand == 'ideaSquared': return f'<div style="position:absolute;inset:0;background:{R.HERO}"></div>'
    return R.cg_bg()


def rule(brand):
    return '<div style="width:72px;height:5px;border-radius:999px;background:#e8911a;flex:none"></div>' if brand == 'ideaSquared' else ''


def banner_page(brand, spec):
    k, dw, dh = spec['k'], spec['w'] // spec['k'], spec['h'] // spec['k']
    x0, y0, x1, y1 = spec['safe']
    ctr = spec['align'] == 'center'
    inner = flat_bg(brand)
    if brand == 'CreatrGrid':
        ts = .75
        inner += glow(int(dw * .55), -int(dh * .3), int(dw * .5), int(dh * 1.3), .20)
        inner += f'<div style="position:absolute;left:0;top:0;width:{int(dw/ts)}px;height:{int(dh/ts)}px;zoom:{ts}">{R.tiles(int(dw/ts), 0, int(dh/ts))}</div>'
    else:
        size = int(dh * 1.7)
        inner += ghost(brand, size, dw - int(size * .55), -int(size * .22))
    ai = 'center' if ctr else 'flex-start'
    inner += (f'<div style="position:absolute;left:{x0}px;top:{y0}px;width:{x1-x0}px;height:{y1-y0}px;display:flex;flex-direction:column;'
              f'justify-content:center;align-items:{ai};gap:{spec["gap"]}px">{lockup(brand, spec["s"], spec["fs"])}{rule(brand) if spec["rule"] else ""}'
              f'{line_html(brand, spec["lfs"], spec["lw"], "center" if ctr else "left")}</div>')
    body = f'<div style="position:absolute;left:0;top:0;width:{dw}px;height:{dh}px;zoom:{k}">{inner}</div>'
    return R.page_html(CSS[brand], body, spec['w'], spec['h'])


def avatar_page(brand):
    W = 1080
    if brand == 'AdoptDontShop':   # glyph centre ~ (50, 51) of 100
        S = 560; m = R.ads_mark(S, '#FFFFFF', '#F43F5E'); dx, dy = 0, -S * .01
    elif brand == 'ideaSquared':   # glyph centre ~ (36, 33) of 64
        S = 720; m = R.isq_mark(True, S); dx, dy = -S * 4 / 64, -S * 1 / 64
    else:
        S = 520; m = R.cg_mark(S, 'a'); dx, dy = 0, 0
    pos = f'<div style="position:absolute;left:{(W-S)/2+dx}px;top:{(W-S)/2+dy}px">{m}</div>'
    return R.page_html(CSS[brand], flat_bg(brand) + pos, W, W)


def highlight_page(brand, label):
    W, H = 1080, 1920
    if brand == 'AdoptDontShop':
        bg = R.ads_bg('rose', W, H); label = R.tc(label)
        st = 'font-family:Fredoka;font-weight:700;color:#fff;letter-spacing:-.01em'
    elif brand == 'ideaSquared':
        bg = flat_bg(brand)
        st = 'font-family:Fraunces,Georgia,serif;font-variation-settings:\'WONK\' 0,\'opsz\' 144;font-weight:500;color:#f7f6f2;letter-spacing:-.025em'
    else:
        bg = R.cg_bg() + glow(-100, 560, 1280, 800, .22)
        st = 'font-family:Inter;font-weight:700;color:#0f172a;letter-spacing:-.03em'
    txt = f'<div style="position:absolute;left:210px;top:0;width:660px;height:{H}px;display:flex;align-items:center;justify-content:center"><h1 style="{st};font-size:120px;line-height:1.08;text-align:center;text-wrap:balance">{R.esc(label)}</h1></div>'
    return R.page_html(CSS[brand], bg + txt, W, H)


def link_page(brand):
    W, H = 1200, 630
    if brand == 'CreatrGrid':
        ts = .62
        bg = R.cg_bg() + glow(520, -150, 760, 700, .20)
        bg += f'<div style="position:absolute;left:0;top:0;width:{int(W/ts)}px;height:{int(H/ts)}px;zoom:{ts}">{R.tiles(int(W/ts), 0, int(H/ts))}</div>'
        lw = 640
    else:
        bg = flat_bg(brand) + ghost(brand, 900, 800, -220)
        lw = 760
    content = (f'<div style="position:absolute;left:90px;top:70px;bottom:70px;width:{lw}px;display:flex;flex-direction:column;justify-content:center;gap:44px">'
               f'{lockup(brand, 104, 68)}{rule(brand)}{line_html(brand, 52 if brand != "CreatrGrid" else 46, lw)}</div>')
    return R.page_html(CSS[brand], bg + content, W, H)


def build_html(brand, kind, arg):
    if kind == 'banner': return banner_page(brand, BANNERS[arg])
    if kind == 'avatar': return avatar_page(brand)
    if kind == 'highlight': return highlight_page(brand, arg)
    return link_page(brand)


def circle_preview(src, dst):
    from PIL import Image, ImageDraw
    im = Image.open(src).convert('RGB'); n = im.size[0]; ss = 4
    mask = Image.new('L', (n * ss, n * ss), 0); ImageDraw.Draw(mask).ellipse((0, 0, n * ss - 1, n * ss - 1), fill=255)
    mask = mask.resize((n, n), Image.LANCZOS)
    out = Image.new('RGB', (n, n), '#d1d5db'); out.paste(im, (0, 0), mask); out.save(dst)


def render_brand(brand, out, workers=3):
    from PIL import Image
    kit = os.path.join(os.path.abspath(out), brand, 'brandkit'); os.makedirs(kit, exist_ok=True)
    items = plan(brand); jobs = []
    with tempfile.TemporaryDirectory() as tmp:
        for name, w, h, kind, arg in items:
            if kind == 'circle': continue
            hp = os.path.join(tmp, name[:-4] + '.html')
            open(hp, 'w', encoding='utf-8').write(build_html(brand, kind, arg))
            jobs.append((hp, os.path.join(kit, name), w, h))
        with ThreadPoolExecutor(workers) as ex: list(ex.map(R.shot, jobs))
    circle_preview(os.path.join(kit, 'avatar.png'), os.path.join(kit, 'avatar_circle_preview.png'))
    for name, w, h, kind, arg in items:
        got = Image.open(os.path.join(kit, name)).size
        if got != (w, h): raise SystemExit(f'{brand}/{name}: expected {(w, h)}, got {got}')
    return kit


def main():
    ap = argparse.ArgumentParser(description='Generate a static brand kit per brand.')
    ap.add_argument('--out', required=True); ap.add_argument('--brand', help='|'.join(BRANDS))
    a = ap.parse_args()
    names = BRANDS
    if a.brand:
        names = [b for b in BRANDS if b.lower() == a.brand.lower()]
        if not names: ap.error(f'unknown brand {a.brand!r}; choose from {", ".join(BRANDS)}')
    for b in names: print(b, '->', render_brand(b, a.out))


if __name__ == '__main__': main()
