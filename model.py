"""Face recognition — Phase 2 (80+ classroom scale).

Upgrades vs Phase 1:
- Class-scoped gallery matching (only compare against enrolled students)
- Unified cosine similarity scoring (no KNN/proba mismatch)
- Higher-res classroom detection + overlap NMS
- Incremental embedding cache (retrain only new/changed images)
"""

from __future__ import annotations

import os
import pickle
from typing import Iterable, Optional, Sequence, Set

import cv2
import numpy as np
from insightface.app import FaceAnalysis
from sklearn.neighbors import KNeighborsClassifier

MODEL_PATH = "model.pkl"
CACHE_PATH = "embedding_cache.pkl"

# Cosine similarity thresholds (embeddings are L2-normalized).
LIVE_SIM_THRESHOLD = 0.38
CLASSROOM_SIM_THRESHOLD = 0.36
# Require winner to beat 2nd place by this margin when both are in-class.
MARGIN = 0.03

_face_apps: dict[tuple[int, int], FaceAnalysis] = {}


def get_face_app(det_size: tuple[int, int] = (640, 640)) -> FaceAnalysis:
    """Lazy-load InsightFace; cache one instance per detection size."""
    key = (int(det_size[0]), int(det_size[1]))
    if key not in _face_apps:
        app = FaceAnalysis(name="buffalo_l")
        # ctx_id=-1 forces CPU if no GPU; 0 uses GPU when available.
        ctx = 0
        try:
            app.prepare(ctx_id=ctx, det_size=key)
        except Exception:
            app.prepare(ctx_id=-1, det_size=key)
        _face_apps[key] = app
    return _face_apps[key]


def _decode_image(stream_or_bytes) -> Optional[np.ndarray]:
    data = stream_or_bytes.read()
    arr = np.frombuffer(data, np.uint8)
    img = cv2.imdecode(arr, cv2.IMREAD_COLOR)
    return img


def extract_embedding_for_image(stream_or_bytes):
    img = _decode_image(stream_or_bytes)
    if img is None:
        return None

    faces = get_face_app((640, 640)).get(img)
    if len(faces) == 0:
        return None

    # Largest face for live / single-person capture
    faces = sorted(
        faces,
        key=lambda f: (f.bbox[2] - f.bbox[0]) * (f.bbox[3] - f.bbox[1]),
        reverse=True,
    )
    return faces[0].normed_embedding


def _iou(a, b) -> float:
    ax1, ay1, ax2, ay2 = a
    bx1, by1, bx2, by2 = b
    ix1, iy1 = max(ax1, bx1), max(ay1, by1)
    ix2, iy2 = min(ax2, bx2), min(ay2, by2)
    iw, ih = max(0, ix2 - ix1), max(0, iy2 - iy1)
    inter = iw * ih
    if inter <= 0:
        return 0.0
    area_a = max(0, ax2 - ax1) * max(0, ay2 - ay1)
    area_b = max(0, bx2 - bx1) * max(0, by2 - by1)
    union = area_a + area_b - inter
    return inter / union if union > 0 else 0.0


def _nms_faces(faces, iou_thresh: float = 0.45):
    """Drop overlapping detections, keep higher detection score."""
    if not faces:
        return []
    ordered = sorted(faces, key=lambda f: float(getattr(f, "det_score", 0.0)), reverse=True)
    kept = []
    for f in ordered:
        bbox = f.bbox.astype(int)
        if any(_iou(bbox, k.bbox.astype(int)) >= iou_thresh for k in kept):
            continue
        kept.append(f)
    return kept


def extract_embeddings_for_classroom(stream_or_bytes, min_face_px: int = 28):
    """
    Detect many faces in a wide classroom photo.
    Uses a larger detector window than live mode so far/small faces survive.
    """
    img = _decode_image(stream_or_bytes)
    if img is None:
        return []

    h, w = img.shape[:2]
    # Upscale small phone photos so far seats get more pixels
    scale = 1.0
    long_edge = max(h, w)
    if long_edge < 1600:
        scale = 1600 / long_edge
        img = cv2.resize(img, (int(w * scale), int(h * scale)), interpolation=cv2.INTER_CUBIC)

    # Higher det_size finds more small faces in crowded frames
    faces = get_face_app((960, 960)).get(img)
    faces = _nms_faces(faces)

    results = []
    for f in faces:
        x1, y1, x2, y2 = f.bbox.astype(int)
        fw, fh = x2 - x1, y2 - y1
        if min(fw, fh) < min_face_px * scale:
            continue
        # Map bbox back to original image coordinates if we upscaled
        if scale != 1.0:
            x1, y1, x2, y2 = [int(v / scale) for v in (x1, y1, x2, y2)]
        results.append(
            {
                "bbox": [int(x1), int(y1), int(x2), int(y2)],
                "embedding": f.normed_embedding,
                "det_score": float(getattr(f, "det_score", 0.0)),
            }
        )
    return results


def load_model_if_exists():
    if not os.path.exists(MODEL_PATH):
        return None
    with open(MODEL_PATH, "rb") as f:
        return pickle.load(f)


def _normalize_allowed(allowed_ids: Optional[Iterable[int]]) -> Optional[Set[int]]:
    if allowed_ids is None:
        return None
    return {int(x) for x in allowed_ids}


def predict_with_model(
    bundle,
    emb,
    allowed_ids: Optional[Iterable[int]] = None,
    similarity_threshold: Optional[float] = None,
    use_centroids: bool = True,
):
    """
    Match embedding with cosine similarity against (optionally class-scoped) gallery.

    Returns (student_id | None, confidence_similarity).
    Confidence is cosine similarity in [0, 1] (not KNN proba).
    """
    if emb is None or bundle is None:
        return None, 0.0

    emb = np.asarray(emb, dtype=np.float32)
    allowed = _normalize_allowed(allowed_ids)
    thr = (
        similarity_threshold
        if similarity_threshold is not None
        else LIVE_SIM_THRESHOLD
    )

    # Prefer per-student centroids when available (faster + stabler for large classes)
    centroids = bundle.get("centroids") if use_centroids else None
    if centroids:
        ids = []
        mats = []
        for sid, vec in centroids.items():
            sid = int(sid)
            if allowed is not None and sid not in allowed:
                continue
            ids.append(sid)
            mats.append(np.asarray(vec, dtype=np.float32))
        if not ids:
            return None, 0.0
        M = np.stack(mats)
        sims = M @ emb
    else:
        X = np.asarray(bundle["X"], dtype=np.float32)
        y = np.asarray(bundle["y"])
        if allowed is not None:
            mask = np.isin(y, list(allowed))
            if not np.any(mask):
                return None, 0.0
            X = X[mask]
            y = y[mask]
        sims = X @ emb
        ids = y

    order = np.argsort(-sims)
    best_i = int(order[0])
    best_sim = float(sims[best_i])
    best_id = int(ids[best_i])

    if best_sim < thr:
        return None, best_sim

    # Margin check against next different identity (reduces lookalike swaps)
    if len(order) > 1:
        for j in order[1:]:
            other_id = int(ids[int(j)])
            if other_id != best_id:
                second = float(sims[int(j)])
                if best_sim - second < MARGIN:
                    return None, best_sim
                break

    return best_id, best_sim


def _load_cache() -> dict:
    if not os.path.exists(CACHE_PATH):
        return {}
    try:
        with open(CACHE_PATH, "rb") as f:
            return pickle.load(f)
    except Exception:
        return {}


def _save_cache(cache: dict) -> None:
    with open(CACHE_PATH, "wb") as f:
        pickle.dump(cache, f)


def _file_signature(path: str) -> str:
    st = os.stat(path)
    return f"{st.st_mtime_ns}:{st.st_size}"


def train_model_background(dataset_dir, progress_callback=None):
    """
    Build gallery + centroids. Reuses embedding_cache.pkl so adding one student
    does not re-embed the whole college.
    """
    cache = _load_cache()  # {sid_str: {filename: {"sig": ..., "emb": ndarray}}}
    student_dirs = [
        d
        for d in os.listdir(dataset_dir)
        if os.path.isdir(os.path.join(dataset_dir, d))
    ]
    total_students = max(1, len(student_dirs))
    processed = 0
    X = []
    y = []
    centroids: dict[int, np.ndarray] = {}

    for sid in student_dirs:
        folder = os.path.join(dataset_dir, sid)
        files = [
            f
            for f in os.listdir(folder)
            if f.lower().endswith((".jpg", ".jpeg", ".png")) and f != "profile.jpg"
        ]
        sid_key = str(sid)
        student_cache = cache.get(sid_key, {})
        new_student_cache = {}
        embs = []

        for fn in files:
            path = os.path.join(folder, fn)
            sig = _file_signature(path)
            cached = student_cache.get(fn)
            if cached and cached.get("sig") == sig and cached.get("emb") is not None:
                emb = np.asarray(cached["emb"], dtype=np.float32)
            else:
                img = cv2.imread(path)
                if img is None:
                    continue
                faces = get_face_app((640, 640)).get(img)
                if len(faces) == 0:
                    continue
                faces = sorted(
                    faces,
                    key=lambda f: (f.bbox[2] - f.bbox[0]) * (f.bbox[3] - f.bbox[1]),
                    reverse=True,
                )
                emb = np.asarray(faces[0].normed_embedding, dtype=np.float32)

            new_student_cache[fn] = {"sig": sig, "emb": emb}
            embs.append(emb)
            X.append(emb)
            y.append(int(sid))

        cache[sid_key] = new_student_cache
        if embs:
            stacked = np.stack(embs)
            # Mean then re-normalize → stable class prototype
            mean = stacked.mean(axis=0)
            norm = np.linalg.norm(mean) + 1e-9
            centroids[int(sid)] = (mean / norm).astype(np.float32)

        processed += 1
        if progress_callback:
            pct = int((processed / total_students) * 80)
            progress_callback(
                pct, f"Processed {processed}/{total_students} students (cached when possible)"
            )

    _save_cache(cache)

    if len(X) == 0:
        if progress_callback:
            progress_callback(0, "No training data found")
        return

    X = np.stack(X).astype(np.float32)
    y = np.array(y)

    if progress_callback:
        progress_callback(85, "Building matcher...")

    # Keep a light KNN for backward compatibility / debugging; matching uses centroids+cosine.
    n_neighbors = min(3, len(set(y.tolist())))
    clf = KNeighborsClassifier(n_neighbors=n_neighbors, metric="euclidean")
    clf.fit(X, y)

    bundle = {
        "version": 2,
        "clf": clf,
        "X": X,
        "y": y,
        "centroids": centroids,
        "student_ids": sorted(centroids.keys()),
    }
    with open(MODEL_PATH, "wb") as f:
        pickle.dump(bundle, f)

    if progress_callback:
        progress_callback(
            100,
            f"Training complete — {len(centroids)} students, {len(X)} embeddings",
        )


def check_face_quality(stream_or_bytes, min_face_ratio=0.04):
    """
    Quick per-frame quality check used during guided capture.
    Rejects frames with: no face, multiple faces, or a face too small.
    """
    img = _decode_image(stream_or_bytes)
    if img is None:
        return {"ok": False, "reason": "invalid image"}

    faces = get_face_app((640, 640)).get(img)
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
