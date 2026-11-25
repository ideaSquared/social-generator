#!/usr/bin/env python3
"""Lint the public text of every row in the Social posts sheet (CSV export).

Usage:  python checks/claims_check.py <sheet.csv> [--strict]

Output, one line per finding:
    ROW <n> <AssetID or title>: <LEVEL> <rule>: <excerpt>
<n> is the row number as the sheet shows it (the header is row 1, so the first
post is row 2).  Exit code 1 if there is any ERROR; warnings fail only with
--strict.  Standard library only, deterministic, no network, no AI.

The maintainer's rule: publish a claim only with dated evidence, and label
targets as targets.  Every rule lives in the RULES section below.
"""
import argparse
import csv
import re
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import captions  # noqa: E402

# =====================================================================
# RULES: edit this section to change what the check enforces.
# =====================================================================

BRANDS = ('AdoptDontShop', 'ideaSquared', 'CreatrGrid')

# Phrases that previously carried unverified claims.  Matched case-insensitively
# as whole words.  A row may override one by putting `allow: <phrase>` in its
# "Check before posting" cell (several may be listed: `allow: waitlist, 10x`).
BANNED_PHRASES = [
    'waitlist', 'pilot rescue', 'pilot rescues', 'letters of intent',
    'most trusted', 'guaranteed for life', 'world-class', 'best-in-class', '10x',
]

# A parked venture.  Any mention is an error unless `allow: Pairflix` is in
# the Check cell.
PARKED_WORDS = ['Pairflix']

# Figures that look like a statistic or a claim.  Each is (name, regex).
# They are only an ERROR when the row has no "Footnote on asset:" line and an
# empty "Check before posting" cell (that cell is where the source is kept).
STAT_PATTERNS = [
    ('percentage',   r'\d+(?:\.\d+)?\s?%'),
    ('money',        r'[£$€]\s?\d(?:[\d,]*\d)?(?:\.\d+)?(?:\s?(?:k|m|bn)\b)?'),
    ('thousands',    r'(?<![\w.,])\d{1,3}(?:,\d{3})+(?![\w,])'),
    ('3+ digits',    r'(?<![\w.,£$€])\d{3,}(?![\w,])'),      # 4-digit years are skipped below
    ('multiplier',   r'(?<![\w.])\d+(?:\.\d+)?[x×](?!\w)'),
    ('abbreviated',  r'(?<![\w.])\d+(?:\.\d+)?(?:k|m|bn)(?!\w)'),
    ('year target',  r'\b(?:19|20)\d\d\s+(?:target|deadline|goal)\b'),
    ('year deadline', r'\b(?:by|before|until|ahead of)\s+(?:the\s+)?(?:end\s+of\s+)?(?:early\s+|late\s+|mid-?)?(?:Q[1-4]\s+)?(?:19|20)\d\d\b'),
]
YEAR_RANGE = (1900, 2100)       # a bare 4-digit number in this range is a year, not a figure

# Text that is stripped before the figure scan (so it cannot cause false positives).
STRIP_FOR_STATS = [
    r'https?://\S+',                                                 # URLs
    r'(?<![\w@])[\w-]+(?:\.[\w-]+)*\.(?:com|co\.uk|org\.uk|org|io|dev|app|net|uk)\b\S*',  # bare domains
    r'#\w+',                                                         # hashtags
    r'\b\d{1,2}\s?[:x]\s?\d{1,2}\b',                                 # aspect ratios 16:9, 9:16, 1:1
    r'\b\d+\s+of\s+\d+\b',                                           # "1 of 5"
    r'^\s*(?:[-•]\s*)?\d+[.)]\s+',                                   # list / slide numbering
]

# Limits for the warnings.
MAX_BEAT_WORDS = 14
MAX_HEADING_WORDS = 8
MAX_HASHTAGS = 6
X_LIMIT = 280
X_URL_LENGTH = 23               # X counts every URL as 23 characters

# Warn about emoji in these brands' rows.
NO_EMOJI_BRANDS = ('CreatrGrid',)   # ideaSquared and AdoptDontShop use emoji as part of their voice
EMOJI_RE = re.compile('[\U0001F000-\U0001FAFF\u2600-\u27BF\u2B50\u2B55\u231A\u231B\u23E9-\u23FA\uFE0F\u200D]')

# American spellings (outside URLs and hashtags).  British forms are not matched.
AMERICAN_SPELLINGS = [
    r'colors?', r'colored', r'coloring', r'organizations?', r'organizational', r'favorites?',
    r'behaviors?', r'behavioral', r'centers?', r'centered', r'analyze[sd]?', r'analyzing',
]

# Check-cell text that must not be forgotten (warning).  (regex, label)
UNRESOLVED_CHECK = [r'CONFLICT', r'(?i)NOT confirmed']

# =====================================================================
# End of rules.  Parsing and the checks follow.
# =====================================================================

KEYED = re.compile(r'^(Hook|Close|Sub|End|Footnote on asset|Stat|Label|Quote|By)\s*:\s*(.*)$')


def parse(content):
    """Same layout as render.py's parse(), but keeps empty values so they can be reported."""
    body = re.split(r'(?m)^Caption:', content, maxsplit=1)[0]
    caption = content[len(body):] if len(body) < len(content) else ''
    d = dict(beats=[], slides=[], keys={}, caption=caption, body=body)
    mode = None
    for ln in body.split('\n'):
        ln = ln.strip()
        if not ln:
            continue
        m = KEYED.match(ln)
        if m:
            d['keys'][m.group(1).split()[0].lower()] = m.group(2).strip()
            mode = None
            continue
        if re.match(r'^Beats\s*:', ln):
            mode = 'b'; d['has_beats'] = True; continue
        if re.match(r'^Slides\s*:', ln):
            mode = 's'; d['has_slides'] = True; continue
        if mode == 'b':
            d['beats'].append(re.sub(r'^[-•]\s*', '', ln))
        elif mode == 's':
            ln = re.sub(r'^\d+[.)]\s*', '', ln)
            i = ln.rfind(': ')
            if i > 0:
                d['slides'].append((ln[:i].strip(), ln[i + 2:].strip()))
            elif ln.endswith(':'):
                d['slides'].append((ln[:-1].strip(), ''))     # heading with no body
            else:
                d['slides'].append((None, ln))                # body-only slide
    return d


def kind_of(fmt):
    fmt = (fmt or '').strip()
    if fmt.startswith('Text-on-screen'):
        return 'video'
    if fmt.startswith('Graphic'):
        return 'carousel'
    if fmt.lower() in ('text card', 'stat card', 'quote card'):
        return fmt.lower().split()[0] + '-card'          # text-card, stat-card, quote-card
    return 'text'


def excerpt(text, start, end, pad=30):
    s = max(0, start - pad); e = min(len(text), end + pad)
    out = re.sub(r'\s+', ' ', text[s:e]).strip()
    return ('...' if s > 0 else '') + out + ('...' if e < len(text) else '')


def phrase_re(phrase):
    """Whole-word, case-insensitive; a trailing plural 's' is tolerated (waitlists)."""
    plural = '' if phrase.lower().endswith('s') else 's?'
    return re.compile(r'(?<!\w)' + re.escape(phrase).replace(r'\ ', r'\s+') + plural + r'(?!\w)', re.I)


def allowed(check, phrase):
    """True if the Check cell has `allow:` followed (on the same clause) by the phrase."""
    for m in re.finditer(r'(?i)allow:([^;\n]*)', check):
        if phrase_re(phrase).search(m.group(1)):
            return True
    return False


def scrub(text, patterns=STRIP_FOR_STATS):
    """Blank out ignorable text, keeping offsets so excerpts line up."""
    for p in patterns:
        text = re.sub(p, lambda m: ' ' * len(m.group(0)), text, flags=re.M | re.I)
    return text


def find_figures(text):
    """Return [(rule, start, end)] for figures that look like statistics or claims."""
    clean = scrub(text)
    found, taken = [], []
    for name, pat in STAT_PATTERNS:
        for m in re.finditer(pat, clean, re.I if name.startswith('year') else 0):
            if name == '3+ digits' and '.' not in m.group(0):
                n = int(m.group(0))
                if len(m.group(0)) == 4 and YEAR_RANGE[0] <= n <= YEAR_RANGE[1]:
                    continue
            if any(m.start() < e and s < m.end() for s, e in taken):
                continue                                   # already reported by an earlier pattern
            taken.append((m.start(), m.end()))
            found.append((name, m.start(), m.end()))
    return sorted(found, key=lambda f: f[1]), clean


def check_row(r, seen_ids):
    """Return a list of (level, rule, excerpt) for one row."""
    out = []
    err = lambda rule, ex: out.append(('ERROR', rule, ex))
    warn = lambda rule, ex: out.append(('WARNING', rule, ex))
    brand = (r.get('Brand') or '').strip()
    title = (r.get('Title') or '').strip()
    content = r.get('Content') or ''
    check = (r.get('Check before posting') or '').strip()
    platform = (r.get('Platform') or '').strip()
    aid = (r.get('Asset ID') or '').strip()
    kind = kind_of(r.get('Format'))
    d = parse(content)
    public = title + '\n' + content

    # --- structure
    if brand not in BRANDS:
        err('unknown-brand', repr(brand))
    if kind != 'text':
        if not aid or aid.lower() == 'text only':
            err('missing-asset-id', title)
        elif aid.lower() in seen_ids:
            err('duplicate-asset-id', aid)
        seen_ids.add(aid.lower())
    if kind == 'video':
        if not d['keys'].get('hook'):
            err('video-no-hook', title)
        if not d['beats']:
            err('video-no-beats', title)
        if not d['keys'].get('close'):
            err('video-no-close', title)
    if kind == 'carousel':
        if not d['slides']:
            err('carousel-no-slides', title)
        for i, (hd, bd) in enumerate(d['slides'], 1):
            if not bd:
                err('empty-slide-body', f'slide {i}: {hd}')
    if kind == 'text-card' and not d['body'].strip():
        err('card-no-text', title)
    if kind == 'stat-card':
        if not d['keys'].get('stat'):
            err('card-no-stat', title)
        if not d['keys'].get('label'):
            err('card-no-label', title)
    if kind == 'quote-card' and not d['keys'].get('quote'):
        err('card-no-quote', title)
    if platform.upper() in ('X', 'TWITTER', 'X (TWITTER)'):
        # Text posts are posted whole; asset rows post only their caption.
        # What X actually gets: its own `Caption for X:` block if there is one, else the general caption
        # after package.py's rules (hashtags trimmed).
        posted, _ = captions.caption_for('X', captions.captions_in(content, kind == 'text'))
        n = captions.x_length(posted.strip())
        if n > X_LIMIT:
            err('x-post-too-long', f'{n} characters (limit {X_LIMIT})')

    # --- banned phrases and parked venture
    reported = []
    for phrase in BANNED_PHRASES:
        m = phrase_re(phrase).search(public)
        if m and (m.start(), m.end()) not in reported and not allowed(check, phrase):
            reported.append((m.start(), m.end()))
            err('banned-phrase', f'"{phrase}" in: ' + excerpt(public, m.start(), m.end()))
    for word in PARKED_WORDS:
        m = phrase_re(word).search(public)
        if m and not allowed(check, word):
            err('parked-venture', excerpt(public, m.start(), m.end()))

    # --- unevidenced figures
    has_evidence = bool(d['keys'].get('footnote')) or bool(check)
    figures, clean = find_figures(public)
    if figures and not has_evidence:
        for name, s, e in figures:
            err('unevidenced-figure', f'{name} "{public[s:e]}" in: ' + excerpt(public, s, e))

    # --- warnings
    for b in d['beats']:
        if len(b.split()) > MAX_BEAT_WORDS:
            warn('long-beat', f'{len(b.split())} words: {b}')
    for hd, _ in d['slides']:
        if hd and len(hd.split()) > MAX_HEADING_WORDS:
            warn('long-slide-heading', f'{len(hd.split())} words: {hd}')
    cap = d['caption'] if kind != 'text' else content
    tags = re.findall(r'(?<![\w&])#\w+', cap)
    if len(tags) > MAX_HASHTAGS:
        warn('too-many-hashtags', f'{len(tags)} hashtags')
    if brand in NO_EMOJI_BRANDS:
        m = EMOJI_RE.search(public)
        if m:
            warn('emoji', excerpt(public, m.start(), m.end()))
    prose = scrub(public, STRIP_FOR_STATS[:3])
    am = re.compile(r'(?<![\w-])(' + '|'.join(AMERICAN_SPELLINGS) + r')(?![\w-])', re.I).search(prose)
    if am:
        warn('american-spelling', excerpt(prose, am.start(), am.end()))
    for pat in UNRESOLVED_CHECK:
        m = re.search(pat, check)
        if m:
            warn('unresolved-check', excerpt(check, m.start(), m.end(), 60))
    return out


def run(path, strict=False, stream=None):
    stream = stream or sys.stdout
    with open(path, newline='', encoding='utf-8') as f:
        rows = list(csv.DictReader(f))
    seen, errors, warnings = set(), 0, 0
    for n, r in enumerate(rows, 2):                        # row 1 is the header
        if not any((r.get(k) or '').strip() for k in ('Brand', 'Title', 'Content')):
            continue                                       # blank row (only formulas)
        label = (r.get('Asset ID') or '').strip()
        if not label or label.lower() == 'text only':
            label = (r.get('Title') or '').strip()
        findings = check_row(r, seen)
        findings.sort(key=lambda f: f[0] != 'ERROR')
        for level, rule, ex in findings:
            print(f'ROW {n} {label}: {level} {rule}: {ex}', file=stream)
            errors += level == 'ERROR'
            warnings += level == 'WARNING'
    print(f'{len(rows)} rows checked: {errors} error(s), {warnings} warning(s)', file=stream)
    return 1 if errors or (strict and warnings) else 0


def main(argv=None):
    ap = argparse.ArgumentParser(description='Lint the public text of the Social posts sheet.')
    ap.add_argument('csv')
    ap.add_argument('--strict', action='store_true', help='treat warnings as failures too')
    a = ap.parse_args(argv)
    return run(a.csv, a.strict)


if __name__ == '__main__':
    sys.exit(main())
