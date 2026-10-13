import re
import sys

sys.stdout.reconfigure(encoding="utf-8")
from app.terms.terms import normalize_arabic

token_regex = re.compile(
    r"[a-z\u0600-\u06ff]+(?:/[a-z0-9\.\²\³]+)+"  # units like ml/min/1.73m², mg/dl
    r"|\d{4}-\d{2}-\d{2}"  # dates like 2026-06-18
    r"|\d+\.\d+"  # decimals like 8.9
    r"|[\w²³]+",  # words and numbers
    re.IGNORECASE,
)

s3 = "فحص السكر التراكمي (HbA1c): 8.9% بتاريخ 2026-06-18"
norm = normalize_arabic(s3).lower()
tokens = [t.rstrip(".") for t in token_regex.findall(norm) if t.rstrip(".")]
print(f"Arabic input: {s3}")
print(f"Tokens: {tokens}")
