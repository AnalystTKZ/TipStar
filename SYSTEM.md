# TipStar — System Documentation

## What It Is

TipStar is a semi-automated football content platform built for a global X (Twitter) account. Its job is to monitor the football news cycle, understand what is happening in the world of football using a curated knowledge base, generate opinionated X posts from that context using an LLM, route them through a human approval step, and publish the approved posts to X.

The operator uses Notion as their editorial workspace — players, teams, tournaments, drama, and a content calendar all live there. TipStar reads from Notion, keeps a Supabase database in sync, enriches that data with live scraped facts, and writes discoveries back to Notion automatically.

---

## Architecture Overview

```
NOTION (editorial workspace)
    │  read / write
    ▼
SUPABASE (live operational database)
    │  semantic search via pgvector
    ▼
FASTAPI BACKEND ─── GROQ LLM (generation)
    │
    ▼
REACT FRONTEND (operator dashboard)
    │
    ▼
X / TWITTER (published posts)
```

The system has five major subsystems:

1. **Harvester** — collects incoming football news from external sources
2. **Knowledge Base** — stores curated data about players, teams, tournaments, and drama
3. **Enrichment + Generation** — embeds news semantically, retrieves relevant context, generates posts via Groq
4. **Approval Pipeline** — routes generated posts through human review before publishing
5. **Sync Layer** — keeps player, team, match, and tournament data fresh from live APIs and scrapers

---

## Subsystem Breakdown

### 1. Harvester

**Purpose:** Pull fresh football news every cycle so the generation pipeline always has material to work from.

**Sources:**
- **NewsAPI** — queries a broad football keyword set (World Cup, Champions League, Haaland, Messi, Mbappe, etc.) for articles published in the last 6 hours
- **RSS feeds** — polls Man City, UEFA, FIFA, Sky Sports, and ESPN RSS feeds for the last 6 hours

**Deduplication:** Title-based fuzzy dedup so the same story from multiple outlets does not generate duplicate posts.

**Trigger:** Manual "Fetch latest" button on the Command Center, or triggered automatically at the start of a generation run.

**Key files:**
- `backend/harvester/harvest.py` — aggregates all sources, deduplicates, returns normalised list
- `backend/harvester/newsapi_harvester.py` — NewsAPI client
- `backend/harvester/rss_harvester.py` — RSS feed parser
- `backend/harvester/deduplicator.py` — title similarity dedup

---

### 2. Knowledge Base

**Purpose:** Give the LLM real, curated context so generated posts contain accurate names, stats, tier judgements, and ongoing storylines — not hallucinated generics.

The knowledge base is maintained in **Notion** by the operator and synced to **Supabase** so the backend can query it at speed via pgvector semantic search.

#### Tables

| Table | What it stores |
|---|---|
| `players` | Name, club, nationality, position, tier (T1/T2/T3), age, WC appearances, WC goals, status, notes |
| `teams` | Name, country, league, manager, WC group, WC status, playing style, priority, notes |
| `tournaments` | Name, type, status, host country, dates, current stage, leader, top scorer, coverage priority |
| `matches` | Fixtures and results for 7 tracked competitions — scores, stage, scorers, coverage status |
| `drama` | Ongoing controversies, bans, feuds, and incidents — severity, summary, status |
| `news` | All harvested articles with full-text and 384-dim embeddings |
| `posts` | Every generated X post — content, type, relevance score, status, timestamps |
| `world_cup_groups` | Live WC group standings |
| `world_cup_squads` | WC squad lists per nation |

#### Tiering system

Players are manually tiered in Notion:
- **Tier 1 Superstar** — Messi, Ronaldo, Haaland, Mbappe, Vinicius etc. Maximum content priority.
- **Tier 2 Elite** — De Bruyne, Bellingham, Rodri, Salah etc. High priority.
- **Tier 3 Notable** — Solid professionals worth covering but not the headline name.

Teams have a **priority** field (High / Medium / Low) used to rank them in the dashboard and weight their presence in generation context.

#### Notion databases

The system reads from and writes to six Notion databases discovered dynamically via the registry (no hardcoded IDs required after initial setup):

| Database | Used for |
|---|---|
| Players | Read player profiles, write new elite players auto-detected in news |
| Teams | Read team profiles, write WC status updates |
| Drama Log | Read ongoing storylines, write newly detected controversies |
| Tournaments & Events | Read tournament context |
| World Cup 2026 | Read/write match results and coverage status |
| Content Calendar | Write generated post ideas for editorial review |

**Key files:**
- `backend/harvester/notion_harvester.py` — all Notion read/write/update operations
- `backend/harvester/notion_registry.py` — dynamic DB ID discovery via Notion search API
- `backend/database/models.py` — SQLAlchemy ORM models
- `backend/database/db.py` — all async database operations

---

### 3. Enrichment + Generation

This is the core intelligence of the system.

#### Enrichment

Before a news story is passed to Groq, it is enriched with context pulled from the knowledge base using **semantic similarity search** (pgvector cosine distance on 384-dim MiniLM embeddings).

For each story, the enricher retrieves:

1. **Similar past news** (top 5 by cosine similarity, similarity ≥ 0.5) — so Groq knows what has already been covered and avoids repeating the same angles
2. **Related players** (top 5) — injected with tier, club, nationality, WC appearances, and WC goals
3. **Related teams** (top 3) — injected with league, priority, WC group, and editorial notes
4. **Active/upcoming tournaments** — full current context: stage, leader, top scorer
5. **Related drama entries** (top 3) — ongoing storylines that might be referenced

This context is injected into the Groq prompt as structured sections.

**Key files:**
- `backend/embeddings/miniLM.py` — MiniLM `all-MiniLM-L6-v2` model wrapper (384-dim, CPU)
- `backend/embeddings/enricher.py` — builds the full context dict for each story
- `backend/embeddings/similarity.py` — pgvector similarity search functions

#### Generation

Groq (`llama3-70b-8192` by default) receives the system prompt and the enriched story and returns a structured JSON bundle with up to 4 post variants:

| Post type | Format | Limit |
|---|---|---|
| **Hot Take** (post_a) | Bold, opinionated, debate-starting | 200 chars |
| **Data & Stats** (post_b) | Stat-led, number-first, factual | 250 chars |
| **Tactical / Contextual** (post_c) | Zoomed-out analysis, thread-worthy | 280 chars |
| **World Cup Narrative** (post_d) | Emotional, legacy-focused storytelling | 280 chars — WC stories only |

Each bundle also includes:
- `relevance_score` (1–10) — stories below threshold (default 5) are discarded
- `is_world_cup` flag
- Hashtag suggestions (3–5 per post)
- Best time to post recommendation

The **relevance scoring** follows a tiered priority:
- 9–10: World Cup match results, Messi/Ronaldo content
- 7–8: UCL results, Haaland/Mbappe/Bellingham, confirmed transfers
- 5–6: Major league results, top-6 club news
- 1–4: Discarded

After generation, content embeddings are computed so future similarity searches can avoid repeating post angles.

**Write-back to Notion:** After generation, the orchestrator automatically:
- Inserts newly mentioned elite players not yet in the Notion Players database
- Logs detected controversies (bans, red cards, scandals) to the Drama Log
- Adds World Cup match results to the Notion matches database
- Pushes generated post ideas to the Content Calendar

**Key files:**
- `backend/generator/groq_generator.py` — Groq API client, JSON parsing, embedding
- `backend/generator/prompt.py` — system prompt and user prompt builder
- `backend/scheduler/orchestrator.py` — full pipeline: harvest → enrich → generate → persist → write-back

---

### 4. Approval Pipeline

All generated posts land in the `posts` table with `status = pending`. Nothing goes to X without a human decision.

#### Post statuses

```
pending → approved → posted
pending → rejected
```

#### Operator workflow

1. **Command Center** — operator fetches latest news, generates posts (configurable: how many stories, minimum relevance score), and publishes approved posts to X — all from one screen
2. **Approval Inbox** — full queue of pending posts grouped by story. Each post shows its type badge, relevance score, char count, and hashtags. Actions per post: approve, reject, edit-then-approve, delete. Bulk approve available. "Generate more" button directly in the inbox.
3. **Post History** — all posts with `status = posted`, filterable by type, WC flag, and date range

#### Publishing

`POST /api/posts/publish` runs the publisher which:
1. Fetches all `approved` posts not yet posted
2. Posts each to X via the Tweepy v2 client (`create_tweet`)
3. Marks each as `posted` and records `posted_at`
4. Auto-truncates to 277 chars + `...` if content exceeds 280

**Key files:**
- `backend/api/routes/posts.py` — all post endpoints including generate and publish
- `backend/scheduler/publisher.py` — Tweepy X client and publish loop
- `frontend/src/pages/CommandCenter.jsx` — generate + publish controls
- `frontend/src/pages/ApprovalInbox.jsx` — approval queue with editing
- `frontend/src/pages/PostHistory.jsx` — published post log

---

### 5. Sync Layer

Keeps player facts, match data, and tournament standings accurate without manual effort.

#### Player sync

Pulls live facts for every player in the database from Transfermarkt (primary), FBref (fallback/supplement), and API-Football (optional, paid plan only).

Fields overwritten: `current_club`, `age`, `status`, `nationality`, `world_cup_appearances`, `world_cup_goals`
Fields never touched: `notes`, `tier`, `content_angle`, `instagram_followers` — editorial decisions

After updating Supabase, it mirrors the changes to the corresponding Notion page.

Runs as a fire-and-forget background task (~2 minutes for a full roster sync due to Transfermarkt rate limiting).

#### Team sync

Same pattern as player sync — updates factual fields, mirrors to Notion.

#### Match sync

Pulls fixtures and results for 7 tracked competitions from football-data.org (primary) or API-Football (fallback):
- FIFA World Cup 2026
- UEFA Champions League
- Premier League, La Liga, Bundesliga, Serie A, Ligue 1

World Cup matches are also synced to the Notion World Cup 2026 database. Editorial coverage statuses (`Covered`, `Scheduled`) are never overwritten.

#### Tournament sync

Pulls live data from football-data.org for every tournament in the database that has a matching competition code. Updates: `current_stage`, `current_leader`, `matches_played`, `top_scorer`, `status`.

Also pulls World Cup squad data into `world_cup_squads` when a WC tournament is tracked.

**Supported tournament aliases:** World Cup, UCL, Premier League, La Liga, Bundesliga, Serie A, Ligue 1, Eredivisie, Primera Liga — all normalised to football-data.org competition codes.

#### World Cup sync

Dedicated sync for WC group standings and squad lists. Pulls from football-data.org `/competitions/WC/standings` and `/competitions/WC/teams`. Updates `world_cup_groups` and `world_cup_squads` tables and mirrors team WC status back to Notion.

**Key files:**
- `backend/sync/player_sync.py`
- `backend/sync/team_sync.py`
- `backend/sync/match_sync.py`
- `backend/sync/tournament_sync.py`
- `backend/sync/world_cup_sync.py`
- `backend/sync/football_data.py` — football-data.org client
- `backend/sync/transfermarkt.py` — Transfermarkt scraper
- `backend/sync/fallback.py` — API-Football client with football-data.org fallback chain
- `backend/sync/sync_logger.py` — logs each sync run to the database

---

## API Reference

All endpoints are prefixed `/api`.

### Posts
| Method | Path | Description |
|---|---|---|
| `GET` | `/posts/pending` | Fetch approval queue |
| `GET` | `/posts/approved` | Fetch approved unposted posts |
| `GET` | `/posts/history` | Fetch all posted content |
| `PATCH` | `/posts/{id}/approve` | Approve a post |
| `PATCH` | `/posts/{id}/reject` | Reject a post |
| `PATCH` | `/posts/{id}/edit` | Edit content and approve in one step |
| `DELETE` | `/posts/{id}` | Delete a post |
| `POST` | `/posts/generate` | Run recent news through Groq (fire-and-forget) |
| `POST` | `/posts/publish` | Post all approved content to X |

### News
| Method | Path | Description |
|---|---|---|
| `GET` | `/news` | Paginated news feed |
| `POST` | `/news/harvest` | Fetch and store latest news from all sources |

### Players / Teams / Tournaments
All three share the same pattern:

| Method | Path | Description |
|---|---|---|
| `GET` | `/{resource}` | List all |
| `GET` | `/{resource}/{id}` | Get one |
| `POST` | `/{resource}` | Create |
| `PATCH` | `/{resource}/{id}` | Update |
| `DELETE` | `/{resource}/{id}` | Delete |
| `POST` | `/{resource}/sync` | Fire-and-forget live sync from external APIs |
| `POST` | `/{resource}/import-from-notion` | Import from Notion database |

### Notion
| Method | Path | Description |
|---|---|---|
| `GET` | `/notion/databases` | List all discovered Notion databases |
| `POST` | `/notion/registry/reload` | Force re-discovery of Notion databases |
| `POST` | `/notion/import` | Import all data (players, teams, drama, tournaments) in one call |

### Analytics
| Method | Path | Description |
|---|---|---|
| `GET` | `/analytics/summary` | Today's totals: generated, approved, WC posts |
| `GET` | `/analytics/posts` | Posts over time (last 7 days) |
| `GET` | `/analytics/coverage` | WC vs non-WC coverage ratio |
| `GET` | `/analytics/types` | Breakdown by post type |
| `GET` | `/analytics/players` | Most mentioned players in generated content |

---

## Frontend Pages

| Page | Route | Purpose |
|---|---|---|
| Command Center | `/` | Dashboard overview: stats, generate controls, publish button, news feed, drama alerts |
| Approval Inbox | `/inbox` | Full pending queue grouped by story with editing, bulk approve, delete |
| Knowledge Base | `/knowledge` | Ranked lists of players, teams, tournaments, matches, drama, and trending topics — with add, delete, sync, and Notion import controls |
| Post History | `/history` | All published posts with type/date/WC filters |
| Analytics | `/analytics` | Charts: posts over time, coverage ratio, post type breakdown, top players |

---

## Environment Variables

| Variable | Required | Description |
|---|---|---|
| `SUPABASE_DB_URL` | Yes | PostgreSQL connection string (asyncpg-compatible) |
| `GROQ_API_KEY` | Yes | Groq API key for LLM generation |
| `NOTION_API_KEY` | Yes | Notion integration token |
| `NOTION_HQ_PAGE_ID` | Yes | Root Notion page — registry searches under this |
| `NEWS_API_KEY` | Yes | NewsAPI.org key for news harvesting |
| `FOOTBALL_DATA_KEY` | Yes | football-data.org API key for tournament/match sync |
| `TWITTER_API_KEY` | For publishing | X API v2 OAuth credentials |
| `TWITTER_API_SECRET` | For publishing | |
| `TWITTER_ACCESS_TOKEN` | For publishing | |
| `TWITTER_ACCESS_SECRET` | For publishing | |
| `TWITTER_BEARER_TOKEN` | For publishing | |
| `API_FOOTBALL_KEY` | Optional | API-Football key (paid plan for player stats) |
| `GROQ_MODEL` | Optional | Defaults to `llama3-70b-8192` |
| `MIN_RELEVANCE_SCORE` | Optional | Default 5 — stories below this are discarded |
| `ENABLE_API_FOOTBALL_PLAYER_SYNC` | Optional | Set `true` to enable paid API-Football player sync |
| `ENABLE_FBREF_PLAYER_SYNC` | Optional | Set `true` to enable FBref as a player sync source |

---

## Data Flow — End to End

```
1. HARVEST
   NewsAPI + RSS feeds → deduplicated stories list

2. STORE
   Stories inserted into news table (deduplicated by URL)

3. ENRICH
   Each story title+description → MiniLM 384-dim embedding
   pgvector similarity search retrieves:
     - 5 similar past news items (avoid repeating angles)
     - 5 related players (with tier, club, WC stats)
     - 3 related teams (with priority, WC group, notes)
     - All active/upcoming tournaments (stage, leader, scorer)
     - 3 related drama entries (severity, summary, status)

4. GENERATE
   System prompt + enriched context → Groq llama3-70b-8192
   Returns JSON: relevance score, is_world_cup, 3–4 post variants
   Posts below MIN_RELEVANCE_SCORE are discarded

5. PERSIST
   Post variants inserted into posts table with status=pending
   Post content embedded and stored for future similarity checks
   Write-back to Notion: new players, drama, match results, calendar entries

6. APPROVE
   Operator reviews posts in Approval Inbox
   Can edit content inline, check char count, approve, reject, or delete
   Bulk approve available for time-sensitive batches

7. PUBLISH
   POST /api/posts/publish → Tweepy v2 create_tweet
   Status updated to posted, posted_at recorded
```

---

## Key Design Decisions

**Why Notion as the editorial layer?**
The operator already uses Notion to track players, teams, and storylines. Treating it as the source of truth for editorial decisions (tiers, priorities, notes) means data entry happens in a familiar interface, not a custom admin panel.

**Why Supabase as the operational database?**
Supabase provides managed Postgres with the pgvector extension, which enables the semantic similarity search that powers contextual generation. It is the fast operational layer — Notion is the editorial layer.

**Why MiniLM for embeddings?**
`all-MiniLM-L6-v2` is fast, CPU-runnable, and produces 384-dimensional vectors well-suited for semantic similarity in a football news domain. No GPU required. Loads once at startup and is reused across all requests.

**Why fire-and-forget sync?**
Transfermarkt enforces a ~2s rate delay per request. Syncing 35+ players synchronously would exceed a 15s API timeout. Background `asyncio.create_task()` lets syncs run to completion in their own task without blocking the request.

**Why human approval before publishing?**
LLMs make mistakes. The account's reputation depends on not posting inaccurate stats or poorly timed takes. The approval step is intentionally lightweight (one click to approve) to keep friction low while ensuring a human sees every post before it goes live.

**Why Groq instead of OpenAI?**
Speed. Groq's LPU inference is fast enough that a generation run over 20 stories takes seconds rather than minutes, which matters when responding to breaking news.
