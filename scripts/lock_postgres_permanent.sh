#!/bin/bash
# Lock Digital Attendance to PostgreSQL permanently on this Mac.
set -euo pipefail

cd "${HOME}/attendance_system"

echo "==> Writing .env (Postgres permanent on port 5433)"
cat > .env <<'EOF'
FLASK_ENV=development
SECRET_KEY=dev-change-me-before-production
ALLOW_PUBLIC_REGISTER=0
DATABASE_URL=postgresql://attendance:attendance@127.0.0.1:5433/attendance
KEEP_CAPTURE_IMAGES=0
MAX_CAPTURE_IMAGES=48
SESSION_COOKIE_SECURE=0
MAX_CONTENT_LENGTH_MB=20
EOF

echo "==> Ensuring ~/.zshrc exports DATABASE_URL"
ZSHRC="${HOME}/.zshrc"
LINE='export DATABASE_URL=postgresql://attendance:attendance@127.0.0.1:5433/attendance'
touch "$ZSHRC"
if ! grep -Fq "DATABASE_URL=postgresql://attendance:attendance@127.0.0.1:5433/attendance" "$ZSHRC"; then
  echo "" >> "$ZSHRC"
  echo "# Digital Attendance — permanent Postgres" >> "$ZSHRC"
  echo "$LINE" >> "$ZSHRC"
  echo "Added to ~/.zshrc"
else
  echo "Already present in ~/.zshrc"
fi

echo "==> Installing psycopg"
python3 -m pip install -q 'psycopg[binary]'

echo
echo "DONE."
echo "1) Open a NEW terminal (or: source ~/.zshrc)"
echo "2) Make sure Postgres.app is Running"
echo "3) cd ~/attendance_system && python3 app.py"
echo "4) Look for: [attendance] database backend = postgresql"
echo
echo "If old SQLite students are missing, migrate once:"
echo "  python3 scripts/migrate_sqlite_to_postgres.py"
