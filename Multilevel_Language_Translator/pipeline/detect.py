"""Level 1 — Language detection."""

from __future__ import annotations

from langdetect import DetectorFactory, detect, detect_langs

# Make detection deterministic for demos/reports
DetectorFactory.seed = 0

# ISO 639-1 → display name (common class demo languages)
LANG_NAMES = {
    "en": "English",
    "hi": "Hindi",
    "es": "Spanish",
    "fr": "French",
    "de": "German",
    "it": "Italian",
    "pt": "Portuguese",
    "ru": "Russian",
    "ja": "Japanese",
    "ko": "Korean",
    "zh-cn": "Chinese (Simplified)",
    "zh-tw": "Chinese (Traditional)",
    "ar": "Arabic",
    "bn": "Bengali",
    "ta": "Tamil",
    "te": "Telugu",
    "mr": "Marathi",
    "gu": "Gujarati",
    "pa": "Punjabi",
    "ur": "Urdu",
    "tr": "Turkish",
    "nl": "Dutch",
    "pl": "Polish",
    "uk": "Ukrainian",
    "vi": "Vietnamese",
    "th": "Thai",
    "id": "Indonesian",
}


def code_to_name(code: str) -> str:
    return LANG_NAMES.get(code, code)


def detect_language(text: str) -> dict:
    """
    Detect source language.

    Returns:
        {
          "code": "en",
          "name": "English",
          "confidence": 0.99,
          "candidates": [{"code": "...", "prob": 0.9}, ...]
        }
    """
    text = (text or "").strip()
    if not text:
        return {
            "code": "unknown",
            "name": "Unknown",
            "confidence": 0.0,
            "candidates": [],
            "error": "Empty text",
        }

    try:
        code = detect(text)
        langs = detect_langs(text)
        candidates = [
            {"code": str(x.lang), "name": code_to_name(str(x.lang)), "prob": float(x.prob)}
            for x in langs[:5]
        ]
        confidence = float(langs[0].prob) if langs else 0.0
        return {
            "code": code,
            "name": code_to_name(code),
            "confidence": confidence,
            "candidates": candidates,
        }
    except Exception as exc:  # noqa: BLE001 — surface to UI for demo clarity
        return {
            "code": "unknown",
            "name": "Unknown",
            "confidence": 0.0,
            "candidates": [],
            "error": str(exc),
        }
