# Feather Note website: agent rules

Rules for AI agents in this repo. `CLAUDE.md` is a symlink to this file. The shared rules for all Feather Note repos are in `../AGENTS.md`; global rules in `~/Dropbox/Configs/claude/AGENTS.md` still apply.

## What this is (when changing anything)

The static website, served by Cloudflare Pages from `site/` as is: no build step, no framework. Pages project settings: production branch `main`, build command empty, output directory `site`.

## Rules (when adding or changing a page)

- JavaScript and requests to other hosts are allowed (the user's decision, 2026-11-10). Before the first thing loads from another host, change the privacy page's "no analytics, no cookies and no third-party scripts" sentence to say what loads and from where, and widen the CSP in `_headers` for it; the checker fails until both are done.
- Colours come only from `../universal/design/tokens.json` (the Mint Glass direction). Light and dark follow `prefers-color-scheme`.
- Text contrast is at least 4.5:1 against every background it can sit on (window, both glows, panels); compute it, don't judge by eye. Links and small accent text use `--accent-text`.
- One primary button per page; button labels say what happens; the 8 pt spacing grid; body lines at most 70 characters.
- Copy that the app also shows comes from `../universal/design/ui-copy.md` word for word.
- `WEBSITE_DOMAIN` and `CLOUD_DOMAIN` are placeholders until the domains are bought (`../server/docs/hosting-mac-mini.md`). They are two different domains: the site is on its own, and Feather Cloud runs on another, so never derive one from the other (no `cloud.<website domain>`).

## SEO and agentic SEO (when adding or changing a page)

Every presentation site is optimized for search engines and for AI assistants (the user's standing rule; `~/Dropbox/hosts/devsite/projects/general-app-knowledge/docs/presentation-site-seo.md`). Here that means:
- Each page: a unique title (at most 60 characters) and description (120–160; the checker enforces both), a canonical URL, Open Graph and Twitter card tags with `assets/social-card.png`, and JSON-LD (`<script type="application/ld+json">`, the home page's `@graph`: Organization, WebSite, SoftwareApplication, FAQPage; other pages: WebPage and BreadcrumbList). `404.html` is `noindex`.
- Content answers first: the first paragraph says what Feather Note is; headings never skip a level; FAQ questions are `<h3>`s whose text and answers match the FAQPage data word for word (the checker compares them).
- A new page goes into `sitemap.xml` (with `lastmod`) and `llms.txt`. Prices go in `pricing.md`; keep it current.
- `robots.txt` lets every search and AI crawler in.
- Absolute URLs use `https://WEBSITE_DOMAIN` until the domain is bought; `check_site.py --publish` refuses the placeholder.

## Images (when changing the social card or touch icon)

Sources are `design/social-card.html` (1200×630) and `design/apple-touch-icon.html` (180×180). Render each with headless Chrome from `design/`, for example:

```bash
"/Applications/Google Chrome.app/Contents/MacOS/Google Chrome" --headless=new --hide-scrollbars --force-device-scale-factor=1 --window-size=1200,630 --screenshot=../site/assets/social-card.png "file://$PWD/social-card.html"
```

## Check (before saying a change works)

```bash
python3 scripts/check_site.py && python3 scripts/test_check_site.py
```

It must print `site OK`, and the checker's own tests must pass (a new rule gets a test that plants a violation in a copy of the site). Then look at every changed page at 1280×800 and 390×844, light and dark (`python3 -m http.server 7843 --bind 127.0.0.1` from `site/`); nothing may scroll sideways at 390 px.

## Dropbox (after cloning and after git work)

```bash
[ -e .git/index ] && xattr -w com.dropbox.ignored 1 .git/index
```
