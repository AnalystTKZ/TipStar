"""Shared helpers for YouTube intelligence extraction."""
from __future__ import annotations

import asyncio
import json
import logging
import re
from typing import Any

from groq import Groq

from backend.config.settings import GROQ_API_KEY, GROQ_MODEL

logger = logging.getLogger(__name__)
_client: Groq | None = None


def _get_client() -> Groq:
    global _client
    if _client is None:
        _client = Groq(api_key=GROQ_API_KEY)
    return _client


async def extract_json_array(system_prompt: str, user_prompt: str, retries: int = 3) -> list[dict]:
    """Call Groq and parse a JSON array, with simple retry handling."""
    if not GROQ_API_KEY:
        logger.warning("GROQ_API_KEY not set, skipping extraction")
        return []

    last_error: Exception | None = None
    for attempt in range(retries):
        try:
            raw = await asyncio.to_thread(_call_groq, system_prompt, user_prompt)
            parsed = _parse_json_array(raw)
            return parsed
        except Exception as exc:
            last_error = exc
            if attempt < retries - 1:
                await asyncio.sleep(10)
    logger.warning("Groq extraction failed after retries: %s", last_error)
    return []


def _call_groq(system_prompt: str, user_prompt: str) -> str:
    client = _get_client()
    response = client.chat.completions.create(
        model=GROQ_MODEL,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        temperature=0.25,
        max_tokens=2200,
    )
    return response.choices[0].message.content.strip()


def _parse_json_array(raw: str) -> list[dict[str, Any]]:
    try:
        parsed = json.loads(raw)
        if isinstance(parsed, list):
            return [item for item in parsed if isinstance(item, dict)]
    except json.JSONDecodeError:
        pass

    match = re.search(r"```(?:json)?\s*(\[.*?\])\s*```", raw, re.DOTALL)
    if match:
        parsed = json.loads(match.group(1))
        if isinstance(parsed, list):
            return [item for item in parsed if isinstance(item, dict)]

    match = re.search(r"\[.*\]", raw, re.DOTALL)
    if match:
        parsed = json.loads(match.group(0))
        if isinstance(parsed, list):
            return [item for item in parsed if isinstance(item, dict)]

    return []
