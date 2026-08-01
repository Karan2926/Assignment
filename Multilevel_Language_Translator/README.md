# Multilevel Language Translator (NLP Class Project)

A **multilevel** translation system: text passes through clear NLP stages instead of a single black-box “translate” button.

## What “multilevel” means here

| Level | Stage | NLP role |
|-------|--------|----------|
| **1** | Language detection | Identify source language |
| **2** | Preprocessing | Clean text, normalize, split sentences |
| **3** | Translation | Translate each sentence to the target language |
| **4** | Quality check | Back-translate + similarity score (rough quality signal) |

This is useful for a class demo because you can **show each stage** and explain why pipelines matter in real NLP systems.

## Tech stack

- **UI:** Streamlit
- **Detection:** `langdetect`
- **Preprocessing:** regex + sentence splitting (`nltk` punkt)
- **Translation:** `deep-translator` (Google Translate backend; no GPU required)
- **Similarity (Level 4):** SequenceMatcher / optional rapidfuzz

## Run locally

```bash
cd nlp_multilevel_translator
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python -m nltk.downloader punkt punkt_tab
streamlit run app.py
```

Open the local URL Streamlit prints (usually http://localhost:8501).

## Demo script for viva

1. Paste English text → choose Hindi (or another target).
2. Show **Level 1**: detected language.
3. Show **Level 2**: cleaned sentences.
4. Show **Level 3**: translated output.
5. Show **Level 4**: back-translation + similarity %.
6. Explain: similarity is only a heuristic, not a perfect BLEU score.

## Project layout

```
nlp_multilevel_translator/
  app.py                 # Streamlit UI
  pipeline/
    detect.py            # Level 1
    preprocess.py        # Level 2
    translate.py         # Level 3
    quality.py           # Level 4
  requirements.txt
  README.md
```

## Future upgrades (optional)

- Add Hugging Face NLLB / MarianMT for offline neural MT
- Add BLEU / chrF evaluation on a small parallel corpus
- Add glossary / domain terms (medical, legal)
- Export pipeline log as JSON for report screenshots
