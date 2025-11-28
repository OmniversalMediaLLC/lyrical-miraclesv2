# Vectorize Worker (Ingest API)

This Worker accepts chunk payloads and handles embeddings + Vectorize upserts
without exposing the REST API directly.

Deploy:
```bash
cd platform/vectorize-worker
npm install --save-dev typescript esbuild # if needed
wrangler deploy
```

`wrangler.toml` already binds:
- `VECTORIZE_INDEX` → `lyrical-miracles`
- `AI` → Workers AI (defaults to BGE base model)

Call the Worker via `POST /ingest` with a JSON array:
```json
[
  {"id":"release/track#chunk-0","text":"...","metadata":{"release":"..."}}
]
```
The CLI script `scripts/autorag/ingest.py --worker-url https://<worker-domain>/ingest`
chunks your repo content and posts batches automatically.
