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

## Automation

`.github/workflows/update-stars.yml` runs **weekly** (and on manual
`workflow_dispatch`). It commits any changes to `data/` and `catalog/` back to the repo.

**Setup:** add an `OPENROUTER_API_KEY` [repository secret]. The built-in `GITHUB_TOKEN`
already covers reading public stars — no extra token needed.

## Editing the taxonomy

Edit `data/categories.json`, then run `python scripts/stars.py --force` to
re-classify everything under the new scheme.

[repository secret]: https://docs.github.com/en/actions/security-guides/using-secrets-in-github-actions
