"""Umwandlung von body_html bzw. Markdown/TXT in einen kanonischen Text mit exakten Zeichenankern.

Der kanonische Text ist die Referenz für alle Spannen: Absätze, Zitate, Links und Argumentationseinheiten
verweisen über start_char/end_char auf genau diesen Text, der unverändert (mit SHA-256) gespeichert wird.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

from bs4 import BeautifulSoup, NavigableString, Tag

EXTRACT_VERSION = "extract-1"

BLOCK_TAGS = {"p": "p", "h1": "h", "h2": "h", "h3": "h", "h4": "h", "h5": "h", "h6": "h", "pre": "pre", "figcaption": "caption"}
SKIP_CLASSES = ("subscription-widget", "button-wrapper", "subscribe-widget", "share-dialog", "image-link-expand",
                "paywall", "footnote-anchor")
WS = re.compile(r"\s+")
TRACKING = re.compile(r"^(utm_\w+|ref|ref_src|source|fbclid|gclid|mc_cid|mc_eid|r|s|si|triedRedirect|publication_id|post_id|isFreemail|token)$", re.I)


@dataclass
class Para:
    start: int
    end: int
    kind: str
    speaker_hint: str


@dataclass
class Link:
    start: int
    end: int
    href: str
    target: str


@dataclass
class Extracted:
    text: str
    paragraphs: list[Para] = field(default_factory=list)
    links: list[Link] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)


def normalize_target(href: str) -> str:
    """Normalisierte Link-Ziele, damit mehrfach zitierte Quellen als dieselbe Quelle erkannt werden."""
    try:
        p = urlsplit(href.strip())
    except ValueError:
        return href.strip()
    host = p.netloc.lower().removeprefix("www.")
    path = p.path.rstrip("/")
    # Bekannte Varianten: arXiv abs/pdf/Version, DOI-Resolver
    m = re.match(r"/(?:abs|pdf)/(\d{4}\.\d{4,5})(?:v\d+)?(?:\.pdf)?$", path)
    if host == "arxiv.org" and m:
        return f"arxiv:{m.group(1)}"
    if host in ("doi.org", "dx.doi.org"):
        return "doi:" + path.lstrip("/").lower()
    if host == "youtu.be" and path:
        return f"youtube:{path.lstrip('/')}"
    # Query bleibt erhalten (z. B. youtube.com/watch?v=…), nur Tracking-Parameter werden entfernt.
    params = sorted(kv for kv in parse_qsl(p.query, keep_blank_values=False) if not TRACKING.match(kv[0]))
    if host.endswith("youtube.com") and path == "/watch":
        v = dict(params).get("v")
        return f"youtube:{v}" if v else "youtube.com/watch"
    return urlunsplit(("", host, path, urlencode(params), "")).lstrip("/")


class _Builder:
    def __init__(self):
        self.parts: list[str] = []
        self.length = 0
        self.paras: list[Para] = []
        self.links: list[Link] = []

    def add_block(self, pieces: list[tuple[str, str | None]], kind: str, speaker: str) -> None:
        # pieces: (text, href|None). Leerraum wird zusammengefasst, Offsets werden dabei exakt mitgeführt.
        buf: list[str] = []
        blen = 0
        pending_links = []
        for txt, href in pieces:
            t = WS.sub(" ", txt)
            if not t:
                continue
            if (blen == 0 or (buf and buf[-1].endswith(" "))) and t.startswith(" "):
                t = t[1:]
                if not t:
                    continue
            s = blen
            buf.append(t)
            blen += len(t)
            if href:
                pending_links.append((s, blen, href))
        block = "".join(buf)
        stripped = block.rstrip()
        if not stripped.strip():
            return
        if self.parts:
            self.parts.append("\n\n")
            self.length += 2
        base = self.length
        self.parts.append(stripped)
        self.length += len(stripped)
        self.paras.append(Para(base, base + len(stripped), kind, speaker))
        for s, e, href in pending_links:
            e = min(e, len(stripped))
            # führende/abschließende Leerzeichen der Linkspanne abschneiden
            while s < e and stripped[s] == " ":
                s += 1
            while e > s and stripped[e - 1] == " ":
                e -= 1
            if e > s:
                self.links.append(Link(base + s, base + e, href, normalize_target(href)))

    def text(self) -> str:
        return "".join(self.parts)


def _skip(el: Tag) -> bool:
    cls = " ".join(el.get("class") or [])
    return any(c in cls for c in SKIP_CLASSES) or el.name in ("script", "style", "noscript", "svg", "button", "form", "img", "picture", "source")


def _inline(el, href=None) -> list[tuple[str, str | None]]:
    out: list[tuple[str, str | None]] = []
    for ch in el.children:
        if isinstance(ch, NavigableString):
            if ch.__class__.__name__ in ("Comment", "Doctype"):
                continue
            out.append((str(ch), href))
        elif isinstance(ch, Tag):
            if _skip(ch):
                continue
            if ch.name == "br":
                out.append((" ", href))
                continue
            h = ch.get("href") if ch.name == "a" and ch.get("href") else href
            if h and h.startswith("#"):
                h = href  # interne Sprungmarken (Fußnoten) sind keine Quellen
            out.extend(_inline(ch, h))
    return out


def _walk(el: Tag, b: _Builder, in_quote: bool) -> None:
    for ch in el.children:
        if isinstance(ch, NavigableString):
            if str(ch).strip() and ch.__class__.__name__ not in ("Comment", "Doctype"):
                b.add_block([(str(ch), None)], "p", "quoted_other" if in_quote else "author")
            continue
        if not isinstance(ch, Tag) or _skip(ch):
            continue
        name = ch.name
        cls = " ".join(ch.get("class") or [])
        if name == "blockquote" or "pullquote" in cls:
            # Blockzitate sind meist Fremdzitate, bei Substack aber auch Pull-Quotes des Autors -> Hinweis 'unclear'
            _walk(ch, b, True)
        elif name in BLOCK_TAGS:
            kind = BLOCK_TAGS[name]
            speaker = "quoted_other" if in_quote else ("unclear" if "pullquote" in cls else "author")
            b.add_block(_inline(ch), kind, speaker)
        elif name == "li":
            if ch.find(["p", "ul", "ol"]):
                _walk(ch, b, in_quote)
            else:
                b.add_block(_inline(ch), "li", "quoted_other" if in_quote else "author")
        elif "footnote" in cls and name == "div":
            b.add_block(_inline(ch), "footnote", "author")
        else:
            _walk(ch, b, in_quote)


def html_to_canonical(html: str) -> Extracted:
    soup = BeautifulSoup(html or "", "lxml")
    root = soup.body or soup
    b = _Builder()
    _walk(root, b, False)
    ex = Extracted(text=b.text(), paragraphs=b.paras, links=b.links)
    for p in ex.paragraphs:
        if p.speaker_hint == "quoted_other":
            ex.notes.append("blockquote")
            break
    return ex


MD_LINK = re.compile(r"\[([^\]]+)\]\(([^)\s]+)\)")


def markdown_to_canonical(md: str) -> Extracted:
    """Einfacher Markdown/TXT-Import: Absätze an Leerzeilen, '>' als Zitat, '#' als Überschrift, [x](url) als Link."""
    b = _Builder()
    blocks = re.split(r"\n\s*\n", md.replace("\r\n", "\n"))
    for blk in blocks:
        blk = blk.strip()
        if not blk:
            continue
        kind, speaker = "p", "author"
        if blk.startswith("#"):
            kind = "h"
            blk = blk.lstrip("#").strip()
        elif blk.startswith(">"):
            speaker = "quoted_other"
            blk = "\n".join(line.lstrip(">").strip() for line in blk.splitlines())
        pieces: list[tuple[str, str | None]] = []
        pos = 0
        for m in MD_LINK.finditer(blk):
            pieces.append((blk[pos:m.start()], None))
            pieces.append((m.group(1), m.group(2)))
            pos = m.end()
        pieces.append((blk[pos:], None))
        b.add_block(pieces, kind, speaker)
    return Extracted(text=b.text(), paragraphs=b.paras, links=b.links)


# Inline-Zitate innerhalb eines Absatzes (Fall 6): „…“ "…" “…” ‚…‘ «…» – als Sprecherhinweis, nicht als Urteil.
QUOTE_RE = re.compile(r"„([^“”\"]{3,}?)[“”\"]|“([^”]{3,}?)”|\"([^\"]{3,}?)\"|‚([^‘’]{3,}?)[‘’]|«([^»]{3,}?)»")


def inline_quotes(text: str, para: Para) -> list[tuple[int, int]]:
    seg = text[para.start:para.end]
    out = []
    for m in QUOTE_RE.finditer(seg):
        out.append((para.start + m.start(), para.start + m.end()))
    return out


WORD_RE = re.compile(r"\w+", re.UNICODE)


def word_count(text: str) -> int:
    return len(WORD_RE.findall(text))
