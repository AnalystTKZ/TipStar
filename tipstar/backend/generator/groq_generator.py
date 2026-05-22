import json
import logging
import re
from typing import Optional

from groq import Groq

from backend.config.settings import GROQ_API_KEY, GROQ_MODEL, MIN_RELEVANCE_SCORE
from backend.generator.prompt import SYSTEM_PROMPT, build_user_prompt
from backend.embeddings.miniLM import encode

logger = logging.getLogger(__name__)

_client: Optional[Groq] = None


def _get_client() -> Groq:
    global _client
    if _client is None:
        _client = Groq(api_key=GROQ_API_KEY)
    return _client


def generate_posts(
    news_item: dict,
    enriched_context: dict | None = None,
) -> dict | None:
    """
    Call Groq with the news item and optional enriched context.
    Returns structured post bundle, or None if below relevance threshold.
    """
    if not GROQ_API_KEY:
        logger.error("GROQ_API_KEY not set")
        return None

    user_prompt = build_user_prompt(news_item, enriched_context)

    try:
        client = _get_client()
        response = client.chat.completions.create(
            model=GROQ_MODEL,
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": user_prompt},
            ],
            temperature=0.85,
            max_tokens=1500,
        )
        raw = response.choices[0].message.content.strip()
        result = _parse_json(raw)

        if result is None:
            logger.warning(f"Could not parse Groq JSON for: {news_item.get('title')}")
            return None

        score = result.get("relevance_score", 0)
        if score < MIN_RELEVANCE_SCORE:
            logger.info(f"Score {score} below threshold: {news_item.get('title')}")
            return None

        # Embed each post content for similarity search later
        for key in ("post_a", "post_b", "post_c", "post_d"):
            post = result.get(key)
            if post and post.get("content"):
                post["embedding"] = encode(post["content"])

        return result

    except Exception as e:
        logger.error(f"Groq generation failed for '{news_item.get('title')}': {e}")
        return None


def _parse_json(raw: str) -> dict | None:
    """Extract and parse the first JSON object from a Groq response."""
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        pass

    match = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", raw, re.DOTALL)
    if match:
        try:
            return json.loads(match.group(1))
        except json.JSONDecodeError:
            pass

    match = re.search(r"\{.*\}", raw, re.DOTALL)
    if match:
        try:
            return json.loads(match.group(0))
        except json.JSONDecodeError:
            pass

    return None
