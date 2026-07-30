"""Production configuration for college-scale Digital Attendance (~7000 users)."""

from __future__ import annotations

import os

APP_DIR = os.path.dirname(os.path.abspath(__file__))

# --- Secrets ---
SECRET_KEY = os.environ.get("SECRET_KEY", "change-this-to-a-random-secret-in-production")

# --- Database ---
# Default SQLite is fine for pilot; set DATABASE_URL for Postgres in production:
#   postgresql://user:pass@localhost:5432/attendance
DATABASE_URL = os.environ.get("DATABASE_URL", "").strip()
DB_PATH = os.environ.get("DB_PATH", os.path.join(APP_DIR, "attendance.db"))

# --- Dataset / face storage ---
DATASET_DIR = os.environ.get("DATASET_DIR", os.path.join(APP_DIR, "dataset"))

# After training, delete capture frames and keep only profile.jpg.
# This is REQUIRED for ~7000 students (raw photos would explode disk).
KEEP_CAPTURE_IMAGES = os.environ.get("KEEP_CAPTURE_IMAGES", "0") == "1"

# Max capture frames retained BEFORE training (hard cap during upload).
MAX_CAPTURE_IMAGES = int(os.environ.get("MAX_CAPTURE_IMAGES", "48"))

# JPEG quality for saved captures / profile (lower = less disk).
JPEG_QUALITY = int(os.environ.get("JPEG_QUALITY", "85"))

# Max profile edge length in pixels (resize on save).
PROFILE_MAX_EDGE = int(os.environ.get("PROFILE_MAX_EDGE", "480"))
