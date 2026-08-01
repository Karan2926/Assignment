# Multilevel Language Translator
## NLP Class Project Report

**Student:** Karan Bhadouriya  
**Subject:** Natural Language Processing  
**Project Title:** Multilevel Language Translator  

---

### 1. Objective
The objective of this project is to design and implement a **multilevel machine translation system** that performs language translation through a clear NLP pipeline instead of a single black-box step.

The system demonstrates four stages:
1. Language detection  
2. Text preprocessing  
3. Sentence-level translation  
4. Quality estimation using back-translation  

This helps in understanding how real-world NLP translation systems are structured.

---

### 2. Introduction / Problem Statement
Most online translators hide internal processing. Users only see input text and output translation. For NLP learning, it is important to understand intermediate stages such as language identification, preprocessing, translation, and evaluation.

This project solves that learning gap by making each NLP level visible and explainable.

---

### 3. Literature / Background Concepts
- **Language Identification:** detecting the language of input text before translation.  
- **Text Preprocessing:** cleaning and splitting text into sentence units.  
- **Machine Translation (MT):** converting text from source language to target language.  
- **Back-translation:** translating output back to source language to check meaning preservation.  
- **Evaluation Metrics:** research systems use BLEU/chrF; this project uses similarity as a classroom heuristic.

---

### 4. Methodology (Multilevel Pipeline)

**Level 1 — Language Detection**  
Detect source language and confidence score.

**Level 2 — Preprocessing**  
Normalize text and split into sentences.

**Level 3 — Translation**  
Translate each sentence into the selected target language.

**Level 4 — Quality Check**  
Back-translate the output and compare with original text using similarity score.

```text
Input Text
   ↓
Language Detection
   ↓
Preprocessing / Sentence Splitting
   ↓
Sentence Translation
   ↓
Back-translation + Similarity
   ↓
Final Output + Quality Label
```

---

### 5. Implementation
**Tech Stack**
- Python  
- Streamlit (UI)  
- langdetect (language detection)  
- NLTK / regex (sentence preprocessing)  
- deep-translator (translation backend)  
- rapidfuzz / SequenceMatcher (similarity)

**Modules**
- `pipeline/detect.py` — Level 1  
- `pipeline/preprocess.py` — Level 2  
- `pipeline/translate.py` — Level 3  
- `pipeline/quality.py` — Level 4  
- `app.py` — Streamlit interface  

**Supported demos:** English, Hindi, Tamil, French, Spanish, and other common languages.

---

### 6. Results
Sample input:  
`My name is Karan. I am building a multilevel language translator for my NLP class.`

Observed behavior:
- Level 1 correctly detects English.  
- Level 2 splits text into sentence units.  
- Level 3 produces target-language translation (e.g., Hindi).  
- Level 4 shows back-translation and similarity percentage.

The interface successfully displays each pipeline stage, making the translation process explainable for academic demonstration.

---

### 7. Advantages
- Clear multilevel NLP architecture  
- Easy to demonstrate in viva  
- Modular code (each level is separate)  
- Works for multiple language pairs  
- Includes basic quality checking  

---

### 8. Limitations
- Translation quality depends on the MT backend  
- Short text may reduce language-detection confidence  
- Similarity score is only a heuristic, not full BLEU evaluation  
- Requires internet for the current translation backend  

---

### 9. Future Scope
- Add offline neural models (MarianMT / NLLB)  
- Add formal BLEU / chrF evaluation on parallel corpus  
- Add domain glossary (medical/legal/education terms)  
- Add speech-to-text and text-to-speech  
- Deploy as a web service for college use  

---

### 10. Conclusion
This project successfully implements a **Multilevel Language Translator** using a four-stage NLP pipeline: detection, preprocessing, translation, and quality checking. It demonstrates practical understanding of NLP system design beyond a simple translation API call, and provides an interactive academic demo using Streamlit.

---

### 11. Viva Summary (memorize)
"My project is a Multilevel Language Translator. It translates text through four NLP levels: language detection, preprocessing, sentence translation, and back-translation quality check. I built it in Python with Streamlit so each stage is visible and explainable."
