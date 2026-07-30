# PostgreSQL for college production

## Why

Local development can keep **SQLite** (one file, easy).  
College production with many teachers marking at once should use **PostgreSQL**.

| | SQLite | PostgreSQL |
|--|--------|------------|
| Local laptop | Yes (default) | Optional |
| Many concurrent marks | Weak | Strong |
| Multi-server later | Hard | Normal |

## Correct project order

1. Core attendance + face + storage + hardening  
2. **PostgreSQL** ← this step  
3. Face recognition worker  
4. HTTPS / CSRF / audit  
5. **College portal API last**

## Switch on (production)

1. Install driver:

```bash
pip3 install 'psycopg[binary]'
```

2. Set env (`.env`):

```bash
DATABASE_URL=postgresql://attendance:attendance@127.0.0.1:5432/attendance
SECRET_KEY=long-random-string
FLASK_ENV=production
```

3. Create DB (once):

```bash
# example with docker:
docker compose up -d db
```

4. Create tables (app does this on start via `db.init_db()`), or:

```bash
python3 -c "import db; db.init_db(); print(db.backend_name())"
```

5. If you already have SQLite data:

```bash
export DATABASE_URL=postgresql://attendance:attendance@127.0.0.1:5432/attendance
python3 scripts/migrate_sqlite_to_postgres.py --sqlite ./attendance.db
```

6. Start app as usual (gunicorn / docker). Leave `DATABASE_URL` set.

## Local Mac (unchanged)

Do **not** set `DATABASE_URL`. App uses `attendance.db` SQLite automatically.

## Docker Compose

`docker compose up` can start Postgres + web together. Web gets:

```bash
DATABASE_URL=postgresql://attendance:attendance@db:5432/attendance
```

## Check which DB is active

```bash
python3 -c "import db; print(db.backend_name())"
```

Prints `sqlite` or `postgresql`.
