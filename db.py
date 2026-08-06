"""Database schema, migrations, and access helpers for Phase 1."""

from __future__ import annotations

import datetime
import os
import sqlite3
from contextlib import contextmanager
from typing import Any, Iterable, Optional

APP_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(APP_DIR, "attendance.db")


@contextmanager
def get_conn():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def _table_columns(conn: sqlite3.Connection, table: str) -> set[str]:
    rows = conn.execute(f"PRAGMA table_info({table})").fetchall()
    return {r[1] for r in rows}


def _ensure_columns(conn: sqlite3.Connection, table: str, columns: dict[str, str]) -> None:
    existing = _table_columns(conn, table)
    for name, decl in columns.items():
        if name not in existing:
            conn.execute(f"ALTER TABLE {table} ADD COLUMN {name} {decl}")


def init_db() -> None:
    with get_conn() as conn:
        c = conn.cursor()

        c.execute(
            """
            CREATE TABLE IF NOT EXISTS students (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                roll TEXT,
                class TEXT,
                section TEXT,
                reg_no TEXT,
                class_id INTEGER,
                created_at TEXT
            )
            """
        )
        c.execute(
            """
            CREATE TABLE IF NOT EXISTS attendance (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                student_id INTEGER,
                name TEXT,
                timestamp TEXT,
                class_id INTEGER,
                subject_id INTEGER,
                marked_by INTEGER,
                source TEXT
            )
            """
        )
        c.execute(
            """
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT UNIQUE NOT NULL,
                password_hash TEXT NOT NULL,
                role TEXT NOT NULL,
                student_id INTEGER,
                full_name TEXT,
                created_at TEXT
            )
            """
        )
        c.execute(
            """
            CREATE TABLE IF NOT EXISTS classes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                section TEXT NOT NULL DEFAULT '',
                academic_year TEXT,
                created_at TEXT
            )
            """
        )
        c.execute(
            """
            CREATE TABLE IF NOT EXISTS subjects (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                class_id INTEGER NOT NULL,
                name TEXT NOT NULL,
                code TEXT,
                created_at TEXT,
                FOREIGN KEY(class_id) REFERENCES classes(id)
            )
            """
        )
        c.execute(
            """
            CREATE TABLE IF NOT EXISTS teacher_assignments (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                class_id INTEGER NOT NULL,
                subject_id INTEGER NOT NULL,
                created_at TEXT,
                UNIQUE(user_id, class_id, subject_id),
                FOREIGN KEY(user_id) REFERENCES users(id),
                FOREIGN KEY(class_id) REFERENCES classes(id),
                FOREIGN KEY(subject_id) REFERENCES subjects(id)
            )
            """
        )
        c.execute(
            """
            CREATE TABLE IF NOT EXISTS enrollments (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                student_id INTEGER NOT NULL,
                class_id INTEGER NOT NULL,
                created_at TEXT,
                UNIQUE(student_id, class_id),
                FOREIGN KEY(student_id) REFERENCES students(id),
                FOREIGN KEY(class_id) REFERENCES classes(id)
            )
            """
        )

        _ensure_columns(
            conn,
            "students",
            {"class_id": "INTEGER"},
        )
        _ensure_columns(
            conn,
            "attendance",
            {
                "class_id": "INTEGER",
                "subject_id": "INTEGER",
                "marked_by": "INTEGER",
                "source": "TEXT",
            },
        )
        _ensure_columns(
            conn,
            "users",
            {"full_name": "TEXT"},
        )

        # Migrate free-text class/section into classes + enrollments where possible.
        students = c.execute(
            "SELECT id, class, section, class_id FROM students WHERE class IS NOT NULL AND TRIM(class) != ''"
        ).fetchall()
        for s in students:
            if s["class_id"]:
                continue
            class_name = (s["class"] or "").strip()
            section = (s["section"] or "").strip()
            existing = c.execute(
                "SELECT id FROM classes WHERE name=? AND section=?",
                (class_name, section),
            ).fetchone()
            if existing:
                class_id = existing["id"]
            else:
                now = datetime.datetime.utcnow().isoformat()
                cur = c.execute(
                    "INSERT INTO classes (name, section, academic_year, created_at) VALUES (?, ?, ?, ?)",
                    (class_name, section, None, now),
                )
                class_id = cur.lastrowid
            c.execute("UPDATE students SET class_id=? WHERE id=?", (class_id, s["id"]))
            c.execute(
                "INSERT OR IGNORE INTO enrollments (student_id, class_id, created_at) VALUES (?, ?, ?)",
                (s["id"], class_id, datetime.datetime.utcnow().isoformat()),
            )


def class_label(row: Any) -> str:
    name = row["name"] if isinstance(row, sqlite3.Row) else row[1]
    section = row["section"] if isinstance(row, sqlite3.Row) else row[2]
    if section:
        return f"{name} — Sec {section}"
    return name


def get_user_assignments(user_id: int, role: str) -> list[sqlite3.Row]:
    with get_conn() as conn:
        if role == "admin":
            return conn.execute(
                """
                SELECT ta.id, ta.user_id, ta.class_id, ta.subject_id,
                       c.name AS class_name, c.section,
                       s.name AS subject_name, s.code AS subject_code
                FROM subjects s
                JOIN classes c ON c.id = s.class_id
                LEFT JOIN teacher_assignments ta
                  ON ta.class_id = s.class_id AND ta.subject_id = s.id
                ORDER BY c.name, c.section, s.name
                """
            ).fetchall()
        return conn.execute(
            """
            SELECT ta.id, ta.user_id, ta.class_id, ta.subject_id,
                   c.name AS class_name, c.section,
                   s.name AS subject_name, s.code AS subject_code
            FROM teacher_assignments ta
            JOIN classes c ON c.id = ta.class_id
            JOIN subjects s ON s.id = ta.subject_id
            WHERE ta.user_id = ?
            ORDER BY c.name, c.section, s.name
            """,
            (user_id,),
        ).fetchall()


def teacher_can_access(user_id: int, role: str, class_id: int, subject_id: int) -> bool:
    if role == "admin":
        with get_conn() as conn:
            row = conn.execute(
                "SELECT id FROM subjects WHERE id=? AND class_id=?",
                (subject_id, class_id),
            ).fetchone()
            return row is not None
    with get_conn() as conn:
        row = conn.execute(
            """
            SELECT id FROM teacher_assignments
            WHERE user_id=? AND class_id=? AND subject_id=?
            """,
            (user_id, class_id, subject_id),
        ).fetchone()
        return row is not None


def teacher_class_ids(user_id: int, role: str) -> Optional[set[int]]:
    """None means all classes (admin)."""
    if role == "admin":
        return None
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT DISTINCT class_id FROM teacher_assignments WHERE user_id=?",
            (user_id,),
        ).fetchall()
    return {r["class_id"] for r in rows}


def list_classes_for_user(user_id: int, role: str) -> list[sqlite3.Row]:
    with get_conn() as conn:
        if role == "admin":
            return conn.execute(
                "SELECT id, name, section, academic_year FROM classes ORDER BY name, section"
            ).fetchall()
        return conn.execute(
            """
            SELECT DISTINCT c.id, c.name, c.section, c.academic_year
            FROM classes c
            JOIN teacher_assignments ta ON ta.class_id = c.id
            WHERE ta.user_id = ?
            ORDER BY c.name, c.section
            """,
            (user_id,),
        ).fetchall()


def list_subjects_for_class(user_id: int, role: str, class_id: int) -> list[sqlite3.Row]:
    with get_conn() as conn:
        if role == "admin":
            return conn.execute(
                "SELECT id, class_id, name, code FROM subjects WHERE class_id=? ORDER BY name",
                (class_id,),
            ).fetchall()
        return conn.execute(
            """
            SELECT s.id, s.class_id, s.name, s.code
            FROM subjects s
            JOIN teacher_assignments ta ON ta.subject_id = s.id
            WHERE ta.user_id=? AND s.class_id=?
            ORDER BY s.name
            """,
            (user_id, class_id),
        ).fetchall()


def student_ids_in_class(class_id: int) -> set[int]:
    with get_conn() as conn:
        rows = conn.execute(
            """
            SELECT student_id FROM enrollments WHERE class_id=?
            UNION
            SELECT id FROM students WHERE class_id=?
            """,
            (class_id, class_id),
        ).fetchall()
    return {r[0] for r in rows}


def mark_present(
    student_ids: Iterable[int],
    class_id: int,
    subject_id: int,
    marked_by: Optional[int],
    source: str = "manual",
) -> int:
    today = datetime.date.today().isoformat()
    ts = datetime.datetime.utcnow().isoformat()
    saved = 0
    with get_conn() as conn:
        c = conn.cursor()
        for sid in student_ids:
            c.execute(
                """
                SELECT id FROM attendance
                WHERE student_id=? AND class_id=? AND subject_id=? AND date(timestamp)=?
                """,
                (sid, class_id, subject_id, today),
            )
            if c.fetchone():
                continue
            row = c.execute("SELECT name FROM students WHERE id=?", (sid,)).fetchone()
            name = row["name"] if row else "Unknown"
            c.execute(
                """
                INSERT INTO attendance
                  (student_id, name, timestamp, class_id, subject_id, marked_by, source)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (sid, name, ts, class_id, subject_id, marked_by, source),
            )
            saved += 1
    return saved
