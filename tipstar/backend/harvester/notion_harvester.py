"""
Notion integration with full read, update, and insert permissions.

READ  -- pulls Players, Teams, Drama Log, and Config into TipStar
UPDATE -- syncs changes back when the bot updates existing records
INSERT -- adds new players, drama entries, match results, and calendar posts

All database IDs are resolved dynamically via notion_registry so new
Notion databases added to TipStar HQ are picked up without code changes.
"""
import logging
from datetime import datetime, date
from typing import Optional

import requests

from backend.config.settings import NOTION_API_KEY, NOTION_CONFIG_PAGE_ID
from backend.harvester.notion_registry import get_db_id

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


def _query_database(db_id: str, filter_payload: Optional[dict] = None) -> list[dict]:
    """Fetch all pages from a Notion database, handling pagination."""
    results = []
    url = f"{BASE_URL}/databases/{db_id}/query"
    payload: dict = {"page_size": 100}
    if filter_payload:
        payload["filter"] = filter_payload

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
            logger.error("Notion DB query failed [%s]: %s", db_id, e)
            break

    return results


def _create_page(db_id: str, properties: dict) -> Optional[dict]:
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
        logger.error("Notion page create failed [%s]: %s", db_id, e)
        return None


def _update_page(page_id: str, properties: dict) -> Optional[dict]:
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
        logger.error("Notion page update failed [%s]: %s", page_id, e)
        return None


def _append_block(page_id: str, text: str) -> None:
    try:
        requests.patch(
            f"{BASE_URL}/blocks/{page_id}/children",
            json={"children": [{"object": "block", "type": "paragraph",
                                 "paragraph": {"rich_text": [{"type": "text", "text": {"content": text}}]}}]},
            headers=_headers(),
            timeout=15,
        )
    except requests.RequestException as e:
        logger.error("Notion block append failed [%s]: %s", page_id, e)


# ---------------------------------------------------------------------------
# Property builders
# ---------------------------------------------------------------------------

def _title_prop(value: str) -> dict:
    return {"title": [{"text": {"content": str(value or "")}}]}


def _text_prop(value: str) -> dict:
    return {"rich_text": [{"text": {"content": str(value or "")}}]}


def _number_prop(value) -> dict:
    return {"number": int(value) if value is not None else None}


def _select_prop(value: str) -> dict:
    return {"select": {"name": str(value)} if value else None}


def _multi_select_prop(values: list) -> dict:
    return {"multi_select": [{"name": str(v)} for v in (values or []) if v]}


def _checkbox_prop(value: bool) -> dict:
    return {"checkbox": bool(value)}


def _date_prop(value) -> dict:
    if not value:
        return {"date": None}
    if isinstance(value, (date, datetime)):
        return {"date": {"start": value.isoformat()}}
    return {"date": {"start": str(value)}}


def _relation_prop(page_urls: list) -> dict:
    """Build a relation property from a list of Notion page URLs or IDs."""
    ids = []
    for url in (page_urls or []):
        # Accept full URL or raw ID
        raw = url.split("/")[-1].split("?")[0].replace("-", "")
        if len(raw) == 32:
            formatted = f"{raw[:8]}-{raw[8:12]}-{raw[12:16]}-{raw[16:20]}-{raw[20:]}"
            ids.append({"id": formatted})
    return {"relation": ids}


# ---------------------------------------------------------------------------
# Property reader
# ---------------------------------------------------------------------------

def _prop(page: dict, key: str, prop_type: str = "rich_text") -> Optional[str]:
    try:
        prop = page["properties"].get(key, {})
        if prop_type == "title":
            return prop["title"][0]["plain_text"] if prop.get("title") else None
        if prop_type == "rich_text":
            return prop["rich_text"][0]["plain_text"] if prop.get("rich_text") else None
        if prop_type == "text":
            # Notion "text" type (page body) uses rich_text
            return prop["rich_text"][0]["plain_text"] if prop.get("rich_text") else None
        if prop_type == "number":
            return prop.get("number")
        if prop_type == "select":
            sel = prop.get("select")
            return sel["name"] if sel else None
        if prop_type == "multi_select":
            return [s["name"] for s in prop.get("multi_select", [])]
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
    db_id = get_db_id("players")
    if not NOTION_API_KEY or not db_id:
        logger.warning("Notion Players DB not configured -- skipping")
        return []

    pages = _query_database(db_id)
    players = []
    for page in pages:
        # current_club: Notion uses a select with Big5 clubs; Non-Big5 is a separate select
        club = _prop(page, "Current Club", "select") or _prop(page, "Current Club (Non-Big5)", "select")
        players.append({
            "_notion_page_id": page["id"],
            "name": _prop(page, "Name", "title") or "",
            "nationality": _prop(page, "Nationality", "select"),
            "current_club": club,
            "position": _prop(page, "Position", "select"),
            "tier": _prop(page, "Tier", "select"),
            "age": _prop(page, "Age", "number"),
            "world_cup_appearances": _prop(page, "World Cup Appearances", "number") or 0,
            "world_cup_goals": _prop(page, "World Cup Goals", "number") or 0,
            "world_cup_squad": _prop(page, "World Cup 2026 Squad", "checkbox") or False,
            "status": _prop(page, "Status", "select") or "Active",
            "market_value": _prop(page, "Market Value", "rich_text"),
            "instagram_followers": _prop(page, "Instagram Followers", "rich_text"),
            "content_angle": _prop(page, "Content Angle", "multi_select") or [],
            "notes": _prop(page, "Notes", "text"),
        })
    logger.info("Notion READ: fetched %d players", len(players))
    return [p for p in players if p["name"]]


def fetch_teams() -> list[dict]:
    db_id = get_db_id("teams")
    if not NOTION_API_KEY or not db_id:
        logger.warning("Notion Teams DB not configured -- skipping")
        return []

    pages = _query_database(db_id)
    teams = []
    for page in pages:
        teams.append({
            "_notion_page_id": page["id"],
            "name": _prop(page, "Team Name", "title") or _prop(page, "Name", "title") or "",
            "country": _prop(page, "Country", "select"),
            "league": _prop(page, "League or Tournament", "select") or _prop(page, "League", "rich_text"),
            "manager": _prop(page, "Manager", "text"),
            "world_cup_group": _prop(page, "World Cup Group", "rich_text"),
            "world_cup_status": _prop(page, "World Cup Status", "select") or "TBC",
            "playing_style": _prop(page, "Playing Style", "select"),
            "priority": _prop(page, "Priority", "select"),
            "notes": _prop(page, "Notes", "text"),
        })
    logger.info("Notion READ: fetched %d teams", len(teams))
    return [t for t in teams if t["name"]]


def fetch_drama() -> list[dict]:
    db_id = get_db_id("drama log")
    if not NOTION_API_KEY or not db_id:
        logger.warning("Notion Drama DB not configured -- skipping")
        return []

    pages = _query_database(db_id)
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
    logger.info("Notion READ: fetched %d drama entries", len(drama_list))
    return [d for d in drama_list if d["title"]]


def fetch_tournaments() -> list[dict]:
    db_id = get_db_id("tournaments")
    if not NOTION_API_KEY or not db_id:
        logger.warning("Notion Tournaments DB not configured -- skipping")
        return []

    pages = _query_database(db_id)
    tournaments = []
    for page in pages:
        content_angles = _prop(page, "Content Angles", "multi_select") or []
        tournaments.append({
            "_notion_page_id": page["id"],
            "name": _prop(page, "Tournament Name", "title") or "",
            "type": _prop(page, "Type", "select"),
            "status": _prop(page, "Status", "select"),
            "host_country": _prop(page, "Host Country", "rich_text"),
            "start_date": _prop(page, "Start Date", "date"),
            "end_date": _prop(page, "End Date", "date"),
            "total_teams": _prop(page, "Total Teams", "number"),
            "total_matches": _prop(page, "Total Matches", "number"),
            "matches_played": _prop(page, "Matches Played", "number"),
            "current_stage": _prop(page, "Current Stage", "select"),
            "defending_champion": _prop(page, "Defending Champion", "rich_text"),
            "current_leader": _prop(page, "Current Leader", "rich_text"),
            "favourite_to_win": _prop(page, "Favourite to Win", "rich_text"),
            "top_scorer": _prop(page, "Top Scorer", "rich_text"),
            "key_teams": _prop(page, "Key Teams", "rich_text"),
            "key_players": _prop(page, "Key Players", "rich_text"),
            "coverage_priority": _prop(page, "Coverage Priority", "select"),
            "content_angles": ", ".join(content_angles) if content_angles else None,
            "notes": _prop(page, "Notes", "rich_text"),
        })
    logger.info("Notion READ: fetched %d tournaments", len(tournaments))
    return [t for t in tournaments if t["name"]]


def fetch_content_calendar(status_filter: Optional[str] = None) -> list[dict]:
    """
    READ -- pull content calendar entries, optionally filtered by status.
    status_filter: one of "Idea", "In Progress", "Scheduled", "Posted", "Rejected"
    """
    db_id = get_db_id("content calendar")
    if not NOTION_API_KEY or not db_id:
        logger.warning("Notion Content Calendar DB not configured -- skipping")
        return []

    filter_payload = None
    if status_filter:
        filter_payload = {"property": "Status", "select": {"equals": status_filter}}

    pages = _query_database(db_id, filter_payload)
    entries = []
    for page in pages:
        entries.append({
            "_notion_page_id": page["id"],
            "post_idea": _prop(page, "Post Idea", "title") or "",
            "status": _prop(page, "Status", "select"),
            "platform": _prop(page, "Platform", "select"),
            "content_type": _prop(page, "Content Type", "select"),
            "priority": _prop(page, "Priority", "select"),
            "target_date": _prop(page, "Target Date", "date"),
            "engagement_score": _prop(page, "Engagement Score", "number"),
            "notes": _prop(page, "Notes", "text"),
        })
    logger.info("Notion READ: fetched %d content calendar entries", len(entries))
    return entries


def fetch_config() -> dict:
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
        logger.error("Notion config fetch failed: %s", e)
        return {}


# ---------------------------------------------------------------------------
# INSERT
# ---------------------------------------------------------------------------

def insert_player(player: dict) -> Optional[str]:
    db_id = get_db_id("players")
    if not NOTION_API_KEY or not db_id:
        return None

    properties = {
        "Name": _title_prop(player.get("name", "")),
        "Nationality": _select_prop(player.get("nationality")),
        "Current Club": _select_prop(player.get("current_club")),
        "Position": _select_prop(player.get("position")),
        "Tier": _select_prop(player.get("tier")),
        "Age": _number_prop(player.get("age")),
        "World Cup Appearances": _number_prop(player.get("world_cup_appearances", 0)),
        "World Cup Goals": _number_prop(player.get("world_cup_goals", 0)),
        "Status": _select_prop(player.get("status", "Active")),
        "Notes": _text_prop(player.get("notes", "")),
    }

    page = _create_page(db_id, properties)
    if page:
        logger.info("Notion INSERT player: %s", player.get("name"))
        return page["id"]
    return None


def insert_drama(drama: dict) -> Optional[str]:
    db_id = get_db_id("drama log")
    if not NOTION_API_KEY or not db_id:
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

    page = _create_page(db_id, properties)
    if page:
        logger.info("Notion INSERT drama: %s", drama.get("title"))
        return page["id"]
    return None


def insert_match_result(match: dict) -> Optional[str]:
    db_id = get_db_id("world cup 2026")
    if not NOTION_API_KEY or not db_id:
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

    page = _create_page(db_id, properties)
    if page:
        logger.info("Notion INSERT match: %s", title)
        return page["id"]
    return None


def insert_content_calendar_entry(entry: dict) -> Optional[str]:
    """
    INSERT -- add a generated post to the Content Calendar.

    entry keys:
        post_idea (str)         -- the post text / headline
        platform (str)          -- "X Post" | "Thread" | "Poll" | "Quote Tweet"
        content_type (str)      -- "Hot Take" | "Data and Stats" | "Tactical" |
                                   "World Cup Narrative" | "Thread" | "Poll"
        priority (str)          -- "High" | "Medium" | "Low"
        target_date (str|date)  -- ISO date string or date object
        notes (str)             -- optional extra context
        status (str)            -- defaults to "Idea"
        related_player_urls (list[str])  -- Notion page URLs for related players
        related_team_urls (list[str])    -- Notion page URLs for related teams
    """
    db_id = get_db_id("content calendar")
    if not NOTION_API_KEY or not db_id:
        logger.debug("Notion Content Calendar DB not configured -- skipping")
        return None

    properties = {
        "Post Idea": _title_prop(entry.get("post_idea", "")),
        "Status": _select_prop(entry.get("status", "Idea")),
        "Platform": _select_prop(entry.get("platform", "X Post")),
        "Content Type": _select_prop(entry.get("content_type")),
        "Priority": _select_prop(entry.get("priority", "Medium")),
        "Target Date": _date_prop(entry.get("target_date")),
        "Notes": _text_prop(entry.get("notes", "")),
    }

    if entry.get("related_player_urls"):
        properties["Related Player"] = _relation_prop(entry["related_player_urls"])
    if entry.get("related_team_urls"):
        properties["Related Team"] = _relation_prop(entry["related_team_urls"])

    page = _create_page(db_id, properties)
    if page:
        logger.info("Notion INSERT content calendar: %s", entry.get("post_idea", "")[:60])
        return page["id"]
    return None


# ---------------------------------------------------------------------------
# UPDATE
# ---------------------------------------------------------------------------

def update_player(notion_page_id: str, updates: dict) -> bool:
    if not NOTION_API_KEY or not notion_page_id:
        return False

    properties = {}
    field_map = {
        "nationality":           ("Nationality",           _select_prop),
        "current_club":          ("Current Club",          _select_prop),
        "position":              ("Position",              _select_prop),
        "tier":                  ("Tier",                  _select_prop),
        "age":                   ("Age",                   _number_prop),
        "world_cup_appearances": ("World Cup Appearances", _number_prop),
        "world_cup_goals":       ("World Cup Goals",       _number_prop),
        "status":                ("Status",                _select_prop),
        "market_value":          ("Market Value",          _text_prop),
        "notes":                 ("Notes",                 _text_prop),
    }

    for key, (notion_key, builder) in field_map.items():
        if key in updates:
            properties[notion_key] = builder(updates[key])

    properties["Last Updated"] = _date_prop(datetime.utcnow().date())

    if not properties:
        return False

    result = _update_page(notion_page_id, properties)
    if result:
        logger.info("Notion UPDATE player [%s]: %s", notion_page_id, list(updates.keys()))
    return result is not None


def update_team_wc_status(notion_page_id: str, wc_status: str, notes: str = "") -> bool:
    if not NOTION_API_KEY or not notion_page_id:
        return False

    properties = {"World Cup Status": _select_prop(wc_status)}
    if notes:
        properties["Notes"] = _text_prop(notes)

    result = _update_page(notion_page_id, properties)
    if result:
        logger.info("Notion UPDATE team WC status [%s]: %s", notion_page_id, wc_status)
    return result is not None


def update_drama_status(notion_page_id: str, status: str, resolution_note: str = "") -> bool:
    if not NOTION_API_KEY or not notion_page_id:
        return False

    properties = {"Status": _select_prop(status)}
    result = _update_page(notion_page_id, properties)

    if result and resolution_note:
        _append_block(notion_page_id, f"Update ({datetime.utcnow().strftime('%Y-%m-%d')}): {resolution_note}")

    if result:
        logger.info("Notion UPDATE drama status [%s]: %s", notion_page_id, status)
    return result is not None


def update_tournament(notion_page_id: str, updates: dict) -> bool:
    """
    UPDATE -- mirror live tournament data back to Notion.
    Only writes fields that have values; never overwrites name or editorial fields.
    """
    if not NOTION_API_KEY or not notion_page_id:
        return False

    properties = {}
    if updates.get("current_stage"):
        properties["Current Stage"] = _select_prop(updates["current_stage"])
    if updates.get("current_leader"):
        properties["Current Leader"] = _text_prop(updates["current_leader"])
    if updates.get("top_scorer"):
        properties["Top Scorer"] = _text_prop(updates["top_scorer"])
    if updates.get("matches_played") is not None:
        properties["Matches Played"] = _number_prop(updates["matches_played"])
    if updates.get("status"):
        properties["Status"] = _select_prop(updates["status"])

    if not properties:
        return False

    result = _update_page(notion_page_id, properties)
    if result:
        logger.info("Notion UPDATE tournament [%s]: %s", notion_page_id, list(properties.keys()))
    return result is not None


def update_team_live_data(notion_page_id: str, updates: dict) -> bool:
    """
    UPDATE -- mirror live-synced team facts back to Notion.
    Writes: manager, world_cup_group, world_cup_status.
    Never overwrites priority, playing_style, notes — editorial decisions.
    """
    if not NOTION_API_KEY or not notion_page_id:
        return False

    properties = {}
    if updates.get("manager"):
        properties["Manager"] = _text_prop(updates["manager"])
    if updates.get("world_cup_group"):
        properties["World Cup Group"] = _text_prop(updates["world_cup_group"])
    if updates.get("world_cup_status") and updates["world_cup_status"] != "TBC":
        properties["World Cup Status"] = _select_prop(updates["world_cup_status"])

    if not properties:
        return False

    result = _update_page(notion_page_id, properties)
    if result:
        logger.info("Notion UPDATE team live data [%s]: %s", notion_page_id, list(properties.keys()))
    return result is not None


def update_content_calendar_status(notion_page_id: str, status: str, engagement_score: Optional[int] = None) -> bool:
    """UPDATE -- mark a calendar entry as Posted, Rejected, etc."""
    if not NOTION_API_KEY or not notion_page_id:
        return False

    properties = {"Status": _select_prop(status)}
    if engagement_score is not None:
        properties["Engagement Score"] = _number_prop(engagement_score)

    result = _update_page(notion_page_id, properties)
    if result:
        logger.info("Notion UPDATE calendar status [%s]: %s", notion_page_id, status)
    return result is not None


# ---------------------------------------------------------------------------
# Lookup helpers
# ---------------------------------------------------------------------------

def _find_page_id(db_name: str, title_prop: str, name: str) -> Optional[str]:
    """Generic: find the first page in a DB where title_prop == name."""
    db_id = get_db_id(db_name)
    if not db_id:
        return None
    pages = _query_database(db_id, {
        "property": title_prop,
        "title": {"equals": name},
    })
    return pages[0]["id"] if pages else None


def _player_exists_in_notion(name: str) -> Optional[str]:
    return _find_page_id("players", "Name", name)


def _drama_exists_in_notion(title: str) -> Optional[str]:
    return _find_page_id("drama log", "Title", title)


# ---------------------------------------------------------------------------
# Smart write-back helpers -- called from orchestrator after generation
# ---------------------------------------------------------------------------

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

# Content type inference from story keywords
_CONTENT_TYPE_MAP = [
    (["stat", "record", "goals", "assists", "appearances", "data"], "Data and Stats"),
    (["tactic", "formation", "press", "possession", "system"], "Tactical"),
    (["world cup", "wc 2026", "group stage", "knockout", "quarter", "semi", "final"], "World Cup Narrative"),
    (["poll", "vote", "who do you"], "Poll"),
    (["thread", "breakdown", "deep dive"], "Thread"),
]


def _infer_content_type(text: str) -> str:
    lower = text.lower()
    for keywords, content_type in _CONTENT_TYPE_MAP:
        if any(k in lower for k in keywords):
            return content_type
    return "Hot Take"


def write_back_from_story(story: dict, generated: dict) -> None:
    """
    Orchestrator hook -- called after Groq generates posts for a story.
    1. Auto-insert newly mentioned elite players not yet in Notion
    2. Auto-log drama entries for controversies detected
    3. Auto-insert World Cup match results
    4. Add approved posts to the Content Calendar
    """
    if not NOTION_API_KEY:
        return

    title = story.get("title", "")
    description = story.get("description", "") or ""
    full_text = f"{title} {description}".lower()
    is_wc = generated.get("is_world_cup", False)
    score = generated.get("relevance_score", 0)

    _maybe_insert_new_players(full_text, score)
    _maybe_insert_drama(story, generated, full_text)

    if is_wc:
        _maybe_insert_match(story, full_text)

    _maybe_add_to_content_calendar(story, generated, full_text)


def _maybe_insert_new_players(full_text: str, score: int) -> None:
    if score < 7:
        return
    for player_name in _KNOWN_ELITE:
        if player_name in full_text:
            if not _player_exists_in_notion(player_name.title()):
                insert_player({
                    "name": player_name.title(),
                    "status": "Active",
                    "notes": f"Auto-added by TipStar on {datetime.utcnow().strftime('%Y-%m-%d')}",
                })


def _maybe_insert_drama(story: dict, generated: dict, full_text: str) -> None:
    if not any(signal in full_text for signal in _DRAMA_SIGNALS):
        return
    title = story.get("title", "")
    if not title or _drama_exists_in_notion(title):
        return

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
    import re
    if not any(re.search(p, full_text) for p in _SCORE_PATTERNS):
        return
    insert_match_result({
        "home_team": "",
        "away_team": "",
        "tournament": "2026 FIFA World Cup",
        "key_events": story.get("title", ""),
        "match_date": datetime.utcnow().isoformat(),
    })


def _maybe_add_to_content_calendar(story: dict, generated: dict, full_text: str) -> None:
    """Add generated posts to the Content Calendar if relevance >= 6."""
    score = generated.get("relevance_score", 0)
    if score < 6:
        return

    posts = generated.get("posts", [])
    if not posts:
        return

    is_wc = generated.get("is_world_cup", False)
    content_type = _infer_content_type(full_text)
    priority = "High" if score >= 8 else "Medium" if score >= 6 else "Low"
    target_date = datetime.utcnow().date().isoformat()

    for post in posts[:2]:  # limit to top 2 posts per story to avoid calendar spam
        post_text = post.get("content", "") if isinstance(post, dict) else str(post)
        if not post_text:
            continue

        platform = "X Post"
        if post_text.count("\n") > 3 or len(post_text) > 280:
            platform = "Thread"

        insert_content_calendar_entry({
            "post_idea": post_text[:500],  # Notion title limit
            "status": "Idea",
            "platform": platform,
            "content_type": "World Cup Narrative" if is_wc else content_type,
            "priority": priority,
            "target_date": target_date,
            "notes": f"Auto-generated from: {story.get('title', '')[:200]}",
        })
