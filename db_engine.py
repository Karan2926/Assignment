"""
SQLite (local) + PostgreSQL (college production) connection adapter.

Keep writing SQL with `?` placeholders like SQLite.
When DATABASE_URL is postgres, this layer:
  - converts ? → %s
  - rewrites INSERT OR IGNORE → ON CONFLICT DO NOTHING
  - adds RETURNING id for lastrowid on inserts
"""

from __future__ import annotations

import re
import sqlite3
from contextlib import contextmanager
from typing import Any, Iterable, Optional, Sequence

import config

_URL = (config.DATABASE_URL or "").strip()
if _URL.startswith("postgres://"):
    _URL = "postgresql://" + _URL[len("postgres://") :]

USE_POSTGRES = _URL.startswith("postgresql://")
DATABASE_URL = _URL

# Unified integrity error for callers (mark_present, unique rolls, etc.)
if USE_POSTGRES:
    try:
        import psycopg

        IntegrityError = psycopg.IntegrityError
    except ImportError as e:  # pragma: no cover
        raise SystemExit(
            "DATABASE_URL is PostgreSQL but psycopg is not installed. "
            "Run: pip install 'psycopg[binary]'"
        ) from e
else:
    IntegrityError = sqlite3.IntegrityError


class Row:
    """sqlite3.Row-like: supports row['col'] and row[0]."""

    __slots__ = ("_fields", "_values", "_map")

    def __init__(self, fields: Sequence[str], values: Sequence[Any]):
        self._fields = list(fields)
        self._values = list(values)
        self._map = dict(zip(self._fields, self._values))

    def __getitem__(self, key):
        if isinstance(key, int):
            return self._values[key]
        return self._map[key]

    def __contains__(self, key):
        return key in self._map

    def keys(self):
        return self._fields

    def __repr__(self) -> str:
        return f"Row({self._map!r})"


def adapt_sql(sql: str) -> str:
    if not USE_POSTGRES:
        return sql

    original = sql
    had_or_ignore = bool(re.search(r"INSERT\s+OR\s+IGNORE\s+INTO", original, re.I))
    sql = re.sub(
        r"INSERT\s+OR\s+IGNORE\s+INTO",
        "INSERT INTO",
        original,
        flags=re.IGNORECASE,
    )
    if had_or_ignore and "ON CONFLICT" not in sql.upper():
        sql = sql.rstrip().rstrip(";") + " ON CONFLICT DO NOTHING"

    # ISO text timestamps: make leftover date(col) safe on Postgres
    sql = re.sub(
        r"\bdate\(([^)]+)\)",
        r"CAST(substr(\1, 1, 10) AS date)",
        sql,
        flags=re.IGNORECASE,
    )

    sql = re.sub(r"\?(?!\?)", "%s", sql)
    return sql


class CursorWrapper:
    def __init__(self, conn: "ConnectionWrapper"):
        self._conn = conn
        self._cur = conn._raw.cursor()
        self.lastrowid: Optional[int] = None
        self.rowcount: int = -1
        self.description = None

    def execute(self, sql: str, params: Optional[Iterable[Any]] = None):
        params = tuple(params) if params is not None else ()
        original = sql
        sql_pg = adapt_sql(sql)

        returning = False
        if (
            USE_POSTGRES
            and re.match(r"^\s*INSERT\s+INTO", sql_pg, re.I)
            and "RETURNING" not in sql_pg.upper()
            and "ON CONFLICT DO NOTHING" not in sql_pg.upper()
            and "face_embeddings" not in sql_pg.lower()
        ):
            # lastrowid support for serial id tables
            sql_pg = sql_pg.rstrip().rstrip(";") + " RETURNING id"
            returning = True

        if USE_POSTGRES:
            self._cur.execute(sql_pg, params)
        else:
            self._cur.execute(original, params)

        self.description = self._cur.description
        self.rowcount = self._cur.rowcount if self._cur.rowcount is not None else -1

        if USE_POSTGRES and returning:
            row = self._cur.fetchone()
            self.lastrowid = int(row[0]) if row else None
        elif not USE_POSTGRES:
            self.lastrowid = self._cur.lastrowid
        else:
            self.lastrowid = None

        return self

    def executemany(self, sql: str, seq_of_params):
        sql_use = adapt_sql(sql) if USE_POSTGRES else sql
        self._cur.executemany(sql_use, seq_of_params)
        self.rowcount = self._cur.rowcount
        return self

    def _wrap_row(self, row):
        if row is None:
            return None
        if not USE_POSTGRES:
            return row
        if self._cur.description is None:
            return row
        fields = [d.name for d in self._cur.description]
        if isinstance(row, dict):
            return Row(fields, [row.get(f) for f in fields])
        return Row(fields, row)

    def fetchone(self):
        return self._wrap_row(self._cur.fetchone())

    def fetchall(self):
        rows = self._cur.fetchall()
        return [self._wrap_row(r) for r in rows]

    def close(self):
        self._cur.close()


class ConnectionWrapper:
    def __init__(self, raw):
        self._raw = raw

    def cursor(self):
        return CursorWrapper(self)

    def execute(self, sql: str, params: Optional[Iterable[Any]] = None):
        cur = self.cursor()
        cur.execute(sql, params)
        return cur

    def commit(self):
        self._raw.commit()

    def rollback(self):
        self._raw.rollback()

    def close(self):
        self._raw.close()


@contextmanager
def get_conn():
    if USE_POSTGRES:
        import psycopg

        raw = psycopg.connect(DATABASE_URL)
        conn = ConnectionWrapper(raw)
        try:
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()
    else:
        raw = sqlite3.connect(config.DB_PATH, timeout=30)
        raw.row_factory = sqlite3.Row
        raw.execute("PRAGMA journal_mode=WAL")
        raw.execute("PRAGMA synchronous=NORMAL")
        raw.execute("PRAGMA foreign_keys=ON")
        conn = ConnectionWrapper(raw)
        try:
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()


def table_columns(conn: ConnectionWrapper, table: str) -> set[str]:
    if USE_POSTGRES:
        rows = conn.execute(
            """
            SELECT column_name
            FROM information_schema.columns
            WHERE table_schema = 'public' AND table_name = ?
            """,
            (table,),
        ).fetchall()
        return {r[0] for r in rows}

    rows = conn.execute(f"PRAGMA table_info({table})").fetchall()
    return {r[1] for r in rows}


def ensure_columns(conn: ConnectionWrapper, table: str, columns: dict[str, str]) -> None:
    existing = table_columns(conn, table)
    for name, decl in columns.items():
        if name in existing:
            continue
        col_decl = decl
        if USE_POSTGRES:
            col_decl = decl.replace("BLOB", "BYTEA").replace("INTEGER", "INTEGER").replace("TEXT", "TEXT")
        conn.execute(f"ALTER TABLE {table} ADD COLUMN {name} {col_decl}")
