import logging
import json
import csv
import io
from fastapi.responses import StreamingResponse
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


class BillingItem(BaseModel):
    createdAt: str
    userId: Optional[str] = None
    userName: Optional[str] = None
    userEmail: Optional[str] = None
    provider: Optional[str] = None
    model: Optional[str] = None
    promptTokens: Optional[int] = None
    completionTokens: Optional[int] = None
    totalTokens: Optional[int] = None
    costUsd: Optional[float] = None
    latencyMs: Optional[int] = None


class BillingOptions(BaseModel):
    models: List[str]
    userNames: List[str]


def _safe_list(values: Optional[List[str]]) -> List[str]:
    if not values:
        return []
    return [v.strip() for v in values if v and v.strip()]


def _build_where(
    date_from: Optional[str],
    date_to: Optional[str],
    models: Optional[List[str]],
    user_names: Optional[List[str]],
):
    where_clauses = []
    params = {}

    if date_from:
        where_clauses.append("datetime(created_at) >= datetime(:date_from)")
        params["date_from"] = date_from

    if date_to:
        where_clauses.append("datetime(created_at) <= datetime(:date_to)")
        params["date_to"] = date_to

    safe_models = _safe_list(models)
    if safe_models:
        where_clauses.append("model IN :models")
        params["models"] = safe_models

    safe_user_names = _safe_list(user_names)
    if safe_user_names:
        where_clauses.append("json_extract(meta_json, '$.user_name') IN :user_names")
        params["user_names"] = safe_user_names

    where_sql = ("WHERE " + " AND ".join(where_clauses)) if where_clauses else ""
    return where_sql, params


def _build_where_for_options(
    date_from: Optional[str],
    date_to: Optional[str],
    models: Optional[List[str]],
    user_names: Optional[List[str]],
    include_models: bool,
    include_user_names: bool,
):
    where_clauses = []
    params = {}

    if date_from:
        where_clauses.append("datetime(created_at) >= datetime(:date_from)")
        params["date_from"] = date_from

    if date_to:
        where_clauses.append("datetime(created_at) <= datetime(:date_to)")
        params["date_to"] = date_to

    if include_models:
        safe_models = _safe_list(models)
        if safe_models:
            where_clauses.append("model IN :models")
            params["models"] = safe_models

    if include_user_names:
        safe_user_names = _safe_list(user_names)
        if safe_user_names:
            where_clauses.append("json_extract(meta_json, '$.user_name') IN :user_names")
            params["user_names"] = safe_user_names

    where_sql = ("WHERE " + " AND ".join(where_clauses)) if where_clauses else ""
    return where_sql, params


@router.get(
    "/billing",
    response_model=List[BillingItem],
    summary="Get billing records from response_meta",
)
async def get_billing(
    page: int = 1,
    date_from: Optional[str] = None,
    date_to: Optional[str] = None,
    order_by: Optional[str] = None,
    order_dir: Optional[str] = None,
    models: Optional[List[str]] = Query(default=None),        # models=a&models=b
    user_names: Optional[List[str]] = Query(default=None),    # user_names=u1&user_names=u2
    user=Depends(get_verified_user),
) -> List[BillingItem]:
    """
    Returns paginated billing records from response_meta table.

    - page starts from 1
    - 10 records per page
    - date_from/date_to filters
    - order_by: prompt_tokens, completion_tokens, total_tokens, cost_usd, latency_ms
    - order_dir: asc or desc
    - models: multi model filter
    - user_names: multi user_name filter (from meta_json)
    """
    try:
        page = max(page, 1)
        page_size = 10
        offset = (page - 1) * page_size

        where_sql, where_params = _build_where(date_from, date_to, models, user_names)
        params = {"limit": page_size, "offset": offset, **where_params}

        valid_order_fields = {
            "prompt_tokens": "prompt_tokens",
            "completion_tokens": "completion_tokens",
            "total_tokens": "total_tokens",
            "cost_usd": "cost_usd",
            "latency_ms": "latency_ms",
        }

        order_sql = "ORDER BY datetime(created_at) DESC"
        if order_by and order_by in valid_order_fields:
            direction = "ASC" if order_dir == "asc" else "DESC"
            order_sql = f"ORDER BY {valid_order_fields[order_by]} {direction}"

        query = f"""
            SELECT
              created_at,
              user_id,
              provider,
              model,
              prompt_tokens,
              completion_tokens,
              total_tokens,
              cost_usd,
              latency_ms,
              meta_json
            FROM response_meta
            {where_sql}
            {order_sql}
            LIMIT :limit OFFSET :offset
        """

        stmt = text(query)
        if "models" in params:
            stmt = stmt.bindparams(bindparam("models", expanding=True))
        if "user_names" in params:
            stmt = stmt.bindparams(bindparam("user_names", expanding=True))

        rows = Session.execute(stmt, params).mappings().all()

        items: List[BillingItem] = []
        for r in rows:
            created_at = r.get("created_at")
            meta_json_str = r.get("meta_json")

            user_name_val = None
            user_email_val = None
            if meta_json_str:
                try:
                    meta = json.loads(meta_json_str)
                    user_name_val = meta.get("user_name")
                    user_email_val = meta.get("user_email")
                except Exception:
                    pass

            items.append(
                BillingItem(
                    createdAt=str(created_at) if created_at else "",
                    userId=r.get("user_id"),
                    userName=user_name_val,
                    userEmail=user_email_val,
                    provider=r.get("provider"),
                    model=r.get("model"),
                    promptTokens=r.get("prompt_tokens"),
                    completionTokens=r.get("completion_tokens"),
                    totalTokens=r.get("total_tokens"),
                    costUsd=r.get("cost_usd"),
                    latencyMs=r.get("latency_ms"),
                )
            )

        return items
    except Exception as e:
        log.exception("Failed to load billing data from DB: %s", e)
        return []


@router.get(
    "/billing/options",
    response_model=BillingOptions,
    summary="Get distinct models and userNames for billing filters (no pagination)",
)
async def get_billing_options(
    date_from: Optional[str] = None,
    date_to: Optional[str] = None,
    models: Optional[List[str]] = Query(default=None),
    user_names: Optional[List[str]] = Query(default=None),
    user=Depends(get_verified_user),
) -> BillingOptions:
    """
    Возвращает уникальные models и userNames без пагинации.

    Facet логика:
    - models: зависит от date_* + user_names, но НЕ зависит от models
    - userNames: зависит от date_* + models, но НЕ зависит от user_names
    """
    try:
        # models list: include user_names, exclude models
        where_models_sql, params_models = _build_where_for_options(
            date_from=date_from,
            date_to=date_to,
            models=models,
            user_names=user_names,
            include_models=False,
            include_user_names=True,
        )

        # userNames list: include models, exclude user_names
        where_users_sql, params_users = _build_where_for_options(
            date_from=date_from,
            date_to=date_to,
            models=models,
            user_names=user_names,
            include_models=True,
            include_user_names=False,
        )

        q_models = f"""
            SELECT DISTINCT model AS value
            FROM response_meta
            {where_models_sql}
            {"AND" if where_models_sql else "WHERE"} model IS NOT NULL AND trim(model) != ''
            ORDER BY value ASC
        """

        q_users = f"""
            SELECT DISTINCT json_extract(meta_json, '$.user_name') AS value
            FROM response_meta
            {where_users_sql}
            {"AND" if where_users_sql else "WHERE"} json_extract(meta_json, '$.user_name') IS NOT NULL
              AND trim(json_extract(meta_json, '$.user_name')) != ''
            ORDER BY value ASC
        """

        stmt_models = text(q_models)
        if "models" in params_models:
            stmt_models = stmt_models.bindparams(bindparam("models", expanding=True))
        if "user_names" in params_models:
            stmt_models = stmt_models.bindparams(bindparam("user_names", expanding=True))

        stmt_users = text(q_users)
        if "models" in params_users:
            stmt_users = stmt_users.bindparams(bindparam("models", expanding=True))
        if "user_names" in params_users:
            stmt_users = stmt_users.bindparams(bindparam("user_names", expanding=True))

        models_rows = Session.execute(stmt_models, params_models).mappings().all()
        users_rows = Session.execute(stmt_users, params_users).mappings().all()

        models_list = sorted({(r.get("value") or "").strip() for r in models_rows if (r.get("value") or "").strip()})
        users_list = sorted({(r.get("value") or "").strip() for r in users_rows if (r.get("value") or "").strip()})

        return BillingOptions(models=models_list, userNames=users_list)
    except Exception as e:
        log.exception("Failed to load billing options: %s", e)
        return BillingOptions(models=[], userNames=[])


@router.get(
    "/billing/export",
    summary="Export billing records from response_meta to CSV (filters applied, no pagination)",
)
async def export_billing_csv(
    date_from: Optional[str] = None,
    date_to: Optional[str] = None,
    order_by: Optional[str] = None,
    order_dir: Optional[str] = None,
    models: Optional[List[str]] = Query(default=None),        # models=a&models=b
    user_names: Optional[List[str]] = Query(default=None),    # user_names=u1&user_names=u2
    user=Depends(get_verified_user),
):
    """
    Экспорт CSV со всеми строками, подходящими под фильтры (без пагинации).
    Фильтры совпадают с /billing:
    - date_from/date_to
    - order_by/order_dir
    - models (multi)
    - user_names (multi, meta_json.user_name)
    """
    try:
        where_sql, where_params = _build_where(date_from, date_to, models, user_names)
        params = {**where_params}

        valid_order_fields = {
            "prompt_tokens": "prompt_tokens",
            "completion_tokens": "completion_tokens",
            "total_tokens": "total_tokens",
            "cost_usd": "cost_usd",
            "latency_ms": "latency_ms",
        }

        order_sql = "ORDER BY datetime(created_at) DESC"
        if order_by and order_by in valid_order_fields:
            direction = "ASC" if order_dir == "asc" else "DESC"
            order_sql = f"ORDER BY {valid_order_fields[order_by]} {direction}"

        query = f"""
            SELECT
              created_at,
              user_id,
              provider,
              model,
              prompt_tokens,
              completion_tokens,
              total_tokens,
              cost_usd,
              latency_ms,
              meta_json
            FROM response_meta
            {where_sql}
            {order_sql}
        """

        stmt = text(query)
        if "models" in params:
            stmt = stmt.bindparams(bindparam("models", expanding=True))
        if "user_names" in params:
            stmt = stmt.bindparams(bindparam("user_names", expanding=True))

        rows = Session.execute(stmt, params).mappings().all()

        def iter_csv():
            buf = io.StringIO()
            w = csv.writer(buf)

            # BOM для Excel
            yield "\ufeff".encode("utf-8")

            w.writerow([
                "createdAt",
                "userId",
                "userName",
                "userEmail",
                "provider",
                "model",
                "promptTokens",
                "completionTokens",
                "totalTokens",
                "costUsd",
                "latencyMs",
            ])
            yield buf.getvalue().encode("utf-8")
            buf.seek(0); buf.truncate(0)

            for r in rows:
                meta_json_str = r.get("meta_json")
                user_name_val = None
                user_email_val = None
                if meta_json_str:
                    try:
                        meta = json.loads(meta_json_str)
                        user_name_val = meta.get("user_name")
                        user_email_val = meta.get("user_email")
                    except Exception:
                        pass

                w.writerow([
                    str(r.get("created_at") or ""),
                    r.get("user_id"),
                    user_name_val or "",
                    user_email_val or "",
                    r.get("provider") or "",
                    r.get("model") or "",
                    r.get("prompt_tokens") if r.get("prompt_tokens") is not None else "",
                    r.get("completion_tokens") if r.get("completion_tokens") is not None else "",
                    r.get("total_tokens") if r.get("total_tokens") is not None else "",
                    r.get("cost_usd") if r.get("cost_usd") is not None else "",
                    r.get("latency_ms") if r.get("latency_ms") is not None else "",
                ])

                yield buf.getvalue().encode("utf-8")
                buf.seek(0); buf.truncate(0)

        headers = {"Content-Disposition": 'attachment; filename="billing.csv"'}
        return StreamingResponse(iter_csv(), media_type="text/csv; charset=utf-8", headers=headers)

    except Exception as e:
        log.exception("Failed to export billing csv: %s", e)
        headers = {"Content-Disposition": 'attachment; filename="billing.csv"'}
        return StreamingResponse(iter([b"\ufeffcreatedAt\n"]), media_type="text/csv; charset=utf-8", headers=headers)
