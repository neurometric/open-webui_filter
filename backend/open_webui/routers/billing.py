import logging
from typing import List, Optional
from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy import text
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
    user=Depends(get_verified_user),
) -> List[BillingItem]:
    """
    Returns paginated billing records from response_meta table.
    
    - `page` starts from 1
    - 10 records per page
    - `date_from` and `date_to` for date range filter (format: YYYY-MM-DD or YYYY-MM-DD HH:MM:SS)
    - `order_by`: prompt_tokens, completion_tokens, cost_usd, latency_ms
    - `order_dir`: asc or desc
    """
    try:
        page = max(page, 1)
        page_size = 10
        offset = (page - 1) * page_size

        # Build WHERE clause for date filtering
        where_clauses = []
        params = {"limit": page_size, "offset": offset}
        
        if date_from:
            where_clauses.append("datetime(created_at) >= datetime(:date_from)")
            params["date_from"] = date_from
        
        if date_to:
            where_clauses.append("datetime(created_at) <= datetime(:date_to)")
            params["date_to"] = date_to
        
        where_sql = ""
        if where_clauses:
            where_sql = "WHERE " + " AND ".join(where_clauses)
        
        # Build ORDER BY clause
        valid_order_fields = {
            "prompt_tokens": "prompt_tokens",
            "completion_tokens": "completion_tokens",
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

        rows = Session.execute(text(query), params).mappings().all()

        items: List[BillingItem] = []
        for r in rows:
            created_at = r.get("created_at")
            meta_json_str = r.get("meta_json")
            
            # Parse meta_json to extract user_name and user_email
            user_name = None
            user_email = None
            if meta_json_str:
                try:
                    import json
                    meta = json.loads(meta_json_str)
                    user_name = meta.get("user_name")
                    user_email = meta.get("user_email")
                except Exception:
                    pass

            items.append(
                BillingItem(
                    createdAt=str(created_at) if created_at else "",
                    userId=r.get("user_id"),
                    userName=user_name,
                    userEmail=user_email,
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

