"""Fetch a user's starred repositories from the GitHub API."""

from __future__ import annotations

import sys
import time

import requests

API_ROOT = "https://api.github.com"
# The star+json media type makes each item {"starred_at": ..., "repo": {...}}.
STAR_ACCEPT = "application/vnd.github.star+json"
PER_PAGE = 100


def _headers(token: str | None) -> dict[str, str]:
    headers = {
        "Accept": STAR_ACCEPT,
        "X-GitHub-Api-Version": "2022-11-28",
        "User-Agent": "github-stars-catalog",
    }
    if token:
        headers["Authorization"] = f"Bearer {token}"
    return headers


def _normalize(item: dict) -> dict:
    """Flatten a starred-item payload into the fields we persist."""
    repo = item.get("repo", item)
    return {
        "full_name": repo["full_name"],
        "url": repo["html_url"],
        "description": repo.get("description") or "",
        "language": repo.get("language") or "",
        "stars": repo.get("stargazers_count", 0),
        "topics": repo.get("topics") or [],
        "starred_at": item.get("starred_at", ""),
    }


def fetch_starred(user: str, token: str | None = None) -> list[dict]:
    """Return all starred repos for ``user`` as normalized dicts.

    Follows the ``Link`` header for pagination and captures ``starred_at``.
    Works unauthenticated (60 req/hr) or with a token (5000 req/hr).
    """
    session = requests.Session()
    session.headers.update(_headers(token))

    url = f"{API_ROOT}/users/{user}/starred?per_page={PER_PAGE}"
    repos: list[dict] = []

    while url:
        resp = session.get(url, timeout=30)
        if resp.status_code == 403 and resp.headers.get("X-RateLimit-Remaining") == "0":
            reset = int(resp.headers.get("X-RateLimit-Reset", "0"))
            wait = max(reset - int(time.time()), 0) + 1
            print(
                f"  rate limited; sleeping {wait}s (set GITHUB_TOKEN to avoid this)",
                file=sys.stderr,
            )
            time.sleep(wait)
            continue
        resp.raise_for_status()

        page = resp.json()
        if not page:
            break
        repos.extend(_normalize(item) for item in page)
        print(f"  fetched {len(repos)} stars...", file=sys.stderr)

        url = resp.links.get("next", {}).get("url")

    return repos
