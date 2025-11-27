#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
ENV_FILE=${LYRICAL_ENV:-"$ROOT_DIR/lyrical-env.sh"}

if [[ ! -f "$ENV_FILE" ]]; then
  echo "[publish] Missing env file: $ENV_FILE" >&2
  echo "Copy lyrical-env.example.sh to lyrical-env.sh and fill in your secrets." >&2
  exit 1
fi

# shellcheck source=/dev/null
source "$ENV_FILE"

WRANGLER_BIN=${WRANGLER_BIN:-wrangler}

require_cmd() {
  if ! command -v "$1" >/dev/null 2>&1; then
    echo "[publish] Required command '$1' not found" >&2
    exit 1
  fi
}

require_var() {
  local name=$1
  if [[ -z ${!name:-} ]]; then
    echo "[publish] Missing env var $name" >&2
    exit 1
  fi
}

require_cmd "$WRANGLER_BIN"
require_cmd python3
require_cmd find

require_var CF_R2_BUCKET
require_var CF_D1_DATABASE

CONTENT_DIR="$ROOT_DIR/content/lyrics"
MEDIA_DIR="$ROOT_DIR/media"
DIST_DIR="$ROOT_DIR/dist"
SCHEMA_FILE="$ROOT_DIR/platform/infra/sql/schema.sql"
SQL_TEMP="$DIST_DIR/d1_seed.sql"

build_manifest() {
  python3 "$ROOT_DIR/scripts/build_manifest.py" --parquet "$DIST_DIR/manifest.parquet"
}

sync_r2_dir() {
  local src=$1
  local prefix=$2
  if [[ ! -d "$src" ]]; then
    echo "[publish] Skip missing dir $src"
    return
  fi
  find "$src" -type f -print0 | while IFS= read -r -d '' file; do
    rel=${file#"$src/"}
    key="$prefix/$rel"
    key=${key// /-}
    mime=$(file --mime-type -b "$file" 2>/dev/null || echo application/octet-stream)
    echo "[publish] Uploading $file → r2://$CF_R2_BUCKET/$key"
    "$WRANGLER_BIN" r2 object put "$CF_R2_BUCKET/$key" --file "$file" --content-type "$mime"
  done
}

seed_d1() {
  python3 "$ROOT_DIR/platform/infra/scripts/manifest_to_sql.py" --manifest "$DIST_DIR/manifest.json" --output "$SQL_TEMP"
  local remote_flag=""
  if [[ ${CF_USE_REMOTE_D1:-true} == true ]]; then
    remote_flag="--remote"
  fi
  "$WRANGLER_BIN" d1 execute "$CF_D1_DATABASE" $remote_flag --yes --file "$SCHEMA_FILE"
  "$WRANGLER_BIN" d1 execute "$CF_D1_DATABASE" $remote_flag --yes --file "$SQL_TEMP"
}

case "${1:-all}" in
  manifest)
    build_manifest
    ;;
  r2)
    build_manifest
    sync_r2_dir "$MEDIA_DIR/audio/raw" "${CF_R2_AUDIO_PREFIX:-audio}"
    sync_r2_dir "$MEDIA_DIR/images/raw" "${CF_R2_IMAGE_PREFIX:-images}"
    ;;
  d1)
    build_manifest
    seed_d1
    ;;
  all)
    build_manifest
    sync_r2_dir "$MEDIA_DIR/audio/raw" "${CF_R2_AUDIO_PREFIX:-audio}"
    sync_r2_dir "$MEDIA_DIR/images/raw" "${CF_R2_IMAGE_PREFIX:-images}"
    seed_d1
    ;;
  *)
    echo "Usage: $0 [manifest|r2|d1|all]" >&2
    exit 1
    ;;
 esac
