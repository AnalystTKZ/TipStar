# TipStar X Post Templates

These templates are designed for reusable TipStar visuals. The Python renderer
in `backend/visuals/social_templates.py` can create the PNGs directly with
Pillow, so approved posts can later receive a matching image automatically.

## Brand Tokens

- Brand: `TipStar`
- Wordmark: `TIPSTAR`
- Handle: `@TipStar`
- Navy: `#1C2C5B`
- Light navy: `#243357`
- Dark: `#0A0F1E`
- Sky blue: `#6CABDD`
- Gold: `#FFD700`
- White: `#FFFFFF`
- Gray: `#A8B0C3`
- Font target: Inter or Helvetica. Renderer fallback: Liberation Sans.
- Logo source: `frontend/src/logos/logo.png`

## Templates

### 1. Standard Post

Use for stats/data/context posts.

- Size: `1080x1080`
- Background: navy
- Top and bottom sky-blue accent lines
- TipStar logo lockup top left
- Subtle logo watermark and pitch-line texture
- Sky-blue motion slashes top right
- Large white main text
- Bottom-left sky-blue stat box
- Bottom-right handle

Renderer:

```python
from backend.visuals import StandardPostPayload, render_standard_post

render_standard_post(StandardPostPayload(
    content="Haaland has now scored in four straight home games for City.",
    stat_number="4",
    stat_label="straight home games",
))
```

### 2. World Cup Special

Use for World Cup 2026 posts.

- Size: `1080x1080`
- Background: navy
- Subtle gold center glow
- Trophy icon and `WORLD CUP 2026` header
- Gold divider and bottom accent
- Flag/context placeholders
- Gold score/stat highlight

Renderer:

```python
from backend.visuals import StandardPostPayload, render_world_cup_special

render_world_cup_special(
    StandardPostPayload(content="Argentina open their World Cup defence with Messi still central."),
    flags=("ARG", "TBC"),
    score_or_stat="GROUP STAGE",
)
```

### 3. Hot Take

Use for bold opinionated posts.

- Size: `1080x1080`
- Background: near-black
- Full-height sky-blue vertical bar
- `HOT TAKE` label and underline
- Large italic white main text
- Football icon bottom left
- Handle at bottom

Renderer:

```python
from backend.visuals import render_hot_take

render_hot_take("City losing Pep one day will hurt the league more than people want to admit.")
```

### 4. Player Spotlight

Use for player profile/stat cards.

- Size: `1080x1080`
- Split layout
- Left: navy text/stat column
- Right: lighter navy image placeholder
- Sky-blue divider and circular image border
- 2x2 stat grid

Renderer:

```python
from backend.visuals import PlayerSpotlightPayload, render_player_spotlight

render_player_spotlight(PlayerSpotlightPayload(
    player_name="Phil Foden",
    position_club="MID | Manchester City",
    stats=(("22", "starts"), ("8", "goals"), ("6", "assists"), ("92%", "pass acc")),
))
```

### 5. Match Result

Use for match result posts.

- Size: `1080x1350`
- Background: near-black
- Competition label top center
- Large centered team/score layout
- White score box
- Team-specific scorers/events and match stats under the correct team
- Man of the match highlight box

Renderer:

```python
from backend.visuals import MatchResultPayload, render_match_result

render_match_result(MatchResultPayload(
    competition="Premier League",
    home_team="Man City",
    away_team="Arsenal",
    score="2-1",
    home_events=("12' Haaland", "78' Foden"),
    away_events=("44' Saka",),
    home_stats=(("shots", "14"), ("xG", "1.8"), ("possession", "58%")),
    away_stats=(("shots", "9"), ("xG", "0.9"), ("possession", "42%")),
    player_of_match="Phil Foden",
))
```

## Example Render Command

```bash
cd /home/tybobo/Desktop/TipStar/tipstar
.venv/bin/python3 -m backend.visuals.render_examples
```

Outputs:

```text
generated/visuals/examples/
```

## Next Integration Step

When a post is approved, TipStar should select a template from `post_type`:

- `data_stats` -> Standard Post
- `hot_take` -> Hot Take
- `wc_narrative` -> World Cup Special
- match result stories -> Match Result
- player-led stories -> Player Spotlight

The generated image path can then be stored on the post row and passed into the
publisher when posting to X.
