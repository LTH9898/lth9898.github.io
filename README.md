# lth9898.github.io

Personal homepage, served at https://lth9898.github.io/.

Built with [Jekyll](https://jekyllrb.com/), which GitHub Pages runs
automatically on push — there is no build step to run yourself for a normal
content change.

## Credits

Adapted from [Xiuming Zhang's homepage](https://xiuming.info)
([source](https://github.com/xiumingzhang/xiumingzhang.github.io)), which is
modified from the [Read Only](https://html5up.net/read-only) template by
[HTML5 UP](https://html5up.net/), licensed under
[CC BY 3.0](https://creativecommons.org/licenses/by/3.0/).

## Writing a blog post

Add one Markdown file to `_posts/`, named `YYYY-MM-DD-slug.md`:

```markdown
---
title: "Flow Matching: velocity fields instead of score functions"
description: One line shown in the post list. Optional.
tags: [generative, flow-matching]
---

Your text here.
```

Commit and push. The post appears at `/blog/slug/`, in the full list at
`/blog/`, and — if it is among the four most recent — in the Blog section of
the home page. `_drafts/` holds unpublished posts; they are ignored unless you
build with `--drafts`.

What you can use in a post:

| Feature | How |
| --- | --- |
| Inline math | `$v_\theta(x_t, t)$` |
| Display math | `$$ ... $$` on its own lines |
| Code | Fenced block with a language, e.g. ` ```python ` |
| Images | Put files in `images/blog/<slug>/`, link as `/images/blog/<slug>/fig.png` |
| Tags | `tags: [a, b]` in the front matter; they become filters on `/blog/` |

Math is rendered by [KaTeX](https://katex.org/) in the browser; code is
highlighted at build time by [Rouge](https://github.com/rouge-ruby/rouge).

## Writing in Notion instead

Posts can also come from a Notion database, so notes written there land on the
blog without a copy-paste step. `tools/notion_sync.py` reads the database
through the Notion API and writes `_posts/YYYY-MM-DD-slug.md` plus any images,
and `.github/workflows/notion-sync.yml` runs it daily and on demand.

Notion's own `Export -> Markdown & CSV` is not used: it writes `$$...$$` for
inline math as well as display math, so inline formulas come out as centred
blocks, and its image links point at URLs that expire after an hour. The
script emits `$...$` inline and downloads every image into the repo.

### One-time setup

1. Create an internal integration at
   <https://www.notion.so/my-integrations> and copy its token.
2. Make a Notion database for posts with these properties:

   | Property | Type | Required | Meaning |
   | --- | --- | --- | --- |
   | `Name` | Title | yes | Post title |
   | `Publish` | Checkbox | yes | Only ticked pages sync |
   | `Date` | Date | no | Post date; defaults to the page's creation date |
   | `Tags` | Multi-select | no | Becomes `tags:` in the front matter |
   | `Description` | Text | no | One-line blurb in the post list |
   | `Slug` | Text | no | Overrides the slug derived from the title |

3. In the database's `...` menu, choose **Connections -> Connect to** and pick
   the integration. Without this the API cannot see the database.
4. Copy the database id -- in the database URL
   `notion.so/<workspace>/<database id>?v=...`, it is the 32-character part
   before the `?`.
5. Add two repository secrets under **Settings -> Secrets and variables ->
   Actions**: `NOTION_TOKEN` and `NOTION_DATABASE_ID`.

### Day to day

Write the note in Notion, tick `Publish`, and either wait for the daily run or
trigger **Actions -> Notion sync -> Run workflow**. Editing the page and
re-running updates the post in place; unticking `Publish` deletes it again.
Posts the script owns carry a `notion_page_id` in their front matter, and
hand-written posts without one are never touched.

Write math as Notion equations (`Ctrl+Shift+E` inline, or `/equation` for a
block) rather than typing dollar signs, so it converts cleanly. Callouts become
blockquotes and toggles become collapsible `<details>` sections.

To check the conversion before it reaches the site:

```bash
NOTION_TOKEN=... NOTION_DATABASE_ID=... python3 tools/notion_sync.py --dry-run
```

## Previewing locally

Optional — only needed if you want to see a post before pushing.

```bash
bundle install --path vendor/bundle
bundle exec jekyll serve --drafts --livereload
```

Then open http://localhost:4000.

## Where to edit

- `index.html` — home page content (About / News / Publications / Blog preview)
- `blog.html` — the `/blog/` post index and tag filter
- `_posts/` — published blog posts, `_drafts/` — unpublished ones
- `_layouts/`, `_includes/` — page shell, sidebar, footer, KaTeX loader
- `css/blog.css` — blog styling; `css/style.css` — the base template
- `images/avatars/profile.jpg` — profile photo
- `images/banners/banner.jpg` — home banner (referenced in `css/style.css`)
- `images/pub/` — paper teaser images, `images/blog/` — post images
- `docs/bib/` — BibTeX files
- `tools/notion_sync.py` — Notion → `_posts/` sync
- `images/logo.png` — favicon and footer logo
