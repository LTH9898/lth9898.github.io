#!/usr/bin/env python3
"""Turn a Notion database of notes into Jekyll posts under _posts/.

Each Notion page with `Publish` checked becomes `_posts/YYYY-MM-DD-slug.md`,
and every image it contains is downloaded into `images/blog/<slug>/`. Notion's
own file URLs expire after an hour, so linking them directly would leave the
post with dead images -- the bytes have to be committed alongside it.

The conversion targets this blog specifically rather than generic Markdown:
inline equations become `$...$` and block equations `$$...$$`, which is what
the KaTeX loader in _includes/katex.html expects. (Notion's built-in Markdown
export writes `$$` for both, so inline math comes out as centred blocks.)

Stdlib only, so it runs on the system Python without a virtualenv.

Usage:
    NOTION_TOKEN=secret_... NOTION_DATABASE_ID=... python3 tools/notion_sync.py
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
import time
import unicodedata
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone

API = "https://api.notion.com/v1"

# Pinned deliberately. Later versions moved database queries to data sources;
# this one keeps /databases/{id}/query working and Notion still supports it.
NOTION_VERSION = "2022-06-28"

# Notion allows ~3 requests/second. Posts are small, so just pace every call
# rather than tracking a budget.
REQUEST_INTERVAL = 0.34

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# Notion language names that Rouge does not know under the same spelling.
CODE_LANGUAGES = {
    "c++": "cpp",
    "c#": "csharp",
    "objective-c": "objc",
    "plain text": "text",
    "shell": "bash",
    "bash": "bash",
    "docker": "dockerfile",
    "f#": "fsharp",
    "vb.net": "vbnet",
    "java/c/c++/c#": "java",
}


# --------------------------------------------------------------------------
# Notion API
# --------------------------------------------------------------------------


class Notion:
    def __init__(self, token: str) -> None:
        self.token = token
        self._last_call = 0.0

    def _request(self, method: str, path: str, body=None):
        gap = REQUEST_INTERVAL - (time.monotonic() - self._last_call)
        if gap > 0:
            time.sleep(gap)

        data = json.dumps(body).encode() if body is not None else None
        req = urllib.request.Request(API + path, data=data, method=method)
        req.add_header("Authorization", "Bearer " + self.token)
        req.add_header("Notion-Version", NOTION_VERSION)
        req.add_header("Content-Type", "application/json")

        for attempt in range(5):
            try:
                with urllib.request.urlopen(req, timeout=60) as resp:
                    self._last_call = time.monotonic()
                    return json.loads(resp.read().decode())
            except urllib.error.HTTPError as err:
                self._last_call = time.monotonic()
                detail = err.read().decode(errors="replace")
                # 429 and 5xx are worth another try; 400/401/404 are not.
                if err.code not in (429, 500, 502, 503, 504) or attempt == 4:
                    raise SystemExit(
                        "Notion API %s %s failed (%s): %s"
                        % (method, path, err.code, detail)
                    )
                time.sleep(float(err.headers.get("Retry-After") or 2 ** attempt))
            except urllib.error.URLError as err:
                self._last_call = time.monotonic()
                if attempt == 4:
                    raise SystemExit("Notion API unreachable: %s" % err)
                time.sleep(2 ** attempt)

    def published_pages(self, database_id: str, publish_property: str):
        """Every page in the database with the publish checkbox ticked."""
        pages, cursor = [], None
        while True:
            body = {
                "page_size": 100,
                "filter": {
                    "property": publish_property,
                    "checkbox": {"equals": True},
                },
            }
            if cursor:
                body["start_cursor"] = cursor
            data = self._request("POST", "/databases/%s/query" % database_id, body)
            pages.extend(data.get("results", []))
            if not data.get("has_more"):
                return pages
            cursor = data.get("next_cursor")

    def children(self, block_id: str):
        blocks, cursor = [], None
        while True:
            query = "?page_size=100"
            if cursor:
                query += "&start_cursor=" + cursor
            data = self._request("GET", "/blocks/%s/children%s" % (block_id, query))
            blocks.extend(data.get("results", []))
            if not data.get("has_more"):
                return blocks
            cursor = data.get("next_cursor")


# --------------------------------------------------------------------------
# Page properties
# --------------------------------------------------------------------------


def plain(rich) -> str:
    return "".join(part.get("plain_text", "") for part in rich or [])


def read_property(page, name: str):
    return (page.get("properties") or {}).get(name)


def property_text(page, name: str) -> str:
    prop = read_property(page, name)
    if not prop:
        return ""
    kind = prop.get("type")
    if kind in ("title", "rich_text"):
        return plain(prop.get(kind)).strip()
    if kind == "select":
        return (prop.get("select") or {}).get("name", "")
    if kind == "url":
        return prop.get("url") or ""
    return ""


def property_tags(page, name: str):
    prop = read_property(page, name)
    if not prop:
        return []
    if prop.get("type") == "multi_select":
        return [opt["name"] for opt in prop.get("multi_select") or []]
    if prop.get("type") == "select":
        option = prop.get("select")
        return [option["name"]] if option else []
    return []


def property_date(page, name: str) -> str:
    """The post date, as YYYY-MM-DD, falling back to when the page was made."""
    prop = read_property(page, name)
    if prop and prop.get("type") == "date":
        start = (prop.get("date") or {}).get("start")
        if start:
            return start[:10]
    created = page.get("created_time", "")
    if created:
        return created[:10]
    return datetime.now(timezone.utc).strftime("%Y-%m-%d")


def clean_slug(text: str) -> str:
    """Make a value safe as a filename and a URL path segment.

    Non-Latin letters are kept rather than dropped: a Korean title would
    otherwise reduce to nothing, and percent-encoded Hangul in the URL still
    beats an opaque `post-1a2b3c4d`.
    """
    text = unicodedata.normalize("NFKC", text).strip().lower()
    text = re.sub(r"[\s/\\]+", "-", text)
    text = re.sub(r"[^\w\-]", "", text, flags=re.UNICODE)  # \w keeps `_`
    return re.sub(r"-{2,}", "-", text).strip("-")


def slugify(text: str) -> str:
    """A slug derived from a title, where `_` reads as a word break."""
    return clean_slug(re.sub(r"_+", "-", text))


def post_slug(filename: str) -> str:
    """Recover the slug from a `YYYY-MM-DD-slug.md` post filename."""
    name = re.sub(r"^\d{4}-\d{2}-\d{2}-", "", os.path.basename(filename))
    return os.path.splitext(name)[0]


def drop_image_dir(image_root: str, slug: str) -> None:
    directory = os.path.join(image_root, slug)
    if not os.path.isdir(directory):
        return
    for name in os.listdir(directory):
        os.remove(os.path.join(directory, name))
    os.rmdir(directory)


# --------------------------------------------------------------------------
# Rich text
# --------------------------------------------------------------------------

# Left alone: `$`, so a stray dollar sign stays readable, and KaTeX only fires
# on matched pairs anyway.
ESCAPE = re.compile(r"([\\`*_\[\]<])")

# Math typed as ordinary text rather than as a Notion equation. Escaping
# inside it would turn `$x_t$` into `$x\_t$` and break the KaTeX render.
MATH_SPAN = re.compile(r"\$[^$\n]+\$")

LIST_KINDS = ("bulleted_list_item", "numbered_list_item", "to_do")
LIST_MARKER = re.compile(r"^(?:[-*+]\s|\d+\.\s)")


def escape_text(text: str) -> str:
    out, last = [], 0
    for match in MATH_SPAN.finditer(text):
        out.append(ESCAPE.sub(r"\\\1", text[last:match.start()]))
        out.append(match.group(0))
        last = match.end()
    out.append(ESCAPE.sub(r"\\\1", text[last:]))
    return "".join(out)


def rich_to_md(rich) -> str:
    out = []
    for part in rich or []:
        kind = part.get("type")

        if kind == "equation":
            expression = (part.get("equation") or {}).get("expression", "").strip()
            # Inline math -- single dollars, unlike Notion's own export.
            out.append("$%s$" % expression if expression else "")
            continue

        text = part.get("plain_text", "")
        if not text:
            continue

        annotations = part.get("annotations") or {}
        if annotations.get("code"):
            # Backticks inside a code span need a longer fence.
            fence = "`" * (max(len(m) for m in re.findall(r"`+", text)) + 1
                           if "`" in text else 1)
            pad = " " if text.startswith("`") or text.endswith("`") else ""
            text = fence + pad + text + pad + fence
        else:
            text = escape_text(text)
            if annotations.get("bold"):
                text = "**%s**" % text
            if annotations.get("italic"):
                text = "*%s*" % text
            if annotations.get("strikethrough"):
                text = "~~%s~~" % text
            if annotations.get("underline"):
                text = "<u>%s</u>" % text

        href = part.get("href")
        if href:
            text = "[%s](%s)" % (text, href)
        out.append(text)

    return "".join(out).strip()


# --------------------------------------------------------------------------
# Blocks -> Markdown
# --------------------------------------------------------------------------


class Converter:
    def __init__(self, notion: Notion, slug: str, image_dir: str, dry_run: bool):
        self.notion = notion
        self.slug = slug
        self.image_dir = image_dir
        self.dry_run = dry_run
        self.images = []  # filenames written, in document order

    # -- images ---------------------------------------------------------

    def save_image(self, url: str, block_id: str) -> str:
        """Download an image next to the post and return its site-root path."""
        name = os.path.basename(urllib.parse.urlparse(url).path)
        name = urllib.parse.unquote(name)
        stem, ext = os.path.splitext(name)
        stem = slugify(stem) or "image"
        if not ext or len(ext) > 6:
            ext = ".png"
        filename = "%02d-%s%s" % (len(self.images) + 1, stem, ext)
        target = os.path.join(self.image_dir, filename)

        if not self.dry_run:
            os.makedirs(self.image_dir, exist_ok=True)
            try:
                request = urllib.request.Request(
                    url, headers={"User-Agent": "notion-sync"}
                )
                with urllib.request.urlopen(request, timeout=120) as resp:
                    payload = resp.read()
                with open(target, "wb") as handle:
                    handle.write(payload)
            except (urllib.error.URLError, OSError) as err:
                print("  ! image download failed (%s): %s" % (block_id, err))
                return url  # keep the post building; the link will rot

        self.images.append(filename)
        return "/images/blog/%s/%s" % (self.slug, filename)

    # -- blocks ---------------------------------------------------------

    def children_of(self, block) -> list:
        if not block.get("has_children"):
            return []
        return self.notion.children(block["id"])

    def convert(self, blocks, indent: str = "") -> list:
        """Render a list of sibling blocks into Markdown lines."""
        lines = []
        number = 0

        for index, block in enumerate(blocks):
            kind = block.get("type")
            body = block.get(kind) or {}
            number = number + 1 if kind == "numbered_list_item" else 0
            following = blocks[index + 1].get("type") if index + 1 < len(blocks) else None

            if kind == "paragraph":
                text = rich_to_md(body.get("rich_text"))
                if text:
                    lines.append(indent + text)
                    lines.append("")
                lines.extend(self.convert(self.children_of(block), indent))

            elif kind in ("heading_1", "heading_2", "heading_3"):
                level = "#" * (int(kind[-1]) + 1)  # h1 in Notion -> ## here,
                text = rich_to_md(body.get("rich_text"))  # the post title is h1
                if text:
                    lines.append("%s %s" % (level, text))
                    lines.append("")
                lines.extend(self.convert(self.children_of(block), indent))

            elif kind in ("bulleted_list_item", "numbered_list_item", "to_do"):
                if kind == "numbered_list_item":
                    marker = "%d. " % number
                elif kind == "to_do":
                    marker = "- [x] " if body.get("checked") else "- [ ] "
                else:
                    marker = "- "
                text = rich_to_md(body.get("rich_text"))
                lines.append(indent + marker + text)

                nested = self.convert(self.children_of(block), indent + " " * len(marker))
                while nested and nested[-1] == "":
                    nested.pop()
                if nested and not LIST_MARKER.match(nested[0].strip()):
                    # An indented paragraph needs the blank line, or Markdown
                    # folds it back into the item's own text.
                    nested.insert(0, "")
                lines.extend(nested)

                if following not in LIST_KINDS:
                    lines.append("")

            elif kind == "toggle":
                summary = rich_to_md(body.get("rich_text"))
                # markdown="1" so kramdown still parses the body inside the tag.
                lines.append(indent + '<details markdown="1">')
                lines.append(indent + "<summary>%s</summary>" % summary)
                lines.append("")
                lines.extend(self.convert(self.children_of(block), indent))
                lines.append(indent + "</details>")
                lines.append("")

            elif kind in ("quote", "callout"):
                text = rich_to_md(body.get("rich_text"))
                if kind == "callout":
                    icon = (body.get("icon") or {}).get("emoji")
                    if icon:
                        text = "%s %s" % (icon, text)
                quoted = [text]
                inner = self.convert(self.children_of(block))
                while inner and inner[-1] == "":
                    inner.pop()
                if inner:
                    quoted.append("")
                    quoted.extend(inner)
                for line in quoted:
                    lines.append((indent + "> " + line).rstrip())
                lines.append("")

            elif kind == "code":
                language = (body.get("language") or "").lower()
                language = CODE_LANGUAGES.get(language, language).replace(" ", "")
                source = plain(body.get("rich_text")).rstrip("\n")
                runs = [len(run) for run in re.findall(r"`+", source)]
                fence = "`" * max([3] + [longest + 1 for longest in runs])
                lines.append(indent + fence + language)
                lines.extend(indent + line for line in source.split("\n"))
                lines.append(indent + fence)
                lines.append("")
                caption = rich_to_md(body.get("caption"))
                if caption:
                    lines.append(indent + "*%s*" % caption)
                    lines.append("")

            elif kind == "equation":
                expression = (body.get("expression") or "").strip()
                lines.append(indent + "$$")
                lines.extend(indent + line for line in expression.split("\n"))
                lines.append(indent + "$$")
                lines.append("")

            elif kind == "image":
                source = body.get(body.get("type"), {}) or {}
                url = source.get("url", "")
                if url:
                    alt = rich_to_md(body.get("caption")) or ""
                    path = self.save_image(url, block["id"])
                    lines.append(indent + "![%s](%s)" % (alt, path))
                    lines.append("")

            elif kind in ("video", "file", "pdf", "bookmark", "embed", "link_preview"):
                source = body.get(body.get("type"), body) or {}
                url = source.get("url") or body.get("url") or ""
                if url:
                    label = rich_to_md(body.get("caption")) or url
                    lines.append(indent + "[%s](%s)" % (label, url))
                    lines.append("")

            elif kind == "divider":
                lines.append(indent + "---")
                lines.append("")

            elif kind == "table":
                lines.extend(self.convert_table(block, indent))

            elif kind in ("column_list", "column", "synced_block"):
                # No column layout in the post template; flatten to one flow.
                lines.extend(self.convert(self.children_of(block), indent))

            elif kind in ("table_of_contents", "breadcrumb", "child_page",
                          "child_database", "unsupported"):
                continue

            else:
                text = rich_to_md(body.get("rich_text"))
                if text:
                    lines.append(indent + text)
                    lines.append("")
                lines.extend(self.convert(self.children_of(block), indent))

        return lines

    def convert_table(self, block, indent: str) -> list:
        rows = [r for r in self.children_of(block) if r.get("type") == "table_row"]
        if not rows:
            return []
        body = block.get("table") or {}
        cells = [
            # A pipe inside a cell would end the column early.
            [(rich_to_md(cell) or " ").replace("|", "\\|")
             for cell in (row["table_row"].get("cells") or [])]
            for row in rows
        ]
        width = max(len(row) for row in cells)
        cells = [row + [" "] * (width - len(row)) for row in cells]

        if body.get("has_column_header"):
            header, rest = cells[0], cells[1:]
        else:
            header, rest = [" "] * width, cells

        lines = [indent + "| " + " | ".join(header) + " |",
                 indent + "| " + " | ".join(["---"] * width) + " |"]
        lines.extend(indent + "| " + " | ".join(row) + " |" for row in rest)
        lines.append("")
        return lines


# --------------------------------------------------------------------------
# Writing posts
# --------------------------------------------------------------------------

FRONT_MATTER = re.compile(r"\A---\n(.*?)\n---\n", re.DOTALL)


def yaml_string(value: str) -> str:
    return '"%s"' % value.replace("\\", "\\\\").replace('"', '\\"')


def front_matter_value(text: str, key: str) -> str:
    match = FRONT_MATTER.match(text)
    if not match:
        return ""
    found = re.search(r"^%s:\s*(.*)$" % re.escape(key), match.group(1), re.MULTILINE)
    return found.group(1).strip() if found else ""


def build_post(page, options, notion: Notion, image_root: str, dry_run: bool):
    """Render one Notion page. Returns (filename, text, slug, images)."""
    title = property_text(page, options.title_property) or "Untitled"
    slug = clean_slug(property_text(page, options.slug_property)) or slugify(title)
    if not slug:
        slug = "post-" + page["id"].replace("-", "")[:8]
    date = property_date(page, options.date_property)

    image_dir = os.path.join(image_root, slug)
    converter = Converter(notion, slug, image_dir, dry_run)
    body = converter.convert(notion.children(page["id"]))

    while body and body[-1] == "":
        body.pop()

    head = [
        "---",
        "title: " + yaml_string(title),
    ]
    description = property_text(page, options.description_property)
    if description:
        head.append("description: " + yaml_string(description))
    tags = property_tags(page, options.tags_property)
    if tags:
        head.append("tags: [%s]" % ", ".join(tags))
    # Ownership markers: they tell a later run which files came from Notion and
    # whether the source has changed since.
    head.append("notion_page_id: " + page["id"])
    head.append("notion_last_edited: " + page.get("last_edited_time", ""))
    head.append("---")
    head.append("")

    text = "\n".join(head + body).rstrip("\n") + "\n"
    return "%s-%s.md" % (date, slug), text, slug, converter.images


def owned_posts(posts_dir: str):
    """Existing posts this script wrote, keyed by Notion page id."""
    owned = {}
    if not os.path.isdir(posts_dir):
        return owned
    for name in sorted(os.listdir(posts_dir)):
        if not name.endswith((".md", ".markdown")):
            continue
        path = os.path.join(posts_dir, name)
        with open(path, encoding="utf-8") as handle:
            head = handle.read(4096)
        page_id = front_matter_value(head, "notion_page_id")
        if page_id:
            owned[page_id] = path
    return owned


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--database", default=os.environ.get("NOTION_DATABASE_ID"),
                        help="Notion database id (or NOTION_DATABASE_ID)")
    parser.add_argument("--posts-dir", default=os.path.join(REPO, "_posts"))
    parser.add_argument("--image-root", default=os.path.join(REPO, "images", "blog"))
    parser.add_argument("--title-property", default="Name")
    parser.add_argument("--slug-property", default="Slug")
    parser.add_argument("--description-property", default="Description")
    parser.add_argument("--tags-property", default="Tags")
    parser.add_argument("--date-property", default="Date")
    parser.add_argument("--publish-property", default="Publish")
    parser.add_argument("--force", action="store_true",
                        help="rewrite posts even when Notion reports no edits")
    parser.add_argument("--keep-unpublished", action="store_true",
                        help="leave posts in place after their page is unpublished")
    parser.add_argument("--dry-run", action="store_true",
                        help="report what would change, write nothing")
    options = parser.parse_args()

    token = os.environ.get("NOTION_TOKEN")
    if not token:
        print("NOTION_TOKEN is not set", file=sys.stderr)
        return 2
    if not options.database:
        print("no database id: pass --database or set NOTION_DATABASE_ID",
              file=sys.stderr)
        return 2

    notion = Notion(token)
    database = options.database.replace("-", "")
    pages = notion.published_pages(database, options.publish_property)
    print("%d published page(s)" % len(pages))

    existing = owned_posts(options.posts_dir)
    seen, changed = set(), 0

    for page in pages:
        page_id = page["id"]
        seen.add(page_id)
        title = property_text(page, options.title_property) or "Untitled"
        previous = existing.get(page_id)

        if previous and not options.force:
            with open(previous, encoding="utf-8") as handle:
                stamp = front_matter_value(handle.read(4096), "notion_last_edited")
            if stamp == page.get("last_edited_time"):
                print("  = %s (unchanged)" % os.path.basename(previous))
                continue

        filename, text, slug, images = build_post(
            page, options, notion, options.image_root, options.dry_run
        )
        path = os.path.join(options.posts_dir, filename)

        if previous and os.path.abspath(previous) != os.path.abspath(path):
            # The title or date moved, so the old filename would 404 alongside
            # the new one.
            print("  - %s (renamed)" % os.path.basename(previous))
            if not options.dry_run:
                os.remove(previous)
                stale = post_slug(previous)
                if stale != slug:
                    drop_image_dir(options.image_root, stale)

        verb = "+" if not previous else "~"
        print("  %s %s  (%s, %d image(s))" % (verb, filename, title, len(images)))
        changed += 1

        if options.dry_run:
            continue

        os.makedirs(options.posts_dir, exist_ok=True)
        with open(path, "w", encoding="utf-8") as handle:
            handle.write(text)

        # Drop images from an earlier version of this same post.
        directory = os.path.join(options.image_root, slug)
        if os.path.isdir(directory):
            for name in os.listdir(directory):
                if name not in images:
                    os.remove(os.path.join(directory, name))

    for page_id, path in existing.items():
        if page_id in seen:
            continue
        print("  - %s (unpublished in Notion)" % os.path.basename(path))
        changed += 1
        if options.keep_unpublished or options.dry_run:
            continue
        os.remove(path)
        drop_image_dir(options.image_root, post_slug(path))

    print("%d post(s) changed" % changed)
    return 0


if __name__ == "__main__":
    sys.exit(main())
