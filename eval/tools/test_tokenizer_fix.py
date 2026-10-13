import re

from app.terms.terms import normalize_arabic

TOKEN_PATTERN = re.compile(
    r"[a-z\u0600-\u06ff]+(?:/[a-z0-9\.\²\³]+)+"  # compound clinical units with slash: ml/min/1.73m², mg/dl
    r"|\d{4}-\d{2}-\d{2}"  # dates: 2026-06-18
    r"|\d+(?:\.\d+)+"  # decimals: 8.9, 1.73
    r"|[\w²³]+",  # words and integers: hba1c, 59, glycated, arabic words
    re.IGNORECASE,
)


def bm25_tokenize(text: str) -> list[str]:
    """Tokenize text splitting on punctuation and brackets while preserving decimals, units, and Arabic."""
    norm = normalize_arabic(text).lower()
    raw_tokens = TOKEN_PATTERN.findall(norm)
    # Strip any trailing period or punctuation from units
    tokens = []
    for t in raw_tokens:
        clean = t.rstrip(".,:;!?%()[]{}")
        if clean:
            tokens.append(clean)
    return tokens


s1 = "Glycated Hemoglobin (HbA1c): 8.9%"
s2 = "Estimated GFR today is 59 mL/min/1.73m²."
s3 = "فحص السكر التراكمي (HbA1c): 8.9% بتاريخ 2026-06-18"
s4 = "Labs reviewed: eGFR 59 mL/min/1.73m²."

print("s1 tokens:", bm25_tokenize(s1))
print("s2 tokens:", bm25_tokenize(s2))
print("s3 tokens:", bm25_tokenize(s3))
print("s4 tokens:", bm25_tokenize(s4))
