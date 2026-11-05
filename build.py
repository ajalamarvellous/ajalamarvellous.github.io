#!/usr/bin/env python3
"""
Build the site.

    content/site.json  +  content/papers.bib  +  content/posts/*.md
        ->  public/

No third-party packages. Edit content, run `python3 build.py`, open
public/index.html.

    python3 build.py            # build
    python3 build.py --watch    # rebuild on every file change
"""

import html
import json
import os
import re
import shutil
import sys
import time
import unicodedata

import md

ROOT = os.path.dirname(os.path.abspath(__file__))
CONTENT = os.path.join(ROOT, "content")
TEMPLATES = os.path.join(ROOT, "templates")
STATIC = os.path.join(ROOT, "static")
PUBLIC = os.path.join(ROOT, "public")
SITE_URL = "https://ajalamarvellous.github.io"

# The nav bar. Home is the name (linked from the wordmark); News and About
# live in the "Elsewhere" list further down the page.
NAV_ITEMS = [
    ("/bibliography.html", "Publications"),
    ("/blog/", "Writing"),
    ("/projects.html", "Projects"),
]


# ==========================================================================
# BibTeX
# ==========================================================================


def _split_top_level(s, sep):
    out, buf = [], []
    depth, in_quote, escaped = 0, False, False
    for ch in s:
        if escaped:
            buf.append(ch)
            escaped = False
            continue
        if ch == "\\":
            buf.append(ch)
            escaped = True
            continue
        if ch == '"':
            in_quote = not in_quote
        if ch == "{" and not in_quote:
            depth += 1
        elif ch == "}" and not in_quote:
            depth -= 1
        if ch == sep and depth == 0 and not in_quote:
            out.append("".join(buf))
            buf = []
            continue
        buf.append(ch)
    out.append("".join(buf))
    return out


def _strip_outer_braces(s):
    while len(s) >= 2 and s[0] == "{" and s[-1] == "}":
        depth = 0
        matched_at = None
        for i, ch in enumerate(s):
            if ch == "{":
                depth += 1
            elif ch == "}":
                depth -= 1
                if depth == 0:
                    matched_at = i
                    break
        if matched_at != len(s) - 1:
            break
        s = s[1:-1]
    return s


def _parse_entry_body(body):
    key, _, rest = body.partition(",")
    fields = {}
    for chunk in _split_top_level(rest, ","):
        if "=" not in chunk:
            continue
        name, _, raw = chunk.partition("=")
        raw = raw.strip()
        if len(raw) >= 2 and raw[0] == '"' and raw[-1] == '"':
            raw = raw[1:-1]
        raw = _strip_outer_braces(raw)
        fields[name.strip().lower()] = raw.strip()
    return key.strip(), fields


def parse_bib(text):
    entries = []
    i = 0
    while True:
        at = text.find("@", i)
        if at == -1:
            break
        m = re.match(r"@(\w+)\s*\{", text[at:])
        if not m:
            i = at + 1
            continue
        start = at + m.end()
        depth, j = 1, start
        while j < len(text) and depth > 0:
            if text[j] == "{":
                depth += 1
            elif text[j] == "}":
                depth -= 1
            j += 1
        key, fields = _parse_entry_body(text[start : j - 1])
        if fields:
            entries.append({"type": m.group(1).lower(), "key": key, "fields": fields})
        i = j
    return entries


# ==========================================================================
# LaTeX -> plain text
# ==========================================================================

ACCENT_MARKS = {
    "'": "\u0301",
    "`": "\u0300",
    '"': "\u0308",
    "^": "\u0302",
    "~": "\u0303",
    "c": "\u0327",
}

LITERAL = {
    r"\&": "&", r"\_": "_", r"\%": "%", r"\$": "$", r"\#": "#",
    r"\{": "{", r"\}": "}", r"\textbackslash": "\\",
    r"\ss": "\u00df", r"\aa": "\u00e5", r"\AA": "\u00c5",
    r"\o": "\u00f8", r"\O": "\u00d8",
    r"\ldots": "\u2026", r"\dots": "\u2026", r"\cdots": "\u2026",
}

WRAPPERS = ("emph", "textit", "textbf", "textsc", "textrm", "texttt", "url", "mathrm")


def _accent(match):
    mark = ACCENT_MARKS.get(match.group(1))
    letter = match.group(2)
    if not mark or letter not in "aeiouyAEIOUYcnNCNSZzs":
        return match.group(0)
    return unicodedata.normalize("NFC", letter + mark)


def clean_latex(s):
    if not s:
        return ""
    s = s.replace("\n", " ")
    s = re.sub(r"\\([`'\^\"~c])\s*([A-Za-z])", _accent, s)
    for pat, rep in LITERAL.items():
        s = s.replace(pat, rep)
    for w in WRAPPERS:
        s = re.sub(r"\\" + w + r"\s*\{([^{}]*)\}", r"\1", s)
    s = re.sub(r"\\[a-zA-Z]+\s*", "", s)
    s = s.replace("~", " ")
    s = s.replace("---", "\u2014").replace("--", "\u2013")
    s = s.replace("{", "").replace("}", "")
    return re.sub(r"\s+", " ", s).strip()


def _norm(name):
    name = unicodedata.normalize("NFKD", name.lower())
    return re.sub(r"[^a-z0-9]", "", name)


def format_authors(raw, owner_names):
    if not raw:
        return ""
    owners = {_norm(o) for o in owner_names}
    names = [p.strip() for p in re.split(r"\s+and\s+", raw) if p.strip()]
    pieces = []
    for n in names:
        if n.lower() == "others":
            pieces.append("<em>et al.</em>")
            continue
        if "," in n:
            last, _, first = n.partition(",")
            display = f"{first.strip()} {last.strip()}".strip()
        else:
            display = n
        display = clean_latex(display)
        if not display:
            continue
        if _norm(display) in owners or _norm(n) in owners:
            pieces.append(f'<span class="me">{html.escape(display)}</span>')
        else:
            pieces.append(html.escape(display))
    return ", ".join(pieces)


def venue_of(f):
    for field in ("abbr", "shortvenue", "booktitle", "journal", "howpublished", "publisher"):
        if f.get(field):
            return clean_latex(f[field])
    return ""


def links_for(f):
    out = []
    doi = f.get("doi", "").strip()
    url = f.get("url", "").strip()
    doi_url = "https://doi.org/" + doi if doi else ""
    if f.get("pdf"):
        out.append(("PDF", f["pdf"]))
    if f.get("code"):
        out.append(("Code", f["code"]))
    if doi:
        out.append(("DOI", doi_url))
    if url and url != doi_url:
        out.append(("Link", url))
    return out


def render_paper(entry, owner_names):
    f = entry["fields"]
    title = clean_latex(f.get("title", "Untitled"))
    venue = venue_of(f)
    year = clean_latex(f.get("year", ""))
    pages = clean_latex(f.get("pages", ""))
    note = clean_latex(f.get("note", ""))
    status = clean_latex(f.get("status", ""))
    supervisor = clean_latex(f.get("supervisor", ""))
    selected = f.get("selected", "false").strip().lower() == "true"

    bits = [b for b in (venue, year) if b]
    if pages:
        bits.append("pp. " + pages)
    venue_line = ", ".join(bits)

    supervisor_html = (
        f'<p class="paper-supervisor">Supervisor: {html.escape(supervisor)}</p>'
        if supervisor else ""
    )

    badges = "".join(
        f'<span class="badge">{html.escape(b)}</span>'
        for b in (status, note)
        if b
    )

    links = links_for(f)
    link_html = ""
    if links:
        items = [
            f'<a href="{html.escape(url, quote=True)}">{html.escape(label)}</a>'
            for label, url in links
        ]
        link_html = '<p class="paper-links">' + '<span class="sep">/</span>'.join(items) + "</p>"

    abstract = clean_latex(f.get("abstract", ""))
    abstract_html = ""
    if abstract:
        abstract_html = (
            '<details class="paper-abs"><summary>Abstract</summary>'
            f"<p>{html.escape(abstract)}</p></details>"
        )

    title_html = html.escape(title)
    if f.get("pdf"):
        title_html = f'<a href="{html.escape(f["pdf"], quote=True)}">{title_html}</a>'

    authors = f.get("authorraw")
    if authors:
        author_html = html.escape(clean_latex(authors))
    else:
        author_html = format_authors(f.get("author", ""), owner_names)

    return f"""<article class="paper" data-selected="{'true' if selected else 'false'}">
<h3 class="paper-title">{title_html}</h3>
<p class="paper-authors">{author_html}</p>
<p class="paper-venue">{html.escape(venue_line)}{badges}</p>
{supervisor_html}
{link_html}
{abstract_html}
</article>"""


def render_reference(entry, owner_names, index):
    """A numbered bibliography entry, APA-ish."""
    f = entry["fields"]
    title = clean_latex(f.get("title", "Untitled"))
    venue = venue_of(f)
    year = clean_latex(f.get("year", "n.d."))
    pages = clean_latex(f.get("pages", ""))
    note = clean_latex(f.get("note", ""))
    status = clean_latex(f.get("status", ""))
    supervisor = clean_latex(f.get("supervisor", ""))

    authors = f.get("authorraw")
    if authors:
        author_html = html.escape(clean_latex(authors))
    else:
        author_html = format_authors(f.get("author", ""), owner_names)

    tail = []
    if venue:
        tail.append(html.escape(venue))
    if pages:
        tail.append("pp. " + html.escape(pages))
    for b in (status, note):
        if b:
            tail.append(f'<span class="badge">{html.escape(b)}</span>')
    tail_html = ". ".join(tail)

    links = links_for(f)
    link_html = ""
    if links:
        items = [
            f'<a href="{html.escape(url, quote=True)}">{html.escape(label)}</a>'
            for label, url in links
        ]
        link_html = '<span class="ref-links">' + '<span class="sep">/</span>'.join(items) + "</span>"

    sup = f'<div class="ref-supervisor">Supervisor: {html.escape(supervisor)}</div>' if supervisor else ""

    return f"""<li class="ref">
<span class="ref-index">{index}</span>
<div class="ref-body">
<p class="ref-text">{author_html} ({html.escape(year)}). {html.escape(title)}. {tail_html}</p>
{link_html}{sup}
</div>
</li>"""


# ==========================================================================
# Posts
# ==========================================================================


def parse_front_matter(text):
    m = re.match(r"^---\s*\n(.*?)\n---\s*\n(.*)$", text, re.S)
    if not m:
        return {}, text
    raw, body = m.group(1), m.group(2)
    meta = {}
    for line in raw.split("\n"):
        km = re.match(r'^([A-Za-z_]+):\s*(.*)$', line)
        if not km:
            continue
        key = km.group(1)
        val = km.group(2).strip()
        if len(val) >= 2 and val[0] == '"' and val[-1] == '"':
            val = val[1:-1]
        meta[key] = val
    return meta, body


MONTHS = [
    "January", "February", "March", "April", "May", "June",
    "July", "August", "September", "October", "November", "December",
]


def parse_date(s):
    m = re.match(r"(\d{4})-(\d{2})-(\d{2})(?:[ T](\d{2}):(\d{2}))?", s.strip())
    if not m:
        return None
    y, mo, d = int(m.group(1)), int(m.group(2)), int(m.group(3))
    hh = int(m.group(4) or 0)
    mm = int(m.group(5) or 0)
    return {
        "iso": f"{y:04d}-{mo:02d}-{d:02d}",
        "pretty": f"{d} {MONTHS[mo - 1]} {y}",
        "year": y,
        "month": mo,
        "day": d,
        "time": f"{hh:02d}:{mm:02d}",
        "sort": f"{y:04d}{mo:02d}{d:02d}{hh:02d}{mm:02d}",
    }


GENERIC_DESCRIPTIONS = {
    "essay", "essays", "personal", "review", "yearly review", "post",
    "article", "blog", "notes", "update", "life", "general",
}


def excerpt(body, limit=190):
    """First sentence or two of a post, for list pages."""
    text = md.plain_text(body)
    text = re.sub(r"^>\s*", "", text)
    if len(text) <= limit:
        return text
    cut = text[:limit]
    for mark in (". ", "? ", "! "):
        idx = cut.rfind(mark)
        if idx > limit * 0.4:
            return cut[: idx + 1].strip()
    idx = cut.rfind(" ")
    return (cut[:idx] + "…").strip()


def load_news():
    """News items are markdown files in content/news/, dated by front matter."""
    news = []
    base = os.path.join(CONTENT, "news")
    if not os.path.isdir(base):
        return news
    for fn in sorted(os.listdir(base)):
        if not fn.endswith(".md"):
            continue
        raw = open(os.path.join(base, fn), encoding="utf-8").read()
        meta, body = parse_front_matter(raw)
        d = parse_date(meta.get("date", ""))
        if not d:
            print(f"  warning: content/news/{fn} has no valid date, skipping")
            continue
        news.append({"date": d, "text": body.strip(), "file": fn})
    news.sort(key=lambda n: n["date"]["sort"], reverse=True)
    return news


def default_post_url(filename, date):
    """Jekyll-style URL: /blog/:year/:title/ -> /blog/:year/:title.html"""
    stem = filename[:-3] if filename.endswith(".md") else filename
    stem = re.sub(r"^\d{4}-\d{2}-\d{2}-", "", stem)
    return f"/blog/{date['year']}/{stem}.html"


def load_posts():
    posts = []
    base = os.path.join(CONTENT, "posts")
    for dirpath, _dirnames, filenames in os.walk(base):
        for fn in sorted(filenames):
            if not fn.endswith(".md"):
                continue
            path = os.path.join(dirpath, fn)
            raw = open(path, encoding="utf-8").read()
            meta, body = parse_front_matter(raw)
            d = parse_date(meta.get("date", "")) or {
                "iso": "1970-01-01", "pretty": "", "year": 1970,
                "month": 1, "day": 1, "time": "00:00", "sort": "0",
            }
            url = meta.get("url") or default_post_url(fn, d)
            desc = meta.get("description", "").strip()
            generated = desc.lower() in GENERIC_DESCRIPTIONS or not desc
            if generated:
                desc = excerpt(body)
            posts.append({
                "meta": meta,
                "body": body,
                "date": d,
                "url": url,
                "title": meta.get("title", fn[:-3]),
                "description": desc,
                "generated": generated,
                "tags": [t.strip() for t in meta.get("tags", "").split(",") if t.strip()],
                "thumbnail": meta.get("thumbnail", ""),
                "words": md.word_count(body),
                "minutes": max(1, round(md.word_count(body) / 220)),
            })
    posts.sort(key=lambda p: p["date"]["sort"], reverse=True)
    return posts


# ==========================================================================
# Page assembly
# ==========================================================================


def esc(s):
    return html.escape(s, quote=True)


def root_rel(path):
    """Make a content path root-relative so it resolves from any depth."""
    if not path:
        return path
    if path.startswith(("http://", "https://", "//", "/")):
        return path
    return "/" + path.lstrip("./")


def _active_for(canonical):
    c = canonical or "index.html"
    if c == "index.html":
        return "/"
    if c.startswith("blog"):
        return "/blog/"
    if c.startswith("bibliography"):
        return "/bibliography.html"
    if c.startswith("projects"):
        return "/projects.html"
    if c.startswith("news"):
        return "/news.html"
    if c.startswith("about"):
        return "/about.html"
    return "/"


def page(site, content, *, title=None, description=None, canonical="", ogtype="website", head=""):
    """Wrap a content fragment in the base template."""
    name = site["name"]
    full_title = f"{title} — {name}" if title else f"{name} — publications, writing and work"

    active = _active_for(canonical)
    nav = "".join(
        f'<a href="{esc(href)}"{" class=\"active\"" if href == active else ""}>{esc(label)}</a>'
        for href, label in NAV_ITEMS
    )

    links = []
    for link in site.get("links", []):
        target = ' target="_blank" rel="noopener"' if link.get("external") else ""
        links.append(f'<a href="{esc(link["url"])}"{target}>{esc(link["label"])}</a>')
    links_html = ""
    if links:
        links_html = '<span class="sep">/</span>' + '<span class="sep">/</span>'.join(links)

    elsewhere = "".join(
        f'<li><a href="{esc(x["url"])}">{esc(x["label"])}</a></li>'
        for x in site.get("elsewhere", [])
    )

    now_html = f'<p class="now">{esc(site["now"])}</p>' if site.get("now") else ""

    initial = unicodedata.normalize("NFKD", name).encode("ascii", "ignore").decode()
    initial = (initial[0] if initial else "A").upper()
    favicon = esc(
        "data:image/svg+xml,"
        "<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 64 64'>"
        "<rect width='64' height='64' rx='8' fill='%238a3b2c'/>"
        f"<text x='32' y='44' font-family='Georgia,serif' font-size='34' fill='white' "
        f"text-anchor='middle'>{initial}</text></svg>"
    )

    base_css = "/style.css"

    values = {
        "{{TITLE}}": esc(full_title),
        "{{DESCRIPTION}}": esc(description or site.get("description", "")),
        "{{AUTHOR}}": esc(name),
        "{{CANONICAL}}": esc(SITE_URL + "/" if canonical == "index.html" else SITE_URL + "/" + canonical),
        "{{OGTYPE}}": esc(ogtype),
        "{{HEAD}}": head,
        "{{CSS}}": base_css,
        "{{HOME}}": "/",
        "{{NAME}}": esc(name),
        "{{NAV}}": nav,
        "{{AFFILIATION}}": esc(site.get("affiliation", "")),
        "{{LINE}}": esc(site.get("line", "")),
        "{{EMAIL}}": esc(site.get("email", "")),
        "{{LINKS}}": links_html,
        "{{NOW}}": now_html,
        "{{CONTENT}}": content,
        "{{ELSEWHERE}}": elsewhere,
        "{{LAST_UPDATED}}": esc(site.get("last_updated", "")),
        "{{FAVICON}}": favicon,
    }

    with open(os.path.join(TEMPLATES, "base.html"), encoding="utf-8") as fh:
        out = fh.read()
    for k, v in values.items():
        out = out.replace(k, v)
    return out


def write(path, content):
    full = os.path.join(PUBLIC, path)
    os.makedirs(os.path.dirname(full), exist_ok=True)
    mode = "wb" if isinstance(content, (bytes, bytearray)) else "w"
    kwargs = {} if isinstance(content, (bytes, bytearray)) else {"encoding": "utf-8"}
    with open(full, mode, **kwargs) as fh:
        fh.write(content)


# ==========================================================================
# Page builders
# ==========================================================================


def build_papers_pdf(site, papers):
    """A typeset bibliography PDF, generated from the same .bib."""
    import pdflite

    doc = pdflite.Doc()
    doc.title(f"{site['name']} — publications")
    doc.text(site.get("affiliation", ""), size=9.5)
    doc.text(site.get("email", ""), size=9.5)
    doc.space(4)
    doc.rule()

    owner = site.get("owner_names", [])
    ordered = sorted(
        papers,
        key=lambda e: (
            -int(re.sub(r"\D", "", e["fields"].get("year", "0")) or 0),
            clean_latex(e["fields"].get("title", "")).lower(),
        ),
    )
    by_year = {}
    for e in ordered:
        by_year.setdefault(clean_latex(e["fields"].get("year", "n.d.")), []).append(e)

    index = 0
    for year, entries in by_year.items():
        doc.space(6)
        doc.text(year, size=12.5, font="F2")
        for e in entries:
            index += 1
            f = e["fields"]
            title = clean_latex(f.get("title", "Untitled"))
            venue = venue_of(f)
            pages = clean_latex(f.get("pages", ""))
            note = clean_latex(f.get("note", ""))
            status = clean_latex(f.get("status", ""))
            supervisor = clean_latex(f.get("supervisor", ""))

            if f.get("authorraw"):
                authors = clean_latex(f["authorraw"])
            else:
                authors = _plain_authors(f.get("author", ""), owner)

            tail = ", ".join(x for x in (venue, ("pp. " + pages) if pages else "") if x)
            for b in (status, note):
                if b:
                    tail += (", " if tail else "") + b
            line = f"{index}. {authors} ({year}). {title}."
            if tail:
                line += " " + tail + "."
            if supervisor:
                line += f" Supervisor: {supervisor}."
            doc.entry(line)

            links = links_for(f)
            if links:
                doc.text(
                    "   ".join(f"{label}: {url}" for label, url in links),
                    size=8.0,
                    indent=16.0,
                    leading=11.0,
                )
    return doc.render()


def _plain_authors(raw, owner_names):
    owners = {_norm(o) for o in owner_names}
    names = [p.strip() for p in re.split(r"\s+and\s+", raw) if p.strip()]
    out = []
    for n in names:
        if n.lower() == "others":
            out.append("et al.")
            continue
        if "," in n:
            last, _, first = n.partition(",")
            display = f"{first.strip()} {last.strip()}".strip()
        else:
            display = n
        display = clean_latex(display)
        if _norm(display) in owners or _norm(n) in owners:
            display = display.replace("À", "A").replace("à", "a")
        out.append(display)
    return ", ".join(out)


# Old URLs from the Jekyll site (permalink: /blog/:year/:title/) that must
# keep working. Each maps to the new path.
REDIRECTS = {
    "blog/2023/year-review": "/blog/2023/2023-year-review.html",
    "blog/2024/in-pursuit-of-happiness": "/blog/2024/in-pursuit-of-happiness.html",
    "blog/2024/mailing-list": "/blog/2024/mailing-list.html",
    "blog/2024/year-review": "/blog/2024/2024-year-review.html",
    "blog/2025/lessons-from-failure": "/blog/2025/lessons-from-failure.html",
    "blog/2025/sometimes-we-lose": "/blog/2025/when-we-do-everything-right-and-still-fail.html",
    "blog/2026/life-of-unending-optimism": "/blog/2026/live-a-life-of-unending-optimism.html",
    "news": "/news.html",
    "projects": "/projects.html",
    "publications": "/bibliography.html",
    "about": "/about.html",
    "404": "/404.html",
}


def build_redirect(old_path, target):
    """A static redirect stub — GitHub Pages has no server-side redirects."""
    return f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<title>Moved</title>
<link rel="canonical" href="{esc(SITE_URL + target)}">
<meta http-equiv="refresh" content="0; url={esc(target)}">
<meta name="robots" content="noindex">
</head>
<body>
<p>This page has moved to <a href="{esc(target)}">{esc(target)}</a>.</p>
</body>
</html>
"""


def build_index(site, papers, posts, news):
    owner = site.get("owner_names", [])
    selected = [p for p in papers if p["fields"].get("selected", "false").lower() == "true"]
    selected.sort(key=lambda e: (-int(re.sub(r"\D", "", e["fields"].get("year", "0")) or 0),))
    papers_html = "\n".join(render_paper(e, owner) for e in papers)

    recent = ""
    if posts:
        items = []
        for p in posts[:3]:
            items.append(f"""<li class="entry">
<p class="entry-meta"><time datetime="{p['date']['iso']}">{p['date']['pretty']}</time> &middot; {p['minutes']} min read</p>
<h3 class="entry-title"><a href="{esc(p['url'])}">{esc(p['title'])}</a></h3>
<p class="entry-desc">{esc(p['description'])}</p>
</li>""")
        recent = f"""<section class="block">
<div class="section-head">
<h2 class="section-label">Writing</h2>
<a class="more" href="/blog/">All posts</a>
</div>
<ul class="entries">{''.join(items)}</ul>
</section>"""

    news_html = ""
    if news:
        items = []
        for n in news[:5]:
            items.append(f'<li class="news-item"><time datetime="{n["date"]["iso"]}">{n["date"]["pretty"]}</time><span>{md.render(n["text"])}</span></li>')
        news_html = f"""<section class="block">
<div class="section-head">
<h2 class="section-label">Recent</h2>
<a class="more" href="/news.html">All news</a>
</div>
<ul class="news">{''.join(items)}</ul>
</section>"""

    content = f"""<section class="papers">
<div class="section-head">
<h2 class="section-label">Selected work</h2>
<button id="filter" class="filter" type="button" aria-pressed="false"></button>
</div>
{papers_html}
<p class="all-link"><a href="/bibliography.html">Full bibliography &rarr;</a></p>
</section>

{recent}

{news_html}

<section class="block">
<div class="section-head"><h2 class="section-label">About</h2></div>
<p class="prose">I am an AI engineer, a pharmacist and a researcher based in Abuja, Nigeria. I work on
applying artificial intelligence to drug discovery — virtual screening and de novo design — and I build
and write about the tools that make that possible.</p>
<p class="prose">I am also building <a href="https://magamios.org">Magami Open Sciences
Initiative</a>, a non-profit supporting African researchers in drug discovery and open science, and I
co-organise the <a href="https://datascienceforhealthafrica.site/">Data Science for Health</a>
workshop at Deep Learning Indaba.</p>
<p class="all-link"><a href="/about.html">More about me &rarr;</a></p>
</section>"""

    return page(site, content, canonical="index.html")


def build_bibliography(site, papers):
    owner = site.get("owner_names", [])
    ordered = sorted(
        papers,
        key=lambda e: (
            -int(re.sub(r"\D", "", e["fields"].get("year", "0")) or 0),
            0 if e["fields"].get("selected", "false").lower() == "true" else 1,
            clean_latex(e["fields"].get("title", "")).lower(),
        ),
    )
    by_year = {}
    for e in ordered:
        by_year.setdefault(clean_latex(e["fields"].get("year", "n.d.")), []).append(e)

    blocks = []
    index = 0
    for year, entries in by_year.items():
        items = []
        for e in entries:
            index += 1
            items.append(render_reference(e, owner, index))
        blocks.append(
            f'<section class="block year-block"><h2 class="year">{esc(year)}</h2>'
            f'<ol class="refs">{"".join(items)}</ol></section>'
        )

    content = f"""<div class="section-head">
<h2 class="section-label">Bibliography</h2>
<a class="more" href="/papers.pdf">Download (PDF)</a>
</div>
<p class="lede">All publications, most recent first. Under-review preprints are marked as such.</p>
{"".join(blocks)}"""

    return page(site, content, title="Publications", canonical="bibliography.html",
                description="Publications by Marvellous Ajala on AI for drug discovery.")


def build_blog_index(site, posts):
    items = []
    for p in posts:
        thumb = ""
        if p["thumbnail"]:
            thumb = f'<a class="entry-thumb" href="{esc(p["url"])}"><img src="{esc(root_rel(p["thumbnail"]))}" alt="" loading="lazy"></a>'
        tags = ""
        if p["tags"]:
            tags = ' <span class="entry-tags">' + ", ".join(esc(t) for t in p["tags"]) + "</span>"
        items.append(f"""<li class="entry entry-wide">
{thumb}
<div class="entry-body">
<p class="entry-meta"><time datetime="{p['date']['iso']}">{p['date']['pretty']}</time> &middot; {p['minutes']} min read{tags}</p>
<h3 class="entry-title"><a href="{esc(p['url'])}">{esc(p['title'])}</a></h3>
<p class="entry-desc">{esc(p['description'])}</p>
</div>
</li>""")

    content = f"""<div class="section-head">
<h2 class="section-label">Writing</h2>
<a class="more" href="/feed.xml">Feed</a>
</div>
<p class="lede">Essays on failure, optimism, research and the work of building things.
Also published on <a href="https://madeofajala.medium.com">Medium</a>,
<a href="https://the-continum.substack.com">Substack</a> and
<a href="https://madeofajala.hashnode.dev">Hashnode</a>.</p>
<ul class="entries entries-wide">{''.join(items)}</ul>"""

    return page(site, content, title="Writing", canonical="blog/",
                description="Essays by Marvellous Ajala on failure, optimism, research and building.",
                ogtype="website")


def build_post(site, post, prev_post, next_post):
    body = md.render(post["body"])
    # images inside posts are stored at the site root
    body = re.sub(r'(src=")img/', r"\1/img/", body)
    tags = ""
    if post["tags"]:
        tags = '<p class="post-tags">' + ", ".join(esc(t) for t in post["tags"]) + "</p>"
    nav = []
    if prev_post:
        nav.append(f'<a class="post-nav-prev" href="{esc(prev_post["url"])}">&larr; {esc(prev_post["title"])}</a>')
    if next_post:
        nav.append(f'<a class="post-nav-next" href="{esc(next_post["url"])}">{esc(next_post["title"])} &rarr;</a>')
    nav_html = f'<nav class="post-nav">{"".join(nav)}</nav>' if nav else ""

    content = f"""<article class="post">
<p class="post-meta"><time datetime="{post['date']['iso']}">{post['date']['pretty']}</time> &middot; {post['minutes']} min read</p>
<h2 class="post-title">{esc(post['title'])}</h2>
{(post['description'] and not post.get('generated')) and f'<p class="post-desc">{esc(post["description"])}</p>' or ""}
<div class="prose">
{body}
</div>
{tags}
</article>
{nav_html}"""

    return page(site, content, title=post["title"], canonical=post["url"].lstrip("/"),
                description=post["description"], ogtype="article")


def build_projects(site, projects):
    """An index of projects — title, one line of description, link to detail."""
    items = []
    for pr in projects:
        title_html = (
            f'<a href="/projects/{esc(pr["slug"])}.html">{esc(pr["title"])}</a>'
        )
        # An outlink to the project itself, if there is one.
        ext = ""
        if pr.get("url"):
            host = pr["url"].split("//")[-1].split("/")[0]
            ext = (
                f'<a class="project-item-ext" href="{esc(pr["url"])}"'
                f' target="_blank" rel="noopener"'
                f' aria-label="{esc(pr["title"])} on {esc(host)}, opens in a new tab">'
                f"&rarr;</a>"
            )
        items.append(f"""<li class="project-item">
<h3 class="project-item-title">{title_html}</h3>
<p class="project-item-tagline">{ext}{esc(pr.get("tagline", ""))}</p>
</li>""")

    content = f"""<div class="section-head"><h2 class="section-label">Projects</h2></div>
<p class="lede">Things I have built, mostly for teaching myself and for other people to use.</p>
<ul class="project-list">{''.join(items)}</ul>"""

    return page(site, content, title="Projects", canonical="projects.html",
                description="Open-source projects by Marvellous Ajala.")


def build_project(site, pr):
    """A single project — the full description, images and links."""
    body = re.sub(r'(src=")img/', r"\1/img/", md.render(pr.get("body", "")))
    link = pr.get("url")
    link_html = ""
    if link:
        label = link.split("//")[-1].split("/")[0]
        link_html = (
            f'<p class="project-detail-links">'
            f'<a href="{esc(link)}" target="_blank" rel="noopener">{esc(label)} &nearr;</a></p>'
        )
    content = f"""<div class="section-head">
<h2 class="section-label">Projects</h2>
<a class="more" href="/projects.html">&larr; All projects</a>
</div>
<article class="project-detail">
<h1 class="project-detail-title">{esc(pr["title"])}</h1>
<p class="project-detail-tagline">{esc(pr.get("tagline", ""))}</p>
{link_html}
<div class="prose">
{body}
</div>
</article>"""

    return page(site, content, title=pr["title"],
                canonical=f"projects/{pr['slug']}.html",
                description=pr.get("tagline", ""))


def build_news(site, news):
    items = []
    for n in news:
        items.append(
            f'<li class="news-item"><time datetime="{n["date"]["iso"]}">{n["date"]["pretty"]}</time>'
            f"<span>{md.render(n['text'])}</span></li>"
        )
    content = f"""<div class="section-head"><h2 class="section-label">News</h2></div>
<ul class="news news-full">{''.join(items)}</ul>"""

    return page(site, content, title="News", canonical="news.html",
                description="Recent talks, papers, workshops and milestones.")


ABOUT_BODY = """
I am an **AI engineer**, a **pharmacist** and a **researcher** based in Abuja, Nigeria.

I currently work as an AI Engineer at [SeamHealth Innovations](https://seamhealth.com), a healthtech consulting company, where I am responsible for
architecting and building resilient, scalable AI applications. Previously I worked at
[Juicelife](https://www.juicelife.io) (formerly Meuve Health), an AI startup using AI and computer
vision to remotely track, evaluate and quantify workouts; at Recop.it, a social commerce platform;
and at [Dryad Network](https://www.dryad.net) (in collaboration with Omdena), a climatetech startup
using AI and sensors to track wildfires in the Amazon. I have also worked with
[Lifebox Labs](https://lifebox.ng), a lifesciences startup building digital therapeutics for
hypertensive and diabetic patients in Lagos.

I hold a Bachelor of Pharmacy from the University of Lagos, and have worked as a pharmacist at the
[University of Ilorin Teaching Hospital](https://www.uithilorin.org.ng) and
[Bowen University Teaching Hospital](https://buth.edu.ng).

## Research

My primary research interest is the application of artificial intelligence to drug discovery,
specifically virtual screening and drug design. My current work is on rigorous evaluation of
LLMs and generative models for drug discovery, and on genome-scale virtual screening — asking
not only whether a model performs well, but understanding what the models conclusions are based on (mechanistically) and whether its conclusions are ones we should act on.

I am also building [Magami Open Sciences Initiative](https://magamios.org), a non-profit open
science organisation focused on collaborating with African researchers on drug discovery projects,
capacity building, and the development of open-source AI tools. If you are interested in starting a
collaboration, or just want to chat about what we do, email me at
[marvellous@magamios.org](mailto:marvellous@magamios.org).

Beyond that, I am involved in efforts generally geared towards global health, public health and the
application of AI in healthcare. I co-organise the
[Data Science for Health](https://datascienceforhealthafrica.site/) workshop at Deep Learning
Indaba — 2024 in Dakar, Senegal; 2025 in Kigali, Rwanda; and 2026 in Lagos, Nigeria.

## Writing

In my spare time you will catch me writing. I publish essays on
[Medium](https://madeofajala.medium.com), [Hashnode](https://madeofajala.hashnode.dev) and
[Substack](https://the-continum.substack.com), and I keep a mailing list for disseminating them. I
also run a photography page on [Instagram](https://instagram.com/shotsbymarve).

## Elsewhere

- [Google Scholar](https://scholar.google.com/citations?user=67T6um4AAAAJ&hl=en)
- [CV (PDF)](pdf/CV-Marvellous-Ajala.pdf)
- [GitHub](https://github.com/ajalamarvellous)
- [LinkedIn](https://www.linkedin.com/in/marvellousajala)
- [Twitter](https://twitter.com/madeofajala)
"""


def build_about(site):
    body = md.render(ABOUT_BODY)
    content = f"""<div class="section-head"><h2 class="section-label">About</h2></div>
<img class="about-photo" src="/img/me.jpg" alt="Marvellous Àjàlá">
<div class="prose">
{body}
</div>"""

    return page(site, content, title="About", canonical="about.html",
                description="About Marvellous Àjàlá — AI engineer, pharmacist and researcher.")


def build_404(site):
    content = """<div class="section-head"><h2 class="section-label">Not found</h2></div>
<p class="lede">That page does not exist. It may have moved, or it may never have existed.</p>
<p class="all-link"><a href="/">Back to the front page &rarr;</a></p>"""
    return page(site, content, title="Page not found", canonical="404.html",
                description="Page not found.")


def build_feed(site, posts):
    entries = []
    for p in posts:
        entries.append(f"""<entry>
<title>{esc(p['title'])}</title>
<link href="{SITE_URL}{esc(p['url'])}"/>
<id>{SITE_URL}{esc(p['url'])}</id>
<published>{p['date']['iso']}T{p['date']['time']}:00Z</published>
<updated>{p['date']['iso']}T{p['date']['time']}:00Z</updated>
<summary>{esc(p['description'])}</summary>
</entry>""")
    feed = f"""<?xml version="1.0" encoding="utf-8"?>
<feed xmlns="http://www.w3.org/2005/Atom">
<title>{esc(site['name'])} — writing</title>
<link href="{SITE_URL}/feed.xml" rel="self"/>
<link href="{SITE_URL}/"/>
<id>{SITE_URL}/</id>
<updated>{posts[0]['date']['iso'] if posts else '2026-01-01'}T00:00:00Z</updated>
<author><name>{esc(site['name'])}</name></author>
{''.join(entries)}
</feed>"""
    return feed


def build_sitemap(posts, projects):
    urls = [
        ("/", "1.0"),
        ("/bibliography.html", "0.8"),
        ("/blog/", "0.7"),
        ("/projects.html", "0.6"),
        ("/news.html", "0.5"),
        ("/about.html", "0.6"),
    ]
    urls += [(p["url"], "0.7") for p in posts]
    urls += [(f"/projects/{pr['slug']}.html", "0.6") for pr in projects]
    body = "".join(
        f"<url><loc>{SITE_URL}{u}</loc><priority>{p}</priority></url>" for u, p in urls
    )
    return (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
        f"{body}\n</urlset>\n"
    )


# ==========================================================================
# Main
# ==========================================================================


def build():
    site = json.load(open(os.path.join(CONTENT, "site.json"), encoding="utf-8"))
    papers = parse_bib(open(os.path.join(CONTENT, "papers.bib"), encoding="utf-8").read())
    posts = load_posts()
    projects = json.load(open(os.path.join(CONTENT, "projects.json"), encoding="utf-8"))
    news = load_news()

    # clean the output directory
    if os.path.isdir(PUBLIC):
        shutil.rmtree(PUBLIC)
    os.makedirs(PUBLIC, exist_ok=True)

    # static assets
    for name in os.listdir(STATIC):
        src = os.path.join(STATIC, name)
        dst = os.path.join(PUBLIC, name)
        if os.path.isdir(src):
            shutil.copytree(src, dst)
        else:
            shutil.copy2(src, dst)

    # pages
    write("index.html", build_index(site, papers, posts, news))
    write("bibliography.html", build_bibliography(site, papers))
    write("blog/index.html", build_blog_index(site, posts))
    write("projects.html", build_projects(site, projects))
    for pr in projects:
        write(f"projects/{pr['slug']}.html", build_project(site, pr))
    write("news.html", build_news(site, news))
    write("about.html", build_about(site))
    write("404.html", build_404(site))
    write("feed.xml", build_feed(site, posts))
    write("papers.pdf", build_papers_pdf(site, papers))
    write("sitemap.xml", build_sitemap(posts, projects))
    write("robots.txt", f"User-agent: *\nAllow: /\nSitemap: {SITE_URL}/sitemap.xml\n")
    # The custom domain, so the published branch declares it explicitly.
    if site.get("domain"):
        write("CNAME", site["domain"] + "\n")

    # redirect stubs for the old Jekyll URLs
    for old, target in REDIRECTS.items():
        write(f"{old}/index.html", build_redirect(old, target))

    # posts
    for i, p in enumerate(posts):
        prev_post = posts[i + 1] if i + 1 < len(posts) else None
        next_post = posts[i - 1] if i > 0 else None
        rel = p["url"].lstrip("/")
        write(rel, build_post(site, p, prev_post, next_post))

    n_sel = sum(
        1 for e in papers if e["fields"].get("selected", "false").lower() == "true"
    )
    print(
        f"built public/  ({len(papers)} papers, {n_sel} selected, "
        f"{len(posts)} posts, {len(news)} news, {len(projects)} projects)"
    )


def watch():
    stamp = None
    while True:
        paths = [os.path.join(TEMPLATES, f) for f in os.listdir(TEMPLATES)]
        paths += [os.path.join(CONTENT, f) for f in os.listdir(CONTENT) if os.path.isfile(os.path.join(CONTENT, f))]
        for dirpath, _d, filenames in os.walk(os.path.join(CONTENT, "posts")):
            paths += [os.path.join(dirpath, f) for f in filenames]
        paths += [os.path.join(STATIC, f) for f in os.listdir(STATIC)]
        try:
            sig = tuple(sorted((p, os.path.getmtime(p)) for p in paths))
        except OSError:
            sig = stamp
        if sig != stamp:
            stamp = sig
            try:
                build()
            except Exception as exc:
                import traceback
                traceback.print_exc()
        time.sleep(1.0)


if __name__ == "__main__":
    if "--watch" in sys.argv:
        watch()
    else:
        build()
