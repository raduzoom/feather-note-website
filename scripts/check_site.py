#!/usr/bin/env python3
"""Checks the Feather Note website before it ships (Phase 9 Review Focus 5).

    python3 scripts/check_site.py      # from the website repo root; prints "site OK" or every failure

Rules: no JavaScript; nothing loaded from another host (the only outside links are <a href> to the project's
GitHub repos); every internal link resolves; each page has a title, description, viewport, lang and one <h1>;
no inline styles or meta refresh; SVG files hold no script and load nothing; CSS colours come from
universal/design/tokens.json and grid columns fit a 320 px screen; _headers sets the security headers.
Pages are parsed with html.parser, so unquoted attributes count too. Tests: scripts/test_check_site.py.
Standard library only.
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
HEADERS = {
    "Content-Security-Policy": "default-src 'self'; img-src 'self' data:; style-src 'self'; script-src 'none'; frame-ancestors 'none'",
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


class Tags(HTMLParser):
    """Every start tag of a page or SVG file, as (tag, {attribute: value}), in document order."""

    def __init__(self, text):
        super().__init__(convert_charrefs=True)
        self.tags = []
        self.feed(text)
        self.close()

    def handle_starttag(self, tag, attrs):
        self.tags.append((tag, {k.lower(): (v or "") for k, v in attrs}))

    handle_startendtag = handle_starttag


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


def check(site=SITE):
    failures = []
    pages = sorted(site.rglob("*.html")) if site.exists() else []
    if not pages:
        failures.append("site/ has no pages")
    for required in ("index.html", "privacy/index.html", "download/index.html", "self-hosting/index.html", "404.html"):
        if not (site / required).exists():
            failures.append(f"missing site/{required}")

    for page in pages:
        name = page.relative_to(site)
        html = page.read_text(encoding="utf-8")
        tags = Tags(html).tags
        if any(t == "script" for t, _ in tags):
            failures.append(f"{name}: has a <script>")
        if any(k.startswith("on") for _, a in tags for k in a):
            failures.append(f"{name}: has an inline event handler")
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
                    if not (tag == "a" and attr == "href" and ref.startswith(ALLOWED_OUTSIDE)):
                        failures.append(f"{name}: loads or links outside the site: {ref}")
                    continue
                if resolve(site, page, ref) is None:
                    failures.append(f"{name}: broken link {ref}")

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

    headers = site / "_headers"
    text = headers.read_text(encoding="utf-8") if headers.exists() else ""
    for key, value in HEADERS.items():
        if f"{key}: {value}" not in text:
            failures.append(f"_headers: needs '{key}: {value}'")
    return failures


if __name__ == "__main__":
    problems = check()
    if problems:
        print("\n".join(problems))
        sys.exit(1)
    print("site OK")
