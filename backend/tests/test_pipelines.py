"""Unit tests for retrieval pipelines, RRF, and BM25 patient isolation (app/rag/pipeline.py)."""

from app.models import Chunk, File
from app.rag.pipeline import RAGPipeline, bm25_tokenize, reciprocal_rank_fusion


class FakeLLMClient:
    def __init__(self, response=None, usage=None):
        self.response = response or {
            "answerable": True,
            "answer": "HbA1c was 8.9%. Worth reviewing.",
            "claims": [
                {
                    "text": "HbA1c was 8.9%.",
                    "chunk_id": "c1",
                    "quote": "HbA1c: 8.9%",
                }
            ],
        }
        self.usage = usage or {"prompt_tokens": 100, "completion_tokens": 20}

    def generate(self, messages, temperature=0.1, use_cache=True):
        return self.response, self.usage, 150


class StubEmbedder:
    def __init__(self, dim=1024):
        self.dim = dim

    def encode(self, texts, normalize_embeddings=True):
        return [[0.05] * self.dim for _ in texts]


def test_reciprocal_rank_fusion_known_rankings():
    # Test RRF with known rankings
    list1 = ["docA", "docB", "docC"]
    list2 = ["docB", "docA", "docD"]
    # k = 60
    # docA score: 1/(60+1) + 1/(60+2) = 1/61 + 1/62 = 0.016393 + 0.016129 = 0.032522
    # docB score: 1/(60+2) + 1/(60+1) = 1/62 + 1/61 = 0.032522
    # docC score: 1/(60+3) = 1/63 = 0.015873
    # docD score: 1/(60+3) = 1/63 = 0.015873
    fused = reciprocal_rank_fusion([list1, list2], k=60)
    top_docs = [doc for doc, score in fused]
    assert "docA" in top_docs[:2]
    assert "docB" in top_docs[:2]
    assert "docC" in top_docs[2:]
    assert "docD" in top_docs[2:]

    # Asymmetric rankings: docA rank 1 in both
    list_x = ["docA", "docB"]
    list_y = ["docA", "docC"]
    fused_xy = reciprocal_rank_fusion([list_x, list_y], k=60)
    assert fused_xy[0][0] == "docA"
    assert fused_xy[0][1] > fused_xy[1][1]


def test_bm25_patient_isolation():
    """Ensure BM25 index over patient 1042 chunks never retrieves another patient's chunks."""
    c1 = Chunk(
        id="1042-note-p1",
        patient_id="1042",
        file_id="f1",
        page=1,
        text="HbA1c: 8.9% diabetes check.",
    )
    c2 = Chunk(
        id="1042-note-p2", patient_id="1042", file_id="f1", page=2, text="eGFR: 59 kidney function."
    )
    f1 = File(id="f1", patient_id="1042", name="note.txt", kind="visit_note", date="2026-06-18")

    # Another patient chunk
    c_other = Chunk(
        id="1043-note-p1",
        patient_id="1043",
        file_id="f2",
        page=1,
        text="Patient has secret 1043 data.",
    )

    pipeline = RAGPipeline(embedder=StubEmbedder(), llm_client=FakeLLMClient())
    bm25, indexed_chunks = pipeline._build_bm25_index([c1, c2], {"f1": f1})

    # Only patient 1042 chunks are indexed
    assert len(indexed_chunks) == 2
    for c in indexed_chunks:
        assert c.patient_id == "1042"
        assert c.id != c_other.id


def test_bm25_tokenization():
    tokens = bm25_tokenize("Estimated GFR: 59 mL/min/1.73m² with HbA1c 8.9% on 2026-06-18")
    assert "59" in tokens
    assert "8.9%" in tokens
    assert "2026-06-18" in tokens
    assert "ml/min/1.73m²" in tokens


def test_pipeline_dry_run_and_execution():
    c1 = Chunk(
        id="c1", patient_id="1042", file_id="f1", page=1, text="HbA1c: 8.9% (Reference <5.7%)"
    )
    f1 = File(
        id="f1", patient_id="1042", name="Lab_Report_2026-06-18.pdf", kind="lab", date="2026-06-18"
    )

    fake_llm = FakeLLMClient()
    pipeline = RAGPipeline(embedder=StubEmbedder(), llm_client=fake_llm)

    # 1. Dry run
    res_dry = pipeline.answer(
        patient_id="1042",
        question="What is the HbA1c?",
        pipeline_name="bm25",
        dry_run=True,
        chunks_override=[c1],
        files_map_override={"f1": f1},
    )
    assert res_dry["answerable"] is True
    assert "[DRY RUN]" in res_dry["answer"]
    assert "c1" in res_dry["retrieved_chunk_ids"]
    assert res_dry["usage"]["prompt_tokens"] == 0

    # 2. Live with FakeLLM
    res_live = pipeline.answer(
        patient_id="1042",
        question="What is the HbA1c?",
        pipeline_name="bm25",
        dry_run=False,
        use_cache=False,
        chunks_override=[c1],
        files_map_override={"f1": f1},
    )
    assert res_live["answerable"] is True
    assert "8.9" in res_live["answer"]
    assert len(res_live["citations"]) == 1
    assert res_live["citations"][0]["chunk_id"] == "c1"
