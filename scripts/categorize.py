"""Categorize new starred repos via OpenRouter (batched, structured output)."""

from __future__ import annotations

import json
import sys
import time

import requests

OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"
DEFAULT_MODEL = "google/gemini-3-flash-preview"
BATCH_SIZE = 15
MAX_RETRIES = 2


class CategorizeError(RuntimeError):
    """Raised when the LLM request fails irrecoverably."""


def _system_prompt(categories: list[dict]) -> str:
    lines = "\n".join(f"- {c['name']}: {c['description']}" for c in categories)
    names = ", ".join(f'"{c["name"]}"' for c in categories)
    return (
        "You organize GitHub starred repositories into a fixed catalog.\n"
        "For each repository you are given, assign:\n"
        "  - category: EXACTLY ONE of the allowed categories below (verbatim name).\n"
        "  - tags: 2-5 short lowercase free-form tags (single words or hyphenated).\n"
        "  - summary: ONE concise sentence (max ~15 words) describing what it is/does.\n\n"
        f"Allowed categories:\n{lines}\n\n"
        f"The category MUST be one of: {names}. If nothing fits, use \"Other\".\n"
        "Respond with ONLY a JSON object of the form "
        '{"results": [{"full_name": "...", "category": "...", '
        '"tags": ["..."], "summary": "..."}, ...]} '
        "with one entry per input repository, preserving full_name exactly."
    )


def _user_prompt(batch: list[dict]) -> str:
    payload = [
        {
            "full_name": r["full_name"],
            "description": r.get("description", ""),
            "language": r.get("language", ""),
            "topics": r.get("topics", []),
        }
        for r in batch
    ]
    return "Classify these repositories:\n" + json.dumps(payload, ensure_ascii=False)


def _call_openrouter(model: str, key: str, system: str, user: str) -> str:
    body = {
        "model": model,
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
        "temperature": 0.1,
        "response_format": {"type": "json_object"},
    }
    headers = {
        "Authorization": f"Bearer {key}",
        "Content-Type": "application/json",
        "X-Title": "github-stars-catalog",
    }
    resp = requests.post(OPENROUTER_URL, headers=headers, json=body, timeout=120)
    resp.raise_for_status()
    data = resp.json()
    return data["choices"][0]["message"]["content"]


def _parse(content: str) -> list[dict]:
    """Parse the model reply into a list of result dicts, tolerating stray text."""
    text = content.strip()
    if text.startswith("```"):
        text = text.split("```", 2)[1]
        if text.startswith("json"):
            text = text[4:]
        text = text.strip()
    obj = json.loads(text)
    if isinstance(obj, dict):
        results = obj.get("results", obj.get("repositories", []))
    else:
        results = obj
    if not isinstance(results, list):
        raise ValueError("expected a list of results")
    return results


def categorize_new(
    new_repos: list[dict],
    categories: list[dict],
    model: str,
    key: str,
    now: str,
) -> dict[str, dict]:
    """Return {full_name: {category, tags, summary, categorized_at, model}}.

    Batches requests. Repos the model fails to classify are simply omitted from
    the result (they stay uncategorized and are retried on the next run).
    """
    if not key:
        raise CategorizeError(
            "OPENROUTER_API_KEY is not set. Use --no-llm to skip categorization."
        )

    valid = {c["name"] for c in categories}
    system = _system_prompt(categories)
    out: dict[str, dict] = {}

    for start in range(0, len(new_repos), BATCH_SIZE):
        batch = new_repos[start : start + BATCH_SIZE]
        by_name = {r["full_name"] for r in batch}
        n = start // BATCH_SIZE + 1
        total = (len(new_repos) + BATCH_SIZE - 1) // BATCH_SIZE
        print(f"  categorizing batch {n}/{total} ({len(batch)} repos)...", file=sys.stderr)

        results = None
        for attempt in range(1, MAX_RETRIES + 1):
            try:
                content = _call_openrouter(model, key, system, _user_prompt(batch))
                results = _parse(content)
                break
            except (requests.RequestException, ValueError, json.JSONDecodeError) as exc:
                print(f"    attempt {attempt} failed: {exc}", file=sys.stderr)
                if attempt < MAX_RETRIES:
                    time.sleep(2 * attempt)

        if results is None:
            print("    batch failed; leaving these repos for next run", file=sys.stderr)
            continue

        for item in results:
            name = item.get("full_name")
            if name not in by_name:
                continue
            category = item.get("category", "Other")
            if category not in valid:
                category = "Other"
            tags = item.get("tags") or []
            if not isinstance(tags, list):
                tags = []
            out[name] = {
                "category": category,
                "tags": [str(t).lower() for t in tags][:5],
                "summary": (item.get("summary") or "").strip(),
                "categorized_at": now,
                "model": model,
            }

    return out
