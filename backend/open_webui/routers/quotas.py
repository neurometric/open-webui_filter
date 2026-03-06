import logging
from typing import List, Optional

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
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
    scopeType: str  # company | group
    scopeId: str
    scopeName: str

    budgetUsd: Optional[float] = None
    spentUsd: Optional[float] = None
    remainingUsd: Optional[float] = None
    spentPercent: Optional[float] = None

    warningPercent: Optional[float] = None
    isActive: bool = True
    status: str  # ok | warning | exceeded | disabled | no_quota


def _build_where(date_from: Optional[str], date_to: Optional[str]):
    where_clauses = []
    params = {}

    if date_from:
        where_clauses.append("datetime(rm.created_at) >= datetime(:date_from)")
        params["date_from"] = date_from

    if date_to:
        where_clauses.append("datetime(rm.created_at) <= datetime(:date_to)")
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
        # company quota
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

        budget_usd = float(quota_row.get("budget_usd")) if quota_row and quota_row.get("budget_usd") is not None else None

        where_sql, params = _build_where(date_from, date_to)

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

        # --- company row ---
        company_quota_query = text("""
            SELECT
              scope_type,
              scope_id,
              scope_name,
              budget_usd,
              warning_percent,
              is_active
            FROM quotas
            WHERE scope_type = 'company' AND scope_id = 'company'
            LIMIT 1
        """)
        company_quota = Session.execute(company_quota_query).mappings().first()

        where_sql, params = _build_where(date_from, date_to)

        company_spent_query = text(f"""
            SELECT COALESCE(SUM(rm.cost_usd), 0) AS spent_usd
            FROM response_meta rm
            {where_sql}
        """)
        company_spent_row = Session.execute(company_spent_query, params).mappings().first()
        company_spent = float(company_spent_row.get("spent_usd") or 0.0)

        company_budget = float(company_quota.get("budget_usd")) if company_quota and company_quota.get("budget_usd") is not None else None
        company_warning = float(company_quota.get("warning_percent")) if company_quota and company_quota.get("warning_percent") is not None else 80.0
        company_active = bool(company_quota.get("is_active")) if company_quota else True

        company_remaining = None if company_budget is None else company_budget - company_spent
        company_percent = None if company_budget is None else (company_spent / company_budget * 100.0 if company_budget > 0 else 0.0)

        items.append(
            QuotaMonitoringItem(
                scopeType="company",
                scopeId="company",
                scopeName=(company_quota.get("scope_name") if company_quota else "Вся компания"),
                budgetUsd=round(company_budget, 2) if company_budget is not None else None,
                spentUsd=round(company_spent, 6),
                remainingUsd=round(company_remaining, 6) if company_remaining is not None else None,
                spentPercent=round(company_percent, 2) if company_percent is not None else None,
                warningPercent=company_warning,
                isActive=company_active,
                status=_calc_status(company_budget, company_percent, company_warning, company_active),
            )
        )

        # --- groups rows ---
        group_filter_sql = ""
        group_params = dict(params)

        safe_group_ids = [g.strip() for g in (group_ids or []) if g and g.strip()]
        if safe_group_ids:
            group_filter_sql = "WHERE g.id IN :group_ids"
            group_params["group_ids"] = safe_group_ids

        groups_and_quotas_query = text(f"""
            SELECT
              g.id AS group_id,
              g.name AS group_name,
              q.budget_usd AS budget_usd,
              q.warning_percent AS warning_percent,
              q.is_active AS is_active
            FROM "group" g
            LEFT JOIN quotas q
              ON q.scope_type = 'group'
             AND q.scope_id = g.id
            {group_filter_sql}
            ORDER BY g.name ASC
        """)
        if safe_group_ids:
            group_spent_query = group_spent_query.bindparams(
                bindparam("group_ids", expanding=True)
            )

        groups_rows = Session.execute(groups_and_quotas_query, group_params).mappings().all()

        group_spent_filter_sql, group_spent_params = _build_where(date_from, date_to)
        group_spent_extra = ""
        if safe_group_ids:
            prefix = "AND" if group_spent_filter_sql else "WHERE"
            group_spent_extra = f" {prefix} g.id IN :group_ids"
            group_spent_params["group_ids"] = safe_group_ids

        group_spent_query = text(f"""
            SELECT
              g.id AS group_id,
              COALESCE(SUM(rm.cost_usd), 0) AS spent_usd
            FROM "group" g
            LEFT JOIN group_member gm
              ON gm.group_id = g.id
            LEFT JOIN user u
              ON u.id = gm.user_id
            LEFT JOIN response_meta rm
              ON rm.user_id = u.id
            {group_spent_filter_sql}
            {group_spent_extra}
            GROUP BY g.id
        """)
        if safe_group_ids:
            group_spent_query = group_spent_query.bindparams(
                __import__("sqlalchemy").bindparam("group_ids", expanding=True)
            )

        spent_rows = Session.execute(group_spent_query, group_spent_params).mappings().all()
        spent_map = {row["group_id"]: float(row.get("spent_usd") or 0.0) for row in spent_rows}

        for row in groups_rows:
            group_id = row["group_id"]
            spent_usd = spent_map.get(group_id, 0.0)

            budget_usd = float(row.get("budget_usd")) if row.get("budget_usd") is not None else None
            warning_percent = float(row.get("warning_percent")) if row.get("warning_percent") is not None else 80.0
            is_active = bool(row.get("is_active")) if row.get("is_active") is not None else True

            remaining_usd = None if budget_usd is None else budget_usd - spent_usd
            spent_percent = None if budget_usd is None else (spent_usd / budget_usd * 100.0 if budget_usd > 0 else 0.0)

            items.append(
                QuotaMonitoringItem(
                    scopeType="group",
                    scopeId=group_id,
                    scopeName=row.get("group_name") or group_id,
                    budgetUsd=round(budget_usd, 2) if budget_usd is not None else None,
                    spentUsd=round(spent_usd, 6),
                    remainingUsd=round(remaining_usd, 6) if remaining_usd is not None else None,
                    spentPercent=round(spent_percent, 2) if spent_percent is not None else None,
                    warningPercent=warning_percent,
                    isActive=is_active,
                    status=_calc_status(budget_usd, spent_percent, warning_percent, is_active),
                )
            )

        return items

    except Exception as e:
        log.exception("Failed to load quotas monitoring: %s", e)
        return []