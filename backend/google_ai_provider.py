"""Server-side OpenRouter provider for Research Nexus.

This module is the only layer that knows about the OpenRouter HTTP API. The
rest of the application calls it through provider-neutral helpers.
"""

import logging
import os
import random
from typing import Any, Dict, List, Optional

import httpx

logger = logging.getLogger(__name__)

OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1"
DEFAULT_MODEL = "google/gemma-4-31b-it"
MAX_DOCUMENT_CHARS = 40_000
_last_provider_error = ""
_last_model_used = ""


def get_ai_provider() -> str:
    return os.getenv("AI_PROVIDER", "openrouter").strip().lower() or "openrouter"


def get_openrouter_api_key() -> str:
    return os.getenv("OPENROUTER_API_KEY", "").strip()


def get_last_provider_error() -> str:
    return _last_provider_error


def get_last_model_used() -> str:
    """Return the model name that last produced a successful response."""
    return _last_model_used


def is_openrouter_configured() -> bool:
    return bool(get_openrouter_api_key())


def is_google_ai_configured() -> bool:
    return is_openrouter_configured()


def get_model_name() -> str:
    return os.getenv("AI_MODEL", DEFAULT_MODEL).strip() or DEFAULT_MODEL


def _fetch_available_models() -> list:
    key = get_openrouter_api_key()
    if not key:
        return []

    try:
        headers = {
            "Authorization": f"Bearer {key}",
            "HTTP-Referer": "https://localhost",
            "X-Title": "Research Nexus",
        }
        with httpx.Client(timeout=15.0) as client:
            response = client.get(f"{OPENROUTER_BASE_URL}/models", headers=headers)
            response.raise_for_status()
            data = response.json()
        models = data.get("data", []) if isinstance(data, dict) else []
        ids = []
        for model in models:
            if not isinstance(model, dict):
                continue
            model_id = model.get("id") or model.get("slug") or model.get("name")
            if model_id:
                ids.append(str(model_id))
        return ids
    except Exception as exc:
        logger.debug("OpenRouter model listing failed: %s", exc)
        return []


_models_cache: list = []
_models_cache_ts: float = 0.0
_CACHE_TTL_SEC = 300


def list_available_models() -> list:
    import time

    global _models_cache, _models_cache_ts
    now = time.time()
    if _models_cache and (now - _models_cache_ts) < _CACHE_TTL_SEC:
        return _models_cache
    models = _fetch_available_models()
    _models_cache = models
    _models_cache_ts = now
    return models


def is_google_api_key_valid() -> bool:
    try:
        return bool(list_available_models())
    except Exception:
        return False


def is_google_ai_model_supported() -> bool:
    return bool(get_model_name().strip()) and get_ai_provider() == "openrouter"


def _get_free_fallback_models() -> List[str]:
    """Return cached free models (ending in :free) excluding the primary model."""
    primary = get_model_name()
    try:
        all_models = list_available_models()
    except Exception:
        all_models = []
    free_models = [
        m for m in all_models
        if isinstance(m, str) and m.endswith(":free") and m != primary
    ]
    random.shuffle(free_models)
    return free_models


def generate_text(
    system_instruction: str,
    user_content: str,
    response_schema: Optional[Dict[str, Any]] = None,
) -> Optional[str]:
    global _last_provider_error, _last_model_used
    _last_provider_error = ""

    provider = get_ai_provider()
    if provider != "openrouter":
        _last_provider_error = f"AI_PROVIDER is set to '{provider}', but this backend only supports the OpenRouter provider."
        return None

    api_key = get_openrouter_api_key()
    if not api_key:
        _last_provider_error = "OPENROUTER_API_KEY is not configured."
        return None

    primary_model = get_model_name()
    prompt = (
        f"{(system_instruction or '').strip()}\n\n"
        "Use only evidence from the supplied document. If information is absent, say so. "
        "Never fabricate citations or page numbers.\n\n"
        f"{user_content[:MAX_DOCUMENT_CHARS]}"
    )

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
        "HTTP-Referer": "https://localhost",
        "X-Title": "Research Nexus",
    }

    def _build_payload(model_name: str) -> Dict[str, Any]:
        payload: Dict[str, Any] = {
            "model": model_name,
            "messages": [
                {"role": "system", "content": system_instruction or "You are a helpful research assistant."},
                {"role": "user", "content": prompt},
            ],
        }
        if response_schema:
            payload["response_format"] = {
                "type": "json_schema",
                "json_schema": {
                    "name": "structured_response",
                    "schema": response_schema,
                    "strict": False,
                },
            }
        return payload

    def _extract_text(resp_json: Dict[str, Any]) -> Optional[str]:
        choices = resp_json.get("choices") or []
        if not choices:
            return None
        message = choices[0].get("message", {}) if isinstance(choices[0], dict) else {}
        content = message.get("content") or ""
        if isinstance(content, list):
            parts = []
            for part in content:
                if isinstance(part, dict):
                    text = part.get("text") or ""
                    if text:
                        parts.append(str(text))
                elif isinstance(part, str):
                    parts.append(part)
            content = "\n".join(parts)
        text = str(content).strip()
        return text or None

    def _request(model_name: str) -> tuple[Optional[int], Optional[str]]:
        """Make a single request. Returns (status_code_or_None, text_or_None)."""
        try:
            with httpx.Client(timeout=90.0) as client:
                response = client.post(
                    f"{OPENROUTER_BASE_URL}/chat/completions",
                    headers=headers,
                    json=_build_payload(model_name),
                )

            if response.status_code >= 400:
                data = {}
                try:
                    if response.headers.get("content-type", "").startswith("application/json"):
                        data = response.json()
                except Exception:
                    data = {}
                error_body = data.get("error", {}) if isinstance(data, dict) else {}
                if isinstance(error_body, dict):
                    message = error_body.get("message") or error_body.get("code") or response.text[:500]
                else:
                    message = str(error_body) or response.text[:500]
                safe_message = str(message).replace(api_key, "[REDACTED]") if api_key else str(message)
                safe_message = safe_message.strip() or "OpenRouter request failed."
                logger.warning("OpenRouter %s HTTP %s: %s", model_name, response.status_code, safe_message)
                return response.status_code, None

            payload_json = response.json()
            text = _extract_text(payload_json)
            if not text:
                _last_provider_error = "OpenRouter returned an empty response."
                logger.warning("OpenRouter returned empty response for model %s", model_name)
                return None, None
            return None, text

        except httpx.HTTPError as exc:
            status = None
            try:
                status = exc.response.status_code if getattr(exc, "response", None) is not None else None
            except Exception:
                status = None
            raw_msg = str(exc)
            safe_msg = raw_msg.replace(api_key, "[REDACTED]") if api_key else raw_msg
            if status:
                logger.warning("OpenRouter %s HTTP %s: %s", model_name, status, safe_msg)
            else:
                logger.warning("OpenRouter %s connection error: %s", model_name, safe_msg)
            return status, None
        except Exception as exc:
            raw_msg = str(exc)
            safe_msg = raw_msg.replace(api_key, "[REDACTED]") if api_key else raw_msg
            logger.warning("OpenRouter %s error: %s", model_name, safe_msg)
            return None, None

    # --- Try primary model first ---
    status, text = _request(primary_model)
    if text:
        _last_model_used = primary_model
        return text

    # --- On 429 only, try free fallback models ---
    if status == 429:
        fallbacks = _get_free_fallback_models()
        if fallbacks:
            logger.info(
                "Primary model %s rate-limited (429). Trying %d free fallback models.",
                primary_model, len(fallbacks),
            )
        for fb_model in fallbacks[:3]:
            logger.info("Trying free fallback model: %s", fb_model)
            fb_status, fb_text = _request(fb_model)
            if fb_text:
                _last_model_used = fb_model
                _last_provider_error = ""
                logger.info("Fallback model %s succeeded.", fb_model)
                return fb_text
            if fb_status == 429:
                logger.info("Fallback model %s also rate-limited, trying next.", fb_model)
                continue
            # Non-429 error from fallback: stop retrying
            break

    # --- All attempts failed ---
    _last_model_used = ""
    if not _last_provider_error:
        _last_provider_error = f"OpenRouter request failed (primary: {primary_model})."
    return None
