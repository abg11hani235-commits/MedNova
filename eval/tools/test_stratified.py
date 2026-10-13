import json
import random


def stratified_sample(questions, n, seed=42):
    if n >= len(questions):
        return questions
    rng = random.Random(seed)
    by_type = {}
    for q in questions:
        by_type.setdefault(q["type"], []).append(q)
    for t, q_list in by_type.items():
        q_list.sort(key=lambda x: (x["patient_id"], x["id"]))
        rng.shuffle(q_list)
    types = sorted(by_type.keys())
    selected = []
    patient_counts = {}
    if n >= len(types):
        for t in types:
            candidates = by_type[t]
            best_idx = 0
            best_p_count = float("inf")
            for idx, cand in enumerate(candidates):
                p_cnt = patient_counts.get(cand["patient_id"], 0)
                if p_cnt < best_p_count:
                    best_p_count = p_cnt
                    best_idx = idx
            chosen = candidates.pop(best_idx)
            selected.append(chosen)
            patient_counts[chosen["patient_id"]] = (
                patient_counts.get(chosen["patient_id"], 0) + 1
            )
    type_idx = 0
    while len(selected) < n:
        t = types[type_idx % len(types)]
        candidates = by_type[t]
        if candidates:
            best_idx = 0
            best_p_count = float("inf")
            for idx, cand in enumerate(candidates):
                p_cnt = patient_counts.get(cand["patient_id"], 0)
                if p_cnt < best_p_count:
                    best_p_count = p_cnt
                    best_idx = idx
            chosen = candidates.pop(best_idx)
            selected.append(chosen)
            patient_counts[chosen["patient_id"]] = (
                patient_counts.get(chosen["patient_id"], 0) + 1
            )
        type_idx += 1
        if all(len(c) == 0 for c in by_type.values()):
            break
    selected.sort(key=lambda x: (x["patient_id"], x["type"], x["id"]))
    return selected


questions = []
with open("eval/questions.jsonl", encoding="utf-8") as f:
    for line in f:
        if line.strip():
            questions.append(json.loads(line))

sample20 = stratified_sample(questions, 20, seed=42)
print("Total sampled:", len(sample20))
types_sampled = sorted({q["type"] for q in sample20})
patients_sampled = sorted({q["patient_id"] for q in sample20})
print("Types sampled count:", len(types_sampled), types_sampled)
print("Patients sampled count:", len(patients_sampled), patients_sampled)
print("\nSampled items:")
for q in sample20:
    print(
        f"  [{q['id']}] patient={q['patient_id']} type={q['type']}: {q['question'][:50]}..."
    )
