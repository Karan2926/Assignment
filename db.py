"""Database schema, migrations, and access helpers — college scale."""

from __future__ import annotations

import datetime
import os
import sqlite3
from contextlib import contextmanager
from typing import Any, Iterable, Optional

import config

APP_DIR = config.APP_DIR
DB_PATH = config.DB_PATH


@contextmanager
def get_conn():
    conn = sqlite3.connect(DB_PATH, timeout=30)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA synchronous=NORMAL")
    conn.execute("PRAGMA foreign_keys=ON")
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
        # Production: store face centroids in DB (~2KB/student), not 48 JPEGs forever.
        c.execute(
            """
            CREATE TABLE IF NOT EXISTS face_embeddings (
                student_id INTEGER PRIMARY KEY,
                centroid BLOB NOT NULL,
                dim INTEGER NOT NULL,
                sample_count INTEGER NOT NULL DEFAULT 0,
                updated_at TEXT,
                FOREIGN KEY(student_id) REFERENCES students(id)
            )
            """
        )

        # Indexes for ~7000 students / heavy attendance reads
        c.execute(
            "CREATE INDEX IF NOT EXISTS idx_attendance_lookup ON attendance(student_id, class_id, subject_id, timestamp)"
        )
        c.execute(
            "CREATE INDEX IF NOT EXISTS idx_attendance_class_day ON attendance(class_id, subject_id, timestamp)"
        )
        c.execute("CREATE INDEX IF NOT EXISTS idx_students_roll ON students(roll)")
        c.execute("CREATE INDEX IF NOT EXISTS idx_students_class ON students(class_id)")
        c.execute(
            "CREATE INDEX IF NOT EXISTS idx_enrollments_class ON enrollments(class_id, student_id)"
        )
        c.execute(
            "CREATE INDEX IF NOT EXISTS idx_assignments_user ON teacher_assignments(user_id)"
        )

        _ensure_columns(
            conn,
            "attendance",
            {"attendance_day": "TEXT"},
        )

        # Backfill attendance_day from timestamp for older rows
        c.execute(
            """
            UPDATE attendance
            SET attendance_day = date(timestamp)
            WHERE attendance_day IS NULL AND timestamp IS NOT NULL
            """
        )

        # Enforce one present mark per student/class/subject/day (critical under concurrency)
        c.execute(
            """
            CREATE UNIQUE INDEX IF NOT EXISTS uq_attendance_day
            ON attendance(student_id, class_id, subject_id, attendance_day)
            WHERE student_id IS NOT NULL
              AND class_id IS NOT NULL
              AND subject_id IS NOT NULL
              AND attendance_day IS NOT NULL
            """
        )

        # Prefer unique rolls when present (ignore blank)
        c.execute(
            """
            CREATE UNIQUE INDEX IF NOT EXISTS uq_students_roll
            ON students(roll)
            WHERE roll IS NOT NULL AND TRIM(roll) != ''
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
            row = c.execute("SELECT name FROM students WHERE id=?", (sid,)).fetchone()
            name = row["name"] if row else "Unknown"
            try:
                c.execute(
                    """
                    INSERT INTO attendance
                      (student_id, name, timestamp, class_id, subject_id, marked_by, source, attendance_day)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (sid, name, ts, class_id, subject_id, marked_by, source, today),
                )
                if c.rowcount:
                    saved += 1
            except sqlite3.IntegrityError:
                # Already marked today for this class+subject
                continue
    return saved


def teacher_can_manage_student(user_id: int, role: str, student_id: int) -> bool:
    """True if admin, or teacher assigned to a class this student is enrolled in."""
    if role == "admin":
        return True
    class_ids = teacher_class_ids(user_id, role)
    if not class_ids:
        return False
    enrolled = set()
    with get_conn() as conn:
        rows = conn.execute(
            """
            SELECT class_id FROM enrollments WHERE student_id=?
            UNION
            SELECT class_id FROM students WHERE id=? AND class_id IS NOT NULL
            """,
            (student_id, student_id),
        ).fetchall()
        enrolled = {r[0] for r in rows}
    return bool(enrolled & class_ids)


def delete_student_cascade(student_id: int) -> None:
    with get_conn() as conn:
        conn.execute("DELETE FROM face_embeddings WHERE student_id=?", (student_id,))
        conn.execute("DELETE FROM enrollments WHERE student_id=?", (student_id,))
        conn.execute("DELETE FROM attendance WHERE student_id=?", (student_id,))
        conn.execute("DELETE FROM users WHERE student_id=?", (student_id,))
        conn.execute("DELETE FROM students WHERE id=?", (student_id,))


def upsert_face_centroid(student_id: int, centroid, sample_count: int) -> None:
    """Persist a L2-normalized embedding centroid (float32 bytes)."""
    import numpy as np

    vec = np.asarray(centroid, dtype=np.float32).reshape(-1)
    now = datetime.datetime.utcnow().isoformat()
    with get_conn() as conn:
        conn.execute(
            """
            INSERT INTO face_embeddings (student_id, centroid, dim, sample_count, updated_at)
            VALUES (?, ?, ?, ?, ?)
            ON CONFLICT(student_id) DO UPDATE SET
              centroid=excluded.centroid,
              dim=excluded.dim,
              sample_count=excluded.sample_count,
              updated_at=excluded.updated_at
            """,
            (int(student_id), vec.tobytes(), int(vec.size), int(sample_count), now),
        )


def load_face_centroids(allowed_ids: Optional[Iterable[int]] = None) -> dict[int, Any]:
    """Return {student_id: np.float32 vector} optionally filtered to a class roster."""
    import numpy as np

    with get_conn() as conn:
        if allowed_ids is None:
            rows = conn.execute(
                "SELECT student_id, centroid, dim FROM face_embeddings"
            ).fetchall()
        else:
            ids = list({int(x) for x in allowed_ids})
            if not ids:
                return {}
            placeholders = ",".join("?" * len(ids))
            rows = conn.execute(
                f"SELECT student_id, centroid, dim FROM face_embeddings WHERE student_id IN ({placeholders})",
                ids,
            ).fetchall()

    out = {}
    for r in rows:
        vec = np.frombuffer(r["centroid"], dtype=np.float32)
        if r["dim"] and len(vec) == r["dim"]:
            out[int(r["student_id"])] = vec.copy()
    return out


def face_embedding_count() -> int:
    with get_conn() as conn:
        row = conn.execute("SELECT COUNT(*) AS n FROM face_embeddings").fetchone()
    return int(row["n"] if row else 0)
