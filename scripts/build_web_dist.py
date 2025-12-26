#!/usr/bin/env python3
from __future__ import annotations

import json
import shutil
import subprocess
import sys
from pathlib import Path

ALLOWED_LYRIC_SUFFIXES = {".md", ".html", ".ipynb"}


def run(cmd: list[str]) -> None:
    subprocess.run(cmd, check=True)


def repo_root() -> Path:
    return Path(__file__).resolve().parents[1]


def write_text(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def build_manifest(root: Path, dist_dir: Path) -> None:
    run(
        [
            sys.executable,
            str(root / "scripts" / "build_manifest.py"),
            "--content",
            str(root / "content" / "lyrics"),
            "--output",
            str(dist_dir / "manifest.json"),
        ]
    )


def sync_lyrics(root: Path, dist_dir: Path) -> None:
    src_root = root / "content" / "lyrics"
    dst_root = dist_dir / "lyrics"
    if dst_root.exists():
        shutil.rmtree(dst_root)

    for src_path in src_root.rglob("*"):
        if not src_path.is_file():
            continue
        if src_path.suffix.lower() not in ALLOWED_LYRIC_SUFFIXES:
            continue
        rel = src_path.relative_to(src_root)
        dst_path = dst_root / rel
        dst_path.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src_path, dst_path)


def build_index(dist_dir: Path) -> None:
    write_text(dist_dir / "index.html", INDEX_HTML)
    write_text(dist_dir / "app.js", APP_JS)


def main() -> None:
    root = repo_root()
    dist_dir = root / "dist"
    dist_dir.mkdir(parents=True, exist_ok=True)

    build_manifest(root, dist_dir)
    sync_lyrics(root, dist_dir)
    build_index(dist_dir)

    manifest_path = dist_dir / "manifest.json"
    json.loads(manifest_path.read_text(encoding="utf-8"))
    print(f"[build_web_dist] Built GitHub Pages artifact at {dist_dir}")


INDEX_HTML = """<!doctype html>
<html lang="en">
  <head>
    <meta charset="utf-8" />
    <meta name="viewport" content="width=device-width,initial-scale=1" />
    <title>Lyrical Miracles v2</title>
    <style>
      :root { color-scheme: dark; }
      body { margin: 0; font-family: ui-sans-serif, system-ui, -apple-system, Segoe UI, Roboto, Arial, sans-serif; background: #0b1020; color: #e7eaff; }
      header { position: sticky; top: 0; z-index: 2; background: rgba(11, 16, 32, 0.95); border-bottom: 1px solid rgba(255,255,255,0.08); backdrop-filter: blur(10px); }
      header .wrap { display: flex; align-items: baseline; gap: 12px; padding: 14px 16px; }
      header h1 { font-size: 16px; margin: 0; letter-spacing: 0.2px; }
      header .meta { color: rgba(231,234,255,0.7); font-size: 12px; }
      main { display: grid; grid-template-columns: 420px 1fr; min-height: calc(100vh - 52px); }
      aside { border-right: 1px solid rgba(255,255,255,0.08); padding: 12px; overflow: auto; }
      .search { width: 100%; box-sizing: border-box; padding: 10px 12px; border-radius: 10px; border: 1px solid rgba(255,255,255,0.10); background: rgba(255,255,255,0.04); color: #e7eaff; }
      .hint { margin: 10px 2px 0; font-size: 12px; color: rgba(231,234,255,0.65); }
      .list { margin-top: 12px; display: flex; flex-direction: column; gap: 8px; }
      .release { margin-top: 10px; font-size: 12px; text-transform: uppercase; letter-spacing: 0.12em; color: rgba(231,234,255,0.55); }
      .item { display: block; padding: 10px 12px; border-radius: 12px; border: 1px solid rgba(255,255,255,0.08); background: rgba(255,255,255,0.03); color: inherit; text-decoration: none; }
      .item:hover { border-color: rgba(139,92,246,0.65); background: rgba(139,92,246,0.12); }
      .item .title { font-size: 13px; font-weight: 600; }
      .item .path { margin-top: 3px; font-size: 11px; color: rgba(231,234,255,0.6); font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, "Liberation Mono", "Courier New", monospace; }
      section { padding: 14px; overflow: auto; }
      .viewer { border: 1px solid rgba(255,255,255,0.08); border-radius: 14px; background: rgba(255,255,255,0.02); overflow: hidden; }
      .viewer header { position: static; background: rgba(255,255,255,0.03); border-bottom: 1px solid rgba(255,255,255,0.08); backdrop-filter: none; }
      .viewer header .wrap { padding: 10px 12px; }
      .viewer-title { font-size: 14px; margin: 0; }
      .viewer-actions { margin-left: auto; display: flex; gap: 8px; }
      .btn { display: inline-block; padding: 7px 10px; border-radius: 10px; border: 1px solid rgba(255,255,255,0.10); background: rgba(255,255,255,0.03); color: inherit; text-decoration: none; font-size: 12px; }
      .btn:hover { border-color: rgba(6,182,212,0.7); background: rgba(6,182,212,0.12); }
      pre { margin: 0; padding: 12px; white-space: pre-wrap; overflow-wrap: anywhere; font-size: 12px; line-height: 1.45; }
      iframe { width: 100%; height: calc(100vh - 140px); border: 0; background: #0b1020; }
      .empty { padding: 22px; color: rgba(231,234,255,0.75); }
      @media (max-width: 900px) { main { grid-template-columns: 1fr; } aside { border-right: 0; border-bottom: 1px solid rgba(255,255,255,0.08); } iframe { height: 60vh; } }
    </style>
  </head>
  <body>
    <header>
      <div class="wrap">
        <h1>Lyrical Miracles v2</h1>
        <div class="meta" id="meta">Loading…</div>
      </div>
    </header>
    <main>
      <aside>
        <input class="search" id="q" placeholder="Search titles / paths…" autocomplete="off" />
        <div class="hint">Tip: click a file to preview. HTML opens in a sandboxed iframe; Markdown shows as raw text.</div>
        <div class="list" id="list"></div>
      </aside>
      <section>
        <div class="viewer" id="viewer">
          <header>
            <div class="wrap">
              <h2 class="viewer-title" id="viewerTitle">Select an item</h2>
              <div class="viewer-actions" id="viewerActions" style="display:none;">
                <a class="btn" id="openRaw" target="_blank" rel="noreferrer">Open raw</a>
              </div>
            </div>
          </header>
          <div id="viewerBody" class="empty">Pick a lyric/notebook from the list to preview it here.</div>
        </div>
      </section>
    </main>
    <script src="./app.js"></script>
  </body>
</html>
"""


APP_JS = """(() => {
  const $ = (id) => document.getElementById(id);
  const listEl = $("list");
  const qEl = $("q");
  const metaEl = $("meta");
  const viewerTitleEl = $("viewerTitle");
  const viewerBodyEl = $("viewerBody");
  const viewerActionsEl = $("viewerActions");
  const openRawEl = $("openRaw");

  function escapeHtml(s) {
    return s.replaceAll("&", "&amp;").replaceAll("<", "&lt;").replaceAll(">", "&gt;");
  }

  function setSelected(path) {
    const url = new URL(window.location.href);
    url.hash = `#${encodeURIComponent(path)}`;
    history.replaceState(null, "", url.toString());
  }

  function getSelected() {
    if (!window.location.hash) return null;
    try {
      return decodeURIComponent(window.location.hash.slice(1));
    } catch {
      return null;
    }
  }

  async function loadText(path) {
    const res = await fetch(path);
    if (!res.ok) throw new Error(`HTTP ${res.status} for ${path}`);
    return await res.text();
  }

  function renderViewer(item, text) {
    viewerTitleEl.textContent = item.title || item.path;
    viewerActionsEl.style.display = "flex";
    openRawEl.href = `./${item.path}`;

    const ext = item.path.split(".").pop()?.toLowerCase();
    if (ext === "html") {
      viewerBodyEl.innerHTML = `<iframe sandbox="allow-same-origin" src="./${escapeHtml(item.path)}"></iframe>`;
      return;
    }

    const pretty = ext === "ipynb" ? tryPrettyJson(text) : text;
    viewerBodyEl.innerHTML = `<pre>${escapeHtml(pretty)}</pre>`;
  }

  function tryPrettyJson(text) {
    try {
      return JSON.stringify(JSON.parse(text), null, 2);
    } catch {
      return text;
    }
  }

  function groupByRelease(items) {
    const groups = new Map();
    for (const item of items) {
      const key = item.release || "unknown";
      if (!groups.has(key)) groups.set(key, []);
      groups.get(key).push(item);
    }
    return [...groups.entries()].sort((a, b) => a[0].localeCompare(b[0]));
  }

  function buildList(items) {
    listEl.innerHTML = "";
    const groups = groupByRelease(items);
    for (const [release, group] of groups) {
      const rel = document.createElement("div");
      rel.className = "release";
      rel.textContent = release;
      listEl.appendChild(rel);

      for (const item of group) {
        const a = document.createElement("a");
        a.href = `#${encodeURIComponent(item.path)}`;
        a.className = "item";
        a.innerHTML = `<div class="title">${escapeHtml(item.title || item.path.split('/').pop() || item.path)}</div><div class="path">${escapeHtml(item.path)}</div>`;
        a.addEventListener("click", (e) => {
          e.preventDefault();
          setSelected(item.path);
          openItem(item);
        });
        listEl.appendChild(a);
      }
    }
  }

  async function openItem(item) {
    try {
      const text = await loadText(`./${item.path}`);
      renderViewer(item, text);
    } catch (err) {
      viewerTitleEl.textContent = item.title || item.path;
      viewerActionsEl.style.display = "none";
      viewerBodyEl.innerHTML = `<div class="empty">Failed to load <code>${escapeHtml(item.path)}</code>: ${escapeHtml(String(err))}</div>`;
    }
  }

  function filterItems(items, query) {
    const q = query.trim().toLowerCase();
    if (!q) return items;
    return items.filter((i) => (i.title || "").toLowerCase().includes(q) || i.path.toLowerCase().includes(q));
  }

  async function init() {
    const res = await fetch("./manifest.json");
    if (!res.ok) throw new Error(`HTTP ${res.status} loading manifest.json`);
    const manifest = await res.json();

    metaEl.textContent = `${manifest.counts.content} items · generated ${manifest.generated_at}`;

    const items = (manifest.content || []).map((c) => ({
      path: c.path,
      release: c.release,
      title: c.title,
      type: c.type,
    }));

    function refresh() {
      const filtered = filterItems(items, qEl.value);
      buildList(filtered);
    }

    qEl.addEventListener("input", refresh);
    refresh();

    const selected = getSelected();
    if (selected) {
      const item = items.find((i) => i.path === selected);
      if (item) openItem(item);
    }
  }

  init().catch((err) => {
    metaEl.textContent = "Failed to load manifest";
    viewerTitleEl.textContent = "Error";
    viewerBodyEl.innerHTML = `<pre>${escapeHtml(String(err))}</pre>`;
  });
})();"""


if __name__ == "__main__":
    main()
