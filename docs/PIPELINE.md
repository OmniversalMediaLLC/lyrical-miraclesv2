# Content → Cloudflare → CMS → AI Pipeline

1. **Author / Update Content**  
   - Write or edit lyrics + essays under `content/`.  
   - Drop new audio/images into `media/` (temporary home before R2 upload).

2. **Normalize Assets**  
   ```bash
   python scripts/normalize_assets.py --content content/lyrics --media media
   ```
   - Ensures consistent slugs, required metadata, and creates `dist/asset_map.json` with the file → slug mapping.

3. **Build the Manifest**  
   ```bash
   python scripts/build_manifest.py --content content --data data --output dist/manifest.json --parquet dist/manifest.parquet
   ```
   - Combines lyric metadata, merch/product CSVs, and local media pointers.  
   - Outputs JSON + Parquet for ingestion into databases and Vectorize.

4. **Publish Binaries to Cloudflare R2**  
   - Use `r2 sync media/audio/raw r2://lyrical-miracles/audio` (or Workers CLI).  
   - Update `dist/asset_map.json` with the resulting object keys (e.g., `r2://.../reincarnated-2-resist.flac`).

5. **Load Structured Data into D1/Postgres**  
   - Run a load job (to be scripted under `platform/infra/`) that ingests `dist/manifest.parquet`.  
   - Tables: `releases`, `tracks`, `media_assets`, `articles`, `merch_products`.

6. **Push to Target CMS / Front-Ends**  
   - `platform/exporters/wordpress.py manifest dist/manifest.json`.  
   - Additional exporters (Ghost, Drupal, Astro/Next.js) read from the same manifest so every surface stays consistent.

7. **Vectorize / AutoRAG**  
  - Use `scripts/autorag/ingest.py` to split lyrics + essays. Set `CF_VECTORIZE_WORKER_URL=https://<worker>/ingest` to post batches to the Workers ingest endpoint (which performs embeddings + upserts).  
  - Fallback mode (no Worker URL) calls the Workers AI + Vectorize REST APIs directly (requires `CF_ACCOUNT_ID`, `CLOUDFLARE_API_TOKEN`, `CF_VECTORIZE_INDEX`, `CF_AI_EMBED_MODEL`).  
  - Example: `source lyrical-env.sh && python scripts/autorag/ingest.py --chunk-size 1500 --chunk-overlap 200 --worker-url https://lyrical-vector-ingest.selene.workers.dev/ingest`  
  - Requires `requests` (`pip install requests`).  
  - Store chunk IDs and metadata alongside track IDs for the site chatbot + search.

8. **Deploy UI / Widgets**  
   - Astro/Next.js site pulls from the API (Workers) or static manifest.  
   - WordPress/Drupal/Ghost use exporters.  
   - `platform/widgets/` components embed lyrics, media players, and the Workers AI chat.

9. **Continuous Delivery**  
  - Add a CI workflow (`.github/workflows/pipeline.yml`) to run steps 2–7 on every `main` push.  
  - Failing validations block deployments; R2 + Vectorize uploads happen after manifests succeed.

---

## Helper Script

`scripts/publish_cloudflare.sh` orchestrates steps 2–6. Copy `lyrical-env.example.sh`
to `lyrical-env.sh`, fill in your Cloudflare credentials, then run:

```bash
bash scripts/publish_cloudflare.sh manifest   # regenerate manifest + parquet
bash scripts/publish_cloudflare.sh r2         # sync audio/images to R2
bash scripts/publish_cloudflare.sh d1         # seed Cloudflare D1 with manifest data
bash scripts/publish_cloudflare.sh all        # do everything in one run
```
