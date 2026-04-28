import json
import os
from dataclasses import dataclass
from typing import Any, Optional

import httpx
from sqlalchemy import text

from open_webui.internal.db import Session


def _safe_json(obj: Any) -> str:
	try:
		return json.dumps(obj, ensure_ascii=False)
	except Exception:
		return '{"_error":"failed_to_json"}'


@dataclass
class SanitizeResult:
	raw_text: Optional[str]
	masked_text: Optional[str]
	has_pii: int
	policy_id: Optional[str]
	detector_version: Optional[str]
	updated_payload: dict
	is_user_input: bool


def _extract_last_user_message(payload: dict) -> tuple[int | None, object | None]:
	msgs = payload.get("messages")
	if not isinstance(msgs, list):
		return None, None

	for i in range(len(msgs) - 1, -1, -1):
		m = msgs[i]
		if not isinstance(m, dict):
			continue
		if m.get("role") != "user":
			continue
		if m.get("_is_background_prompt") is True:
			continue
		return i, m.get("content")

	return None, None


def _content_to_text(content: Any) -> Optional[str]:
	if content is None:
		return None

	if isinstance(content, str):
		return content

	if isinstance(content, list):
		parts = []
		for p in content:
			if isinstance(p, dict):
				t = p.get("text")
				if p.get("type") in ("text", "input_text") and isinstance(t, str):
					parts.append(t)

		return "\n".join(parts) if parts else None

	return str(content)


def _is_background_prompt(text: str) -> bool:
	return text.startswith("### Task:") or "<chat_history>" in text


def is_real_user_message(m: dict) -> bool:
	return m.get("role") == "user" and not m.get("_is_background_prompt", False)


def _extract_last_non_background_user_message(payload: dict):
	msgs = payload.get("messages")
	if not isinstance(msgs, list):
		return None, None

	for i in range(len(msgs) - 1, -1, -1):
		m = msgs[i]
		if not isinstance(m, dict) or m.get("role") != "user":
			continue

		content = m.get("content")
		text_value = _content_to_text(content)

		if isinstance(text_value, str) and text_value.strip() and not _is_background_prompt(text_value):
			return i, content

	return None, None


async def sanitize_payload_last_user_message(payload: dict) -> SanitizeResult:
	updated = dict(payload)
	idx, raw_content = _extract_last_user_message(updated)
	raw_text = _content_to_text(raw_content)

	if idx is None or not isinstance(raw_text, str) or not raw_text.strip():
		return SanitizeResult(
			raw_text=None,
			masked_text=None,
			has_pii=0,
			policy_id=None,
			detector_version=None,
			updated_payload=updated,
			is_user_input=False,
		)

	if _is_background_prompt(raw_text):
		return SanitizeResult(
			raw_text=None,
			masked_text=None,
			has_pii=0,
			policy_id=None,
			detector_version=None,
			updated_payload=updated,
			is_user_input=False,
		)

	policy_id = os.getenv("SANITIZER_POLICY", "default")
	sanitizer_url = os.getenv("SANITIZER_URL", "").strip()

	masked_text = raw_text
	has_pii = 0
	detector_version = None

	if sanitizer_url:
		try:
			async with httpx.AsyncClient(timeout=5.0) as client:
				resp = await client.post(
					sanitizer_url,
					json={"text": raw_text, "policy_id": policy_id},
				)
				resp.raise_for_status()
				data = resp.json() if resp.content else {}

			masked_text = data.get("masked_text", raw_text)
			has_pii = int(data.get("has_pii", 0) or 0)
			policy_id = data.get("policy_id", policy_id)
			detector_version = data.get("detector_version")
		except Exception:
			masked_text = raw_text
			has_pii = 0
			detector_version = None

	try:
		msgs = updated.get("messages")
		if isinstance(msgs, list) and idx < len(msgs) and isinstance(masked_text, str):
			if isinstance(msgs[idx].get("content"), list):
				msgs[idx]["content"] = [{"type": "text", "text": masked_text}]
			else:
				msgs[idx]["content"] = masked_text
	except Exception:
		updated = dict(payload)
		masked_text = raw_text
		has_pii = 0

	if isinstance(raw_text, str) and len(raw_text) > 100_000:
		raw_text = raw_text[:100_000] + "...TRUNCATED"

	if isinstance(masked_text, str) and len(masked_text) > 100_000:
		masked_text = masked_text[:100_000] + "...TRUNCATED"

	return SanitizeResult(
		raw_text=raw_text,
		masked_text=masked_text,
		has_pii=1 if has_pii else 0,
		policy_id=policy_id,
		detector_version=detector_version,
		updated_payload=updated,
		is_user_input=True,
	)


def sanitize_text_for_audit_sync(text: str) -> tuple[str, int, str, Optional[str]]:
	policy_id = os.getenv("SANITIZER_POLICY", "default")
	sanitizer_url = os.getenv("SANITIZER_URL", "").strip()

	raw_text = text or ""
	if not isinstance(raw_text, str):
		raw_text = str(raw_text)

	masked_text = raw_text
	has_pii = 0
	detector_version = None

	if sanitizer_url:
		try:
			with httpx.Client(timeout=5.0) as client:
				resp = client.post(
					sanitizer_url,
					json={"text": raw_text, "policy_id": policy_id},
				)
				resp.raise_for_status()
				data = resp.json() if resp.content else {}

			masked_text = data.get("masked_text", raw_text)
			has_pii = int(data.get("has_pii", 0) or 0)
			policy_id = data.get("policy_id", policy_id)
			detector_version = data.get("detector_version")
		except Exception:
			masked_text = raw_text
			has_pii = 0
			detector_version = None

	if len(raw_text) > 100_000:
		raw_text = raw_text[:100_000] + "...TRUNCATED"

	if isinstance(masked_text, str) and len(masked_text) > 100_000:
		masked_text = masked_text[:100_000] + "...TRUNCATED"

	return masked_text, 1 if has_pii else 0, policy_id, detector_version


@dataclass
class LLMResponseMeta:
	user_id: Optional[str]
	session_id: Optional[str]
	conversation_id: Optional[str]
	message_id: Optional[str]

	provider: Optional[str]
	model: Optional[str]
	request_id: Optional[str]
	upstream_id: Optional[str]

	prompt_tokens: Optional[int]
	completion_tokens: Optional[int]
	total_tokens: Optional[int]
	latency_ms: Optional[int]
	cost_usd: Optional[float]

	meta_json: Optional[dict]


def update_response_meta_usage(
	*,
	response_meta_id: str,
	prompt_tokens: Optional[int],
	completion_tokens: Optional[int],
	total_tokens: Optional[int],
	cost_usd: Optional[float],
	usage_details: Optional[dict] = None,
	latency_ms: Optional[int] = None,
) -> None:
	try:
		meta_json = None

		if usage_details is not None:
			row = Session.execute(
				text("SELECT meta_json FROM response_meta WHERE id = :id"),
				{"id": int(response_meta_id)},
			).mappings().first()

			meta = {}
			if row and row.get("meta_json"):
				try:
					meta = row["meta_json"]
					if isinstance(meta, str):
						meta = json.loads(meta)
				except Exception:
					meta = {}

			meta["usage_details"] = usage_details
			meta_json = _safe_json(meta)

		if meta_json is not None:
			Session.execute(
				text("""
					UPDATE response_meta
					SET prompt_tokens = :prompt_tokens,
						completion_tokens = :completion_tokens,
						total_tokens = :total_tokens,
						cost_usd = :cost_usd,
						latency_ms = COALESCE(:latency_ms, latency_ms),
						meta_json = CAST(:meta_json AS JSON)
					WHERE id = :id
				"""),
				{
					"id": int(response_meta_id),
					"prompt_tokens": prompt_tokens or 0,
					"completion_tokens": completion_tokens or 0,
					"total_tokens": total_tokens or 0,
					"cost_usd": cost_usd or 0,
					"latency_ms": latency_ms,
					"meta_json": meta_json,
				},
			)
		else:
			Session.execute(
				text("""
					UPDATE response_meta
					SET prompt_tokens = :prompt_tokens,
						completion_tokens = :completion_tokens,
						total_tokens = :total_tokens,
						cost_usd = :cost_usd,
						latency_ms = COALESCE(:latency_ms, latency_ms)
					WHERE id = :id
				"""),
				{
					"id": int(response_meta_id),
					"prompt_tokens": prompt_tokens or 0,
					"completion_tokens": completion_tokens or 0,
					"total_tokens": total_tokens or 0,
					"cost_usd": cost_usd or 0,
					"latency_ms": latency_ms,
				},
			)

		Session.commit()
	except Exception:
		Session.rollback()
		raise


def insert_audit_rows(
	*,
	response_meta: LLMResponseMeta,
	raw_text: Optional[str],
	masked_text: Optional[str],
	has_pii: int,
	policy_id: Optional[str],
	detector_version: Optional[str],
) -> str:
	try:
		row = Session.execute(
			text("""
				INSERT INTO response_meta (
					created_at,
					user_id, session_id, conversation_id, message_id,
					provider, model, request_id, upstream_id,
					prompt_tokens, completion_tokens, total_tokens,
					latency_ms, cost_usd,
					meta_json
				) VALUES (
					CURRENT_TIMESTAMP,
					:user_id, :session_id, :conversation_id, :message_id,
					:provider, :model, :request_id, :upstream_id,
					:prompt_tokens, :completion_tokens, :total_tokens,
					:latency_ms, :cost_usd,
					CAST(:meta_json AS JSON)
				)
				RETURNING id
			"""),
			{
				"user_id": response_meta.user_id,
				"session_id": response_meta.session_id,
				"conversation_id": response_meta.conversation_id,
				"message_id": response_meta.message_id,
				"provider": response_meta.provider,
				"model": response_meta.model,
				"request_id": response_meta.request_id,
				"upstream_id": response_meta.upstream_id,
				"prompt_tokens": response_meta.prompt_tokens or 0,
				"completion_tokens": response_meta.completion_tokens or 0,
				"total_tokens": response_meta.total_tokens or 0,
				"latency_ms": response_meta.latency_ms,
				"cost_usd": response_meta.cost_usd or 0,
				"meta_json": _safe_json(response_meta.meta_json or {}),
			},
		).mappings().first()

		response_meta_id = str(row["id"])

		if raw_text is not None:
			meta = response_meta.meta_json or {}

			Session.execute(
				text("""
					INSERT INTO request_texts (
						created_at,
						response_meta_id,
						user_id, user_name, user_email, user_role,
						session_id, conversation_id, message_id,
						raw_text, masked_text,
						has_pii,
						policy_id, detector_version
					) VALUES (
						CURRENT_TIMESTAMP,
						:response_meta_id,
						:user_id, :user_name, :user_email, :user_role,
						:session_id, :conversation_id, :message_id,
						:raw_text, :masked_text,
						:has_pii,
						:policy_id, :detector_version
					)
				"""),
				{
					"response_meta_id": response_meta_id,
					"user_id": response_meta.user_id,
					"user_name": meta.get("user_name"),
					"user_email": meta.get("user_email"),
					"user_role": meta.get("user_role"),
					"session_id": response_meta.session_id,
					"conversation_id": response_meta.conversation_id,
					"message_id": response_meta.message_id,
					"raw_text": raw_text,
					"masked_text": masked_text,
					"has_pii": int(has_pii) if has_pii else 0,
					"policy_id": policy_id,
					"detector_version": detector_version,
				},
			)

		Session.commit()
		return response_meta_id

	except Exception:
		Session.rollback()
		raise


def update_response_meta_provider_model(
	*,
	response_meta_id: str,
	provider: Optional[str],
	model: Optional[str],
) -> None:
	try:
		Session.execute(
			text("""
				UPDATE response_meta
				SET provider = COALESCE(:provider, provider),
					model = COALESCE(:model, model)
				WHERE id = :id
			"""),
			{
				"id": int(response_meta_id),
				"provider": provider,
				"model": model,
			},
		)
		Session.commit()
	except Exception:
		Session.rollback()
		raise