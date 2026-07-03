#!/usr/bin/env python3
"""Orchestrator: fetch stars, categorize new ones via LLM, rebuild the catalog.

Usage:
    python scripts/stars.py            # fetch, categorize new stars, rebuild catalog
    python scripts/stars.py --no-llm   # refresh metadata + rebuild, no LLM calls
    python scripts/stars.py --force    # re-categorize every repo (after taxonomy edits)
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

import catalog as catalog_mod
import github as github_mod
from categorize import DEFAULT_MODEL, CategorizeError, categorize_new

ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT / "data"
STARS_PATH = DATA_DIR / "stars.json"
CATEGORIES_PATH = DATA_DIR / "categories.json"
CATALOG_DIR = ROOT / "catalog"

# Fields the LLM owns; carried over when a repo already exists.
LLM_FIELDS = ("category", "tags", "summary", "categorized_at", "model")
# Fields refreshed from GitHub on every run.
META_FIELDS = ("url", "description", "language", "stars", "topics", "starred_at")


def load_env(root: Path) -> None:
    """Minimal .env loader (no dependency). Does not override real env vars."""
    env_file = root / ".env"
    if not env_file.exists():
        return
    for raw in env_file.read_text().splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        key, value = key.strip(), value.strip().strip('"').strip("'")
        os.environ.setdefault(key, value)


def load_stars() -> dict:
    if STARS_PATH.exists():
        return json.loads(STARS_PATH.read_text())
    return {"meta": {}, "repos": {}}


def write_stars(data: dict) -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    STARS_PATH.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n")


def main() -> int:
    parser = argparse.ArgumentParser(description="Organize GitHub stars.")
    parser.add_argument("--no-llm", action="store_true",
                        help="skip categorization; refresh metadata + rebuild catalog only")
    parser.add_argument("--force", action="store_true",
                        help="re-categorize every repo (implies LLM)")
    args = parser.parse_args()

    load_env(ROOT)
    user = os.environ.get("GH_USER", "nyokinokonoko")
    token = os.environ.get("GITHUB_TOKEN") or None
    api_key = os.environ.get("OPENROUTER_API_KEY", "")
    model = os.environ.get("OPENROUTER_MODEL", DEFAULT_MODEL)
    now = datetime.now(timezone.utc).replace(microsecond=0).isoformat()

    categories = json.loads(CATEGORIES_PATH.read_text())["categories"]

    db = load_stars()
    stored = db.get("repos", {})

    print(f"Fetching stars for '{user}'...", file=sys.stderr)
    fetched = github_mod.fetch_starred(user, token)
    fetched_by_name = {r["full_name"]: r for r in fetched}
    print(f"Fetched {len(fetched)} stars.", file=sys.stderr)

    # Diff against the stored database.
    new_names = [n for n in fetched_by_name if n not in stored]
    removed_names = [n for n in stored if n not in fetched_by_name]

    # Build the fresh repo table: refresh metadata, carry over LLM fields.
    repos: dict[str, dict] = {}
    for name, meta in fetched_by_name.items():
        entry = dict(stored.get(name, {}))
        entry["full_name"] = name
        for field in META_FIELDS:
            entry[field] = meta.get(field, entry.get(field))
        repos[name] = entry

    # Decide which repos need categorization.
    if args.force:
        to_categorize = [repos[n] for n in repos]
    else:
        to_categorize = [repos[n] for n in repos if not repos[n].get("category")]

    if args.no_llm:
        if to_categorize:
            print(f"--no-llm: skipping categorization of {len(to_categorize)} repo(s).",
                  file=sys.stderr)
    elif to_categorize:
        print(f"Categorizing {len(to_categorize)} repo(s) via {model}...", file=sys.stderr)
        try:
            results = categorize_new(to_categorize, categories, model, api_key, now)
        except CategorizeError as exc:
            print(f"ERROR: {exc}", file=sys.stderr)
            return 1
        for name, fields in results.items():
            repos[name].update(fields)
        missed = [r["full_name"] for r in to_categorize
                  if not repos[r["full_name"]].get("category")]
        if missed:
            print(f"  {len(missed)} repo(s) left uncategorized (retried next run).",
                  file=sys.stderr)

    # Persist.
    db = {
        "meta": {
            "user": user,
            "generated_at": now,
            "count": len(repos),
            "model": model,
        },
        "repos": repos,
    }
    write_stars(db)

    # Rebuild catalog from the fresh database.
    catalog_mod.generate(STARS_PATH, categories, CATALOG_DIR, user, now)

    # Refresh the Pages site data (docs/data.json).
    catalog_mod.write_site_data(STARS_PATH, ROOT / "docs", db["meta"])

    print(
        f"Done. total={len(repos)} new={len(new_names)} pruned={len(removed_names)}",
        file=sys.stderr,
    )
    if removed_names:
        print(f"  pruned: {', '.join(removed_names[:10])}"
              + (" ..." if len(removed_names) > 10 else ""), file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
