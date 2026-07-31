"""Production configuration — college deployment (~7000 users)."""

from __future__ import annotations

import os
import sys

APP_DIR = os.path.dirname(os.path.abspath(__file__))

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

DATABASE_URL = os.environ.get("DATABASE_URL", "").strip()
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
