import logging
from collections import deque
from datetime import datetime
from typing import Deque, List, Optional

from fastapi import APIRouter, Depends
from pydantic import BaseModel
import httpx
from sqlalchemy import text
from open_webui.env import SRC_LOG_LEVELS
from open_webui.utils.auth import get_verified_user
from open_webui.internal.db import Session



log = logging.getLogger(__name__)
log.setLevel(SRC_LOG_LEVELS["MAIN"])

router = APIRouter()

NER_MASK_URL = "http://172.31.4.20:8002/mask"

class RequestItem(BaseModel):
    # legacy fields used by the frontend page
    time: str
    chatLink: str
    originalText: str
    modifiedText: str

    # additional fields for Requests tab
    userId: Optional[str] = None
    userName: Optional[str] = None
    userEmail: Optional[str] = None
    userRole: Optional[str] = None
    conversationId: Optional[str] = None
    hasPii: bool = False


class RequestCreate(BaseModel):
    chatLink: Optional[str] = ""
    originalText: str
    modifiedText: str


MAX_REQUESTS = 100
_request_log: Deque[RequestItem] = deque(maxlen=MAX_REQUESTS)


@router.get(
    "/requests",
    response_model=List[RequestItem],
    summary="Get list of last modification requests",
)
async def get_requests(
    page: int = 1,
    query: Optional[str] = None,
    has_pii: Optional[bool] = None,
    user=Depends(get_verified_user),
) -> List[RequestItem]:
    """
    Returns paginated user requests from DB table `request_texts` (newest first).

    - `page` starts from 1
    - 10 records per page
    - optional `query` filter by `user_name` / `user_email` (substring match)
    - optional `has_pii` filter by presence of personal data
    """
    try:
        page = max(page, 1)
        page_size = 10
        offset = (page - 1) * page_size

        base_sql = """
            SELECT
              id,
              created_at,
              user_id,
              user_name,
              user_email,
              user_role,
              conversation_id,
              raw_text,
              masked_text,
              has_pii
            FROM request_texts
        """

        conditions = []
        params: dict = {"limit": page_size, "offset": offset}

        if query:
            conditions.append("(user_name LIKE :search OR user_email LIKE :search)")
            params["search"] = f"%{query}%"

        if has_pii is not None:
            conditions.append("has_pii = :has_pii")
            params["has_pii"] = 1 if has_pii else 0

        if conditions:
            base_sql += " WHERE " + " AND ".join(conditions)

        base_sql += """
            ORDER BY created_at DESC
            LIMIT :limit OFFSET :offset
        """

        rows = Session.execute(
            text(base_sql),
            params,
        ).mappings().all()

        items: List[RequestItem] = []
        for r in rows:
            conversation_id = r.get("conversation_id")
            chat_link = f"/s/{conversation_id}" if conversation_id else ""
            created_at = r.get("created_at")

            items.append(
                RequestItem(
                    time=str(created_at) if created_at is not None else "",
                    chatLink=chat_link,
                    originalText=(r.get("raw_text") or ""),
                    modifiedText=(r.get("masked_text") or ""),
                    userId=r.get("user_id"),
                    userName=r.get("user_name"),
                    userEmail=r.get("user_email"),
                    userRole=r.get("user_role"),
                    conversationId=conversation_id,
                    hasPii=bool(r.get("has_pii") == 1),
                )
            )

        return items
    except Exception as e:
        log.exception("Failed to load request_texts from DB: %s", e)
        # keep response shape stable for the UI
        return []


@router.post(
    "/requests",
    response_model=RequestItem,
    summary="Add a modification request entry",
)
async def add_request(
    payload: RequestCreate,
    user=Depends(get_verified_user),
) -> RequestItem:
    """
    Append a new modification request to the in-memory log.
    This is a lightweight temporary implementation without DB persistence.
    """

    masked_text = payload.modifiedText

    # если modifiedText не передан — маскируем originalText
    
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            resp = await client.post(
                NER_MASK_URL,
                json={"text": payload.originalText},
            )
            resp.raise_for_status()
            data = resp.json()
            masked_text = data.get("masked_text", payload.originalText)
    except Exception as e:
        log.warning("NER mask service failed: %s", e)
        masked_text = payload.originalText  # fallback

    item = RequestItem(
        time=datetime.now().strftime("%H:%M"),
        chatLink=payload.chatLink or "",
        originalText=payload.originalText,
        modifiedText=masked_text,
    )

    _request_log.appendleft(item)

    log.debug(
        "Logged modification request for user %s",
        getattr(user, "id", None),
    )
    return item

