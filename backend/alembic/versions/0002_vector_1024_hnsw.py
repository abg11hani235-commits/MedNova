"""vector 1024 hnsw

Revision ID: 0002
Revises: 0001
"""

import sqlalchemy as sa
from alembic import op
from app.config import get_settings
from pgvector.sqlalchemy import Vector

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    dim = get_settings().embedding_dim
    op.drop_column("chunks", "embedding")
    op.add_column("chunks", sa.Column("embedding", Vector(dim), nullable=True))
    op.create_index(
        "ix_chunks_embedding_hnsw",
        "chunks",
        ["embedding"],
        unique=False,
        postgresql_using="hnsw",
        postgresql_ops={"embedding": "vector_cosine_ops"},
    )


def downgrade() -> None:
    op.drop_index("ix_chunks_embedding_hnsw", table_name="chunks", postgresql_using="hnsw")
    op.drop_column("chunks", "embedding")
    op.add_column("chunks", sa.Column("embedding", Vector(768), nullable=True))
