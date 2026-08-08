# Apply Phase 2 Login on your Mac

## Why you saw "Authentication credentials were not provided"
You opened the site as http://localhost:5173 but API was http://127.0.0.1:8000.
Browsers treat localhost and 127.0.0.1 as different sites, so logout session cookie failed.
Latest patch uses the same hostname automatically.

## Install / update

1. Download:
   https://github.com/Karan2926/Assignment/blob/cursor/saas-phase1-installer-33ca/installers/smart-attendance-saas-phase2-login.tgz

2. Terminal:
```bash
cd ~/Smart-Attendance-SaaS
tar xzf ~/Downloads/smart-attendance-saas-phase2-login.tgz
git add .
git commit -m "Phase 2 login cookie fix"
git push
```

3. Restart React terminal (Ctrl+C then):
```bash
cd ~/Smart-Attendance-SaaS/frontend
npm run dev
```

4. Open exactly: http://localhost:5173
   (and keep Django on http://localhost:8000)

5. Login admin / admin123, then Log out — error should be gone.
