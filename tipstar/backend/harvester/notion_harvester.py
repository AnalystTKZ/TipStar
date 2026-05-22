"""
Notion integration with full read, update, and insert permissions.

READ  -- pulls Players, Teams, Drama Log, and Config into TipStar
UPDATE -- syncs changes back when the bot updates existing records
INSERT -- adds new players, drama entries, and match results automatically

All three operations are intentional:
- New players discovered in news are added to the Players database automatically
- Breaking controversies are logged to the Drama Log as they are detected
- Match results are written to the World Cup Tracker as they come in
- Notion becomes a self-updating knowledge base, not a static one
"""
import logging
from datetime import datetime, date
from typing import Optional

import requests

from backend.config.settings import (
    NOTION_API_KEY,
    NOTION_PLAYERS_DB_ID,
    NOTION_TEAMS_DB_ID,
    NOTION_DRAMA_DB_ID,
    NOTION_CONFIG_PAGE_ID,
)

logger = logging.getLogger(__name__)

NOTION_VERSION = "2022-06-28"
BASE_URL = "https://api.notion.com/v1"


# ---------------------------------------------------------------------------
# Core HTTP helpers
# ---------------------------------------------------------------------------

def _headers() -> dict:
    return {
        "Authorization": f"Bearer {NOTION_API_KEY}",
        "Notion-Version": NOTION_VERSION,
        "Content-Type": "application/json",
    }


def _query_database(db_id: str) -> list[dict]:
    """Fetch all pages from a Notion database, handling pagination."""
    results = []
    url = f"{BASE_URL}/databases/{db_id}/query"
    payload = {"page_size": 100}

    while True:
        try:
            resp = requests.post(url, json=payload, headers=_headers(), timeout=20)
            resp.raise_for_status()
            data = resp.json()
            results.extend(data.get("results", []))
            if not data.get("has_more"):
                break
            payload["start_cursor"] = data["next_cursor"]
        except requests.RequestException as e:
            logger.error(f"Notion DB query failed [{db_id}]: {e}")
            break

    return results


def _create_page(db_id: str, properties: dict) -> Optional[dict]:
    """INSERT -- create a new page (row) in a Notion database."""
    try:
        resp = requests.post(
            f"{BASE_URL}/pages",
            json={"parent": {"database_id": db_id}, "properties": properties},
            headers=_headers(),
            timeout=20,
        )
        resp.raise_for_status()
        return resp.json()
    except requests.RequestException as e:
        logger.error(f"Notion page create failed [{db_id}]: {e}")
        return None


def _update_page(page_id: str, properties: dict) -> Optional[dict]:
    """UPDATE -- patch properties on an existing Notion page."""
    try:
        resp = requests.patch(
            f"{BASE_URL}/pages/{page_id}",
            json={"properties": properties},
            headers=_headers(),
            timeout=20,
        )
        resp.raise_for_status()
        return resp.json()
    except requests.RequestException as e:
        logger.error(f"Notion page update failed [{page_id}]: {e}")
        return None


def _append_block(page_id: str, text: str) -> None:
    """Append a paragraph block to a Notion page (used for Config notes)."""
    try:
        requests.patch(
            f"{BASE_URL}/blocks/{page_id}/children",
            json={"children": [{"object": "block", "type": "paragraph",
                                 "paragraph": {"rich_text": [{"type": "text", "text": {"content": text}}]}}]},
            headers=_headers(),
            timeout=15,
        )
    except requests.RequestException as e:
        logger.error(f"Notion block append failed [{page_id}]: {e}")


# ---------------------------------------------------------------------------
# Property builders -- convert Python values into Notion API property dicts
# ---------------------------------------------------------------------------

def _title_prop(value: str) -> dict:
    return {"title": [{"text": {"content": str(value or "")}}]}


def _text_prop(value: str) -> dict:
    return {"rich_text": [{"text": {"content": str(value or "")}}]}


def _number_prop(value) -> dict:
    return {"number": int(value) if value is not None else None}


def _select_prop(value: str) -> dict:
    return {"select": {"name": str(value)} if value else None}


def _date_prop(value) -> dict:
    if not value:
        return {"date": None}
    if isinstance(value, (date, datetime)):
        return {"date": {"start": value.isoformat()}}
    return {"date": {"start": str(value)}}


# ---------------------------------------------------------------------------
# Property reader
# ---------------------------------------------------------------------------

def _prop(page: dict, key: str, prop_type: str = "rich_text") -> Optional[str]:
    """Safely extract a property value from a Notion page."""
    try:
        prop = page["properties"].get(key, {})
        if prop_type == "title":
            return prop["title"][0]["plain_text"] if prop.get("title") else None
        if prop_type == "rich_text":
            return prop["rich_text"][0]["plain_text"] if prop.get("rich_text") else None
        if prop_type == "number":
            return prop.get("number")
        if prop_type == "select":
            sel = prop.get("select")
            return sel["name"] if sel else None
        if prop_type == "date":
            d = prop.get("date")
            return d["start"] if d else None
        if prop_type == "checkbox":
            return prop.get("checkbox", False)
    except (KeyError, IndexError, TypeError):
        pass
    return None


# ---------------------------------------------------------------------------
# READ -- pull knowledge base into TipStar
# ---------------------------------------------------------------------------

def fetch_players() -> list[dict]:
    """READ -- pull all player records from the Notion Players database."""
    if not NOTION_API_KEY or not NOTION_PLAYERS_DB_ID:
        logger.warning("Notion Players DB not configured -- skipping")
        return []

    pages = _query_database(NOTION_PLAYERS_DB_ID)
    players = []
    for page in pages:
        players.append({
            "_notion_page_id": page["id"],
            "name": _prop(page, "Name", "title") or "",
            "nationality": _prop(page, "Nationality", "rich_text"),
            "current_club": _prop(page, "Current Club", "rich_text"),
            "position": _prop(page, "Position", "select"),
            "tier": _prop(page, "Tier", "select"),
            "age": _prop(page, "Age", "number"),
            "world_cup_appearances": _prop(page, "World Cup Appearances", "number") or 0,
            "world_cup_goals": _prop(page, "World Cup Goals", "number") or 0,
            "status": _prop(page, "Status", "select") or "Active",
            "notes": _prop(page, "Notes", "rich_text"),
        })
    logger.info(f"Notion READ: fetched {len(players)} players")
    return [p for p in players if p["name"]]


def fetch_teams() -> list[dict]:
    """READ -- pull all team records from the Notion Teams database."""
    if not NOTION_API_KEY or not NOTION_TEAMS_DB_ID:
        logger.warning("Notion Teams DB not configured -- skipping")
        return []

    pages = _query_database(NOTION_TEAMS_DB_ID)
    teams = []
    for page in pages:
        teams.append({
            "_notion_page_id": page["id"],
            "name": _prop(page, "Name", "title") or "",
            "country": _prop(page, "Country", "rich_text"),
            "league": _prop(page, "League", "rich_text"),
            "manager": _prop(page, "Manager", "rich_text"),
            "world_cup_group": _prop(page, "World Cup Group", "select"),
            "world_cup_status": _prop(page, "World Cup Status", "select") or "TBC",
            "playing_style": _prop(page, "Playing Style", "rich_text"),
            "priority": _prop(page, "Priority", "select"),
            "notes": _prop(page, "Notes", "rich_text"),
        })
    logger.info(f"Notion READ: fetched {len(teams)} teams")
    return [t for t in teams if t["name"]]


def fetch_drama() -> list[dict]:
    """READ -- pull all drama entries from the Notion Drama Log database."""
    if not NOTION_API_KEY or not NOTION_DRAMA_DB_ID:
        logger.warning("Notion Drama DB not configured -- skipping")
        return []

    pages = _query_database(NOTION_DRAMA_DB_ID)
    drama_list = []
    for page in pages:
        drama_list.append({
            "_notion_page_id": page["id"],
            "title": _prop(page, "Title", "title") or "",
            "players_involved": _prop(page, "Players Involved", "rich_text"),
            "teams_involved": _prop(page, "Teams Involved", "rich_text"),
            "category": _prop(page, "Category", "select"),
            "severity": _prop(page, "Severity", "select"),
            "summary": _prop(page, "Summary", "rich_text"),
            "status": _prop(page, "Status", "select") or "Ongoing",
            "source": _prop(page, "Source", "rich_text"),
            "drama_date": _prop(page, "Date", "date"),
        })
    logger.info(f"Notion READ: fetched {len(drama_list)} drama entries")
    return [d for d in drama_list if d["title"]]


def fetch_config() -> dict:
    """READ -- pull editorial preferences from the TipStar Config Notion page."""
    if not NOTION_API_KEY or not NOTION_CONFIG_PAGE_ID:
        logger.warning("Notion Config page not configured -- skipping")
        return {}

    try:
        blocks_resp = requests.get(
            f"{BASE_URL}/blocks/{NOTION_CONFIG_PAGE_ID}/children",
            headers=_headers(),
            timeout=15,
        )
        blocks_resp.raise_for_status()
        blocks = blocks_resp.json().get("results", [])

        notes_lines = []
        for block in blocks:
            block_type = block.get("type")
            if block_type in ("paragraph", "bulleted_list_item", "numbered_list_item"):
                rich_text = block.get(block_type, {}).get("rich_text", [])
                line = "".join(t.get("plain_text", "") for t in rich_text)
                if line.strip():
                    notes_lines.append(line.strip())

        return {"editorial_notes": "\n".join(notes_lines)}
    except Exception as e:
        logger.error(f"Notion config fetch failed: {e}")
        return {}


# ---------------------------------------------------------------------------
# INSERT -- bot adds new records to Notion automatically
# ---------------------------------------------------------------------------

def insert_player(player: dict) -> Optional[str]:
    """
    INSERT -- add a newly discovered player to the Notion Players database.
    Called when the bot encounters a relevant player not yet in the knowledge base.
    Returns the new Notion page ID, or None on failure.
    """
    if not NOTION_API_KEY or not NOTION_PLAYERS_DB_ID:
        return None

    properties = {
        "Name": _title_prop(player.get("name", "")),
        "Nationality": _text_prop(player.get("nationality", "")),
        "Current Club": _text_prop(player.get("current_club", "")),
        "Position": _select_prop(player.get("position")),
        "Tier": _select_prop(player.get("tier")),
        "Age": _number_prop(player.get("age")),
        "World Cup Appearances": _number_prop(player.get("world_cup_appearances", 0)),
        "World Cup Goals": _number_prop(player.get("world_cup_goals", 0)),
        "Status": _select_prop(player.get("status", "Active")),
        "Notes": _text_prop(player.get("notes", "")),
    }

    page = _create_page(NOTION_PLAYERS_DB_ID, properties)
    if page:
        logger.info(f"Notion INSERT player: {player.get('name')}")
        return page["id"]
    return None


def insert_drama(drama: dict) -> Optional[str]:
    """
    INSERT -- log a new controversy or drama entry to the Notion Drama Log.
    Called automatically when the bot detects a new incident in the news.
    Returns the new Notion page ID, or None on failure.
    """
    if not NOTION_API_KEY or not NOTION_DRAMA_DB_ID:
        return None

    properties = {
        "Title": _title_prop(drama.get("title", "")),
        "Players Involved": _text_prop(drama.get("players_involved", "")),
        "Teams Involved": _text_prop(drama.get("teams_involved", "")),
        "Category": _select_prop(drama.get("category")),
        "Severity": _select_prop(drama.get("severity")),
        "Summary": _text_prop(drama.get("summary", "")),
        "Status": _select_prop(drama.get("status", "Ongoing")),
        "Source": _text_prop(drama.get("source", "")),
        "Date": _date_prop(drama.get("drama_date")),
    }

    page = _create_page(NOTION_DRAMA_DB_ID, properties)
    if page:
        logger.info(f"Notion INSERT drama: {drama.get('title')}")
        return page["id"]
    return None


def insert_match_result(match: dict) -> Optional[str]:
    """
    INSERT -- write a new match result to the Notion World Cup Tracker.
    Called when the bot processes a match result story.
    Uses NOTION_MATCHES_DB_ID from settings if configured.
    """
    from backend.config.settings import NOTION_MATCHES_DB_ID
    if not NOTION_API_KEY or not NOTION_MATCHES_DB_ID:
        logger.debug("Notion Matches DB not configured -- skipping match insert")
        return None

    home = match.get("home_team", "")
    away = match.get("away_team", "")
    title = f"{home} {match.get('home_score', '?')} - {match.get('away_score', '?')} {away}"

    properties = {
        "Match": _title_prop(title),
        "Home Team": _text_prop(home),
        "Away Team": _text_prop(away),
        "Home Score": _number_prop(match.get("home_score")),
        "Away Score": _number_prop(match.get("away_score")),
        "Stage": _select_prop(match.get("stage")),
        "Tournament": _text_prop(match.get("tournament", "")),
        "Venue": _text_prop(match.get("venue", "")),
        "Date": _date_prop(match.get("match_date")),
        "Scorers": _text_prop(match.get("scorers", "")),
        "Key Events": _text_prop(match.get("key_events", "")),
    }

    page = _create_page(NOTION_MATCHES_DB_ID, properties)
    if page:
        logger.info(f"Notion INSERT match: {title}")
        return page["id"]
    return None


# ---------------------------------------------------------------------------
# UPDATE -- sync changes back when the bot updates existing records
# ---------------------------------------------------------------------------

def update_player(notion_page_id: str, updates: dict) -> bool:
    """
    UPDATE -- patch an existing player's properties in Notion.
    Called when the bot discovers new stats, a club move, or updated notes.
    """
    if not NOTION_API_KEY or not notion_page_id:
        return False

    # Build only the fields that are present in updates
    properties = {}
    field_map = {
        "nationality":          ("Nationality",            _text_prop),
        "current_club":         ("Current Club",           _text_prop),
        "position":             ("Position",               _select_prop),
        "tier":                 ("Tier",                   _select_prop),
        "age":                  ("Age",                    _number_prop),
        "world_cup_appearances":("World Cup Appearances",  _number_prop),
        "world_cup_goals":      ("World Cup Goals",        _number_prop),
        "status":               ("Status",                 _select_prop),
        "notes":                ("Notes",                  _text_prop),
    }

    for key, (notion_key, builder) in field_map.items():
        if key in updates:
            properties[notion_key] = builder(updates[key])

    if not properties:
        return False

    result = _update_page(notion_page_id, properties)
    if result:
        logger.info(f"Notion UPDATE player [{notion_page_id}]: {list(updates.keys())}")
    return result is not None


def update_team_wc_status(notion_page_id: str, wc_status: str, notes: str = "") -> bool:
    """
    UPDATE -- update a team's World Cup status in Notion.
    Called when match results reveal a team's progression or elimination.
    """
    if not NOTION_API_KEY or not notion_page_id:
        return False

    properties = {
        "World Cup Status": _select_prop(wc_status),
    }
    if notes:
        properties["Notes"] = _text_prop(notes)

    result = _update_page(notion_page_id, properties)
    if result:
        logger.info(f"Notion UPDATE team WC status [{notion_page_id}]: {wc_status}")
    return result is not None


def update_drama_status(notion_page_id: str, status: str, resolution_note: str = "") -> bool:
    """
    UPDATE -- mark a drama entry as Resolved or update its status.
    Called when the bot detects follow-up news that closes an incident.
    """
    if not NOTION_API_KEY or not notion_page_id:
        return False

    properties = {"Status": _select_prop(status)}
    result = _update_page(notion_page_id, properties)

    if result and resolution_note:
        _append_block(notion_page_id, f"Update ({datetime.utcnow().strftime('%Y-%m-%d')}): {resolution_note}")

    if result:
        logger.info(f"Notion UPDATE drama status [{notion_page_id}]: {status}")
    return result is not None


# ---------------------------------------------------------------------------
# Smart write-back helpers -- called from the orchestrator after generation
# ---------------------------------------------------------------------------

def _player_exists_in_notion(name: str) -> Optional[str]:
    """Return the Notion page ID if a player already exists, else None."""
    if not NOTION_PLAYERS_DB_ID:
        return None
    pages = _query_database(NOTION_PLAYERS_DB_ID)
    name_lower = name.lower().strip()
    for page in pages:
        existing = (_prop(page, "Name", "title") or "").lower().strip()
        if existing == name_lower:
            return page["id"]
    return None


def _drama_exists_in_notion(title: str) -> Optional[str]:
    """Return the Notion page ID if a drama entry with this title already exists."""
    if not NOTION_DRAMA_DB_ID:
        return None
    pages = _query_database(NOTION_DRAMA_DB_ID)
    title_lower = title.lower().strip()
    for page in pages:
        existing = (_prop(page, "Title", "title") or "").lower().strip()
        if existing == title_lower:
            return page["id"]
    return None


def write_back_from_story(story: dict, generated: dict) -> None:
    """
    Orchestrator hook -- called after Groq generates posts for a story.
    Decides which Notion write operations to perform based on story content.

    Three actions:
    1. If a new Tier 1/2 player is mentioned and is not in Notion -- INSERT them
    2. If the story contains drama/controversy signals -- INSERT a drama entry
    3. If the story is a World Cup match result -- INSERT the match result
    """
    if not NOTION_API_KEY:
        return

    title = story.get("title", "")
    description = story.get("description", "") or ""
    full_text = f"{title} {description}".lower()
    is_wc = generated.get("is_world_cup", False)
    score = generated.get("relevance_score", 0)

    # 1. Auto-insert newly mentioned elite players not yet in the knowledge base
    _maybe_insert_new_players(full_text, score)

    # 2. Auto-log drama entries for controversies detected in the story
    _maybe_insert_drama(story, generated, full_text)

    # 3. Auto-insert World Cup match results
    if is_wc:
        _maybe_insert_match(story, full_text)


# Tier 1/2 players to watch for -- extend as needed
_KNOWN_ELITE = [
    "messi", "ronaldo", "neymar", "haaland", "mbappe", "vinicius", "bellingham",
    "de bruyne", "rodri", "salah", "kane", "rashford", "saka", "pedri", "gavi",
    "lamine yamal", "kylian mbappe", "jude bellingham",
]

_DRAMA_SIGNALS = [
    "ban", "suspended", "red card", "controversy", "row", "argument", "fight",
    "arrested", "accused", "investigation", "fallout", "rift", "clash", "scandal",
    "sacked", "fired", "racist", "abuse", "incident",
]

_SCORE_PATTERNS = [
    r"\b(\d+)-(\d+)\b",
    r"\bbeat\b", r"\bdefeated\b", r"\bwon\b", r"\bdrew\b", r"\blost\b",
]


def _maybe_insert_new_players(full_text: str, score: int) -> None:
    """Insert tier-1/2 players mentioned in the story if not already in Notion."""
    if score < 7:
        return  # Only auto-add players from high-relevance stories

    for player_name in _KNOWN_ELITE:
        if player_name in full_text:
            existing_id = _player_exists_in_notion(player_name.title())
            if not existing_id:
                insert_player({
                    "name": player_name.title(),
                    "status": "Active",
                    "notes": f"Auto-added by TipStar on {datetime.utcnow().strftime('%Y-%m-%d')}",
                })


def _maybe_insert_drama(story: dict, generated: dict, full_text: str) -> None:
    """If a story contains drama signals and does not exist yet, log it to Notion."""
    has_drama = any(signal in full_text for signal in _DRAMA_SIGNALS)
    if not has_drama:
        return

    title = story.get("title", "")
    if not title:
        return

    # Avoid duplicates
    if _drama_exists_in_notion(title):
        return

    # Infer severity from relevance score
    score = generated.get("relevance_score", 0)
    severity = "critical" if score >= 9 else "high" if score >= 7 else "medium"

    insert_drama({
        "title": title,
        "summary": story.get("description", ""),
        "source": story.get("url", story.get("source", "")),
        "severity": severity,
        "status": "Ongoing",
        "drama_date": datetime.utcnow().date().isoformat(),
    })


def _maybe_insert_match(story: dict, full_text: str) -> None:
    """If a story reads like a match result, insert it into the World Cup Tracker."""
    import re
    has_score = any(re.search(p, full_text) for p in _SCORE_PATTERNS)
    if not has_score:
        return

    # Only attempt if NOTION_MATCHES_DB_ID is configured
    from backend.config.settings import NOTION_MATCHES_DB_ID
    if not NOTION_MATCHES_DB_ID:
        return

    insert_match_result({
        "home_team": "",  # Parsing team names from headlines is unreliable -- log with title only
        "away_team": "",
        "tournament": "2026 FIFA World Cup",
        "key_events": story.get("title", ""),
        "match_date": datetime.utcnow().isoformat(),
    })
