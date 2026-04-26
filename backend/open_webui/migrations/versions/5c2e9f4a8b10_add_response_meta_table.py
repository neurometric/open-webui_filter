"""add response_meta table

Revision ID: 5c2e9f4a8b10
Revises: 4b95447f00fd
Create Date: 2026-04-25
"""

from alembic import op
import sqlalchemy as sa


revision = "5c2e9f4a8b10"
down_revision = "0253328bf353"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "response_meta",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column(
            "created_at",
            sa.DateTime(),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
        sa.Column("user_id", sa.String(), nullable=True),
        sa.Column("provider", sa.String(), nullable=True),
        sa.Column("model", sa.String(), nullable=True),
        sa.Column("prompt_tokens", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("completion_tokens", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("total_tokens", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("cost_usd", sa.Float(), nullable=False, server_default="0"),
        sa.Column("latency_ms", sa.Integer(), nullable=True),
        sa.Column("meta_json", sa.JSON(), nullable=True),
    )

    op.create_index(
        "idx_response_meta_created_at",
        "response_meta",
        ["created_at"],
    )
    op.create_index(
        "idx_response_meta_user_id",
        "response_meta",
        ["user_id"],
    )
    op.create_index(
        "idx_response_meta_model",
        "response_meta",
        ["model"],
    )


def downgrade():
    op.drop_index("idx_response_meta_model", table_name="response_meta")
    op.drop_index("idx_response_meta_user_id", table_name="response_meta")
    op.drop_index("idx_response_meta_created_at", table_name="response_meta")
    op.drop_table("response_meta")