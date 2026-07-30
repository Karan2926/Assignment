# Production storage — ~7000 college users

This system is **not** meant to keep 48 photos per student forever.

## The problem

| What you store | ~7000 students |
|----------------|----------------|
| 48 JPEG captures × ~50 KB | **~16+ GB** and growing |
| 1 profile thumbnail × ~40 KB | **~280 MB** |
| Face embedding (512 float32) × 1 | **~14 MB** |

Raw captures will fill college disks. **Embeddings + one profile** scale.

## What this build does

1. Capture faces for enrollment (temporary)
2. **Train Model** → compute centroid → save into `face_embeddings` table (~2 KB/student)
3. **Delete capture frames** automatically (keeps only `profile.jpg`)
4. Recognition matches against **DB embeddings**, class-scoped
5. SQLite WAL + indexes for attendance at scale

## Disk budget (target)

For 7000 students after training:

- Embeddings in DB: ~15 MB  
- Profiles: ~300 MB  
- Attendance DB: grows with years of records (Postgres recommended long-term)  

**Total face media: well under 1 GB** instead of tens of GB.

## Ops

```bash
# See disk use
curl -b cookie.txt http://127.0.0.1:5001/storage_stats

# Force prune captures (admin)
curl -X POST -b cookie.txt http://127.0.0.1:5001/prune_captures
```

Env flags:

```bash
export KEEP_CAPTURE_IMAGES=0   # default: prune after train
export MAX_CAPTURE_IMAGES=48
export JPEG_QUALITY=85
export PROFILE_MAX_EDGE=480
export SECRET_KEY='long-random-string'
```

## Next for true production (7000 concurrent-capable)

1. **Postgres** — set `DATABASE_URL` (see `POSTGRES.md`) ✅ wiring started  
2. InsightFace worker (off web workers)  
3. nginx TLS termination  
4. Backups of DB + `dataset/*/profile.jpg` nightly  
5. College portal API **last**

## Rule

Treat capture photos as **training fuel**, not permanent storage.  
The permanent identity is the **embedding in the database**.
