#!/usr/bin/env python3
"""
Copy data from local SQLite (attendance.db) into PostgreSQL.

Usage:
  export DATABASE_URL=postgresql://attendance:attendance@127.0.0.1:5432/attendance
  python3 scripts/migrate_sqlite_to_postgres.py
  python3 scripts/migrate_sqlite_to_postgres.py --sqlite /path/to/attendance.db
"""

from __future__ import annotations

import argparse
import os
import sqlite3
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

TABLES = [
    "classes",
    "subjects",
    "students",
    "users",
    "enrollments",
    "teacher_assignments",
    "attendance",
    "face_embeddings",
]


def main() -> int:
    parser = argparse.ArgumentParser(description="Migrate SQLite → PostgreSQL")
    parser.add_argument(
        "--sqlite",
        default=os.environ.get("DB_PATH", os.path.join(ROOT, "attendance.db")),
        help="Source SQLite path",
    )
    args = parser.parse_args()

    url = (os.environ.get("DATABASE_URL") or "").strip()
    if url.startswith("postgres://"):
        url = "postgresql://" + url[len("postgres://") :]
    if not url.startswith("postgresql://"):
        print("Set DATABASE_URL to postgresql://... first.", file=sys.stderr)
        return 1
    if not os.path.exists(args.sqlite):
        print(f"SQLite file not found: {args.sqlite}", file=sys.stderr)
        return 1

    try:
        import psycopg
    except ImportError:
        print("Install: pip install 'psycopg[binary]'", file=sys.stderr)
        return 1

    # Import db only after DATABASE_URL is present in the environment.
    os.environ["DATABASE_URL"] = url
    import db

    if not db.USE_POSTGRES:
        print("db.USE_POSTGRES is False — abort.", file=sys.stderr)
        return 1

    db.init_db()

    src = sqlite3.connect(args.sqlite)
    src.row_factory = sqlite3.Row

    with psycopg.connect(url) as pg:
        with pg.cursor() as cur:
            for table in TABLES:
                try:
                    rows = src.execute(f"SELECT * FROM {table}").fetchall()
                except sqlite3.Error as e:
                    print(f"{table}: skip ({e})")
                    continue
                if not rows:
                    print(f"{table}: 0 rows")
                    continue
                cols = list(rows[0].keys())
                col_list = ", ".join(cols)
                placeholders = ", ".join(["%s"] * len(cols))
                cur.execute(f"TRUNCATE TABLE {table} RESTART IDENTITY CASCADE")
                sql = f"INSERT INTO {table} ({col_list}) VALUES ({placeholders})"
                for r in rows:
                    values = []
                    for c in cols:
                        v = r[c]
                        if c == "centroid" and v is not None and not isinstance(v, (bytes, memoryview)):
                            v = bytes(v)
                        values.append(v)
                    cur.execute(sql, values)
                print(f"{table}: {len(rows)} rows")

            for table in TABLES:
                if table == "face_embeddings":
                    continue
                cur.execute(
                    f"""
                    SELECT setval(
                      pg_get_serial_sequence('{table}', 'id'),
                      COALESCE((SELECT MAX(id) FROM {table}), 1),
                      true
                    )
                    """
                )
        pg.commit()

    src.close()
    print("Migration complete.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
