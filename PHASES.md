# Phased roadmap

## Correct completion order
1. Foundation + recognition + storage + hardening ✅  
2. **PostgreSQL** (this) — campus concurrent DB  
3. Face recognition **worker** (off web workers)  
4. HTTPS / CSRF / audit  
5. **College portal API last** (React site connects afterward)

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
- Face centroids stored in DB (`face_embeddings`)
- Capture JPEGs pruned after train (keep profile only)
- Disk stats + admin prune endpoint
- See `STORAGE.md`

## Phase 2.6 — Production hardening ✅
- Gunicorn + Docker deploy (`DEPLOY.md`)
- Require `SECRET_KEY` when `FLASK_ENV=production`
- Public register **off** by default
- Upload authz, unique attendance day, rate limits, backups

## Phase 2.7 — PostgreSQL ✅ (started)
- Same app code; `DATABASE_URL` selects Postgres, else SQLite
- `db_engine.py` adapter (`?` SQL works on both)
- docker-compose Postgres service
- `scripts/migrate_sqlite_to_postgres.py`
- See `POSTGRES.md`

## Phase 3 — Face worker + deploy security
- InsightFace worker process (off gunicorn workers)
- nginx TLS, CSRF, richer audit log

## Phase 4 — College portal integration (LAST)
- React college portal connects via API afterward
- Student ID mapping (roll ↔ portal ID)
- Daily attendance pull/push
