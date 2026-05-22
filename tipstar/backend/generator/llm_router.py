"""LLM routing: Groq primary, OpenRouter fallback."""
from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any

import requests
from groq import Groq

from backend.config.settings import (
    GROQ_API_KEY,
    GROQ_MODEL,
    OPENROUTER_FALLBACK_MODELS,
    OPENROUTER_API_KEY,
    OPENROUTER_APP_NAME,
    OPENROUTER_MODEL,
    OPENROUTER_SITE_URL,
)

logger = logging.getLogger(__name__)

_groq_client: Groq | None = None


@dataclass(frozen=True)
class LLMResult:
    content: str
    provider: str
    model: str


def chat_completion(
    messages: list[dict[str, str]],
    *,
    temperature: float,
    max_tokens: int,
    purpose: str,
) -> LLMResult:
    """
    Call Groq first. If Groq is out of tokens, rate-limited, or unavailable,
    retry the exact same request through OpenRouter.
    """
    groq_error: Exception | None = None

    if GROQ_API_KEY:
        try:
            return _call_groq(messages, temperature=temperature, max_tokens=max_tokens)
        except Exception as exc:
            groq_error = exc
            logger.warning(
                "Groq failed for %s, trying OpenRouter fallback: %s",
                purpose,
                _compact_error(exc),
            )
    else:
        logger.warning("GROQ_API_KEY not set for %s, trying OpenRouter fallback", purpose)

    if OPENROUTER_API_KEY:
        return _call_openrouter_chain(messages, temperature=temperature, max_tokens=max_tokens)

    if groq_error:
        raise groq_error
    raise RuntimeError("No LLM provider configured. Set GROQ_API_KEY or OPENROUTER_API_KEY.")


def _get_groq_client() -> Groq:
    global _groq_client
    if _groq_client is None:
        _groq_client = Groq(api_key=GROQ_API_KEY)
    return _groq_client


def _call_groq(
    messages: list[dict[str, str]],
    *,
    temperature: float,
    max_tokens: int,
) -> LLMResult:
    client = _get_groq_client()
    response = client.chat.completions.create(
        model=GROQ_MODEL,
        messages=messages,
        temperature=temperature,
        max_tokens=max_tokens,
    )
    return LLMResult(
        content=response.choices[0].message.content.strip(),
        provider="groq",
        model=GROQ_MODEL,
    )


def _call_openrouter_chain(
    messages: list[dict[str, str]],
    *,
    temperature: float,
    max_tokens: int,
) -> LLMResult:
    errors: list[str] = []
    for model in _openrouter_models():
        try:
            return _call_openrouter_model(
                model,
                messages,
                temperature=temperature,
                max_tokens=max_tokens,
            )
        except Exception as exc:
            errors.append(f"{model}: {_compact_error(exc)}")
            logger.warning("OpenRouter model failed (%s): %s", model, _compact_error(exc))
    raise RuntimeError("All OpenRouter fallback models failed: " + " | ".join(errors))


def _call_openrouter_model(
    model: str,
    messages: list[dict[str, str]],
    *,
    temperature: float,
    max_tokens: int,
) -> LLMResult:
    response = requests.post(
        "https://openrouter.ai/api/v1/chat/completions",
        headers={
            "Authorization": f"Bearer {OPENROUTER_API_KEY}",
            "Content-Type": "application/json",
            "HTTP-Referer": OPENROUTER_SITE_URL,
            "X-Title": OPENROUTER_APP_NAME,
        },
        json={
            "model": model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
            "include_reasoning": False,
        },
        timeout=60,
    )
    response.raise_for_status()
    payload: dict[str, Any] = response.json()
    choices = payload.get("choices") or []
    if not choices:
        raise RuntimeError(f"OpenRouter returned no choices: {payload}")
    content = choices[0].get("message", {}).get("content", "")
    if not content:
        finish_reason = choices[0].get("finish_reason")
        provider = payload.get("provider")
        usage = payload.get("usage", {})
        raise RuntimeError(
            f"OpenRouter returned empty content "
            f"(provider={provider}, finish_reason={finish_reason}, usage={usage})"
        )
    logger.info("Used OpenRouter fallback model: %s", model)
    return LLMResult(
        content=content.strip(),
        provider="openrouter",
        model=model,
    )


def _openrouter_models() -> list[str]:
    configured = [OPENROUTER_MODEL]
    configured.extend((OPENROUTER_FALLBACK_MODELS or "").split(","))
    configured.append("openrouter/auto")

    seen = set()
    models: list[str] = []
    for raw in configured:
        model = (raw or "").strip()
        if not model or model in seen:
            continue
        seen.add(model)
        if model == "openrouter/auto":
            continue
        models.append(model)

    if "openrouter/auto" in seen:
        models.append("openrouter/auto")
    return models


def _compact_error(exc: Exception) -> str:
    text = str(exc).replace("\n", " ")
    return text[:300]
