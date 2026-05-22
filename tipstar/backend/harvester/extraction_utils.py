"""Shared helpers for YouTube intelligence extraction."""
from __future__ import annotations

import asyncio
import json
import logging
import re
from typing import Any

from backend.generator.llm_router import chat_completion

logger = logging.getLogger(__name__)


async def extract_json_array(system_prompt: str, user_prompt: str, retries: int = 3) -> list[dict]:
    """Call the configured LLM and parse a JSON array, with simple retry handling."""
    last_error: Exception | None = None
    for attempt in range(retries):
        try:
            raw = await asyncio.to_thread(_call_llm, system_prompt, user_prompt)
            parsed = _parse_json_array(raw)
            return parsed
        except Exception as exc:
            last_error = exc
            if attempt < retries - 1:
                await asyncio.sleep(10)
    logger.warning("LLM extraction failed after retries: %s", last_error)
    return []


def _call_llm(system_prompt: str, user_prompt: str) -> str:
    result = chat_completion(
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        temperature=0.25,
        max_tokens=2200,
        purpose="YouTube intelligence extraction",
    )
    return result.content


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
