"""Rule-based reply engine: ordered patterns plus the mood states."""

from core.rule.rules import (
    BASE_MOOD,
    GROUPS,
    MOOD_THRESHOLD,
    Group,
    Mood,
    Pattern,
    Response,
    Tone,
    match_group,
    respond,
    shift_for,
)

__all__ = [
    "BASE_MOOD",
    "GROUPS",
    "MOOD_THRESHOLD",
    "Group",
    "Mood",
    "Pattern",
    "Response",
    "Tone",
    "match_group",
    "respond",
    "shift_for",
]
