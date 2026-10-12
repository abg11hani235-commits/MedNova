"""Embed chunks in PostgreSQL database using BAAI/bge-m3.

Idempotent: skips chunks that already have embeddings unless --force is given.
Prints a clear notice before downloading model weights.
Supports custom model injection for testing.
"""

from __future__ import annotations

import argparse
import sys
import time
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import get_settings
from app.db import get_engine
from app.models import Chunk


def get_embedder(model_name: str | None = None) -> Any:
    """Load SentenceTransformer embedding model with prominent download notice."""
    settings = get_settings()
    name = model_name or settings.embedding_model
    print(
        f"[INFO] Initializing embedding model '{name}'...",
        file=sys.stderr,
    )
    from sentence_transformers import SentenceTransformer

    try:
        return SentenceTransformer(name, local_files_only=True)
    except Exception:
        return SentenceTransformer(name)


def embed_all_chunks(
    session: Session,
    embedder: Any = None,
    batch_size: int = 32,
    force: bool = False,
    patient_id: str | None = None,
) -> dict[str, Any]:
    """Embed chunks and save vectors into chunks.embedding.

    Returns summary dictionary with counts and timing.
    """
    settings = get_settings()
    target_dim = settings.embedding_dim

    stmt = select(Chunk)
    if patient_id:
        stmt = stmt.where(Chunk.patient_id == patient_id)
    if not force:
        stmt = stmt.where(Chunk.embedding.is_(None))

    chunks_to_embed = list(session.scalars(stmt))
    total_to_embed = len(chunks_to_embed)

    if total_to_embed == 0:
        print("[INFO] All chunks already embedded. Use --force to re-embed.")
        return {"total": 0, "embedded": 0, "skipped": 0, "time_seconds": 0.0}

    if embedder is None:
        embedder = get_embedder()

    start_time = time.time()
    embedded_count = 0

    for i in range(0, total_to_embed, batch_size):
        batch = chunks_to_embed[i : i + batch_size]
        texts = [chunk.text for chunk in batch]

        # Handle sentence-transformers or mock embedder
        if hasattr(embedder, "encode"):
            vectors = embedder.encode(texts, normalize_embeddings=True)
        else:
            vectors = embedder(texts)

        for chunk, vec in zip(batch, vectors, strict=False):
            # Convert numpy array or list to python list of floats
            vec_list = [float(v) for v in vec]
            if len(vec_list) != target_dim:
                raise ValueError(
                    f"Embedding dimension mismatch: got {len(vec_list)}, expected {target_dim}"
                )
            chunk.embedding = vec_list

        session.commit()
        embedded_count += len(batch)
        print(f"[INFO] Embedded {embedded_count}/{total_to_embed} chunks...")

    elapsed = time.time() - start_time
    print(f"[SUCCESS] Embedded {embedded_count} chunks in {elapsed:.2f}s.")
    return {
        "total": total_to_embed,
        "embedded": embedded_count,
        "skipped": 0,
        "time_seconds": elapsed,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Embed chunks using BGE-M3")
    parser.add_argument("--batch-size", type=int, default=32, help="Batch size for embedding")
    parser.add_argument("--force", action="store_true", help="Re-embed all chunks")
    parser.add_argument("--patient-id", type=str, default=None, help="Filter by patient ID")
    args = parser.parse_args()

    engine = get_engine()
    with Session(engine) as session:
        embed_all_chunks(
            session=session,
            batch_size=args.batch_size,
            force=args.force,
            patient_id=args.patient_id,
        )


if __name__ == "__main__":
    main()
