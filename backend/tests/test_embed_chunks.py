"""Unit tests for embed_chunks.py with stub embedder."""

from unittest.mock import MagicMock

from app.config import get_settings
from app.models import Chunk
from scripts.embed_chunks import embed_all_chunks


class StubEmbedder:
    def __init__(self, dim: int = 1024):
        self.dim = dim

    def encode(self, texts, normalize_embeddings=True):
        # Deterministic lightweight 1024-dim stub vectors
        return [[0.1] * self.dim for _ in texts]


def test_embed_all_chunks_idempotent_and_stub():
    settings = get_settings()
    stub = StubEmbedder(dim=settings.embedding_dim)

    # Create mock chunks
    chunk1 = Chunk(
        id="c1", patient_id="p1", file_id="f1", page=1, text="Test text 1", embedding=None
    )
    chunk2 = Chunk(
        id="c2", patient_id="p1", file_id="f1", page=2, text="Test text 2", embedding=None
    )

    session = MagicMock()
    # First query returns both chunks
    session.scalars.return_value = [chunk1, chunk2]

    res = embed_all_chunks(session, embedder=stub, batch_size=2, force=False)
    assert res["embedded"] == 2
    assert chunk1.embedding is not None
    assert len(chunk1.embedding) == settings.embedding_dim
    assert chunk2.embedding is not None
    assert session.commit.called

    # When all chunks are already embedded
    session.scalars.return_value = []
    res_empty = embed_all_chunks(session, embedder=stub, batch_size=2, force=False)
    assert res_empty["embedded"] == 0
