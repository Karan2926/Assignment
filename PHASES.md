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

## Phase 2.5 — Production storage (7000 users) ✅ (this branch)
- Face centroids stored in SQLite (`face_embeddings`)
- Capture JPEGs pruned after train (keep profile only)
- Disk stats + admin prune endpoint
- Indexes + WAL for larger attendance load
- See `STORAGE.md`

## Phase 3 — College portal integration
- Export format matching portal maintainer spec
- Optional API push of daily attendance
- Student ID mapping (roll ↔ portal ID)

## Phase 4 — Production hardening
- Strong secrets, HTTPS, rate limits
- Audit log for deletes / overrides
- Backup of DB + dataset
- Role reviews and password reset flow
