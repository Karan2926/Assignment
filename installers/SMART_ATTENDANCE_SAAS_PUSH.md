# Push Smart Attendance SaaS Phase 1 from your Mac

Cursor cannot push to https://github.com/Karan2926/Smart-Attendance-SaaS
until the Cursor GitHub App is installed on that repo.
Use this Mac flow instead:

```bash
cd ~
mkdir -p Smart-Attendance-SaaS && cd Smart-Attendance-SaaS
# If repo is empty, clone it first:
git clone https://github.com/Karan2926/Smart-Attendance-SaaS.git .
# If clone fails because empty weirdness:
# git init && git remote add origin https://github.com/Karan2926/Smart-Attendance-SaaS.git

# Unpack the phase1 archive into this folder (download smart-attendance-saas-phase1.tgz from Cursor artifacts)
tar xzf ~/Downloads/smart-attendance-saas-phase1.tgz --strip-components=0
# If the archive extracts a top folder, move contents up:
# mv Smart-Attendance-SaaS/* . && rmdir Smart-Attendance-SaaS

git add .
git commit -m "Phase 1: Django + React foundation"
git branch -M main
git push -u origin main
```

Then run locally:

```bash
cd backend
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
python manage.py migrate
python scripts/seed_demo.py
python manage.py runserver 8000
```

```bash
cd frontend
npm install
npm run dev
```

Demo login: admin / admin123
