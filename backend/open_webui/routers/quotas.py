import logging
from typing import List, Optional, Literal

from fastapi import APIRouter, Depends, Query, HTTPException
from pydantic import BaseModel, Field, ConfigDict
from sqlalchemy import text, bindparam

from open_webui.env import SRC_LOG_LEVELS
from open_webui.utils.auth import get_verified_user
from open_webui.internal.db import Session


log = logging.getLogger(__name__)
log.setLevel(SRC_LOG_LEVELS["MAIN"])

router = APIRouter()


class QuotaSummary(BaseModel):
    totalBudgetUsd: Optional[float] = None
    spentUsd: Optional[float] = None
    remainingUsd: Optional[float] = None
    spentPercent: Optional[float] = None


class QuotaMonitoringItem(BaseModel):
    scopeType: str
    scopeId: str
    scopeName: str

    budgetUsd: Optional[float] = None
    spentUsd: Optional[float] = None
    remainingUsd: Optional[float] = None
    spentPercent: Optional[float] = None

    warningPercent: Optional[float] = None
    isActive: bool = True
    quotaMode: Optional[str] = None
    usersCount: Optional[int] = None
    perUserBudgetUsd: Optional[float] = None

    status: str


class UpdateGroupQuotaForm(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    budget_usd: Optional[float] = Field(default=None, ge=0, alias="budgetUsd")
    is_active: bool = Field(alias="isActive")
    quota_mode: Literal["shared_evenly", "unique"] = Field(alias="quotaMode")


class ChatQuotaState(BaseModel):
    allowed: bool
    quotaMode: Optional[str] = None

    percentUsed: Optional[float] = None
    spentUsd: Optional[float] = None
    limitUsd: Optional[float] = None
    remainingUsd: Optional[float] = None

    notifyLevel: Optional[int] = None
    message: Optional[str] = None

class GroupUserQuotaItem(BaseModel):
    userId: str
    name: str
    email: Optional[str] = None
    allocatedUsd: Optional[float] = None
    spentUsd: float = 0.0

def _get_notify_level(percent_used: Optional[float]) -> Optional[int]:
    if percent_used is None:
        return None
    if percent_used >= 100:
        return 100
    if percent_used >= 95:
        return 95
    if percent_used >= 90:
        return 90
    if percent_used >= 85:
        return 85
    return None


def get_user_chat_quota_state(user_id: str) -> ChatQuotaState:
    group = Session.execute(
        text("""
            SELECT
              g.id AS group_id,
              g.name AS group_name
            FROM group_member gm
            JOIN "group" g
              ON g.id = gm.group_id
            WHERE gm.user_id = :user_id
            ORDER BY g.name ASC
            LIMIT 1
        """),
        {"user_id": user_id},
    ).mappings().first()

    if not group:
        return ChatQuotaState(
            allowed=True,
            message=None,
        )

    quota = Session.execute(
        text("""
            SELECT
              budget_usd,
              is_active,
              quota_mode
            FROM quotas
            WHERE scope_type = 'group' AND scope_id = :group_id
            LIMIT 1
        """),
        {"group_id": group["group_id"]},
    ).mappings().first()

    if not quota:
        return ChatQuotaState(
            allowed=True,
            message=None,
        )

    budget_usd = quota.get("budget_usd")
    is_active = bool(quota.get("is_active"))
    quota_mode = quota.get("quota_mode") or "shared_evenly"

    if not is_active or budget_usd is None:
        return ChatQuotaState(
            allowed=True,
            quotaMode=quota_mode,
            message=None,
        )

    budget_usd = float(budget_usd)

    if quota_mode == "shared_evenly":
        users_count_row = Session.execute(
            text("""
                SELECT COUNT(DISTINCT gm.user_id) AS users_count
                FROM group_member gm
                WHERE gm.group_id = :group_id
            """),
            {"group_id": group["group_id"]},
        ).mappings().first()

        users_count = int((users_count_row or {}).get("users_count") or 0)
        limit_usd = (budget_usd / users_count) if users_count > 0 else 0.0

        spent_row = Session.execute(
            text("""
                SELECT COALESCE(SUM(rm.cost_usd), 0) AS spent_usd
                FROM group_member gm
                LEFT JOIN response_meta rm
                  ON rm.user_id = gm.user_id
                WHERE gm.group_id = :group_id
                  AND gm.user_id = :user_id
            """),
            {"group_id": group["group_id"], "user_id": user_id},
        ).mappings().first()

        spent_usd = float((spent_row or {}).get("spent_usd") or 0.0)
    else:
        limit_usd = budget_usd

        spent_row = Session.execute(
            text("""
                SELECT COALESCE(SUM(rm.cost_usd), 0) AS spent_usd
                FROM group_member gm
                LEFT JOIN response_meta rm
                  ON rm.user_id = gm.user_id
                WHERE gm.group_id = :group_id
            """),
            {"group_id": group["group_id"]},
        ).mappings().first()

        spent_usd = float((spent_row or {}).get("spent_usd") or 0.0)

    remaining_usd = limit_usd - spent_usd if limit_usd is not None else None
    percent_used = (spent_usd / limit_usd * 100.0) if limit_usd and limit_usd > 0 else 0.0
    notify_level = _get_notify_level(percent_used)
    allowed = percent_used < 100.0

    message = None
    if notify_level == 85:
        message = "Израсходовано 85% от вашей квоты."
    elif notify_level == 90:
        message = "Израсходовано 90% от вашей квоты."
    elif notify_level == 95:
        message = "Израсходовано 95% от вашей квоты."
    elif notify_level == 100:
        message = "Квота исчерпана. Отправка сообщений заблокирована."

    return ChatQuotaState(
        allowed=allowed,
        quotaMode=quota_mode,
        percentUsed=round(percent_used, 2),
        spentUsd=round(spent_usd, 6),
        limitUsd=round(limit_usd, 6) if limit_usd is not None else None,
        remainingUsd=round(remaining_usd, 6) if remaining_usd is not None else None,
        notifyLevel=notify_level,
        message=message,
    )


@router.get(
    "/quotas/chat/check",
    response_model=ChatQuotaState,
    summary="Check current user's chat quota state",
)
async def check_chat_quota(user=Depends(get_verified_user)) -> ChatQuotaState:
    return get_user_chat_quota_state(str(user.id))


def _build_where(date_from: Optional[str], date_to: Optional[str], alias: str = "rm"):
    where_clauses = []
    params = {}

    if date_from:
        where_clauses.append(f"datetime({alias}.created_at) >= datetime(:date_from)")
        params["date_from"] = date_from

    if date_to:
        where_clauses.append(f"datetime({alias}.created_at) <= datetime(:date_to)")
        params["date_to"] = date_to

    where_sql = ("WHERE " + " AND ".join(where_clauses)) if where_clauses else ""
    return where_sql, params


def _calc_status(
    budget_usd: Optional[float],
    spent_percent: Optional[float],
    warning_percent: Optional[float],
    is_active: bool,
) -> str:
    if not is_active:
        return "disabled"

    if budget_usd is None:
        return "no_quota"

    if spent_percent is None:
        return "ok"

    if spent_percent >= 100:
        return "exceeded"

    threshold = warning_percent if warning_percent is not None else 80.0
    if spent_percent >= threshold:
        return "warning"

    return "ok"


def _safe_round(value: Optional[float], digits: int) -> Optional[float]:
    if value is None:
        return None
    return round(value, digits)



@router.get(
    "/quotas/summary",
    response_model=QuotaSummary,
    summary="Get company quota summary",
)
async def get_quotas_summary(
    date_from: Optional[str] = None,
    date_to: Optional[str] = None,
    user=Depends(get_verified_user),
) -> QuotaSummary:
    try:
        quota_query = text("""
            SELECT
              budget_usd,
              warning_percent,
              is_active
            FROM quotas
            WHERE scope_type = 'company' AND scope_id = 'company'
            LIMIT 1
        """)
        quota_row = Session.execute(quota_query).mappings().first()

        budget_usd = (
            float(quota_row.get("budget_usd"))
            if quota_row and quota_row.get("budget_usd") is not None
            else None
        )

        where_sql, params = _build_where(date_from, date_to, alias="rm")

        spent_query = text(f"""
            SELECT COALESCE(SUM(rm.cost_usd), 0) AS spent_usd
            FROM response_meta rm
            {where_sql}
        """)
        spent_row = Session.execute(spent_query, params).mappings().first()
        spent_usd = float(spent_row.get("spent_usd") or 0.0)

        if budget_usd is None:
            return QuotaSummary(
                totalBudgetUsd=None,
                spentUsd=round(spent_usd, 6),
                remainingUsd=None,
                spentPercent=None,
            )

        remaining_usd = budget_usd - spent_usd
        spent_percent = (spent_usd / budget_usd * 100.0) if budget_usd > 0 else 0.0

        return QuotaSummary(
            totalBudgetUsd=round(budget_usd, 2),
            spentUsd=round(spent_usd, 6),
            remainingUsd=round(remaining_usd, 6),
            spentPercent=round(spent_percent, 2),
        )

    except Exception as e:
        log.exception("Failed to load quotas summary: %s", e)
        return QuotaSummary(
            totalBudgetUsd=None,
            spentUsd=0.0,
            remainingUsd=None,
            spentPercent=None,
        )


@router.get(
    "/quotas/monitoring",
    response_model=List[QuotaMonitoringItem],
    summary="Get company and group quota monitoring",
)
async def get_quotas_monitoring(
    date_from: Optional[str] = None,
    date_to: Optional[str] = None,
    group_ids: Optional[List[str]] = Query(default=None),
    user=Depends(get_verified_user),
) -> List[QuotaMonitoringItem]:
    try:
        items: List[QuotaMonitoringItem] = []
        safe_group_ids = [g.strip() for g in (group_ids or []) if g and g.strip()]

        # --- company row ---
        company_quota_query = text("""
            SELECT
              scope_type,
              scope_id,
              scope_name,
              budget_usd,
              warning_percent,
              is_active,
              quota_mode
            FROM quotas
            WHERE scope_type = 'company' AND scope_id = 'company'
            LIMIT 1
        """)
        company_quota = Session.execute(company_quota_query).mappings().first()

        company_where_sql, company_params = _build_where(date_from, date_to, alias="rm")

        company_spent_query = text(f"""
            SELECT COALESCE(SUM(rm.cost_usd), 0) AS spent_usd
            FROM response_meta rm
            {company_where_sql}
        """)
        company_spent_row = Session.execute(company_spent_query, company_params).mappings().first()
        company_spent = float(company_spent_row.get("spent_usd") or 0.0)

        company_budget = (
            float(company_quota.get("budget_usd"))
            if company_quota and company_quota.get("budget_usd") is not None
            else None
        )
        company_warning = (
            float(company_quota.get("warning_percent"))
            if company_quota and company_quota.get("warning_percent") is not None
            else 80.0
        )
        company_active = bool(company_quota.get("is_active")) if company_quota else True
        company_quota_mode = company_quota.get("quota_mode") if company_quota else None

        company_remaining = None if company_budget is None else company_budget - company_spent
        company_percent = (
            None
            if company_budget is None
            else (company_spent / company_budget * 100.0 if company_budget > 0 else 0.0)
        )

        items.append(
            QuotaMonitoringItem(
                scopeType="company",
                scopeId="company",
                scopeName=(company_quota.get("scope_name") if company_quota else "Вся компания"),
                budgetUsd=_safe_round(company_budget, 2),
                spentUsd=round(company_spent, 6),
                remainingUsd=_safe_round(company_remaining, 6),
                spentPercent=_safe_round(company_percent, 2),
                warningPercent=company_warning,
                isActive=company_active,
                quotaMode=company_quota_mode,
                usersCount=None,
                perUserBudgetUsd=None,
                status=_calc_status(company_budget, company_percent, company_warning, company_active),
            )
        )

        # --- groups + quotas ---
        group_params = {}

        groups_and_quotas_query = text("""
            SELECT
              g.id AS group_id,
              g.name AS group_name,
              q.budget_usd AS budget_usd,
              q.warning_percent AS warning_percent,
              q.is_active AS is_active,
              q.quota_mode AS quota_mode
            FROM "group" g
            LEFT JOIN quotas q
              ON q.scope_type = 'group'
             AND q.scope_id = g.id
            {group_filter_sql}
            ORDER BY g.name ASC
        """.replace("{group_filter_sql}", "WHERE g.id IN :group_ids" if safe_group_ids else ""))

        if safe_group_ids:
            group_params["group_ids"] = safe_group_ids
            groups_and_quotas_query = groups_and_quotas_query.bindparams(
                bindparam("group_ids", expanding=True)
            )

        groups_rows = Session.execute(groups_and_quotas_query, group_params).mappings().all()

        # --- group spent ---
        group_spent_conditions = []
        group_spent_params = {}

        if date_from:
            group_spent_conditions.append("datetime(rm.created_at) >= datetime(:date_from)")
            group_spent_params["date_from"] = date_from

        if date_to:
            group_spent_conditions.append("datetime(rm.created_at) <= datetime(:date_to)")
            group_spent_params["date_to"] = date_to

        if safe_group_ids:
            group_spent_conditions.append("g.id IN :group_ids")
            group_spent_params["group_ids"] = safe_group_ids

        group_spent_where_sql = (
            "WHERE " + " AND ".join(group_spent_conditions)
            if group_spent_conditions
            else ""
        )

        group_spent_query = text(f"""
            SELECT
              g.id AS group_id,
              COALESCE(SUM(rm.cost_usd), 0) AS spent_usd
            FROM "group" g
            LEFT JOIN group_member gm
              ON gm.group_id = g.id
            LEFT JOIN "user" u
              ON u.id = gm.user_id
            LEFT JOIN response_meta rm
              ON rm.user_id = u.id
            {group_spent_where_sql}
            GROUP BY g.id
        """)

        if safe_group_ids:
            group_spent_query = group_spent_query.bindparams(
                bindparam("group_ids", expanding=True)
            )

        spent_rows = Session.execute(group_spent_query, group_spent_params).mappings().all()
        spent_map = {row["group_id"]: float(row.get("spent_usd") or 0.0) for row in spent_rows}

        # --- group users count ---
        group_users_params = {}
        group_users_count_query = text("""
            SELECT
              g.id AS group_id,
              COUNT(DISTINCT gm.user_id) AS users_count
            FROM "group" g
            LEFT JOIN group_member gm
              ON gm.group_id = g.id
            {group_filter_sql}
            GROUP BY g.id
        """.replace("{group_filter_sql}", "WHERE g.id IN :group_ids" if safe_group_ids else ""))

        if safe_group_ids:
            group_users_params["group_ids"] = safe_group_ids
            group_users_count_query = group_users_count_query.bindparams(
                bindparam("group_ids", expanding=True)
            )

        users_count_rows = Session.execute(
            group_users_count_query,
            group_users_params
        ).mappings().all()

        users_count_map = {
            row["group_id"]: int(row.get("users_count") or 0)
            for row in users_count_rows
        }

        for row in groups_rows:
            group_id = row["group_id"]
            spent_usd = spent_map.get(group_id, 0.0)
            users_count = users_count_map.get(group_id, 0)

            budget_usd = float(row.get("budget_usd")) if row.get("budget_usd") is not None else None
            warning_percent = (
                float(row.get("warning_percent")) if row.get("warning_percent") is not None else 80.0
            )
            is_active = bool(row.get("is_active")) if row.get("is_active") is not None else True
            quota_mode = row.get("quota_mode") or "shared_evenly"

            per_user_budget_usd = None
            if budget_usd is not None and quota_mode == "shared_evenly":
                per_user_budget_usd = (budget_usd / users_count) if users_count > 0 else 0.0

            remaining_usd = None if budget_usd is None else budget_usd - spent_usd
            spent_percent = (
                None
                if budget_usd is None
                else (spent_usd / budget_usd * 100.0 if budget_usd > 0 else 0.0)
            )

            items.append(
                QuotaMonitoringItem(
                    scopeType="group",
                    scopeId=group_id,
                    scopeName=row.get("group_name") or group_id,
                    budgetUsd=_safe_round(budget_usd, 2),
                    spentUsd=round(spent_usd, 6),
                    remainingUsd=_safe_round(remaining_usd, 6),
                    spentPercent=_safe_round(spent_percent, 2),
                    warningPercent=warning_percent,
                    isActive=is_active,
                    quotaMode=quota_mode,
                    usersCount=users_count,
                    perUserBudgetUsd=_safe_round(per_user_budget_usd, 2),
                    status=_calc_status(budget_usd, spent_percent, warning_percent, is_active),
                )
            )

        return items

    except Exception as e:
        log.exception("Failed to load quotas monitoring: %s", e)
        return []

@router.get(
    "/quotas/groups/{group_id}/users",
    response_model=List[GroupUserQuotaItem],
    summary="Get group users quota breakdown",
)
async def get_group_users_quota(
    group_id: str,
    user=Depends(get_verified_user),
) -> List[GroupUserQuotaItem]:
    try:
        group_row = Session.execute(
            text("""
                SELECT
                  g.id,
                  g.name
                FROM "group" g
                WHERE g.id = :group_id
                LIMIT 1
            """),
            {"group_id": group_id},
        ).mappings().first()

        if not group_row:
            raise HTTPException(status_code=404, detail="Группа не найдена")

        quota_row = Session.execute(
            text("""
                SELECT
                  budget_usd,
                  quota_mode,
                  is_active
                FROM quotas
                WHERE scope_type = 'group' AND scope_id = :group_id
                LIMIT 1
            """),
            {"group_id": group_id},
        ).mappings().first()

        budget_usd = (
            float(quota_row.get("budget_usd"))
            if quota_row and quota_row.get("budget_usd") is not None
            else None
        )
        quota_mode = quota_row.get("quota_mode") if quota_row else None

        rows = Session.execute(
            text("""
                SELECT
                  u.id AS user_id,
                  u.name AS user_name,
                  u.email AS user_email,
                  COALESCE(SUM(rm.cost_usd), 0) AS spent_usd
                FROM group_member gm
                JOIN "user" u
                  ON u.id = gm.user_id
                LEFT JOIN response_meta rm
                  ON rm.user_id = u.id
                WHERE gm.group_id = :group_id
                GROUP BY u.id, u.name, u.email
                ORDER BY spent_usd DESC, u.name ASC, u.email ASC
            """),
            {"group_id": group_id},
        ).mappings().all()

        users_count = len(rows)

        allocated_usd = None
        if quota_mode == "shared_evenly" and budget_usd is not None:
            allocated_usd = (budget_usd / users_count) if users_count > 0 else 0.0

        items: List[GroupUserQuotaItem] = []
        for row in rows:
            items.append(
                GroupUserQuotaItem(
                    userId=row["user_id"],
                    name=row.get("user_name") or row.get("user_email") or row["user_id"],
                    email=row.get("user_email"),
                    allocatedUsd=round(allocated_usd, 2) if allocated_usd is not None else None,
                    spentUsd=round(float(row.get("spent_usd") or 0.0), 6),
                )
            )

        return items

    except HTTPException:
        raise
    except Exception as e:
        log.exception("Failed to load group users quota for %s: %s", group_id, e)
        raise HTTPException(
            status_code=500,
            detail="Не удалось загрузить пользователей группы",
        )
    

@router.patch(
    "/quotas/groups/{group_id}",
    response_model=QuotaMonitoringItem,
    summary="Update group quota",
)
async def update_group_quota(
    group_id: str,
    form: UpdateGroupQuotaForm,
    user=Depends(get_verified_user),
) -> QuotaMonitoringItem:
    try:
        group_query = text("""
            SELECT id, name
            FROM "group"
            WHERE id = :group_id
            LIMIT 1
        """)
        group_row = Session.execute(group_query, {"group_id": group_id}).mappings().first()

        if not group_row:
            raise HTTPException(status_code=404, detail="Группа не найдена")

        upsert_query = text("""
            INSERT INTO quotas (
              scope_type,
              scope_id,
              scope_name,
              budget_usd,
              warning_percent,
              is_active,
              quota_mode
            )
            VALUES (
              'group',
              :group_id,
              :scope_name,
              :budget_usd,
              COALESCE(
                (
                  SELECT warning_percent
                  FROM quotas
                  WHERE scope_type = 'group' AND scope_id = :group_id
                  LIMIT 1
                ),
                80.0
              ),
              :is_active,
              :quota_mode
            )
            ON CONFLICT(scope_type, scope_id)
            DO UPDATE SET
              scope_name = excluded.scope_name,
              budget_usd = excluded.budget_usd,
              is_active = excluded.is_active,
              quota_mode = excluded.quota_mode
        """)

        Session.execute(
            upsert_query,
            {
                "group_id": group_id,
                "scope_name": group_row["name"],
                "budget_usd": form.budget_usd,
                "is_active": form.is_active,
                "quota_mode": form.quota_mode,
            },
        )
        Session.commit()

        quota_query = text("""
            SELECT
              q.scope_name,
              q.budget_usd,
              q.warning_percent,
              q.is_active,
              q.quota_mode
            FROM quotas q
            WHERE q.scope_type = 'group' AND q.scope_id = :group_id
            LIMIT 1
        """)
        quota_row = Session.execute(quota_query, {"group_id": group_id}).mappings().first()

        spent_query = text("""
            SELECT COALESCE(SUM(rm.cost_usd), 0) AS spent_usd
            FROM "group" g
            LEFT JOIN group_member gm
              ON gm.group_id = g.id
            LEFT JOIN "user" u
              ON u.id = gm.user_id
            LEFT JOIN response_meta rm
              ON rm.user_id = u.id
            WHERE g.id = :group_id
        """)
        spent_row = Session.execute(spent_query, {"group_id": group_id}).mappings().first()
        spent_usd = float(spent_row.get("spent_usd") or 0.0)

        users_count_query = text("""
            SELECT COUNT(DISTINCT gm.user_id) AS users_count
            FROM group_member gm
            WHERE gm.group_id = :group_id
        """)
        users_count_row = Session.execute(users_count_query, {"group_id": group_id}).mappings().first()
        users_count = int(users_count_row.get("users_count") or 0)

        budget_usd = float(quota_row.get("budget_usd")) if quota_row.get("budget_usd") is not None else None
        warning_percent = (
            float(quota_row.get("warning_percent")) if quota_row.get("warning_percent") is not None else 80.0
        )
        is_active = bool(quota_row.get("is_active")) if quota_row.get("is_active") is not None else True
        quota_mode = quota_row.get("quota_mode") or "shared_evenly"

        per_user_budget_usd = None
        if budget_usd is not None and quota_mode == "shared_evenly":
            per_user_budget_usd = (budget_usd / users_count) if users_count > 0 else 0.0

        remaining_usd = None if budget_usd is None else budget_usd - spent_usd
        spent_percent = (
            None
            if budget_usd is None
            else (spent_usd / budget_usd * 100.0 if budget_usd > 0 else 0.0)
        )

        return QuotaMonitoringItem(
            scopeType="group",
            scopeId=group_id,
            scopeName=quota_row.get("scope_name") or group_row["name"] or group_id,
            budgetUsd=_safe_round(budget_usd, 2),
            spentUsd=round(spent_usd, 6),
            remainingUsd=_safe_round(remaining_usd, 6),
            spentPercent=_safe_round(spent_percent, 2),
            warningPercent=warning_percent,
            isActive=is_active,
            quotaMode=quota_mode,
            usersCount=users_count,
            perUserBudgetUsd=_safe_round(per_user_budget_usd, 2),
            status=_calc_status(budget_usd, spent_percent, warning_percent, is_active),
        )

    except HTTPException:
        raise
    except Exception as e:
        Session.rollback()
        log.exception("Failed to update group quota %s: %s", group_id, e)
        raise HTTPException(status_code=500, detail="Не удалось сохранить квоту группы")