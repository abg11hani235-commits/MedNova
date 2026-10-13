# Evaluation Diagnostic Tools (`eval/tools/`)

This directory contains standalone diagnostic and inspection tools preserved from evaluation investigations:

- `check_not_evaluable.py`: Inspects questions marked not evaluable under evidence coverage and checks token presence in patient records.
- `resume_bge_m3.py`: Verification utility for testing local availability and embedding dimensions of the BGE-M3 model.
- `test_bm25_investigate.py`: Investigates BM25 candidate scoring and rank ordering across clinical documents.
- `test_bm25_scores.py`: Verifies raw BM25 score distributions, term frequencies, and document lengths.
- `test_edge_cases.py`: Checks edge cases in clinical question normalization and value extraction.
- `test_new_bm25_retrieval.py`: Tests the updated BM25 tokenizer with punctuation splitting and unit preservation.
- `test_stratified.py`: Validates deterministic stratified sampling across patient IDs and question types.
- `test_tokenizer_arabic.py`: Tests Arabic clinical tokenization, normalization, and diacritic handling.
- `test_tokenizer_fix.py`: Validates decimal numbers, lab units (e.g. mL/min/1.73m²), and date token retention.
- `test_tokenizer_patterns.py`: Evaluates regular expressions for BM25 term extraction across multilingual records.
- `compare_safety.py`: Compares raw before/after answers and policy compliance for all safety questions.
