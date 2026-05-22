"""
Transfermarkt scraper for player facts.
Scrapes current club, age, market value, injury/suspension status,
nationality, position, and contract expiry directly from Transfermarkt profiles.

Rate limit: 1 request per 2 seconds -- self-imposed to be respectful.
"""
import logging
import re
import time
from typing import Optional
from urllib.parse import quote

import requests
from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)

_BASE = "https://www.transfermarkt.com"
_SEARCH_URL = "https://www.transfermarkt.com/schnellsuche/ergebnis/schnellsuche"
_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "en-US,en;q=0.9",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
}
_RATE_DELAY = 2.0


def _get(url: str) -> Optional[BeautifulSoup]:
    try:
        time.sleep(_RATE_DELAY)
        resp = requests.get(url, headers=_HEADERS, timeout=20)
        if resp.status_code != 200:
            logger.warning("Transfermarkt HTTP %s: %s", resp.status_code, url)
            return None
        return BeautifulSoup(resp.text, "html.parser")
    except Exception as exc:
        logger.warning("Transfermarkt request error for %s: %s", url, exc)
        return None


def _search_player_url(name: str) -> Optional[str]:
    """
    Search Transfermarkt for a player by name.
    Returns the profile URL of the top result, or None.
    """
    soup = _get(f"{_SEARCH_URL}?query={quote(name)}")
    if not soup:
        return None

    # Player results are in a table with class "items" inside the players section
    for table in soup.select("table.items"):
        header = table.find_previous("h2")
        if header and "player" in header.get_text(strip=True).lower():
            first_row = table.select_one("tbody tr.odd, tbody tr.even")
            if first_row:
                link = first_row.select_one("td.hauptlink a[href*='/profil/spieler/']")
                if link and link.get("href"):
                    href = link["href"]
                    return f"{_BASE}{href}" if not href.startswith("http") else href

    # Fallback: any link matching the spieler profile pattern
    link = soup.select_one("a[href*='/profil/spieler/']")
    if link and link.get("href"):
        href = link["href"]
        return f"{_BASE}{href}" if not href.startswith("http") else href

    return None


def _search_club_url(name: str) -> Optional[str]:
    """
    Search Transfermarkt for a club by name.
    Returns the club profile URL of the top result, or None.
    """
    soup = _get(f"{_SEARCH_URL}?query={quote(name)}")
    if not soup:
        return None

    for table in soup.select("table.items"):
        header = table.find_previous("h2")
        header_text = header.get_text(" ", strip=True).lower() if header else ""
        if any(word in header_text for word in ["club", "verein"]):
            first_row = table.select_one("tbody tr.odd, tbody tr.even")
            if first_row:
                link = first_row.select_one("td.hauptlink a[href*='/startseite/verein/']")
                if link and link.get("href"):
                    href = link["href"]
                    return f"{_BASE}{href}" if not href.startswith("http") else href

    link = soup.select_one("a[href*='/startseite/verein/']")
    if link and link.get("href"):
        href = link["href"]
        return f"{_BASE}{href}" if not href.startswith("http") else href

    return None


def _parse_market_value(text: str) -> Optional[int]:
    """Convert '€120m', '€45.50m', '€800k' etc. to integer euros."""
    if not text:
        return None
    text = text.strip().replace(",", ".")
    m = re.search(r"[\d.]+", text)
    if not m:
        return None
    num = float(m.group())
    if "bn" in text.lower():
        return int(num * 1_000_000_000)
    if "m" in text.lower():
        return int(num * 1_000_000)
    if "k" in text.lower():
        return int(num * 1_000)
    return int(num)


def _info_value(soup: BeautifulSoup, label: str) -> tuple[Optional[str], Optional[BeautifulSoup]]:
    """Return a Transfermarkt info-table value by its left-hand label."""
    wanted = label.strip().lower().rstrip(":")
    cells = soup.select(".info-table__content")
    for idx, cell in enumerate(cells):
        text = cell.get_text(" ", strip=True).lower().rstrip(":")
        if text == wanted and idx + 1 < len(cells):
            value = cells[idx + 1]
            return value.get_text(" ", strip=True) or None, value
    return None, None


def get_player(name: str) -> Optional[dict]:
    """
    Search Transfermarkt for a player by name and return normalised facts.

    Returns dict with keys:
        name, current_club, age, nationality, position,
        market_value_eur, status, contract_until
    or None if not found / scraping failed.
    """
    profile_url = _search_player_url(name)
    if not profile_url:
        logger.debug("Transfermarkt: no profile URL found for '%s'", name)
        return None

    soup = _get(profile_url)
    if not soup:
        return None

    result: dict = {"name": name}

    # --- Current club ---
    club_text, _club_cell = _info_value(soup, "Current club")
    if not club_text:
        club_el = soup.select_one("span[itemprop='affiliation'] a, .data-header__club a")
        if not club_el:
            club_el = soup.select_one("a[href*='/startseite/verein/']")
        club_text = club_el.get_text(strip=True) if club_el else None
    result["current_club"] = club_text

    # --- Age ---
    born_text, _born_cell = _info_value(soup, "Date of birth/Age")
    if not born_text:
        born_el = soup.select_one("span[itemprop='birthDate'], .data-header__born")
        born_text = born_el.get_text(" ", strip=True) if born_el else None
    if born_text:
        age_match = re.search(r"\((\d+)\)", born_text)
        if age_match:
            result["age"] = int(age_match.group(1))

    # --- Nationality ---
    nationality, nationality_cell = _info_value(soup, "Citizenship")
    if nationality_cell:
        flag = nationality_cell.select_one("img.flaggenrahmen")
        nationality = flag.get("title") if flag and flag.get("title") else nationality
    if not nationality:
        nat_el = soup.select_one("span[itemprop='nationality']")
        nationality = nat_el.get_text(strip=True) if nat_el else None
    result["nationality"] = nationality

    # --- Position ---
    position, _position_cell = _info_value(soup, "Position")
    if not position:
        pos_el = soup.select_one("dd.detail-position__position, span[itemprop='jobTitle']")
        position = pos_el.get_text(strip=True) if pos_el else None
    result["position"] = position

    # --- Market value ---
    mv_el = soup.select_one("a.data-header__market-value-wrapper, .marktwert-box .right-td")
    if mv_el:
        result["market_value_eur"] = _parse_market_value(mv_el.get_text(strip=True))

    # --- Contract expiry ---
    contract_until, _contract_cell = _info_value(soup, "Contract expires")
    if contract_until:
        result["contract_until"] = contract_until

    # --- Injury / suspension status ---
    status = "Active"
    injury_banner = soup.select_one(
        ".verletzungsbox, .tm-injury-widget, .data-header__absence, "
        ".data-header__verletzung, [data-injury]"
    )
    if injury_banner:
        banner_text = injury_banner.get_text(strip=True).lower()
        if "suspen" in banner_text or "red card" in banner_text:
            status = "Suspended"
        elif banner_text:
            status = "Injured"
    result["status"] = status

    logger.debug("Transfermarkt: fetched %s -> %s", name, result)
    return result


def get_club(name: str) -> Optional[dict]:
    """
    Search Transfermarkt for a club by name and return normalised club facts.

    Returns dict with keys:
        name, country, league, manager, notes
    or None if not found / scraping failed.
    """
    profile_url = _search_club_url(name)
    if not profile_url:
        logger.debug("Transfermarkt: no club URL found for '%s'", name)
        return None

    soup = _get(profile_url)
    if not soup:
        return None

    heading = soup.select_one("h1.data-header__headline-wrapper, h1")
    result: dict = {
        "name": heading.get_text(" ", strip=True) if heading else name,
    }

    league_el = soup.select_one(".data-header__club-info a[href*='/startseite/wettbewerb/']")
    if not league_el:
        league_el = soup.select_one("a[href*='/startseite/wettbewerb/']")
    if league_el:
        result["league"] = league_el.get_text(" ", strip=True) or None

    country = None
    level = soup.select_one(".data-header__label img.flaggenrahmen, .data-header__content img.flaggenrahmen")
    if level and level.get("title"):
        country = level["title"]
    if not country:
        official_address, official_cell = _info_value(soup, "Address")
        if official_cell:
            flags = [img.get("title") for img in official_cell.select("img.flaggenrahmen") if img.get("title")]
            if flags:
                country = flags[-1]
            else:
                lines = [line.strip() for line in official_cell.stripped_strings if line.strip()]
                if lines:
                    country = lines[-1]
        elif official_address:
            country = official_address.split()[-1]
    result["country"] = country

    manager, _manager_cell = _info_value(soup, "Manager")
    if manager:
        result["manager"] = manager

    notes = []
    for label in ["Squad size", "Average age", "Stadium", "Current transfer record"]:
        value = _data_header_value(soup, label)
        if value:
            notes.append(f"{label}: {value}")
    if notes:
        result["notes"] = " | ".join(notes)

    logger.debug("Transfermarkt: fetched club %s -> %s", name, result)
    return result


def _data_header_value(soup: BeautifulSoup, label: str) -> Optional[str]:
    wanted = label.strip().lower()
    for item in soup.select(".data-header__label"):
        text = item.get_text(" ", strip=True)
        if not text.lower().startswith(wanted):
            continue
        if ":" in text:
            value = text.split(":", 1)[1].strip()
            if value:
                return value
        content = item.find_next_sibling(class_="data-header__content")
        if content:
            return content.get_text(" ", strip=True) or None
    return None
