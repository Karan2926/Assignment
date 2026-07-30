#!/usr/bin/env bash
# Nightly-style backup of DB + profile photos
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
STAMP="$(date -u +%Y%m%dT%H%M%SZ)"
OUT="${1:-$ROOT/backups}/backup-$STAMP"
mkdir -p "$OUT"

DB_PATH="${DB_PATH:-$ROOT/attendance.db}"
DATASET_DIR="${DATASET_DIR:-$ROOT/dataset}"

if [[ -f "$DB_PATH" ]]; then
  cp "$DB_PATH" "$OUT/attendance.db"
  # checkpoint WAL if present
  if [[ -f "${DB_PATH}-wal" ]]; then
    cp "${DB_PATH}-wal" "$OUT/attendance.db-wal" || true
  fi
fi

if [[ -d "$DATASET_DIR" ]]; then
  mkdir -p "$OUT/profiles"
  find "$DATASET_DIR" -type f -name 'profile.jpg' -print0 |
    while IFS= read -r -d '' f; do
      sid="$(basename "$(dirname "$f")")"
      cp "$f" "$OUT/profiles/${sid}.jpg"
    done
fi

echo "Backup written to $OUT"
