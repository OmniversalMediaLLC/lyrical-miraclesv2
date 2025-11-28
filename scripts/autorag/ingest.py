#!/usr/bin/env python3
"""Chunk lyric content, create embeddings via Workers AI, and upsert to Vectorize."""

from __future__ import annotations

import argparse
import html
import json
import os
import re
import sys
import time
from pathlib import Path
from typing import Dict, Iterable, List, Sequence
from urllib.parse import quote
import hashlib

import requests

DEFAULT_MODEL = "@cf/baai/bge-base-en-v1.5"
DEFAULT_CHUNK_SIZE = 1400
DEFAULT_CHUNK_OVERLAP = 200
DEFAULT_BATCH_SIZE = 32


def read_text(path: Path) -> str:
    suffix = path.suffix.lower()
    if suffix in {".md", ".txt"}:
        return path.read_text(encoding="utf-8", errors="ignore")
    if suffix == ".html":
        raw = path.read_text(encoding="utf-8", errors="ignore")
        text = re.sub(r"<[^>]+>", " ", raw)
        return html.unescape(text)
    if suffix == ".ipynb":
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            return ""
        cells = data.get("cells", [])
        parts = []
        for cell in cells:
            if cell.get("cell_type") in {"markdown", "code"}:
                parts.append("".join(cell.get("source", [])))
        return "\n".join(parts)
    return ""


def chunk_text(text: str, size: int, overlap: int) -> List[str]:
    cleaned = re.sub(r"\s+", " ", text).strip()
    if not cleaned:
        return []
    if len(cleaned) <= size:
        return [cleaned]
    chunks = []
    start = 0
    while start < len(cleaned):
        end = min(len(cleaned), start + size)
        chunks.append(cleaned[start:end])
        if end == len(cleaned):
            break
        start = max(0, end - overlap)
    return chunks


def embed_text(account_id: str, token: str, model: str, text: str) -> Sequence[float]:
    model_path = quote(model, safe="@/:")
    url = f"https://api.cloudflare.com/client/v4/accounts/{account_id}/ai/run/{model_path}"
    resp = requests.post(
        url,
        headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
        json={"text": text},
        timeout=30,
    )
    resp.raise_for_status()
    payload = resp.json()
    result = payload.get("result", {})
    data = result.get("data")
    if isinstance(data, list) and data:
        first = data[0]
        if isinstance(first, dict) and "embedding" in first:
            return first["embedding"]
        if isinstance(first, list):
            return first
    raise RuntimeError(f"Unexpected embedding response: {payload}")


def upsert_vectors(account_id: str, token: str, index: str, vectors: List[Dict]) -> None:
    url = f"https://api.cloudflare.com/client/v4/accounts/{account_id}/vectorize/indexes/{index}/upsert"
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/x-ndjson",
        "CF-Vectorize-Version": "2",
    }
    payload = "\n".join(json.dumps(vector) for vector in vectors)
    resp = requests.post(url, headers=headers, data=payload, timeout=30)
    if resp.status_code >= 400:
        print(f"[autorag] Vectorize upsert failed: {resp.text}", file=sys.stderr)
    resp.raise_for_status()
    payload = resp.json()
    if not payload.get("success", False):  # pragma: no cover
        raise RuntimeError(f"Vectorize upsert failed: {payload}")


def load_manifest_entries(manifest_path: Path, content_root: Path) -> Iterable[Dict]:
    data = json.loads(manifest_path.read_text(encoding="utf-8"))
    for entry in data.get("content", []):
        rel = entry.get("path")
        if not rel:
            continue
        suffix = Path(rel).suffix
        if suffix.lower() not in {".md", ".html", ".ipynb"}:
            continue
        source_path = content_root / rel
        if not source_path.exists():
            continue
        yield {
            "source_path": source_path,
            "release": entry.get("release"),
            "title": entry.get("title"),
            "manifest_path": rel,
        }


def send_worker_batch(worker_url: str, batch: List[Dict]) -> None:
    resp = requests.post(worker_url, headers={"Content-Type": "application/json"}, json=batch, timeout=60)
    if resp.status_code >= 400:
        print(f"[autorag] Worker ingest failed: {resp.text}", file=sys.stderr)
    resp.raise_for_status()


def process_entries(
    entries: Iterable[Dict],
    account_id: str,
    token: str,
    index: str,
    model: str,
    chunk_size: int,
    overlap: int,
    batch_size: int,
    dry_run: bool,
    worker_url: str | None,
) -> None:
    pending: List[Dict] = []
    processed = 0
    for entry in entries:
        text = read_text(entry["source_path"])
        chunks = chunk_text(text, chunk_size, overlap)
        if not chunks:
            continue
        for idx, chunk in enumerate(chunks):
            chunk_id = f"{entry['manifest_path']}#chunk-{idx}"
            metadata = {
                "path": entry["manifest_path"],
                "release": entry.get("release"),
                "title": entry.get("title"),
                "chunk_index": idx,
                "chunk_count": len(chunks),
            }
            if worker_url:
                short_id = hashlib.sha1(chunk_id.encode("utf-8")).hexdigest()[:32]
                pending.append({"id": short_id, "text": chunk, "metadata": metadata})
            else:
                if dry_run:
                    pending.append({"id": chunk_id, "values": [], "metadata": metadata})
                    continue
                embedding = embed_text(account_id, token, model, chunk)
                pending.append({"id": chunk_id, "values": embedding, "metadata": metadata})
                processed += 1
                if processed % 25 == 0:
                    print(f"[autorag] embedded {processed} chunks", flush=True)
            if len(pending) >= batch_size:
                if worker_url:
                    send_worker_batch(worker_url, pending)
                else:
                    upsert_vectors(account_id, token, index, pending)
                pending.clear()
                time.sleep(0.2)
    if not dry_run and pending:
        if worker_url:
            send_worker_batch(worker_url, pending)
        else:
            upsert_vectors(account_id, token, index, pending)
    if dry_run:
        print(f"[autorag] Dry run complete — would upload {len(pending)} chunks")
    else:
        print(f"[autorag] Finished uploading chunks", flush=True)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Ingest lyrics into Cloudflare Vectorize")
    parser.add_argument("--manifest", type=Path, default=Path("dist/manifest.json"))
    parser.add_argument("--content-root", type=Path, default=Path("content"))
    parser.add_argument("--account-id", default=os.environ.get("CF_ACCOUNT_ID"))
    parser.add_argument("--api-token", default=os.environ.get("CLOUDFLARE_API_TOKEN"))
    parser.add_argument("--vectorize-index", default=os.environ.get("CF_VECTORIZE_INDEX"))
    parser.add_argument("--model", default=os.environ.get("CF_AI_EMBED_MODEL", DEFAULT_MODEL))
    parser.add_argument("--chunk-size", type=int, default=DEFAULT_CHUNK_SIZE)
    parser.add_argument("--chunk-overlap", type=int, default=DEFAULT_CHUNK_OVERLAP)
    parser.add_argument("--batch-size", type=int, default=DEFAULT_BATCH_SIZE)
    parser.add_argument("--worker-url", default=os.environ.get("CF_VECTORIZE_WORKER_URL"), help="Optional Workers ingest endpoint")
    parser.add_argument("--dry-run", action="store_true", help="Skip API calls; report chunk counts only")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    if args.worker_url:
        missing = []
    else:
        missing = [name for name, value in (
            ("account-id", args.account_id),
            ("api-token", args.api_token),
            ("vectorize-index", args.vectorize_index),
        ) if not value]
    if missing:
        print(f"Missing required arguments: {', '.join(missing)}", file=sys.stderr)
        sys.exit(1)

    content_root = args.content_root
    entries = list(load_manifest_entries(args.manifest, content_root))
    if not entries:
        print("No content entries found — run build_manifest.py first", file=sys.stderr)
        sys.exit(1)

    process_entries(
        entries,
        account_id=args.account_id,
        token=args.api_token,
        index=args.vectorize_index,
        model=args.model,
        chunk_size=args.chunk_size,
        overlap=args.chunk_overlap,
        batch_size=args.batch_size,
        dry_run=args.dry_run,
        worker_url=args.worker_url,
    )


if __name__ == "__main__":
    main()
