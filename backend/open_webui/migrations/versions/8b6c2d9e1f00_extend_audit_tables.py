"""extend audit tables

Revision ID: 8b6c2d9e1f00
Revises: 7a1b2c3d4e5f
Create Date: 2026-04-26
"""

from alembic import op
import sqlalchemy as sa


revision = "8b6c2d9e1f00"
down_revision = "7a1b2c3d4e5f"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("response_meta", sa.Column("session_id", sa.String(), nullable=True))
    op.add_column("response_meta", sa.Column("conversation_id", sa.String(), nullable=True))
    op.add_column("response_meta", sa.Column("message_id", sa.String(), nullable=True))
    op.add_column("response_meta", sa.Column("request_id", sa.String(), nullable=True))
    op.add_column("response_meta", sa.Column("upstream_id", sa.String(), nullable=True))

    op.add_column("request_texts", sa.Column("response_meta_id", sa.String(), nullable=True))
    op.add_column("request_texts", sa.Column("session_id", sa.String(), nullable=True))
    op.add_column("request_texts", sa.Column("message_id", sa.String(), nullable=True))
    op.add_column("request_texts", sa.Column("policy_id", sa.String(), nullable=True))
    op.add_column("request_texts", sa.Column("detector_version", sa.String(), nullable=True))

    op.create_index("idx_response_meta_session_id", "response_meta", ["session_id"])
    op.create_index("idx_response_meta_conversation_id", "response_meta", ["conversation_id"])
    op.create_index("idx_response_meta_request_id", "response_meta", ["request_id"])

    op.create_index("idx_request_texts_response_meta_id", "request_texts", ["response_meta_id"])
    op.create_index("idx_request_texts_session_id", "request_texts", ["session_id"])


def downgrade():
    op.drop_index("idx_request_texts_session_id", table_name="request_texts")
    op.drop_index("idx_request_texts_response_meta_id", table_name="request_texts")

    op.drop_index("idx_response_meta_request_id", table_name="response_meta")
    op.drop_index("idx_response_meta_conversation_id", table_name="response_meta")
    op.drop_index("idx_response_meta_session_id", table_name="response_meta")

    op.drop_column("request_texts", "detector_version")
    op.drop_column("request_texts", "policy_id")
    op.drop_column("request_texts", "message_id")
    op.drop_column("request_texts", "session_id")
    op.drop_column("request_texts", "response_meta_id")

    op.drop_column("response_meta", "upstream_id")
    op.drop_column("response_meta", "request_id")
    op.drop_column("response_meta", "message_id")
    op.drop_column("response_meta", "conversation_id")
    op.drop_column("response_meta", "session_id")
