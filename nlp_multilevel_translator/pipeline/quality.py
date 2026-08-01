"""Level 4 — Quality check via back-translation + similarity."""

from __future__ import annotations

from difflib import SequenceMatcher

try:
    from rapidfuzz import fuzz

    def _ratio(a: str, b: str) -> float:
        return float(fuzz.token_sort_ratio(a, b)) / 100.0

except ImportError:  # pragma: no cover

    def _ratio(a: str, b: str) -> float:
        return SequenceMatcher(None, a.lower(), b.lower()).ratio()


def similarity(a: str, b: str) -> float:
    """Return similarity in [0, 1]."""
    a = (a or "").strip()
    b = (b or "").strip()
    if not a or not b:
        return 0.0
    return _ratio(a, b)


def quality_label(score: float) -> str:
    if score >= 0.75:
        return "Good (heuristic)"
    if score >= 0.50:
        return "Okay (heuristic)"
    return "Weak (heuristic)"


def quality_check(
    original: str,
    translated: str,
    *,
    source_code: str,
    target_code: str,
) -> dict:
    """
    Back-translate target → source and compare with original.

    Classroom heuristic — not a formal MT metric like BLEU.
    """
    from .translate import translate_one

    original = (original or "").strip()
    translated = (translated or "").strip()
    if not original or not translated:
        return {
            "back_translation": "",
            "similarity": 0.0,
            "similarity_pct": 0.0,
            "label": "N/A",
            "note": "Need both original and translated text.",
        }

    back_target = source_code
    if not back_target or back_target in ("unknown", "auto"):
        back_target = "en"

    # Normalize Chinese codes for GoogleTranslator
    if back_target.lower().startswith("zh"):
        back_target = "zh-CN"
    if target_code.lower().startswith("zh"):
        target_code = "zh-CN"

    try:
        back = translate_one(translated, source=target_code, target=back_target)
    except Exception as exc:  # noqa: BLE001
        return {
            "back_translation": "",
            "similarity": 0.0,
            "similarity_pct": 0.0,
            "label": "Error",
            "note": str(exc),
        }

    score = similarity(original, back)
    return {
        "back_translation": back,
        "similarity": round(score, 4),
        "similarity_pct": round(score * 100, 1),
        "label": quality_label(score),
        "note": (
            "Back-translation similarity is a rough classroom check. "
            "Real evaluation uses BLEU/chrF on parallel corpora."
        ),
    }
