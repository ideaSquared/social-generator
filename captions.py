"""Captions per platform: shared by package.py, gallery.py and the claims check."""
import re

PLATFORMS = ('Instagram', 'Facebook', 'TikTok', 'LinkedIn', 'X')

# ---------------------------------------------------------------- per-platform caption rules
# hashtags: the most a caption keeps (the sheet lists them most important first).
# links: False where a link in a caption cannot be tapped, so it is swapped for LINK_NOTE.
RULES = {
    'Instagram': dict(hashtags=5, links=False),
    'TikTok': dict(hashtags=4, links=False),
    'Facebook': dict(hashtags=2, links=True),
    'LinkedIn': dict(hashtags=3, links=True),
    'X': dict(hashtags=2, links=True, limit=280),
}
LINK_NOTE = 'Link in bio.'
X_URL_LENGTH = 23           # X counts every link as 23 characters
# A full link with a scheme, or a bare domain with an optional path, query or fragment. A bare domain must end at a
# word boundary, so 'acme.company' is not read as 'acme.com' plus 'pany'.
_URL = re.compile(r'https?://[^\s<>]+|(?<![\w@./-])(?:[a-z0-9-]+\.)+(?:co\.uk|org\.uk|com|org|net|uk|io|app|dev)(?![\w-])(?:[/?#][^\s<>]*)?', re.I)


def find_urls(text):
    """[(start, end)] of each link, without trailing sentence punctuation."""
    spans = []
    for m in _URL.finditer(text):
        end = m.end()
        while end > m.start() and text[end - 1] in '.,;:!?)\'"':
            end -= 1
        if end > m.start():
            spans.append((m.start(), end))
    return spans


def replace_urls(text, repl):
    out, last = [], 0
    for a, b in find_urls(text):
        out.append(text[last:a]); out.append(repl); last = b
    return ''.join(out) + text[last:]


def has_url(text):
    return bool(find_urls(text))
TAG_RE = re.compile(r'#\w+')
BLOCK_RE = re.compile(r'(?m)^Caption(?: for (\w+))?:[ \t]*')
OVERRIDE_RE = re.compile(r'(?m)^Caption for (\w+):[ \t]*')


def captions_in(content, is_text_post):
    """{'': the general caption, 'Instagram': an override, ...} from a Content cell.

    A text post has no Caption: line, because the whole cell is the post: everything before the first
    `Caption for <Platform>:` block is the general text, and a plain `Caption:` line is just text."""
    content = (content or '').replace('\r\n', '\n').replace('\r', '\n')
    if is_text_post:
        parts = OVERRIDE_RE.split(content)
        found = {'': parts[0].strip()}
        for name, text in zip(parts[1::2], parts[2::2]):
            found[name.strip()] = text.strip()
        return found
    parts = BLOCK_RE.split(content)             # [script, name, text, name, text, ...]
    found = {}
    for name, text in zip(parts[1::2], parts[2::2]):
        found[(name or '').strip()] = text.strip()
    return found


def split_tags(caption):
    """(body, hashtags) where hashtags are the ones on trailing lines made only of hashtags."""
    lines = caption.rstrip().split('\n')
    tags = []
    while lines and lines[-1].strip() and all(t.startswith('#') for t in lines[-1].split()):
        tags = lines.pop().split() + tags
    return '\n'.join(lines).rstrip(), tags


def x_length(text):
    return len(replace_urls(text, 'x' * X_URL_LENGTH))


def caption_for(platform, captions):
    """The caption to paste on one platform. Returns (text, [warnings])."""
    notes = []
    override = next((v for k, v in captions.items() if k.lower() == platform.lower()), None)
    if override is not None:
        text = override                           # written for this platform: used as it is
    else:
        rule = RULES[platform]
        body, tags = split_tags(captions.get('', ''))
        if not rule['links'] and has_url(body):
            kept = []
            for line in body.split('\n'):
                if has_url(line) and not re.search(r'\w', replace_urls(line, '')):
                    continue                       # the line was only a link
                kept.append(re.sub(r'[ \t]{2,}', ' ', replace_urls(line, '')).rstrip() if has_url(line) else line)
            body = '\n'.join(kept).rstrip()
            if LINK_NOTE.lower() not in body.lower():
                body += '\n\n' + LINK_NOTE
        body = re.sub(r'\n{3,}', '\n\n', body)
        tags = tags[:rule['hashtags']]
        text = body + ('\n\n' + ' '.join(tags) if tags else '')
    limit = RULES[platform].get('limit')
    if limit and x_length(text) > limit:
        notes.append(f'{x_length(text)} characters, over the {limit} limit')
    return text.strip() + '\n', notes


