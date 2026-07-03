# ⭐ GitHub Stars Catalog

A self-updating, LLM-organized catalog of my GitHub stars.

Stars are fetched from GitHub, **new** ones are categorized by an LLM (via
[OpenRouter](https://openrouter.ai/)), and a browsable markdown catalog is generated —
all kept current by a weekly GitHub Action.

## 🔎 Browse & search

👉 **[Live site →](https://nyokinokonoko.github.io/github-stars/)** — instant search,
filter by category / language / tag, and sort. _(Enable GitHub Pages: Settings → Pages →
Deploy from branch → `main` `/docs`.)_

Prefer plain markdown? **[catalog/README.md](catalog/README.md)** — index with
per-category counts and stats; each category has its own file under [`catalog/`](catalog/).

## How it works

```
GitHub API ─▶ diff vs data/stars.json ─▶ LLM categorizes NEW repos only ─▶ stars.json ─┬▶ catalog/*.md
                                                                                        └▶ docs/data.json (Pages site)
```

- **`data/stars.json`** — the canonical database of every starred repo (keyed by
  `owner/name`). Existing entries are never re-sent to the LLM, so **LLM cost scales
  only with newly-added stars**.
- **`data/categories.json`** — the editable taxonomy. The LLM must pick one of these
  categories; it also adds free-form tags and a one-line summary.
- **`catalog/`** — generated markdown; do not edit by hand (it's overwritten each run).
- **`docs/`** — the GitHub Pages site (static, zero-dependency). `docs/data.json` is
  generated each run; `index.html` / `app.js` / `style.css` are the hand-authored app.

## Running locally

```bash
pip install -r requirements.txt
cp .env.example .env        # then fill in OPENROUTER_API_KEY (and optionally GITHUB_TOKEN)

python scripts/stars.py              # fetch, categorize new stars, rebuild catalog
python scripts/stars.py --no-llm     # refresh metadata + rebuild catalog, no API calls
python scripts/stars.py --force      # re-categorize everything (after editing the taxonomy)
```

## Working on the site locally

The site (`docs/`) is **static with no build step** — `index.html`, `app.js`, and
`style.css` are served as-is; they just read `docs/data.json`.

**1. Regenerate `docs/data.json`** (only needed after the star data changes):

```bash
python scripts/stars.py --no-llm     # refreshes stars.json + catalog + docs/data.json (no LLM cost)
```

Or rebuild just the site payload from the existing `data/stars.json`, fully offline:

```bash
python -c "import json,sys; sys.path.insert(0,'scripts'); import catalog; \
d=json.load(open('data/stars.json')); \
catalog.write_site_data(__import__('pathlib').Path('data/stars.json'), __import__('pathlib').Path('docs'), d['meta'])"
```

**2. Serve `docs/` and open it** (an HTTP server is required — `fetch('data.json')`
does not work from a `file://` URL):

```bash
python -m http.server 8000 -d docs
# then open http://localhost:8000/
```

**3. Validate:** search, toggle category/language/tag filters and sorting, reload with a
populated URL hash (e.g. `#q=cli&cat=CLI+%26+Terminal`), and switch dark/light. The
browser DevTools **Network** tab should show only `data.json` fetched — no external
requests (no CDNs, no third-party JS).

## Automation

`.github/workflows/update-stars.yml` runs **weekly** (and on manual
`workflow_dispatch`). It commits any changes to `data/` and `catalog/` back to the repo.

**Setup:** add an `OPENROUTER_API_KEY` [repository secret]. The built-in `GITHUB_TOKEN`
already covers reading public stars — no extra token needed.

## Editing the taxonomy

Edit `data/categories.json`, then run `python scripts/stars.py --force` to
re-classify everything under the new scheme.

[repository secret]: https://docs.github.com/en/actions/security-guides/using-secrets-in-github-actions
