import os
import re
from typing import Optional, Dict, Any, List, Tuple

import httpx
from fastapi import FastAPI
from pydantic import BaseModel, Field
import logging

# ---------------- API models ----------------

class SanitizeReq(BaseModel):
    text: str = Field(..., description="Raw user input")
    policy_id: Optional[str] = Field(None, description="Policy id (optional)")


class SanitizeResp(BaseModel):
    masked_text: str
    has_pii: int  # 0/1
    policy_id: str
    detector_version: str


# ---------------- ENV config ----------------

def _env_bool(name: str, default: str = "0") -> bool:
    return os.getenv(name, default).strip().lower() in ("1", "true", "yes", "on")


NER_ENABLED = _env_bool("NER_ENABLED", "1")
NER_URL = os.getenv("NER_URL", "http://172.31.4.20:8002/ner").strip()
NER_TIMEOUT_MS = int(os.getenv("NER_TIMEOUT_MS", "2000"))
NER_MIN_SCORE = float(os.getenv("NER_MIN_SCORE", "0.65"))
NER_LABELS = {
    x.strip().upper()
    for x in os.getenv("NER_LABELS", "PER,ORG,LOC,FIRST_NAME,LAST_NAME,MIDDLE_NAME").split(",")
    if x.strip()
}
logging.info(NER_LABELS)

SANITIZER_VERSION = os.getenv("SANITIZER_VERSION", "mvp-0.2").strip()
DEFAULT_POLICY = os.getenv("SANITIZER_POLICY", "default").strip() or "default"


# ---------------- PII regex (MVP) ----------------

EMAIL_RE = re.compile(r"\b[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}\b")
IPV4_RE = re.compile(r"\b(?:(?:25[0-5]|2[0-4]\d|1?\d?\d)\.){3}(?:25[0-5]|2[0-4]\d|1?\d?\d)\b")
CARD_RE = re.compile(r"\b(?:\d[ \-]?){13,19}\b")

PHONE_RE = re.compile(
    r"(?<!\w)("
    r"(?:\+?\d{1,3}[\s\-]?)?"
    r"(?:\(?\d{2,4}\)?[\s\-]?)?"
    r"\d{3}[\s\-]?\d{2}[\s\-]?\d{2,4}"
    r")"
    r"(?!\w)"
)


def _replace_with_counter(text: str, pattern: re.Pattern, tag: str, start_from: int = 0) -> Tuple[str, int, int]:
    """
    Replace matches with <TAG_N> tokens.
    Returns: (new_text, next_counter, replaced_any(0/1))
    """
    counter = start_from
    replaced_any = 0

    def _repl(_m: re.Match) -> str:
        nonlocal counter, replaced_any
        replaced_any = 1
        counter += 1
        return f"<{tag}_{counter}>"

    return pattern.sub(_repl, text), counter, replaced_any


def _apply_regex(text: str, policy_id: str) -> Tuple[str, int]:
    """
    Returns: (masked_text, has_pii(0/1))
    """
    masked = text
    has_pii = 0

    # Counters per type
    email_c = phone_c = ip_c = card_c = 0

    masked, email_c, r = _replace_with_counter(masked, EMAIL_RE, "EMAIL", email_c)
    has_pii |= r

    masked, ip_c, r = _replace_with_counter(masked, IPV4_RE, "IP", ip_c)
    has_pii |= r

    # card guard: only mask if 13-19 digits after cleanup
    def _card_guard(m: re.Match) -> str:
        nonlocal card_c, has_pii
        s = m.group(0)
        digits = re.sub(r"\D", "", s)
        if 13 <= len(digits) <= 19:
            has_pii = 1
            card_c += 1
            return f"<CARD_{card_c}>"
        return s

    masked = CARD_RE.sub(_card_guard, masked)

    # phone guard: 9-15 digits
    def _phone_guard(m: re.Match) -> str:
        nonlocal phone_c, has_pii
        s = m.group(0).strip()
        digits = re.sub(r"\D", "", s)
        if 9 <= len(digits) <= 15:
            has_pii = 1
            phone_c += 1
            return f"<PHONE_{phone_c}>"
        return s

    masked = PHONE_RE.sub(_phone_guard, masked)

    return masked, 1 if has_pii else 0


# ---------------- NER call + masking ----------------

async def _call_ner(text: str) -> Tuple[List[Dict[str, Any]], Optional[str]]:
    """
    Returns: (entities, model_id_or_version)
    Compatible with your NER service: {"entities": [...]}
    """
    if not (NER_ENABLED and NER_URL):
        return [], None

    timeout = httpx.Timeout(NER_TIMEOUT_MS / 1000.0)
    async with httpx.AsyncClient(timeout=timeout) as client:
        r = await client.post(NER_URL, json={"text": text})
        r.raise_for_status()
        data = r.json() if r.content else {}

    entities = data.get("entities") or []
    # Optional fields if you add them later
    model_id = data.get("model_id") or data.get("model") or None
    model_ver = data.get("model_version") or data.get("version") or None
    model_info = model_ver or model_id
    return entities if isinstance(entities, list) else [], model_info


def _mask_ner_entities(text: str, entities: List[Dict[str, Any]]) -> Tuple[str, int]:
    """
    Masks PER/ORG/LOC entities (configurable via NER_LABELS) using start/end offsets.
    Replace token format: <PER_1>, <ORG_1>...
    Returns: (masked_text, has_pii(0/1))
    """
    if not entities:
        return text, 0

    counters: Dict[str, int] = {label: 0 for label in NER_LABELS}
    masked = text
    changed = 0

    # sort from end to start so indices don't shift
    def _key(e: Dict[str, Any]) -> int:
        try:
            return int(e.get("start", -1))
        except Exception:
            return -1

    for ent in sorted(entities, key=_key, reverse=True):
        try:
            label = (ent.get("entity_group") or ent.get("entity") or "").upper()
            score = float(ent.get("score", 0.0))
            start = int(ent.get("start"))
            end = int(ent.get("end"))
        except Exception:
            continue

        if label not in NER_LABELS:
            continue
        if score < NER_MIN_SCORE:
            continue
        if not (0 <= start < end <= len(masked)):
            continue

        counters.setdefault(label, 0)
        counters[label] += 1
        token = f"<{label}_{counters[label]}>"

        masked = masked[:start] + token + masked[end:]
        changed = 1

    return masked, 1 if changed else 0


# ---------------- FastAPI ----------------

app = FastAPI(title="Sanitizer Service", version=SANITIZER_VERSION)


@app.get("/health")
def health():
    return {
        "ok": True,
        "version": SANITIZER_VERSION,
        "ner_enabled": NER_ENABLED,
        "ner_url_set": bool(NER_URL),
        "ner_min_score": NER_MIN_SCORE,
        "ner_labels": sorted(list(NER_LABELS)),
    }


@app.post("/v1/sanitize", response_model=SanitizeResp)
async def sanitize(req: SanitizeReq):
    raw = req.text or ""
    policy_id = (req.policy_id or DEFAULT_POLICY).strip() or DEFAULT_POLICY

    # 1) regex first (fast)
    masked, has_pii = _apply_regex(raw, policy_id)

    # 2) NER second (slower). You can gate it if you want:
    # if has_pii == 0: only then run NER (faster)
    ner_model_info = None
    if NER_ENABLED and NER_URL:
        try:
            entities, ner_model_info = await _call_ner(masked)
            masked2, ner_found = _mask_ner_entities(masked, entities)
            masked = masked2
            has_pii = 1 if (has_pii or ner_found) else 0
        except Exception:
            # MVP: sanitizer should not fail chat because NER failed
            pass

    detector_version = SANITIZER_VERSION
    if ner_model_info:
        detector_version = f"{SANITIZER_VERSION}|ner:{ner_model_info}"

    return SanitizeResp(
        masked_text=masked,
        has_pii=int(has_pii),
        policy_id=policy_id,
        detector_version=detector_version,
    )
