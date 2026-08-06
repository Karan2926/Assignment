"""WSGI entrypoint for production (gunicorn)."""

from app import app as application

# gunicorn wsgi:application
app = application
