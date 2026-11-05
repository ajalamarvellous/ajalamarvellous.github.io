# ajalamarvellous.github.io

A minimalist personal academic site. Static HTML generated from plain text
sources — no Jekyll, no Node, no third-party Python packages.

```
content/
  site.json        identity, links, contact          ← edit this
  papers.bib       publications                        ← edit this
  news/            dated announcements, one file each   ← add a file
  projects.json    projects, with markdown bodies      ← edit this
                    (each also gets its own page at /projects/<slug>.html)
  posts/           blog posts, markdown + front matter ← edit this
templates/base.html   page shell
static/
  style.css        all styling
  img/             images
  pdf/             CV
md.py              markdown renderer
pdflite.py         minimal PDF writer (for papers.pdf)
build.py           the generator
check.py           link checker — run it after every build
public/            generated output — this is what you deploy
```

## Build

```bash
python3 build.py            # writes public/
python3 build.py --watch    # rebuilds on every save
python3 check.py            # verifies every local link and image resolves
python3 -m http.server 8731 --directory public
```

`check.py` is worth running every time. It catches the classic failure here:
an image referenced by a post that no longer exists in `static/img/`.

## Deploy

```bash
./deploy.sh --dry-run       # preview
./deploy.sh                 # build, sync into the repo, commit, push
```

Set `REPO=` and `BRANCH=` if they differ from the defaults. The repo is a
Jekyll site today; the script replaces its contents with `public/`. The old
site stays in git history, and the first commit is a single `git revert`
away from restoring it.

Alternatively, keep the old repo and run the build in CI — copy `content/`,
`templates/`, `static/`, `md.py`, `pdflite.py` and `build.py` into it and add
a GitHub Actions job that publishes `public/` to Pages.

**Note:** internal links are root-relative (`/blog/`), so the site must be
served from the domain root. That is the case for a GitHub Pages *user* site
(`ajalamarvellous.github.io`). If you move it to a subpath, or to a custom
domain with a base path, prefix the links in `build.py` and `site.json`.

## Adding a post

Drop a markdown file into `content/posts/` and rebuild. That is all — the
post page, the blog index, the front page, the feed, the sitemap and the
reading time all update themselves.

```markdown
---
title: "Lessons From Failure"
date: 2025-01-11 17:00:00
description: essay
tags: personal
categories: life
thumbnail: img/lessons-from-failure-cover.jpg
---

The body, in markdown.
```

- `title` and `date` are the only required fields.
- `date` drives ordering, the URL and the reading time.
- The URL is derived automatically, Jekyll-style: a file called
  `2026-10-20-my-post.md` is published at `/blog/2026/my-post.html`. The
  subdirectory the file sits in does not matter.
- `description` is the standfirst. If it is generic ("essay", "review") an
  excerpt is generated from the opening of the post instead.
- `thumbnail` is the image shown in listings. Optional.
- `url` overrides the derived URL if you want a different one.

## Adding a news item

Same idea: drop a file into `content/news/`.

```markdown
---
date: "2026-10-22"
---

We are hosting a **journal club** on 28 October. [Link](https://luma.com/...)
```

Only the date is required. News is sorted newest-first, and the five most
recent appear on the front page. The body can use the full markdown subset.

Images live in `static/img/` and are referenced from the markdown as
`img/name.jpg`. The renderer rewrites that to a root-relative path so it
resolves from any depth.

**Supported markdown:** paragraphs, `#` headings, `>` blockquotes, `-` and
`1.` lists, `- [x]` task lists, fenced code blocks, `---` rules, `![alt](src)`
images (the alt text becomes the caption), `[text](url)` links, `**bold**`,
`*italic*`, `` `code` ``, and raw HTML.

## Writing your `.bib`

Standard BibTeX, plus these fields:

| field         | effect                                                      |
|---------------|-------------------------------------------------------------|
| `selected`    | `true` puts the entry in the "Selected work" list on the front page |
| `abbr`        | short venue label, used instead of `booktitle`/`journal`     |
| `status`      | rendered as a badge — e.g. "Under review"                    |
| `pdf`         | adds a **PDF** link and makes the title itself a link        |
| `code`        | adds a **Code** link                                         |
| `abstract`    | shown behind a `+` toggle, expanded in place                 |
| `note`        | rendered as a badge — e.g. "Best Paper Award"                |
| `supervisor`  | shown for theses                                             |
| `authorraw`   | author string used verbatim, for very long author lists      |

Author names in `Last, First` form are rewritten to `First Last`, and your
own name (listed in `owner_names` in `site.json`) is bolded. LaTeX accents,
`--`, `{}`, `\emph{}` and `\ldots` are cleaned up automatically.

`papers.pdf` is generated from the same `.bib` by `pdflite.py`.

## Customising

**Colours and type** are CSS custom properties at the top of
`static/style.css`:

```
--paper  --ink  --muted  --rule  --accent  --wash
```

**Type scale.** Every size on the site is in `rem`, and `rem` follows the
root font-size set in `static/style.css`:

```css
html { font-size: 87.5%; }   /* the whole site scales from here */
```

Set it to `100%` for the full-size version, or lower it for a denser one.
Using a percentage rather than `14px` means the reader's own browser
font-size preference still applies — the whole site scales with it.

At the current root, `1rem` is exactly 14px. Body copy, the one-liner, paper
titles and post prose are all set to `1rem`, so they are 14px and they move
together if you change the root:

```css
body, .prose, .line, .paper-title { font-size: 1rem; }
```

The nav is pinned at 11px, which does not move with the root:

```css
.nav { font-size: 0.786rem; }
```

**Column width** is set in `rem`, not `ch`, so that changing the body font
size can never change the width of the page column:

```css
--measure: 47.14rem;   /* 660px */
```

If you want the column wider still, raise that number.

**Fonts.** The default is a system serif stack (Iowan Old Style, Charter,
Sitka, Cambria, Georgia…). To pin the look everywhere, self-host Source
Serif 4 (SIL OFL) and put it first in `--serif`. Do not link Google Fonts —
it costs a request per visit and leaks your readers.

**Dark mode** follows `prefers-color-scheme`; the button in the top right
pins it to one mode and remembers the choice.

**Printing.** `Cmd-P` gives a clean PDF: every paper listed, links spelled
out as URLs, images dropped.

## Old URLs

The Jekyll site used `/blog/:year/:title/`. Those paths still work — the
build writes redirect stubs for each of them. If you delete a post, keep its
stub in `REDIRECTS` in `build.py` or the old link will 404.

## What updates itself on a build

| you add | and it appears in |
|---|---|
| `content/posts/*.md` | the post page, blog index, front page, `feed.xml`, `sitemap.xml` |
| `content/news/*.md` | the news page and the front page's recent list |
| `content/papers.bib` | front page, bibliography page, `papers.pdf` |
| `content/site.json` | every page |
| `content/projects.json` | the projects page |

Nothing else needs editing. There is no index file to keep in sync.

## Things worth adding later, in this order

1. A second domain (`ajalamarvellous.xyz` is referenced in some of the older
   posts — the `CNAME` file is currently empty).
2. `pagefind` client-side search, once you are past ~15 publications.
3. A page for talks and teaching, if they earn one.
4. An OG image for link previews — the posts currently share one.

## Things not worth adding

Analytics, a cookie banner, a logo, a slideshow, a comment system, "tags" on
papers, an auto-updating publication count. Each one costs attention and
returns nothing.
