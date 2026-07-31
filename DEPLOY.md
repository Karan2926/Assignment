# Production runbook — Digital Attendance (college)

## Never do this in production
```bash
python3 app.py   # debug server — laptop only
```

## Correct production start
```bash
export FLASK_ENV=production
export SECRET_KEY="$(python3 -c 'import secrets; print(secrets.token_hex(32))')"
export ALLOW_PUBLIC_REGISTER=0

pip install -r requirements.txt gunicorn
gunicorn -c gunicorn.conf.py wsgi:app
```

Or Docker:
```bash
cp .env.example .env   # set SECRET_KEY
docker compose up -d --build
```

App listens on **:8000** (put nginx TLS in front).

## Security defaults in this build
- Public `/register` **disabled** unless `ALLOW_PUBLIC_REGISTER=1`
- Teachers/admins create student logins via API
- Face upload only for students the teacher can manage
- Attendance uniqueness enforced in DB (one mark / student / class / subject / day)
- Session cookies HttpOnly + SameSite; Secure in production
- Rate limits on login and recognition
- Upload size capped

## Create a student login (teacher/admin)
```http
POST /api/students/<id>/create_login
{"username":"roll23","password":"strong-pass"}
```

## Backup
```bash
chmod +x scripts/backup.sh
./scripts/backup.sh /path/to/backup-dir
```

## Still next (P0 remaining)
- Move InsightFace to a worker process (don’t run heavy AI in every gunicorn worker forever)
- Postgres for multi-building concurrency
- College portal SSO / sync
