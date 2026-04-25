"""add quota_mode to quotas

Revision ID: 0253328bf353
Revises: 4b95447f00fd
Create Date: 2026-04-14 21:25:56.048649

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
import open_webui.internal.db


# revision identifiers, used by Alembic.
revision: str = '0253328bf353'
down_revision: Union[str, None] = '4b95447f00fd'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _has_column(table_name: str, column_name: str) -> bool:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    columns = inspector.get_columns(table_name)
    return any(col["name"] == column_name for col in columns)


def upgrade() -> None:
    if not _has_column("quotas", "quota_mode"):
        op.add_column(
            "quotas",
            sa.Column(
                "quota_mode",
                sa.String(),
                nullable=False,
                server_default="shared_evenly",
            ),
        )

    with op.batch_alter_table("quotas") as batch_op:
        batch_op.alter_column(
            "budget_usd",
            existing_type=sa.Float(),
            nullable=True,
        )
        batch_op.create_check_constraint(
            "ck_quotas_quota_mode",
            "quota_mode IN ('shared_evenly', 'unique')",
        )


def downgrade() -> None:
    with op.batch_alter_table("quotas") as batch_op:
        batch_op.alter_column(
            "budget_usd",
            existing_type=sa.Float(),
            nullable=False,
        )
        batch_op.drop_constraint("ck_quotas_quota_mode", type_="check")
        batch_op.drop_column("quota_mode")