"""Level 2 — Text preprocessing."""

from __future__ import annotations

import re
from typing import List

_SENT_SPLIT = re.compile(r"(?<=[.!?।؟])\s+")


def _ensure_nltk_punkt() -> None:
    try:
        import nltk
        from nltk.tokenize import sent_tokenize

        # Probe once; download if missing
        try:
            sent_tokenize("Test. Sentence.")
        except LookupError:
            nltk.download("punkt", quiet=True)
            nltk.download("punkt_tab", quiet=True)
    except Exception:
        pass


def clean_text(text: str) -> str:
    """Normalize whitespace and strip noisy characters for translation."""
    text = text.replace("\u00a0", " ")
    text = re.sub(r"[\t\r]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    text = re.sub(r"[ ]{2,}", " ", text)
    return text.strip()


def split_sentences(text: str) -> List[str]:
    """Split into sentences (NLTK if available, else regex fallback)."""
    text = clean_text(text)
    if not text:
        return []

    _ensure_nltk_punkt()
    try:
        from nltk.tokenize import sent_tokenize

        parts = [p.strip() for p in sent_tokenize(text) if p.strip()]
        if parts:
            return parts
    except Exception:
        pass

    parts = [p.strip() for p in _SENT_SPLIT.split(text) if p.strip()]
    return parts or [text]


def preprocess_text(text: str) -> dict:
    """
    Level 2 output for the UI / report.

    Returns cleaned text + sentence list + light stats.
    """
    cleaned = clean_text(text or "")
    sentences = split_sentences(cleaned)
    words = re.findall(r"\w+", cleaned, flags=re.UNICODE)
    return {
        "original": text or "",
        "cleaned": cleaned,
        "sentences": sentences,
        "sentence_count": len(sentences),
        "word_count": len(words),
        "char_count": len(cleaned),
    }
