# College Portal API (Phase 3)

Smart Attendance stays its own system. The **React college portal** connects later through these JSON APIs.

```text
React college portal
        |
        |  Authorization: Bearer <PORTAL_API_KEY>
        v
Smart Attendance  /api/portal/v1/...
```

## Setup

On the attendance server (`.env`):

```bash
PORTAL_API_KEY=long-random-shared-secret
# optional outbound push into React backend:
# PORTAL_PUSH_URL=https://college-portal.example/api/attendance/ingest
# PORTAL_PUSH_TOKEN=token-college-expects
```

Restart gunicorn/docker after changing env.

## Auth

Every portal route requires one of:

```http
Authorization: Bearer <PORTAL_API_KEY>
```

or

```http
X-Portal-Api-Key: <PORTAL_API_KEY>
```

If `PORTAL_API_KEY` is unset, routes return `503`.

## Endpoints

Base path: `/api/portal/v1`

| Method | Path | Purpose |
|--------|------|---------|
| GET | `/health` | Connectivity check |
| GET | `/classes` | Classes + subjects (for mapping) |
| GET | `/students?class_id=` | Local students + portal mapping status |
| POST | `/students/sync` | Portal pushes official student master list |
| PATCH | `/students/<id>/mapping` | Link one local student → portal id |
| GET | `/attendance?date=YYYY-MM-DD` | Present marks for a day |
| GET | `/attendance/export?from=&to=` | Bulk pack for portal import |
| POST | `/attendance/push` | Push pack to `PORTAL_PUSH_URL` |

## Typical React flow

### 1) Sync official students into attendance (recommended first)

```http
POST /api/portal/v1/students/sync
Content-Type: application/json

{
  "students": [
    {
      "portal_student_id": "SIS-10021",
      "name": "Ada Lovelace",
      "roll": "24CSE001",
      "class_id": 1
    }
  ]
}
```

Matching order: `portal_student_id` → `roll` → create new local student.

### 2) Teachers mark attendance in Smart Attendance (face system)

No change — teachers keep using this app.

### 3) Portal pulls daily attendance

```http
GET /api/portal/v1/attendance?date=2026-07-30
```

Example record:

```json
{
  "attendance_id": 55,
  "student_id": 12,
  "portal_student_id": "SIS-10021",
  "roll": "24CSE001",
  "student_name": "Ada Lovelace",
  "status": "present",
  "date": "2026-07-30",
  "marked_at": "2026-07-30T09:15:00",
  "class_id": 1,
  "class_name": "B.Tech CSE",
  "class_section": "A",
  "subject_id": 3,
  "subject_name": "DSA",
  "subject_code": "CS201",
  "source": "classroom"
}
```

### 4) Optional: attendance server pushes to portal webhook

```http
POST /api/portal/v1/attendance/push
{"date": "2026-07-30"}
```

Requires `PORTAL_PUSH_URL` on the attendance server.

## Student identity mapping

| Field | Meaning |
|-------|---------|
| `student_id` | ID inside Smart Attendance |
| `portal_student_id` | ID inside college React / SIS |
| `roll` | College roll number (bridge if portal id missing) |

Unmapped students still appear in exports with empty `portal_student_id` — portal should treat `roll` as fallback.

## What this API does *not* do

- Does not replace college login/SSO (later)
- Does not run face recognition (that stays in attendance app)
- Does not require rewriting the attendance UI in React

## Quick curl test

```bash
export KEY='your-portal-key'
curl -s -H "Authorization: Bearer $KEY" http://127.0.0.1:5001/api/portal/v1/health
curl -s -H "Authorization: Bearer $KEY" "http://127.0.0.1:5001/api/portal/v1/attendance?date=2026-07-30"
```
