"""add patient meals and chat

Revision ID: 0003
Revises: 0002
"""

import sqlalchemy as sa

from alembic import op

revision = "0003"
down_revision = "0002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "meal_logs",
        sa.Column("id", sa.String(length=64), primary_key=True),
        sa.Column(
            "patient_id",
            sa.String(length=64),
            sa.ForeignKey("patients.id"),
            nullable=False,
            index=True,
        ),
        sa.Column("local_date", sa.String(length=10), nullable=False, index=True),
        sa.Column("logged_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("meal_type", sa.String(length=32), nullable=False, server_default="unspecified"),
        sa.Column("raw_text", sa.Text(), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("clarification_question", sa.Text(), nullable=True),
        sa.Column("clarification_options", sa.JSON(), nullable=True),
        sa.Column("safety_flag", sa.String(length=64), nullable=True),
    )

    op.create_table(
        "meal_items",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column(
            "meal_log_id",
            sa.String(length=64),
            sa.ForeignKey("meal_logs.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        ),
        sa.Column("food_id", sa.String(length=64), nullable=False, index=True),
        sa.Column("food_name_ar", sa.String(length=128), nullable=False),
        sa.Column("food_name_en", sa.String(length=128), nullable=False),
        sa.Column("quantity", sa.Float(), nullable=False, server_default="1.0"),
        sa.Column("unit", sa.String(length=64), nullable=False),
        sa.Column("grams", sa.Float(), nullable=False),
        sa.Column("kcal", sa.Float(), nullable=False),
        sa.Column("protein_g", sa.Float(), nullable=False),
        sa.Column("carbs_g", sa.Float(), nullable=False),
        sa.Column("fat_g", sa.Float(), nullable=False),
        sa.Column("fiber_g", sa.Float(), nullable=False),
        sa.Column("match_method", sa.String(length=32), nullable=False),
        sa.Column("match_score", sa.Float(), nullable=False, server_default="1.0"),
        sa.Column("confirmed", sa.Boolean(), nullable=False, server_default=sa.true()),
    )

    op.create_table(
        "patient_chat_messages",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column(
            "patient_id",
            sa.String(length=64),
            sa.ForeignKey("patients.id"),
            nullable=False,
            index=True,
        ),
        sa.Column("role", sa.String(length=16), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column(
            "meal_log_id",
            sa.String(length=64),
            sa.ForeignKey("meal_logs.id", ondelete="SET NULL"),
            nullable=True,
            index=True,
        ),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )


def downgrade() -> None:
    op.drop_table("patient_chat_messages")
    op.drop_table("meal_items")
    op.drop_table("meal_logs")
