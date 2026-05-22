"""Extract and verify factual claims from harvested football stories."""
from __future__ import annotations

import asyncio
import json
import logging
import re
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from backend.database.db import upsert_fact_claim
from backend.embeddings.miniLM import encode
from backend.generator.llm_router import chat_completion

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """You are a football fact extraction analyst.
Extract only atomic factual claims from the story.

Return a JSON array. Each object must include:
- claim_text: one factual claim in a complete sentence.
- claim_type: transfer, injury, selection, result, fixture, quote, contract, manager, squad, tournament, disciplinary, stat, or general.
- entity_type: player, team, tournament, match, manager, or general.
- entities: list of player, team, manager, tournament, or competition names.
- temporal_scope: current, historical, future, or rumour.

Rules:
- Only extract claims directly supported by the story.
- Do not extract opinions, hype, jokes, or fan reaction as facts.
- Transfer rumours must use temporal_scope rumour unless official or confirmed.
- Keep claims short and verifiable.
- Return at most 5 claims.
- Return only JSON, no markdown."""


async def extract_and_store_facts(
    session: AsyncSession,
    news_item: dict,
    news_id: str | None = None,
) -> list[dict]:
    """Extract fact claims from one story, embed them, and upsert into fact_claims."""
    if not _has_fact_signal(news_item):
        return []

    try:
        rows = await asyncio.to_thread(_extract_claims, news_item)
    except Exception as exc:
        logger.warning("Fact extraction failed for %s: %s", news_item.get("title"), exc)
        return []

    stored = []
    for row in rows[:5]:
        claim_text = str(row.get("claim_text") or "").strip()
        if not _valid_claim(claim_text):
            continue
        data = {
            "news_id": news_id,
            "claim_text": claim_text,
            "normalized_claim": normalize_claim(claim_text),
            "claim_type": _clean_label(row.get("claim_type"), "general"),
            "entity_type": _clean_label(row.get("entity_type"), "general"),
            "entities": row.get("entities") or [],
            "temporal_scope": _clean_label(row.get("temporal_scope"), "current"),
            "source": news_item.get("source"),
            "source_confidence": news_item.get("source_confidence", "trusted_news"),
            "source_url": news_item.get("url"),
            "embedding": encode(claim_text),
        }
        try:
            claim = await upsert_fact_claim(session, data)
            stored.append(claim.to_dict())
        except Exception as exc:
            logger.warning("Could not store fact claim for %s: %s", news_item.get("title"), exc)

    if stored:
        verified = sum(1 for row in stored if row.get("status") == "verified")
        logger.info(
            "Fact extraction: %s claims=%d verified=%d story=%s",
            news_item.get("source_confidence", "trusted_news"),
            len(stored),
            verified,
            news_item.get("title"),
        )
    return stored


def normalize_claim(text: str) -> str:
    normalized = text.lower()
    normalized = re.sub(r"https?://\S+", "", normalized)
    normalized = re.sub(r"[^a-z0-9]+", " ", normalized)
    return re.sub(r"\s+", " ", normalized).strip()


def _extract_claims(news_item: dict) -> list[dict[str, Any]]:
    prompt = "\n".join([
        f"TITLE: {news_item.get('title', '')}",
        f"DESCRIPTION: {news_item.get('description') or news_item.get('content') or ''}",
        f"SOURCE: {news_item.get('source', '')}",
        f"SOURCE_CONFIDENCE: {news_item.get('source_confidence', 'trusted_news')}",
        f"PUBLISHED: {news_item.get('published_at', '')}",
        f"URL: {news_item.get('url', '')}",
    ])
    result = chat_completion(
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": prompt},
        ],
        temperature=0.05,
        max_tokens=900,
        purpose=f"fact extraction: {news_item.get('title')}",
    )
    return _parse_json_array(result.content)


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


def _has_fact_signal(news_item: dict) -> bool:
    text = f"{news_item.get('title', '')} {news_item.get('description') or news_item.get('content') or ''}".lower()
    signals = [
        "confirmed",
        "announced",
        "signed",
        "agreed",
        "injury",
        "injured",
        "squad",
        "lineup",
        "team news",
        "transfer",
        "talks",
        "bid",
        "contract",
        "manager",
        "press conference",
        "interview",
        "world cup",
        "result",
        "score",
        "goal",
    ]
    return any(signal in text for signal in signals)


def _valid_claim(text: str) -> bool:
    if len(text) < 20 or len(text) > 320:
        return False
    low = text.lower()
    vague = ["fans think", "could be", "might be", "will be interesting", "is a debate"]
    return not any(term in low for term in vague)


def _clean_label(value, default: str) -> str:
    text = str(value or default).strip().lower()
    text = re.sub(r"[^a-z0-9_]+", "_", text)
    return text[:50] or default
