"""initial schema

Revision ID: 0001
Revises:
"""

import sqlalchemy as sa
from pgvector.sqlalchemy import Vector

from alembic import op
from app.config import get_settings

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")
    op.create_table(
        "patients",
        sa.Column("id", sa.String(64), primary_key=True),
        sa.Column("display_name", sa.String(128), nullable=False),
        sa.Column("age", sa.Integer, nullable=False),
        sa.Column("diabetes_type", sa.String(32), nullable=False),
        sa.Column("duration_years", sa.Integer, nullable=True),
        sa.Column("medications", sa.JSON, nullable=False),
        sa.Column("as_of_date", sa.String(10), nullable=False),
        sa.Column("trends", sa.JSON, nullable=False),
        sa.Column("care_gaps", sa.JSON, nullable=False),
        sa.Column("chat_questions", sa.JSON, nullable=False),
    )
    op.create_table(
        "files",
        sa.Column("id", sa.String(200), primary_key=True),
        sa.Column(
            "patient_id", sa.String(64), sa.ForeignKey("patients.id"), nullable=False, index=True
        ),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("kind", sa.String(32), nullable=False),
        sa.Column("date", sa.String(10), nullable=True),
        sa.Column("is_scan", sa.Boolean, nullable=False),
        sa.Column("status", sa.String(32), nullable=False),
        sa.Column("storage_path", sa.String(500), nullable=True),
    )
    op.create_table(
        "chunks",
        sa.Column("id", sa.String(240), primary_key=True),
        sa.Column(
            "patient_id", sa.String(64), sa.ForeignKey("patients.id"), nullable=False, index=True
        ),
        sa.Column("file_id", sa.String(200), sa.ForeignKey("files.id"), nullable=False, index=True),
        sa.Column("page", sa.Integer, nullable=False),
        sa.Column("text", sa.Text, nullable=False),
        sa.Column("embedding", Vector(get_settings().embedding_dim), nullable=True),
    )
    op.create_table(
        "insights",
        sa.Column("id", sa.String(200), primary_key=True),
        sa.Column(
            "patient_id", sa.String(64), sa.ForeignKey("patients.id"), nullable=False, index=True
        ),
        sa.Column("type", sa.String(64), nullable=False),
        sa.Column("severity", sa.String(16), nullable=False),
        sa.Column("statement", sa.Text, nullable=False),
        sa.Column("why", sa.Text, nullable=True),
        sa.Column("source_chunk_id", sa.String(240), sa.ForeignKey("chunks.id"), nullable=True),
        sa.Column("quote", sa.Text, nullable=True),
        sa.Column("absence_note", sa.Text, nullable=True),
        sa.Column("review_state", sa.String(16), nullable=False),
        sa.Column("feedback", sa.String(16), nullable=False),
        sa.Column("rank", sa.Integer, nullable=False),
    )
    op.create_table(
        "chat_messages",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column(
            "patient_id", sa.String(64), sa.ForeignKey("patients.id"), nullable=False, index=True
        ),
        sa.Column("role", sa.String(16), nullable=False),
        sa.Column("content", sa.Text, nullable=False),
        sa.Column("answerable", sa.Boolean, nullable=True),
        sa.Column("source_chunk_id", sa.String(240), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_table(
        "audit_log",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("ts", sa.DateTime(timezone=True), nullable=False),
        sa.Column("actor", sa.String(64), nullable=False),
        sa.Column("action", sa.String(64), nullable=False),
        sa.Column("patient_id", sa.String(64), nullable=True),
        sa.Column("detail", sa.Text, nullable=True),
    )


def downgrade() -> None:
    for t in ("audit_log", "chat_messages", "insights", "chunks", "files", "patients"):
        op.drop_table(t)
