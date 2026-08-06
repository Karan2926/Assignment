# Digital Attendance — Phase 1

Smart face-recognition attendance for college, built on your existing Flask + InsightFace prototype.

## What Phase 1 adds

- **Classes & subjects** — structured college data instead of free-text only
- **Teacher access control** — each teacher only sees assigned class+subject pairs
- **Scoped attendance** — mark / classroom / records / analytics / CSV filtered by access
- **Admin panel** — create classes, subjects, teachers, and assignments
- **Enrollment** — students belong to a class; recognition rejects out-of-class matches
- **Per day uniqueness** — one present mark per student **per class + subject + day**

Face recognition (`model.py`) is unchanged for Phase 1. Phase 2 will improve large-class matching.

## Quick start

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

# Create admin + optional demo class/teacher
python scripts/seed_admin.py --demo

python app.py
```

Open http://127.0.0.1:5001

### Demo logins (with `--demo`)

| Role | Username | Password |
|------|----------|----------|
| Admin | `admin` | `admin123` |
| Teacher | `teacher1` | `teacher123` |

Students register at `/register` using a roll number the teacher already added.

## Suggested admin setup

1. Log in as admin → **Admin**
2. Create classes (e.g. B.Tech CSE — Sec A)
3. Add subjects under each class
4. Create teacher accounts
5. Assign each teacher to class + subject
6. Teachers add students (enrolled in their class), capture faces, train model
7. Teachers select class + subject before live/classroom marking

## Roadmap

| Phase | Focus |
|-------|--------|
| **1 (this)** | Data model, teacher access, scoped attendance |
| **2** | Face recognition for 80+ students (class-scoped gallery, better classroom detection) |
| **3** | College portal sync (API / CSV) |
| **4** | Hardening, ops, production secrets |

## Project layout

```
app.py              Flask routes
db.py               Schema, migrations, access helpers
model.py            InsightFace + KNN (lazy-loaded)
scripts/seed_admin.py
templates/          UI
static/css|js       Theme + camera scripts
dataset/            Face images (gitignored)
```

Set `SECRET_KEY` in the environment before any real deployment.
