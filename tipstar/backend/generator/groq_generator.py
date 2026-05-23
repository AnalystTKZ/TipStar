import json
import logging
import re

from backend.config.settings import MIN_RELEVANCE_SCORE
from backend.generator.llm_router import chat_completion
from backend.generator.prompt import SYSTEM_PROMPT, build_user_prompt
from backend.embeddings.miniLM import encode

logger = logging.getLogger(__name__)


def generate_posts(
    news_item: dict,
    enriched_context: dict | None = None,
) -> dict | None:
    """
    Call the configured LLM with the news item and optional enriched context.
    Returns structured post bundle, or None if below relevance threshold.
    """
    user_prompt = build_user_prompt(news_item, enriched_context)

    try:
        result_msg = chat_completion(
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": user_prompt},
            ],
            temperature=0.62,
            max_tokens=1500,
            purpose=f"post generation: {news_item.get('title')}",
        )
        raw = result_msg.content
        result = _parse_json(raw)

        if result is None:
            logger.warning(
                "Could not parse %s JSON for: %s",
                result_msg.provider,
                news_item.get("title"),
            )
            return None

        if _looks_robotic(result):
            result = _rewrite_robotic_posts(news_item, enriched_context, raw) or result

        result["_llm_provider"] = result_msg.provider
        result["_llm_model"] = result_msg.model

        score = result.get("relevance_score", 0)
        if score < MIN_RELEVANCE_SCORE:
            logger.info(f"Score {score} below threshold: {news_item.get('title')}")
            return None

        # Normalise the new flat output shape.
        # post_body is the image text; caption is the hook above the image.
        post_body = (result.get("post_body") or "").strip()
        caption = (result.get("caption") or "").strip()
        if post_body:
            result["post_body"] = post_body
            result["caption"] = _normalise_caption_flat(caption, result.get("hashtags", []))
            result["embedding"] = encode(post_body)

        return result

    except Exception as e:
        logger.error(f"LLM generation failed for '{news_item.get('title')}': {e}")
        return None


def _rewrite_robotic_posts(
    news_item: dict,
    enriched_context: dict | None,
    previous_json: str,
) -> dict | None:
    """One cheap retry when the first draft sounds like article copy."""
    user_prompt = build_user_prompt(news_item, enriched_context)
    rewrite_prompt = f"""{user_prompt}

The previous draft sounded too generic or journalistic.
Rewrite it in TipStar's casual informer voice.
Keep every factual claim grounded in the story and context.
Use shorter lines, more natural football phrasing, and less article language.
Return the same strict JSON shape only.

PREVIOUS DRAFT:
{previous_json[:4000]}"""
    try:
        retry_msg = chat_completion(
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": rewrite_prompt},
            ],
            temperature=0.72,
            max_tokens=1500,
            purpose=f"post generation tone rewrite: {news_item.get('title')}",
        )
        return _parse_json(retry_msg.content)
    except Exception as exc:
        logger.warning("Tone rewrite failed for '%s': %s", news_item.get("title"), exc)
        return None


def _parse_json(raw: str) -> dict | None:
    """Extract and parse the first JSON object from an LLM response."""
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


def _looks_robotic(result: dict) -> bool:
    banned = (
        "it is worth noting",
        "this highlights",
        "in the world of football",
        "fans are buzzing",
        "only time will tell",
        "the beautiful game",
        "a reminder of",
        "a testament to",
        "a significant development",
        "adds another layer",
        "according to reports",
        "the player stated",
        "the manager expressed",
        "will be hoping",
    )
    text = f"{result.get('post_body', '')} {result.get('caption', '')}".lower()
    return sum(1 for phrase in banned if phrase in text) >= 1


def _normalise_caption_flat(caption: str, hashtags) -> str:
    """
    Build the final X caption text (shown above the image).
    Caption is the short hook — hashtags are NOT appended here,
    they go on the post body / image only.
    """
    caption = (caption or "").strip()
    if len(caption) > 280:
        caption = caption[:277].rstrip() + "..."
    return caption
