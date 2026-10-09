# ClinSight Synthetic Patient Dataset

This directory contains the reproducible synthetic patient dataset and ground-truth validation suite for ClinSight decision support evaluation.

## Clinical Safety & Ground Rules (per `AGENTS.md`)
- **Decision Support Only:** Never outputs a diagnosis or drug dosage. Findings use neutral clinical phrasing like *"worth reviewing"*.
- **Strict Grounding:** Every insight carries exact source attribution (`source_file`, `page`, and quoted text).
- **Refusal Guarantee:** If a query cannot be answered from patient files, ClinSight replies with the canonical refusal text:
  ```text
  "I couldn't find this in the patient's files."
  ```
- **Fictional Egyptian Identifiers:** All personal data is strictly synthetic. National IDs are 14 digits starting with `9` (impossible for real Egyptian IDs). Phone numbers use fictional Egyptian mobile patterns (`010 0000 1042`, etc.), with fictional names and addresses in Cairo, Giza, and Alexandria.
- **Reference Date (`as_of_date`):** Set fixed to `2026-06-18` across all ground-truth files and validation logic. Never uses runtime system clock.

---

## Dataset Summary

| Patient ID | Name | Age / Sex | Diabetes Type | Total Files | Readable Files | Scanned Images | Arabic Notes | Planted Findings | Refusal Questions |
| :---: | :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| **#1042** | Farouk Adel Mansour | 62M | Type 2 | 17 | 14 | 3 | 2 | 5 | 4 |
| **#1043** | Salma Tarek Mostafa | 41F | Type 1 | 16 | 14 | 2 | 2 | 5 | 4 |
| **#1044** | Mahmoud Hassan Ibrahim | 68M | Type 2 | 16 | 14 | 2 | 2 | 5 | 4 |
| **#1045** | Layla Karim El-Sayed | 54F | Type 2 | 16 | 14 | 2 | 2 | 5 | 4 |
| **#1046** | Ahmed Mohamed Radwan | 72M | Type 2 | 17 | 15 | 2 | 2 | 5 | 4 |
| **#1047** | Mona Hany Youssef | 58F | Type 2 | 16 | 14 | 2 | 2 | 5 | 4 |
| **#1048** | Omar Khaled Zaki | 39M | Type 1 | 16 | 14 | 2 | 2 | 5 | 4 |
| **#1049** | Nadia Sherif Fathy | 65F | Type 2 | 16 | 14 | 2 | 2 | 5 | 4 |
| **#1050** | Samir Wahba Ghattas | 70M | Type 2 | 17 | 15 | 2 | 2 | 5 | 4 |
| **#1051** | Zeinab Essam El-Din | 49F | Type 2 | 16 | 14 | 2 | 2 | 5 | 4 |

---

## File Structure & Git Storage (Option A)

To keep git history lean while supporting immediate frontend demo inspection:
- **Patient #1042 (Demo Set):** All 17 PDFs are committed to git to back `Main.html` and `Evidence.html` preview fixtures.
- **Patients #1043–#1051:** PDFs are excluded via `.gitignore` (`data/synthetic/**/*.pdf`, with negation `!data/synthetic/1042/*.pdf`).
- **All Patients (#1042–#1051):** Plain-text companions (`.txt`) and ground-truth evaluations (`data/ground_truth/*.json`) are committed to git.
- **Bundled Fonts:** Bundled open font `data/fonts/IBMPlexSansArabic-Regular.ttf` (SIL Open Font License) guarantees reproducible rendering on any operating system or CI pipeline without system font dependencies.

```
data/
├── README.md
├── requirements.txt
├── constants.py
├── generate_synthetic.py
├── validate_dataset.py
├── fonts/
│   └── IBMPlexSansArabic-Regular.ttf
├── ground_truth/
│   ├── 1042.json
│   └── ... (1043.json - 1051.json)
├── synthetic/
│   ├── 1042/            # 17 PDFs + 17 TXT files
│   └── 1043-1051/       # 16-17 TXT files each (PDFs regenerable on demand)
└── tests/
    └── test_validate_dataset.py
```

---

## Setup & Dependencies

Install generation and validation dependencies in your Python environment:
```bash
pip install -r data/requirements.txt
```

*(Note: Data generation dependencies are intentionally separate from `backend/pyproject.toml` to keep the production runtime lean.)*

---

## Generating the Dataset

To regenerate all synthetic charts and ground-truth evaluations deterministically:
```bash
python -m data.generate_synthetic
```
The generator uses fixed RNG seeds (`seed=42`), ReportLab's `invariant=True`, fixed PDF metadata timestamps (`FIXED_PDF_TIMESTAMP`), and deterministic baseline JPEG compression settings to guarantee byte-identical outputs (including `.txt` companion files, scanned PDFs, and ground-truth JSON files) on every run.


---

## Running Dataset Validation & Tests

To validate all 10 patient charts against the ground-truth specification:
```bash
python -m data.validate_dataset
```

To run the automated pytest test suite:
```bash
pytest data/tests
```

### Validation Checks Performed:
1. **Schema & Reference Date:** Verifies `as_of_date == "2026-06-18"` and patient profile consistency.
2. **Deterministic Manifest Parity:** Verifies file count, file names, page counts, and scan flags match `files_summary`.
3. **Planted Findings Integrity:**
   - Verifies exactly 5 planted findings per patient.
   - Verifies quotes are situated exclusively in English files (Arabic notes do not host ground-truth quotes).
   - Verifies each quote appears **exactly once** on its designated page.
4. **Care Gap Absence Checks:**
   - If UACR gap is flagged, verifies no UACR/microalbumin mention exists within 12 months prior to `as_of_date`.
   - If retinal exam is flagged overdue, verifies no eye report exists within 12 months prior to `as_of_date`.
5. **Deterministic Trends:** Verifies each trend point (HbA1c, eGFR) matches deterministic values in the corresponding lab or clinic note.
6. **Chat Evaluation Refusal:**
   - Verifies $\ge 4$ unanswerable questions per patient.
   - Verifies canonical refusal text matches exactly: `"I couldn't find this in the patient's files."`
   - Verifies unanswerable questions have `source_file: null` and `page: null`.
7. **Type 1 Diabetes Medication Guard:**
   - Verifies Type 1 patients (#1043, #1048) receive insulin therapy and never Metformin or Gliclazide.
8. **PDF Layer Check:**
   - Scanned PDFs have 0 text layer.
   - Readable PDFs yield extracted text.
