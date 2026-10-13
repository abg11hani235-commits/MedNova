import sys
from pathlib import Path

ROOT = Path.cwd()
sys.path.insert(0, str(ROOT / "backend"))
from app.rag.pipeline import RAGPipeline, bm25_tokenize

p = RAGPipeline()
q_hba1c = "What is the patient's most recent HbA1c value and date?"
res1 = p.answer("1042", q_hba1c, pipeline_name="bm25", dry_run=True)
print("Q:", q_hba1c)
print("Query tokens:", bm25_tokenize(q_hba1c))
print("Retrieved:", res1["retrieved_chunk_ids"])

q_egfr = "What is the patient's last recorded eGFR and date?"
res2 = p.answer("1042", q_egfr, pipeline_name="bm25", dry_run=True)
print("Q:", q_egfr)
print("Query tokens:", bm25_tokenize(q_egfr))
print("Retrieved:", res2["retrieved_chunk_ids"])
