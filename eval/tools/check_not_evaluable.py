import json
import sys
from pathlib import Path

ROOT = Path.cwd()
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "backend"))
from app.db import get_engine
from app.models import Chunk
from sqlalchemy import select
from sqlalchemy.orm import Session

from eval.normalize import matches_all_expected_values

engine = get_engine()
with Session(engine) as session:
    all_chunks = list(session.scalars(select(Chunk)))

chunks_by_patient = {}
for c in all_chunks:
    chunks_by_patient.setdefault(c.patient_id, []).append(c)

questions = []
with open("eval/questions.jsonl", encoding="utf-8") as f:
    for line in f:
        if line.strip():
            questions.append(json.loads(line))

not_evaluable = []
answerable_with_chunks = []

for q in questions:
    if q.get("expected_behavior") != "answer" or not q.get("expected_values"):
        continue
    pid = q["patient_id"]
    p_chunks = chunks_by_patient.get(pid, [])
    bearing = [
        c.id
        for c in p_chunks
        if matches_all_expected_values(q["expected_values"], c.text)
    ]
    if not bearing:
        not_evaluable.append((q["id"], q["type"], q["question"], q["expected_values"]))
    else:
        answerable_with_chunks.append((q["id"], len(bearing)))

print(
    f"Total answer questions checked: {len(answerable_with_chunks) + len(not_evaluable)}"
)
print(f"Questions WITH answer-bearing chunks: {len(answerable_with_chunks)}")
print(f"Questions with NO answer-bearing chunk ('not evaluable'): {len(not_evaluable)}")
print("\nList of 'not evaluable' questions:")
for qid, qtype, qtext, exp in not_evaluable:
    print(f"  [{qid}] ({qtype}) expected={exp}: {qtext}")
