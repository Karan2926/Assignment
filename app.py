import os
import io
import shutil
import threading
import datetime
import json

from flask import (
    Flask,
    render_template,
    request,
    jsonify,
    send_file,
    abort,
    session,
    redirect,
    url_for,
)
from functools import wraps
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import timedelta

import config
import db

try:
    from flask_limiter import Limiter
    from flask_limiter.util import get_remote_address
except ImportError:  # pragma: no cover
    Limiter = None
    get_remote_address = None

APP_DIR = config.APP_DIR
DATASET_DIR = config.DATASET_DIR
os.makedirs(DATASET_DIR, exist_ok=True)

TRAIN_STATUS_FILE = os.path.join(APP_DIR, "train_status.json")

app = Flask(__name__, static_folder="static", template_folder="templates")
app.secret_key = config.SECRET_KEY
app.config["MAX_CONTENT_LENGTH"] = config.MAX_CONTENT_LENGTH_MB * 1024 * 1024
app.config["PERMANENT_SESSION_LIFETIME"] = timedelta(hours=config.PERMANENT_SESSION_LIFETIME_HOURS)
app.config["SESSION_COOKIE_HTTPONLY"] = config.SESSION_COOKIE_HTTPONLY
app.config["SESSION_COOKIE_SAMESITE"] = config.SESSION_COOKIE_SAMESITE
app.config["SESSION_COOKIE_SECURE"] = config.SESSION_COOKIE_SECURE

db.init_db()

# Permanent Postgres: fail early with a clear message if DB is wrong/unreachable
try:
    backend = db.backend_name() if hasattr(db, "backend_name") else (
        "postgresql" if config.DATABASE_URL else "sqlite"
    )
except Exception:
    backend = "postgresql" if config.DATABASE_URL else "sqlite"

if config.DATABASE_URL and not str(config.DATABASE_URL).lower().startswith("postgres"):
    raise SystemExit(
        "DATABASE_URL must be a PostgreSQL URL. "
        "Example: postgresql://attendance:attendance@127.0.0.1:5433/attendance"
    )

print(f"[attendance] database backend = {backend}")
if backend == "sqlite":
    print(
        "[attendance] WARNING: SQLite mode (USE_SQLITE=1). "
        "Normal college use should be PostgreSQL via .env DATABASE_URL."
    )

limiter = None
if Limiter and get_remote_address:
    limiter = Limiter(
        get_remote_address,
        app=app,
        default_limits=[config.RATELIMIT_DEFAULT],
        storage_uri="memory://",
    )


def _limit(rule):
    def deco(f):
        if limiter is None:
            return f
        return limiter.limit(rule)(f)

    return deco


def write_train_status(status_dict):
    with open(TRAIN_STATUS_FILE, "w") as f:
        json.dump(status_dict, f)


def read_train_status():
    if not os.path.exists(TRAIN_STATUS_FILE):
        return {"running": False, "progress": 0, "message": "Not trained"}
    with open(TRAIN_STATUS_FILE, "r") as f:
        return json.load(f)


write_train_status({"running": False, "progress": 0, "message": "No training yet."})


# ---------- Auth helpers ----------
def login_required(f):
    @wraps(f)
    def wrapper(*args, **kwargs):
        if "user_id" not in session:
            return redirect(url_for("login"))
        return f(*args, **kwargs)

    return wrapper


def role_required(*roles):
    def decorator(f):
        @wraps(f)
        def wrapper(*args, **kwargs):
            if "user_id" not in session:
                return redirect(url_for("login"))
            if session.get("role") not in roles:
                return jsonify({"error": "Not authorized"}), 403
            return f(*args, **kwargs)

        return wrapper

    return decorator


def _parse_class_subject():
    class_id = request.values.get("class_id") or (request.json or {}).get("class_id")
    subject_id = request.values.get("subject_id") or (request.json or {}).get("subject_id")
    try:
        class_id = int(class_id)
        subject_id = int(subject_id)
    except (TypeError, ValueError):
        return None, None
    return class_id, subject_id


def _require_assignment():
    class_id, subject_id = _parse_class_subject()
    if not class_id or not subject_id:
        return None, None, (jsonify({"error": "class_id and subject_id required"}), 400)
    if not db.teacher_can_access(
        session["user_id"], session.get("role"), class_id, subject_id
    ):
        return None, None, (jsonify({"error": "Not authorized for this class/subject"}), 403)
    return class_id, subject_id, None


# ---------- Auth routes ----------
@app.route("/register", methods=["GET", "POST"])
@_limit(config.RATELIMIT_LOGIN)
def register():
    if not config.ALLOW_PUBLIC_REGISTER:
        if request.method == "GET":
            return render_template(
                "register.html",
                error="Public registration is disabled. Ask your teacher to create your login.",
                disabled=True,
                config_invite=False,
            )
        return jsonify({"error": "Public registration disabled"}), 403

    if request.method == "GET":
        return render_template(
            "register.html",
            disabled=False,
            config_invite=bool(config.REGISTER_INVITE_CODE),
        )

    username = request.form.get("username", "").strip()
    password = request.form.get("password", "").strip()
    roll = request.form.get("roll", "").strip()
    invite = request.form.get("invite_code", "").strip()

    if config.REGISTER_INVITE_CODE and invite != config.REGISTER_INVITE_CODE:
        return render_template("register.html", error="Invalid invite code.", disabled=False)

    if not username or not password or not roll:
        return render_template("register.html", error="All fields are required.", disabled=False)
    if len(password) < 8:
        return render_template(
            "register.html", error="Password must be at least 8 characters.", disabled=False
        )

    with db.get_conn() as conn:
        c = conn.cursor()
        c.execute("SELECT id FROM students WHERE roll=?", (roll,))
        row = c.fetchone()
        if not row:
            return render_template(
                "register.html",
                error="No student found with that roll number. Ask your teacher to add you first.",
                disabled=False,
            )
        student_id = row["id"]

        c.execute("SELECT id FROM users WHERE student_id=?", (student_id,))
        if c.fetchone():
            return render_template(
                "register.html",
                error="An account already exists for this student. Contact your teacher.",
                disabled=False,
            )

        c.execute("SELECT id FROM users WHERE username=?", (username,))
        if c.fetchone():
            return render_template(
                "register.html", error="That username is already taken.", disabled=False
            )

        password_hash = generate_password_hash(password)
        now = datetime.datetime.utcnow().isoformat()
        c.execute(
            "INSERT INTO users (username, password_hash, role, student_id, created_at) VALUES (?, ?, ?, ?, ?)",
            (username, password_hash, "student", student_id, now),
        )

    return redirect(url_for("login"))


@app.route("/login", methods=["GET", "POST"])
@_limit(config.RATELIMIT_LOGIN)
def login():
    if request.method == "GET":
        return render_template("login.html")

    username = request.form.get("username", "").strip()
    password = request.form.get("password", "").strip()

    with db.get_conn() as conn:
        row = conn.execute(
            "SELECT id, password_hash, role, student_id FROM users WHERE username=?",
            (username,),
        ).fetchone()

    if not row or not check_password_hash(row["password_hash"], password):
        return render_template("login.html", error="Invalid username or password.")

    session.clear()
    session.permanent = True
    session["user_id"] = row["id"]
    session["role"] = row["role"]
    session["student_id"] = row["student_id"]
    session["username"] = username

    if row["role"] == "student":
        return redirect(url_for("my_attendance"))
    return redirect(url_for("index"))


@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("login"))


@app.route("/my_attendance", methods=["GET"])
@role_required("student")
def my_attendance():
    sid = session.get("student_id")
    with db.get_conn() as conn:
        student = conn.execute(
            "SELECT name, roll, class, section FROM students WHERE id=?", (sid,)
        ).fetchone()
        records = conn.execute(
            """
            SELECT a.timestamp, c.name AS class_name, c.section, s.name AS subject_name
            FROM attendance a
            LEFT JOIN classes c ON c.id = a.class_id
            LEFT JOIN subjects s ON s.id = a.subject_id
            WHERE a.student_id=?
            ORDER BY a.timestamp DESC
            LIMIT 200
            """,
            (sid,),
        ).fetchall()
    return render_template("my_attendance.html", student=student, records=records)


@app.route("/")
@login_required
def index():
    if session.get("role") == "student":
        return redirect(url_for("my_attendance"))
    assignments = db.get_user_assignments(session["user_id"], session.get("role"))
    classes = db.list_classes_for_user(session["user_id"], session.get("role"))
    return render_template(
        "index.html",
        role=session.get("role"),
        username=session.get("username"),
        assignment_count=len(assignments) if session.get("role") != "admin" else None,
        class_count=len(classes),
    )


@app.route("/attendance_stats")
@login_required
def attendance_stats():
    class_ids = db.teacher_class_ids(session["user_id"], session.get("role"))
    with db.get_conn() as conn:
        if class_ids is None:
            rows = conn.execute("SELECT timestamp FROM attendance").fetchall()
        elif not class_ids:
            rows = []
        else:
            placeholders = ",".join("?" * len(class_ids))
            rows = conn.execute(
                f"SELECT timestamp FROM attendance WHERE class_id IN ({placeholders})",
                tuple(class_ids),
            ).fetchall()

    last_30 = [datetime.date.today() - datetime.timedelta(days=i) for i in range(29, -1, -1)]
    if not rows:
        dates = [d.strftime("%d-%b") for d in last_30]
        return jsonify({"dates": dates, "counts": [0] * 30})

    counts_by_date = {}
    for r in rows:
        try:
            d = datetime.datetime.fromisoformat(r["timestamp"]).date()
        except Exception:
            continue
        counts_by_date[d] = counts_by_date.get(d, 0) + 1
    counts = [int(counts_by_date.get(d, 0)) for d in last_30]
    dates = [d.strftime("%d-%b") for d in last_30]
    return jsonify({"dates": dates, "counts": counts})


# ---------- Phase 1: classes / subjects / teachers ----------
@app.route("/admin")
@role_required("admin")
def admin_panel():
    with db.get_conn() as conn:
        classes = conn.execute(
            "SELECT id, name, section, academic_year FROM classes ORDER BY name, section"
        ).fetchall()
        subjects = conn.execute(
            """
            SELECT s.id, s.name, s.code, s.class_id, c.name AS class_name, c.section
            FROM subjects s JOIN classes c ON c.id = s.class_id
            ORDER BY c.name, s.name
            """
        ).fetchall()
        teachers = conn.execute(
            "SELECT id, username, full_name, created_at FROM users WHERE role='teacher' ORDER BY username"
        ).fetchall()
        assignments = conn.execute(
            """
            SELECT ta.id, u.username, c.name AS class_name, c.section, s.name AS subject_name
            FROM teacher_assignments ta
            JOIN users u ON u.id = ta.user_id
            JOIN classes c ON c.id = ta.class_id
            JOIN subjects s ON s.id = ta.subject_id
            ORDER BY u.username, c.name, s.name
            """
        ).fetchall()
    return render_template(
        "admin.html",
        classes=classes,
        subjects=subjects,
        teachers=teachers,
        assignments=assignments,
    )


@app.route("/api/classes", methods=["GET", "POST"])
@role_required("teacher", "admin")
def api_classes():
    if request.method == "GET":
        rows = db.list_classes_for_user(session["user_id"], session.get("role"))
        return jsonify(
            {
                "classes": [
                    {
                        "id": r["id"],
                        "name": r["name"],
                        "section": r["section"],
                        "label": db.class_label(r),
                        "academic_year": r["academic_year"],
                    }
                    for r in rows
                ]
            }
        )

    if session.get("role") != "admin":
        return jsonify({"error": "Only admin can create classes"}), 403

    data = request.get_json(silent=True) or request.form
    name = (data.get("name") or "").strip()
    section = (data.get("section") or "").strip()
    year = (data.get("academic_year") or "").strip() or None
    if not name:
        return jsonify({"error": "name required"}), 400
    now = datetime.datetime.utcnow().isoformat()
    with db.get_conn() as conn:
        cur = conn.execute(
            "INSERT INTO classes (name, section, academic_year, created_at) VALUES (?, ?, ?, ?)",
            (name, section, year, now),
        )
        class_id = cur.lastrowid
    return jsonify({"class_id": class_id}), 201


@app.route("/api/classes/<int:class_id>/subjects", methods=["GET", "POST"])
@role_required("teacher", "admin")
def api_subjects(class_id):
    if request.method == "GET":
        rows = db.list_subjects_for_class(session["user_id"], session.get("role"), class_id)
        return jsonify(
            {
                "subjects": [
                    {"id": r["id"], "name": r["name"], "code": r["code"], "class_id": r["class_id"]}
                    for r in rows
                ]
            }
        )

    if session.get("role") != "admin":
        return jsonify({"error": "Only admin can create subjects"}), 403

    data = request.get_json(silent=True) or request.form
    name = (data.get("name") or "").strip()
    code = (data.get("code") or "").strip() or None
    if not name:
        return jsonify({"error": "name required"}), 400
    now = datetime.datetime.utcnow().isoformat()
    with db.get_conn() as conn:
        exists = conn.execute("SELECT id FROM classes WHERE id=?", (class_id,)).fetchone()
        if not exists:
            return jsonify({"error": "class not found"}), 404
        cur = conn.execute(
            "INSERT INTO subjects (class_id, name, code, created_at) VALUES (?, ?, ?, ?)",
            (class_id, name, code, now),
        )
        subject_id = cur.lastrowid
    return jsonify({"subject_id": subject_id}), 201


@app.route("/api/teachers", methods=["POST"])
@role_required("admin")
def api_create_teacher():
    data = request.get_json(silent=True) or request.form
    username = (data.get("username") or "").strip()
    password = (data.get("password") or "").strip()
    full_name = (data.get("full_name") or "").strip() or None
    if not username or not password:
        return jsonify({"error": "username and password required"}), 400
    now = datetime.datetime.utcnow().isoformat()
    try:
        with db.get_conn() as conn:
            cur = conn.execute(
                """
                INSERT INTO users (username, password_hash, role, student_id, full_name, created_at)
                VALUES (?, ?, 'teacher', NULL, ?, ?)
                """,
                (username, generate_password_hash(password), full_name, now),
            )
            user_id = cur.lastrowid
    except Exception:
        return jsonify({"error": "username already exists"}), 409
    return jsonify({"user_id": user_id}), 201


@app.route("/api/assignments", methods=["POST"])
@role_required("admin")
def api_assign_teacher():
    data = request.get_json(silent=True) or request.form
    try:
        user_id = int(data.get("user_id"))
        class_id = int(data.get("class_id"))
        subject_id = int(data.get("subject_id"))
    except (TypeError, ValueError):
        return jsonify({"error": "user_id, class_id, subject_id required"}), 400

    with db.get_conn() as conn:
        teacher = conn.execute(
            "SELECT id FROM users WHERE id=? AND role='teacher'", (user_id,)
        ).fetchone()
        if not teacher:
            return jsonify({"error": "teacher not found"}), 404
        subject = conn.execute(
            "SELECT id FROM subjects WHERE id=? AND class_id=?", (subject_id, class_id)
        ).fetchone()
        if not subject:
            return jsonify({"error": "subject does not belong to class"}), 400
        now = datetime.datetime.utcnow().isoformat()
        try:
            cur = conn.execute(
                """
                INSERT INTO teacher_assignments (user_id, class_id, subject_id, created_at)
                VALUES (?, ?, ?, ?)
                """,
                (user_id, class_id, subject_id, now),
            )
            assignment_id = cur.lastrowid
        except Exception:
            return jsonify({"error": "assignment already exists"}), 409
    return jsonify({"assignment_id": assignment_id}), 201


@app.route("/api/my_assignments")
@role_required("teacher", "admin")
def api_my_assignments():
    rows = db.get_user_assignments(session["user_id"], session.get("role"))
    # For admin this returns subjects joined loosely; normalize response for teachers primarily.
    if session.get("role") == "admin":
        with db.get_conn() as conn:
            rows = conn.execute(
                """
                SELECT NULL AS id, NULL AS user_id, s.class_id, s.id AS subject_id,
                       c.name AS class_name, c.section,
                       s.name AS subject_name, s.code AS subject_code
                FROM subjects s
                JOIN classes c ON c.id = s.class_id
                ORDER BY c.name, c.section, s.name
                """
            ).fetchall()
    return jsonify(
        {
            "assignments": [
                {
                    "id": r["id"],
                    "class_id": r["class_id"],
                    "subject_id": r["subject_id"],
                    "class_label": f"{r['class_name']}"
                    + (f" — Sec {r['section']}" if r["section"] else ""),
                    "subject_name": r["subject_name"],
                    "subject_code": r["subject_code"],
                }
                for r in rows
            ]
        }
    )


# ---------- Students ----------
@app.route("/add_student", methods=["GET", "POST"])
@role_required("teacher", "admin")
def add_student():
    if request.method == "GET":
        classes = db.list_classes_for_user(session["user_id"], session.get("role"))
        return render_template("add_student.html", classes=classes, role=session.get("role"))

    data = request.form
    name = data.get("name", "").strip()
    roll = data.get("roll", "").strip()
    cls = data.get("class", "").strip()
    sec = data.get("sec", "").strip()
    reg_no = data.get("reg_no", "").strip()
    class_id_raw = data.get("class_id", "").strip()

    if not name:
        return jsonify({"error": "name required"}), 400

    class_id = None
    if class_id_raw:
        try:
            class_id = int(class_id_raw)
        except ValueError:
            return jsonify({"error": "invalid class_id"}), 400
        allowed = db.list_classes_for_user(session["user_id"], session.get("role"))
        if class_id not in {c["id"] for c in allowed}:
            return jsonify({"error": "Not authorized for this class"}), 403
        with db.get_conn() as conn:
            crow = conn.execute(
                "SELECT name, section FROM classes WHERE id=?", (class_id,)
            ).fetchone()
            if crow:
                cls = crow["name"]
                sec = crow["section"] or sec

    now = datetime.datetime.utcnow().isoformat()
    with db.get_conn() as conn:
        c = conn.cursor()
        c.execute(
            """
            INSERT INTO students (name, roll, class, section, reg_no, class_id, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (name, roll, cls, sec, reg_no, class_id, now),
        )
        sid = c.lastrowid
        if class_id:
            c.execute(
                "INSERT OR IGNORE INTO enrollments (student_id, class_id, created_at) VALUES (?, ?, ?)",
                (sid, class_id, now),
            )
    os.makedirs(os.path.join(DATASET_DIR, str(sid)), exist_ok=True)
    return jsonify({"student_id": sid})


@app.route("/upload_face", methods=["POST"])
@role_required("teacher", "admin")
def upload_face():
    student_id = request.form.get("student_id")
    if not student_id:
        return jsonify({"error": "student_id required"}), 400
    try:
        sid = int(student_id)
    except ValueError:
        return jsonify({"error": "invalid student_id"}), 400

    if not db.teacher_can_manage_student(session["user_id"], session.get("role"), sid):
        return jsonify({"error": "Not authorized for this student"}), 403

    files = request.files.getlist("images[]")
    files = files[: config.MAX_CAPTURE_IMAGES]
    saved = 0
    folder = os.path.join(DATASET_DIR, str(sid))
    os.makedirs(folder, exist_ok=True)
    for f in files:
        try:
            fname = f"{datetime.datetime.utcnow().timestamp():.6f}_{saved}.jpg"
            path = os.path.join(folder, fname)
            f.save(path)
            if saved == 0:
                _save_compact_profile(path, os.path.join(folder, "profile.jpg"))
            saved += 1
        except Exception as e:
            app.logger.error("save error: %s", e)
    return jsonify(
        {
            "saved": saved,
            "note": "Captures are temporary. After Train Model, only profile.jpg is kept.",
        }
    )


def _save_compact_profile(src_path: str, dest_path: str) -> None:
    """Store a small profile thumbnail for UI — not used as the face gallery."""
    try:
        import cv2

        img = cv2.imread(src_path)
        if img is None:
            shutil.copyfile(src_path, dest_path)
            return
        h, w = img.shape[:2]
        edge = max(h, w)
        if edge > config.PROFILE_MAX_EDGE:
            scale = config.PROFILE_MAX_EDGE / edge
            img = cv2.resize(img, (int(w * scale), int(h * scale)))
        cv2.imwrite(dest_path, img, [int(cv2.IMWRITE_JPEG_QUALITY), config.JPEG_QUALITY])
    except Exception:
        shutil.copyfile(src_path, dest_path)


@app.route("/api/students/<int:sid>/create_login", methods=["POST"])
@role_required("teacher", "admin")
def create_student_login(sid):
    """Teacher/admin issues a student account (public register is disabled by default)."""
    if not db.teacher_can_manage_student(session["user_id"], session.get("role"), sid):
        return jsonify({"error": "Not authorized for this student"}), 403

    data = request.get_json(silent=True) or request.form
    username = (data.get("username") or "").strip()
    password = (data.get("password") or "").strip()
    if not username or not password:
        return jsonify({"error": "username and password required"}), 400
    if len(password) < 8:
        return jsonify({"error": "password must be at least 8 characters"}), 400

    with db.get_conn() as conn:
        st = conn.execute("SELECT id FROM students WHERE id=?", (sid,)).fetchone()
        if not st:
            return jsonify({"error": "student not found"}), 404
        existing = conn.execute(
            "SELECT id FROM users WHERE student_id=? OR username=?", (sid, username)
        ).fetchone()
        if existing:
            return jsonify({"error": "login already exists for student or username"}), 409
        now = datetime.datetime.utcnow().isoformat()
        cur = conn.execute(
            """
            INSERT INTO users (username, password_hash, role, student_id, created_at)
            VALUES (?, ?, 'student', ?, ?)
            """,
            (username, generate_password_hash(password), sid, now),
        )
        user_id = cur.lastrowid
    return jsonify({"user_id": user_id, "username": username}), 201


@app.route("/student_photo/<int:sid>", methods=["GET"])
@login_required
def student_photo(sid):
    role = session.get("role")
    if role == "student" and session.get("student_id") != sid:
        abort(403)
    if role in ("teacher", "admin"):
        if not db.teacher_can_manage_student(session["user_id"], role, sid):
            # Admin always ok via helper; teachers restricted
            if role != "admin":
                abort(403)
    profile_path = os.path.join(DATASET_DIR, str(sid), "profile.jpg")
    if os.path.exists(profile_path):
        return send_file(profile_path, mimetype="image/jpeg")
    abort(404)


@app.route("/train_model", methods=["GET"])
@role_required("teacher", "admin")
def train_model_route():
    status = read_train_status()
    if status.get("running"):
        return jsonify({"status": "already_running"}), 202
    write_train_status({"running": True, "progress": 0, "message": "Starting training"})

    from model import train_model_background

    def _progress(p, m):
        running = p < 100
        write_train_status({"running": running, "progress": p, "message": m})

    t = threading.Thread(
        target=train_model_background,
        args=(DATASET_DIR, _progress),
    )
    t.daemon = True
    t.start()
    return jsonify({"status": "started"}), 202


@app.route("/storage_stats", methods=["GET"])
@role_required("admin", "teacher")
def storage_stats():
    from model import dataset_disk_usage

    usage = dataset_disk_usage(DATASET_DIR)
    return jsonify(
        {
            "dataset": usage,
            "face_embeddings": db.face_embedding_count(),
            "keep_capture_images": config.KEEP_CAPTURE_IMAGES,
            "max_capture_images": config.MAX_CAPTURE_IMAGES,
            "guidance": {
                "embeddings_mb_for_7000": round(7000 * 2 / 1024, 2),
                "profiles_mb_for_7000_est": round(7000 * 40 / 1024, 1),
                "raw_48jpg_mb_for_7000_est": round(7000 * 48 * 50 / 1024, 0),
            },
        }
    )


@app.route("/prune_captures", methods=["POST"])
@role_required("admin")
def prune_captures():
    """Admin: free disk by deleting enrollment frames (keeps profile.jpg)."""
    from model import prune_capture_images

    stats = prune_capture_images(DATASET_DIR, keep_profile=True)
    return jsonify(stats)


@app.route("/train_status", methods=["GET"])
@role_required("teacher", "admin")
def train_status():
    return jsonify(read_train_status())


@app.route("/mark_attendance", methods=["GET"])
@role_required("teacher", "admin")
def mark_attendance_page():
    classes = db.list_classes_for_user(session["user_id"], session.get("role"))
    return render_template("mark_attendance.html", classes=classes, role=session.get("role"))


@app.route("/recognize_face", methods=["POST"])
@role_required("teacher", "admin")
@_limit(config.RATELIMIT_RECOGNIZE)
def recognize_face():
    class_id, subject_id, err = _require_assignment()
    if err:
        return err

    if "image" not in request.files:
        return jsonify({"recognized": False, "error": "no image"}), 400
    img_file = request.files["image"]
    try:
        from model import (
            extract_embedding_for_image,
            load_model_if_exists,
            predict_with_model,
        )

        emb = extract_embedding_for_image(img_file.stream)
        if emb is None:
            return jsonify({"recognized": False, "error": "no face detected"}), 200

        clf = load_model_if_exists()
        if clf is None:
            return jsonify({"recognized": False, "error": "model not trained"}), 200

        # Phase 2: match only against students enrolled in this class
        enrolled = db.student_ids_in_class(class_id)
        pred_label, conf = predict_with_model(
            clf,
            emb,
            allowed_ids=enrolled if enrolled else None,
        )
        if pred_label is None:
            return jsonify({"recognized": False, "confidence": float(conf)}), 200

        sid = int(pred_label)

        with db.get_conn() as conn:
            row = conn.execute("SELECT name FROM students WHERE id=?", (sid,)).fetchone()
            name = row["name"] if row else "Unknown"

        saved = db.mark_present(
            [sid],
            class_id,
            subject_id,
            session.get("user_id"),
            source="live",
        )
        return jsonify(
            {
                "recognized": True,
                "student_id": sid,
                "name": name,
                "confidence": float(conf),
                "saved": saved > 0,
                "already_marked": saved == 0,
            }
        ), 200
    except Exception as e:
        app.logger.exception("recognize error")
        return jsonify({"recognized": False, "error": "recognition failed"}), 500


@app.route("/attendance_record", methods=["GET"])
@role_required("teacher", "admin")
def attendance_record():
    period = request.args.get("period", "all")
    class_id = request.args.get("class_id", type=int)
    subject_id = request.args.get("subject_id", type=int)

    class_ids = db.teacher_class_ids(session["user_id"], session.get("role"))
    classes = db.list_classes_for_user(session["user_id"], session.get("role"))

    query = """
        SELECT a.id, a.student_id, a.name, a.timestamp, a.class_id, a.subject_id,
               c.name AS class_name, c.section, s.name AS subject_name
        FROM attendance a
        LEFT JOIN classes c ON c.id = a.class_id
        LEFT JOIN subjects s ON s.id = a.subject_id
        WHERE 1=1
    """
    params = []

    if class_ids is not None:
        if not class_ids:
            records = []
            return render_template(
                "attendance_record.html",
                records=records,
                period=period,
                classes=classes,
                selected_class_id=class_id,
                selected_subject_id=subject_id,
            )
        placeholders = ",".join("?" * len(class_ids))
        query += f" AND (a.class_id IN ({placeholders}) OR a.class_id IS NULL)"
        params.extend(class_ids)

    if class_id:
        if class_ids is not None and class_id not in class_ids:
            return jsonify({"error": "Not authorized"}), 403
        query += " AND a.class_id = ?"
        params.append(class_id)
    if subject_id:
        query += " AND a.subject_id = ?"
        params.append(subject_id)

    if period == "daily":
        query += " AND date(a.timestamp) = ?"
        params.append(datetime.date.today().isoformat())
    elif period == "weekly":
        start = (datetime.date.today() - datetime.timedelta(days=7)).isoformat()
        query += " AND date(a.timestamp) >= ?"
        params.append(start)
    elif period == "monthly":
        start = (datetime.date.today() - datetime.timedelta(days=30)).isoformat()
        query += " AND date(a.timestamp) >= ?"
        params.append(start)

    query += " ORDER BY a.timestamp DESC LIMIT 5000"
    with db.get_conn() as conn:
        records = conn.execute(query, params).fetchall()

    return render_template(
        "attendance_record.html",
        records=records,
        period=period,
        classes=classes,
        selected_class_id=class_id,
        selected_subject_id=subject_id,
    )


@app.route("/download_csv", methods=["GET"])
@role_required("teacher", "admin")
def download_csv():
    class_ids = db.teacher_class_ids(session["user_id"], session.get("role"))
    with db.get_conn() as conn:
        if class_ids is None:
            rows = conn.execute(
                """
                SELECT a.id, a.student_id, a.name, a.timestamp, c.name, c.section, s.name, s.code
                FROM attendance a
                LEFT JOIN classes c ON c.id = a.class_id
                LEFT JOIN subjects s ON s.id = a.subject_id
                ORDER BY a.timestamp DESC
                """
            ).fetchall()
        elif not class_ids:
            rows = []
        else:
            placeholders = ",".join("?" * len(class_ids))
            rows = conn.execute(
                f"""
                SELECT a.id, a.student_id, a.name, a.timestamp, c.name, c.section, s.name, s.code
                FROM attendance a
                LEFT JOIN classes c ON c.id = a.class_id
                LEFT JOIN subjects s ON s.id = a.subject_id
                WHERE a.class_id IN ({placeholders})
                ORDER BY a.timestamp DESC
                """,
                tuple(class_ids),
            ).fetchall()

    output = io.StringIO()
    output.write("id,student_id,name,timestamp,class,section,subject,subject_code\n")
    for r in rows:
        output.write(
            f'{r[0]},{r[1]},{r[2]},{r[3]},{r[4] or ""},{r[5] or ""},{r[6] or ""},{r[7] or ""}\n'
        )
    mem = io.BytesIO()
    mem.write(output.getvalue().encode("utf-8"))
    mem.seek(0)
    return send_file(
        mem, as_attachment=True, download_name="attendance.csv", mimetype="text/csv"
    )


@app.route("/students", methods=["GET"])
@role_required("teacher", "admin")
def students_list():
    class_ids = db.teacher_class_ids(session["user_id"], session.get("role"))
    with db.get_conn() as conn:
        if class_ids is None:
            rows = conn.execute(
                "SELECT id, name, roll, class, section, reg_no, class_id, created_at FROM students ORDER BY id DESC"
            ).fetchall()
        elif not class_ids:
            rows = []
        else:
            placeholders = ",".join("?" * len(class_ids))
            rows = conn.execute(
                f"""
                SELECT DISTINCT st.id, st.name, st.roll, st.class, st.section, st.reg_no, st.class_id, st.created_at
                FROM students st
                LEFT JOIN enrollments e ON e.student_id = st.id
                WHERE st.class_id IN ({placeholders}) OR e.class_id IN ({placeholders})
                ORDER BY st.id DESC
                """,
                tuple(class_ids) + tuple(class_ids),
            ).fetchall()
    data = [
        {
            "id": r["id"],
            "name": r["name"],
            "roll": r["roll"],
            "class": r["class"],
            "section": r["section"],
            "reg_no": r["reg_no"],
            "class_id": r["class_id"],
            "created_at": r["created_at"],
        }
        for r in rows
    ]
    return jsonify({"students": data})


@app.route("/manage_students", methods=["GET"])
@role_required("teacher", "admin")
def manage_students_page():
    """List students and edit name / roll / class / section."""
    classes = db.list_classes_for_user(session["user_id"], session.get("role"))
    class_ids = db.teacher_class_ids(session["user_id"], session.get("role"))
    with db.get_conn() as conn:
        if class_ids is None:
            rows = conn.execute(
                """
                SELECT st.id, st.name, st.roll, st.class, st.section, st.reg_no, st.class_id,
                       c.name AS class_name, c.section AS class_section
                FROM students st
                LEFT JOIN classes c ON c.id = st.class_id
                ORDER BY st.name
                """
            ).fetchall()
        elif not class_ids:
            rows = []
        else:
            placeholders = ",".join("?" * len(class_ids))
            rows = conn.execute(
                f"""
                SELECT DISTINCT st.id, st.name, st.roll, st.class, st.section, st.reg_no, st.class_id,
                       c.name AS class_name, c.section AS class_section
                FROM students st
                LEFT JOIN enrollments e ON e.student_id = st.id
                LEFT JOIN classes c ON c.id = st.class_id
                WHERE st.class_id IN ({placeholders}) OR e.class_id IN ({placeholders})
                ORDER BY st.name
                """,
                tuple(class_ids) + tuple(class_ids),
            ).fetchall()

    students = []
    for r in rows:
        label = ""
        if r["class_name"]:
            label = r["class_name"]
            if r["class_section"]:
                label += f" — Sec {r['class_section']}"
        elif r["class"]:
            label = r["class"]
            if r["section"]:
                label += f" — Sec {r['section']}"
        students.append(
            {
                "id": r["id"],
                "name": r["name"],
                "roll": r["roll"] or "",
                "reg_no": r["reg_no"] or "",
                "class_id": r["class_id"],
                "class_label": label or "—",
                "class": r["class"] or "",
                "section": r["section"] or "",
            }
        )

    return render_template(
        "manage_students.html",
        students=students,
        classes=classes,
        role=session.get("role"),
    )


@app.route("/api/students/<int:sid>", methods=["GET", "PUT", "PATCH"])
@role_required("teacher", "admin")
def api_student_update(sid):
    if not db.teacher_can_manage_student(session["user_id"], session.get("role"), sid):
        return jsonify({"error": "Not authorized for this student"}), 403

    if request.method == "GET":
        with db.get_conn() as conn:
            row = conn.execute(
                """
                SELECT id, name, roll, class, section, reg_no, class_id, created_at
                FROM students WHERE id=?
                """,
                (sid,),
            ).fetchone()
        if not row:
            return jsonify({"error": "student not found"}), 404
        return jsonify(
            {
                "id": row["id"],
                "name": row["name"],
                "roll": row["roll"] or "",
                "class": row["class"] or "",
                "section": row["section"] or "",
                "reg_no": row["reg_no"] or "",
                "class_id": row["class_id"],
            }
        )

    data = request.get_json(silent=True) or {}
    name = str(data.get("name", "")).strip()
    roll = str(data.get("roll", "")).strip()
    reg_no = str(data.get("reg_no", "")).strip()
    class_id_raw = data.get("class_id", None)

    if not name:
        return jsonify({"error": "Name is required"}), 400

    class_id = None
    cls_name = ""
    section = ""
    if class_id_raw is not None and str(class_id_raw).strip() != "":
        try:
            class_id = int(class_id_raw)
        except (TypeError, ValueError):
            return jsonify({"error": "invalid class_id"}), 400
        allowed = db.list_classes_for_user(session["user_id"], session.get("role"))
        if class_id not in {c["id"] for c in allowed}:
            return jsonify({"error": "Not authorized for this class"}), 403
        with db.get_conn() as conn:
            crow = conn.execute(
                "SELECT name, section FROM classes WHERE id=?", (class_id,)
            ).fetchone()
            if not crow:
                return jsonify({"error": "Class not found"}), 404
            cls_name = crow["name"]
            section = crow["section"] or ""

    roll_db = roll or None
    now = datetime.datetime.utcnow().isoformat()
    try:
        with db.get_conn() as conn:
            existing = conn.execute("SELECT id, class_id FROM students WHERE id=?", (sid,)).fetchone()
            if not existing:
                return jsonify({"error": "student not found"}), 404
            old_class_id = existing["class_id"]

            if class_id is not None:
                conn.execute(
                    """
                    UPDATE students
                    SET name=?, roll=?, reg_no=?, class_id=?, class=?, section=?
                    WHERE id=?
                    """,
                    (name, roll_db, reg_no, class_id, cls_name, section, sid),
                )
                # Move enrollment to the new class
                if old_class_id and int(old_class_id) != int(class_id):
                    conn.execute(
                        "DELETE FROM enrollments WHERE student_id=? AND class_id=?",
                        (sid, old_class_id),
                    )
                conn.execute(
                    "INSERT OR IGNORE INTO enrollments (student_id, class_id, created_at) VALUES (?, ?, ?)",
                    (sid, class_id, now),
                )
            else:
                conn.execute(
                    """
                    UPDATE students
                    SET name=?, roll=?, reg_no=?
                    WHERE id=?
                    """,
                    (name, roll_db, reg_no, sid),
                )
    except db.IntegrityError:
        return jsonify({"error": f"Roll number '{roll}' already exists. Use a unique roll."}), 409

    return jsonify(
        {
            "updated": True,
            "student_id": sid,
            "name": name,
            "roll": roll,
            "reg_no": reg_no,
            "class_id": class_id,
            "class": cls_name,
            "section": section,
        }
    )


@app.route("/students/<int:sid>", methods=["DELETE"])
@role_required("teacher", "admin")
def delete_student(sid):
    """Remove a student (and related enrollment/attendance/embeddings/login)."""
    if not db.teacher_can_manage_student(session["user_id"], session.get("role"), sid):
        return jsonify({"error": "Not authorized for this student"}), 403
    db.delete_student_cascade(sid)
    folder = os.path.join(DATASET_DIR, str(sid))
    if os.path.isdir(folder):
        shutil.rmtree(folder, ignore_errors=True)
    return jsonify({"deleted": True})


@app.route("/recognize_classroom", methods=["POST"])
@role_required("teacher", "admin")
@_limit(config.RATELIMIT_RECOGNIZE)
def recognize_classroom():
    class_id, subject_id, err = _require_assignment()
    if err:
        return err

    if "image" not in request.files:
        return jsonify({"error": "no image"}), 400
    img_file = request.files["image"]

    try:
        from model import (
            CLASSROOM_MARGIN,
            CLASSROOM_SIM_THRESHOLD,
            extract_embeddings_for_classroom,
            load_model_if_exists,
            predict_with_model,
        )
        try:
            from model import CLASSROOM_STRONG_THRESHOLD
        except ImportError:
            CLASSROOM_STRONG_THRESHOLD = 0.32

        faces = extract_embeddings_for_classroom(img_file.stream)
        if not faces:
            return jsonify({"faces": [], "message": "No faces detected"}), 200

        clf = load_model_if_exists()
        if clf is None:
            return jsonify({"error": "model not trained"}), 200

        enrolled = db.student_ids_in_class(class_id)
        if not enrolled:
            return (
                jsonify(
                    {
                        "faces": [],
                        "error": "No students enrolled in this class. Add students to this class and Train Model first.",
                    }
                ),
                200,
            )

        # Small demo classes: allow slightly lower match score (far faces are weaker)
        sim_thr = CLASSROOM_SIM_THRESHOLD
        if len(enrolled) <= 5:
            sim_thr = min(sim_thr, 0.25)

        today = datetime.date.today().isoformat()
        results_list = []
        # Keep best match per student when one person appears multiple times
        best_by_student = {}

        with db.get_conn() as conn:
            c = conn.cursor()
            for face in faces:
                emb = face["embedding"]
                pred_label, conf = predict_with_model(
                    clf,
                    emb,
                    allowed_ids=enrolled,
                    similarity_threshold=sim_thr,
                    margin=CLASSROOM_MARGIN,
                )
                # Always compute closest gallery face for teacher feedback
                closest_id, closest_conf = predict_with_model(
                    clf,
                    emb,
                    allowed_ids=enrolled,
                    similarity_threshold=0.0,
                    margin=0.0,
                )

                entry = {
                    "bbox": face["bbox"],
                    "confidence": float(conf),
                    "recognized": False,
                    "name": "Unknown",
                    "student_id": None,
                    "already_marked": False,
                    "needs_review": True,
                    "closest_name": None,
                    "closest_confidence": float(closest_conf) if closest_id is not None else 0.0,
                }
                if closest_id is not None:
                    crow = c.execute(
                        "SELECT name, roll FROM students WHERE id=?", (int(closest_id),)
                    ).fetchone()
                    if crow:
                        entry["closest_name"] = crow["name"]
                        entry["closest_roll"] = crow["roll"]

                if pred_label is not None:
                    sid = int(pred_label)
                    c.execute(
                        "SELECT name, roll, class FROM students WHERE id=?", (sid,)
                    )
                    row = c.fetchone()
                    if row:
                        entry["recognized"] = True
                        entry["name"] = row["name"]
                        entry["roll"] = row["roll"]
                        entry["class"] = row["class"]
                        entry["student_id"] = sid
                        entry["confidence"] = float(conf)
                        # Weak matches need teacher confirmation (UI hides raw %)
                        entry["needs_review"] = float(conf) < CLASSROOM_STRONG_THRESHOLD

                        c.execute(
                            """
                            SELECT id FROM attendance
                            WHERE student_id=? AND class_id=? AND subject_id=? AND date(timestamp)=?
                            """,
                            (sid, class_id, subject_id, today),
                        )
                        if c.fetchone():
                            entry["already_marked"] = True

                        prev = best_by_student.get(sid)
                        if prev is None or entry["confidence"] > prev["confidence"]:
                            best_by_student[sid] = entry
                        continue

                # Not matched — keep label simple for teachers
                entry["name"] = "Unknown"
                entry["needs_review"] = True
                entry["confidence"] = float(entry.get("closest_confidence") or conf or 0.0)
                results_list.append(entry)

        # Recognized students once each + unknowns
        results_list = list(best_by_student.values()) + [
            e for e in results_list if not e.get("recognized")
        ]

        return jsonify(
            {
                "faces": results_list,
                "class_id": class_id,
                "subject_id": subject_id,
                "detected": len(faces),
                "matched": len(best_by_student),
                "phase": 2,
            }
        ), 200

    except Exception as e:
        app.logger.exception("classroom recognize error")
        return jsonify({"error": "recognition failed"}), 500


@app.route("/mark_attendance_classroom", methods=["GET"])
@role_required("teacher", "admin")
def mark_attendance_classroom_page():
    classes = db.list_classes_for_user(session["user_id"], session.get("role"))
    return render_template(
        "mark_attendance_classroom.html", classes=classes, role=session.get("role")
    )


@app.route("/confirm_classroom_attendance", methods=["POST"])
@role_required("teacher", "admin")
def confirm_classroom_attendance():
    class_id, subject_id, err = _require_assignment()
    if err:
        return err

    data = request.get_json(silent=True) or {}
    student_ids = data.get("student_ids", [])
    if not student_ids:
        return jsonify({"saved": 0}), 200

    enrolled = db.student_ids_in_class(class_id)
    if enrolled:
        student_ids = [sid for sid in student_ids if int(sid) in enrolled]

    saved = db.mark_present(
        [int(sid) for sid in student_ids],
        class_id,
        subject_id,
        session.get("user_id"),
        source="classroom",
    )
    return jsonify({"saved": saved}), 200


@app.route("/attendance_record/<int:record_id>", methods=["DELETE"])
@role_required("teacher", "admin")
def delete_attendance_record(record_id):
    class_ids = db.teacher_class_ids(session["user_id"], session.get("role"))
    with db.get_conn() as conn:
        row = conn.execute(
            "SELECT id, class_id FROM attendance WHERE id=?", (record_id,)
        ).fetchone()
        if not row:
            return jsonify({"error": "not found"}), 404
        if class_ids is not None and row["class_id"] not in class_ids:
            return jsonify({"error": "Not authorized"}), 403
        conn.execute("DELETE FROM attendance WHERE id=?", (record_id,))
    return jsonify({"deleted": True})


@app.route("/analytics", methods=["GET"])
@role_required("teacher", "admin")
def analytics():
    class_id = request.args.get("class_id", type=int)
    subject_id = request.args.get("subject_id", type=int)
    classes = db.list_classes_for_user(session["user_id"], session.get("role"))
    class_ids = db.teacher_class_ids(session["user_id"], session.get("role"))

    if class_id and class_ids is not None and class_id not in class_ids:
        return jsonify({"error": "Not authorized"}), 403

    with db.get_conn() as conn:
        if class_id:
            students = conn.execute(
                """
                SELECT DISTINCT st.id, st.name, st.roll, st.created_at
                FROM students st
                LEFT JOIN enrollments e ON e.student_id = st.id
                WHERE st.class_id=? OR e.class_id=?
                ORDER BY st.name ASC
                """,
                (class_id, class_id),
            ).fetchall()
        elif class_ids is None:
            students = conn.execute(
                "SELECT id, name, roll, created_at FROM students ORDER BY name ASC"
            ).fetchall()
        elif not class_ids:
            students = []
        else:
            placeholders = ",".join("?" * len(class_ids))
            students = conn.execute(
                f"""
                SELECT DISTINCT st.id, st.name, st.roll, st.created_at
                FROM students st
                LEFT JOIN enrollments e ON e.student_id = st.id
                WHERE st.class_id IN ({placeholders}) OR e.class_id IN ({placeholders})
                ORDER BY st.name ASC
                """,
                tuple(class_ids) + tuple(class_ids),
            ).fetchall()

        rows = []
        for st in students:
            sid = st["id"]
            q = "SELECT COUNT(DISTINCT date(timestamp)) FROM attendance WHERE student_id=?"
            params = [sid]
            if class_id:
                q += " AND class_id=?"
                params.append(class_id)
            if subject_id:
                q += " AND subject_id=?"
                params.append(subject_id)
            days_present = conn.execute(q, params).fetchone()[0] or 0

            try:
                start_date = datetime.datetime.fromisoformat(st["created_at"]).date()
            except Exception:
                start_date = datetime.date.today()
            total_days = max((datetime.date.today() - start_date).days + 1, 1)
            pct = round((days_present / total_days) * 100, 1)
            rows.append(
                {
                    "id": sid,
                    "name": st["name"],
                    "roll": st["roll"] or "-",
                    "days_present": days_present,
                    "total_days": total_days,
                    "pct": pct,
                }
            )

    return render_template(
        "analytics.html",
        rows=rows,
        classes=classes,
        selected_class_id=class_id,
        selected_subject_id=subject_id,
    )


@app.route("/copilot", methods=["GET"])
@role_required("teacher", "admin")
def copilot_page():
    return render_template(
        "copilot.html",
        role=session.get("role"),
        username=session.get("username"),
    )


@app.route("/api/copilot", methods=["POST"])
@role_required("teacher", "admin")
@_limit(config.RATELIMIT_DEFAULT)
def api_copilot():
    """Rules-based AI Attendance Copilot — answers from live DB (no LLM)."""
    data = request.get_json(silent=True) or {}
    query = (data.get("query") or data.get("message") or "").strip()
    if len(query) > 500:
        return jsonify({"error": "Query too long"}), 400
    try:
        import copilot as copilot_mod

        result = copilot_mod.ask(session["user_id"], session.get("role"), query)
        return jsonify(result), 200
    except Exception:
        app.logger.exception("copilot error")
        return jsonify({"error": "Copilot failed", "ok": False, "answer": "Something went wrong."}), 500


@app.route("/register_export", methods=["GET"])
@role_required("teacher", "admin")
def register_export_page():
    """ITM-style monthly attendance register Excel for higher authority."""
    import calendar

    classes = db.list_classes_for_user(session["user_id"], session.get("role"))
    now = datetime.datetime.now()
    return render_template(
        "register_export.html",
        classes=classes,
        current_month=now.month,
        current_year=now.year,
        month_names={i: calendar.month_name[i] for i in range(1, 13)},
        username=session.get("username"),
        role=session.get("role"),
        error=None,
    )


@app.route("/download_register_xlsx", methods=["GET"])
@role_required("teacher", "admin")
def download_register_xlsx():
    """Download monthly register .xlsx (paper-register layout)."""
    import calendar

    try:
        class_id = int(request.args.get("class_id"))
        subject_id = int(request.args.get("subject_id"))
        year = int(request.args.get("year"))
        month = int(request.args.get("month"))
    except (TypeError, ValueError):
        return jsonify({"error": "class_id, subject_id, year, month required"}), 400

    if month < 1 or month > 12:
        return jsonify({"error": "invalid month"}), 400

    if not db.teacher_can_access(
        session["user_id"], session.get("role"), class_id, subject_id
    ):
        return jsonify({"error": "Not authorized for this class/subject"}), 403

    session_label = (request.args.get("session") or "").strip()
    faculty = (request.args.get("faculty") or "").strip()
    branch = (request.args.get("branch") or "").strip()

    try:
        from register_export import build_register_workbook

        data = build_register_workbook(
            class_id=class_id,
            subject_id=subject_id,
            year=year,
            month=month,
            session_label=session_label,
            faculty_name=faculty,
            branch_label=branch,
        )
    except Exception:
        app.logger.exception("register export failed")
        return jsonify({"error": "Failed to build register Excel"}), 500

    fname = f"attendance_register_{year}_{month:02d}_c{class_id}_s{subject_id}.xlsx"
    mem = io.BytesIO(data)
    mem.seek(0)
    return send_file(
        mem,
        as_attachment=True,
        download_name=fname,
        mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )


@app.route("/check_face", methods=["POST"])
@role_required("teacher", "admin")
def check_face():
    if "image" not in request.files:
        return jsonify({"ok": False, "reason": "no image"}), 400
    from model import check_face_quality

    result = check_face_quality(request.files["image"].stream)
    return jsonify(result), 200


if __name__ == "__main__":
    # Development only. Production: gunicorn -c gunicorn.conf.py wsgi:app
    if config.IS_PRODUCTION:
        raise SystemExit("Refusing to start debug server in production. Use gunicorn (see DEPLOY.md).")
    app.run(debug=True, port=5001)
