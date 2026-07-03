"""Generate the markdown catalog from stars.json. Pure — no network."""

from __future__ import annotations

import json
import re
from collections import Counter
from pathlib import Path

UNCATEGORIZED = "Uncategorized"
RECENT_COUNT = 15

# Fields the web UI needs; keeps docs/data.json slim.
SITE_FIELDS = (
    "full_name",
    "url",
    "description",
    "summary",
    "language",
    "stars",
    "tags",
    "category",
    "starred_at",
)


def slugify(name: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")
    return slug or "other"


def _escape(text: str) -> str:
    """Escape pipes/newlines so cell content can't break a markdown table."""
    return text.replace("|", "\\|").replace("\n", " ").strip()


def _category_order(categories: list[dict]) -> list[str]:
    order = [c["name"] for c in categories]
    if UNCATEGORIZED not in order:
        order.append(UNCATEGORIZED)
    return order


def _group(repos: dict[str, dict]) -> dict[str, list[dict]]:
    groups: dict[str, list[dict]] = {}
    for repo in repos.values():
        cat = repo.get("category") or UNCATEGORIZED
        groups.setdefault(cat, []).append(repo)
    # Sort each category by stars desc, then name.
    for items in groups.values():
        items.sort(key=lambda r: (-r.get("stars", 0), r["full_name"].lower()))
    return groups


def _repo_row(repo: dict) -> str:
    name = repo["full_name"]
    url = repo.get("url", f"https://github.com/{name}")
    lang = _escape(repo.get("language") or "—")
    stars = repo.get("stars", 0)
    summary = _escape(repo.get("summary") or repo.get("description") or "")
    tags = repo.get("tags") or []
    tag_str = " ".join(f"`{_escape(str(t))}`" for t in tags)
    return f"| [{_escape(name)}]({url}) | {lang} | {stars:,} | {summary} | {tag_str} |"


def _category_page(category: str, description: str, items: list[dict]) -> str:
    lines = [
        f"# {category}",
        "",
        f"_{description}_" if description else "",
        "",
        f"**{len(items)}** repositories.",
        "",
        "[← Back to index](README.md)",
        "",
        "| Repository | Language | ★ | Summary | Tags |",
        "| --- | --- | --: | --- | --- |",
    ]
    lines.extend(_repo_row(r) for r in items)
    lines.append("")
    return "\n".join(line for line in lines if line is not None)


def _index_page(
    user: str,
    generated_at: str,
    repos: dict[str, dict],
    categories: list[dict],
    groups: dict[str, list[dict]],
) -> str:
    total = len(repos)
    langs = Counter(r.get("language") or "—" for r in repos.values())

    lines = [
        "# ⭐ Stars Catalog Index",
        "",
        f"**{total}** starred repositories by [`{user}`](https://github.com/{user}?tab=stars), "
        "organized by category.",
        "",
        f"_Last updated: {generated_at}_",
        "",
        "## Categories",
        "",
        "| Category | Count |",
        "| --- | --: |",
    ]
    for name in _category_order(categories):
        items = groups.get(name)
        if not items:
            continue
        lines.append(f"| [{name}]({slugify(name)}.md) | {len(items)} |")
    lines += ["", "## Top languages", ""]
    for lang, count in langs.most_common(12):
        lines.append(f"- **{lang}** — {count}")

    # Recently starred (needs starred_at timestamps).
    recent = [r for r in repos.values() if r.get("starred_at")]
    recent.sort(key=lambda r: r["starred_at"], reverse=True)
    if recent:
        lines += ["", f"## Recently starred (latest {RECENT_COUNT})", ""]
        for repo in recent[:RECENT_COUNT]:
            date = repo["starred_at"][:10]
            cat = repo.get("category") or UNCATEGORIZED
            lines.append(
                f"- `{date}` [{repo['full_name']}]({repo.get('url')}) "
                f"— {cat}"
            )
    lines.append("")
    return "\n".join(lines)


def generate(
    stars_path: Path,
    categories: list[dict],
    catalog_dir: Path,
    user: str,
    generated_at: str,
) -> None:
    data = json.loads(stars_path.read_text())
    repos: dict[str, dict] = data.get("repos", {})
    groups = _group(repos)
    desc_by_name = {c["name"]: c.get("description", "") for c in categories}

    catalog_dir.mkdir(parents=True, exist_ok=True)

    # Remove stale generated pages so pruned/renamed categories don't linger.
    for old in catalog_dir.glob("*.md"):
        if old.name != "README.md":
            old.unlink()

    for name in _category_order(categories):
        items = groups.get(name)
        if not items:
            continue
        page = _category_page(name, desc_by_name.get(name, ""), items)
        (catalog_dir / f"{slugify(name)}.md").write_text(page)

    index = _index_page(user, generated_at, repos, categories, groups)
    (catalog_dir / "README.md").write_text(index)


def write_site_data(stars_path: Path, docs_dir: Path, meta: dict) -> None:
    """Write docs/data.json — a slim, UI-only payload for the Pages site.

    Pure and network-free. Repos are emitted as a list (easier to consume in JS),
    sorted by stars desc so the default render is stable. Only SITE_FIELDS are kept.
    """
    data = json.loads(stars_path.read_text())
    repos = data.get("repos", {})

    slim = []
    for repo in repos.values():
        entry = {k: repo.get(k) for k in SITE_FIELDS}
        entry["category"] = entry.get("category") or UNCATEGORIZED
        entry["tags"] = entry.get("tags") or []
        slim.append(entry)
    slim.sort(key=lambda r: (-(r.get("stars") or 0), (r.get("full_name") or "").lower()))

    payload = {"meta": meta, "repos": slim}
    docs_dir.mkdir(parents=True, exist_ok=True)
    (docs_dir / "data.json").write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n"
    )
