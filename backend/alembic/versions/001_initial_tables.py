"""Initial tables: conversations + messages

Revision ID: 001
Revises:
Create Date: 2026-06-02
"""
import sqlalchemy as sa
from alembic import op

revision = "001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ── conversations ──────────────────────────────────────────
    op.create_table(
        "conversations",
        sa.Column("id",         sa.String(36),              primary_key=True),
        sa.Column("title",      sa.String(200),             nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False,
                  server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False,
                  server_default=sa.func.now()),
    )

    # ── messages ───────────────────────────────────────────────
    op.create_table(
        "messages",
        sa.Column("id",                sa.String(36),              primary_key=True),
        sa.Column("conversation_id",   sa.String(36),              nullable=False),
        sa.Column("role",              sa.String(20),              nullable=False),
        sa.Column("content",           sa.Text,                    nullable=False),
        sa.Column("retrieved_context", sa.JSON,                    nullable=True),
        sa.Column("created_at",        sa.DateTime(timezone=True), nullable=False,
                  server_default=sa.func.now()),

        sa.ForeignKeyConstraint(
            ["conversation_id"], ["conversations.id"],
            ondelete="CASCADE",
        ),
    )

    # Indexes
    op.create_index("ix_messages_conversation_id", "messages", ["conversation_id"])
    op.create_index("ix_messages_created_at",      "messages", ["created_at"])


def downgrade() -> None:
    op.drop_table("messages")
    op.drop_table("conversations")
