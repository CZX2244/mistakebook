"""Tests for the spaced-repetition scheduler."""

from datetime import datetime, timedelta, timezone

import pytest

from mistakebook import scheduler


def test_correct_advances_stage():
    assert scheduler.next_stage(0, "correct") == 1
    assert scheduler.next_stage(3, "correct") == 4


def test_correct_caps_at_max():
    assert scheduler.next_stage(5, "correct") == 5


def test_partial_stays():
    assert scheduler.next_stage(2, "partial") == 2


def test_wrong_resets():
    assert scheduler.next_stage(4, "wrong") == 0


def test_invalid_result_raises():
    with pytest.raises(ValueError):
        scheduler.next_stage(0, "nope")


def test_intervals():
    assert scheduler.interval_for_stage(0) == 1
    assert scheduler.interval_for_stage(1) == 3
    assert scheduler.interval_for_stage(2) == 7
    assert scheduler.interval_for_stage(3) == 14
    assert scheduler.interval_for_stage(4) == 30
    assert scheduler.interval_for_stage(5) == 30


def test_next_review_at():
    base = datetime(2026, 1, 1, tzinfo=timezone.utc)
    nr = scheduler.next_review_at(stage=1, from_dt=base)
    assert nr == base + timedelta(days=3)


def test_is_due():
    past = datetime(2026, 1, 1, tzinfo=timezone.utc)
    future = datetime(2099, 1, 1, tzinfo=timezone.utc)
    now = datetime(2026, 6, 1, tzinfo=timezone.utc)
    assert scheduler.is_due(past, now)
    assert not scheduler.is_due(future, now)


def test_mastery_mapping():
    for stage in range(6):
        assert scheduler.mastery_from_stage(stage) == stage
