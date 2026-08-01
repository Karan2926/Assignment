"""
Multilevel Language Translator — Streamlit app (NLP class project)

Pipeline:
  Level 1 Language detection
  Level 2 Preprocessing
  Level 3 Sentence translation
  Level 4 Back-translation quality check
"""

from __future__ import annotations

import streamlit as st

from pipeline.detect import detect_language
from pipeline.preprocess import preprocess_text
from pipeline.translate import SUPPORTED_TARGETS, translate_sentences
from pipeline.quality import quality_check

st.set_page_config(
    page_title="Multilevel Language Translator",
    page_icon="🌐",
    layout="wide",
)

st.title("Multilevel Language Translator")
st.caption(
    "NLP class project — translation as a **4-level pipeline**, not a single black box."
)

with st.sidebar:
    st.header("Settings")
    target_name = st.selectbox("Target language", list(SUPPORTED_TARGETS.keys()), index=1)
    target_code = SUPPORTED_TARGETS[target_name]
    run_quality = st.checkbox("Run Level 4 quality check", value=True)
    st.markdown("---")
    st.markdown(
        """
**Levels**
1. Detect language  
2. Preprocess / split sentences  
3. Translate each sentence  
4. Back-translate + similarity  
"""
    )

text = st.text_area(
    "Enter text to translate",
    height=160,
    placeholder="Type or paste text in any supported language…",
)

col_run, col_clear = st.columns([1, 1])
run = col_run.button("Run multilevel translation", type="primary")
if col_clear.button("Clear"):
    st.rerun()

if run:
    if not text.strip():
        st.warning("Please enter some text.")
        st.stop()

    # -------- Level 1 --------
    st.subheader("Level 1 — Language detection")
    detection = detect_language(text)
    if detection.get("error"):
        st.error(f"Detection issue: {detection['error']}")
    c1, c2, c3 = st.columns(3)
    c1.metric("Detected", detection.get("name", "Unknown"))
    c2.metric("Code", detection.get("code", "—"))
    c3.metric("Confidence", f"{detection.get('confidence', 0) * 100:.1f}%")
    if detection.get("candidates"):
        st.write("Top candidates:")
        st.dataframe(detection["candidates"], use_container_width=True, hide_index=True)

    # -------- Level 2 --------
    st.subheader("Level 2 — Preprocessing")
    prep = preprocess_text(text)
    p1, p2, p3 = st.columns(3)
    p1.metric("Sentences", prep["sentence_count"])
    p2.metric("Words", prep["word_count"])
    p3.metric("Characters", prep["char_count"])
    st.text_area("Cleaned text", prep["cleaned"], height=100)
    st.write("Sentence units:")
    for i, s in enumerate(prep["sentences"], start=1):
        st.markdown(f"**{i}.** {s}")

    # -------- Level 3 --------
    st.subheader(f"Level 3 — Translation → {target_name}")
    source_code = detection.get("code")
    if source_code in (None, "unknown"):
        source_code = "auto"
    # deep-translator uses zh-CN; langdetect may return zh-cn
    if isinstance(source_code, str) and source_code.lower().startswith("zh"):
        source_code = "zh-CN"

    with st.spinner("Translating sentence by sentence…"):
        result = translate_sentences(
            prep["sentences"],
            target_code=target_code,
            source_code=source_code,
        )

    st.success("Translation complete")
    st.text_area("Translated text", result["translated_text"], height=140)
    st.write("Sentence-level log (good for report screenshots):")
    st.dataframe(result["rows"], use_container_width=True, hide_index=True)

    # -------- Level 4 --------
    if run_quality and result["translated_text"]:
        st.subheader("Level 4 — Quality check (back-translation)")
        with st.spinner("Back-translating for similarity check…"):
            q = quality_check(
                prep["cleaned"],
                result["translated_text"],
                source_code=source_code if source_code != "auto" else detection.get("code", "en"),
                target_code=target_code,
            )
        q1, q2 = st.columns(2)
        q1.metric("Similarity", f"{q.get('similarity_pct', 0)}%")
        q2.metric("Label", q.get("label", "—"))
        st.text_area("Back-translation", q.get("back_translation", ""), height=120)
        st.info(q.get("note", ""))

    st.markdown("---")
    st.markdown(
        "**How to explain this in viva:** "
        "Level 1 finds the source language; Level 2 prepares clean sentence units; "
        "Level 3 translates each unit; Level 4 roughly checks meaning preservation "
        "via back-translation. Production MT uses stronger models and formal metrics (BLEU/chrF)."
    )
