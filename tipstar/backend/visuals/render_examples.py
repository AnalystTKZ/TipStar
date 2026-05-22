"""Render example TipStar social templates."""
from pathlib import Path

from backend.visuals.social_templates import (
    MatchResultPayload,
    PlayerSpotlightPayload,
    StandardPostPayload,
    render_hot_take,
    render_match_result,
    render_player_spotlight,
    render_standard_post,
    render_world_cup_special,
)


def main() -> None:
    output_dir = Path("generated/visuals/examples")
    output_dir.mkdir(parents=True, exist_ok=True)

    render_standard_post(
        StandardPostPayload(
            content="Haaland has now scored in four straight home games for City.",
            stat_number="4",
            stat_label="straight home games",
        ),
        output_dir / "standard_post.png",
    )
    render_world_cup_special(
        StandardPostPayload(
            content="Argentina open their World Cup defence with Messi still at the heart of everything.",
        ),
        output_dir / "world_cup_special.png",
        flags=("ARG", "TBC"),
        score_or_stat="GROUP STAGE",
    )
    render_hot_take(
        "City losing Pep one day will hurt the league more than people want to admit.",
        output_dir / "hot_take.png",
    )
    render_player_spotlight(
        PlayerSpotlightPayload(
            player_name="Phil Foden",
            position_club="MID | Manchester City",
            stats=(("22", "starts"), ("8", "goals"), ("6", "assists"), ("92%", "pass acc")),
        ),
        output_dir / "player_spotlight.png",
    )
    render_match_result(
        MatchResultPayload(
            competition="Premier League",
            home_team="Man City",
            away_team="Arsenal",
            score="2-1",
            home_events=("12' Haaland", "78' Foden"),
            away_events=("44' Saka",),
            home_stats=(("shots", "14"), ("xG", "1.8"), ("possession", "58%")),
            away_stats=(("shots", "9"), ("xG", "0.9"), ("possession", "42%")),
            player_of_match="Phil Foden",
        ),
        output_dir / "match_result.png",
    )
    print(f"Rendered examples to {output_dir.resolve()}")


if __name__ == "__main__":
    main()
