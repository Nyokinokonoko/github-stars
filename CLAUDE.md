# CLAUDE.md

Guidance for working in this repository.

## Purpose

A self-updating catalog of GitHub stars for user `nyokinokonoko`. Stars are fetched,
**newly-added** repos are categorized by an LLM (OpenRouter), everything persists to a
JSON database, and a markdown catalog is regenerated from that database.

## Architecture / data flow

```
scripts/stars.py (orchestrator)
  1. load  data/stars.json            (canonical DB; {} if absent)
  2. fetch stars via scripts/github.py (paginated, captures starred_at)
  3. diff:  new = fetched − stored     ·  removed = stored − fetched (PRUNED)
  4. categorize NEW repos via scripts/categorize.py (OpenRouter) — new only!
  5. refresh mutable metadata (stars/desc/topics) on existing entries (no LLM)
  6. write data/stars.json
  7. regenerate catalog/ via scripts/catalog.py (pure, no LLM)
  8. write docs/data.json for the Pages site (catalog.write_site_data, pure)
```

Key invariant: **the LLM is only ever called on repos not already in `stars.json`.**
This keeps cost proportional to *new* stars, not the total. `--force` overrides this to
re-categorize everything (use after editing the taxonomy).

## Files

- `scripts/stars.py` — CLI entry point / orchestrator. Flags: `--no-llm`, `--force`.
- `scripts/github.py` — GitHub starred-repos fetching + pagination.
- `scripts/categorize.py` — OpenRouter client; batches repos, structured JSON output.
- `scripts/catalog.py` — markdown generation from `stars.json`. No network.
- `data/stars.json` — canonical database, keyed by `owner/name`. **Source of truth.**
- `data/categories.json` — editable taxonomy (category list + descriptions for the LLM).
- `scripts/catalog.py` also has `write_site_data()` → emits `docs/data.json`.
- `catalog/` — **generated**; never hand-edit (overwritten every run).
- `docs/` — GitHub Pages site (Pages source = `main` `/docs`). Static, zero-dependency
  vanilla JS; no build step. `docs/data.json` is **generated** (do not hand-edit);
  `index.html` / `app.js` / `style.css` / `.nojekyll` are hand-authored.
- `.github/workflows/update-stars.yml` — weekly cron + `workflow_dispatch`; commits
  `data/`, `catalog/`, and `docs/data.json`.

## Running locally

```bash
pip install -r requirements.txt
cp .env.example .env    # fill OPENROUTER_API_KEY (+ optional GITHUB_TOKEN)
python scripts/stars.py            # full run
python scripts/stars.py --no-llm   # metadata refresh + rebuild, no API cost
python scripts/stars.py --force    # re-categorize all (after taxonomy edits)
```

Env vars: `GH_USER`, `GITHUB_TOKEN` (optional), `OPENROUTER_API_KEY`,
`OPENROUTER_MODEL` (optional, defaults to `google/gemini-3-flash-preview`).

## Editing the taxonomy

Categories live in `data/categories.json`. Add/rename entries there, then run with
`--force`. The LLM is constrained to the listed categories; anything it can't place
falls back to `Other`.

## Cost model

Only new stars hit the LLM, batched ~15 per request with structured JSON output.
A no-change run makes **zero** LLM calls. Full re-categorization (`--force`, or the very
first run) processes all repos once.

## Commit convention

Keep commits small and logical — one concern per commit. When a change spans code +
generated data, prefer separate commits (e.g. "scripts: ..." then "catalog: regenerate").
Generated files (`data/stars.json`, `catalog/`) may be committed by the GitHub Action;
its automated commits are titled `chore: update stars catalog`.

## Conventions

- Python: stdlib + `requests` only; keep scripts dependency-light and runnable with
  `python scripts/stars.py` from the repo root.
- Never commit `.env` or API keys.
- Don't hand-edit anything under `catalog/` — edit the generator or the data instead.
