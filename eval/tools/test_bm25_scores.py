import sys
from pathlib import Path

ROOT = Path.cwd()
sys.path.insert(0, str(ROOT / "backend"))
from app.db import get_engine
from app.models import Chunk, File
from app.rag.pipeline import bm25_tokenize
from rank_bm25 import BM25Okapi
from sqlalchemy import select
from sqlalchemy.orm import Session

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

print("Total chunks for 1042:", len(chunks))

# Check Lab_Report_2026-06-18-p1
lab_chunk = next(c for c in chunks if "Lab_Report_2026-06-18-p1" in c.id)
print("\n--- Lab_Report_2026-06-18-p1 text preview ---")
print(lab_chunk.text[:300])
print("\nTokens in lab chunk containing 'hba1c' or '8.9' or 'egfr' or '59':")
lab_tokens = bm25_tokenize(lab_chunk.text)
print(
    [t for t in lab_tokens if any(k in t for k in ["hba", "8.9", "egfr", "59", "gfr"])]
)

# Build BM25 and inspect per-token scores
corpus = []
for c in chunks:
    f = files.get(c.file_id)
    kind = f.kind if f else "doc"
    date = f.date if f and f.date else ""
    header = f"{kind} {date} page {c.page}\n"
    corpus.append(bm25_tokenize(header + c.text))

bm25 = BM25Okapi(corpus)
q = "What is the patient's most recent HbA1c value and date?"
q_tokens = bm25_tokenize(q)
scores = bm25.get_scores(q_tokens)

print("\n--- BM25 Scores for Q: HbA1c ---")
ranked = sorted(zip(chunks, scores), key=lambda x: x[1], reverse=True)
for c, sc in ranked[:8]:
    print(f"{c.id}: score={sc:.3f}, len={len(corpus[chunks.index(c)])}")

lab_idx = chunks.index(lab_chunk)
print(
    f"Target Lab chunk: rank={[c.id for c, _ in ranked].index(lab_chunk.id) + 1}, score={scores[lab_idx]:.3f}"
)

# Check IDF of query tokens
print("\nIDF of query tokens:")
for qt in q_tokens:
    idf = bm25.idf.get(qt, 0.0)
    print(f"  '{qt}': idf={idf:.3f}")
