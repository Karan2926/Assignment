"""Seed an admin user and optional demo class/subject/teacher for Phase 1."""

from __future__ import annotations

import argparse
import datetime
import os
import sys

from werkzeug.security import generate_password_hash

# Allow running from repo root
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import db  # noqa: E402


def seed(admin_user: str, admin_pass: str, with_demo: bool) -> None:
    db.init_db()
    now = datetime.datetime.utcnow().isoformat()

    with db.get_conn() as conn:
        existing = conn.execute(
            "SELECT id FROM users WHERE username=?", (admin_user,)
        ).fetchone()
        if existing:
            print(f"Admin '{admin_user}' already exists (id={existing['id']})")
            admin_id = existing["id"]
        else:
            cur = conn.execute(
                """
                INSERT INTO users (username, password_hash, role, student_id, full_name, created_at)
                VALUES (?, ?, 'admin', NULL, 'System Admin', ?)
                """,
                (admin_user, generate_password_hash(admin_pass), now),
            )
            admin_id = cur.lastrowid
            print(f"Created admin '{admin_user}' (id={admin_id})")

        if not with_demo:
            return

        class_row = conn.execute(
            "SELECT id FROM classes WHERE name=? AND section=?",
            ("B.Tech CSE", "A"),
        ).fetchone()
        if class_row:
            class_id = class_row["id"]
        else:
            cur = conn.execute(
                "INSERT INTO classes (name, section, academic_year, created_at) VALUES (?, ?, ?, ?)",
                ("B.Tech CSE", "A", "2025-26", now),
            )
            class_id = cur.lastrowid
            print(f"Created class B.Tech CSE — Sec A (id={class_id})")

        sub_row = conn.execute(
            "SELECT id FROM subjects WHERE class_id=? AND code=?",
            (class_id, "DS101"),
        ).fetchone()
        if sub_row:
            subject_id = sub_row["id"]
        else:
            cur = conn.execute(
                "INSERT INTO subjects (class_id, name, code, created_at) VALUES (?, ?, ?, ?)",
                (class_id, "Data Structures", "DS101", now),
            )
            subject_id = cur.lastrowid
            print(f"Created subject Data Structures / DS101 (id={subject_id})")

        teacher = conn.execute(
            "SELECT id FROM users WHERE username=?", ("teacher1",)
        ).fetchone()
        if teacher:
            teacher_id = teacher["id"]
        else:
            cur = conn.execute(
                """
                INSERT INTO users (username, password_hash, role, student_id, full_name, created_at)
                VALUES (?, ?, 'teacher', NULL, 'Demo Teacher', ?)
                """,
                ("teacher1", generate_password_hash("teacher123"), now),
            )
            teacher_id = cur.lastrowid
            print("Created teacher 'teacher1' / teacher123")

        assign = conn.execute(
            """
            SELECT id FROM teacher_assignments
            WHERE user_id=? AND class_id=? AND subject_id=?
            """,
            (teacher_id, class_id, subject_id),
        ).fetchone()
        if not assign:
            conn.execute(
                """
                INSERT INTO teacher_assignments (user_id, class_id, subject_id, created_at)
                VALUES (?, ?, ?, ?)
                """,
                (teacher_id, class_id, subject_id, now),
            )
            print("Assigned teacher1 → B.Tech CSE A / Data Structures")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Seed Phase 1 admin + optional demo data")
    parser.add_argument("--admin-user", default="admin")
    parser.add_argument("--admin-pass", default="admin123")
    parser.add_argument("--demo", action="store_true", help="Also create demo class/teacher")
    args = parser.parse_args()
    seed(args.admin_user, args.admin_pass, args.demo)
    print("Done.")
