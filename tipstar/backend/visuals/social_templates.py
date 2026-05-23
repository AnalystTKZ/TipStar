"""
Pillow renderers for TipStar social templates.

These are deterministic, flat-design templates that can be generated without
Canva/Midjourney. They are intentionally data-first so an approved post can be
turned into a matching PNG automatically.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from textwrap import wrap
from typing import Sequence

try:
    from PIL import Image, ImageDraw, ImageFont, ImageFilter
except ImportError as exc:  # pragma: no cover - import guard for optional runtime dependency
    raise RuntimeError(
        "Pillow is required for visual rendering. Install project requirements first."
    ) from exc


NAVY = "#1C2C5B"
LIGHT_NAVY = "#243357"
DARK = "#0A0F1E"
SKY = "#6CABDD"
GOLD = "#FFD700"
WHITE = "#FFFFFF"
GRAY = "#A8B0C3"
HANDLE = "@TipStar"
WORDMARK = "TIPSTAR"

ROOT = Path(__file__).resolve().parents[2]
OUTPUT_DIR = ROOT / "generated" / "visuals"
LOGO_PATH = ROOT / "frontend" / "src" / "logos" / "logo.png"

FONT_REGULAR = "/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf"
FONT_BOLD = "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf"
FONT_ITALIC = "/usr/share/fonts/truetype/liberation/LiberationSans-BoldItalic.ttf"


@dataclass
class RenderedTemplate:
    template: str
    path: Path
    width: int
    height: int


@dataclass
class StandardPostPayload:
    content: str
    stat_number: str = ""
    stat_label: str = ""
    template: str = "standard"


@dataclass
class PlayerSpotlightPayload:
    player_name: str
    position_club: str = ""
    stats: Sequence[tuple[str, str]] = field(default_factory=tuple)
    template: str = "player_spotlight"


@dataclass
class MatchResultPayload:
    competition: str
    home_team: str
    away_team: str
    score: str
    home_events: Sequence[str] = field(default_factory=tuple)
    away_events: Sequence[str] = field(default_factory=tuple)
    home_stats: Sequence[tuple[str, str]] = field(default_factory=tuple)
    away_stats: Sequence[tuple[str, str]] = field(default_factory=tuple)
    key_events: Sequence[str] = field(default_factory=tuple)
    player_of_match: str = ""
    template: str = "match_result"


def render_standard_post(
    payload: StandardPostPayload,
    output_path: str | Path | None = None,
) -> RenderedTemplate:
    img = Image.new("RGB", (1080, 1080), NAVY)
    draw = ImageDraw.Draw(img)

    _draw_pitch_lines(draw, 1080, 1080, SKY, opacity_color="#294070")
    _logo_watermark(img, (638, 164), 540, opacity=0.10)
    draw.rectangle((0, 0, 1080, 10), fill=SKY)
    draw.rectangle((0, 1070, 1080, 1080), fill=SKY)
    _corner_slashes(draw, 806, 64, SKY)
    _brand_lockup(img, draw, 72, 42, logo_size=56)

    _draw_wrapped_text(
        draw,
        payload.content,
        box=(72, 200, 880, 560),
        font_path=FONT_BOLD,
        max_size=78,
        min_size=42,
        fill=WHITE,
        spacing=14,
    )

    if payload.stat_number or payload.stat_label:
        draw.rounded_rectangle((72, 846, 390, 992), radius=12, fill=SKY)
        draw.rectangle((72, 846, 82, 992), fill=WHITE)
        _center_text(draw, payload.stat_number, (92, 862, 390, 920), FONT_BOLD, 52, WHITE)
        _center_wrapped_text(draw, payload.stat_label.upper(), (104, 922, 372, 978), FONT_BOLD, 21, WHITE)

    _handle(draw, 850, 942)
    path = _save(img, output_path, "standard_post.png")
    return RenderedTemplate("standard", path, 1080, 1080)


def render_world_cup_special(
    payload: StandardPostPayload,
    output_path: str | Path | None = None,
    flags: tuple[str, str] = ("", ""),
    score_or_stat: str = "",
) -> RenderedTemplate:
    img = Image.new("RGB", (1080, 1080), NAVY)
    glow = Image.new("RGBA", (1080, 1080), (0, 0, 0, 0))
    glow_draw = ImageDraw.Draw(glow)
    glow_draw.ellipse((230, 210, 850, 830), fill=(255, 215, 0, 34))
    img = Image.alpha_composite(img.convert("RGBA"), glow.filter(ImageFilter.GaussianBlur(70))).convert("RGB")
    draw = ImageDraw.Draw(img)

    _draw_pitch_lines(draw, 1080, 1080, GOLD, opacity_color="#333353")
    _logo_watermark(img, (710, 690), 330, opacity=0.14)
    _brand_lockup(img, draw, 72, 50, logo_size=50)
    _trophy_icon(draw, 540, 104, GOLD)
    _center_text(draw, "WORLD CUP 2026", (0, 146, 1080, 206), FONT_BOLD, 40, GOLD)
    draw.line((250, 225, 830, 225), fill=GOLD, width=4)

    _draw_wrapped_text(
        draw,
        payload.content,
        box=(90, 310, 900, 430),
        font_path=FONT_BOLD,
        max_size=76,
        min_size=42,
        fill=WHITE,
        spacing=14,
    )

    _flag_pair(draw, 92, 890, flags)
    if score_or_stat:
        _center_text(draw, score_or_stat, (350, 860, 730, 950), FONT_BOLD, 48, GOLD)
    _handle(draw, 850, 928)
    draw.rectangle((0, 1072, 1080, 1080), fill=GOLD)
    path = _save(img, output_path, "world_cup_special.png")
    return RenderedTemplate("world_cup", path, 1080, 1080)


def render_hot_take(
    content: str,
    output_path: str | Path | None = None,
) -> RenderedTemplate:
    img = Image.new("RGB", (1080, 1080), DARK)
    draw = ImageDraw.Draw(img)

    _logo_watermark(img, (620, 120), 560, opacity=0.08)
    _corner_slashes(draw, 760, 64, SKY)
    draw.rectangle((0, 0, 14, 1080), fill=SKY)
    _brand_lockup(img, draw, 72, 48, logo_size=52)

    _draw_wrapped_text(
        draw,
        content,
        box=(72, 200, 900, 620),
        font_path=FONT_ITALIC,
        max_size=86,
        min_size=44,
        fill=WHITE,
        spacing=16,
    )

    _football_icon(draw, 75, 902, SKY)
    draw.line((72, 884, 320, 884), fill="#20304F", width=3)
    _handle(draw, 72, 972)
    path = _save(img, output_path, "hot_take.png")
    return RenderedTemplate("hot_take", path, 1080, 1080)


def render_player_spotlight(
    payload: PlayerSpotlightPayload,
    output_path: str | Path | None = None,
) -> RenderedTemplate:
    img = Image.new("RGB", (1080, 1080), NAVY)
    draw = ImageDraw.Draw(img)
    draw.rectangle((540, 0, 1080, 1080), fill=LIGHT_NAVY)
    _draw_pitch_lines(draw, 1080, 1080, SKY, opacity_color="#2D416A")
    _logo_watermark(img, (640, 185), 430, opacity=0.12)
    draw.rectangle((536, 0, 546, 1080), fill=SKY)

    _brand_lockup(img, draw, 72, 50, logo_size=50)
    _draw_wrapped_text(
        draw,
        payload.player_name,
        box=(72, 220, 395, 170),
        font_path=FONT_BOLD,
        max_size=68,
        min_size=42,
        fill=WHITE,
        spacing=8,
    )
    if payload.position_club:
        draw.text((72, 386), payload.position_club, font=_font(FONT_REGULAR, 28), fill=GRAY)

    stats = list(payload.stats)[:4]
    while len(stats) < 4:
        stats.append(("-", "STAT"))
    _stat_grid(draw, stats, left=72, top=508)

    _handle(draw, 72, 970)
    draw.ellipse((635, 278, 985, 628), fill="#1B2947", outline=SKY, width=8)
    _paste_logo(img, 690, 335, 240, opacity=0.86)
    _center_text(draw, "PLAYER IMAGE", (640, 650, 980, 698), FONT_BOLD, 24, GRAY)

    path = _save(img, output_path, "player_spotlight.png")
    return RenderedTemplate("player_spotlight", path, 1080, 1080)


def render_match_result(
    payload: MatchResultPayload,
    output_path: str | Path | None = None,
) -> RenderedTemplate:
    img = Image.new("RGB", (1080, 1350), DARK)
    draw = ImageDraw.Draw(img)

    _logo_watermark(img, (345, 350), 390, opacity=0.07)
    _corner_slashes(draw, 774, 70, SKY)
    _brand_lockup(img, draw, 72, 54, logo_size=54)
    _center_text(draw, payload.competition.upper(), (0, 110, 1080, 160), FONT_BOLD, 30, SKY)
    draw.line((260, 182, 820, 182), fill=SKY, width=4)

    draw.rounded_rectangle((62, 358, 1018, 590), radius=18, outline="#20304F", width=3)
    _center_text(draw, payload.home_team.upper(), (55, 430, 385, 520), FONT_BOLD, 42, WHITE)
    draw.rounded_rectangle((400, 395, 680, 545), radius=14, fill=WHITE)
    _center_text(draw, payload.score, (400, 410, 680, 530), FONT_BOLD, 76, SKY)
    _center_text(draw, payload.away_team.upper(), (695, 430, 1025, 520), FONT_BOLD, 42, WHITE)

    draw.line((190, 640, 890, 640), fill="#26344F", width=3)

    if payload.home_events or payload.away_events or payload.home_stats or payload.away_stats:
        _team_detail_column(
            draw,
            title=payload.home_team,
            events=payload.home_events,
            stats=payload.home_stats,
            box=(92, 675, 440, 360),
            align="left",
        )
        _team_detail_column(
            draw,
            title=payload.away_team,
            events=payload.away_events,
            stats=payload.away_stats,
            box=(640, 675, 348, 360),
            align="right",
        )
    elif payload.key_events:
        _center_text(draw, "KEY MOMENTS", (0, 670, 1080, 705), FONT_BOLD, 22, SKY)
        y = 730
        for event in payload.key_events[:5]:
            _center_text(draw, event, (245, y, 835, y + 34), FONT_REGULAR, 28, WHITE)
            y += 48

    if payload.player_of_match:
        draw.rounded_rectangle((72, 1130, 650, 1230), radius=12, fill=SKY)
        _star_icon(draw, 122, 1182, 18, WHITE)
        draw.text((155, 1162), payload.player_of_match.upper(), font=_font(FONT_BOLD, 32), fill=WHITE)

    _handle(draw, 812, 1245)
    path = _save(img, output_path, "match_result.png")
    return RenderedTemplate("match_result", path, 1080, 1350)


def _save(img: Image.Image, output_path: str | Path | None, default_name: str) -> Path:
    if output_path is None:
        OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
        path = OUTPUT_DIR / default_name
    else:
        path = Path(output_path)
        path.parent.mkdir(parents=True, exist_ok=True)
    img.save(path, "PNG")
    return path


def _load_logo(size: int, opacity: float = 1.0) -> Image.Image | None:
    if not LOGO_PATH.exists():
        return None
    logo = Image.open(LOGO_PATH).convert("RGBA")
    logo.thumbnail((size, size), Image.Resampling.LANCZOS)

    # The provided logo PNG has a light checkerboard background. Remove light
    # pixels so the blue/navy mark can sit cleanly on dark templates.
    pixels = logo.load()
    for y in range(logo.height):
        for x in range(logo.width):
            r, g, b, a = pixels[x, y]
            if r > 225 and g > 225 and b > 225:
                pixels[x, y] = (r, g, b, 0)
            else:
                pixels[x, y] = (r, g, b, int(a * opacity))
    return logo


def _paste_logo(img: Image.Image, x: int, y: int, size: int, opacity: float = 1.0) -> None:
    logo = _load_logo(size, opacity)
    if not logo:
        return
    img.paste(logo, (x, y), logo)


def _logo_watermark(img: Image.Image, pos: tuple[int, int], size: int, opacity: float = 0.1) -> None:
    _paste_logo(img, pos[0], pos[1], size, opacity)


def _brand_lockup(img: Image.Image, draw: ImageDraw.ImageDraw, x: int, y: int, logo_size: int = 52) -> None:
    _paste_logo(img, x, y - 12, logo_size, opacity=1.0)
    draw.text((x + logo_size + 16, y), WORDMARK, font=_font(FONT_BOLD, 26), fill=WHITE)
    draw.text((x + logo_size + 18, y + 31), "FOOTBALL INTELLIGENCE", font=_font(FONT_BOLD, 13), fill=SKY)


def _draw_pitch_lines(
    draw: ImageDraw.ImageDraw,
    width: int,
    height: int,
    accent: str,
    opacity_color: str,
) -> None:
    for offset in range(-height, width, 180):
        draw.line((offset, height, offset + height, 0), fill=opacity_color, width=2)
    draw.rectangle((44, 44, width - 44, height - 44), outline=opacity_color, width=2)
    draw.arc((width - 330, height - 330, width + 80, height + 80), 180, 270, fill=opacity_color, width=3)
    draw.line((width - 210, 0, width - 60, 0), fill=accent, width=6)


def _corner_slashes(draw: ImageDraw.ImageDraw, x: int, y: int, fill: str) -> None:
    for idx in range(3):
        xx = x + idx * 42
        draw.polygon([(xx, y), (xx + 18, y), (xx - 72, y + 170), (xx - 90, y + 170)], fill=fill)


def _pill(draw: ImageDraw.ImageDraw, text: str, x: int, y: int, bg: str, fg: str) -> None:
    font = _font(FONT_BOLD, 18)
    tw = _bbox(draw, text, font)[2]
    draw.rounded_rectangle((x, y, x + tw + 34, y + 40), radius=20, fill=bg)
    draw.text((x + 17, y + 10), text, font=font, fill=fg)


def _font(path: str, size: int) -> ImageFont.FreeTypeFont:
    try:
        return ImageFont.truetype(path, size=size)
    except OSError:
        return ImageFont.load_default()


def _draw_wrapped_text(
    draw: ImageDraw.ImageDraw,
    text: str,
    box: tuple[int, int, int, int],
    font_path: str,
    max_size: int,
    min_size: int,
    fill: str,
    spacing: int = 10,
) -> None:
    x, y, width, height = box
    text = " ".join(str(text).split())
    for size in range(max_size, min_size - 1, -2):
        font = _font(font_path, size)
        avg = max(10, int(size * 0.55))
        lines = wrap(text, width=max(8, width // avg))
        line_heights = [_bbox(draw, line, font)[3] for line in lines]
        total_height = sum(line_heights) + spacing * max(0, len(lines) - 1)
        if total_height <= height:
            yy = y
            for line in lines:
                draw.text((x, yy), line, font=font, fill=fill)
                yy += _bbox(draw, line, font)[3] + spacing
            return
    font = _font(font_path, min_size)
    yy = y
    for line in wrap(text, width=max(8, width // max(10, int(min_size * 0.55))))[:8]:
        draw.text((x, yy), line, font=font, fill=fill)
        yy += _bbox(draw, line, font)[3] + spacing


def _center_text(
    draw: ImageDraw.ImageDraw,
    text: str,
    box: tuple[int, int, int, int],
    font_path: str,
    size: int,
    fill: str,
) -> None:
    font = _font(font_path, size)
    lines = str(text).splitlines() or [""]
    heights = [_bbox(draw, line, font)[3] for line in lines]
    total_h = sum(heights) + 6 * max(0, len(lines) - 1)
    y = box[1] + ((box[3] - box[1]) - total_h) / 2
    for line, h in zip(lines, heights):
        w = _bbox(draw, line, font)[2]
        x = box[0] + ((box[2] - box[0]) - w) / 2
        draw.text((x, y), line, font=font, fill=fill)
        y += h + 6


def _center_wrapped_text(
    draw: ImageDraw.ImageDraw,
    text: str,
    box: tuple[int, int, int, int],
    font_path: str,
    size: int,
    fill: str,
) -> None:
    x1, y1, x2, y2 = box
    font = _font(font_path, size)
    width = max(1, x2 - x1)
    avg = max(8, int(size * 0.55))
    lines = wrap(str(text), width=max(8, width // avg))
    line_h = _bbox(draw, "Ag", font)[3]
    total_h = len(lines) * line_h + max(0, len(lines) - 1) * 4
    y = y1 + max(0, (y2 - y1 - total_h) / 2)
    for line in lines[:3]:
        w = _bbox(draw, line, font)[2]
        draw.text((x1 + (width - w) / 2, y), line, font=font, fill=fill)
        y += line_h + 4


def _bbox(draw: ImageDraw.ImageDraw, text: str, font: ImageFont.ImageFont) -> tuple[int, int, int, int]:
    left, top, right, bottom = draw.textbbox((0, 0), text, font=font)
    return (left, top, right - left, bottom - top)


def _wordmark(draw: ImageDraw.ImageDraw, x: int, y: int) -> None:
    draw.text((x, y), WORDMARK, font=_font(FONT_BOLD, 20), fill=WHITE)


def _handle(draw: ImageDraw.ImageDraw, x: int, y: int) -> None:
    draw.text((x, y), HANDLE, font=_font(FONT_REGULAR, 24), fill=GRAY)


def _football_hex(draw: ImageDraw.ImageDraw, x: int, y: int, fill: str) -> None:
    points = [(x, y - 24), (x + 22, y - 12), (x + 22, y + 12), (x, y + 24), (x - 22, y + 12), (x - 22, y - 12)]
    draw.polygon(points, outline=fill, width=4)
    draw.line((x - 15, y, x + 15, y), fill=fill, width=3)
    draw.line((x, y - 16, x, y + 16), fill=fill, width=3)


def _football_icon(draw: ImageDraw.ImageDraw, x: int, y: int, fill: str) -> None:
    draw.ellipse((x, y, x + 44, y + 44), outline=fill, width=4)
    draw.polygon([(x + 22, y + 11), (x + 33, y + 20), (x + 29, y + 33), (x + 15, y + 33), (x + 11, y + 20)], outline=fill)


def _trophy_icon(draw: ImageDraw.ImageDraw, cx: int, cy: int, fill: str) -> None:
    draw.rectangle((cx - 20, cy - 22, cx + 20, cy + 14), outline=fill, width=4)
    draw.arc((cx - 48, cy - 18, cx - 12, cy + 28), 90, 265, fill=fill, width=4)
    draw.arc((cx + 12, cy - 18, cx + 48, cy + 28), 275, 90, fill=fill, width=4)
    draw.line((cx, cy + 14, cx, cy + 40), fill=fill, width=5)
    draw.rectangle((cx - 24, cy + 40, cx + 24, cy + 48), fill=fill)


def _star_icon(draw: ImageDraw.ImageDraw, cx: int, cy: int, radius: int, fill: str) -> None:
    points = [
        (cx, cy - radius),
        (cx + radius * 0.35, cy - radius * 0.35),
        (cx + radius, cy - radius * 0.25),
        (cx + radius * 0.48, cy + radius * 0.18),
        (cx + radius * 0.6, cy + radius),
        (cx, cy + radius * 0.52),
        (cx - radius * 0.6, cy + radius),
        (cx - radius * 0.48, cy + radius * 0.18),
        (cx - radius, cy - radius * 0.25),
        (cx - radius * 0.35, cy - radius * 0.35),
    ]
    draw.polygon(points, fill=fill)


def _flag_pair(draw: ImageDraw.ImageDraw, x: int, y: int, flags: tuple[str, str]) -> None:
    labels = [flags[0] or "A", "VS", flags[1] or "B"]
    draw.ellipse((x, y, x + 66, y + 66), fill=WHITE)
    _center_text(draw, labels[0][:3].upper(), (x, y, x + 66, y + 66), FONT_BOLD, 18, NAVY)
    draw.text((x + 86, y + 21), labels[1], font=_font(FONT_BOLD, 22), fill=WHITE)
    draw.ellipse((x + 142, y, x + 208, y + 66), fill=WHITE)
    _center_text(draw, labels[2][:3].upper(), (x + 142, y, x + 208, y + 66), FONT_BOLD, 18, NAVY)


def _stat_grid(draw: ImageDraw.ImageDraw, stats: Sequence[tuple[str, str]], left: int, top: int) -> None:
    box_w = 185
    box_h = 115
    gap = 22
    for idx, (number, label) in enumerate(stats[:4]):
        col = idx % 2
        row = idx // 2
        x = left + col * (box_w + gap)
        y = top + row * (box_h + gap)
        draw.rectangle((x, y, x + box_w, y + box_h), outline="#32436B", width=2)
        _center_text(draw, str(number), (x, y + 12, x + box_w, y + 62), FONT_BOLD, 38, SKY)
        _center_text(draw, str(label).upper(), (x + 10, y + 62, x + box_w - 10, y + 104), FONT_BOLD, 18, WHITE)


def _team_detail_column(
    draw: ImageDraw.ImageDraw,
    title: str,
    events: Sequence[str],
    stats: Sequence[tuple[str, str]],
    box: tuple[int, int, int, int],
    align: str,
) -> None:
    x, y, width, height = box
    title_font = _font(FONT_BOLD, 22)
    text_font = _font(FONT_REGULAR, 24)
    label_font = _font(FONT_BOLD, 18)
    value_font = _font(FONT_BOLD, 24)

    draw.text((x, y), title.upper(), font=title_font, fill=SKY)
    yy = y + 44
    max_y = y + height

    if events:
        draw.text((x, yy), "SCORERS / EVENTS", font=label_font, fill=GRAY)
        yy += 34
        for event in events[:4]:
            if yy + 28 > max_y:
                break
            line = str(event)
            if align == "right":
                line_w = _bbox(draw, line, text_font)[2]
                draw.text((x + width - line_w, yy), line, font=text_font, fill=WHITE)
            else:
                draw.text((x, yy), line, font=text_font, fill=WHITE)
            yy += 38

    if stats and yy + 42 < max_y:
        yy += 14
        draw.text((x, yy), "MATCH STATS", font=label_font, fill=GRAY)
        yy += 34
        for label, value in stats[:4]:
            if yy + 28 > max_y:
                break
            label_text = str(label).upper()
            value_text = str(value)
            draw.text((x, yy), label_text, font=label_font, fill=WHITE)
            value_w = _bbox(draw, value_text, value_font)[2]
            draw.text((x + width - value_w, yy - 3), value_text, font=value_font, fill=SKY)
            yy += 36
