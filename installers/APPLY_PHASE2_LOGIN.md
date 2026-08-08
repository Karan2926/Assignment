# Apply Phase 2 Login on your Mac

1. Open browser (logged into GitHub) and download:
   https://github.com/Karan2926/Assignment/blob/cursor/saas-phase1-installer-33ca/installers/smart-attendance-saas-phase2-login.tgz

2. In Terminal:

```bash
cd ~/Smart-Attendance-SaaS
tar xzf ~/Downloads/smart-attendance-saas-phase2-login.tgz
git add .
git commit -m "Phase 2 login"
git push
```

3. Restart servers (Ctrl+C each terminal, then start again):

Backend:
```bash
cd ~/Smart-Attendance-SaaS/backend
source .venv/bin/activate
python manage.py runserver 8000
```

Frontend:
```bash
cd ~/Smart-Attendance-SaaS/frontend
npm run dev
```

4. Open http://localhost:5173
   Login: admin / admin123

5. Read learning notes:
   docs/LEARN_LOGIN.md
