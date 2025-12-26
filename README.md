# Lyrical Miracles v2 — EverLight Archive Backbone

This folder is the cleaned, future-facing version of the `lyrical-miracles` repo. It aligns the Hawk Eye catalog with the infrastructure plan from *The Omniversal Aether* so we can:  
- ship a Git-ready archive,  
- mirror all assets into Cloudflare R2 + D1 (or Postgres), and  
- feed CMS targets (WordPress, Ghost, Drupal, Astro/Next.js) plus Workers AI / AutoRAG pipelines.

## Layout
```
lyrical-miracles-v2/
├─ content/
│  ├─ articles/          ← essays, SEO briefs, front matter
│  ├─ lyrics/            ← release folders with Markdown/HTML/IPYNB source
│  └─ notebooks/         ← creative + business notebooks (cleaned copies)
├─ media/
│  ├─ audio/raw/         ← lossless stems + masters (to sync with R2)
│  └─ images/raw/        ← cover art, promo assets, liner scans
├─ data/
│  ├─ catalogs/          ← CSV/JSON truth (music, merch, manifests)
│  └─ reference/         ← site maps, html exports, planning docs
├─ docs/                 ← operating guides (structure, pipelines, TODOs)
├─ platform/
│  ├─ exporters/         ← CMS + API push scripts (wordPress, Ghost, etc.)
│  ├─ infra/             ← IaC / Terraform / MAAS notes
│  └─ widgets/           ← client components (player, chat, embeds)
├─ scripts/              ← build + ingest automation
├─ dist/                 ← generated manifest + parquet exports
└─ media + data → future Cloudflare R2 bucket + D1/Postgres sync
```

## Quick Start
1. Drop or edit lyric markdown under `content/lyrics/releases/<release>/...`.  
2. Run `python scripts/normalize_assets.py` to enforce slug, metadata, and pointer consistency.  
3. Run `python scripts/build_manifest.py --out dist/manifest.json` to bundle lyrics, merch, media, and metadata into a single machine-readable document for CMS + AI ingestion.  
4. Upload binaries from `media/audio` + `media/images` to Cloudflare R2, saving the returned keys back into `dist/manifest.json`.  
5. Use `platform/exporters/*` to sync pages/posts into WordPress, Ghost, Drupal, or static builds.  
6. Trigger the Vectorize/AutoRAG ingest described in `docs/EverLights_autorag_guidebook.md`.

## Cloudflare Pages (Static Site)
This repo includes a tiny static browser for the lyrics archive that builds into `dist/`:

- Build locally: `python3 scripts/build_web_dist.py` then serve `dist/` (any static server).
- CI deploy: `.github/workflows/cloudflare-pages.yml` publishes `dist/` to Cloudflare Pages.
  - Set GitHub repo secrets: `CLOUDFLARE_API_TOKEN`, `CLOUDFLARE_ACCOUNT_ID`
  - Create a Cloudflare Pages project named `lyrical-miraclesv2` (or edit the workflow project name).

## Status
- Source materials imported from `~/lyrical-miracles/HAWK-ARS`.  
- TODO backlog copied into `docs/NEXTSTEPS_TODO.md`.  
- Scripts + docs are stubs—fill them out as we codify the pipeline.
