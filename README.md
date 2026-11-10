# Feather Note website

The website for Feather Note, a native Mac app for Markdown notes with end-to-end-encrypted sync. Plain HTML and CSS in `site/`, served by Cloudflare Pages with no build step. Built for search engines and AI assistants: structured data, a sitemap, `robots.txt`, `llms.txt` and `pricing.md`.

Check it before publishing:

```bash
python3 scripts/check_site.py && python3 scripts/test_check_site.py
```

Before going live, replace `WEBSITE_DOMAIN` everywhere in `site/` and run `python3 scripts/check_site.py --publish`.

## Related repositories

- `feather-note-mac`: the macOS app (MIT)
- `feather-note-server`: the Feather Cloud sync server (AGPL-3.0)

## License

MIT, see [LICENSE](LICENSE).

## Trademark

The name Feather Note stays with the author. Forks must use a different name.
