#!/usr/bin/env python3
"""Check every local link and image in public/ actually resolves."""

import os
import re
import sys

PUBLIC = os.path.join(os.path.dirname(os.path.abspath(__file__)), "public")

HREF = re.compile(r'(?:href|src)="([^"]+)"')
BROKEN_LINK = 0


def check():
    global BROKEN_LINK
    problems = []
    for dirpath, _d, filenames in os.walk(PUBLIC):
        for fn in sorted(filenames):
            if not fn.endswith(".html"):
                continue
            page = os.path.join(dirpath, fn)
            rel_page = os.path.relpath(page, PUBLIC)
            html = open(page, encoding="utf-8").read()
            for m in HREF.finditer(html):
                url = m.group(1)
                if url.startswith(("http://", "https://", "mailto:", "data:", "//", "#")):
                    continue
                target = url.split("#")[0].split("?")[0]
                if not target:
                    continue
                if target.startswith("/"):
                    resolved = os.path.join(PUBLIC, target.lstrip("/"))
                else:
                    resolved = os.path.normpath(os.path.join(dirpath, target))
                if not os.path.exists(resolved):
                    problems.append((rel_page, url))
                    BROKEN_LINK += 1

    if problems:
        print(f"{BROKEN_LINK} broken reference(s):\n")
        seen = set()
        for page, url in problems:
            key = (page, url)
            if key in seen:
                continue
            seen.add(key)
            print(f"  {page}  ->  {url}")
        return 1
    print("all local references resolve")
    return 0


if __name__ == "__main__":
    sys.exit(check())
