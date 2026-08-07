# Smart Attendance SaaS (startup product)

Multi-organization face attendance platform for **colleges, offices, factories, coaching centers**, and more.

```text
saas/
├── backend/     # Django + DRF API
└── frontend/    # React (Vite + TypeScript)
```

## Phase 1 (done in this scaffold)
- Django project with apps: `core`, `orgs`, `accounts`
- `Organization` model (education / corporate / industrial / ...)
- Custom `User` with roles + organization link
- APIs:
  - `GET  /api/health/`
  - `GET/POST /api/organizations/`
  - `POST /api/auth/login/`
  - `POST /api/auth/logout/`
  - `GET  /api/auth/me/`
- React home page that calls health API

## Run locally

### Backend
```bash
cd saas/backend
python3 -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt
python manage.py migrate
python manage.py createsuperuser
python manage.py runserver 8000
```

### Frontend
```bash
cd saas/frontend
npm install
npm run dev
```

Open: http://localhost:5173  
API health: http://127.0.0.1:8000/api/health/

## Next steps (Phase 2)
1. React login page
2. People directory (employees/students)
3. Groups (class/department/shift)
4. Face enrollment
5. Live attendance camera

Old Flask college project stays at repo root. This SaaS lives under `saas/`.
