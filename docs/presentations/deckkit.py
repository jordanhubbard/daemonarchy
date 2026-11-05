#!/usr/bin/env python3
"""Shared deck builder for the Daemonarchy presentations.

Reads a deck specification written in a small Markdown dialect and writes a
PowerPoint file with python-pptx.  The specification is the single source of
the slide content; this module holds only layout and styling.  No network, no
LLM calls: the same specification always produces the same deck.

Specification dialect (see any deck-specification.md):

    deck-key: value            front matter, before the first "## "
    ## Slide title             starts a slide
    layout: cover|section|bullets|cards|table|diagram|code|stats|bars
    kicker: small label above the title
    lede: one-sentence framing under the title
    image: path/relative/to/the/spec.png      (bullets layout, right side)
    caption: text under the image
    - bullet                   (supports **bold**, `code`, and a leading
                               [verified] [not verified] [limit] [planned] tag)
    ### Card title | tone      starts a card (cards, diagram text, bars group)
    | a | b | c |              table rows (first row is the header)
    widths: 2,4,4              table column weights
    box: id | col,row WxH | Title | text | tone      (diagram)
    arrow: a -> b : label                            (diagram)
    stat: value | label        (stats)
    bar: label | value | unit | max | tone           (bars, inside a group)
    ```code```                 fenced code block (code layout)
    source: where the claim comes from (shown in the footer)
    notes: speaker notes (may continue on following indented lines)
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

from PIL import Image, ImageFont
from pptx import Presentation
from pptx.dml.color import RGBColor
from pptx.enum.shapes import MSO_CONNECTOR, MSO_SHAPE
from pptx.enum.text import MSO_ANCHOR, PP_ALIGN
from pptx.oxml.ns import qn
from pptx.util import Emu, Inches, Pt
from lxml import etree

SW, SH = 13.333, 7.5
FONT, MONO = "Arial", "Courier New"
C = {
    "ink": "0F1419", "panel": "1B222B", "text": "1F2933", "muted": "5F6B7A",
    "fog": "F3F4F6", "line": "D5DAE0", "white": "FFFFFF",
    "red": "C8102E", "red2": "FF6B6B", "green": "2E8B57", "amber": "B7791F",
    "blue": "2F6FA8", "slate": "52606D",
}
TONES = {
    "red": C["red"], "green": C["green"], "amber": C["amber"],
    "blue": C["blue"], "slate": C["slate"], "ink": C["panel"], "": C["slate"],
}
TAGS = {
    "[verified]": ("VERIFIED", C["green"]),
    "[not verified]": ("NOT VERIFIED", C["amber"]),
    "[limit]": ("LIMIT", C["amber"]),
    "[planned]": ("PLANNED", C["blue"]),
    "[same]": ("SAME", C["blue"]),
    "[different]": ("DIFFERENT", C["red"]),
}
_FONT_FILES = {
    False: "/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf",
    True: "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf",
}
_MONO_FILE = "/usr/share/fonts/truetype/liberation/LiberationMono-Regular.ttf"
_font_cache: dict = {}


def rgb(h: str) -> RGBColor:
    return RGBColor.from_string(h)


# ---------------------------------------------------------------- parsing
class Slide(dict):
    pass


def parse_spec(path: Path):
    front, slides, cur = {}, [], None
    lines = path.read_text(encoding="utf-8").splitlines()
    i, card, in_code, code = 0, None, False, []
    key_re = re.compile(r"^(layout|kicker|lede|image|caption|widths|source|notes|"
                        r"title|footer|stat|box|arrow|bar):\s*(.*)$")
    for raw in lines:
        if in_code:
            if raw.startswith("```"):
                cur["code"] = "\n".join(code)
                in_code, code = False, []
            else:
                code.append(raw)
            continue
        if raw.startswith("## "):
            cur = Slide(title=raw[3:].strip(), bullets=[], cards=[], rows=[],
                        boxes=[], arrows=[], stats=[], bars=[], notes="")
            slides.append(cur)
            card = None
            continue
        if cur is None:
            m = re.match(r"^([a-z-]+):\s*(.*)$", raw)
            if m:
                front[m.group(1)] = m.group(2).strip()
            continue
        if raw.startswith("```"):
            in_code = True
            continue
        if raw.startswith("<!--") or raw.startswith("<!--"):
            continue
        if raw.strip() == "---":
            card = None
            continue
        if raw.startswith("### "):
            head = raw[4:].strip()
            tone = ""
            if "|" in head:
                head, tone = [p.strip() for p in head.rsplit("|", 1)]
            card = {"title": head, "tone": tone, "bullets": []}
            cur["cards"].append(card)
            continue
        if raw.startswith("- "):
            (card["bullets"] if card is not None else cur["bullets"]).append(raw[2:].strip())
            continue
        if raw.startswith("|"):
            cells = [c.strip().replace("\x00", "|") for c in raw.strip().strip("|").replace("\\|", "\x00").split("|")]
            if not all(re.fullmatch(r":?-{2,}:?", c) for c in cells):
                cur["rows"].append(cells)
            continue
        m = key_re.match(raw)
        if m:
            k, v = m.group(1), m.group(2).strip()
            if k == "box":
                p = [x.strip().replace("\x00", "|") for x in v.replace("\\|", "\x00").split("|")]
                while len(p) < 5:
                    p.append("")
                cur["boxes"].append(p)
            elif k == "arrow":
                cur["arrows"].append(v)
            elif k == "stat":
                cur["stats"].append([x.strip() for x in v.split("|")])
            elif k == "bar":
                g = cur["cards"][-1] if cur["cards"] else None
                if g is None:
                    raise ValueError("bar: outside a ### group in " + cur["title"])
                g.setdefault("bars", []).append([x.strip() for x in v.split("|")])
            else:
                cur[k] = v
            last_key = k
            continue
        if raw.startswith("  ") and cur.get("notes") is not None and raw.strip():
            cur["notes"] = (cur["notes"] + " " + raw.strip()).strip()
    return front, slides


# ---------------------------------------------------------------- text
def _font(bold: bool, size: float, mono=False):
    k = (bold, round(size * 4), mono)
    if k not in _font_cache:
        _font_cache[k] = ImageFont.truetype(_MONO_FILE if mono else _FONT_FILES[bold], int(size * 10))
    return _font_cache[k]


def runs_of(text: str):
    """Split markup into (text, bold, mono) runs."""
    out = []
    for part in re.split(r"(\*\*.+?\*\*|`.+?`)", text):
        if not part:
            continue
        if part.startswith("**"):
            out.append((part[2:-2], True, False))
        elif part.startswith("`"):
            out.append((part[1:-1], False, True))
        else:
            out.append((part, False, False))
    return out


def split_tag(text: str):
    for k, (label, col) in TAGS.items():
        if text.lower().startswith(k):
            return (label, col), text[len(k):].strip()
    return None, text


def lines_needed(text: str, size: float, width_in: float, base_bold=False) -> int:
    """Greedy word-wrap estimate in Liberation Sans metrics."""
    width = width_in * 72 * 10  # points*10 as font units
    total = 0
    for para in text.split("\n"):
        words = []
        for t, b, m in runs_of(para):
            for w in re.findall(r"\S+\s*", t):
                words.append((w, b or base_bold, m))
        if not words:
            total += 1
            continue
        cur, n = 0.0, 1
        for w, b, m in words:
            wd = _font(b, size, m).getlength(w)
            if wd > width:  # unbreakable token: the renderer splits it mid-word
                n += int((cur + wd) // width)
                cur = (cur + wd) % width
                continue
            if cur + wd > width and cur > 0:
                n += 1
                cur = wd
            else:
                cur += wd
        total += n
    return total


def fit(texts, size, min_size, width_in, height_in, gap_pt=6, line=1.26, bold=False):
    """Largest size (pt) at which all paragraphs fit in the box."""
    s = size
    while s >= min_size:
        h = 0.0
        for t in texts:
            h += lines_needed(t, s, width_in, bold) * s * line + gap_pt
        if h / 72 <= height_in:
            return s
        s -= 0.5
    return min_size


def add_text(slide, x, y, w, h, text, size=16, color=C["text"], bold=False,
             align=PP_ALIGN.LEFT, anchor=MSO_ANCHOR.TOP, mono=False, font=None):
    tb = slide.shapes.add_textbox(Inches(x), Inches(y), Inches(w), Inches(h))
    tf = tb.text_frame
    tf.word_wrap = True
    tf.margin_left = tf.margin_right = tf.margin_top = tf.margin_bottom = 0
    tf.vertical_anchor = anchor
    first = True
    for para in str(text).split("\n"):
        p = tf.paragraphs[0] if first else tf.add_paragraph()
        first = False
        p.alignment = align
        for t, b, m in runs_of(para):
            r = p.add_run()
            r.text = t
            r.font.size = Pt(size)
            r.font.bold = bold or b
            r.font.name = MONO if (m or mono) else (font or FONT)
            r.font.color.rgb = rgb(color)
    return tb


def add_rect(slide, x, y, w, h, fill, line=None, shape=MSO_SHAPE.RECTANGLE, radius=None):
    sp = slide.shapes.add_shape(shape, Inches(x), Inches(y), Inches(w), Inches(h))
    sp.fill.solid()
    sp.fill.fore_color.rgb = rgb(fill)
    if line:
        sp.line.color.rgb = rgb(line)
        sp.line.width = Pt(0.75)
    else:
        sp.line.fill.background()
    sp.shadow.inherit = False
    if radius is not None and shape == MSO_SHAPE.ROUNDED_RECTANGLE:
        sp.adjustments[0] = radius
    return sp


def add_bullets(slide, x, y, w, h, bullets, size=18, min_size=11, color=C["text"],
                gap=7, bullet_color=None):
    """Bullets with leading status tags; shrinks to fit the box."""
    items = []
    for b in bullets:
        tag, rest = split_tag(b)
        items.append((tag, rest))
    indent = 0.28
    texts = [((tag[0] + "  ") if tag else "") + rest for tag, rest in items]
    s = fit(texts, size, min_size, w - indent, h, gap_pt=gap)
    tb = slide.shapes.add_textbox(Inches(x), Inches(y), Inches(w), Inches(h))
    tf = tb.text_frame
    tf.word_wrap = True
    tf.margin_left = tf.margin_right = tf.margin_top = tf.margin_bottom = 0
    first = True
    for tag, rest in items:
        p = tf.paragraphs[0] if first else tf.add_paragraph()
        first = False
        p.space_after = Pt(gap)
        p.line_spacing = 1.0
        pPr = p._p.get_or_add_pPr()
        pPr.set("marL", str(int(Inches(indent))))
        pPr.set("indent", str(-int(Inches(indent))))
        bu = etree.SubElement(pPr, qn("a:buClr"))
        sc = etree.SubElement(bu, qn("a:srgbClr"))
        sc.set("val", bullet_color or C["red"])
        bf = etree.SubElement(pPr, qn("a:buFont"))
        bf.set("typeface", "Arial")
        bc = etree.SubElement(pPr, qn("a:buChar"))
        bc.set("char", "▪")
        if tag:
            r = p.add_run()
            r.text = tag[0] + "  "
            r.font.size = Pt(s * 0.72)
            r.font.bold = True
            r.font.name = FONT
            r.font.color.rgb = rgb(tag[1])
        for t, b, m in runs_of(rest):
            r = p.add_run()
            r.text = t
            r.font.size = Pt(s)
            r.font.bold = b
            r.font.name = MONO if m else FONT
            r.font.color.rgb = rgb(color)
    return s


# ---------------------------------------------------------------- chrome
def chrome(prs, slide, deck, spec, n, total, dark=False):
    fg = "9AA5B1" if dark else C["muted"]
    add_rect(slide, 0, SH - 0.42, SW, 0.42, C["ink"] if dark else C["fog"])
    add_text(slide, 0.6, SH - 0.31, 3.0, 0.2, deck["footer"], 9.5, fg)
    src = spec.get("source", "")
    if src:
        src = "Source: " + src.replace("`", "")
        fs = 9.5
        while fs > 7 and _font(False, fs).getlength(src) > 8.6 * 72 * 10:
            fs -= 0.5
        add_text(slide, 3.7, SH - 0.31, 8.6, 0.2, src, fs, fg, align=PP_ALIGN.RIGHT)
    add_text(slide, SW - 0.95, SH - 0.31, 0.35, 0.2, f"{n}", 9.5, fg, align=PP_ALIGN.RIGHT)


def headline(slide, spec, dark=False, y=0.5):
    col = C["white"] if dark else C["ink"]
    if spec.get("kicker"):
        add_text(slide, 0.6, y, 11, 0.3, spec["kicker"].upper(), 11.5, C["red2"] if dark else C["red"], bold=True)
    size = fit([spec["title"]], 32, 22, 12.1, 1.0, gap_pt=0, bold=True, line=1.15)
    add_text(slide, 0.6, y + 0.3, 12.1, 0.95, spec["title"], size, col, bold=True)
    top = y + 0.3 + size * 1.15 * lines_needed(spec["title"], size, 12.1, True) / 72 + 0.12
    if spec.get("lede"):
        ls = fit([spec["lede"]], 17, 12.5, 12.1, 0.8, gap_pt=0)
        add_text(slide, 0.6, top, 12.1, 0.8, spec["lede"], ls, "C7CED6" if dark else C["muted"])
        top += lines_needed(spec["lede"], ls, 12.1) * ls * 1.18 / 72 + 0.15
    return top + 0.1


BODY_BOTTOM = SH - 0.62


# ---------------------------------------------------------------- layouts
def L_cover(prs, s, deck, spec, n, total):
    add_rect(s, 0, 0, SW, SH, C["ink"])
    add_rect(s, 0, 0, 0.28, SH, C["red"])
    if spec.get("kicker"):
        add_text(s, 1.0, 1.6, 11, 0.4, spec["kicker"].upper(), 14, C["red2"], bold=True)
    size = fit([spec["title"]], 54, 34, 11.2, 2.0, gap_pt=0, bold=True, line=1.1)
    add_text(s, 1.0, 2.1, 11.2, 2.0, spec["title"], size, C["white"], bold=True)
    if spec.get("lede"):
        ly = 2.1 + size * 1.1 * lines_needed(spec["title"], size, 11.2, True) / 72 + 0.45
        add_text(s, 1.0, ly, 10.5, 1.1, spec["lede"], 22, "C7CED6")
    if spec.get("footer"):
        add_text(s, 1.0, 6.2, 11.5, 0.6, spec["footer"], 12, "9AA5B1")
    for b in spec["bullets"]:
        pass


def L_section(prs, s, deck, spec, n, total):
    add_rect(s, 0, 0, SW, SH, C["panel"])
    add_rect(s, 0.9, 2.55, 0.12, 1.7, C["red"])
    if spec.get("kicker"):
        add_text(s, 1.3, 2.5, 10, 0.4, spec["kicker"].upper(), 13, C["red2"], bold=True)
    add_text(s, 1.3, 2.95, 11, 1.0, spec["title"], 40, C["white"], bold=True)
    if spec.get("lede"):
        add_text(s, 1.3, 3.95, 10.5, 1.2, spec["lede"], 19, "C7CED6")
    chrome(prs, s, deck, spec, n, total, dark=True)


def L_bullets(prs, s, deck, spec, n, total):
    top = headline(s, spec)
    img = spec.get("image")
    if img:
        p = (deck["_dir"] / img).resolve()
        iw, ih = Image.open(p).size
        maxw, maxh = 6.1, BODY_BOTTOM - top - (0.45 if spec.get("caption") else 0.05)
        sc = min(maxw / iw, maxh / ih)
        w, h = iw * sc, ih * sc
        x = SW - 0.6 - w
        add_rect(s, x - 0.04, top - 0.04, w + 0.08, h + 0.08, C["line"])
        s.shapes.add_picture(str(p), Inches(x), Inches(top), Inches(w), Inches(h))
        if spec.get("caption"):
            add_text(s, x - 0.04, top + h + 0.12, w + 0.08, 0.4, spec["caption"], 10.5, C["muted"])
        bw = x - 0.6 - 0.35
    else:
        bw = 12.1
    add_bullets(s, 0.6, top + 0.05, bw, BODY_BOTTOM - top - 0.05, spec["bullets"], size=22)
    chrome(prs, s, deck, spec, n, total)


def L_cards(prs, s, deck, spec, n, total):
    top = headline(s, spec)
    cards = spec["cards"]
    k = len(cards)
    gap = 0.25
    w = (12.13 - gap * (k - 1)) / k
    h = BODY_BOTTOM - top - (0.9 if spec["bullets"] else 0.05)
    for i, c in enumerate(cards):
        x = 0.6 + i * (w + gap)
        tone = TONES.get(c["tone"], C["slate"])
        add_rect(s, x, top, w, h, C["fog"], C["line"])
        add_rect(s, x, top, w, 0.09, tone)
        hs = fit([c["title"]], 19, 14, w - 0.4, 0.8, gap_pt=0, bold=True)
        add_text(s, x + 0.2, top + 0.22, w - 0.4, 0.6, c["title"], hs, tone, bold=True)
        hl = lines_needed(c["title"], hs, w - 0.4, True)
        by = top + 0.3 + hl * hs * 1.2 / 72 + 0.12
        add_bullets(s, x + 0.2, by, w - 0.4, top + h - by - 0.15, c["bullets"], size=19, min_size=11, gap=7)
    if spec["bullets"]:
        add_bullets(s, 0.6, top + h + 0.12, 12.1, 0.75, spec["bullets"], size=16, min_size=11, gap=3)
    chrome(prs, s, deck, spec, n, total)


def L_table(prs, s, deck, spec, n, total):
    top = headline(s, spec)
    rows = spec["rows"]
    ncol = len(rows[0])
    wts = [float(x) for x in spec.get("widths", ",".join("1" * ncol)).split(",")] if spec.get("widths") else [1] * ncol
    tot = sum(wts)
    cw = [12.13 * w / tot for w in wts]
    avail = BODY_BOTTOM - top - (0.8 if spec["bullets"] else 0.05)
    # choose one font size that makes the whole table fit
    size = 17.0
    while size > 9.5:
        hts = []
        for ri, r in enumerate(rows):
            hts.append(max(lines_needed(c, size, cw[ci] - 0.2, ri == 0 or ci == 0) * size * 1.22 / 72 + 0.2 for ci, c in enumerate(r)))
        if sum(hts) <= avail:
            break
        size -= 0.5
    y = top
    for ri, r in enumerate(rows):
        x = 0.6
        for ci, c in enumerate(r):
            if ri == 0:
                add_rect(s, x, y, cw[ci], hts[ri], C["ink"])
                add_text(s, x + 0.1, y + 0.09, cw[ci] - 0.2, hts[ri] - 0.1, c, size, C["white"], bold=True)
            else:
                fill = C["fog"] if ri % 2 else C["white"]
                add_rect(s, x, y, cw[ci], hts[ri], fill, C["line"])
                tag, rest = split_tag(c) if ci else (None, c)
                col, bd = (C["ink"] if ci == 0 else C["text"]), ci == 0
                if rest in ("pass", "FAIL", "skipped"):
                    col, bd = {"pass": C["green"], "FAIL": C["red"], "skipped": C["muted"]}[rest], True
                add_text(s, x + 0.1, y + 0.09, cw[ci] - 0.2, hts[ri] - 0.1, rest, size, col, bold=bd)
            x += cw[ci]
        y += hts[ri]
    if spec["bullets"]:
        add_bullets(s, 0.6, y + 0.15, 12.1, BODY_BOTTOM - y - 0.15, spec["bullets"], size=15, min_size=11, gap=3)
    chrome(prs, s, deck, spec, n, total)


def _anchor(b, side):
    x, y, w, h = b
    return {"l": (x, y + h / 2), "r": (x + w, y + h / 2), "t": (x + w / 2, y), "b": (x + w / 2, y + h)}[side]


def _arrow(slide, p1, p2, label="", color=C["slate"]):
    ln = slide.shapes.add_connector(MSO_CONNECTOR.STRAIGHT, Inches(p1[0]), Inches(p1[1]), Inches(p2[0]), Inches(p2[1]))
    ln.line.color.rgb = rgb(color)
    ln.line.width = Pt(2)
    spPr = ln._element.spPr
    lnel = spPr.find(qn("a:ln"))
    tail = etree.SubElement(lnel, qn("a:tailEnd"))
    tail.set("type", "triangle")
    tail.set("w", "med")
    tail.set("len", "med")
    if label:
        mx, my = (p1[0] + p2[0]) / 2, (p1[1] + p2[1]) / 2
        tw = max(0.9, 0.095 * len(label))
        add_rect(slide, mx - tw / 2, my - 0.13, tw, 0.26, C["white"])
        add_text(slide, mx - tw / 2, my - 0.1, tw, 0.22, label, 10, C["muted"], align=PP_ALIGN.CENTER)


def L_diagram(prs, s, deck, spec, n, total):
    top = headline(s, spec)
    boxes = {}
    cols = rows_ = 0
    parsed = []
    for bid, pos, title, text, tone in spec["boxes"]:
        m = re.match(r"(\d+),(\d+)(?:\s+(\d+)x(\d+))?", pos)
        c0, r0 = int(m.group(1)), int(m.group(2))
        cw_, rh_ = int(m.group(3) or 1), int(m.group(4) or 1)
        parsed.append((bid, c0, r0, cw_, rh_, title, text, tone))
        cols = max(cols, c0 + cw_)
        rows_ = max(rows_, r0 + rh_)
    foot = 1.15 if spec["bullets"] else 0.0
    area_h = BODY_BOTTOM - top - foot
    gx, gy = 0.55, 0.5
    bw = (12.13 - gx * (cols - 1)) / cols
    bh = min(2.7, (area_h - gy * (rows_ - 1)) / rows_)
    ytop = top + (area_h - (bh * rows_ + gy * (rows_ - 1))) / 2
    for bid, c0, r0, cw_, rh_, title, text, tone in parsed:
        x = 0.6 + c0 * (bw + gx)
        y = ytop + r0 * (bh + gy)
        w = bw * cw_ + gx * (cw_ - 1)
        h = bh * rh_ + gy * (rh_ - 1)
        boxes[bid] = (x, y, w, h)
        col = TONES.get(tone, C["slate"])
        add_rect(s, x, y, w, h, C["fog"], col, MSO_SHAPE.ROUNDED_RECTANGLE, 0.06)
        add_rect(s, x, y + 0.08, 0.08, h - 0.16, col)
        ts = 17.0
        while ts > 11 and _font(True, ts).getlength(title) > (w - 0.4) * 72 * 10:
            ts -= 0.5
        add_text(s, x + 0.22, y + 0.12, w - 0.34, 0.5, title, ts, col, bold=True)
        tl = lines_needed(title, ts, w - 0.34, True)
        ty = y + 0.18 + tl * ts * 1.2 / 72
        if text:
            es = fit([text], 18, 9.5, w - 0.4, h - (ty - y) - 0.1, gap_pt=0)
            add_text(s, x + 0.22, ty, w - 0.4, h - (ty - y) - 0.08, text, es, C["text"])
    for a in spec["arrows"]:
        m = re.match(r"(\w+)\s*->\s*(\w+)\s*(?::\s*(.*))?$", a)
        a1, a2, label = m.group(1), m.group(2), m.group(3) or ""
        b1, b2 = boxes[a1], boxes[a2]
        if abs((b1[1] + b1[3] / 2) - (b2[1] + b2[3] / 2)) < 0.3:  # same row
            if b1[0] < b2[0]:
                p1, p2 = _anchor(b1, "r"), _anchor(b2, "l")
            else:
                p1, p2 = _anchor(b1, "l"), _anchor(b2, "r")
        else:
            if b1[1] < b2[1]:
                p1, p2 = _anchor(b1, "b"), _anchor(b2, "t")
            else:
                p1, p2 = _anchor(b1, "t"), _anchor(b2, "b")
            # align vertically on shared x when overlapping
            lo, hi = max(b1[0], b2[0]), min(b1[0] + b1[2], b2[0] + b2[2])
            if hi > lo:
                xm = (lo + hi) / 2
                p1, p2 = (xm, p1[1]), (xm, p2[1])
        _arrow(s, p1, p2, label)
    if spec["bullets"]:
        add_bullets(s, 0.6, BODY_BOTTOM - foot + 0.1, 12.1, foot, spec["bullets"], size=17, min_size=11, gap=4)
    chrome(prs, s, deck, spec, n, total)


def L_code(prs, s, deck, spec, n, total):
    top = headline(s, spec)
    code = spec.get("code", "")
    cw = 6.9
    ch = BODY_BOTTOM - top - 0.05
    add_rect(s, 0.6, top, cw, ch, C["ink"], shape=MSO_SHAPE.ROUNDED_RECTANGLE, radius=0.03)
    nl = code.count("\n") + 1
    size = 14.0
    while size > 9 and (max(lines_needed(l, size, cw - 0.5) for l in code.split("\n")) > 1
                        and any(len(l) * size * 0.6 / 72 > cw - 0.5 for l in code.split("\n")) or nl * size * 1.25 / 72 > ch - 0.4):
        size -= 0.5
    tb = add_text(s, 0.85, top + 0.22, cw - 0.5, ch - 0.3, code, size, "E6EDF3", mono=True)
    add_bullets(s, 0.6 + cw + 0.4, top + 0.05, 12.73 - (0.6 + cw + 0.4), ch, spec["bullets"], size=18, min_size=11)
    chrome(prs, s, deck, spec, n, total)


def L_stats(prs, s, deck, spec, n, total):
    top = headline(s, spec)
    k = len(spec["stats"])
    gap = 0.25
    w = (12.13 - gap * (k - 1)) / k
    h = 1.9
    for i, st in enumerate(spec["stats"]):
        x = 0.6 + i * (w + gap)
        add_rect(s, x, top, w, h, C["fog"], C["line"])
        add_rect(s, x, top, w, 0.09, C["red"])
        vs = fit([st[0]], 40, 24, w - 0.3, 0.9, gap_pt=0, bold=True)
        add_text(s, x + 0.15, top + 0.3, w - 0.3, 0.9, st[0], vs, C["red"], bold=True)
        add_text(s, x + 0.15, top + 1.1, w - 0.3, 0.8, st[1] if len(st) > 1 else "", 13.5, C["text"])
    y = top + h + 0.3
    add_bullets(s, 0.6, y, 12.1, BODY_BOTTOM - y, spec["bullets"], size=18, min_size=11)
    chrome(prs, s, deck, spec, n, total)


def L_bars(prs, s, deck, spec, n, total):
    top = headline(s, spec)
    groups = spec["cards"]
    k = len(groups)
    gap = 0.3
    w = (12.13 - gap * (k - 1)) / k
    ch = 3.2
    foot = 0.9 if spec["bullets"] else 0
    ch = min(3.4, BODY_BOTTOM - top - foot - 0.1)
    for i, g in enumerate(groups):
        x = 0.6 + i * (w + gap)
        add_text(s, x, top, w, 0.4, g["title"], 15, C["ink"], bold=True)
        base = top + ch
        bars = g.get("bars", [])
        bw = (w - 0.2 * (len(bars) - 1)) / max(len(bars), 1) * 0.8
        mx = max(float(b[3]) for b in bars)
        for j, b in enumerate(bars):
            label, val, unit, maxv = b[0], float(b[1]), b[2], float(b[3])
            tone = TONES.get(b[4] if len(b) > 4 else "", C["slate"])
            bx = x + 0.1 + j * (bw + 0.2 + (w - 0.2 * (len(bars) - 1) - bw * len(bars)) / max(len(bars), 1))
            bh = (ch - 1.25) * val / mx
            add_rect(s, bx, base - 0.55 - bh, bw, bh, tone)
            add_text(s, bx - 0.1, base - 0.55 - bh - 0.36, bw + 0.2, 0.3, f"{val:g} {unit}", 14, C["ink"], bold=True, align=PP_ALIGN.CENTER)
            add_text(s, bx - 0.15, base - 0.48, bw + 0.3, 0.5, label, 11, C["muted"], align=PP_ALIGN.CENTER)
        add_rect(s, x, base - 0.56, w, 0.02, C["line"])
    if spec["bullets"]:
        add_bullets(s, 0.6, top + ch + 0.15, 12.1, BODY_BOTTOM - top - ch - 0.15, spec["bullets"], size=15, min_size=11, gap=3)
    chrome(prs, s, deck, spec, n, total)


LAYOUTS = {"cover": L_cover, "section": L_section, "bullets": L_bullets, "cards": L_cards,
           "table": L_table, "diagram": L_diagram, "code": L_code, "stats": L_stats, "bars": L_bars}


def build(spec_path: Path, out_path: Path):
    front, slides = parse_spec(spec_path)
    deck = {"footer": front.get("footer", front.get("title", "")), "_dir": spec_path.parent}
    prs = Presentation()
    prs.slide_width, prs.slide_height = Inches(SW), Inches(SH)
    blank = prs.slide_layouts[6]
    prs.core_properties.title = front.get("title", "")
    prs.core_properties.author = "Daemonarchy contributors"
    prs.core_properties.subject = front.get("subject", "")
    total = len(slides)
    for i, sp in enumerate(slides, 1):
        s = prs.slides.add_slide(blank)
        lay = sp.get("layout", "bullets")
        if lay == "cover":
            sp.setdefault("footer", front.get("cover-footer", ""))
        LAYOUTS[lay](prs, s, deck, sp, i, total)
        if sp.get("notes"):
            s.notes_slide.notes_text_frame.text = sp["notes"]
    out_path.parent.mkdir(parents=True, exist_ok=True)
    prs.save(out_path)
    return total


if __name__ == "__main__":
    spec = Path(sys.argv[1])
    out = Path(sys.argv[2])
    print(f"{build(spec, out)} slides -> {out}")
