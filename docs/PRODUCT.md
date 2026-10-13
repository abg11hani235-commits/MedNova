# Rafiq Product Overview

Rafiq is a SaaS layer on top of a patient file for nutrition specialists in Egypt. Tagline: "Every finding, traced to its source." The specialist opens a patient and gets a one-page brief before the visit; every sentence links to the original place in the file. The demo stays focused on diabetes nutrition follow-up (HbA1c, glucose, creatinine, eGFR, UACR, lipids, weight), with synthetic data only. Rafiq supports the specialist's judgment. It does not diagnose, prescribe, set medication or supplement doses, or tell anyone what to do.

---

# Rafiq project rules (all agents and contributors must follow)

## Product safety (never break these)
1. Rafiq supports specialist judgment only. Never output a diagnosis, a drug dose, or a directive instruction. Use wording like "worth reviewing".
2. Every insight must carry a source: document name, page, and the quoted text. No source means the insight must not be shown.
3. If the answer is not in the patient's files, reply exactly: "المعلومة دي مش موجودة في ملف المريض." Never guess or infer.
4. Numbers (trends, ranges, care gaps) are computed by deterministic code rules, never by the LLM. The LLM only summarizes and answers from retrieved text.
5. Each patient's data is isolated: every query is filtered by patient_id. A question must never retrieve another patient's chunks.
6. Personal identifiers are removed before any text is sent to an LLM.

## Data and security
7. Synthetic data only. Never commit real patient data, real names, or real national IDs.
8. Never commit secrets. Use .env (git-ignored) and .env.example with placeholders.
9. Keep an audit log entry for file opens, uploads, and chat questions.

## UI rules
10. The UI follows /design exactly: tokens, components, spacing, copy. Do not invent new colors or fonts.
11. Severity is always icon + text + color, never color alone.
12. Use CSS logical properties so RTL (Arabic) works. Keep medical terms (HbA1c, eGFR) in Latin characters inside Arabic text.
13. Always keep this footer on every screen: "أداة مساعدة، القرار النهائي للأخصائي. كل البيانات في الـDemo Synthetic."


## Engineering
14. Work on your own branch. Small tasks, small commits. Never push to main.
15. Every feature ships with tests. Run lint and tests before asking for review.
16. Backend: Python 3.11+, FastAPI, Postgres + pgvector, type hints, ruff. Frontend: Next.js, TypeScript, Tailwind, shadcn/ui.
17. Do not edit /design. If the design must change, propose it in /docs/DECISIONS.md.
18. When unsure, ask. Do not make large unrequested changes or add dependencies without saying why.
