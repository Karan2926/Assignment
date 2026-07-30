# Phased roadmap

## Phase 1 — Foundation (done in this branch)
- Classes, subjects, enrollments
- Teacher assignments (class + subject)
- Admin panel
- Attendance scoped by class/subject/day
- Teacher-only visibility of records/analytics/CSV

## Phase 2 — Recognition at 80+ scale
- Match only against the selected class roster (not whole college)
- Improve classroom detection (higher det size / multi-shot)
- Align distance + confidence scoring
- Incremental embedding index (avoid full retrain when possible)

## Phase 3 — College portal integration
- Export format matching portal maintainer spec
- Optional API push of daily attendance
- Student ID mapping (roll ↔ portal ID)

## Phase 4 — Production hardening
- Strong secrets, HTTPS, rate limits
- Audit log for deletes / overrides
- Backup of DB + dataset
- Role reviews and password reset flow
