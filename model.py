import os
import cv2
import numpy as np
import pickle
from sklearn.neighbors import KNeighborsClassifier
from insightface.app import FaceAnalysis

MODEL_PATH = "model.pkl"

_face_app = None


def get_face_app():
    """Lazy-load InsightFace so admin/setup works before models download."""
    global _face_app
    if _face_app is None:
        _face_app = FaceAnalysis(name="buffalo_l")
        _face_app.prepare(ctx_id=0, det_size=(640, 640))
    return _face_app


def extract_embedding_for_image(stream_or_bytes):
    data = stream_or_bytes.read()
    arr = np.frombuffer(data, np.uint8)
    img = cv2.imdecode(arr, cv2.IMREAD_COLOR)
    if img is None:
        return None

    faces = get_face_app().get(img)
    if len(faces) == 0:
        return None

    return faces[0].normed_embedding


def extract_embeddings_for_classroom(stream_or_bytes):
    data = stream_or_bytes.read()
    arr = np.frombuffer(data, np.uint8)
    img = cv2.imdecode(arr, cv2.IMREAD_COLOR)
    if img is None:
        return []

    faces = get_face_app().get(img)

    results = []
    for f in faces:
        x1, y1, x2, y2 = f.bbox.astype(int)
        results.append(
            {
                "bbox": [int(x1), int(y1), int(x2), int(y2)],
                "embedding": f.normed_embedding,
            }
        )
    return results


def load_model_if_exists():
    if not os.path.exists(MODEL_PATH):
        return None
    with open(MODEL_PATH, "rb") as f:
        return pickle.load(f)


def predict_with_model(bundle, emb, distance_threshold=0.45):
    clf = bundle["clf"]
    X = bundle["X"]
    y = bundle["y"]

    similarities = X @ emb
    distances = 1 - similarities
    best_idx = np.argmin(distances)
    best_distance = distances[best_idx]

    if best_distance > distance_threshold:
        return None, 0.0

    proba = clf.predict_proba([emb])[0]
    idx = np.argmax(proba)
    label = clf.classes_[idx]
    conf = float(proba[idx])
    return label, conf


def train_model_background(dataset_dir, progress_callback=None):
    X = []
    y = []
    student_dirs = [
        d
        for d in os.listdir(dataset_dir)
        if os.path.isdir(os.path.join(dataset_dir, d))
    ]
    total_students = max(1, len(student_dirs))
    processed = 0

    for sid in student_dirs:
        folder = os.path.join(dataset_dir, sid)
        files = [
            f
            for f in os.listdir(folder)
            if f.lower().endswith((".jpg", ".jpeg", ".png")) and f != "profile.jpg"
        ]
        for fn in files:
            path = os.path.join(folder, fn)
            img = cv2.imread(path)
            if img is None:
                continue
            faces = get_face_app().get(img)
            if len(faces) == 0:
                continue
            X.append(faces[0].normed_embedding)
            y.append(int(sid))
        processed += 1
        if progress_callback:
            pct = int((processed / total_students) * 80)
            progress_callback(pct, f"Processed {processed}/{total_students} students")

    if len(X) == 0:
        if progress_callback:
            progress_callback(0, "No training data found")
        return

    X = np.stack(X)
    y = np.array(y)

    if progress_callback:
        progress_callback(85, "Training KNN classifier...")
    n_neighbors = min(3, len(set(y)))
    clf = KNeighborsClassifier(n_neighbors=n_neighbors, metric="euclidean")
    clf.fit(X, y)

    bundle = {"clf": clf, "X": X, "y": y}
    with open(MODEL_PATH, "wb") as f:
        pickle.dump(bundle, f)

    if progress_callback:
        progress_callback(100, "Training complete")


def check_face_quality(stream_or_bytes, min_face_ratio=0.04):
    """
    Quick per-frame quality check used during guided capture.
    Rejects frames with: no face, multiple faces, or a face too small
    (person too far from camera).
    """
    data = stream_or_bytes.read()
    arr = np.frombuffer(data, np.uint8)
    img = cv2.imdecode(arr, cv2.IMREAD_COLOR)
    if img is None:
        return {"ok": False, "reason": "invalid image"}

    faces = get_face_app().get(img)
    if len(faces) == 0:
        return {"ok": False, "reason": "No face detected"}
    if len(faces) > 1:
        return {"ok": False, "reason": "More than one face in frame"}

    h, w = img.shape[:2]
    x1, y1, x2, y2 = faces[0].bbox
    face_area_ratio = ((x2 - x1) * (y2 - y1)) / (w * h)
    if face_area_ratio < min_face_ratio:
        return {"ok": False, "reason": "Move closer to the camera"}

    return {"ok": True}
