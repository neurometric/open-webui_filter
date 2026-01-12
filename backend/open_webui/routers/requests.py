import logging
from collections import deque
from datetime import datetime
from typing import Deque, List, Optional

from fastapi import APIRouter, Depends
from pydantic import BaseModel
import httpx
from open_webui.env import SRC_LOG_LEVELS
from open_webui.utils.auth import get_verified_user



log = logging.getLogger(__name__)
log.setLevel(SRC_LOG_LEVELS["MAIN"])

router = APIRouter()

NER_MASK_URL = "http://172.31.4.20:8002/mask"

class RequestItem(BaseModel):
    time: str
    chatLink: str
    originalText: str
    modifiedText: str


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
async def get_requests(user=Depends(get_verified_user)) -> List[RequestItem]:
    """
    Returns up to the last 100 modification requests (newest first).
    """
    return list(_request_log)


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

