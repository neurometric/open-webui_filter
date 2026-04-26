"""add request_texts table

Revision ID: 7a1b2c3d4e5f
Revises: 5c2e9f4a8b10
Create Date: 2026-04-25
"""

from alembic import op
import sqlalchemy as sa


revision = "7a1b2c3d4e5f"
down_revision = "5c2e9f4a8b10"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "request_texts",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column(
            "created_at",
            sa.DateTime(),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
        sa.Column("user_id", sa.String(), nullable=True),
        sa.Column("user_name", sa.String(), nullable=True),
        sa.Column("user_email", sa.String(), nullable=True),
        sa.Column("user_role", sa.String(), nullable=True),
        sa.Column("conversation_id", sa.String(), nullable=True),
        sa.Column("raw_text", sa.Text(), nullable=True),
        sa.Column("masked_text", sa.Text(), nullable=True),
        sa.Column("has_pii", sa.Integer(), nullable=False, server_default="0"),
    )

    op.create_index("idx_request_texts_created_at", "request_texts", ["created_at"])
    op.create_index("idx_request_texts_user_id", "request_texts", ["user_id"])
    op.create_index("idx_request_texts_conversation_id", "request_texts", ["conversation_id"])


def downgrade():
    op.drop_index("idx_request_texts_conversation_id", table_name="request_texts")
    op.drop_index("idx_request_texts_user_id", table_name="request_texts")
    op.drop_index("idx_request_texts_created_at", table_name="request_texts")
    op.drop_table("request_texts")