# PostgreSQL — permanent database for this project

SQLite is **no longer the normal path**. The app defaults to PostgreSQL so
student/attendance data does not get split across two databases.

## Default connection (this Mac / Postgres.app)

```text
postgresql://attendance:attendance@127.0.0.1:5433/attendance
```

Port **5433** is the Postgres.app port used on this project.

## One-time Mac setup

### 1) Create role + database (Postgres.app running)

```bash
psql -p 5433 -d postgres <<'SQL'
DO $$
BEGIN
  IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname = 'attendance') THEN
    CREATE ROLE attendance LOGIN PASSWORD 'attendance';
  END IF;
END$$;
SELECT 'CREATE DATABASE attendance OWNER attendance'
WHERE NOT EXISTS (SELECT FROM pg_database WHERE datname = 'attendance')\gexec
SQL
```

### 2) Install driver + lock config in project

```bash
cd ~/attendance_system
pip3 install 'psycopg[binary]'
cp .env.example .env
```

`.env` must contain:

```bash
DATABASE_URL=postgresql://attendance:attendance@127.0.0.1:5433/attendance
```

### 3) Make shell permanent too (optional but recommended)

Add to `~/.zshrc`:

```bash
export DATABASE_URL=postgresql://attendance:attendance@127.0.0.1:5433/attendance
```

Then:

```bash
source ~/.zshrc
```

### 4) Start app

```bash
cd ~/attendance_system
python3 app.py
```

You should see:

```text
[attendance] database backend = postgresql
```

## Migrate old SQLite data into Postgres (if needed)

If your 12 students are still only in `attendance.db`:

```bash
cd ~/attendance_system
export DATABASE_URL=postgresql://attendance:attendance@127.0.0.1:5433/attendance
python3 scripts/migrate_sqlite_to_postgres.py
```

## Emergency SQLite only

```bash
USE_SQLITE=1 python3 app.py
```

Do **not** use this for normal college work.

## Rule

One database only: **PostgreSQL**.  
Never switch back and forth — that is how data “disappears.”
