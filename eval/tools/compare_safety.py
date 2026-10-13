"""Compare safety answers before and after safety guard implementation."""

import json

target_types = {"policy", "injection", "cross_patient"}


def load_safety_answers(path: str) -> dict:
    answers = {}
    with open(path, encoding="utf-8") as f:
        for line in f:
            if not line.strip():
                continue
            d = json.loads(line)
            if d.get("header"):
                continue
            if d.get("type") in target_types:
                answers[d["question_id"]] = {
                    "type": d["type"],
                    "question": d["question"],
                    "answer": d.get("answer"),
                    "policy_pass": d.get("metrics", {}).get("policy_pass"),
                }
    return answers


before_facts = load_safety_answers("eval/results/archive/20261013_015318_facts.jsonl")
after_facts = load_safety_answers("eval/results/20261013_154742_facts.jsonl")

before_ht = load_safety_answers(
    "eval/results/archive/20261013_015201_hybrid_terms.jsonl"
)
after_ht = load_safety_answers("eval/results/20261013_154647_hybrid_terms.jsonl")

print(f"Total safety questions found: {len(after_facts)}")
print("=== FACTS PIPELINE: BEFORE vs AFTER ===")
for qid in sorted(after_facts.keys()):
    bf = before_facts.get(qid, {})
    af = after_facts[qid]
    print(f"[{af['type']}] {qid}")
    print(f"  Q: {af['question']}")
    print(f"  BEFORE: ans={bf.get('answer')!r} | policy_pass={bf.get('policy_pass')}")
    print(f"  AFTER : ans={af.get('answer')!r} | policy_pass={af.get('policy_pass')}")

print("\n=== HYBRID_TERMS PIPELINE: BEFORE vs AFTER ===")
for qid in sorted(after_ht.keys()):
    bht = before_ht.get(qid, {})
    aht = after_ht[qid]
    print(f"[{aht['type']}] {qid}")
    print(f"  Q: {aht['question']}")
    print(f"  BEFORE: ans={bht.get('answer')!r} | policy_pass={bht.get('policy_pass')}")
    print(f"  AFTER : ans={aht.get('answer')!r} | policy_pass={aht.get('policy_pass')}")
