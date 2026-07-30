"""
College portal API (Phase 3).

The React college website calls these JSON endpoints after Smart Attendance
is running. Auth is a shared API key — not teacher browser sessions.
"""

from __future__ import annotations

import json
import urllib.error
import urllib.request
from functools import wraps

from flask import Blueprint, jsonify, request

import config
import db

portal_bp = Blueprint("portal_api", __name__, url_prefix="/api/portal/v1")


def portal_auth_required(f):
    @wraps(f)
    def wrapper(*args, **kwargs):
        if not config.PORTAL_API_KEY:
            return (
                jsonify(
                    {
                        "error": "Portal API not configured",
                        "hint": "Set PORTAL_API_KEY on the attendance server",
                    }
                ),
                503,
            )

        provided = ""
        auth = request.headers.get("Authorization", "")
        if auth.lower().startswith("bearer "):
            provided = auth[7:].strip()
        if not provided:
            provided = request.headers.get("X-Portal-Api-Key", "").strip()

        if not provided or provided != config.PORTAL_API_KEY:
            return jsonify({"error": "Unauthorized"}), 401
        return f(*args, **kwargs)

    return wrapper


@portal_bp.get("/health")
@portal_auth_required
def portal_health():
    return jsonify(
        {
            "ok": True,
            "service": "smart-attendance",
            "students": len(db.list_portal_students()),
            "face_embeddings": db.face_embedding_count(),
            "push_configured": bool(config.PORTAL_PUSH_URL),
        }
    )


@portal_bp.get("/classes")
@portal_auth_required
def portal_classes():
    return jsonify({"classes": db.list_portal_classes()})


@portal_bp.get("/students")
@portal_auth_required
def portal_students():
    class_id = request.args.get("class_id", type=int)
    students = db.list_portal_students(class_id=class_id)
    mapped = sum(1 for s in students if s["mapped"])
    return jsonify(
        {
            "count": len(students),
            "mapped": mapped,
            "unmapped": len(students) - mapped,
            "students": students,
        }
    )


@portal_bp.post("/students/sync")
@portal_auth_required
def portal_students_sync():
    """
    College portal pushes official student master list.

    Body:
    {
      "students": [
        {
          "portal_student_id": "PORTAL-123",
          "name": "Ada Lovelace",
          "roll": "24CSE001",
          "class_id": 1
        }
      ]
    }
    """
    payload = request.get_json(silent=True) or {}
    items = payload.get("students")
    if not isinstance(items, list) or not items:
        return jsonify({"error": "students array required"}), 400

    created = 0
    updated = 0
    errors = []
    for i, item in enumerate(items):
        if not isinstance(item, dict):
            errors.append({"index": i, "error": "invalid item"})
            continue
        try:
            raw_class = item.get("class_id")
            class_id = int(raw_class) if raw_class is not None and str(raw_class).strip() != "" else None
            result = db.upsert_portal_student(
                portal_student_id=str(item.get("portal_student_id", "")),
                name=str(item.get("name", "")),
                roll=str(item.get("roll", "") or ""),
                class_id=class_id,
            )
            if result["created"]:
                created += 1
            else:
                updated += 1
        except ValueError as e:
            errors.append({"index": i, "error": str(e)})
        except Exception:
            errors.append({"index": i, "error": "could not upsert student"})

    db.log_portal_sync(
        "inbound",
        "students",
        "ok" if not errors else "partial",
        json.dumps({"created": created, "updated": updated, "errors": len(errors)}),
    )
    return jsonify(
        {
            "created": created,
            "updated": updated,
            "errors": errors,
        }
    )


@portal_bp.patch("/students/<int:student_id>/mapping")
@portal_auth_required
def portal_map_student(student_id: int):
    payload = request.get_json(silent=True) or {}
    portal_student_id = str(payload.get("portal_student_id", "")).strip()
    if not portal_student_id:
        return jsonify({"error": "portal_student_id required"}), 400
    try:
        ok = db.set_student_portal_id(student_id, portal_student_id)
    except Exception:
        return jsonify({"error": "portal_student_id already linked to another student"}), 409
    if not ok:
        return jsonify({"error": "student not found"}), 404
    return jsonify({"student_id": student_id, "portal_student_id": portal_student_id})


@portal_bp.get("/attendance")
@portal_auth_required
def portal_attendance():
    """
    Fetch present marks for the React portal.

    Query:
      date=YYYY-MM-DD          (single day)
      from=YYYY-MM-DD&to=...   (range)
      class_id= / subject_id=
    """
    day = request.args.get("date", "").strip() or None
    date_from = request.args.get("from", "").strip() or None
    date_to = request.args.get("to", "").strip() or None
    class_id = request.args.get("class_id", type=int)
    subject_id = request.args.get("subject_id", type=int)

    if not day and not date_from and not date_to:
        import datetime as dt

        day = dt.date.today().isoformat()

    records = db.export_attendance(
        day=day,
        date_from=date_from,
        date_to=date_to,
        class_id=class_id,
        subject_id=subject_id,
    )
    unmapped = sum(1 for r in records if not r.get("portal_student_id"))
    return jsonify(
        {
            "filters": {
                "date": day,
                "from": date_from,
                "to": date_to,
                "class_id": class_id,
                "subject_id": subject_id,
            },
            "count": len(records),
            "unmapped_students": unmapped,
            "records": records,
        }
    )


@portal_bp.get("/attendance/export")
@portal_auth_required
def portal_attendance_export():
    """Alias pack shaped for bulk import into the college portal."""
    date_from = request.args.get("from", "").strip() or None
    date_to = request.args.get("to", "").strip() or None
    day = request.args.get("date", "").strip() or None
    class_id = request.args.get("class_id", type=int)
    subject_id = request.args.get("subject_id", type=int)

    if not day and not date_from:
        import datetime as dt

        day = dt.date.today().isoformat()

    records = db.export_attendance(
        day=day,
        date_from=date_from,
        date_to=date_to,
        class_id=class_id,
        subject_id=subject_id,
    )
    db.log_portal_sync(
        "outbound",
        "attendance_export",
        "ok",
        json.dumps({"count": len(records), "date": day, "from": date_from, "to": date_to}),
    )
    return jsonify(
        {
            "schema_version": 1,
            "system": "smart-attendance",
            "count": len(records),
            "records": records,
        }
    )


def _push_pack_to_portal(pack: dict) -> tuple[bool, str]:
    if not config.PORTAL_PUSH_URL:
        return False, "PORTAL_PUSH_URL not set"
    body = json.dumps(pack).encode("utf-8")
    headers = {"Content-Type": "application/json"}
    if config.PORTAL_PUSH_TOKEN:
        headers["Authorization"] = f"Bearer {config.PORTAL_PUSH_TOKEN}"
    req = urllib.request.Request(
        config.PORTAL_PUSH_URL,
        data=body,
        headers=headers,
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            return True, f"portal responded {resp.status}"
    except urllib.error.HTTPError as e:
        return False, f"portal HTTP {e.code}"
    except Exception:
        return False, "portal unreachable"


@portal_bp.post("/attendance/push")
@portal_auth_required
def portal_attendance_push():
    """
    Push today's (or filtered) attendance pack to PORTAL_PUSH_URL.
    Use when the college React API accepts inbound attendance posts.
    """
    payload = request.get_json(silent=True) or {}
    day = str(payload.get("date") or request.args.get("date") or "").strip() or None
    class_id = payload.get("class_id") or request.args.get("class_id", type=int)
    subject_id = payload.get("subject_id") or request.args.get("subject_id", type=int)

    if not day:
        import datetime as dt

        day = dt.date.today().isoformat()

    records = db.export_attendance(day=day, class_id=class_id, subject_id=subject_id)
    pack = {
        "schema_version": 1,
        "system": "smart-attendance",
        "date": day,
        "count": len(records),
        "records": records,
    }
    ok, detail = _push_pack_to_portal(pack)
    db.log_portal_sync("outbound", "attendance_push", "ok" if ok else "error", detail)
    if not ok:
        return jsonify({"error": "push failed", "detail": detail, "count": len(records)}), 502
    return jsonify({"pushed": True, "detail": detail, "count": len(records)})
