"""
A very small PDF writer — enough to typeset a bibliography page.

Standard Type1 fonts (Helvetica), one column, WinAnsi encoding, automatic
page breaks. No dependencies.
"""

# WinAnsi code points for punctuation that plain latin-1 does not cover.
WINANSI = {
    "\u2013": 0x96,  # en dash
    "\u2014": 0x97,  # em dash
    "\u2018": 0x91,  # left single quote
    "\u2019": 0x92,  # right single quote
    "\u201c": 0x93,  # left double quote
    "\u201d": 0x94,  # right double quote
    "\u2022": 0x95,  # bullet
    "\u2026": 0x85,  # ellipsis
    "\u00a0": 0x20,  # nbsp
}

PAGE_W, PAGE_H = 595.0, 842.0
MARGIN_X, MARGIN_TOP, MARGIN_BOTTOM = 56.0, 64.0, 56.0
BODY_SIZE, LEADING = 9.5, 13.0
TITLE_SIZE = 17.0
YEAR_SIZE = 12.5


def _encode(s):
    out = bytearray()
    for ch in s:
        if ch in WINANSI:
            out.append(WINANSI[ch])
        else:
            try:
                out.extend(ch.encode("latin-1"))
            except UnicodeEncodeError:
                out.extend(b"?")
    return bytes(out)


def _escape(s):
    return s.replace("\\", r"\\").replace("(", r"\(").replace(")", r"\)")


def _wrap(text, width_chars):
    words = text.split()
    if not words:
        return [""]
    lines, current = [], words[0]
    for w in words[1:]:
        if len(current) + 1 + len(w) <= width_chars:
            current += " " + w
        else:
            lines.append(current)
            current = w
    lines.append(current)
    return lines


class Doc:
    def __init__(self, width_chars=96):
        self.width_chars = width_chars
        self.pages = []
        self._ops = []
        self._y = PAGE_H - MARGIN_TOP

    def _new_page(self):
        if self._ops:
            self.pages.append("\n".join(self._ops))
        self._ops = []
        self._y = PAGE_H - MARGIN_TOP

    def _ensure(self, needed):
        if self._y - needed < MARGIN_BOTTOM:
            self._new_page()

    def space(self, amount):
        self._ensure(amount)
        self._y -= amount

    def text(self, s, size=BODY_SIZE, font="F1", indent=0.0, leading=LEADING):
        if not s.strip():
            return
        self._ensure(leading)
        chunk = _escape(s)
        self._ops.append(
            f"BT /{font} {size} Tf 1 0 0 1 {MARGIN_X + indent:.2f} {self._y:.2f} Tm ({chunk}) Tj ET"
        )
        self._y -= leading

    def title(self, s):
        self.space(6)
        self._ensure(TITLE_SIZE + 14)
        chunk = _escape(s)
        self._ops.append(
            f"BT /F2 {TITLE_SIZE} Tf 1 0 0 1 {MARGIN_X:.2f} {self._y:.2f} Tm ({chunk}) Tj ET"
        )
        self._y -= TITLE_SIZE + 10

    def rule(self):
        self._ensure(6)
        self._ops.append(
            f"0.78 0.76 0.72 RG 0.5 w {MARGIN_X:.2f} {self._y:.2f} m "
            f"{PAGE_W - MARGIN_X:.2f} {self._y:.2f} l S"
        )
        self._y -= 12

    def entry(self, text, indent=16.0):
        for line in _wrap(text, int(self.width_chars - indent)):
            self.text(line, indent=indent)

    def render(self):
        if self._ops:
            self.pages.append("\n".join(self._ops))
        return _assemble(self.pages)


def _assemble(pages):
    objects = []
    n_pages = len(pages)

    kids = " ".join(f"{4 + 2 * i} 0 R" for i in range(n_pages))
    objects.append(b"<< /Type /Catalog /Pages 2 0 R >>")
    objects.append(f"<< /Type /Pages /Kids [{kids}] /Count {n_pages} >>".encode())
    objects.append(b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica /Encoding /WinAnsiEncoding >>")
    objects.append(b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica-Bold /Encoding /WinAnsiEncoding >>")

    for i, content in enumerate(pages):
        page_obj = 4 + 2 * i
        content_obj = page_obj + 1
        objects.append(
            (
                f"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 {PAGE_W:.0f} {PAGE_H:.0f}] "
                f"/Resources << /Font << /F1 3 0 R /F2 4 0 R >> >> /Contents {content_obj} 0 R >>"
            ).encode()
        )
        stream = content.encode("latin-1", "replace")
        objects.append(
            b"<< /Length "
            + str(len(stream)).encode()
            + b" >>\nstream\n"
            + stream
            + b"\nendstream"
        )

    out = bytearray(b"%PDF-1.4\n%\xe2\xe3\xcf\xd3\n")
    offsets = []
    for i, obj in enumerate(objects, start=1):
        offsets.append(len(out))
        out += f"{i} 0 obj\n".encode() + obj + b"\nendobj\n"

    xref_pos = len(out)
    out += f"xref\n0 {len(objects) + 1}\n".encode()
    out += b"0000000000 65535 f \n"
    for off in offsets:
        out += f"{off:010d} 00000 n \n".encode()
    out += (
        f"trailer\n<< /Size {len(objects) + 1} /Root 1 0 R >>\nstartxref\n{xref_pos}\n%%EOF\n"
    ).encode()
    return bytes(out)
