"""Map approved posts to TipStar social templates."""
from __future__ import annotations

import re
from pathlib import Path

from backend.visuals.social_templates import (
    MatchResultPayload,
    StandardPostPayload,
    render_hot_take,
    render_match_result,
    render_standard_post,
    render_world_cup_special,
)


PROJECT_ROOT = Path(__file__).resolve().parents[2]
POST_VISUAL_DIR = PROJECT_ROOT / "generated" / "visuals" / "posts"


def render_post_visual(post: dict) -> str:
    """
    Render a PNG for an approved/generated post.

    Returns a project-relative path suitable for storing in posts.image_path,
    e.g. ``generated/visuals/posts/post_123.png``.
    """
    post_id = str(post.get("id") or "preview")
    post_type = str(post.get("post_type") or "")
    content = str(post.get("content") or "").strip()
    output_path = POST_VISUAL_DIR / f"post_{post_id}.png"

    if post_type == "hot_take":
        rendered = render_hot_take(content, output_path)
    elif post_type == "wc_narrative" or post.get("is_world_cup"):
        rendered = render_world_cup_special(
            StandardPostPayload(content=content),
            output_path,
            score_or_stat="WORLD CUP 2026",
        )
    elif _looks_like_match_result(post):
        rendered = render_match_result(_match_payload_from_post(post), output_path)
    else:
        number, label = _extract_stat(content)
        rendered = render_standard_post(
            StandardPostPayload(content=content, stat_number=number, stat_label=label),
            output_path,
        )

    return str(rendered.path.relative_to(PROJECT_ROOT))


def _extract_stat(content: str) -> tuple[str, str]:
    match = re.search(r"\b(\d+(?:\.\d+)?%?)\b", content)
    if not match:
        return "", ""
    number = match.group(1)
    tail = content[match.end():].strip(" .,:;-")
    label = " ".join(tail.split()[:3]) or "stat"
    return number, label


def _looks_like_match_result(post: dict) -> bool:
    title = str(post.get("story_title") or "")
    content = str(post.get("content") or "")
    haystack = f"{title} {content}".lower()
    return bool(re.search(r"\b\d+\s*[--]\s*\d+\b", haystack)) and any(
        token in haystack for token in ["beat", "defeat", "draw", "full-time", "full time", "result", "win"]
    )


def _match_payload_from_post(post: dict) -> MatchResultPayload:
    title = str(post.get("story_title") or "")
    content = str(post.get("content") or "")
    combined = f"{title} {content}"
    score_match = re.search(r"\b(\d+\s*[--]\s*\d+)\b", combined)
    score = score_match.group(1).replace("-", "-") if score_match else "0-0"
    teams = _guess_teams(combined)
    return MatchResultPayload(
        competition="MATCH RESULT",
        home_team=teams[0],
        away_team=teams[1],
        score=score,
        key_events=(content[:90],),
    )


def _guess_teams(text: str) -> tuple[str, str]:
    vs = re.search(r"([A-Z][A-Za-z .'-]{2,24})\s+(?:vs|v|against)\s+([A-Z][A-Za-z .'-]{2,24})", text)
    if vs:
        return vs.group(1).strip(), vs.group(2).strip()
    return "Team A", "Team B"
