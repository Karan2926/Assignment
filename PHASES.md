# Phased roadmap

## Phase 1 — Foundation ✅
- Classes, subjects, enrollments
- Teacher assignments (class + subject)
- Admin panel
- Attendance scoped by class/subject/day
- Teacher-only visibility of records/analytics/CSV

## Phase 2 — Recognition at 80+ scale ✅
- Match only against the selected class roster (not whole college)
- Higher-res classroom detection (960 det size + upscale + NMS)
- Unified cosine similarity scoring + margin check
- Per-student centroids + incremental embedding cache

## Phase 2.5 — Production storage (7000 users) ✅
- Face centroids stored in SQLite (`face_embeddings`)
- Capture JPEGs pruned after train (keep profile only)
- Disk stats + admin prune endpoint
- Indexes + WAL for larger attendance load
- See `STORAGE.md`

## Phase 2.6 — Production hardening (started) ✅
- Gunicorn + Docker deploy (`DEPLOY.md`) — no debug server in production
- Require `SECRET_KEY` when `FLASK_ENV=production`
- Public register **off** by default; teacher/admin creates student logins
- Upload authz (teachers only manage their students)
- DB unique attendance per student/class/subject/day
- Rate limits, session cookie flags, upload size cap
- Backup script

## Phase 3 — College portal integration (API started)
- `/api/portal/v1/*` JSON API for React college portal — see `PORTAL_API.md`
- Shared `PORTAL_API_KEY` auth (Bearer / X-Portal-Api-Key)
- Student master sync from portal + `portal_student_id` mapping
- Attendance pull/export pack + optional push to `PORTAL_PUSH_URL`
- Sync log table `portal_sync_log`

## Phase 4 — Remaining production
- InsightFace worker process (off web workers)
- Postgres for multi-building concurrency
- CSRF tokens, SSO, richer audit log
