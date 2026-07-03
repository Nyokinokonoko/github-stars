"use strict";

/* ===== Palette maps ===== */
// Category → accent color (brand accents first, harmonized extensions after).
const CATEGORY_COLORS = {
  "AI & LLM Tools": "#e6266f",            // magenta
  "CLI & Terminal": "#0f6f97",            // deep blue
  "System Monitoring": "#4ebac6",         // teal
  "Self-Hosted Apps": "#9acc6d",          // green
  "Developer Tools": "#f3c122",           // amber
  "Web & Frontend": "#7b61ff",
  "Mobile & Desktop Apps": "#ff7a45",
  "Game Dev & Unity": "#2bb673",
  "Libraries & SDKs": "#3d7dd8",
  "Security & Secrets": "#d64545",
  "Blogs, Themes & Static Sites": "#b06fd6",
  "File Sharing & Transfer": "#17a2b8",
  "Learning & Reference": "#e08e0b",
  "Other": "#8a8a80",
  "Uncategorized": "#8a8a80",
};
const catColor = (c) => CATEGORY_COLORS[c] || "#8a8a80";

// Common GitHub language colors; unknown → neutral.
const LANG_COLORS = {
  TypeScript: "#3178c6", JavaScript: "#f1e05a", Python: "#3572a5", "C#": "#178600",
  Go: "#00add8", Rust: "#dea584", Swift: "#f05138", "C++": "#f34b7d", C: "#555555",
  Java: "#b07219", Ruby: "#701516", PHP: "#4f5d95", Shell: "#89e051", Lua: "#000080",
  Dart: "#00b4ab", Vue: "#41b883", Svelte: "#ff3e00", HTML: "#e34c26", CSS: "#563d7c",
  SCSS: "#c6538c", Astro: "#ff5a03", Kotlin: "#a97bff", "Jupyter Notebook": "#da5b0b",
  QML: "#44a51c", Zig: "#ec915c", Elixir: "#6e4a7e", Haskell: "#5e5086",
  ShaderLab: "#222c37", EJS: "#a91e50", Nix: "#7e7eff", PowerShell: "#012456",
};
const langColor = (l) => LANG_COLORS[l] || "var(--text-dim)";

/* ===== State ===== */
const state = { q: "", category: "All", language: "All", tags: new Set(), sort: "stars" };
let REPOS = [];
let META = {};
let CATEGORY_ORDER = []; // pill order, stable (by total count desc)

/* ===== DOM ===== */
const $ = (id) => document.getElementById(id);
const els = {};

/* ===== Utilities ===== */
function escapeHTML(s) {
  return String(s == null ? "" : s)
    .replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;").replace(/'/g, "&#39;");
}
const fmt = new Intl.NumberFormat("en-US");
function debounce(fn, ms) {
  let t;
  return (...a) => { clearTimeout(t); t = setTimeout(() => fn(...a), ms); };
}
function haystack(r) {
  return (
    r.full_name + " " + (r.description || "") + " " + (r.summary || "") + " " +
    (r.tags || []).join(" ") + " " + (r.language || "")
  ).toLowerCase();
}

/* ===== URL hash state ===== */
function writeHash() {
  const p = new URLSearchParams();
  if (state.q) p.set("q", state.q);
  if (state.category !== "All") p.set("cat", state.category);
  if (state.language !== "All") p.set("lang", state.language);
  if (state.sort !== "stars") p.set("sort", state.sort);
  if (state.tags.size) p.set("tags", [...state.tags].join(","));
  const hash = p.toString();
  history.replaceState(null, "", hash ? "#" + hash : location.pathname + location.search);
}
function readHash() {
  const p = new URLSearchParams(location.hash.replace(/^#/, ""));
  state.q = p.get("q") || "";
  state.category = p.get("cat") || "All";
  state.language = p.get("lang") || "All";
  state.sort = p.get("sort") || "stars";
  state.tags = new Set((p.get("tags") || "").split(",").filter(Boolean));
}

/* ===== Filtering ===== */
function matchesText(r, tokens) {
  if (!tokens.length) return true;
  const h = haystack(r);
  return tokens.every((t) => h.includes(t));
}
function passNonCategory(r, tokens) {
  if (!matchesText(r, tokens)) return false;
  if (state.language !== "All" && (r.language || "") !== state.language) return false;
  for (const t of state.tags) if (!(r.tags || []).includes(t)) return false;
  return true;
}
function sortRepos(list) {
  const s = state.sort;
  const arr = list.slice();
  if (s === "name") {
    arr.sort((a, b) => a.full_name.toLowerCase().localeCompare(b.full_name.toLowerCase()));
  } else if (s === "recent") {
    arr.sort((a, b) => (b.starred_at || "").localeCompare(a.starred_at || ""));
  } else {
    arr.sort((a, b) => (b.stars || 0) - (a.stars || 0) ||
      a.full_name.toLowerCase().localeCompare(b.full_name.toLowerCase()));
  }
  return arr;
}

/* ===== Rendering ===== */
function renderPills(base) {
  const counts = {};
  for (const r of base) counts[r.category] = (counts[r.category] || 0) + 1;
  const parts = [
    `<button class="pill" data-cat="All" aria-pressed="${state.category === "All"}">All<span class="count">${fmt.format(base.length)}</span></button>`,
  ];
  for (const cat of CATEGORY_ORDER) {
    const n = counts[cat] || 0;
    parts.push(
      `<button class="pill" data-cat="${escapeHTML(cat)}" aria-pressed="${state.category === cat}" ` +
      `style="--cat:${catColor(cat)}">${escapeHTML(cat)}<span class="count">${fmt.format(n)}</span></button>`
    );
  }
  els.categories.innerHTML = parts.join("");
}

function renderActiveTags() {
  if (!state.tags.size) { els.activeTags.hidden = true; els.activeTags.innerHTML = ""; return; }
  els.activeTags.hidden = false;
  const chips = [...state.tags].map(
    (t) => `<button class="tag-chip" data-tag="${escapeHTML(t)}">${escapeHTML(t)}</button>`
  );
  els.activeTags.innerHTML = `<span class="label">Tags:</span>` + chips.join("");
}

function cardHTML(r) {
  const owner = r.full_name.split("/")[0];
  const name = r.full_name.slice(owner.length + 1);
  const summary = r.summary || r.description || "";
  const summaryClass = r.summary ? "summary" : "summary dim";
  const tags = (r.tags || []).map(
    (t) => `<button class="tag" data-tag="${escapeHTML(t)}">${escapeHTML(t)}</button>`
  ).join("");
  const lang = r.language
    ? `<span class="lang"><span class="lang-dot" style="--lang-color:${langColor(r.language)}"></span>${escapeHTML(r.language)}</span>`
    : "";
  return (
    `<article class="card">` +
      `<div class="card-top">` +
        `<button class="badge" data-cat="${escapeHTML(r.category)}" style="--cat:${catColor(r.category)}">${escapeHTML(r.category)}</button>` +
        `<span class="stars"><span class="icon">★</span> ${fmt.format(r.stars || 0)}</span>` +
      `</div>` +
      `<h2><a href="${escapeHTML(r.url)}" target="_blank" rel="noopener">` +
        `<span class="owner">${escapeHTML(owner)}/</span>${escapeHTML(name)}</a></h2>` +
      `<p class="${summaryClass}">${escapeHTML(summary) || "No description."}</p>` +
      `<div class="card-foot">${lang}<div class="tags">${tags}</div></div>` +
    `</article>`
  );
}

function render() {
  const tokens = state.q.toLowerCase().split(/\s+/).filter(Boolean);
  const base = REPOS.filter((r) => passNonCategory(r, tokens));
  renderPills(base);
  renderActiveTags();

  let filtered = state.category === "All" ? base : base.filter((r) => r.category === state.category);
  filtered = sortRepos(filtered);

  els.resultCount.textContent =
    `${fmt.format(filtered.length)} of ${fmt.format(REPOS.length)} repositories`;

  if (!filtered.length) {
    els.results.innerHTML = "";
    els.empty.hidden = false;
  } else {
    els.empty.hidden = true;
    els.results.innerHTML = filtered.map(cardHTML).join("");
  }

  // Reflect control values.
  els.search.value = state.q;
  els.language.value = state.language;
  els.sort.value = state.sort;
  writeHash();
}

/* ===== Events ===== */
function setCategory(cat) { state.category = state.category === cat ? "All" : cat; render(); }
function toggleTag(tag) {
  if (state.tags.has(tag)) state.tags.delete(tag); else state.tags.add(tag);
  render();
}

function wireEvents() {
  els.search.addEventListener("input", debounce((e) => {
    state.q = e.target.value.trim();
    render();
  }, 120));
  els.language.addEventListener("change", (e) => { state.language = e.target.value; render(); });
  els.sort.addEventListener("change", (e) => { state.sort = e.target.value; render(); });

  els.categories.addEventListener("click", (e) => {
    const b = e.target.closest(".pill");
    if (b) setCategory(b.dataset.cat);
  });
  els.results.addEventListener("click", (e) => {
    const tag = e.target.closest(".tag");
    if (tag) { toggleTag(tag.dataset.tag); return; }
    const badge = e.target.closest(".badge");
    if (badge) setCategory(badge.dataset.cat);
  });
  els.activeTags.addEventListener("click", (e) => {
    const chip = e.target.closest(".tag-chip");
    if (chip) toggleTag(chip.dataset.tag);
  });
  els.clearFilters.addEventListener("click", () => {
    state.q = ""; state.category = "All"; state.language = "All"; state.tags.clear();
    render();
  });

  els.themeToggle.addEventListener("click", () => {
    const dark = document.documentElement.dataset.theme !== "dark";
    document.documentElement.dataset.theme = dark ? "dark" : "light";
    try { localStorage.setItem("theme", dark ? "dark" : "light"); } catch (e) {}
  });

  window.addEventListener("hashchange", () => { readHash(); render(); });
}

function populateLanguages() {
  const counts = {};
  for (const r of REPOS) if (r.language) counts[r.language] = (counts[r.language] || 0) + 1;
  const langs = Object.keys(counts).sort((a, b) => counts[b] - counts[a] || a.localeCompare(b));
  const opts = [`<option value="All">All languages</option>`].concat(
    langs.map((l) => `<option value="${escapeHTML(l)}">${escapeHTML(l)} (${counts[l]})</option>`)
  );
  els.language.innerHTML = opts.join("");
}

function computeCategoryOrder() {
  const counts = {};
  for (const r of REPOS) counts[r.category] = (counts[r.category] || 0) + 1;
  CATEGORY_ORDER = Object.keys(counts).sort((a, b) => counts[b] - counts[a] || a.localeCompare(b));
}

/* ===== Init ===== */
async function init() {
  ["categories", "activeTags", "results", "empty", "resultCount", "search",
   "language", "sort", "themeToggle", "clearFilters", "tagline", "footerMeta"]
    .forEach((k) => {
      const idMap = {
        activeTags: "active-tags", resultCount: "result-count",
        themeToggle: "theme-toggle", clearFilters: "clear-filters",
        footerMeta: "footer-meta",
      };
      els[k] = $(idMap[k] || k);
    });

  els.results.innerHTML = `<div class="loading">Loading catalog…</div>`;
  try {
    const resp = await fetch("data.json", { cache: "no-cache" });
    if (!resp.ok) throw new Error("HTTP " + resp.status);
    const data = await resp.json();
    REPOS = data.repos || [];
    META = data.meta || {};
  } catch (err) {
    els.results.innerHTML = `<div class="loading">Failed to load data.json (${escapeHTML(err.message)}).</div>`;
    return;
  }

  const count = REPOS.length;
  els.tagline.textContent = `${fmt.format(count)} starred repositories · ${META.user || ""}`;
  els.search.placeholder = `Search ${fmt.format(count)} repos… (name, summary, tag, language)`;
  const updated = (META.generated_at || "").slice(0, 10);
  els.footerMeta.textContent = `${fmt.format(count)} repos · updated ${updated || "—"} · model ${META.model || "—"}`;

  computeCategoryOrder();
  populateLanguages();
  readHash();
  wireEvents();
  render();
}

document.addEventListener("DOMContentLoaded", init);
