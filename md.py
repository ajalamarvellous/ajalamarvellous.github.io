"""
A small Markdown subset renderer — enough for this site's posts, no dependencies.

Handles: paragraphs, ATX headings, blockquotes, bullet/ordered lists, task
lists, fenced code blocks, horizontal rules, images, links, bold, italic,
inline code, and raw HTML passthrough.
"""

import html
import re

# --------------------------------------------------------------------------
# inline
# --------------------------------------------------------------------------

_HTML_TAG = re.compile(r"<(?:[a-zA-Z][^>]*|/[a-zA-Z][^>]*|!--.*?-->)>", re.S)
_IMG = re.compile(r"!\[(?P<alt>[^\]]*)\]\((?P<src>[^)\s]+)(?:\s+\"(?P<title>[^\"]*)\")?\)")
_LINK = re.compile(r"(?<!\!)\[(?P<text>[^\]]*)\]\((?P<href>[^)\s]+)(?:\s+\"(?P<title>[^\"]*)\")?\)")
_CODE = re.compile(r"`(?P<code>[^`]+)`")
_BOLD = re.compile(r"\*\*(?P<text>.+?)\*\*", re.S)
_BOLD2 = re.compile(r"__(?P<text>.+?)__", re.S)
_ITALIC = re.compile(r"(?<![\*\w])\*(?P<text>[^*\n]+?)\*(?![\*\w])")
_ITALIC2 = re.compile(r"(?<![\w_])_(?P<text>[^_\n]+?)_(?![\w_])")
_AUTOLINK = re.compile(r"(?<![<\w])(https?://[^\s<>\"]+)")


def _protect_html(text, store):
    def repl(m):
        store.append(m.group(0))
        return f"\x00{len(store) - 1}\x00"
    return _HTML_TAG.sub(repl, text)


def _restore_html(text, store):
    return re.sub(r"\x00(\d+)\x00", lambda m: store[int(m.group(1))], text)


def _inline(text):
    store = []
    text = _protect_html(text, store)

    def keep(markup):
        store.append(markup)
        return f"\x00{len(store) - 1}\x00"

    text = html.escape(text, quote=False)

    # images first, then links, then bare URLs — each result is parked in the
    # store so later passes cannot rewrite text inside an already-built tag.
    text = _IMG.sub(
        lambda m: keep(
            (
                f'<figure><img src="{html.escape(m.group("src"), quote=True)}"'
                f' alt="{html.escape(m.group("alt"), quote=True)}"'
                + (f' title="{html.escape(m.group("title"), quote=True)}"' if m.group("title") else "")
                + ' loading="lazy">'
                + f'<figcaption>{m.group("alt")}</figcaption></figure>'
            )
            if m.group("alt").strip()
            else (
                f'<img src="{html.escape(m.group("src"), quote=True)}"'
                f' alt="{html.escape(m.group("alt"), quote=True)}"'
                + (f' title="{html.escape(m.group("title"), quote=True)}"' if m.group("title") else "")
                + ' loading="lazy">'
            )
        ),
        text,
    )
    text = _LINK.sub(
        lambda m: keep(
            f'<a href="{html.escape(m.group("href"), quote=True)}"'
            + (f' title="{html.escape(m.group("title"), quote=True)}"' if m.group("title") else "")
            + f">{m.group('text')}</a>"
        ),
        text,
    )
    text = _AUTOLINK.sub(lambda m: keep(f'<a href="{m.group(1)}">{m.group(1)}</a>'), text)
    text = _CODE.sub(lambda m: keep(f"<code>{m.group('code')}</code>"), text)
    text = _BOLD.sub(lambda m: keep(f"<strong>{m.group('text')}</strong>"), text)
    text = _BOLD2.sub(lambda m: keep(f"<strong>{m.group('text')}</strong>"), text)
    text = _ITALIC.sub(lambda m: keep(f"<em>{m.group('text')}</em>"), text)
    text = _ITALIC2.sub(lambda m: keep(f"<em>{m.group('text')}</em>"), text)

    return _restore_html(text, store)


# --------------------------------------------------------------------------
# block
# --------------------------------------------------------------------------


def _slug(text):
    s = re.sub(r"[^\w\s-]", "", text.lower())
    return re.sub(r"[\s_-]+", "-", s).strip("-")


def render(md):
    md = md.replace("\r\n", "\n").replace("\r", "\n")
    lines = md.split("\n")
    out = []
    i = 0
    n = len(lines)

    while i < n:
        line = lines[i]

        if not line.strip():
            i += 1
            continue

        # fenced code
        m = re.match(r"^\s*```\s*(\w*)\s*$", line)
        if m:
            lang = m.group(1)
            i += 1
            buf = []
            while i < n and not re.match(r"^\s*```\s*$", lines[i]):
                buf.append(lines[i])
                i += 1
            i += 1
            cls = f' class="language-{lang}"' if lang else ""
            body = html.escape("\n".join(buf), quote=False)
            out.append(f"<pre><code{cls}>{body}\n</code></pre>")
            continue

        # horizontal rule
        if re.match(r"^\s*([-*_])\s*(\1\s*){2,}$", line):
            out.append("<hr>")
            i += 1
            continue

        # heading
        m = re.match(r"^(#{1,6})\s+(.*?)\s*#*\s*$", line)
        if m:
            level = len(m.group(1))
            text = m.group(2)
            out.append(f'<h{level} id="{_slug(text)}">{_inline(text)}</h{level}>')
            i += 1
            continue

        # blockquote
        if re.match(r"^\s*>", line):
            buf = []
            while i < n and (re.match(r"^\s*>", lines[i]) or (buf and lines[i].strip())):
                buf.append(re.sub(r"^\s*>\s?", "", lines[i]))
                i += 1
            inner = render("\n".join(buf))
            out.append(f"<blockquote>{inner}</blockquote>")
            continue

        # list
        if re.match(r"^\s*([-*+]|\d+\.)\s+", line):
            ordered = bool(re.match(r"^\s*\d+\.\s+", line))
            items = []
            while i < n:
                lm = re.match(r"^(\s*)([-*+]|\d+\.)\s+(.*)$", lines[i])
                if lm and len(lm.group(1)) < 3:
                    content = lm.group(3)
                    task = None
                    tm = re.match(r"^\[([ xX])\]\s+(.*)$", content)
                    if tm:
                        task = tm.group(1).lower() == "x"
                        content = tm.group(2)
                    items.append((content, task))
                    i += 1
                elif lines[i].strip() and lines[i].startswith(("  ", "\t")) and items:
                    # continuation line
                    items[-1] = (items[-1][0] + " " + lines[i].strip(), items[-1][1])
                    i += 1
                else:
                    break
            tag = "ol" if ordered else "ul"
            has_tasks = any(t is not None for _c, t in items)
            lis = []
            for content, task in items:
                inner = _inline(content)
                if task is not None:
                    mark = '<span class="task done">✓</span>' if task else '<span class="task">○</span>'
                    inner = f"{mark} {inner}"
                lis.append(f"<li>{inner}</li>")
            cls = ' class="tasks"' if has_tasks else ""
            out.append(f"<{tag}{cls}>{''.join(lis)}</{tag}>")
            continue

        # paragraph: consume until a blank line or a block-level marker
        buf = []
        while i < n and lines[i].strip():
            nxt = lines[i]
            if (
                re.match(r"^\s*(#{1,6}\s|```|>|([-*+]|\d+\.)\s)", nxt)
                and buf
            ):
                break
            buf.append(nxt)
            i += 1
        para = "\n".join(buf).strip()
        if para:
            out.append(f"<p>{_inline(para)}</p>")

    return "\n".join(out)


def plain_text(md):
    """Strip markdown to plain text — used for excerpts and reading time."""
    md = re.sub(r"```.*?```", " ", md, flags=re.S)
    md = re.sub(r"!\[[^\]]*\]\([^)]*\)", " ", md)
    md = re.sub(r"\[([^\]]*)\]\([^)]*\)", r"\1", md)
    md = re.sub(r"[*_`>#]", "", md)
    md = re.sub(r"<[^>]+>", " ", md)
    return re.sub(r"\s+", " ", md).strip()


def word_count(md):
    return len(plain_text(md).split())
