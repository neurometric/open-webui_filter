import logging
from collections import deque
from datetime import datetime
from typing import Deque, List, Optional

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from open_webui.env import SRC_LOG_LEVELS
from open_webui.utils.auth import get_verified_user


log = logging.getLogger(__name__)
log.setLevel(SRC_LOG_LEVELS["MAIN"])

router = APIRouter()


class RequestItem(BaseModel):
    time: str
    chatLink: str
    originalText: str
    modifiedText: str


class RequestCreate(BaseModel):
    chatLink: Optional[str] = ""
    originalText: str
    modifiedText: str


MAX_REQUESTS = 10
_request_log: Deque[RequestItem] = deque(maxlen=MAX_REQUESTS)


@router.get(
    "/requests",
    response_model=List[RequestItem],
    summary="Get list of last modification requests",
)
async def get_requests(user=Depends(get_verified_user)) -> List[RequestItem]:
    """
    Returns up to the last 10 modification requests (newest first).
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
    item = RequestItem(
        time=datetime.now().strftime("%H:%M"),
        chatLink=payload.chatLink or "",
        originalText=payload.originalText,
        modifiedText=payload.modifiedText,
    )

    # Newest first
    _request_log.appendleft(item)

    log.debug("Logged modification request for user %s", getattr(user, "id", None))
    return item

