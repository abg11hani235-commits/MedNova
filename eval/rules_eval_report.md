# Rafiq Clinical & Nutrition Rules Regression Report

> **Methodology Note & Transparency**:
> These 28 cases in `eval/rules_cases.jsonl` are author-written regression tests designed
> to verify deterministic code execution, not an independent clinical validation.
> Test fixtures, thresholds, and rule parameters were iteratively adjusted during development.
> Results reflect code consistency across author-defined scenarios rather than empirical diagnostic accuracy.

### Regression Cases Summary

| Rule Name | Regression Cases (n) | Passed / Total | Severity Matches | Status |
| :--- | :---: | :---: | :---: | :---: |
| `hba1c_gap` | 5 | 5/5 | 2/2 | Passed |
| `hypoglycemia_scan` | 5 | 5/5 | 3/3 | Passed |
| `meal_log_gap` | 3 | 3/3 | 1/1 | Passed |
| `medication_consideration` | 7 | 7/7 | 4/4 | Passed |
| `renal_panel_gap` | 5 | 5/5 | 3/3 | Passed |
| `weight_bmi_gap` | 3 | 3/3 | 2/2 | Passed |
| **Overall Total** | **28** | **28/28** | **All Evaluated** | **All Passed** |
