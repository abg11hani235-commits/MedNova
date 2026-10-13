from test_tokenizer_fix import bm25_tokenize

print("Lab line:", bm25_tokenize("Fasting Blood Glucose: 192 mg/dL (Reference: 70-99)"))
print("BP:", bm25_tokenize("Blood Pressure: 120/80 mmHg"))
print("Range:", bm25_tokenize("HbA1c range 4.0 - 5.6%"))
