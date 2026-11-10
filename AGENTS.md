# Feather Note website: agent rules

Rules for AI agents in this repo. `CLAUDE.md` is a symlink to this file. The shared rules for all Feather Note repos are in `../AGENTS.md`; global rules in `~/Dropbox/Configs/claude/AGENTS.md` still apply.

## What this is (when changing anything)

The static website, served by Cloudflare Pages from `site/` as is: no build step, no framework. Pages project settings: production branch `main`, build command empty, output directory `site`.

## Rules (when adding or changing a page)

- No JavaScript, no cookies, no analytics, and nothing loaded from another host: fonts, images, styles and scripts all come from `site/`. The only outside links are `<a href>` to the project's GitHub repos.
- Colours come only from `../universal/design/tokens.json` (the Mint Glass direction). Light and dark follow `prefers-color-scheme`.
- Text contrast is at least 4.5:1 against every background it can sit on (window, both glows, panels); compute it, don't judge by eye. Links and small accent text use `--accent-text`.
- One primary button per page; button labels say what happens; the 8 pt spacing grid; body lines at most 70 characters.
- Copy that the app also shows comes from `../universal/design/ui-copy.md` word for word.
- `WEBSITE_DOMAIN` and `CLOUD_DOMAIN` are placeholders until the domains are bought (`../server/docs/hosting-mac-mini.md`).

## Check (before saying a change works)

```bash
python3 scripts/check_site.py && python3 scripts/test_check_site.py
```

It must print `site OK`, and the checker's own tests must pass (a new rule gets a test that plants a violation in a copy of the site). Then look at every changed page at 1280×800 and 390×844, light and dark (`python3 -m http.server 7843 --bind 127.0.0.1` from `site/`); nothing may scroll sideways at 390 px.

## Dropbox (after cloning and after git work)

```bash
[ -e .git/index ] && xattr -w com.dropbox.ignored 1 .git/index
```
