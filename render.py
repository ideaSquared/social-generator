import sys, os, json, html, subprocess, shutil, re, pathlib
import music
from concurrent.futures import ThreadPoolExecutor
from lib import *
def ff(fam,fn,ws,style='normal'): return ''.join(f'@font-face{{font-family:"{fam}";src:url("../fonts/{fn}-{w}-{style}.woff2") format("woff2");font-weight:{w};font-style:{style}}}' for w in ws)
FONT=(ff('Inter Tight','inter-tight-latin',(400,500,600,700))+ff('Inter','inter-latin',(400,500,600))+ff('Fredoka','fredoka-latin',(500,600,700))
 +'@font-face{font-family:"Fraunces";src:url("../fonts/fraunces-latin-full-normal.woff2") format("woff2");font-weight:100 900;font-style:normal}@font-face{font-family:"Fraunces";src:url("../fonts/fraunces-latin-full-italic.woff2") format("woff2");font-weight:100 900;font-style:italic}')
BASE='*{box-sizing:border-box;margin:0;padding:0}html,body{margin:0}body{position:relative;overflow:hidden;-webkit-font-smoothing:antialiased;font-family:"Inter","Noto Color Emoji",sans-serif}h1,p{word-spacing:.04em}'
def esc(t):
    t=re.sub(r' (?=[^\w\s\u2018\u2019\u201c\u201d.,!?:;()\u2013-]+$)','\u00a0',t)
    return html.escape(t)
def S(h,card,story): return card if h<1500 else story  # vertical position: 1080x1350 card vs 1080x1920 story safe zone
def pick(t,table):
    n=len(t)
    L=max((len(x) for x in re.split(r'[\s\-\u2011/]+',t)),default=0); cap=int(850/(0.6*L)) if L>=10 else 999
    for lim,sz in table:
        if n<=lim: return min(sz,cap)
    return min(table[-1][1],cap)
# ---------- marks
def isq_mark(dark,size):
    stem='#ffffff' if dark else '#08182a'; sq='#e8911a' if dark else '#c4750c'
    return f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 64 64" width="{size}" height="{size}"><rect x="20" y="10" width="14" height="14" rx="2" fill="{stem}"/><rect x="20" y="28" width="14" height="28" rx="2" fill="{stem}"/><rect x="38" y="10" width="14" height="14" rx="2" fill="{sq}"/><text x="45" y="22" text-anchor="middle" font-family="Inter Tight" font-size="12" font-weight="900" fill="#08182a">2</text></svg>'
def ads_mark(size,c='#F43F5E',w='#FFFFFF'):
    return f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 100 100" width="{size}" height="{size}"><defs><filter id="ds" x="-20%" y="-15%" width="140%" height="135%"><feDropShadow dx="0" dy="2" stdDeviation="1.6" flood-color="#0F172A" flood-opacity="0.16"/></filter></defs><g filter="url(#ds)"><path d="M50 10 C 53 10, 55 11, 57 13 L 88 42 C 90 44, 91 46, 91 49 L 91 84 C 91 88, 87 92, 83 92 L 17 92 C 13 92, 9 88, 9 84 L 9 49 C 9 46, 10 44, 12 42 L 43 13 C 45 11, 47 10, 50 10 Z" fill="{c}"/><g fill="{w}"><ellipse cx="32" cy="62" rx="5.5" ry="7" transform="rotate(-18 32 62)"/><ellipse cx="43" cy="55" rx="5.5" ry="7.5" transform="rotate(-6 43 55)"/><ellipse cx="57" cy="55" rx="5.5" ry="7.5" transform="rotate(6 57 55)"/><ellipse cx="68" cy="62" rx="5.5" ry="7" transform="rotate(18 68 62)"/><path d="M50 67 C 40 67, 33 73, 33 80 C 33 86, 41 89, 50 89 C 59 89, 67 86, 67 80 C 67 73, 60 67, 50 67 Z"/></g></g></svg>'
# ---------- ideaSquared templates
HERO='radial-gradient(ellipse at 22% 18%,#1a3a5e 0%,#08182a 55%,#04121f 100%)'
def isq_lock(s,fs,col,dark): return f'<div style="display:flex;align-items:center;gap:{int(s*.28)}px">{isq_mark(dark,s)}<span style="font-family:\'Inter Tight\';font-weight:700;font-size:{fs}px;color:{col};letter-spacing:-.01em">ideaSquared</span></div>'
ISQ_CSS='.eb{font-family:"Inter Tight";font-weight:600;letter-spacing:.14em;text-transform:uppercase;display:inline-flex;align-items:center;gap:16px}.eb::before{content:"";width:36px;height:2px;background:currentColor}h1,p.d{font-family:"Fraunces",Georgia,serif;font-variation-settings:"WONK" 0,"opsz" 144}p.s{font-family:"Inter Tight",sans-serif}'
def isq_bg(dark,w,h): return f'<div style="position:absolute;inset:0;background:{HERO if dark else "#f7f6f2"}"></div>'+(f'<div style="position:absolute;left:{int(w*.52)}px;top:-60px;opacity:.07">{isq_mark(True,int(w*.85))}</div>' if dark else '')
def isq_gcover(t,sub,w,h):
    sz=pick(t,[(24,150),(40,128),(64,104),(100,86),(999,72)])
    return isq_bg(True,w,h)+f'<div class="eb" style="position:absolute;left:96px;top:{S(h,110,260)}px;color:#9aa1ab;font-size:26px">Studio notes</div><div style="position:absolute;left:96px;width:{w-300}px;top:{S(h,250,400)}px;bottom:{S(h,300,420)}px;display:flex;flex-direction:column;justify-content:center;gap:44px"><h1 style="font-weight:500;font-size:{sz}px;line-height:1.02;letter-spacing:-.025em;color:#f7f6f2;text-wrap:balance">{esc(t)}</h1><div style="width:120px;height:6px;border-radius:999px;background:#e8911a"></div>'+(f'<p class="s" style="font-size:42px;line-height:1.3;color:#c3c9d2">{esc(sub)}</p>' if sub else '')+f'</div><div style="position:absolute;left:96px;bottom:{S(h,96,300)}px">{isq_lock(64,34,"#f7f6f2",True)}</div><div style="position:absolute;right:96px;bottom:{S(h,108,312)}px;font-family:\'Inter Tight\';font-weight:500;font-size:26px;color:#9aa1ab">Swipe through.</div>'
def isq_gslide(i,n,head,body,w,h):
    hs=pick(head or '',[(14,200),(26,150),(44,112),(999,88)]) if head else 0
    bs=pick(body,[(90,56),(150,48),(220,42),(999,38)]) if head else pick(body,[(60,96),(110,80),(170,66),(999,54)])
    prog=''.join(f'<div style="flex:1;height:6px;border-radius:999px;background:{"#08182a" if j<=i else "#e2ddd1"}"></div>' for j in range(n))
    inner=(f'<h1 style="font-weight:500;font-size:{hs}px;line-height:1.02;letter-spacing:-.03em;color:#14130f;text-wrap:balance">{esc(head)}</h1><div style="width:120px;height:6px;border-radius:999px;background:#e8911a"></div>' if head else '<div style="width:120px;height:6px;border-radius:999px;background:#e8911a"></div>')
    bf='p s' if head else 'd'
    bst='font-weight:400;color:#2c2a25' if head else 'font-weight:500;color:#14130f;letter-spacing:-.02em'
    return isq_bg(False,w,h)+f'<div style="position:absolute;left:96px;right:96px;top:{S(h,96,250)}px;display:flex;justify-content:space-between;align-items:center"><span class="eb" style="color:#5b574c;font-size:24px">{(str(i+1)+" of "+str(n)) if n>1 else "Studio notes"}</span>{isq_mark(False,56)}</div><div style="position:absolute;left:96px;right:110px;top:{S(h,240,400)}px;bottom:{S(h,240,420)}px;display:flex;flex-direction:column;justify-content:center;gap:42px">{inner}<p class="{bf}" style="font-size:{bs}px;line-height:1.28;{bst};text-wrap:pretty">{esc(body)}</p></div><div style="position:absolute;left:96px;right:96px;bottom:{S(h,120,330)}px;display:flex;gap:12px">{prog}</div>'
def isq_end(text,w,h,ptop):
    return isq_bg(True,w,h)+f'<div style="position:absolute;left:96px;right:130px;top:{ptop}px;bottom:{ptop+140}px;display:flex;flex-direction:column;justify-content:center;gap:70px"><p class="d" style="font-style:italic;font-weight:400;font-size:{pick(text,[(30,112),(60,96),(110,80),(999,66)])}px;line-height:1.1;letter-spacing:-.01em;color:#f7f6f2;text-wrap:balance">{esc(text)}</p>{isq_lock(88,50,"#f7f6f2",True)}</div>'
def isq_vtitle(t,w,h):
    sz=pick(t,[(30,160),(50,134),(80,108),(120,90),(999,76)])
    return isq_bg(True,w,h)+f'<div class="eb" style="position:absolute;left:96px;top:300px;color:#9aa1ab;font-size:30px">ideaSquared</div><div style="position:absolute;left:96px;width:{w-260}px;top:420px;bottom:420px;display:flex;flex-direction:column;justify-content:center;gap:56px"><h1 style="font-weight:500;font-size:{sz}px;line-height:1.02;letter-spacing:-.025em;color:#f7f6f2;text-wrap:balance">{esc(t)}</h1><div style="width:120px;height:6px;border-radius:999px;background:#e8911a"></div></div>'
def isq_vbeat(i,n,t,w,h):
    sz=pick(t,[(30,120),(55,100),(90,84),(140,70),(999,60)])
    return isq_bg(False,w,h)+f'<div class="eb" style="position:absolute;left:96px;top:300px;color:#5b574c;font-size:30px">{i+1} of {n}</div><div style="position:absolute;left:88px;top:380px;font-family:Fraunces;font-weight:400;font-size:330px;line-height:1;letter-spacing:-.04em;color:#14130f;font-variation-settings:\'WONK\' 0,\'opsz\' 144;font-feature-settings:\'lnum\' 1">{i+1}</div><div style="position:absolute;left:96px;right:120px;top:760px;bottom:300px;display:flex;flex-direction:column;gap:48px"><div style="width:120px;height:6px;border-radius:999px;background:#e8911a;flex:none"></div><p class="d" style="font-weight:500;font-size:{sz}px;line-height:1.1;letter-spacing:-.02em;color:#14130f;text-wrap:balance">{esc(t)}</p></div>'
# ---------- ADS templates
GRAD='linear-gradient(135deg,#F43F5E 0%,#E11D48 100%)'
def ads_lock(s,fs,col,dark=False):
    m=ads_mark(s,'#FFFFFF','#F43F5E') if dark else ads_mark(s)
    return f'<div style="display:flex;align-items:center;gap:{int(s*.3)}px">{m}<span style="font-family:Fredoka;font-weight:600;font-size:{fs}px;color:{col};letter-spacing:-.01em">AdoptDontShop</span></div>'
ADS_CSS='h1,p.d{font-family:"Fredoka","Inter","Noto Color Emoji",sans-serif}p.s{font-family:"Inter","Noto Color Emoji",sans-serif}.pill{display:inline-flex;align-items:center;font-family:"Inter";font-weight:600;border-radius:999px}'
def tc(t): return titlecase(t) if (len(t)<=60 and not re.search(r'[.?!]$',t)) else t
def ads_bg(kind,w,h):
    if kind=='rose': return f'<div style="position:absolute;inset:0;background:{GRAD}"></div><div style="position:absolute;left:{int(w*.52)}px;top:-100px;opacity:.12;transform:rotate(12deg)">{ads_mark(int(w*.8),"#FFFFFF","#F43F5E")}</div>'
    return f'<div style="position:absolute;inset:0;background:{ {"light":"#f8fafc","blush":"#fff1f2"}[kind] }"></div>'
def badge(i,t,size):
    if re.match(r'^(no|never)\b',t,re.I): return f'<div style="width:{size}px;height:{size}px;border-radius:999px;background:#ffe4e6;display:flex;align-items:center;justify-content:center;font-size:{int(size*.55)}px;font-family:\'Noto Color Emoji\'">\U0001F6AB</div>'
    return f'<div style="width:{size}px;height:{size}px;border-radius:999px;background:#ffe4e6;display:flex;align-items:center;justify-content:center;font-family:Fredoka;font-weight:700;font-size:{int(size*.5)}px;color:#be123c">{i+1}</div>'
def ads_gcover(t,sub,w,h):
    t=tc(t); sz=pick(t,[(24,150),(40,128),(64,104),(100,86),(999,72)])
    return ads_bg('rose',w,h)+f'<div class="pill" style="position:absolute;left:96px;top:{S(h,104,260)}px;background:rgba(255,255,255,.18);color:#fff;font-size:28px;padding:14px 28px">From the build</div><div style="position:absolute;left:96px;width:{w-190}px;top:{S(h,250,400)}px;bottom:{S(h,300,420)}px;display:flex;flex-direction:column;justify-content:center;gap:44px"><h1 style="font-weight:700;font-size:{sz}px;line-height:1.04;letter-spacing:-.02em;color:#fff;text-wrap:balance">{esc(t)}</h1>'+(f'<p style="font-weight:500;font-size:42px;line-height:1.3;color:#fff">{esc(sub)}</p>' if sub else '')+f'</div><div style="position:absolute;left:96px;bottom:{S(h,90,300)}px;background:#fff;border-radius:18px;padding:10px 20px 10px 12px">{ads_lock(56,34,"#be123c")}</div><div style="position:absolute;right:96px;bottom:{S(h,108,312)}px;font-family:Inter;font-weight:600;font-size:28px;color:#fff">Swipe →</div>'
def ads_gslide(i,n,head,body,w,h):
    head=tc(head) if head else None
    hs=pick(head,[(16,150),(30,120),(48,96),(999,80)]) if head else 0
    bs=pick(body,[(90,48),(150,44),(220,40),(999,36)]) if head else pick(body,[(60,84),(110,70),(170,58),(999,48)])
    dots=''.join(f'<div style="width:{44 if j==i else 14}px;height:14px;border-radius:999px;background:{"#dc1a45" if j==i else "#cbd5e1"}"></div>' for j in range(n))
    hd=f'<h1 style="font-weight:700;font-size:{hs}px;line-height:1.04;letter-spacing:-.02em;color:#0f172a;text-wrap:balance">{esc(head)}</h1>' if head else ''
    bst='font-weight:400;color:#334155' if head else 'font-weight:600;color:#0f172a'
    bcls='s' if head else 'd'
    return ads_bg('light',w,h)+f'<div style="position:absolute;left:96px;right:96px;top:{S(h,96,250)}px;display:flex;justify-content:space-between;align-items:center"><span class="pill" style="background:#ffe4e6;color:#be123c;font-size:26px;padding:12px 26px">{(str(i+1)+" of "+str(n)) if n>1 else "From the build"}</span>{ads_mark(64)}</div><div style="position:absolute;left:96px;right:96px;top:{S(h,240,400)}px;bottom:{S(h,260,420)}px;background:#fff;border-radius:48px;box-shadow:0 20px 25px -5px rgba(0,0,0,.1),0 8px 10px -6px rgba(0,0,0,.1);padding:60px;display:flex;flex-direction:column;justify-content:center;gap:40px">{badge(i,(head or body),130)}{hd}<p class="{bcls}" style="font-size:{bs}px;line-height:1.3;{bst};text-wrap:pretty">{esc(body)}</p></div><div style="position:absolute;left:96px;right:96px;bottom:{S(h,110,330)}px;display:flex;justify-content:center;gap:12px">{dots}</div>'
def ads_end(text,w,h,ptop):
    return ads_bg('blush',w,h)+f'<div style="position:absolute;left:96px;right:110px;top:{ptop}px;bottom:{ptop+140}px;display:flex;flex-direction:column;justify-content:center;gap:70px"><h1 style="font-weight:700;font-size:{pick(text,[(30,130),(60,112),(110,90),(999,72)])}px;line-height:1.06;letter-spacing:-.02em;color:#0f172a;text-wrap:balance">{esc(text)}</h1>{ads_lock(96,56,"#be123c")}</div>'
def ads_vtitle(t,w,h):
    t=tc(t); sz=pick(t,[(30,170),(50,140),(80,112),(120,92),(999,76)])
    return ads_bg('rose',w,h)+f'<div class="pill" style="position:absolute;left:96px;top:300px;background:rgba(255,255,255,.18);color:#fff;font-size:32px;padding:16px 32px">AdoptDontShop</div><div style="position:absolute;left:96px;width:{w-190}px;top:420px;bottom:420px;display:flex;flex-direction:column;justify-content:center"><h1 style="font-weight:700;font-size:{sz}px;line-height:1.04;letter-spacing:-.02em;color:#fff;text-wrap:balance">{esc(t)}</h1></div>'
def ads_vbeat(i,n,t,w,h):
    sz=pick(t,[(30,128),(55,108),(90,90),(140,74),(999,62)])
    dots=''.join(f'<div style="width:{44 if j==i else 14}px;height:14px;border-radius:999px;background:{"#dc1a45" if j==i else "#cbd5e1"}"></div>' for j in range(n))
    return ads_bg('light',w,h)+f'<div class="pill" style="position:absolute;left:96px;top:300px;background:#ffe4e6;color:#be123c;font-size:32px;padding:14px 30px">{i+1} of {n}</div><div style="position:absolute;left:96px;right:110px;top:420px;bottom:420px;display:flex;flex-direction:column;justify-content:center;gap:70px">{badge(i,t,190)}<h1 style="font-weight:700;font-size:{sz}px;line-height:1.08;letter-spacing:-.02em;color:#0f172a;text-wrap:balance">{esc(t)}</h1></div><div style="position:absolute;left:96px;bottom:260px;display:flex;gap:12px">{dots}</div>'
T={'ideaSquared':dict(css=ISQ_CSS,gcover=isq_gcover,gslide=isq_gslide,gend=lambda t,w,h:isq_end(t,w,h,300 if h<1500 else 420),vtitle=isq_vtitle,vbeat=isq_vbeat,vend=lambda t,w,h:isq_end(t,w,h,420),cta='Follow the build.'),
   'AdoptDontShop':dict(css=ADS_CSS,gcover=ads_gcover,gslide=ads_gslide,gend=lambda t,w,h:ads_end(t,w,h,300 if h<1500 else 420),vtitle=ads_vtitle,vbeat=ads_vbeat,vend=lambda t,w,h:ads_end(t,w,h,420),cta='Follow the Build')}
def page_html(css,body,w,h): return f'<!doctype html><html lang="en-GB"><head><meta charset="utf-8"><style>{FONT}{BASE}{css}body{{width:{w}px;height:{h}px}}</style></head><body>{body}</body></html>'
CHROME=os.environ.get('CHROME') or shutil.which('google-chrome') or shutil.which('chromium') or shutil.which('chromium-browser') or next((p for v in ('PROGRAMFILES','PROGRAMFILES(X86)','LOCALAPPDATA') if v in os.environ for p in [os.path.join(os.environ[v],'Google','Chrome','Application','chrome.exe')] if os.path.exists(p)),'google-chrome')
def shot(job):
    hp,png,w,h=job
    for _try in range(4):
      subprocess.run([CHROME,'--headless=new','--no-sandbox','--disable-gpu','--hide-scrollbars','--force-device-scale-factor=1',f'--window-size={w},{h}','--virtual-time-budget=3000',f'--screenshot={png}',f'file://{hp}'],check=True,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,timeout=120)
      from PIL import Image
      im=Image.open(png).convert('RGB'); 
      if im.size==(w,h) and not (im.getpixel((w-3,h-3))==(255,255,255) and im.getpixel((3,h-3))!=(255,255,255)): break
def video_cmd(job):
    """The ffmpeg command for one video. job is (pngs, durs, mp4, track); track is a music file or None (silent)."""
    pngs,durs,mp4,track=job
    fade=.35; cmd=['ffmpeg','-y','-loglevel','error']
    for p,d in zip(pngs,durs): cmd+=['-loop','1','-t',f'{d+fade:.2f}','-framerate','30','-i',p]
    fc='';prev='[0:v]';off=0
    for i in range(1,len(pngs)):
        off+=durs[i-1]; fc+=f'{prev}[{i}:v]xfade=transition=fade:duration={fade}:offset={off:.2f}[v{i}];'; prev=f'[v{i}]'
    total=sum(durs)+fade; audio=[]
    if track: cmd+=music.input_args(track); fc+=music.audio_filter(len(pngs),total); audio=music.output_args(total)
    cmd+=['-filter_complex',fc.rstrip(';'),'-map',prev,'-c:v','libx264','-preset','veryfast','-crf','20','-pix_fmt','yuv420p','-r','30']+audio+['-movflags','+faststart',mp4]
    return cmd
def video(job): subprocess.run(video_cmd(job),check=True)
# ---------- CreatrGrid templates (tokens from the design system)
BG,SUR,BOR,TX,MUT,PRI,ACC,DEEP='#f8fafc','#ffffff','#e2e8f0','#0f172a','#64748b','#7c3aed','#ec4899','#6d28d9'
def cg_mark(s,uid='g'):
    return f'<svg xmlns="http://www.w3.org/2000/svg" width="{s}" height="{s}" viewBox="0 0 64 64"><defs><linearGradient id="{uid}" x1="0" y1="0" x2="64" y2="64" gradientUnits="userSpaceOnUse"><stop offset="0" stop-color="#7C3AED"></stop><stop offset="1" stop-color="#EC4899"></stop></linearGradient></defs><mask id="{uid}m"><rect width="64" height="64" fill="#fff"></rect><path d="M11 13.5v13a1.2 1.2 0 0 0 1.8 1l10.4-6.5a1.2 1.2 0 0 0 0-2l-10.4-6.5a1.2 1.2 0 0 0-1.8 1Z" fill="#000"></path></mask><g fill="url(#{uid})" mask="url(#{uid}m)"><rect x="0" y="0" width="30" height="40" rx="7"></rect><rect x="0" y="44" width="30" height="20" rx="7"></rect><rect x="34" y="0" width="30" height="22" rx="7"></rect><rect x="34" y="26" width="30" height="38" rx="7"></rect></g></svg>'
def cg_lock(s,fs,uid='l'): return f'<div style="display:flex;align-items:center;gap:{int(s*.32)}px">{cg_mark(s,uid)}<span style="font-weight:700;font-size:{fs}px;letter-spacing:-.02em;color:{TX}">CreatrGrid</span></div>'
CG_CSS='body{font-family:"Inter",system-ui,sans-serif}h1{font-family:"Inter";font-weight:700;letter-spacing:-.02em;line-height:1.12;color:#0f172a}.cap{font-weight:600;letter-spacing:.06em;text-transform:uppercase;color:#64748b}'
def tiles(w,top,hh):
    # masonry tiles at platform ratios, bleeding off the top and right edges
    cw,gp=232,24; x0=w-3*cw-2*gp+70
    spec=[(0,-60,412,PRI),(0,376,130,BOR),(1,-150,232,ACC),(1,106,130,TX),(1,260,412,PRI),(2,-20,232,DEEP),(2,236,412,ACC)]
    r=''.join(f'<rect x="{x0+c*(cw+gp)}" y="{y}" width="{cw}" height="{hgt}" rx="28" fill="{col}"/>' for c,y,hgt,col in spec)
    return f'<svg style="position:absolute;left:0;top:{top}px" width="{w}" height="{hh}" viewBox="0 0 {w} {hh}">{r}</svg>'
def cg_bg(): return f'<div style="position:absolute;inset:0;background:{BG}"></div>'
def cg_gcover(t,sub,w,h):
    sz=pick(t,[(24,128),(40,108),(64,90),(999,74)])
    return cg_bg()+tiles(w,0,470)+f'<div style="position:absolute;left:96px;right:96px;top:520px;bottom:{S(h,250,420)}px;display:flex;flex-direction:column;justify-content:center;gap:36px"><div class="cap" style="font-size:26px">@@PILLAR@@</div><h1 style="font-size:{sz}px;text-wrap:balance">{esc(t)}</h1>'+(f'<p style="font-size:42px;line-height:1.4;color:{MUT}">{esc(sub)}</p>' if sub else '')+f'</div><div style="position:absolute;left:96px;bottom:{S(h,100,300)}px">{cg_lock(64,44)}</div><div style="position:absolute;right:96px;bottom:{S(h,114,314)}px;font-weight:600;font-size:28px;color:{PRI}">Swipe</div>'
def dots(i,n): return ''.join(f'<div style="width:{44 if j==i else 14}px;height:14px;border-radius:999px;background:{PRI if j==i else "#cbd5e1"}"></div>' for j in range(n))
def cg_gslide(i,n,head,body,w,h):
    hs=pick(head,[(16,116),(30,96),(48,80),(999,68)]); bs=pick(body,[(60,54),(110,48),(170,44),(999,40)])
    return cg_bg()+f'<div style="position:absolute;left:96px;right:96px;top:{S(h,96,250)}px;display:flex;justify-content:space-between;align-items:center"><span class="cap" style="font-size:26px">{i+1} of {n}</span>{cg_mark(60,"s")}</div><div style="position:absolute;left:96px;right:96px;top:{S(h,230,400)}px;bottom:{S(h,250,420)}px;background:{SUR};border:2px solid {BOR};border-radius:28px;box-shadow:0 8px 28px rgba(15,23,42,.10);padding:64px;display:flex;flex-direction:column;justify-content:center;gap:36px"><div style="width:96px;height:10px;border-radius:999px;background:linear-gradient(135deg,#7C3AED,#EC4899)"></div><h1 style="font-size:{hs}px;text-wrap:balance">{esc(head)}</h1><p style="font-size:{bs}px;line-height:1.45;color:{MUT};text-wrap:pretty">{esc(body)}</p></div><div style="position:absolute;left:96px;right:96px;bottom:{S(h,120,330)}px;display:flex;justify-content:center;gap:12px">{dots(i,n)}</div>'
def cg_end(text,w,h,ptop):
    text=text.replace(' creatrgrid.com','').strip()
    glow=f'<div style="position:absolute;left:-10%;right:-10%;top:-20%;height:70%;background:radial-gradient(ellipse at 50% 0%,rgba(124,58,237,.28),rgba(236,72,153,.10) 45%,rgba(248,250,252,0) 70%)"></div>'
    return cg_bg()+glow+f'<div style="position:absolute;left:96px;right:96px;top:{ptop}px;bottom:{ptop+120}px;display:flex;flex-direction:column;justify-content:center;gap:56px"><h1 style="font-size:{pick(text,[(24,124),(50,104),(90,84),(999,70)])}px;text-wrap:balance">{esc(text)}</h1><div style="display:flex;align-items:center;gap:28px"><span style="background:{PRI};color:#fff;font-weight:600;font-size:38px;padding:22px 40px;border-radius:18px">Get started free</span><span style="font-weight:600;font-size:38px;color:{PRI}">creatrgrid.com</span></div><div style="margin-top:20px">{cg_lock(80,54,"e")}</div></div>'
def cg_vtitle(t,w,h):
    sz=pick(t,[(30,132),(50,112),(80,94),(120,80),(999,68)])
    return cg_bg()+tiles(w,0,470)+f'<div style="position:absolute;left:96px;right:110px;top:560px;bottom:520px;display:flex;flex-direction:column;justify-content:center;gap:44px"><div style="width:120px;height:12px;border-radius:999px;background:linear-gradient(135deg,#7C3AED,#EC4899)"></div><h1 style="font-size:{sz}px;text-wrap:balance">{esc(t)}</h1></div><div style="position:absolute;left:96px;bottom:300px">{cg_lock(64,44)}</div>'
def cg_vbeat(i,n,t,w,h):
    sz=pick(t,[(30,120),(55,100),(90,84),(140,70),(999,60)])
    return cg_bg()+f'<div class="cap" style="position:absolute;left:96px;top:300px;font-size:30px">{i+1} of {n}</div><div style="position:absolute;right:96px;top:286px">{cg_mark(64,"b")}</div><div style="position:absolute;left:96px;right:110px;top:420px;bottom:420px;display:flex;flex-direction:column;justify-content:center;gap:48px"><div style="font-weight:700;font-size:200px;line-height:.9;letter-spacing:-.04em;background:linear-gradient(135deg,#7C3AED,#EC4899);-webkit-background-clip:text;color:transparent;width:fit-content">{i+1}</div><h1 style="font-size:{sz}px;text-wrap:balance">{esc(t)}</h1></div><div style="position:absolute;left:96px;bottom:260px;display:flex;gap:12px">{dots(i,n)}</div>'
T['CreatrGrid']=dict(css=CG_CSS,gcover=cg_gcover,gslide=cg_gslide,gend=lambda t,w,h:cg_end(t,w,h,300 if h<1500 else 420),vtitle=cg_vtitle,vbeat=cg_vbeat,vend=lambda t,w,h:cg_end(t,w,h,420))

# ---------- single-image cards (Text / Stat / Quote), 1080x1350
def paras(t): return '<br><br>'.join(esc(p) for p in t.split('\n') if p.strip())
def fit_stat(stat,w,k,cap=360): return min(cap,int((w-192)/(k*max(len(stat),1))))
def isq_tcard(text,w,h):
    sz=pick(text,[(60,104),(120,84),(200,70),(280,60),(400,50),(999,42)])
    return isq_bg(False,w,h)+f'<div style="position:absolute;left:96px;right:96px;top:96px;display:flex;justify-content:space-between;align-items:center"><span class="eb" style="color:#5b574c;font-size:24px">Studio notes</span>{isq_mark(False,56)}</div><div style="position:absolute;left:96px;right:110px;top:220px;bottom:250px;display:flex;flex-direction:column;justify-content:center;gap:48px"><div style="width:120px;height:6px;border-radius:999px;background:#e8911a;flex:none"></div><p class="d" style="font-weight:500;font-size:{sz}px;line-height:1.16;letter-spacing:-.02em;color:#14130f;text-wrap:pretty">{paras(text)}</p></div><div style="position:absolute;left:96px;bottom:96px">{isq_lock(56,30,"#14130f",False)}</div>'
def isq_scard(stat,label,w,h):
    sz=fit_stat(stat,w,.58); ls=pick(label,[(50,58),(90,50),(150,44),(999,38)])
    return isq_bg(True,w,h)+f'<div class="eb" style="position:absolute;left:96px;top:110px;color:#9aa1ab;font-size:26px">Studio notes</div><div style="position:absolute;left:96px;right:96px;top:250px;bottom:300px;display:flex;flex-direction:column;justify-content:center;gap:44px"><div class="d" style="font-family:Fraunces;font-weight:400;font-size:{sz}px;line-height:1;letter-spacing:-.04em;color:#f7f6f2;font-variation-settings:\'WONK\' 0,\'opsz\' 144;font-feature-settings:\'lnum\' 1;white-space:nowrap">{esc(stat)}</div><div style="width:120px;height:6px;border-radius:999px;background:#e8911a"></div><p class="s" style="font-size:{ls}px;line-height:1.3;color:#c3c9d2;text-wrap:balance">{esc(label)}</p></div><div style="position:absolute;left:96px;bottom:96px">{isq_lock(64,34,"#f7f6f2",True)}</div>'
def isq_qcard(quote,by,w,h):
    sz=pick(quote,[(60,92),(110,78),(180,66),(280,56),(999,46)])
    return isq_bg(False,w,h)+f'<div style="position:absolute;left:88px;top:110px;font-family:Fraunces;font-weight:500;font-size:340px;line-height:1;color:#e8911a;font-variation-settings:\'WONK\' 0,\'opsz\' 144;height:200px;overflow:hidden">“</div><div style="position:absolute;left:96px;right:110px;top:330px;bottom:260px;display:flex;flex-direction:column;justify-content:center;gap:52px"><p class="d" style="font-style:italic;font-weight:400;font-size:{sz}px;line-height:1.16;letter-spacing:-.015em;color:#14130f;text-wrap:pretty">{paras(quote)}</p>'+(f'<div class="eb" style="color:#5b574c;font-size:26px">{esc(by)}</div>' if by else '')+f'</div><div style="position:absolute;left:96px;bottom:96px">{isq_lock(56,30,"#14130f",False)}</div>'
def ads_tcard(text,w,h):
    sz=pick(text,[(60,84),(120,68),(200,56),(280,48),(400,40),(999,34)])
    return ads_bg('light',w,h)+f'<div style="position:absolute;left:96px;right:96px;top:96px;display:flex;justify-content:space-between;align-items:center"><span class="pill" style="background:#ffe4e6;color:#be123c;font-size:26px;padding:12px 26px">From the build</span>{ads_mark(64)}</div><div style="position:absolute;left:96px;right:96px;top:220px;bottom:250px;background:#fff;border-radius:48px;box-shadow:0 20px 25px -5px rgba(0,0,0,.1),0 8px 10px -6px rgba(0,0,0,.1);padding:60px;display:flex;flex-direction:column;justify-content:center"><p class="d" style="font-weight:600;font-size:{sz}px;line-height:1.28;letter-spacing:-.01em;color:#0f172a;text-wrap:pretty">{paras(text)}</p></div><div style="position:absolute;left:96px;bottom:96px">{ads_lock(56,34,"#be123c")}</div>'
def ads_scard(stat,label,w,h):
    sz=fit_stat(stat,w,.62); ls=pick(label,[(50,56),(90,48),(150,42),(999,36)])
    return ads_bg('rose',w,h)+f'<div class="pill" style="position:absolute;left:96px;top:104px;background:rgba(255,255,255,.18);color:#fff;font-size:28px;padding:14px 28px">From the build</div><div style="position:absolute;left:96px;right:96px;top:250px;bottom:300px;display:flex;flex-direction:column;justify-content:center;gap:40px"><div style="font-family:Fredoka;font-weight:700;font-size:{sz}px;line-height:1;letter-spacing:-.02em;color:#fff;white-space:nowrap">{esc(stat)}</div><p style="font-family:Inter;font-weight:600;font-size:{ls}px;line-height:1.3;color:#fff;text-wrap:balance">{esc(label)}</p></div><div style="position:absolute;left:96px;bottom:96px;background:#fff;border-radius:18px;padding:10px 20px 10px 12px">{ads_lock(56,34,"#be123c")}</div>'
def ads_qcard(quote,by,w,h):
    sz=pick(quote,[(60,92),(110,76),(180,62),(280,52),(999,42)])
    return ads_bg('blush',w,h)+f'<div style="position:absolute;left:92px;top:96px;font-family:Fredoka;font-weight:700;font-size:340px;line-height:1;color:#F43F5E;height:210px;overflow:hidden">“</div><div style="position:absolute;left:96px;right:110px;top:320px;bottom:260px;display:flex;flex-direction:column;justify-content:center;gap:48px"><h1 style="font-weight:600;font-size:{sz}px;line-height:1.16;letter-spacing:-.01em;color:#0f172a;text-wrap:pretty">{paras(quote)}</h1>'+(f'<div><span class="pill" style="background:#ffe4e6;color:#be123c;font-size:30px;padding:14px 30px">{esc(by)}</span></div>' if by else '')+f'</div><div style="position:absolute;left:96px;bottom:96px">{ads_lock(56,34,"#be123c")}</div>'
def cg_tcard(text,w,h):
    sz=pick(text,[(60,84),(120,68),(200,58),(280,50),(400,42),(999,36)])
    return cg_bg()+f'<div style="position:absolute;left:96px;right:96px;top:96px;display:flex;justify-content:space-between;align-items:center"><span class="cap" style="font-size:26px">@@PILLAR@@</span>{cg_mark(60,"s")}</div><div style="position:absolute;left:96px;right:96px;top:220px;bottom:250px;background:{SUR};border:2px solid {BOR};border-radius:28px;box-shadow:0 8px 28px rgba(15,23,42,.10);padding:64px;display:flex;flex-direction:column;justify-content:center;gap:40px"><div style="width:96px;height:10px;border-radius:999px;background:linear-gradient(135deg,#7C3AED,#EC4899);flex:none"></div><p style="font-weight:600;font-size:{sz}px;line-height:1.3;letter-spacing:-.02em;color:{TX};text-wrap:pretty">{paras(text)}</p></div><div style="position:absolute;left:96px;bottom:96px">{cg_lock(56,38,"l")}</div>'
def cg_scard(stat,label,w,h):
    sz=fit_stat(stat,w,.62); ls=pick(label,[(50,54),(90,48),(150,42),(999,36)])
    return cg_bg()+tiles(w,0,470)+f'<div style="position:absolute;left:96px;right:96px;top:520px;bottom:250px;display:flex;flex-direction:column;justify-content:center;gap:32px"><div class="cap" style="font-size:26px">@@PILLAR@@</div><div style="font-weight:700;font-size:{sz}px;line-height:1.05;letter-spacing:-.04em;background:linear-gradient(135deg,#7C3AED,#EC4899);-webkit-background-clip:text;color:transparent;width:fit-content;white-space:nowrap;padding-bottom:.08em">{esc(stat)}</div><p style="font-weight:500;font-size:{ls}px;line-height:1.35;color:{MUT};text-wrap:balance">{esc(label)}</p></div><div style="position:absolute;left:96px;bottom:96px">{cg_lock(56,38,"l")}</div>'
def cg_qcard(quote,by,w,h):
    sz=pick(quote,[(60,92),(110,76),(180,64),(280,54),(999,44)])
    return cg_bg()+f'<div style="position:absolute;left:96px;top:90px;font-weight:700;font-size:340px;line-height:1;background:linear-gradient(135deg,#7C3AED,#EC4899);-webkit-background-clip:text;color:transparent;height:200px;overflow:hidden;width:fit-content">“</div><div style="position:absolute;left:96px;right:110px;top:320px;bottom:260px;display:flex;flex-direction:column;justify-content:center;gap:48px"><h1 style="font-weight:700;font-size:{sz}px;line-height:1.2;text-wrap:pretty">{paras(quote)}</h1>'+(f'<div class="cap" style="font-size:28px">{esc(by)}</div>' if by else '')+f'</div><div style="position:absolute;left:96px;bottom:96px">{cg_lock(56,38,"l")}</div>'
for _b,_f in (('ideaSquared',(isq_tcard,isq_scard,isq_qcard)),('AdoptDontShop',(ads_tcard,ads_scard,ads_qcard)),('CreatrGrid',(cg_tcard,cg_scard,cg_qcard))): T[_b].update(tcard=_f[0],scard=_f[1],qcard=_f[2])
CARD_FORMATS={'text card':'text','stat card':'stat','quote card':'quote'}

# ---------- sheet -> frames (no AI: the sheet is the only input)
import csv, argparse, html as _html
HERE=os.path.dirname(os.path.abspath(__file__))
FONT=(FONT+'@font-face{font-family:"Inter";src:url("../fonts/inter-latin-700-normal.woff2") format("woff2");font-weight:700;font-style:normal}').replace('../fonts/',pathlib.Path(HERE,'fonts').as_uri()+'/')
def parse(content,fmt=''):
    """Content cell format.
    Video:    Hook: ... / Beats: (one '- ' line each) / Close: ...
    Carousel: Sub: ... / Slides: (one 'N. Heading: body' line each) / End: ...
    Stat card:  Stat: ... / Label: ...        Quote card: Quote: ... / By: ...
    Text card (pass fmt='Text card'): the whole cell is the post text.
    Optional: 'Footnote on asset: ...'. Everything from 'Caption:' down is ignored."""
    body=content.split('\nCaption:')[0]; d=dict(beats=[],slides=[]); mode=None
    if CARD_FORMATS.get(fmt.strip().lower())=='text':
        lines=[]
        for ln in body.split('\n'):
            ln=ln.strip(); m=re.match(r'^Footnote on asset\s*:\s*(.*)$',ln)
            if m: d['footnote']=m.group(1).strip()
            elif ln or (lines and lines[-1]): lines.append(ln)
        d['text']='\n'.join(' '.join(p.split()) for p in '\n'.join(lines).strip().split('\n') if p.strip()); return d
    for ln in body.split('\n'):
        ln=ln.strip()
        if not ln: continue
        m=re.match(r'^(Hook|Close|Sub|End|Stat|Label|Quote|By|Footnote on asset)\s*:\s*(.*)$',ln)
        if m: d[m.group(1).split()[0].lower()]=m.group(2).strip(); mode=None; continue
        if re.match(r'^Beats\s*:',ln): mode='b'; continue
        if re.match(r'^Slides\s*:',ln): mode='s'; continue
        if mode=='b': d['beats'].append(re.sub(r'^[-•]\s*','',ln))
        elif mode=='s':
            ln=re.sub(r'^\d+[.)]\s*','',ln); i=ln.rfind(': ')
            d['slides'].append((ln[:i].strip(),ln[i+2:].strip()) if i>0 else (None,ln))
    return d
def frames(title,d,story=False):
    """Plan the frames for one asset: ([(template key, args)], width, height). story=True plans a carousel at 1080x1920."""
    if d.get('text'): return [('tcard',(d['text'],))],1080,1350
    if d.get('stat'): return [('scard',(d['stat'],d.get('label','')))],1080,1350
    if d.get('quote'): return [('qcard',(d['quote'],d.get('by','')))],1080,1350
    if d['beats']:
        n=len(d['beats']); return [('vtitle',(d['hook'],))]+[('vbeat',(i,n,x)) for i,x in enumerate(d['beats'])]+[('vend',(d.get('close') or 'Follow along.',))],1080,1920
    n=len(d['slides']); return [('gcover',(title,d.get('sub')))]+[('gslide',(i,n,hd,bd)) for i,(hd,bd) in enumerate(d['slides'])]+[('gend',(d.get('end') or 'Follow along.',))],1080,(1920 if story else 1350)
def foot_html(text,h,brand,bottom=None):
    st='background:#ffffff;color:#64748b;border:1px solid #e2e8f0' if brand=='CreatrGrid' else 'background:rgba(8,24,42,.82);color:#e8ecf1'
    return f'<div style="position:absolute;left:96px;right:96px;bottom:{bottom if bottom is not None else 12 if h<1500 else 150}px;z-index:9"><span style="display:inline-block;{st};font:500 {16 if h<1500 else 26}px/1.3 Inter,sans-serif;padding:7px 12px;border-radius:10px">{_html.escape(text)}</span></div>'
def main():
    ap=argparse.ArgumentParser(description='Render social carousels, text videos and single-image cards from the Social posts sheet (CSV export).')
    ap.add_argument('csv'); ap.add_argument('--out',default='out'); ap.add_argument('--only',default='',help='comma-separated Asset IDs'); ap.add_argument('--dry-run',action='store_true',help='parse the sheet and write manifest.json without rendering'); ap.add_argument('--new-only',action='store_true',help="skip rows whose 'Assets made' cell is filled"); ap.add_argument('--stories',action='store_true',help='also render every carousel slide at 1080x1920 into a stories/ subfolder')
    a=ap.parse_args(); only=set(x for x in a.only.split(',') if x); out=os.path.abspath(a.out); tmp=os.path.join(out,'.html'); os.makedirs(tmp,exist_ok=True)
    jobs=[];vids=[];man=[];covers=[]
    for r in csv.DictReader(open(a.csv,newline='',encoding='utf-8')):
        aid=(r.get('Asset ID') or '').strip(); brand=(r.get('Brand') or '').strip(); fmt=(r.get('Format') or ''); card=CARD_FORMATS.get(fmt.strip().lower())
        if brand not in T or not aid or aid=='Text only' or not (card or fmt.startswith('Text-on-screen') or fmt.startswith('Graphic')): continue
        if only and aid not in only: continue
        if a.new_only and (r.get('Assets made') or '').strip(): continue
        d=parse(r['Content'],fmt); title=typo(r['Title'].strip())
        if card and not d.get(card): print(f"skipping {aid}: {fmt} needs {'text' if card=='text' else card.capitalize()+':'} content"); continue
        fr,w,h=frames(title,d); t=T[brand]; vid=h>1500
        fr=[(fn,tuple((('\n'.join(typo(p) for p in x.split('\n')) if fn=='tcard' else typo(x)) if isinstance(x,str) else x) for x in args)) for fn,args in fr]
        dd=os.path.join(out,brand,f"{aid}_{slug(r['Title'])}")
        if not a.dry_run:
            shutil.rmtree(dd,ignore_errors=True); os.makedirs(os.path.join(dd,'frames') if vid else dd)
            if a.stories and fmt.startswith('Graphic'): os.makedirs(os.path.join(dd,'stories'))
        pngs=[];durs=[]; pillar=_html.escape((r.get('Pillar') or brand).strip())
        def build(fn,args,w,h,fb=None): return t[fn](*args,w,h).replace('@@PILLAR@@',pillar).replace('>From the build<','>'+pillar+'<').replace('>Studio notes<','>'+pillar+'<')+(foot_html(d['footnote'],h,brand,fb) if d.get('footnote') else '')
        for k,(fn,args) in enumerate(fr,1):
            body=build(fn,args,w,h)
            hp=os.path.join(tmp,f'{aid}_{k}.html'); open(hp,'w',encoding='utf-8').write(page_html(t['css'],body,w,h))
            png=os.path.join(dd,'frames','frame_%02d.png'%k) if vid else os.path.join(dd,'card.png') if card else os.path.join(dd,'slide_%02d.png'%k); jobs.append((hp,png,w,h)); pngs.append(png)
            if vid: durs.append(2.8 if fn=='vtitle' else 3.4 if fn=='vend' else max(2.4,min(5.2,1.4+len(args[-1].split())*.3)))
        extra={}
        if vid:
            track=music.track_for(brand) if music.wants_music(r) else None
            vids.append((pngs,durs,os.path.join(dd,'video.mp4'),track)); covers.append((pngs[0],os.path.join(dd,'cover.png'))); extra['cover']=True
            if track: extra['music']=os.path.basename(track)
        if card: extra['card']=True
        if a.stories and fmt.startswith('Graphic'):
            sf,sw,sh=frames(title,d,story=True); sf=[(fn,tuple(typo(x) if isinstance(x,str) else x for x in args)) for fn,args in sf]
            for k,(fn,args) in enumerate(sf,1):
                hp=os.path.join(tmp,f'{aid}_s{k}.html'); open(hp,'w',encoding='utf-8').write(page_html(t['css'],build(fn,args,sw,sh,230),sw,sh)); jobs.append((hp,os.path.join(dd,'stories','story_%02d.png'%k),sw,sh))
            extra['stories']=len(sf)
        man.append(dict(asset=aid,brand=brand,title=r['Title'],folder=os.path.relpath(dd,out),frames=len(fr),video=vid,text=[' / '.join(x for x in args if isinstance(x,str)) for fn,args in fr],footnote=d.get('footnote',''),**extra))
    if a.dry_run: jobs=[];vids=[];covers=[]
    with ThreadPoolExecutor(os.cpu_count() or 2) as ex: list(ex.map(shot,jobs))
    for src,dst in covers: shutil.copyfile(src,dst)
    with ThreadPoolExecutor(2) as ex: list(ex.map(video,vids))
    mp=os.path.join(out,'manifest.json')
    if (only or a.new_only) and os.path.exists(mp):
        keep=[m for m in json.load(open(mp,encoding='utf-8')) if m['asset'] not in {x['asset'] for x in man}]
        man=sorted(keep+man,key=lambda m:m['asset'])
    json.dump(man,open(mp,'w',encoding='utf-8'),indent=1,ensure_ascii=False)
    silent=sorted({m['brand'] for m in man if m.get('video') and not m.get('music') and not music.track_for(m['brand'])})
    if silent and vids: print('no music track for: '+', '.join(silent)+' (videos are silent; see docs/music.md)')
    print(f'{len(man)} assets, {len(jobs)} frames, {len(vids)} videos -> {out}')
if __name__=='__main__': main()
