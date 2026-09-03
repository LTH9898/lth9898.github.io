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
- `images/logo.png` — favicon and footer logo
