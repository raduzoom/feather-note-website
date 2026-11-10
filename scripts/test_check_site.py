#!/usr/bin/env python3
"""Tests for check_site.py: each rule it enforces must catch a violation planted in a copy of the site.

    python3 scripts/test_check_site.py      # from the website repo root
"""
import pathlib
import re
import shutil
import sys
import tempfile
import unittest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import check_site  # noqa: E402

HOME = "index.html"


class CheckSiteTests(unittest.TestCase):
    def setUp(self):
        self.tmp = pathlib.Path(tempfile.mkdtemp())
        self.site = self.tmp / "site"
        shutil.copytree(check_site.SITE, self.site)

    def tearDown(self):
        shutil.rmtree(self.tmp)

    def plant(self, path, before, after):
        p = self.site / path
        text = p.read_text(encoding="utf-8")
        self.assertIn(before, text, f"{path} lost its anchor text")
        p.write_text(text.replace(before, after, 1), encoding="utf-8")

    def failures(self):
        return check_site.check(self.site)

    def assertCaught(self, needle):
        found = self.failures()
        self.assertTrue(any(needle in f for f in found), f"expected a failure mentioning {needle!r}, got {found}")

    def test_real_site_passes(self):
        self.assertEqual(self.failures(), [])

    def test_unquoted_outside_stylesheet(self):
        self.plant(HOME, "</head>", "<link rel=stylesheet href=https://fonts.example.com/a.css></head>")
        self.assertCaught("https://fonts.example.com/a.css")

    def test_outside_srcset(self):
        self.plant(HOME, "</main>", '<img alt="" srcset="https://tracker.example/p.png 1x"></main>')
        self.assertCaught("https://tracker.example/p.png")

    def test_meta_refresh(self):
        self.plant(HOME, "</head>", '<meta http-equiv="refresh" content="0;url=https://evil.example"></head>')
        self.assertCaught("refresh")

    def test_script_in_svg(self):
        self.plant("assets/feather.svg", "</svg>", "<script>alert(1)</script></svg>")
        self.assertCaught("feather.svg")

    def test_outside_image_in_svg(self):
        self.plant("assets/feather.svg", "</svg>", '<image href="https://tracker.example/p.png"/></svg>')
        self.assertCaught("https://tracker.example/p.png")

    def test_inline_style(self):
        self.plant(HOME, "<main", '<main style="color:#ff0000"')
        self.assertCaught("style")

    def test_grid_column_wider_than_a_phone(self):
        # minmax(20rem, 1fr) scrolls sideways under ~352 px (iPhone SE, 200% zoom); min(20rem, 100%) doesn't
        self.plant("assets/site.css", "minmax(min(16rem, 100%), 1fr)", "minmax(16rem, 1fr)")
        self.assertCaught("minmax")

    # SEO and agentic SEO (website/AGENTS.md "SEO")

    def test_structured_data_is_allowed_but_must_parse(self):
        self.plant(HOME, "</head>", '<script type="application/ld+json">{"@context": oops}</script></head>')
        found = self.failures()
        self.assertFalse(any("has a <script>" in f for f in found), found)
        self.assertCaught("JSON-LD")

    def test_scripts_are_allowed(self):
        # the user's decision (2026-11-10): the site may use JavaScript and load from other hosts
        self.plant(HOME, "</head>", '<script src="/assets/app.js"></script></head>')
        (self.site / "assets" / "app.js").write_text("1", encoding="utf-8")
        self.assertCaught("script-src")  # the CSP still blocks every script
        self.plant("_headers", "script-src 'none'", "script-src 'self'")
        self.assertEqual(self.failures(), [])

    def test_outside_script_while_privacy_page_promises_none(self):
        self.plant(HOME, "</head>", '<script src="https://cdn.example.com/a.js"></script></head>')
        self.assertCaught("privacy")

    def test_outside_script_after_privacy_page_says_so(self):
        self.plant(HOME, "</head>", '<script src="https://cdn.example.com/a.js"></script></head>')
        self.plant("privacy/index.html", check_site.PRIVACY_PROMISE, "This website loads a script from cdn.example.com.")
        self.plant("_headers", "script-src 'none'", "script-src https://cdn.example.com")
        self.assertEqual(self.failures(), [])

    def test_page_without_canonical(self):
        self.plant("privacy/index.html", 'rel="canonical"', 'rel="alternate"')
        self.assertCaught("canonical")

    def test_canonical_for_another_page(self):
        self.plant("privacy/index.html", "/privacy/\"", "/download/\"")
        self.assertCaught("canonical")

    def test_page_without_social_card(self):
        self.plant("download/index.html", 'property="og:image"', 'property="og:imagex"')
        self.assertCaught("og:image")

    def test_sitemap_misses_a_page(self):
        self.plant("sitemap.xml", "<loc>https://WEBSITE_DOMAIN/self-hosting/</loc>", "<loc>https://WEBSITE_DOMAIN/elsewhere/</loc>")
        self.assertCaught("sitemap")

    def test_404_must_not_be_indexed(self):
        self.plant("404.html", 'content="noindex"', 'content="index"')
        self.assertCaught("404.html")

    def test_robots_blocks_an_ai_crawler(self):
        self.plant("robots.txt", "User-agent: *", "User-agent: GPTBot\nDisallow: /\n\nUser-agent: *")
        self.assertCaught("GPTBot")

    def test_llms_txt_broken_link(self):
        self.plant("llms.txt", "/privacy/", "/no-such-page/")
        self.assertCaught("llms.txt")

    def test_faq_schema_differs_from_the_page(self):
        self.plant(HOME, "<h3>Is Feather Note free?</h3>", "<h3>Is Feather Note cheap?</h3>")
        self.assertCaught("FAQ")

    def test_heading_level_skipped(self):
        self.plant("privacy/index.html", "</main>", "<h4>Deep</h4></main>")
        self.assertCaught("heading")

    def test_title_too_long_for_search_results(self):
        self.plant("download/index.html", "<title>Download Feather Note for Mac</title>",
                   "<title>Download Feather Note for Mac, the native Markdown notes app with sync</title>")
        self.assertCaught("title")

    def test_description_too_short(self):
        self.plant("download/index.html", '<meta name="description" content="', '<meta name="description" content="Short. ')
        p = self.site / "download/index.html"
        p.write_text(re.sub(r'(<meta name="description" content=")[^"]*"', r'\1Download it."', p.read_text(encoding="utf-8")), encoding="utf-8")
        self.assertCaught("description")

    def test_publish_refuses_the_placeholder_domain(self):
        found = check_site.check(self.site, publish=True)
        self.assertTrue(any("WEBSITE_DOMAIN" in f for f in found), found)


if __name__ == "__main__":
    unittest.main(verbosity=1)
