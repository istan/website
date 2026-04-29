from __future__ import annotations

import html
import re
import shutil
from dataclasses import dataclass
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


@dataclass
class Page:
    source_path: Path
    title: str
    slug: str
    body: str
    description: str = ""
    image_path: str = ""
    image_alt: str = ""

    @property
    def current_path(self) -> str:
        return "/" if self.slug == "" else f"/{self.slug}/"

    @property
    def output_path(self) -> str:
        return "index.html" if self.slug == "" else f"{self.slug}/index.html"


@dataclass
class Post:
    source_path: Path
    title: str
    slug: str
    published_on: date
    summary: str
    body: str


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
    escaped = re.sub(r"\*\*([^*]+)\*\*", r"<strong>\1</strong>", escaped)
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


def site_shell(
    *,
    site: dict,
    pages: list[Page],
    title: str,
    description: str,
    current_path: str,
    content: str,
) -> str:
    page_title = title if title == site["name"] else f"{title} | {site['name']}"
    summary = description or site["description"]
    return f"""<!DOCTYPE html>
<html lang="en">
  <head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <title>{html.escape(page_title)}</title>
    <meta name="description" content="{html.escape(summary, quote=True)}">
    <link rel="stylesheet" href="/assets/style.css">
    <link rel="canonical" href="{html.escape(site['url'] + current_path, quote=True)}">
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
  </body>
</html>
"""


def render_page_body(page: Page, posts: list[Post] | None = None) -> str:
    if page.slug == "" and page.image_path:
        image_html = (
            f'<img class="headshot" src="{html.escape(page.image_path, quote=True)}" '
            f'alt="{html.escape(page.image_alt, quote=True)}">'
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


def write_output(relative_path: str, content: str) -> None:
    destination = OUTPUT_DIR / relative_path
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(content, encoding="utf-8")


def build() -> None:
    site = load_site_config()
    pages = load_pages()
    posts = load_posts()

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
            current_path=f"/posts/{post.slug}/",
            content=render_post_body(post),
        )
        write_output(f"posts/{post.slug}/index.html", post_html)

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
