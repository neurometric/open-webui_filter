from sqlalchemy import (
    Column,
    Integer,
    String,
    Float,
    Boolean,
    DateTime,
    CheckConstraint,
    UniqueConstraint,
    text,
)
from open_webui.internal.db import Base


class Quota(Base):
    __tablename__ = "quotas"

    id = Column(Integer, primary_key=True, autoincrement=True)

    # company | group
    scope_type = Column(String, nullable=False)
    # company or group_id
    scope_id = Column(String, nullable=False)
    scope_name = Column(String, nullable=False)

    # None = квота не задана
    budget_usd = Column(Float, nullable=True)

    warning_percent = Column(Float, nullable=False, server_default=text("80"))
    is_active = Column(Boolean, nullable=False, server_default=text("1"))

    # shared_evenly | unique
    quota_mode = Column(String, nullable=False, server_default=text("'shared_evenly'"))

    # пока поддерживаем только monthly
    period_type = Column(String, nullable=False, server_default=text("'monthly'"))

    created_at = Column(
        DateTime,
        nullable=False,
        server_default=text("CURRENT_TIMESTAMP"),
    )
    updated_at = Column(
        DateTime,
        nullable=False,
        server_default=text("CURRENT_TIMESTAMP"),
    )

    __table_args__ = (
        CheckConstraint(
            "scope_type IN ('company', 'group')",
            name="ck_quotas_scope_type",
        ),
        CheckConstraint(
            "quota_mode IN ('shared_evenly', 'unique')",
            name="ck_quotas_quota_mode",
        ),
        CheckConstraint(
            "period_type IN ('monthly')",
            name="ck_quotas_period_type",
        ),
        UniqueConstraint(
            "scope_type",
            "scope_id",
            name="uq_quotas_scope_type_scope_id",
        ),
    )
    
    def to_dict(self):
        return {
            "id": self.id,
            "scope_type": self.scope_type,
            "scope_id": self.scope_id,
            "scope_name": self.scope_name,
            "budget_usd": self.budget_usd,
            "warning_percent": self.warning_percent,
            "is_active": self.is_active,
            "quota_mode": self.quota_mode,
            "period_type": self.period_type,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
        }