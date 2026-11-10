#!/usr/bin/env python3
"""Checks the Feather Note website before it ships (Phase 9 Review Focus 5).

    python3 scripts/check_site.py      # from the website repo root; prints "site OK" or every failure

Rules: JavaScript and outside requests are allowed (the user's decision, 2026-11-10), but the privacy page's
promise of no third-party requests must go before anything loads from another host, and the CSP must not block
scripts a page uses; every internal link resolves; each page has a title, description, viewport, lang and one <h1>;
no inline styles or meta refresh; SVG files hold no script and load nothing; CSS colours come from
universal/design/tokens.json and grid columns fit a 320 px screen; _headers sets the security headers.
SEO and agentic SEO: every page but 404 has a canonical URL, social card tags and a sitemap entry; 404 is
noindex; headings never skip a level; JSON-LD (the one script type allowed: a data block browsers don't run)
parses, and FAQ structured data matches the visible questions and answers; robots.txt points to the sitemap
and blocks no search or AI crawler; llms.txt links resolve.
Pages are parsed with html.parser, so unquoted attributes count too. Tests: scripts/test_check_site.py.
Standard library only.

    python3 scripts/check_site.py --publish   # also refuses the WEBSITE_DOMAIN placeholder, before going live
"""
import json
import pathlib
import re
import sys
from html.parser import HTMLParser

ROOT = pathlib.Path(__file__).resolve().parent.parent
SITE = ROOT / "site"
TOKENS = ROOT.parent / "universal" / "design" / "tokens.json"
ALLOWED_OUTSIDE = ("https://github.com/raduzoom/",)
# the privacy page's promise; while it stands, nothing may load from another host
PRIVACY_PROMISE = "This website and the app use no analytics, no cookies and no third-party scripts."
HEADERS = {
    "Referrer-Policy": "no-referrer",
    "Permissions-Policy": "interest-cohort=()",
}


def token_colours():
    """Every colour value in tokens.json, normalised (lowercase hex, rgba without spaces)."""
    if not TOKENS.exists():
        return None
    colours = set()

    def walk(node):
        if isinstance(node, dict):
            for v in node.values():
                walk(v)
        elif isinstance(node, str):
            for m in re.findall(r"#[0-9a-fA-F]{6}\b|rgba?\([^)]*\)", node):
                colours.add(normalise(m))

    walk(json.loads(TOKENS.read_text(encoding="utf-8")).get("color", {}))
    return colours


def normalise(c):
    return re.sub(r"\s+", "", c.lower())


# attributes whose value is a URL (srcset: a list of "URL width" pairs)
URL_ATTRS = {"src", "href", "action", "formaction", "data", "poster", "background", "cite", "xlink:href", "ping"}


JSON_LD = "application/ld+json"
# crawlers that feed search engines and AI answers; robots.txt must not shut any of them out
CRAWLERS = ("Googlebot", "Bingbot", "Google-Extended", "GPTBot", "OAI-SearchBot", "ChatGPT-User", "PerplexityBot",
            "ClaudeBot", "Claude-SearchBot", "Claude-User", "anthropic-ai", "Applebot", "Applebot-Extended", "DuckDuckBot")


class Tags(HTMLParser):
    """A page or SVG file: every start tag as (tag, {attribute: value}) in document order, the JSON-LD blocks,
    the headings as (level, text), and the visible text."""

    def __init__(self, text):
        super().__init__(convert_charrefs=True)
        self.tags, self.json_ld, self.headings, self.text = [], [], [], []
        self._script = None   # the JSON-LD block being read, or None
        self._heading = None  # (level, [text]) of the heading being read
        self._skip = 0        # inside <script>, <style> or <head>: not visible text
        self.feed(text)
        self.close()

    def handle_starttag(self, tag, attrs):
        a = {k.lower(): (v or "") for k, v in attrs}
        self.tags.append((tag, a))
        if tag == "script" and a.get("type", "").lower() == JSON_LD:
            self._script = []
        if tag in ("script", "style", "head"):
            self._skip += 1
        if re.fullmatch(r"h[1-6]", tag):
            self._heading = (int(tag[1]), [])

    def handle_startendtag(self, tag, attrs):
        self.tags.append((tag, {k.lower(): (v or "") for k, v in attrs}))

    def handle_endtag(self, tag):
        if tag == "script" and self._script is not None:
            self.json_ld.append("".join(self._script))
            self._script = None
        if tag in ("script", "style", "head"):
            self._skip = max(0, self._skip - 1)
        if self._heading and tag == f"h{self._heading[0]}":
            self.headings.append((self._heading[0], squash("".join(self._heading[1]))))
            self._heading = None

    def handle_data(self, data):
        if self._script is not None:
            self._script.append(data)
        if self._heading:
            self._heading[1].append(data)
        if not self._skip:
            self.text.append(data)

    def visible_text(self):
        return squash(" ".join(self.text))


def squash(text):
    return re.sub(r"\s+", " ", text).strip()


def page_path(site, page):
    """The URL path a page is served at: /, /privacy/, /404.html."""
    rel = page.relative_to(site).as_posix()
    if rel == "index.html":
        return "/"
    if rel.endswith("/index.html"):
        return "/" + rel[: -len("index.html")]
    return "/" + rel


def url_path(url):
    """The path of an absolute https URL, or None."""
    m = re.match(r"https://[^/]+(/.*)?$", url)
    return (m.group(1) or "/") if m else None


def meta(tags, key):
    """The content of <meta name=key> or <meta property=key>."""
    for t, a in tags:
        if t == "meta" and key in (a.get("name"), a.get("property")):
            return a.get("content", "")
    return None


def check_seo(site, page, name, tags, parsed, failures):
    """SEO and agentic SEO rules for one page. Returns the canonical URL, or None for a noindex page."""
    robots = (meta(tags, "robots") or "").lower()
    path = page_path(site, page)
    for block in parsed.json_ld:
        try:
            data = json.loads(block)
        except ValueError as e:
            failures.append(f"{name}: JSON-LD doesn't parse ({e})")
            continue
        check_faq(name, data, parsed, failures)
    previous = 0
    for level, text in parsed.headings:
        if level > previous + 1:
            failures.append(f"{name}: heading <h{level}> {text!r} skips a level after <h{previous}>")
        previous = level
    if path == "/404.html":
        if "noindex" not in robots:
            failures.append(f'{name}: needs <meta name="robots" content="noindex">')
        return None
    if "noindex" in robots:
        failures.append(f"{name}: is noindex")
    m = re.search(r"<title>([^<]*)</title>", page.read_text(encoding="utf-8"))
    title = squash(m.group(1)) if m else ""
    if len(title) > 60:
        failures.append(f"{name}: title is {len(title)} characters; search results cut it after about 60")
    description = meta(tags, "description") or ""
    if not 120 <= len(description) <= 160:
        failures.append(f"{name}: description is {len(description)} characters; keep it 120–160 so search results show all of it")
    canonical = next((a.get("href", "") for t, a in tags if t == "link" and a.get("rel", "").lower() == "canonical"), None)
    if not canonical:
        failures.append(f"{name}: missing <link rel=\"canonical\">")
    elif url_path(canonical) != path:
        failures.append(f"{name}: canonical {canonical} isn't this page ({path})")
    for key in ("og:type", "og:title", "og:description", "og:url", "og:image", "og:image:alt", "twitter:card"):
        if not meta(tags, key):
            failures.append(f"{name}: missing <meta {key}>")
    if canonical and meta(tags, "og:url") and meta(tags, "og:url") != canonical:
        failures.append(f"{name}: og:url differs from the canonical URL")
    image = meta(tags, "og:image")
    if image and (url_path(image) is None or not (site / url_path(image).lstrip("/")).is_file()):
        failures.append(f"{name}: og:image {image} isn't an https URL of a file in site/")
    return canonical


def check_faq(name, data, parsed, failures):
    """FAQPage structured data must say what the page shows: each question is a heading, each answer is on the page."""
    items = data.get("@graph", [data]) if isinstance(data, dict) else []
    headings = {text for _, text in parsed.headings}
    body = parsed.visible_text()
    for item in items:
        if not isinstance(item, dict) or item.get("@type") != "FAQPage":
            continue
        for q in item.get("mainEntity", []):
            question = squash(q.get("name", ""))
            answer = squash(q.get("acceptedAnswer", {}).get("text", ""))
            if question not in headings:
                failures.append(f"{name}: FAQ question {question!r} isn't a heading on the page")
            if answer not in body:
                failures.append(f"{name}: FAQ answer to {question!r} isn't the page's text")


def check_site_files(site, canonicals, failures):
    """sitemap.xml, robots.txt and llms.txt."""
    sitemap = site / "sitemap.xml"
    if not sitemap.exists():
        failures.append("missing site/sitemap.xml")
    else:
        locs = re.findall(r"<loc>\s*([^<\s]+)\s*</loc>", sitemap.read_text(encoding="utf-8"))
        if sorted(locs) != sorted(canonicals):
            missing, extra = set(canonicals) - set(locs), set(locs) - set(canonicals)
            failures.append(f"sitemap.xml: must list exactly the canonical pages (missing {sorted(missing)}, extra {sorted(extra)})")

    robots = site / "robots.txt"
    text = robots.read_text(encoding="utf-8") if robots.exists() else ""
    if not robots.exists():
        failures.append("missing site/robots.txt")
    elif not re.search(r"(?mi)^Sitemap:\s*https://\S+/sitemap\.xml\s*$", text):
        failures.append("robots.txt: needs a Sitemap: line with the sitemap's https URL")
    groups = re.split(r"\n\s*\n", text)
    for group in groups:
        agents = re.findall(r"(?mi)^User-agent:\s*(\S+)", group)
        if re.search(r"(?mi)^Disallow:\s*/\s*$", group):
            for agent in agents:
                if agent == "*" or agent.lower() in (c.lower() for c in CRAWLERS):
                    failures.append(f"robots.txt: shuts out {agent}")

    llms = site / "llms.txt"
    if not llms.exists():
        failures.append("missing site/llms.txt")
    else:
        body = llms.read_text(encoding="utf-8")
        if not body.startswith("# "):
            failures.append("llms.txt: must start with '# <name>' (llmstxt.org)")
        for ref in re.findall(r"\]\(([^)\s]+)\)", body):
            if ref.startswith(ALLOWED_OUTSIDE):
                continue
            path = url_path(ref) if ref.startswith("https://") else ref
            if path is None or not path.startswith("/") or resolve(site, site / "index.html", path) is None:
                failures.append(f"llms.txt: broken link {ref}")


def urls(tag, attrs):
    """(attribute, URL) pairs a tag can load or link to."""
    for k, v in attrs.items():
        if k in URL_ATTRS:
            yield k, v.strip()
        elif k in ("srcset", "imagesrcset"):
            for part in v.split(","):
                if part.strip():
                    yield k, part.strip().split()[0]
    if tag == "meta" and attrs.get("http-equiv", "").lower() == "refresh":
        yield "refresh", attrs.get("content", "")


def is_outside(ref):
    return bool(re.match(r"[a-z][a-z0-9+.-]*:", ref, re.I)) or ref.startswith("//")


def resolve(site, page, ref):
    """The file an internal href/src points at, or None if it doesn't exist."""
    ref = ref.split("#", 1)[0].split("?", 1)[0]
    if ref == "":
        return page
    target = site / ref.lstrip("/") if ref.startswith("/") else page.parent / ref
    if target.is_dir() or ref.endswith("/"):
        target = target / "index.html"
    return target if target.exists() else None


def check(site=SITE, publish=False):
    failures = []
    canonicals = []
    pages = sorted(site.rglob("*.html")) if site.exists() else []
    if not pages:
        failures.append("site/ has no pages")
    for required in ("index.html", "privacy/index.html", "download/index.html", "self-hosting/index.html", "404.html"):
        if not (site / required).exists():
            failures.append(f"missing site/{required}")

    privacy = site / "privacy" / "index.html"
    promises = privacy.exists() and PRIVACY_PROMISE in squash(privacy.read_text(encoding="utf-8"))
    uses_scripts = False
    for page in pages:
        name = page.relative_to(site)
        html = page.read_text(encoding="utf-8")
        parsed = Tags(html)
        tags = parsed.tags
        if any((t == "script" and a.get("type", "").lower() != JSON_LD) or any(k.startswith("on") for k in a) for t, a in tags):
            uses_scripts = True
        if any("style" in a for _, a in tags):
            failures.append(f"{name}: has an inline style attribute (styles live in assets/site.css)")
        if not any(t == "html" and a.get("lang") == "en" for t, a in tags):
            failures.append(f'{name}: <html> needs lang="en"')
        if not re.search(r"<title>[^<]+</title>", html):
            failures.append(f"{name}: missing title")
        for meta in ("description", "viewport"):
            if not any(t == "meta" and a.get("name") == meta and a.get("content") for t, a in tags):
                failures.append(f"{name}: missing {meta}")
        if sum(t == "h1" for t, _ in tags) != 1:
            failures.append(f"{name}: needs exactly one <h1>")
        for tag, attrs in tags:
            for attr, ref in urls(tag, attrs):
                if attr == "refresh":
                    failures.append(f"{name}: has a meta refresh ({ref})")
                    continue
                if ref.startswith(("mailto:", "#")):
                    continue
                if is_outside(ref):
                    # the canonical link names this site's own address; it loads nothing
                    if tag == "link" and attrs.get("rel", "").lower() == "canonical":
                        continue
                    if tag != "a" and promises:
                        failures.append(f"{name}: loads {ref} from another host, but privacy/index.html still promises "
                                        "no third-party scripts; say what loads, and from where, first")
                    continue
                if resolve(site, page, ref) is None:
                    failures.append(f"{name}: broken link {ref}")
        canonical = check_seo(site, page, name, tags, parsed, failures)
        if canonical:
            canonicals.append(canonical)

    for svg in sorted(site.rglob("*.svg")) if site.exists() else []:
        name = svg.relative_to(site)
        for tag, attrs in Tags(svg.read_text(encoding="utf-8")).tags:
            if tag in ("script", "foreignobject") or any(k.startswith("on") for k in attrs):
                failures.append(f"{name}: has a <{tag}> or event handler")
            for _, ref in urls(tag, attrs):
                if is_outside(ref) and not ref.startswith(("#", "data:")):
                    failures.append(f"{name}: loads from outside the site: {ref}")

    allowed = token_colours()
    if allowed is None:
        failures.append(f"can't read {TOKENS}")
    for css in sorted(site.rglob("*.css")) if site.exists() else []:
        name = css.relative_to(site)
        text = re.sub(r"/\*.*?\*/", "", css.read_text(encoding="utf-8"), flags=re.S)
        if re.search(r"@import|url\(\s*['\"]?(https?:)?//", text):
            failures.append(f"{name}: imports or loads from another host")
        for colour in re.findall(r"#[0-9a-fA-F]{3,8}\b|rgba?\([^)]*\)", text):
            if allowed is not None and normalise(colour) not in allowed:
                failures.append(f"{name}: colour {colour} isn't a design token")
        for m in re.findall(r"minmax\(\s*([^,]+),", text):
            if re.match(r"[\d.]+(rem|em|px)", m.strip()):
                failures.append(f"{name}: minmax({m.strip()}, …) is wider than a 320 px screen; use minmax(min({m.strip()}, 100%), …)")

    check_site_files(site, canonicals, failures)
    if publish:
        for f in sorted(site.rglob("*")):
            if f.is_file() and f.suffix in (".html", ".xml", ".txt", ".md", ".json", "") and "WEBSITE_DOMAIN" in f.read_text(encoding="utf-8", errors="ignore"):
                failures.append(f"{f.relative_to(site)}: still has the WEBSITE_DOMAIN placeholder")

    headers = site / "_headers"
    text = headers.read_text(encoding="utf-8") if headers.exists() else ""
    csp = re.search(r"Content-Security-Policy:\s*(.+)", text)
    if not csp or "frame-ancestors 'none'" not in csp.group(1):
        failures.append("_headers: needs a Content-Security-Policy with frame-ancestors 'none'")
    elif uses_scripts and "script-src 'none'" in csp.group(1):
        failures.append("_headers: the CSP's script-src 'none' blocks the scripts a page uses")
    for key, value in HEADERS.items():
        if f"{key}: {value}" not in text:
            failures.append(f"_headers: needs '{key}: {value}'")
    return failures


if __name__ == "__main__":
    problems = check(publish="--publish" in sys.argv[1:])
    if problems:
        print("\n".join(problems))
        sys.exit(1)
    print("site OK")
