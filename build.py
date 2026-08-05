from __future__ import annotations

import html
import json
import re
import shutil
from dataclasses import dataclass, field
from datetime import date, datetime
from pathlib import Path
from typing import Iterable
import tomllib


ROOT = Path(__file__).parent
CONTENT_DIR = ROOT / "content"
POSTS_DIR = CONTENT_DIR / "posts"
STATIC_DIR = ROOT / "static"
OUTPUT_DIR = ROOT / "dist"
SITE_CONFIG_PATH = ROOT / "site.toml"

# Redirect slugs become directories under dist/, so keep them to plain path
# segments — no '..', no absolute paths, nothing that escapes the output tree.
REDIRECT_SLUG_PATTERN = re.compile(r"[a-z0-9_-]+(?:/[a-z0-9_-]+)*")


@dataclass
class Page:
    source_path: Path
    title: str
    slug: str
    body: str
    description: str = ""
    image_path: str = ""
    image_alt: str = ""
    redirects: list[str] = field(default_factory=list)

    @property
    def current_path(self) -> str:
        return "/" if self.slug == "" else f"/{self.slug}/"

    @property
    def output_path(self) -> str:
        return "index.html" if self.slug == "" else f"{self.slug}/index.html"

    def redirect_paths(self) -> list[str]:
        return [f"/{slug}/" for slug in self.redirects]


@dataclass
class Post:
    source_path: Path
    title: str
    slug: str
    published_on: date
    summary: str
    body: str
    image_path: str = ""
    image_alt: str = ""
    redirects: list[str] = field(default_factory=list)

    @property
    def current_path(self) -> str:
        return f"/posts/{self.slug}/"

    def redirect_paths(self) -> list[str]:
        return [f"/posts/{slug}/" for slug in self.redirects]


def load_site_config() -> dict:
    with SITE_CONFIG_PATH.open("rb") as handle:
        return tomllib.load(handle)


def parse_content_file(path: Path) -> tuple[dict, str]:
    text = path.read_text(encoding="utf-8").strip()
    if not text.startswith("+++"):
        return {}, text

    _, rest = text.split("+++\n", 1)
    frontmatter, body = rest.split("\n+++\n", 1)
    metadata = tomllib.loads(frontmatter)
    return metadata, body.strip()


def slugify(value: str) -> str:
    normalized = re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")
    return normalized or "post"


def load_redirect_slugs(metadata: dict, source_path: Path) -> list[str]:
    raw = metadata.get("redirects", [])
    if isinstance(raw, str):
        raw = [raw]
    if not isinstance(raw, list):
        raise ValueError(
            f"{source_path}: 'redirects' must be a string or a list of strings"
        )

    slugs: list[str] = []
    for entry in raw:
        if not isinstance(entry, str):
            raise ValueError(f"{source_path}: every 'redirects' entry must be a string")
        slug = entry.strip().strip("/")
        if not slug:
            raise ValueError(f"{source_path}: 'redirects' entries cannot be empty")
        if not REDIRECT_SLUG_PATTERN.fullmatch(slug):
            raise ValueError(
                f"{source_path}: redirect '{entry}' is not a valid path — use "
                "lowercase letters, numbers, dashes, and underscores, optionally "
                "separated by '/'"
            )
        if slug not in slugs:
            slugs.append(slug)
    return slugs


def render_inline(text: str) -> str:
    escaped = html.escape(text, quote=False)
    escaped = re.sub(
        r"!\[([^\]]*)\]\(([^)]+)\)",
        lambda match: (
            f'<img src="{html.escape(match.group(2), quote=True)}" '
            f'alt="{html.escape(match.group(1), quote=True)}">'
        ),
        escaped,
    )
    escaped = re.sub(
        r"`([^`]+)`",
        lambda match: f"<code>{html.escape(match.group(1), quote=False)}</code>",
        escaped,
    )
    escaped = re.sub(
        r"\[([^\]]+)\]\(([^)]+)\)",
        lambda match: (
            f'<a href="{html.escape(match.group(2), quote=True)}">'
            f"{match.group(1)}</a>"
        ),
        escaped,
    )
    escaped = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", escaped)
    escaped = re.sub(r"\*([^*]+)\*", r"<em>\1</em>", escaped)
    return escaped


def flush_paragraph(buffer: list[str], parts: list[str]) -> None:
    if not buffer:
        return
    paragraph = " ".join(line.strip() for line in buffer)
    parts.append(f"<p>{render_inline(paragraph)}</p>")
    buffer.clear()


def markdown_to_html(text: str) -> str:
    lines = text.splitlines()
    parts: list[str] = []
    paragraph_buffer: list[str] = []
    in_code_block = False
    code_lines: list[str] = []
    code_language = ""
    in_list = False
    list_tag = ""
    in_blockquote = False
    blockquote_lines: list[str] = []

    def close_list() -> None:
        nonlocal in_list, list_tag
        if in_list:
            parts.append(f"</{list_tag}>")
            in_list = False
            list_tag = ""

    def close_blockquote() -> None:
        nonlocal in_blockquote
        if in_blockquote:
            quote_html = markdown_to_html("\n".join(blockquote_lines))
            parts.append(f"<blockquote>{quote_html}</blockquote>")
            blockquote_lines.clear()
            in_blockquote = False

    for line in lines:
        stripped = line.strip()

        if stripped.startswith("```"):
            close_blockquote()
            flush_paragraph(paragraph_buffer, parts)
            close_list()
            if in_code_block:
                language_attr = (
                    f' class="language-{html.escape(code_language, quote=True)}"'
                    if code_language
                    else ""
                )
                code_html = html.escape("\n".join(code_lines))
                parts.append(f"<pre><code{language_attr}>{code_html}</code></pre>")
                in_code_block = False
                code_lines.clear()
                code_language = ""
            else:
                in_code_block = True
                code_language = stripped.removeprefix("```").strip()
            continue

        if in_code_block:
            code_lines.append(line)
            continue

        if stripped.startswith(">"):
            flush_paragraph(paragraph_buffer, parts)
            close_list()
            in_blockquote = True
            blockquote_lines.append(stripped.removeprefix(">").lstrip())
            continue

        close_blockquote()

        if not stripped:
            flush_paragraph(paragraph_buffer, parts)
            close_list()
            continue

        paragraph_class_match = re.match(r"^\{:\s*\.([A-Za-z0-9_-]+)\s*\}$|^\{\.([A-Za-z0-9_-]+)\}$", stripped)
        if paragraph_class_match:
            flush_paragraph(paragraph_buffer, parts)
            if parts and parts[-1].startswith("<p>"):
                class_name = paragraph_class_match.group(1) or paragraph_class_match.group(2)
                parts[-1] = parts[-1].replace("<p>", f'<p class="{html.escape(class_name, quote=True)}">', 1)
            continue

        heading_match = re.match(r"^(#{1,6})\s+(.+)$", stripped)
        if heading_match:
            flush_paragraph(paragraph_buffer, parts)
            close_list()
            level = len(heading_match.group(1))
            parts.append(f"<h{level}>{render_inline(heading_match.group(2))}</h{level}>")
            continue

        unordered_match = re.match(r"^[-*]\s+(.+)$", stripped)
        ordered_match = re.match(r"^\d+\.\s+(.+)$", stripped)
        if unordered_match or ordered_match:
            flush_paragraph(paragraph_buffer, parts)
            next_tag = "ul" if unordered_match else "ol"
            if not in_list:
                in_list = True
                list_tag = next_tag
                parts.append(f"<{list_tag}>")
            elif list_tag != next_tag:
                close_list()
                in_list = True
                list_tag = next_tag
                parts.append(f"<{list_tag}>")
            item_text = unordered_match.group(1) if unordered_match else ordered_match.group(1)
            parts.append(f"<li>{render_inline(item_text)}</li>")
            continue

        paragraph_buffer.append(line)

    close_blockquote()
    flush_paragraph(paragraph_buffer, parts)
    close_list()
    return "\n".join(parts)


def load_page(path: Path) -> Page:
    metadata, body = parse_content_file(path)
    default_slug = path.stem if path.stem != "index" else ""
    slug = metadata.get("slug", default_slug)
    return Page(
        source_path=path,
        title=metadata.get("title", path.stem.replace("-", " ").title()),
        slug=slug,
        body=body,
        description=metadata.get("description", ""),
        image_path=metadata.get("image", ""),
        image_alt=metadata.get("image_alt", ""),
        redirects=load_redirect_slugs(metadata, path),
    )


def load_pages() -> list[Page]:
    pages = [load_page(path) for path in sorted(CONTENT_DIR.glob("*.md"))]
    pages.sort(key=lambda page: (page.slug != "", page.slug))
    return pages


def load_posts() -> list[Post]:
    posts: list[Post] = []
    for path in sorted(POSTS_DIR.glob("*.md")):
        metadata, body = parse_content_file(path)
        published_on = datetime.strptime(metadata["date"], "%Y-%m-%d").date()
        slug = metadata.get("slug", slugify(metadata["title"]))
        posts.append(
            Post(
                source_path=path,
                title=metadata["title"],
                slug=slug,
                published_on=published_on,
                summary=metadata.get("summary", ""),
                body=body,
                image_path=metadata.get("image", ""),
                image_alt=metadata.get("image_alt", ""),
                redirects=load_redirect_slugs(metadata, path),
            )
        )
    posts.sort(key=lambda post: post.published_on, reverse=True)
    return posts


def nav_html(current_path: str, pages: list[Page]) -> str:
    links = [("/", "Home"), ("/writing/", "Writing")]
    links.extend(
        (page.current_path, page.title) for page in pages if page.slug != ""
    )
    items = []
    for href, label in links:
        class_name = ' class="active"' if href == current_path else ""
        items.append(f'<a href="{href}"{class_name}>{label}</a>')
    return "\n".join(items)


def image_dimensions(asset_path: str) -> tuple[int, int] | None:
    """Read (width, height) from a PNG or JPEG header, or None if unreadable."""
    if not asset_path.startswith("/assets/"):
        return None
    path = STATIC_DIR / asset_path[len("/assets/") :]
    try:
        data = path.read_bytes()
    except OSError:
        return None

    if data[:8] == b"\x89PNG\r\n\x1a\n":
        width = int.from_bytes(data[16:20], "big")
        height = int.from_bytes(data[20:24], "big")
        return (width, height) if width and height else None

    if data[:2] == b"\xff\xd8":
        i = 2
        while i + 9 < len(data) and data[i] == 0xFF:
            marker, size = data[i + 1], int.from_bytes(data[i + 2 : i + 4], "big")
            # Start-of-frame markers carry the dimensions; skip the rest.
            if marker in {*range(0xC0, 0xC4), *range(0xC5, 0xC8), *range(0xC9, 0xCC)}:
                height = int.from_bytes(data[i + 5 : i + 7], "big")
                width = int.from_bytes(data[i + 7 : i + 9], "big")
                return (width, height) if width and height else None
            i += 2 + size
    return None


def twitter_card(image_path: str) -> str:
    """Large cards crop to roughly 1.91:1, so only use one on a wide image."""
    if not image_path:
        return "summary"
    size = image_dimensions(image_path)
    if size is None:
        return "summary_large_image"
    width, height = size
    return "summary_large_image" if width >= height * 1.4 else "summary"


def social_title(*, site: dict, title: str, page_title: str, kind: str) -> str:
    """Headline used in link previews.

    Posts share under their bare title. Networks already show the source
    separately, and og:site_name carries it, so the " | Ian McCrystal"
    suffix that suits a browser tab just eats headline room in a card.
    """
    return title if kind == "article" else page_title


def social_tags(
    *,
    site: dict,
    title: str,
    summary: str,
    current_path: str,
    image_path: str,
    image_alt: str,
    kind: str,
) -> str:
    """Open Graph and Twitter card tags for link previews.

    Scrapers do not resolve relative URLs, so every href here is absolute.
    """
    tags = [
        ("og:type", kind),
        ("og:site_name", site["name"]),
        ("og:title", title),
        ("og:description", summary),
        ("og:url", site["url"] + current_path),
    ]
    if image_path:
        tags.append(("og:image", site["url"] + image_path))
        if image_alt:
            tags.append(("og:image:alt", image_alt))

    lines = [
        f'<meta property="{name}" content="{html.escape(value, quote=True)}">'
        for name, value in tags
    ]
    named = [
        ("twitter:card", twitter_card(image_path)),
        ("twitter:title", title),
        ("twitter:description", summary),
    ]
    if image_path:
        named.append(("twitter:image", site["url"] + image_path))
        if image_alt:
            named.append(("twitter:image:alt", image_alt))
    lines.extend(
        f'<meta name="{name}" content="{html.escape(value, quote=True)}">'
        for name, value in named
    )
    return "\n    ".join(lines)


def site_shell(
    *,
    site: dict,
    pages: list[Page],
    title: str,
    description: str,
    current_path: str,
    content: str,
    image_path: str = "",
    image_alt: str = "",
    kind: str = "website",
) -> str:
    page_title = title if title == site["name"] else f"{title} | {site['name']}"
    summary = description or site["description"]
    social = social_tags(
        site=site,
        title=social_title(site=site, title=title, page_title=page_title, kind=kind),
        summary=summary,
        current_path=current_path,
        image_path=image_path,
        image_alt=image_alt,
        kind=kind,
    )
    return f"""<!DOCTYPE html>
<html lang="en">
  <head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <title>{html.escape(page_title)}</title>
    <meta name="description" content="{html.escape(summary, quote=True)}">
    <link rel="stylesheet" href="/assets/style.css">
    <link rel="icon" type="image/png" sizes="32x32" href="/assets/favicon-32.png">
    <link rel="icon" type="image/png" sizes="16x16" href="/assets/favicon-16.png">
    <link rel="apple-touch-icon" href="/assets/apple-touch-icon.png">
    <link rel="canonical" href="{html.escape(site['url'] + current_path, quote=True)}">
    {social}
  </head>
  <body>
    <div class="page">
      <header class="site-header">
        <a class="site-title" href="/">{html.escape(site["name"])}</a>
        <nav>
          {nav_html(current_path, pages)}
        </nav>
      </header>
      <main>
        {content}
      </main>
      <footer class="site-footer">
        <p>{html.escape(site["footer"])}</p>
      </footer>
    </div>
    <script>
    (function () {{
      var IMAGE_W = 1365, IMAGE_H = 2048;
      var EYES = {{
        left:  {{ x: 558 / IMAGE_W, y: 927 / IMAGE_H }},
        right: {{ x: 778 / IMAGE_W, y: 930 / IMAGE_H }}
      }};
      var IRIS_SIZE = 32;
      var MAX_MOVE = 1;
      var wrap = document.querySelector(".headshot-wrap");
      if (!wrap) return;
      var pupils = wrap.querySelectorAll(".headshot-pupil");
      if (!pupils.length || !window.matchMedia("(hover: hover) and (pointer: fine)").matches) return;

      function imgToFrac(ix, iy) {{
        var rect = wrap.getBoundingClientRect();
        var scale = Math.max(rect.width / IMAGE_W, rect.height / IMAGE_H);
        var offX = (rect.width - IMAGE_W * scale) / 2;
        var offY = (rect.height - IMAGE_H * scale) / 2;
        return {{
          fx: (ix * IMAGE_W * scale + offX) / rect.width,
          fy: (iy * IMAGE_H * scale + offY) / rect.height
        }};
      }}

      var base = {{}};
      pupils.forEach(function (p) {{
        var e = EYES[p.getAttribute("data-eye")];
        if (!e) return;
        var f = imgToFrac(e.x, e.y);
        base[p.getAttribute("data-eye")] = f;
        var rect = wrap.getBoundingClientRect();
        var scale = Math.max(rect.width / IMAGE_W, rect.height / IMAGE_H);
        p.style.width = (IRIS_SIZE * scale) + "px";
        p.style.height = (IRIS_SIZE * scale) + "px";
        p.style.left = (f.fx * 100) + "%";
        p.style.top = (f.fy * 100) + "%";
      }});

      function mouseMove(ev) {{
        var r = wrap.getBoundingClientRect();
        pupils.forEach(function (p) {{
          var e = base[p.getAttribute("data-eye")];
          if (!e) return;
          var dx = ev.clientX - (r.left + e.fx * r.width);
          var dy = ev.clientY - (r.top + e.fy * r.height);
          var len = Math.hypot(dx, dy) || 1;
          var t = Math.min(1, MAX_MOVE / len);
          p.style.translate = (dx * t) + "px " + (dy * t) + "px";
        }});
      }}
      function mouseLeave() {{
        wrap.classList.remove("is-hovering");
        pupils.forEach(function (p) {{
          p.style.translate = "0px 0px";
        }});
      }}

      wrap.addEventListener("mouseenter", function () {{
        wrap.classList.add("is-hovering");
      }});
      wrap.addEventListener("mousemove", mouseMove);
      wrap.addEventListener("mouseleave", mouseLeave);
    }})();
    </script>
  </body>
</html>
"""


def render_page_body(page: Page, posts: list[Post] | None = None) -> str:
    if page.slug == "" and page.image_path:
        image_html = (
            '<div class="headshot-wrap">'
            f'<img class="headshot" src="{html.escape(page.image_path, quote=True)}" '
            f'alt="{html.escape(page.image_alt, quote=True)}">'
            '<span class="headshot-pupil" data-eye="left"></span>'
            '<span class="headshot-pupil" data-eye="right"></span>'
            "</div>"
        )
        article = [
            '<section class="home-hero">',
            '<div class="home-copy">',
            f"<h1>{html.escape(page.title)}</h1>",
            markdown_to_html(page.body),
            "</div>",
            f'<div class="home-photo">{image_html}</div>',
            "</section>",
        ]
    else:
        article = [f"<article><h1>{html.escape(page.title)}</h1>"]
        article.append(markdown_to_html(page.body))
        article.append("</article>")

    if posts is not None:
        latest_items = "\n".join(render_post_item(post) for post in posts[:5])
        article.append(
            f"""
<section class="post-list">
  <div class="section-label">Recent writing</div>
  <ul class="entries">
    {latest_items}
  </ul>
  <p><a href="/writing/">See all posts</a></p>
</section>
"""
        )

    return "\n".join(article)


def render_post_item(post: Post) -> str:
    return f"""
<li>
  <a href="/posts/{post.slug}/">{html.escape(post.title)}</a>
  <span>{post.published_on.strftime("%B %-d, %Y")}</span>
  <p>{html.escape(post.summary)}</p>
</li>
""".strip()


def render_post_body(post: Post) -> str:
    return f"""
<article>
  <p class="eyebrow"><a href="/writing/">Writing</a></p>
  <h1>{html.escape(post.title)}</h1>
  <p class="meta">{post.published_on.strftime("%B %-d, %Y")}</p>
  {markdown_to_html(post.body)}
</article>
""".strip()


def render_writing_index(posts: Iterable[Post]) -> str:
    items = "\n".join(render_post_item(post) for post in posts)
    return f"""
<section>
  <h1>Writing</h1>
  <p>A running archive of notes, essays, and whatever else felt worth jotting down.</p>
  <ul class="entries">
    {items}
  </ul>
</section>
""".strip()


def render_redirect(
    *,
    site: dict,
    target_path: str,
    title: str,
    summary: str,
    image_path: str,
    image_alt: str,
    kind: str,
) -> str:
    """A forwarding stub that still previews as the page it points at.

    Social scrapers do not follow a meta refresh, so an old URL shared on
    LinkedIn or Slack is previewed from this stub rather than the
    destination. Carry the destination's metadata so those links still
    unfurl with a title, description, and image.
    """
    href = html.escape(target_path, quote=True)
    target_url = html.escape(site["url"] + target_path, quote=True)
    script_target = json.dumps(target_path).replace("<", "\\u003c")
    page_title = title if title == site["name"] else f"{title} | {site['name']}"
    social = social_tags(
        site=site,
        title=social_title(site=site, title=title, page_title=page_title, kind=kind),
        summary=summary,
        # Point previews at the destination, not at this stub.
        current_path=target_path,
        image_path=image_path,
        image_alt=image_alt,
        kind=kind,
    )
    return f"""<!DOCTYPE html>
<html lang="en">
  <head>
    <meta charset="utf-8">
    <title>{html.escape(page_title)}</title>
    <meta name="description" content="{html.escape(summary, quote=True)}">
    <meta name="robots" content="noindex">
    <meta http-equiv="refresh" content="0; url={href}">
    <link rel="canonical" href="{target_url}">
    {social}
    <script>window.location.replace({script_target});</script>
  </head>
  <body>
    <p>This page has moved to <a href="{href}">{target_url}</a>.</p>
  </body>
</html>
"""


def resolve_redirects(
    pages: list[Page], posts: list[Post]
) -> list[tuple[str, Page | Post]]:
    """Pair every redirect path with its destination, rejecting conflicts.

    Redirect stubs are written into the same output tree as real pages, so a
    redirect that shadows live content would silently clobber it. Fail loudly
    instead.
    """
    live: dict[str, str] = {"/writing/": "the generated writing index"}
    for item in [*pages, *posts]:
        live[item.current_path] = str(item.source_path.relative_to(ROOT))

    claimed: dict[str, tuple[Page | Post, str]] = {}
    for item in [*pages, *posts]:
        source = str(item.source_path.relative_to(ROOT))
        for path in item.redirect_paths():
            if path in live:
                raise ValueError(
                    f"{source}: redirect '{path}' collides with live content from "
                    f"{live[path]}"
                )
            if path in claimed:
                raise ValueError(
                    f"{source}: redirect '{path}' is already claimed by "
                    f"{claimed[path][1]}"
                )
            claimed[path] = (item, source)
    return [(path, target) for path, (target, _) in sorted(claimed.items())]


def write_output(relative_path: str, content: str) -> None:
    destination = OUTPUT_DIR / relative_path
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(content, encoding="utf-8")


def build() -> None:
    site = load_site_config()
    pages = load_pages()
    posts = load_posts()
    redirects = resolve_redirects(pages, posts)

    if OUTPUT_DIR.exists():
        shutil.rmtree(OUTPUT_DIR)

    shutil.copytree(STATIC_DIR, OUTPUT_DIR / "assets")

    for page in pages:
        page_html = site_shell(
            site=site,
            pages=pages,
            title=page.title,
            description=page.description,
            current_path=page.current_path,
            content=render_page_body(page, posts=posts if page.slug == "" else None),
            image_path=page.image_path,
            image_alt=page.image_alt,
        )
        write_output(page.output_path, page_html)

    writing_html = site_shell(
        site=site,
        pages=pages,
        title="Writing",
        description="A list of blog posts and notes.",
        current_path="/writing/",
        content=render_writing_index(posts),
    )
    write_output("writing/index.html", writing_html)

    for post in posts:
        post_html = site_shell(
            site=site,
            pages=pages,
            title=post.title,
            description=post.summary,
            current_path=post.current_path,
            content=render_post_body(post),
            image_path=post.image_path,
            image_alt=post.image_alt,
            kind="article",
        )
        write_output(f"posts/{post.slug}/index.html", post_html)

    for redirect_path, target in redirects:
        is_post = isinstance(target, Post)
        write_output(
            f"{redirect_path.strip('/')}/index.html",
            render_redirect(
                site=site,
                target_path=target.current_path,
                title=target.title,
                summary=(target.summary if is_post else target.description)
                or site["description"],
                image_path=target.image_path,
                image_alt=target.image_alt,
                kind="article" if is_post else "website",
            ),
        )

    write_output("CNAME", f"{site['domain']}\n")
    write_output(
        "robots.txt",
        f"User-agent: *\nAllow: /\nSitemap: {site['url']}/sitemap.xml\n",
    )
    sitemap_entries = [""]
    for page in pages:
        sitemap_entries.extend(
            [
                "  <url>",
                f"    <loc>{site['url']}{page.current_path}</loc>",
                "  </url>",
            ]
        )
    sitemap_entries.extend(
        [
            "  <url>",
            f"    <loc>{site['url']}/writing/</loc>",
            "  </url>",
        ]
    )
    for post in posts:
        sitemap_entries.extend(
            [
                "  <url>",
                f"    <loc>{site['url']}/posts/{post.slug}/</loc>",
                "  </url>",
            ]
        )
    sitemap = (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
        + "\n".join(sitemap_entries)
        + "\n</urlset>\n"
    )
    write_output("sitemap.xml", sitemap)


if __name__ == "__main__":
    build()
