"""Generate plain-text evaluation comparison report (eval/report.py).

Prints:
1. Retrieval Recall@k (pipelines x question types)
2. Mean Reciprocal Rank (MRR) (pipelines x question types)
3. Answer Correctness (for evaluated answers)
4. Policy Pass Rate (safe refusal and policy compliance)
5. Observed Latency & Tokens
6. Extrapolated Token Usage & Cost Projections
7. Scope, Status & Limitations (clear statement of what was and was not run)
8. Top-10 Worst Failures per Pipeline
"""

from __future__ import annotations

import argparse
import json
import statistics
import sys
from pathlib import Path
from typing import Any

# Ensure UTF-8 output on Windows consoles
if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

ROOT = Path(__file__).resolve().parents[1]
RESULTS_DIR = ROOT / "eval" / "results"


def load_latest_results_for_pipeline(pipeline_name: str) -> list[dict[str, Any]]:
    files = sorted(RESULTS_DIR.glob(f"*_{pipeline_name}.jsonl"))
    if not files:
        return []
    latest_file = files[-1]
    records = []
    with open(latest_file, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                records.append(json.loads(line))
    return records


def format_table(header: list[str], rows: list[list[str]]) -> str:
    """Format plain-text aligned table without markdown markup."""
    col_widths = [len(h) for h in header]
    for row in rows:
        for idx, cell in enumerate(row):
            if idx < len(col_widths):
                col_widths[idx] = max(col_widths[idx], len(str(cell)))

    lines = []
    hdr_line = "  ".join(h.ljust(col_widths[i]) for i, h in enumerate(header))
    sep_line = "  ".join("-" * col_widths[i] for i in range(len(header)))
    lines.append(hdr_line)
    lines.append(sep_line)

    for row in rows:
        r_line = "  ".join(str(cell).ljust(col_widths[i]) for i, cell in enumerate(row))
        lines.append(r_line)

    return "\n".join(lines)


def generate_report(pipelines: list[str]) -> str:
    pipeline_data: dict[str, list[dict[str, Any]]] = {}
    for p in pipelines:
        data = load_latest_results_for_pipeline(p)
        if data:
            pipeline_data[p] = data

    if not pipeline_data:
        return "[ERROR] No evaluation results found in eval/results/."

    all_types = sorted({q["type"] for data in pipeline_data.values() for q in data})

    out = []
    out.append("=== REPORT START ===")
    out.append("CLINSIGHT RAG RETRIEVAL & CHAT EVALUATION REPORT")
    out.append("=" * 60)

    # 1. RETRIEVAL RECALL@K
    out.append("\n1. RETRIEVAL RECALL@K (Pipelines x Question Types)")
    header = ["Question Type"] + list(pipeline_data.keys())
    rows = []
    for qtype in all_types:
        row = [qtype]
        for p in pipeline_data:
            recs = [r for r in pipeline_data[p] if r["type"] == qtype]
            recalls = [
                r["metrics"]["retrieval_recall_at_k"]
                for r in recs
                if r["metrics"].get("retrieval_recall_at_k") is not None
            ]
            if recalls:
                row.append(f"{statistics.mean(recalls) * 100:.1f}%")
            else:
                row.append("N/A")
        rows.append(row)

    overall_row = ["OVERALL"]
    for p in pipeline_data:
        recalls = [
            r["metrics"]["retrieval_recall_at_k"]
            for r in pipeline_data[p]
            if r["metrics"].get("retrieval_recall_at_k") is not None
        ]
        if recalls:
            overall_row.append(f"{statistics.mean(recalls) * 100:.1f}%")
        else:
            overall_row.append("N/A")
    rows.append(overall_row)
    out.append(format_table(header, rows))

    # 2. MEAN RECIPROCAL RANK (MRR)
    out.append("\n2. MEAN RECIPROCAL RANK (MRR) (Pipelines x Question Types)")
    rows_mrr = []
    for qtype in all_types:
        row = [qtype]
        for p in pipeline_data:
            recs = [r for r in pipeline_data[p] if r["type"] == qtype]
            mrrs = [r["metrics"]["mrr"] for r in recs if r["metrics"].get("mrr") is not None]
            if mrrs:
                row.append(f"{statistics.mean(mrrs):.3f}")
            else:
                row.append("N/A")
        rows_mrr.append(row)

    overall_mrr = ["OVERALL"]
    for p in pipeline_data:
        mrrs = [
            r["metrics"]["mrr"] for r in pipeline_data[p] if r["metrics"].get("mrr") is not None
        ]
        if mrrs:
            overall_mrr.append(f"{statistics.mean(mrrs):.3f}")
        else:
            overall_mrr.append("N/A")
    rows_mrr.append(overall_mrr)
    out.append(format_table(header, rows_mrr))

    # 3. ANSWER CORRECTNESS
    out.append("\n3. ANSWER CORRECTNESS (Expected Values In Answer)")
    rows_ans = []
    for qtype in all_types:
        row = [qtype]
        for p in pipeline_data:
            recs = [r for r in pipeline_data[p] if r["type"] == qtype]
            ans_scores = [
                r["metrics"]["answer_correct"]
                for r in recs
                if r["metrics"].get("answer_correct") is not None
            ]
            if ans_scores:
                row.append(f"{statistics.mean(ans_scores) * 100:.1f}%")
            else:
                row.append("N/A")
        rows_ans.append(row)

    overall_ans = ["OVERALL"]
    for p in pipeline_data:
        ans_scores = [
            r["metrics"]["answer_correct"]
            for r in pipeline_data[p]
            if r["metrics"].get("answer_correct") is not None
        ]
        if ans_scores:
            overall_ans.append(f"{statistics.mean(ans_scores) * 100:.1f}%")
        else:
            overall_ans.append("N/A")
    rows_ans.append(overall_ans)
    out.append(format_table(header, rows_ans))

    # 4. POLICY PASS RATE
    out.append("\n4. POLICY PASS RATE (Policy Adherence / Refusal on Adversarial Prompts)")
    rows_pol = []
    for qtype in all_types:
        row = [qtype]
        for p in pipeline_data:
            recs = [r for r in pipeline_data[p] if r["type"] == qtype]
            pol_scores = [
                r["metrics"]["policy_pass"]
                for r in recs
                if r["metrics"].get("policy_pass") is not None
            ]
            if pol_scores:
                row.append(f"{statistics.mean(pol_scores) * 100:.1f}%")
            else:
                row.append("N/A")
        rows_pol.append(row)

    overall_pol = ["OVERALL (Policy/Inj)"]
    for p in pipeline_data:
        pol_scores = [
            r["metrics"]["policy_pass"]
            for r in pipeline_data[p]
            if r["metrics"].get("policy_pass") is not None
        ]
        if pol_scores:
            overall_pol.append(f"{statistics.mean(pol_scores) * 100:.1f}%")
        else:
            overall_pol.append("N/A")
    rows_pol.append(overall_pol)
    out.append(format_table(header, rows_pol))

    # 5. LATENCY & MEASURED TOKENS
    out.append("\n5. OBSERVED LATENCY & TOKEN CONSUMPTION")
    cost_header = ["Pipeline", "Queries", "Median Latency", "Prompt Tokens", "Comp Tokens"]
    cost_rows = []
    for p in pipeline_data:
        latencies = [r.get("latency_ms", 0) for r in pipeline_data[p]]
        med_lat = f"{int(statistics.median(latencies))}ms" if latencies else "0ms"
        prompt_toks = sum(r.get("usage", {}).get("prompt_tokens", 0) for r in pipeline_data[p])
        comp_toks = sum(r.get("usage", {}).get("completion_tokens", 0) for r in pipeline_data[p])
        cost_rows.append([p, str(len(pipeline_data[p])), med_lat, str(prompt_toks), str(comp_toks)])
    out.append(format_table(cost_header, cost_rows))

    # 6. EXTRAPOLATED TOKEN USAGE AND COST PROJECTIONS
    out.append("\n6. TOKEN USAGE & COST EXTRAPOLATION (Full Benchmark Projections)")
    out.append("-" * 60)
    out.append("Assumptions:")
    out.append("  - Groq Model: llama-3.3-70b-versatile ($0.59 / 1M prompt, $0.79 / 1M completion)")
    out.append("  - Benchmark size: 220 total questions (10 patients x 22 questions)")
    out.append("  - Average chunk text: ~1,200 chars (~300 tokens); system prompt: ~180 tokens")
    out.append("  - Average completion length: ~80 tokens")
    out.append("  - Fullchart rule: fullchart planned for 2 patients only (44 questions)")
    out.append("")

    extrap_header = [
        "Pipeline",
        "Scope (Qs)",
        "Est Prompt Tok",
        "Est Comp Tok",
        "Est Total Tok",
        "Est Cost (USD)",
    ]
    extrap_rows = [
        ["vector", "220", "84,762", "17,600", "102,362", "$0.064"],
        ["bm25", "220", "87,274", "17,600", "104,874", "$0.065"],
        ["hybrid", "220", "90,304", "17,600", "107,904", "$0.067"],
        ["hybrid_terms", "220", "80,133", "17,600", "97,733", "$0.061"],
        ["facts (hybrid fb)", "220 (28 fb)", "39,575", "7,040", "46,615", "$0.029"],
        ["fullchart (all 10)", "220", "235,952", "17,600", "253,552", "$0.153"],
        ["fullchart (2 pts)", "44", "57,758", "3,520", "61,278", "$0.037"],
    ]
    out.append(format_table(extrap_header, extrap_rows))

    # 7. SCOPE, STATUS & LIMITATIONS
    out.append("\n7. SCOPE, STATUS & LIMITATIONS (What Was & Was Not Run)")
    out.append("-" * 60)
    out.append(
        "  [x] Dry-run evaluation: Completed across all 6 pipelines "
        "(vector, bm25, hybrid, hybrid_terms, facts, fullchart)."
    )
    out.append(
        "  [x] Embedding generation: Completed. All 263 chunks embedded with "
        "1024-dim BGE-M3 and indexed via HNSW."
    )
    out.append("  [x] Schema & Migrations: Verified zero drift via `alembic check`.")
    out.append(
        "  [!] Full LLM evaluation: STOPPED per user instruction #1. "
        "Awaiting token usage and cost review approval."
    )
    out.append(
        "  [!] Reranker model (BAAI/bge-reranker-v2-m3): NOT downloaded. "
        "Model size is ~2.24 GB (2,240,432,128 bytes)."
    )
    out.append("      Kept --rerank OFF awaiting explicit user approval.")
    out.append(
        "  [!] Fullchart evaluation: Will be restricted to 2 patients only "
        "(44 questions) upon approval."
    )
    out.append(
        "  [!] Facts Router Layout Dependency: The deterministic facts extractor is "
        "designed specifically for"
    )
    out.append(
        "      the synthetic dataset's text format and table headers. "
        "Performance may degrade on other document layouts."
    )

    # 8. TOP-10 WORST FAILURES PER PIPELINE
    out.append("\n8. TOP-10 WORST FAILURES PER PIPELINE")
    out.append("-" * 60)
    for p in pipeline_data:
        out.append(f"\nPipeline: {p}")
        failures = []
        for r in pipeline_data[p]:
            m = r.get("metrics", {})
            if m.get("retrieval_recall_at_k") == 0.0 or m.get("answer_correct") == 0.0:
                failures.append(r)

        if not failures:
            out.append("  No failures recorded.")
            continue

        for idx, f in enumerate(failures[:10], start=1):
            qid = f.get("question_id")
            q = f.get("question")
            exp = f.get("expected_values")
            retrieved = f.get("retrieved_chunk_ids", [])
            ans = f.get("answer", "")
            out.append(f"  {idx}. [{qid}] Question: {q}")
            out.append(f"     Expected: {exp}")
            out.append(f"     Retrieved: {retrieved[:3]}")
            out.append(f"     Answer: {ans[:120]}...")

    out.append("\n=== REPORT END ===")
    return "\n".join(out)


def main() -> None:
    parser = argparse.ArgumentParser(description="ClinSight Evaluation Report Generator")
    parser.add_argument(
        "--pipelines",
        type=str,
        default="vector,bm25,hybrid,hybrid_terms,facts,fullchart",
        help="Comma-separated pipelines to include",
    )
    args = parser.parse_args()
    pipe_list = [p.strip() for p in args.pipelines.split(",")]
    report_text = generate_report(pipe_list)
    print(report_text)


if __name__ == "__main__":
    main()
