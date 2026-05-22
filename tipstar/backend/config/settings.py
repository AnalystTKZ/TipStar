import os
from dotenv import load_dotenv

load_dotenv()

# --- API Keys ---
NEWS_API_KEY = os.getenv("NEWS_API_KEY")
GROQ_API_KEY = os.getenv("GROQ_API_KEY")
GROQ_MODEL = os.getenv("GROQ_MODEL", "llama3-70b-8192")

# --- Twitter / X ---
TWITTER_API_KEY = os.getenv("TWITTER_API_KEY")
TWITTER_API_SECRET = os.getenv("TWITTER_API_SECRET")
TWITTER_ACCESS_TOKEN = os.getenv("TWITTER_ACCESS_TOKEN")
TWITTER_ACCESS_SECRET = os.getenv("TWITTER_ACCESS_SECRET")
TWITTER_BEARER_TOKEN = os.getenv("TWITTER_BEARER_TOKEN")

# --- Database ---
SUPABASE_DB_URL = os.getenv("SUPABASE_DB_URL")

# --- Notion ---
NOTION_API_KEY = os.getenv("NOTION_API_KEY")
NOTION_HQ_PAGE_ID = os.getenv("NOTION_HQ_PAGE_ID", "3688031e4fc981acb97ef602b52eeb7f")
# Legacy explicit IDs -- used as fallback if registry discovery fails
NOTION_PLAYERS_DB_ID = os.getenv("NOTION_PLAYERS_DB_ID")
NOTION_TEAMS_DB_ID = os.getenv("NOTION_TEAMS_DB_ID")
NOTION_DRAMA_DB_ID = os.getenv("NOTION_DRAMA_DB_ID")
NOTION_CONFIG_PAGE_ID = os.getenv("NOTION_CONFIG_PAGE_ID")
NOTION_MATCHES_DB_ID = os.getenv("NOTION_MATCHES_DB_ID")
NOTION_CONTENT_CALENDAR_DB_ID = os.getenv("NOTION_CONTENT_CALENDAR_DB_ID")

# --- API Sync ---
API_FOOTBALL_KEY = os.getenv("API_FOOTBALL_KEY")
API_FOOTBALL_HOST = os.getenv("API_FOOTBALL_HOST", "api-sports.io")
FOOTBALL_DATA_KEY = os.getenv("FOOTBALL_DATA_KEY")

# --- Frontend ---
FRONTEND_ORIGIN = os.getenv("FRONTEND_ORIGIN", "http://localhost:5173")

# --- Harvester ---
NEWSAPI_FOOTBALL_QUERY = (
    "football OR soccer OR FIFA OR 'World Cup' OR 'Premier League' "
    "OR 'Champions League' OR Haaland OR Messi OR Ronaldo OR Mbappe"
)
NEWSAPI_PAGE_SIZE = 30
NEWSAPI_LANGUAGE = "en"

RSS_FEEDS = [
    "https://www.mancity.com/rss",
    "https://www.uefa.com/rssfeed/newsrss.xml",
    "https://www.fifa.com/rss.xml",
    "https://feeds.skysports.com/skysports/football/news",
    "https://www.espn.com/espn/rss/soccer/news",
]

# --- Relevance threshold ---
MIN_RELEVANCE_SCORE = 5

# --- Scheduling intervals (minutes) ---
HARVEST_INTERVAL_MINUTES = 30
NOTION_SYNC_INTERVAL_MINUTES = 360
