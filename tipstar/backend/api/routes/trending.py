"""
Trending entities endpoint.

Scans recent news (DB first, live fetch fallback) for player/club/event
mentions not already in the knowledge base, ranked by mention frequency.
"""
import logging
import re
from collections import defaultdict
from datetime import datetime, timedelta

from fastapi import APIRouter, Depends
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from backend.database.db import get_db
from backend.database.models import News, Player, Team

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/trending", tags=["trending"])

# ---------------------------------------------------------------------------
# Entity dictionaries
# These are matched against news text. Extend freely -- no code changes needed
# for new names, just add to the list.
# ---------------------------------------------------------------------------

_PLAYERS = [
    # World Cup 2026 superstars
    "Lionel Messi", "Cristiano Ronaldo", "Kylian Mbappé", "Kylian Mbappe",
    "Erling Haaland", "Vinicius Jr", "Vinicius Junior", "Jude Bellingham",
    "Neymar", "Pedri", "Gavi", "Lamine Yamal", "Rodri", "Kevin De Bruyne",
    "Mohamed Salah", "Harry Kane", "Bukayo Saka", "Marcus Rashford",
    "Phil Foden", "Declan Rice", "Jamal Musiala", "Florian Wirtz",
    "Federico Valverde", "Vinícius Júnior", "Raphinha", "Rodrygo",
    "Antoine Griezmann", "Ousmane Dembélé", "Ousmane Dembele",
    "Leroy Sane", "Leroy Sané", "Serge Gnabry", "Thomas Müller", "Thomas Muller",
    "Robert Lewandowski", "Wojciech Szczesny",
    "Achraf Hakimi", "Hakim Ziyech", "Riyad Mahrez",
    "Sadio Mané", "Sadio Mane", "Kalidou Koulibaly",
    "Victor Osimhen", "Ademola Lookman",
    "Son Heung-min", "Takumi Minamino", "Ritsu Doan",
    "Christian Pulisic", "Weston McKennie", "Tyler Adams",
    "Alphonso Davies", "Jonathan David",
    "Julian Alvarez", "Alexis Mac Allister", "Enzo Fernandez",
    "Cody Gakpo", "Memphis Depay", "Virgil van Dijk",
    "Bruno Fernandes", "Bernardo Silva", "Diogo Jota", "Ruben Dias",
    "Pedri González", "Yamal", "Ferran Torres",
    "Trent Alexander-Arnold", "Trent Arnold",
    "Jack Grealish", "Kyle Walker", "John Stones", "Ruben Dias",
    "Ederson", "Alisson", "Marc-André ter Stegen",
    "Xavi", "Iniesta", "Zlatan Ibrahimovic",
    "Dani Carvajal", "Luka Modric", "Toni Kroos",
    "Karim Benzema", "Marco Asensio",
    "Nicolo Barella", "Federico Chiesa", "Gianluigi Donnarumma",
    "Rafael Leão", "Rafael Leao", "Theo Hernandez",
    "Khvicha Kvaratskhelia", "Victor Osimhen",
    "Oscar Bobb", "Savinho", "Matheus Nunes",
    "Luis Suarez", "Darwin Nunez", "Federico Valverde",
    "Endrick", "Estevao", "Estêvão",
    "Arda Güler", "Arda Guler",
    "Dominik Szoboszlai", "Martin Odegaard",
    "Cole Palmer", "Noni Madueke", "Nicolas Jackson",
    "Lautaro Martinez", "Marcus Thuram",
    "Evan Ferguson", "Ollie Watkins",
    "Joao Felix", "João Félix",
    "Gabriel Martinelli", "Leandro Trossard",
    "William Saliba", "Ben White",
]

_CLUBS = [
    "Manchester City", "Man City", "Real Madrid", "Barcelona", "Bayern Munich",
    "Liverpool", "Arsenal", "Chelsea", "Manchester United", "Man United",
    "Tottenham", "Spurs", "Atletico Madrid", "Atlético Madrid",
    "Inter Milan", "AC Milan", "Juventus", "Napoli",
    "PSG", "Paris Saint-Germain", "Borussia Dortmund", "BVB",
    "Porto", "Benfica", "Ajax", "Bayer Leverkusen",
    "RB Leipzig", "Sevilla", "Valencia", "Real Sociedad",
    "Lazio", "Roma", "Fiorentina", "Atalanta",
    "Newcastle", "Aston Villa", "West Ham", "Brentford",
    "Brighton", "Fulham", "Wolves", "Everton",
    "Celtic", "Rangers", "Marseille", "Lyon", "Monaco",
    "Al Nassr", "Al Hilal", "Inter Miami",
]

_EVENTS = [
    # Major international tournaments
    "World Cup 2026", "FIFA World Cup", "World Cup",
    "Euro 2024", "Euro 2028", "UEFA Euro",
    "AFCON", "Africa Cup of Nations",
    "Copa America", "Gold Cup", "Asian Cup", "AFC Asian Cup",
    "Concacaf Nations League", "Olympic Games football",

    # Club competitions
    "Champions League", "UEFA Champions League", "UCL",
    "Europa League", "UEFA Europa League", "UEL",
    "Conference League", "UECL",
    "Club World Cup", "FIFA Club World Cup",
    "Super Cup", "UEFA Super Cup",

    # Domestic leagues
    "Premier League", "EPL",
    "La Liga",
    "Bundesliga",
    "Serie A",
    "Ligue 1",
    "Eredivisie",
    "Liga Portugal", "Primeira Liga",
    "Scottish Premiership",
    "MLS", "Major League Soccer",
    "Saudi Pro League",
    "J1 League",

    # Domestic cups
    "FA Cup", "Carabao Cup", "EFL Cup",
    "Copa del Rey",
    "DFB Pokal",
    "Coppa Italia",
    "Coupe de France",
    "Trophée des Champions",

    # Nations League
    "UEFA Nations League", "Nations League",

    # Transfer / off-pitch topics
    "transfer window", "transfer deadline", "summer transfer",
    "January transfer", "free agent", "contract extension",
    "managerial sacking", "manager appointed", "new signing",
    "release clause", "buyout clause",

    # Match events / awards
    "injury update", "suspension", "red card", "VAR",
    "hat trick", "hat-trick", "penalty shootout",
    "golden boot", "Ballon d'Or", "FIFA Best",
    "best XI", "player of the year",
]

# Normalise for matching (strip accents for fuzzy match)
def _ascii(s: str) -> str:
    import unicodedata
    return unicodedata.normalize("NFKD", s).encode("ascii", "ignore").decode().lower()

_PLAYER_INDEX = {_ascii(p): p for p in _PLAYERS}
_CLUB_INDEX   = {_ascii(c): c for c in _CLUBS}
_EVENT_INDEX  = {_ascii(e): e for e in _EVENTS}


def _scan_text(text_blob: str) -> dict[str, dict]:
    """
    Scan a blob of text for entity mentions.
    Returns {canonical_name: {type, count, ascii_key}}
    """
    blob_ascii = _ascii(text_blob)
    hits: dict[str, dict] = {}

    for ascii_key, canonical in _PLAYER_INDEX.items():
        if ascii_key in blob_ascii:
            if canonical not in hits:
                hits[canonical] = {"type": "player", "count": 0}
            hits[canonical]["count"] += blob_ascii.count(ascii_key)

    for ascii_key, canonical in _CLUB_INDEX.items():
        if ascii_key in blob_ascii:
            if canonical not in hits:
                hits[canonical] = {"type": "club", "count": 0}
            hits[canonical]["count"] += blob_ascii.count(ascii_key)

    for ascii_key, canonical in _EVENT_INDEX.items():
        if ascii_key in blob_ascii:
            if canonical not in hits:
                hits[canonical] = {"type": "event", "count": 0}
            hits[canonical]["count"] += blob_ascii.count(ascii_key)

    return hits


async def _get_known_names(session: AsyncSession) -> set[str]:
    """Return normalised names of all players and teams already in the DB."""
    p_result = await session.execute(select(Player.name))
    t_result = await session.execute(select(Team.name))
    known = set()
    for (name,) in p_result:
        known.add(_ascii(name))
    for (name,) in t_result:
        known.add(_ascii(name))
    return known


async def _fetch_recent_news_text(session: AsyncSession, days: int = 7) -> str:
    """Pull recent news titles + descriptions from DB."""
    since = datetime.utcnow() - timedelta(days=days)
    result = await session.execute(
        select(News.title, News.content)
        .where(News.created_at >= since)
        .order_by(News.created_at.desc())
        .limit(500)
    )
    parts = []
    for title, content in result:
        if title:
            parts.append(title)
        if content:
            parts.append(content[:300])
    return " ".join(parts)


def _live_fetch_text() -> str:
    """Fallback: fetch live news when DB is empty."""
    try:
        from backend.harvester.newsapi_harvester import fetch_newsapi_stories
        from backend.harvester.rss_harvester import fetch_rss_stories
        stories = fetch_newsapi_stories() + fetch_rss_stories()
        parts = []
        for s in stories:
            if s.get("title"):
                parts.append(s["title"])
            if s.get("description"):
                parts.append(s["description"][:300])
        return " ".join(parts)
    except Exception as exc:
        logger.warning("Live news fetch for trending failed: %s", exc)
        return ""


@router.get("")
async def get_trending(days: int = 7, limit: int = 30, db: AsyncSession = Depends(get_db)):
    """
    Return trending football entities not yet in the knowledge base.

    Query params:
        days  -- how many days of news to scan (default 7)
        limit -- max results to return (default 30)

    Response items: {name, type, mentions, in_db}
    """
    # Get text corpus
    text_blob = await _fetch_recent_news_text(db, days)
    source = "db"
    if len(text_blob) < 200:
        text_blob = _live_fetch_text()
        source = "live"

    if not text_blob:
        return {"items": [], "source": "none", "days": days}

    # Scan for mentions
    hits = _scan_text(text_blob)

    # Get known names to flag what's already in DB
    known = await _get_known_names(db)

    items = []
    for name, meta in hits.items():
        items.append({
            "name": name,
            "type": meta["type"],
            "mentions": meta["count"],
            "in_db": _ascii(name) in known,
        })

    # Sort by mentions desc, new entities first
    items.sort(key=lambda x: (-x["mentions"], x["in_db"]))
    items = items[:limit]

    return {"items": items, "source": source, "days": days, "total": len(hits)}
