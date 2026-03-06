"""add quotas table

Revision ID: 4b95447f00fd
Revises: 3e0e00844bb0
Create Date: 2026-03-06 23:39:05.314491

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
import open_webui.internal.db


# revision identifiers, used by Alembic.
revision: str = '4b95447f00fd'
down_revision: Union[str, None] = '3e0e00844bb0'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade():
    op.create_table(
        "quotas",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),

        sa.Column("scope_type", sa.String(), nullable=False),   # company | group
        sa.Column("scope_id", sa.String(), nullable=False),     # company or group_id
        sa.Column("scope_name", sa.String(), nullable=False),

        sa.Column("budget_usd", sa.Float(), nullable=False),

        sa.Column("warning_percent", sa.Float(), nullable=False, server_default="80"),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("1")),

        sa.Column("period_type", sa.String(), nullable=False, server_default="monthly"),

        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),

        sa.CheckConstraint("scope_type IN ('company', 'group')", name="ck_quotas_scope_type"),
        sa.CheckConstraint("period_type IN ('monthly')", name="ck_quotas_period_type"),
        sa.UniqueConstraint("scope_type", "scope_id", name="uq_quotas_scope_type_scope_id"),
    )

    op.create_index("ix_quotas_scope_type", "quotas", ["scope_type"])
    op.create_index("ix_quotas_scope_id", "quotas", ["scope_id"])

def downgrade():
    op.drop_index("ix_quotas_scope_id", table_name="quotas")
    op.drop_index("ix_quotas_scope_type", table_name="quotas")
    op.drop_table("quotas")
