# Digital Attendance — Phase 2

Smart face-recognition attendance for college, built on your Flask + InsightFace prototype.

## What Phase 1 added

- **Classes & subjects** — structured college data instead of free-text only
- **Teacher access control** — each teacher only sees assigned class+subject pairs
- **Scoped attendance** — mark / classroom / records / analytics / CSV filtered by access
- **Admin panel** — create classes, subjects, teachers, and assignments
- **Enrollment** — students belong to a class
- **Per day uniqueness** — one present mark per student **per class + subject + day**

## What Phase 2 adds

- **Class-scoped matching** — compare faces only to students enrolled in the selected class
- **Better classroom detection** — larger detector window, upscale, overlap NMS
- **Cleaner confidence** — cosine similarity + margin (no conflicting KNN probability)
- **Faster retrain** — `embedding_cache.pkl` skips unchanged face photos

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
| **1** | Data model, teacher access, scoped attendance ✅ |
| **2** | Face recognition for 80+ students ✅ |
| **2.5 / 2.6** | Storage + production hardening ✅ |
| **3** | College React portal API (`PORTAL_API.md`) |
| **4** | Postgres, face worker, CSRF/SSO |

## College portal (React)

Smart Attendance stays separate. Connect the college React site later:

```bash
export PORTAL_API_KEY='long-random-key'
# Portal calls: GET /api/portal/v1/attendance?date=YYYY-MM-DD
```

Details: [`PORTAL_API.md`](PORTAL_API.md)

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
