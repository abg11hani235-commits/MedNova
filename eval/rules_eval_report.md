# Rafiq Clinical & Nutrition Rules Engine Evaluation Report

Deterministic evaluation of rules in `backend/app/nutrition_rules.py` against `eval/rules_cases.jsonl`.

| Rule Name | Count (n) | Precision | Recall | Accuracy | Severity Matches |
| :--- | :---: | :---: | :---: | :---: | :---: |
| `hba1c_gap` | 5 | 100.0% | 100.0% | 100.0% | 2/2 |
| `hypoglycemia_scan` | 5 | 100.0% | 100.0% | 100.0% | 3/3 |
| `meal_log_gap` | 3 | 100.0% | 100.0% | 100.0% | 1/1 |
| `medication_consideration` | 7 | 100.0% | 100.0% | 100.0% | 4/4 |
| `renal_panel_gap` | 5 | 100.0% | 100.0% | 100.0% | 3/3 |
| `weight_bmi_gap` | 3 | 100.0% | 100.0% | 100.0% | 2/2 |
| **Overall Total** | **28** | **100.0%** | **100.0%** | **100.0%** | **All Passed** |
