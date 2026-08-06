#!/usr/bin/env bash
# Backup DB (Postgres preferred) + profile photos
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
STAMP="$(date -u +%Y%m%dT%H%M%SZ)"
OUT="${1:-$ROOT/backups}/backup-$STAMP"
mkdir -p "$OUT"

# Load .env if present (does not override existing env)
if [[ -f "$ROOT/.env" ]]; then
  set -a
  # shellcheck disable=SC1091
  source "$ROOT/.env"
  set +a
fi

DB_PATH="${DB_PATH:-$ROOT/attendance.db}"
DATASET_DIR="${DATASET_DIR:-$ROOT/dataset}"
DATABASE_URL="${DATABASE_URL:-}"

if [[ -n "$DATABASE_URL" && "$DATABASE_URL" == postgres* ]]; then
  if command -v pg_dump >/dev/null 2>&1; then
    pg_dump "$DATABASE_URL" -Fc -f "$OUT/attendance.dump"
    echo "Postgres dump → $OUT/attendance.dump"
  elif command -v docker >/dev/null 2>&1 && docker compose ps db 2>/dev/null | grep -q Up; then
    docker compose exec -T db pg_dump -U attendance -d attendance -Fc > "$OUT/attendance.dump"
    echo "Postgres dump (docker) → $OUT/attendance.dump"
  else
    echo "WARN: DATABASE_URL set but pg_dump / docker db not available" >&2
  fi
elif [[ -f "$DB_PATH" ]]; then
  cp "$DB_PATH" "$OUT/attendance.db"
  if [[ -f "${DB_PATH}-wal" ]]; then
    cp "${DB_PATH}-wal" "$OUT/attendance.db-wal" || true
  fi
  echo "SQLite copy → $OUT/attendance.db"
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
