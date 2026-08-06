"""Production configuration — college deployment (~7000 users)."""

from __future__ import annotations

import os
import sys

APP_DIR = os.path.dirname(os.path.abspath(__file__))


def _load_dotenv(path: str | None = None) -> None:
    """Load KEY=VALUE pairs from .env without overriding real environment vars."""
    env_path = path or os.path.join(APP_DIR, ".env")
    if not os.path.isfile(env_path):
        return
    try:
        with open(env_path, encoding="utf-8") as f:
            for raw in f:
                line = raw.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                key, val = line.split("=", 1)
                key = key.strip()
                val = val.strip().strip('"').strip("'")
                if key and key not in os.environ:
                    os.environ[key] = val
    except OSError:
        pass


_load_dotenv()

# production | development
FLASK_ENV = os.environ.get("FLASK_ENV", "development").strip().lower()
IS_PRODUCTION = FLASK_ENV == "production"

_DEFAULT_SECRET = "change-this-to-a-random-secret-in-production"
SECRET_KEY = os.environ.get("SECRET_KEY", _DEFAULT_SECRET).strip()

if IS_PRODUCTION:
    if not SECRET_KEY or SECRET_KEY == _DEFAULT_SECRET:
        print(
            "FATAL: Set a strong SECRET_KEY env var before running in production.",
            file=sys.stderr,
        )
        sys.exit(1)

# Public self-register is OFF by default (security). Teachers/admins create logins.
ALLOW_PUBLIC_REGISTER = os.environ.get("ALLOW_PUBLIC_REGISTER", "0") == "1"

# Optional shared invite code if public register is enabled
REGISTER_INVITE_CODE = os.environ.get("REGISTER_INVITE_CODE", "").strip()

# ---------------------------------------------------------------------------
# Database — PostgreSQL is permanent default (avoids SQLite/Postgres mix-ups)
# Postgres.app on this project uses port 5433.
# Escape hatch for emergencies only: USE_SQLITE=1
# ---------------------------------------------------------------------------
_DEFAULT_DATABASE_URL = (
    "postgresql://attendance:attendance@127.0.0.1:5433/attendance"
)
USE_SQLITE = os.environ.get("USE_SQLITE", "0").strip() == "1"

if USE_SQLITE:
    DATABASE_URL = ""
else:
    DATABASE_URL = os.environ.get("DATABASE_URL", _DEFAULT_DATABASE_URL).strip()
    if not DATABASE_URL:
        DATABASE_URL = _DEFAULT_DATABASE_URL

DB_PATH = os.environ.get("DB_PATH", os.path.join(APP_DIR, "attendance.db"))

DATASET_DIR = os.environ.get("DATASET_DIR", os.path.join(APP_DIR, "dataset"))
KEEP_CAPTURE_IMAGES = os.environ.get("KEEP_CAPTURE_IMAGES", "0") == "1"
MAX_CAPTURE_IMAGES = int(os.environ.get("MAX_CAPTURE_IMAGES", "48"))
JPEG_QUALITY = int(os.environ.get("JPEG_QUALITY", "85"))
PROFILE_MAX_EDGE = int(os.environ.get("PROFILE_MAX_EDGE", "480"))

# Upload / request limits
MAX_CONTENT_LENGTH_MB = int(os.environ.get("MAX_CONTENT_LENGTH_MB", "20"))

# Session
SESSION_COOKIE_HTTPONLY = True
SESSION_COOKIE_SAMESITE = "Lax"
SESSION_COOKIE_SECURE = IS_PRODUCTION or os.environ.get("SESSION_COOKIE_SECURE", "0") == "1"
PERMANENT_SESSION_LIFETIME_HOURS = int(os.environ.get("SESSION_LIFETIME_HOURS", "8"))

# Rate limits (flask-limiter style strings)
RATELIMIT_DEFAULT = os.environ.get("RATELIMIT_DEFAULT", "200 per hour")
RATELIMIT_LOGIN = os.environ.get("RATELIMIT_LOGIN", "10 per minute")
RATELIMIT_RECOGNIZE = os.environ.get("RATELIMIT_RECOGNIZE", "30 per minute")
