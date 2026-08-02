"""Spaced repetition scheduling for mistakebook.

Intervals: 1 → 3 → 7 → 14 → 30 days (then every 30 days).
Result "correct" advances the stage; "partial" stays; "wrong" resets to 1 day.
Mastery (0-5) mirrors the stage reached.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

# Stage → days until the next review.
INTERVALS_DAYS = [1, 3, 7, 14, 30]
MAX_STAGE = len(INTERVALS_DAYS) - 1  # 4; stage 5 is "fully mastered" (30-day loop)

VALID_RESULTS = ("correct", "partial", "wrong")


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def next_stage(current_stage: int, result: str) -> int:
    """Compute the new stage after a review.

    correct → advance one stage (capped at MAX_STAGE + 1 = 5)
    partial → stay at current stage (never below 0)
    wrong   → back to stage 0
    """
    if result not in VALID_RESULTS:
        raise ValueError(f"invalid result {result!r}; expected one of {VALID_RESULTS}")
    if result == "correct":
        return min(current_stage + 1, MAX_STAGE + 1)
    if result == "partial":
        return max(current_stage, 0)
    return 0


def interval_for_stage(stage: int) -> int:
    """Days until next review for a given stage."""
    if stage >= len(INTERVALS_DAYS):
        return INTERVALS_DAYS[-1]
    return INTERVALS_DAYS[max(stage, 0)]


def next_review_at(stage: int, from_dt: datetime | None = None) -> datetime:
    base = from_dt or utc_now()
    return base + timedelta(days=interval_for_stage(stage))


def mastery_from_stage(stage: int) -> int:
    """Map stage (0-5) to mastery (0-5)."""
    return max(0, min(stage, 5))


def is_due(next_review: datetime, now: datetime | None = None) -> bool:
    return (now or utc_now()) >= next_review
