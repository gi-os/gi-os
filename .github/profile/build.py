#!/usr/bin/env python3
"""Builds the profile README and its images from content.json.

    python3 .github/profile/build.py

Writes README.md and images/*-light.svg + images/*-dark.svg at the repo root. The Sponsors and
Guestbook blocks in README.md are carried over untouched (GitHub Actions own them). If Node is
installed, the Sponsors block is then re-rendered from sponsors.json by .github/scripts/sponsors.js.
Standard library only.
"""
import json
import math
import re
import shutil
import subprocess
import textwrap
from html import escape
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent.parent
C = json.loads((HERE / 'content.json').read_text(encoding='utf-8'))
IMAGES = ROOT / 'images'
README = ROOT / 'README.md'

# ---------------------------------------------------------------- tokens
THEMES = {
    'light': dict(text='#1f2328', muted='#59636e', rule='#d1d9e0', accent='#c93c1e', on_accent='#ffffff'),
    # dark hairlines are a step brighter than GitHub's own border so they survive the dimmed theme (#212830)
    'dark': dict(text='#f0f6fc', muted='#9198a1', rule='#4f5762', accent='#ff7a59', on_accent='#0d1117'),
}
SERIF = '"Iowan Old Style", "Palatino Linotype", Palatino, Georgia, "Times New Roman", serif'
SANS = '-apple-system, BlinkMacSystemFont, "Segoe UI", "Noto Sans", Helvetica, Arial, sans-serif'
MONO = 'ui-monospace, SFMono-Regular, "SF Mono", Menlo, Consolas, "Liberation Mono", monospace'
W = 846       # full-width pieces: the README column on a desktop
CW = 420      # cards: two per row on a desktop (420 + a space + 420), one per row on a phone
INSET = 24    # right inset for text in a card, so side-by-side cards keep a gutter
WRAP = 35     # characters per line of card text
REDUCED = '@media (prefers-reduced-motion: reduce) { * { animation: none !important; } }'

# Blocks the Actions rewrite. Used only if README.md doesn't have them yet.
DEFAULT_BLOCKS = {
    'Sponsors': '<p>No sponsors yet.</p>\n',
    'Guestbook': '| Name | Date | Message |\n|---|---|---|\n| | | No entries yet. |\n',
}


# ---------------------------------------------------------------- svg helpers
def svg(w, h, label, body, extra_css=''):
    return (f'<svg xmlns="http://www.w3.org/2000/svg" width="{w}" height="{h}" viewBox="0 0 {w} {h}" '
            f'role="img" aria-label="{escape(label, quote=True)}">\n'
            f'<style>{extra_css}{REDUCED}</style>\n{body}\n</svg>\n')


def text(x, y, s, size, fill, family=SANS, weight=400, anchor='start', italic=False, ls=None):
    extra = ' font-style="italic"' if italic else ''
    extra += f' letter-spacing="{ls}"' if ls is not None else ''
    return (f'<text x="{x}" y="{y}" font-family=\'{family}\' font-size="{size}" font-weight="{weight}" '
            f'text-anchor="{anchor}" fill="{fill}"{extra}>{escape(s)}</text>')


def rule(x1, x2, y, color, sw=1):
    return f'<line x1="{x1}" y1="{y}" x2="{x2}" y2="{y}" stroke="{color}" stroke-width="{sw}"/>'


def arrow(x, y, col, w=2.2, s=1):
    return (f'<path d="M{x} {y}H{x + 26 * s}M{x + 17 * s} {y - 9 * s}L{x + 26 * s} {y}L{x + 17 * s} {y + 9 * s}" '
            f'fill="none" stroke="{col}" stroke-width="{w}" stroke-linecap="round" stroke-linejoin="round"/>')


# ---------------------------------------------------------------- glyphs (36x36, one stroke weight)
# Horizontal ink extent of each glyph, so glyphs line up on their drawn right edge, not their box.
INK = {'camera': (3, 33), 'ticket': (3, 33), 'cassette': (3, 33), 'book': (8, 28), 'pause': (4, 32),
       'blocks': (4, 32), 'notebook': (5, 33), 'storefront': (3, 33), 'rocket': (8.5, 27.5), 'bag': (4, 32),
       'film': (4, 32), 'wheel': (4, 32), 'keyboard': (3, 33), 'envelope': (3, 33), 'window': (3, 33),
       'chip': (3.5, 32.5), 'bell': (3, 33), 'arrow': (5, 31)}
GLYPH_SCALE = 1.22


def glyph(name, col):
    f = f'fill="{col}"'
    if name == 'blocks':
        lit = {(0, 0), (1, 0), (1, 1), (2, 2)}
        body = ''.join(f'<rect x="{4 + i * 10}" y="{4 + j * 10}" width="8" height="8" rx="1.2" {f if (i, j) in lit else ""}/>'
                       for i in range(3) for j in range(3))
    elif name == 'wheel':
        ticks = ''.join(f'<path d="M{18 + 11 * math.cos(math.radians(a)):.2f} {18 + 11 * math.sin(math.radians(a)):.2f}'
                        f'L{18 + 14 * math.cos(math.radians(a)):.2f} {18 + 14 * math.sin(math.radians(a)):.2f}"/>'
                        for a in range(0, 360, 45))
        body = f'<circle cx="18" cy="18" r="10"/><circle cx="18" cy="18" r="3"/>{ticks}'
    elif name == 'keyboard':
        keys = ''.join(f'<rect x="{6.5 + i * 5.2}" y="{y}" width="3" height="3" rx="0.6" {f}/>' for y in (13, 18) for i in range(5))
        body = f'<rect x="3" y="8" width="30" height="20" rx="2.5"/>{keys}<rect x="11" y="22.5" width="14" height="2.2" rx="1" {f}/>'
    elif name == 'chip':
        pins = ''.join(f'<path d="M{p} 3.5V9M{p} 27V32.5M3.5 {p}H9M27 {p}H32.5"/>' for p in (13.5, 18, 22.5))
        body = f'<rect x="9" y="9" width="18" height="18" rx="2"/><rect x="14" y="14" width="8" height="8"/>{pins}'
    else:
        body = {
            'camera': f'<rect x="3" y="10" width="30" height="19" rx="3"/><circle cx="18" cy="19.5" r="5.5"/><rect x="6" y="6" width="7" height="4"/><circle cx="27.5" cy="15" r="1" {f}/>',
            'ticket': '<path d="M3 9H33V15A3 3 0 0 0 33 21V27H3V21A3 3 0 0 0 3 15Z"/><path d="M24 11V25" stroke-dasharray="2 2.6"/>',
            'cassette': '<rect x="3" y="8" width="30" height="20" rx="2.5"/><circle cx="12" cy="17" r="3.5"/><circle cx="24" cy="17" r="3.5"/><path d="M10 28L12.5 23H23.5L26 28"/>',
            'book': '<rect x="8" y="3" width="20" height="26" rx="1.5"/><path d="M12.5 3V29"/><path d="M22 29V34L24 32.2L26 34V29"/>',
            'pause': '<circle cx="18" cy="18" r="14"/><path d="M14.5 12V24M21.5 12V24" stroke-width="2.6"/>',
            'notebook': '<rect x="5" y="3" width="19" height="29" rx="2"/><path d="M9.5 11H19.5M9.5 16H17M9.5 21H15"/><path d="M31 6L23 27L22 31L26 28.5L33 8Z"/>',
            'storefront': '<path d="M3 13L7 5H29L33 13Z"/><path d="M3 13Q7.7 19 12.3 13Q17 19 21.7 13Q26.3 19 31 13"/><path d="M6 18V31H30V18"/><rect x="15" y="22" width="6" height="9"/>',
            'rocket': '<path d="M18 3C25 9 25 19 22.5 26H13.5C11 19 11 9 18 3Z"/><circle cx="18" cy="13" r="2.6"/><path d="M13.5 21L8.5 27L13.5 26M22.5 21L27.5 27L22.5 26M16 29L18 34L20 29"/>',
            'bag': '<path d="M6 12H30L32 32H4Z"/><path d="M12.5 12V9A5.5 5.5 0 0 1 23.5 9V12"/>',
            # 35mm canister with the film leader pulled out
            'film': '<rect x="4" y="9" width="15" height="22" rx="2.5"/><path d="M9 9V6H14V9"/><path d="M19 14H32V26H19"/><path d="M22 17H30M22 23H30" stroke-dasharray="1.6 2.4"/>',
            'envelope': '<rect x="3" y="7" width="30" height="22" rx="2.5"/><path d="M3.5 9L18 20L32.5 9"/>',
            'window': f'<rect x="3" y="5" width="30" height="26" rx="3"/><path d="M3 12H33"/><circle cx="7.5" cy="8.5" r="1" {f}/><circle cx="11.5" cy="8.5" r="1" {f}/><circle cx="15.5" cy="8.5" r="1" {f}/>',
            'bell': '<path d="M5 25A13 13 0 0 1 31 25Z"/><path d="M18 12V8M15 8H21"/><rect x="3" y="27.5" width="30" height="3.5" rx="1.7"/>',
            'arrow': '<path d="M5 18H31M22 9L31 18L22 27"/>',
        }[name]
    return (f'<g fill="none" stroke="{col}" stroke-width="1.8" stroke-linecap="round" '
            f'stroke-linejoin="round">{body}</g>')


# ---------------------------------------------------------------- cards
def lines_of(item):
    """Wrap card text, avoiding a last line that is one short word."""
    s = item.get('line', '')
    lines = textwrap.wrap(s, WRAP, break_long_words=False)
    for width in range(WRAP - 1, WRAP - 9, -1):
        if len(lines) < 2 or ' ' in lines[-1] or len(lines[-1]) > 8:
            break
        lines = textwrap.wrap(s, width, break_long_words=False)
    return lines


def card_height(item):
    n = len(lines_of(item))
    return 146 + 27 * (n - 1) + 32 if n else 128


def card(item, number, H, t):
    k = THEMES[t]
    x1 = CW - INSET
    more = item.get('kind') == 'more'
    b = [rule(0, CW, 1, k['text'], 2),
         text(0, 38, 'More' if more else number, 18, k['accent'], MONO, 700)]
    if item.get('tag'):
        b.append(text(x1, 38, item['tag'], 17, k['muted'], MONO, 400, 'end'))
    b.append(text(0, 104, item['name'], 40, k['text'], SERIF, 400, ls=-0.5))
    name = 'arrow' if more else item['glyph']
    gx = x1 - GLYPH_SCALE * (INK[name][1] + 0.9)    # 0.9 = half the stroke width
    b.append(f'<g transform="translate({gx:.1f} 66) scale({GLYPH_SCALE})">'
             f'{glyph(name, k["accent"] if more else k["text"])}</g>')
    for i, ln in enumerate(lines_of(item)):
        b.append(text(0, 146 + 27 * i, ln, 19, k['text'], SANS))
    if more:
        label = item['name']
    else:
        label = f'{number} {item["name"]}. {item["line"]}' + (f' {item["tag"]}.' if item.get('tag') else '')
    return svg(CW, H, label, '\n'.join(b)), label


def slug(s):
    return re.sub(r'[^a-z0-9]+', '-', s.lower()).strip('-')


def picture(name, w, alt, top=False):
    # align="top" lets side-by-side cards keep their own heights and still line up at the top
    align = ' align="top"' if top else ''
    return (f'<picture><source media="(prefers-color-scheme: dark)" srcset="images/{name}-dark.svg">'
            f'<img src="images/{name}-light.svg" width="{w}"{align} alt="{escape(alt, quote=True)}"></picture>')


def write_pair(name, fn, *args):
    label = None
    for t in THEMES:
        out = fn(*args, t)
        s, label = out if isinstance(out, tuple) else (out, label)
        (IMAGES / f'{name}-{t}.svg').write_text(s, encoding='utf-8')
    return label


def cards(num, items):
    """Write one SVG pair per card; return the HTML paragraph that lays them out."""
    html, n = [], 0
    for it in items:
        if it.get('kind') != 'more':
            n += 1
        name = f'card-{slug(it["name"])}'
        label = write_pair(name, card, it, f'{num}.{n}', card_height(it))
        pic = picture(name, CW, label, top=True)
        html.append(f'<a href="{escape(it["url"], quote=True)}">{pic}</a>' if it.get('url') else pic)
    return '<p>\n' + '\n'.join(html) + '\n</p>'


# ---------------------------------------------------------------- masthead, section heads, word list, buttons
def masthead(t):
    k = THEMES[t]
    P = C['person']
    first, last = P['name'].split(' ', 1)
    count = sum(1 for s in C['sections'] for it in s['items'] if it.get('kind') != 'more')
    b = [rule(0, W, 1, k['text'], 2),
         text(0, 165, first, 156, k['text'], SERIF, 400, ls=-3),
         f'<text x="0" y="309" font-family=\'{SERIF}\' font-size="156" fill="{k["text"]}" letter-spacing="-3">'
         f'{escape(last)}<tspan fill="{k["accent"]}">.</tspan></text>',
         # right-aligned text sits INSET in from the edge, like the tags on the cards below
         text(W - INSET, 232, 'Index of work', 38, k['accent'], MONO, 700, 'end'),
         # hand-drawn underline that draws itself once
         f'<path class="u" pathLength="1" d="M{W - INSET - 296} 250C{W - INSET - 240} 245 {W - INSET - 180} 254 '
         f'{W - INSET - 120} 248S{W - INSET - 30} 251 {W - INSET} 247" fill="none" '
         f'stroke="{k["accent"]}" stroke-width="4" stroke-linecap="round"/>',
         text(W - INSET, 288, f'{count} projects', 38, k['text'], MONO, 400, 'end'),
         text(W - INSET, 330, f'{P["since"]} to now', 38, k['muted'], MONO, 400, 'end'),
         rule(0, W, 368, k['rule'], 1)]
    for i, ln in enumerate(P['standfirst']):
        # 39px keeps the longest line about 24px inside the edge even in Georgia (Android, some Windows setups)
        b.append(text(0, 428 + 50 * i, ln, 39, k['text'], SERIF, 400, italic=True))
    css = '.u{stroke-dasharray:1;animation:draw 1.3s ease-out .5s both}@keyframes draw{from{stroke-dashoffset:1}to{stroke-dashoffset:0}}'
    label = f'{P["name"]}. Index of work, {count} projects, {P["since"]} to now. {" ".join(P["standfirst"])}'
    return svg(W, 428 + 50 * (len(P['standfirst']) - 1) + 24, label, '\n'.join(b), css), label


def head(num, title, t):
    k = THEMES[t]
    b = [rule(0, W, 1, k['text'], 2),
         text(0, 88, num, 44, k['accent'], MONO, 700),
         text(104, 88, title, 68, k['text'], SERIF, 400, ls=-1)]
    return svg(W, 110, f'{num} {title}', '\n'.join(b)), f'{num} {title}'   # 22px under the baseline for descenders


def word_list(words, t):
    k = THEMES[t]
    cols, rows = 3, math.ceil(len(words) / 3)
    cw, rh = W / cols, 60
    b = []
    for i, wd in enumerate(words):
        c, r = divmod(i, rows)
        x = c * cw + (0 if c == 0 else 12)
        b.append(rule(x, c * cw + cw - (12 if c < cols - 1 else 0), r * rh + 1, k['rule'], 1))
        b.append(text(x, r * rh + 43, wd, 38, k['text'], SERIF, 400))
    label = 'A Light Phone home screen: ' + ', '.join(words)
    return svg(W, rows * rh + 2, label, '\n'.join(b)), label


def button(label, w, filled, t):
    k = THEMES[t]
    h = 60
    if filled:
        b, fg = [f'<rect x="1" y="1" width="{w - 2}" height="{h - 2}" rx="6" fill="{k["accent"]}"/>'], k['on_accent']
    else:
        b, fg = [f'<rect x="1" y="1" width="{w - 2}" height="{h - 2}" rx="6" fill="none" stroke="{k["text"]}" stroke-width="2"/>'], k['text']
    b += [text(24, 38, label, 22, fg, SANS, 600), arrow(w - 48, 30, fg, 2.4, 1)]
    return svg(w, h, label, '\n'.join(b)), label


# ---------------------------------------------------------------- assemble
def keep_block(name, old):
    m = re.search(rf'<!-- {name} -->\n([\s\S]*?)<!-- /{name} -->', old)
    return f'<!-- {name} -->\n{m.group(1) if m else DEFAULT_BLOCKS[name]}<!-- /{name} -->'


def main():
    old = README.read_text(encoding='utf-8') if README.exists() else ''
    IMAGES.mkdir(exist_ok=True)
    for f in [*IMAGES.glob('*-light.svg'), *IMAGES.glob('*-dark.svg')]:
        f.unlink()   # everything generated is rebuilt; images/bright-sponsors.svg is left alone

    P, L = C['person'], C['links']
    md = [f'<p>{picture("masthead", W, write_pair("masthead", masthead))}</p>',
          ' · '.join(f'[{c["label"]}]({c["url"]})' if c.get('url') else c['label'] for c in P['contact'])]

    def section(num, sid, title):
        return f'<p>{picture(f"head-{sid}", W, write_pair(f"head-{sid}", head, num, title))}</p>'

    n = 0
    for n, s in enumerate(C['sections'], 1):
        num = f'{n:02d}'
        md.append(section(num, s['id'], s['title']))
        if s.get('intro'):
            md.append(s['intro'])
        if s.get('words'):
            md.append(f'<p>{picture("words", W, write_pair("words", word_list, s["words"]))}</p>')
        md.append(cards(num, s['items']))
        if s.get('outro'):
            md.append(s['outro'])

    md += [section(f'{n + 1:02d}', 'sponsors', 'Sponsors'),
           keep_block('Sponsors', old),
           f'<p><a href="{L["sponsor"]}">{picture("button-sponsor", 200, write_pair("button-sponsor", button, "Sponsor", 200, False))}</a></p>',
           section(f'{n + 2:02d}', 'guestbook', 'Guestbook'),
           f'<p><a href="{L["guestbook"]}">{picture("button-guestbook", 336, write_pair("button-guestbook", button, "Sign the guestbook", 336, True))}</a></p>',
           keep_block('Guestbook', old)]
    README.write_text('\n\n'.join(md) + '\n', encoding='utf-8')

    node = shutil.which('node')
    if node:   # re-render the Sponsors block in its current format, offline
        subprocess.run([node, '.github/scripts/sponsors.js', 'local'], cwd=ROOT, check=True)
    print(f'README.md and {len(list(IMAGES.glob("*-light.svg"))) * 2} images written'
          + ('' if node else ' (Node not found: Sponsors block left as it was)'))


if __name__ == '__main__':
    main()
