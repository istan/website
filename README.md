# ianmccrystal.com

A minimal personal website with markdown posts and no CMS.

## Structure

- `site.toml` holds the site name, domain, and a few shared settings.
- `content/index.md` is the homepage copy.
- `content/contact.md` is the contact page.
- `content/posts/*.md` are blog posts.
- `build.py` renders everything into `dist/` and auto-discovers top-level pages from `content/*.md`.

## Routing and navigation

### Top-level pages

Any markdown file placed directly in `content/` becomes a top-level page automatically.

- `content/index.md` builds to `/`
- `content/contact.md` builds to `/contact/`
- a file like `content/projects.md` would build to `/projects/`

By default, the route comes from the filename. If you want a different URL without renaming the file, add a `slug` in front matter:

```toml
+++
title = "Projects"
slug = "work"
+++
```

That page would render at `/work/`.

### Post routes

Posts live in `content/posts/`.

- The post URL defaults to a slugified version of the post title.
- You can override that by setting `slug` in the post front matter.

Example:

```toml
+++
title = "The world needs 100x more APIs"
date = "2026-04-27"
slug = "the-world-needs-100x-more-apis"
summary = "A one-line description for the archive page."
+++
```

That post renders at `/posts/the-world-needs-100x-more-apis/`.

### How the nav is built

The header nav is generated automatically by `build.py`.

- `Home` is always included and points to `/`
- `Writing` is always included and points to `/writing/`
- Every non-index markdown file in `content/` is added after that

The nav label comes from each page's `title` front matter, not the filename. So if you change a page title, the nav updates automatically on the next build.

### How to add or rename a page

To add a new page:

1. Create a markdown file in `content/`
2. Give it a `title` in front matter
3. Run `python3 build.py`

To rename a page in the nav:

1. Change the `title` in front matter
2. Rebuild the site

To change the page URL:

1. Rename the file in `content/`, or
2. Add/update the `slug` in front matter
3. Rebuild the site

### Sitemap behavior

The sitemap is also generated automatically from the discovered top-level pages plus the writing index and all posts, so page route changes do not require updating `build.py`.

## Write a post

Create a new markdown file in `content/posts/` with TOML front matter:

```md
+++
title = "Post title"
date = "2026-04-27"
summary = "A one-line description for the archive page."
+++

Write the post here.
```

The body supports:

- headings
- paragraphs
- bulleted and numbered lists
- blockquotes
- fenced code blocks
- inline code
- markdown links

You can also apply a class to the previous paragraph by adding a line like:

```md
Some intro copy.
{:.lede}
```

## Build locally

```bash
python3 build.py
```

That creates a static site in `dist/`.

## Preview locally

```bash
python3 -m http.server 8000 --directory dist
```

Then open `http://localhost:8000`.

## Publish

Upload the contents of `dist/` to any static host.

If you use GitHub Pages, Netlify, Cloudflare Pages, or a similar service, point `ianmccrystal.com` at that host and publish the generated output directory. The build also creates a `CNAME` file automatically.
