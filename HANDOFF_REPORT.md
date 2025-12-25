# Hand Off Report — Lyrical Miracles v2 / EverLight Archive

> Quick reference for whoever picks up the baton next. Read this first to avoid re-learning all the tribal knowledge the hard way.

---

## 1. Project Snapshot
- **Goal:** Reshape Hawk Eye's lyric + media archive into a Git-first source of truth that can feed Cloudflare R2/D1, Workers AI (Vectorize), CMS exporters, and future web/app surfaces.
- **Tech Surface:** Python scripts for manifests + normalization, Cloudflare Wrangler for infra sync, a Workers-based Vectorize ingest/search service, and lots of Markdown/IPYNB source assets under `content/`.
- **Key Credentials:** Stored in `lyrical-env.sh` (sourced before running any pipeline). Includes CF account ID, API token, R2 bucket, D1 DB, Vectorize worker URL, etc. Treat this file as sensitive.

## 2. Repository Tour
- `content/` — lyrics, articles, notebooks. Singles live at `content/lyrics/releases/HAWK-ARS-00/01_singles/`. All placeholders were replaced with real lyrics.
- `media/` — `audio/raw` and `images/raw` are synced to R2. Filenames are slug-safe post `normalize_assets`.
- `dist/` — generated artifacts: `manifest.json`, `asset_map.json`, `d1_seed.sql`, etc.
- `scripts/` — automation entry points:
  - `normalize_assets.py`
  - `build_manifest.py`
  - `autorag/ingest.py`
  - `publish_cloudflare.sh` (wraps manifest, R2 sync, D1 load).
- `platform/vectorize-worker/` — Worker code that embeds chunks and serves `/ingest` + `/search`.
- `docs/` — pipeline guide (`docs/PIPELINE.md`), TODO (`docs/NEXTSTEPS_TODO.md`).

## 3. Operational Pipelines
1. **Normalization**
   ```bash
   python3 scripts/normalize_assets.py --content content/lyrics --media media --output dist/asset_map.json
   ```
2. **Manifest Build**
   ```bash
   python3 scripts/build_manifest.py --content content --media media --data data --output dist/manifest.json --parquet dist/manifest.parquet
   ```
   - `publish_cloudflare.sh` currently scopes to `content/lyrics`, so running it trims manifest entries to 215 lyrics (still fine for ingest).
3. **Cloudflare R2 Sync**
   ```bash
   source lyrical-env.sh
   bash scripts/publish_cloudflare.sh r2
   ```
   - Uploads `media/audio/raw/**` and `media/images/raw/**` to `r2://lyrical-miracles-v2/`.
4. **Cloudflare D1 Seed**
   ```bash
   bash scripts/publish_cloudflare.sh d1
   ```
   - Generates `dist/d1_seed.sql` via `platform/infra/scripts/manifest_to_sql.py` and runs schema + data against remote D1.
   - Wrangler 4.51.0 occasionally throws `TypeError: fetch failed`; re-run usually succeeds (see last run logs).
5. **Vectorize / AutoRAG Ingestion**
   ```bash
   python3 scripts/autorag/ingest.py --manifest dist/manifest.json --content-root content
   ```
   - Uses env values (`CF_VECTORIZE_WORKER_URL`, etc.) to POST chunk batches (2,077 chunks total) to the Workers ingest endpoint.
   - Wrapper logging snippet used in the last run lives in `codex-logs.md` if needed.
6. **Workers Search**
   - Worker deployed at `lyrical-vector-ingest.omniversalmail.workers.dev`.
   - `/ingest` and `/search` both work. The zero-dimension Vectorize error was resolved on Dec 19 by normalizing embedding outputs and using the latest Vectorize query signature.

## 4. Current State (as of latest session)
- `content/lyrics/releases/HAWK-ARS-00/01_singles/*` all contain real lyrics + metadata (no placeholders anywhere).
- `dist/asset_map.json`: normalized snapshot of content/media slugs.
- `dist/manifest.json`: 215 lyric entries (lyrics only, due to CLI scope) + 305 media assets + 19 catalogs.
- **R2 Bucket (`lyrical-miracles-v2`):** All `media/audio/raw` + `media/images/raw` files uploaded via Wrangler.
- **D1 DB (`lyrical-miracles`):** Fresh schema + data import completed (542 statements, 1,836 rows written).
- **Vectorize Index (`lyrical-miracles`):** 2,077 lyric chunks embedded and upserted with metadata via the Workers ingest run.

## 5. Outstanding / Watchlist
1. **Manifest scope mismatch:** Running `scripts/build_manifest.py` manually (with `--content content`) sees 321 entries, but `publish_cloudflare.sh` (which calls the script without flags) only includes `content/lyrics`. Decide whether the manifest should cover articles/notebooks or restrict to lyrics.
2. **Wrangler version:** Worker was redeployed with Wrangler 4.56.0, but other scripts still use the default (4.51.0). Consider upgrading globally to avoid the intermittent D1 `fetch failed` warning.
3. **Parquet output:** Skipped because `pandas`/`pyarrow` aren’t installed. Install if analytics/D1 ingestion needs parquet.
4. **Automation backlog:** `docs/NEXTSTEPS_TODO.md` still lists site rebuild, exporters, cycle automation, etc.

## 6. Working With Hawk (User Notes)
- **Expect nonlinear brainstorming.** Hawk will often explore tangents or revisit earlier decisions. Keep a running list of requested outcomes and confirm priorities before deep work.
- **Translate ideas into checklists.** When Hawk says “ship everything,” break it into discrete steps and get sign-off per step; this keeps both sides oriented.
- **Surface progress frequently.** Short, high-signal updates (even mid-run) prevent loops. Screenshots/command summaries help.
- **Assume varying context retention.** Re-state key assumptions (“Manifest currently limited to lyrics…”) when revisiting a topic.
- **Be candid about blockers.** Hawk appreciates transparency—tell them when something is slow, needs credentials, or requires clarification.

## 7. Quick-Start Checklist for the Next Agent
1. `cd /home/selene/Documents/lyric-ai-tests/lyrical-miracles-v2`
2. `source lyrical-env.sh` (verify secrets still valid).
3. `python3 scripts/normalize_assets.py …` (optional sanity check).
4. `python3 scripts/build_manifest.py …` (confirm counts match expectation).
5. `bash scripts/publish_cloudflare.sh r2` if new media landed.
6. `bash scripts/publish_cloudflare.sh d1` after manifest changes.
7. `python3 scripts/autorag/ingest.py --manifest dist/manifest.json --content-root content` to refresh Vectorize.
8. Worker `/search` is fixed; if it breaks again, inspect `platform/vectorize-worker/src/index.ts` and redeploy via `wrangler deploy` under `platform/vectorize-worker`.
9. Keep `codex-logs.md` updated with any non-obvious commands or hiccups for the next person.

Stay organized, over-communicate, and we’ll keep this archive humming.
