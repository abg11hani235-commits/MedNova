import re

from app.terms.terms import normalize_arabic


def test_pattern(pat, text):
    norm = normalize_arabic(text).lower()
    return re.findall(pat, norm)


s1 = "Glycated Hemoglobin (HbA1c): 8.9%"
s2 = "Estimated GFR today is 59 mL/min/1.73m²."
s3 = "فحص السكر التراكمي (HbA1c): 8.9% بتاريخ 2026-06-18"
s4 = "Blood pressure: 120/80 mmHg, Fasting Glucose: 110 mg/dL."

# Pattern idea:
# Match units first, then decimals, then dates/words
# A token can be:
# 1. compound unit with slash: [a-z\u0600-\u06ff]+(?:/[a-z0-9\.\²\³]+)+
# 2. date: \d{4}-\d{2}-\d{2}
# 3. decimal number: \d+\.\d+
# 4. word/number: [\w²³]+
token_regex = re.compile(
    r"[a-z\u0600-\u06ff]+(?:/[a-z0-9\.\²\³]+)+"  # units like ml/min/1.73m², mg/dl
    r"|\d{4}-\d{2}-\d{2}"  # dates like 2026-06-18
    r"|\d+\.\d+"  # decimals like 8.9
    r"|[\w²³]+",  # words and numbers
    re.IGNORECASE,
)

for s in [s1, s2, s3, s4]:
    norm = normalize_arabic(s).lower()
    tokens = token_regex.findall(norm)
    # clean any trailing dots just in case
    clean_tokens = [t.rstrip(".") for t in tokens if t.rstrip(".")]
    print(f"Input: {s}")
    print(f"Tokens: {clean_tokens}\n")
