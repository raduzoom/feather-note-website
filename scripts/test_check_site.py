#!/usr/bin/env python3
"""Tests for check_site.py: each rule it enforces must catch a violation planted in a copy of the site.

    python3 scripts/test_check_site.py      # from the website repo root
"""
import pathlib
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


if __name__ == "__main__":
    unittest.main(verbosity=1)
