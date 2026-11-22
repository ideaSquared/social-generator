import re, json, html
EMO=re.compile('[\U0001F000-\U0001FAFF☀-➿⬀-⯿️‍⃣←-⇿⌀-⏿]')
SMALL={'a','an','the','and','but','or','for','nor','on','at','to','by','in','of','up','as','vs','with','from'}
UK={'organization':'organisation','organizations':'organisations','color':'colour','colors':'colours','favorite':'favourite','favorites':'favourites','behavior':'behaviour','behaviors':'behaviours','center':'centre','license':'licence','prioritize':'prioritise','recognize':'recognise','customize':'customise','optimize':'optimise','analyze':'analyse','gray':'grey','realize':'realise','specialize':'specialise','minimize':'minimise','neighborhood':'neighbourhood','catalog':'catalogue'}
def uk(s):
    def r(m):
        w=m.group(0); l=w.lower()
        if l in UK:
            n=UK[l]; return n.capitalize() if w[0].isupper() else n
        return w
    return re.sub(r"[A-Za-z]+",r,s)
def typo(s):
    s=s.replace('\u2014',' \u2013 ').replace(' - ',' \u2013 ')
    s=re.sub(r"(?<=\w)'(?=\w)",'\u2019',s)
    s=re.sub(r'"([^"]+)"',lambda m:'\u201c'+m.group(1)+'\u201d',s)
    s=re.sub(r"(^|[\s(])'(?=\w)",lambda m:m.group(1)+'\u2018',s)
    s=s.replace("'",'\u2019')
    s=re.sub(r'\s+',' ',s).strip()
    s=re.sub(r'\s+([.,!?:;])',r'\1',s)
    if '\u2019' in s and '\u2018' not in s:
        m=re.match(r"^([A-Z][A-Za-z ]{2,30})\u2019 (?=[a-z])",s)
        if m: s='\u2018'+s
    return s
def clean(s,brand):
    s=re.sub(r'#\w+','',s)
    s=re.sub(r'[0-9]️?⃣','',s)
    if brand=='ideaSquared': s=EMO.sub('',s)
    else: s=s.replace('\U0001F43E','')  # blue paw clashes with rose; strip
    return uk(typo(s)).strip()
def titlecase(s):
    w=s.split(' '); out=[]
    for i,x in enumerate(w):
        core=re.sub(r'^\W+','',x)
        if x.isupper() and len(x)>1: out.append(x)
        elif core.lower() in SMALL and 0<i<len(w)-1: out.append(x.lower() if x.lower()==x or True else x)
        else: out.append(x[:1].upper()+x[1:] if x else x)
    return ' '.join(out)
BULLET=re.compile(r'^\s*(?:[-•—–*]|\d+[.)]|[0-9]️?⃣)\s*')
PREF=re.compile(r'^(?:text overlay|text on screen|on[- ]screen text|overlay|voiceover|vo|visual|text|beat \d+)\s*:\s*',re.I)
DIRECTION=re.compile(r'^(?:shot of|clip of|show |cut to|b-roll|camera|animation|quick montage|screen recording)',re.I)
def unq(s): return s.strip().strip('“”"\'').strip()
def paragraphs(content):
    c=content.replace('\r','')
    c=re.sub(r'^\s*Content\s*\n','',c)
    return [p.strip() for p in re.split(r'\n\s*\n',c) if p.strip()]
def parse_video(content,brand,title):
    hook=close=None; beats=[]
    lines=[l.strip() for l in content.replace('\r','').split('\n')]
    skipcap=False; mid=None
    for l in lines:
        if not l: skipcap=False; continue
        if re.match(r'^caption\s*:',l,re.I): skipcap=True; continue
        if skipcap: continue
        if re.match(r'^#\w+',l) and not re.sub(r'#\w+|\s','',l): continue
        m=re.match(r'^hook[^:]*:\s*(.*)$',l,re.I)
        if m: hook=unq(m.group(1)) or hook; continue
        m=re.match(r'^(?:close|cta|ending|outro)[^:]*:\s*(.*)$',l,re.I)
        if m: close=unq(m.group(1)); continue
        if re.match(r'^beats?\s*:?\s*$',l,re.I) or re.match(r'^(voiceover|script|visuals?)\s*:?\s*$',l,re.I): continue
        if BULLET.match(l):
            b=BULLET.sub('',l); b=PREF.sub('',b); b=unq(b)
            if b and not DIRECTION.match(b):
                if mid and mid[0]==len(beats): beats.append(mid[1]); mid=None
                beats.append(b)
            continue
        if hook is None: hook=unq(PREF.sub('',l))
        elif beats: mid=(len(beats),unq(PREF.sub('',l)))
        elif close is None: close=unq(PREF.sub('',l))
    if mid and not close: close=mid[1]
    hook=clean(hook or title,brand); beats=[clean(b,brand) for b in beats]; beats=[b for b in beats if b and not re.search(r'\d,\d{3}\+?\s*(waitlist|adopter|member|sign)',b,re.I)]
    close=clean(close,brand) if close else None
    if close and (len(close)<3 or close==hook): close=None
    return hook,beats[:7],close
def split_sentences(t):
    return [x.strip() for x in re.split(r'(?<=[.!?])\s+',t) if x.strip()]
def parse_graphic(content,brand,title):
    if re.search(r'Frame\s*1\s*[:\-\u2013]',content): content=re.sub(r'\s*Frame\s*\d+\s*[:\-\u2013]\s*','\n- ',content)
    paras=paragraphs(content)
    paras=[p for p in paras if re.sub(r'#\w+|\s','',p)]
    items=[]; prose=[]
    for p in paras:
        ls=[l for l in p.split('\n') if l.strip()]
        if all(BULLET.match(l) for l in ls) or (len(ls)>1 and sum(1 for l in ls if BULLET.match(l))>=len(ls)-1):
            for l in ls:
                if BULLET.match(l): items.append(clean(BULLET.sub('',l),brand))
        elif len(ls)==1 and BULLET.match(ls[0]): items.append(clean(BULLET.sub('',ls[0]),brand))
        else: prose.append(clean(' '.join(ls),brand))
    # numbered/emoji-list paragraphs written one per paragraph
    for p in list(paras):
        if re.match(r'^[0-9]️?⃣',p) or re.match(r'^[❌✅✔❎]',p):
            t=clean(re.sub(r'^[❌✅✔❎️\s]+','',re.sub(r'^[0-9]️?⃣\s*','',p)),brand)
            if t and t not in items: items.append(t)
    prose=[x for x in prose if x]
    prose=[p for p in prose if not any(p==i for i in items)]
    return prose,[i for i in items if i]
def split_hb(t):
    m=re.match(r'^(.{3,48}?)\s+(?:–|:)\s+(.+)$',t)
    if m: return m.group(1).strip(),m.group(2).strip()
    return None,t
FLAG=re.compile(r'(\d[\d,]*\+)|(\d+\s?%)|(£\s?\d)|(by 20\d\d)|(in \d+ (?:days|weeks|minutes|hours))|(Charity Commission)|(Companies House)|(waitlist)|(\d{2,}[\d,]*\s+(?:pets|adopters|rescues|users|creators|members|adoptions))',re.I)
def flags(text):
    return sorted({m.group(0) for m in FLAG.finditer(text)})
def slug(t): return re.sub(r'[^a-z0-9]+','-',t.lower()).strip('-')[:40]
