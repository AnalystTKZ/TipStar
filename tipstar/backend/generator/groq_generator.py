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

        result["_llm_provider"] = result_msg.provider
        result["_llm_model"] = result_msg.model

        score = result.get("relevance_score", 0)
        if score < MIN_RELEVANCE_SCORE:
            logger.info(f"Score {score} below threshold: {news_item.get('title')}")
            return None

        # Embed each post content for similarity search later
        for key in ("post_a", "post_b", "post_c", "post_d"):
            post = result.get(key)
            if post and post.get("content"):
                post["caption"] = _normalise_caption(post)
                post["embedding"] = encode(post["content"])

        return result

    except Exception as e:
        logger.error(f"LLM generation failed for '{news_item.get('title')}': {e}")
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


def _normalise_caption(post: dict) -> str:
    content = (post.get("content") or "").strip()
    caption = (post.get("caption") or "").strip()
    hashtags = post.get("hashtags") or []
    if isinstance(hashtags, str):
        tags = [t.strip() for t in re.split(r"[,\s]+", hashtags) if t.strip()]
    else:
        tags = [str(t).strip() for t in hashtags if str(t).strip()]
    tag_text = " ".join(t if t.startswith("#") else f"#{t}" for t in tags[:3])

    if not caption:
        caption = content
    if tag_text and not any(tag.lower() in caption.lower() for tag in tags):
        caption = f"{caption}\n\n{tag_text}".strip()
    if len(caption) > 260:
        caption = caption[:257].rstrip() + "..."
    return caption
