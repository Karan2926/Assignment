"""Level 3 — Sentence-level translation."""

from __future__ import annotations

from typing import List, Optional

from deep_translator import GoogleTranslator

# UI-friendly language list (deep-translator Google codes)
SUPPORTED_TARGETS = {
    "English": "en",
    "Hindi": "hi",
    "Spanish": "es",
    "French": "fr",
    "German": "de",
    "Italian": "it",
    "Portuguese": "pt",
    "Russian": "ru",
    "Japanese": "ja",
    "Korean": "ko",
    "Chinese (Simplified)": "zh-CN",
    "Arabic": "ar",
    "Bengali": "bn",
    "Tamil": "ta",
    "Telugu": "te",
    "Marathi": "mr",
    "Gujarati": "gu",
    "Punjabi": "pa",
    "Urdu": "ur",
    "Turkish": "tr",
    "Dutch": "nl",
    "Vietnamese": "vi",
    "Thai": "th",
    "Indonesian": "id",
}


def translate_one(text: str, source: str, target: str) -> str:
    """Translate a single string. source/target are ISO-ish codes (or 'auto')."""
    text = (text or "").strip()
    if not text:
        return ""
    translator = GoogleTranslator(source=source, target=target)
    return translator.translate(text) or ""


def translate_sentences(
    sentences: List[str],
    target_code: str,
    source_code: Optional[str] = None,
) -> dict:
    """
    Translate sentence by sentence (multilevel: unit = sentence).

    source_code=None → auto-detect at translator level.
    """
    source = source_code or "auto"
    rows = []
    outputs = []

    for i, sent in enumerate(sentences, start=1):
        try:
            out = translate_one(sent, source=source, target=target_code)
            err = None
        except Exception as exc:  # noqa: BLE001
            out = ""
            err = str(exc)
        rows.append(
            {
                "index": i,
                "source": sent,
                "translation": out,
                "error": err,
            }
        )
        if out:
            outputs.append(out)

    return {
        "source_code": source,
        "target_code": target_code,
        "rows": rows,
        "translated_text": " ".join(outputs).strip(),
    }
