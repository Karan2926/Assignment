# Deploy Digital Attendance on a VPS

This guide deploys **frontend + backend + PostgreSQL** on one server
(DigitalOcean Droplet, AWS Lightsail, etc.).

Your Mac `localhost` stays for development. The VPS is for teachers/students
on a real URL with HTTPS (required for the camera).

---

## What you need

| Item | Recommendation |
|------|----------------|
| VPS | **2 GB RAM minimum**, **4 GB better** (InsightFace needs memory) |
| OS | Ubuntu 22.04 or 24.04 |
| Domain (optional but best) | e.g. `attendance.yourcollege.edu` → VPS IP |
| Local Mac data | Postgres dump if you want to keep existing students/attendance |

**Do not use** Vercel / Netlify for this project.

---

## Architecture (one server)

```text
Browser  --HTTPS-->  Nginx  -->  Gunicorn/Flask (port 8000)
                                      |
                                      +--> PostgreSQL (Docker)
                                      +--> InsightFace models
                                      +--> /data volume (photos)
```

Frontend templates and APIs are the **same Flask app** — one deploy covers both.

---

## Step 1 — Create the VPS

1. Create a Droplet / Lightsail instance (Ubuntu, 2–4 GB RAM).
2. Note the **public IP**.
3. SSH in:

```bash
ssh root@YOUR_SERVER_IP
```

---

## Step 2 — Install Docker

```bash
apt-get update
apt-get install -y ca-certificates curl git
curl -fsSL https://get.docker.com | sh
systemctl enable --now docker
docker --version
docker compose version
```

---

## Step 3 — Copy the project onto the server

**Option A — Git clone (if your full code is on GitHub):**

```bash
cd /opt
git clone https://github.com/Karan2926/Assignment.git attendance
cd attendance
# Use the branch that has your full app, e.g.:
git checkout cursor/vps-deploy-guide-33ca
```

**Option B — Upload from Mac (zip / scp):**

```bash
# On Mac, from your attendance_system folder:
cd ~/attendance_system
tar czf /tmp/attendance.tgz \
  --exclude='.git' --exclude='__pycache__' --exclude='dataset' \
  --exclude='*.db' --exclude='backups' .
scp /tmp/attendance.tgz root@YOUR_SERVER_IP:/opt/

# On server:
mkdir -p /opt/attendance && cd /opt/attendance
tar xzf /opt/attendance.tgz
```

---

## Step 4 — Create production `.env`

```bash
cd /opt/attendance
cp .env.example .env
nano .env
```

Set at least:

```bash
FLASK_ENV=production
SECRET_KEY=PASTE_LONG_RANDOM_HEX_HERE
POSTGRES_PASSWORD=choose_a_strong_db_password
ALLOW_PUBLIC_REGISTER=0
SESSION_COOKIE_SECURE=0
GUNICORN_WORKERS=2
GUNICORN_TIMEOUT=180
```

Generate `SECRET_KEY`:

```bash
python3 -c "import secrets; print(secrets.token_hex(32))"
```

> After HTTPS works, set `SESSION_COOKIE_SECURE=1`.

`DATABASE_URL` for Docker is set automatically by `docker-compose.yml`
(`postgresql://attendance:...@db:5432/attendance`). You do **not** need
your Mac’s `127.0.0.1:5433` URL on the server.

---

## Step 5 — Start the stack

```bash
cd /opt/attendance
docker compose up -d --build
docker compose ps
docker compose logs -f web
```

Look for:

```text
[attendance] database backend = postgresql
```

Open in browser (temporary, HTTP):

```text
http://YOUR_SERVER_IP:8000
```

First InsightFace start can take a few minutes while models download.

---

## Step 6 — Create admin login

```bash
cd /opt/attendance
docker compose exec web python3 scripts/seed_admin.py --user admin --password 'ChangeMeNow!'
```

Log in at `/login` with that admin user.

---

## Step 7 — HTTPS with Nginx (needed for camera)

Camera APIs require a **secure origin** (HTTPS) when not on localhost.

```bash
apt-get install -y nginx certbot python3-certbot-nginx
cp /opt/attendance/deploy/nginx.conf.example /etc/nginx/sites-available/attendance
# Edit server_name to your domain
nano /etc/nginx/sites-available/attendance
ln -sf /etc/nginx/sites-available/attendance /etc/nginx/sites-enabled/
nginx -t && systemctl reload nginx

# Point DNS A record: attendance.example.com → YOUR_SERVER_IP
certbot --nginx -d attendance.example.com
```

Then in `.env` set `SESSION_COOKIE_SECURE=1` and restart:

```bash
cd /opt/attendance
# edit .env
docker compose up -d
```

Teachers use: `https://attendance.example.com`

**Firewall:** allow 22, 80, 443. You can close public 8000 after Nginx is up:

```bash
ufw allow OpenSSH
ufw allow 80
ufw allow 443
ufw enable
```

---

## Step 8 — Move data from Mac (no data loss)

### On Mac — dump Postgres

```bash
# Adjust port/user if needed (Postgres.app often uses 5433)
pg_dump "postgresql://attendance:attendance@127.0.0.1:5433/attendance" -Fc -f ~/attendance_mac.dump
scp ~/attendance_mac.dump root@YOUR_SERVER_IP:/opt/attendance/
```

### On server — restore into Docker Postgres

```bash
cd /opt/attendance
docker compose exec -T db pg_restore -U attendance -d attendance --clean --if-exists < attendance_mac.dump
```

Or if `pg_restore` complains about ownership, try without `--clean` on a fresh DB:

```bash
docker compose exec -T db pg_restore -U attendance -d attendance --no-owner < attendance_mac.dump
```

Restart web:

```bash
docker compose restart web
```

Verify students / attendance on the site. Keep the Mac dump file as a backup.

---

## Day-to-day commands

```bash
cd /opt/attendance

# Status
docker compose ps
docker compose logs -f --tail=100 web

# Restart after code update
git pull   # or re-upload files
docker compose up -d --build

# Backup (Postgres dump + profile photos)
chmod +x scripts/backup.sh
./scripts/backup.sh /opt/attendance/backups
```

Schedule nightly backup (crontab):

```bash
crontab -e
# add:
0 2 * * * /opt/attendance/scripts/backup.sh /opt/attendance/backups >> /var/log/attendance-backup.log 2>&1
```

---

## Never do this on the VPS

```bash
python3 app.py    # debug server — Mac only
```

Production entrypoint is always:

```bash
docker compose up -d
# or: gunicorn -c gunicorn.conf.py wsgi:app
```

---

## Troubleshooting

| Symptom | Fix |
|---------|-----|
| Site loads but camera blocked | Use HTTPS (or `localhost` only) |
| `database backend = sqlite` | Remove `USE_SQLITE`; set Postgres via compose |
| Out of memory / killed | Upgrade to 4 GB RAM; keep `GUNICORN_WORKERS=2` |
| Recognition very slow first time | Normal — models downloading into container |
| Login fails after migrate | Restore dump again; re-run `seed_admin.py` if empty |
| Port 8000 closed after Nginx | Use `https://your-domain` only |

---

## Security checklist

- [ ] Strong `SECRET_KEY` and `POSTGRES_PASSWORD`
- [ ] `ALLOW_PUBLIC_REGISTER=0`
- [ ] HTTPS + `SESSION_COOKIE_SECURE=1`
- [ ] Firewall: 22/80/443 only
- [ ] Nightly `backup.sh` (or `pg_dump`)
- [ ] Change default admin password after first login

---

## Cost / sizing tip

For a college demo class: **1 VPS (4 GB) is enough**.  
You do **not** need separate frontend hosting.
