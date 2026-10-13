import sys
from pathlib import Path

ROOT = Path.cwd()
sys.path.insert(0, str(ROOT / "backend"))
import re

from app.db import get_engine
from app.models import Chunk, File
from app.terms.terms import normalize_arabic
from rank_bm25 import BM25Okapi
from sqlalchemy import select
from sqlalchemy.orm import Session

token_regex = re.compile(
    r"[a-z\u0600-\u06ff]+(?:/[a-z0-9\.\²\³]+)+"
    r"|\d{4}-\d{2}-\d{2}"
    r"|\d+\.\d+"
    r"|[\w²³]+",
    re.IGNORECASE,
)


def new_bm25_tokenize(text: str) -> list[str]:
    norm = normalize_arabic(text).lower()
    return [t.rstrip(".") for t in token_regex.findall(norm) if t.rstrip(".")]


engine = get_engine()
with Session(engine) as session:
    chunks = list(
        session.scalars(
            select(Chunk).where(Chunk.patient_id == "1042").order_by(Chunk.id)
        )
    )
    files = {
        f.id: f for f in session.scalars(select(File).where(File.patient_id == "1042"))
    }

corpus = []
for c in chunks:
    f = files.get(c.file_id)
    kind = f.kind if f else "doc"
    date = f.date if f and f.date else ""
    header = f"{kind} {date} page {c.page}\n"
    corpus.append(new_bm25_tokenize(header + c.text))

bm25 = BM25Okapi(corpus)

for q, gold in [
    (
        "What is the patient's most recent HbA1c value and date?",
        ["1042-Lab_Report_2026-06-18-p1", "1042-Lab_Report_2026-06-18-p2"],
    ),
    (
        "What is the patient's last recorded eGFR and date?",
        ["1042-Lab_Report_2026-06-18-p1"],
    ),
]:
    q_tokens = new_bm25_tokenize(q)
    scores = bm25.get_scores(q_tokens)
    ranked = sorted(zip(chunks, scores), key=lambda x: x[1], reverse=True)[:6]
    retrieved_ids = [c.id for c, _ in ranked]
    print(f"\nQ: {q}")
    print(f"Tokens: {q_tokens}")
    print(f"Retrieved: {retrieved_ids}")
    hit = any(g in retrieved_ids for g in gold)
    print(f"Strict recall hit: {hit}")
