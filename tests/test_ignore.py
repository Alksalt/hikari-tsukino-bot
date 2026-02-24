"""Tests for ignore mechanic and action display (v0.2.1)."""

from __future__ import annotations

import bot.chat as chat_module
import pytest
from bot.chat import (
    clear_history,
    get_ignore_streak,
    increment_ignore_streak,
    is_ignore_cooldown,
    reset_ignore_streak,
    tick_ignore_cooldown,
)


def setup_function():
    """Reset ignore state before each test."""
    clear_history()


# ---------------------------------------------------------------------------
# Ignore streak state
# ---------------------------------------------------------------------------


def test_initial_state():
    assert get_ignore_streak() == 0
    assert not is_ignore_cooldown()


def test_increment_ignore_streak():
    increment_ignore_streak()
    assert get_ignore_streak() == 1
    increment_ignore_streak()
    assert get_ignore_streak() == 2


def test_reset_ignore_streak_clears_streak():
    increment_ignore_streak()
    increment_ignore_streak()
    reset_ignore_streak()
    assert get_ignore_streak() == 0


def test_reset_ignore_streak_sets_cooldown():
    increment_ignore_streak()
    reset_ignore_streak()
    assert is_ignore_cooldown()


def test_tick_ignore_cooldown_decrements():
    increment_ignore_streak()
    reset_ignore_streak()
    # cooldown = 3; tick three times → should reach 0
    tick_ignore_cooldown()
    tick_ignore_cooldown()
    tick_ignore_cooldown()
    assert not is_ignore_cooldown()


def test_tick_ignore_cooldown_no_underflow():
    # Ticking when already 0 should not go negative
    assert not is_ignore_cooldown()
    tick_ignore_cooldown()
    assert not is_ignore_cooldown()
    assert chat_module._ignore_cooldown == 0


def test_clear_history_resets_ignore_state():
    increment_ignore_streak()
    increment_ignore_streak()
    reset_ignore_streak()
    clear_history()
    assert get_ignore_streak() == 0
    assert not is_ignore_cooldown()


# ---------------------------------------------------------------------------
# _should_ignore logic (via handlers module)
# ---------------------------------------------------------------------------


def test_should_ignore_disabled_by_settings():
    from bot.handlers import _should_ignore

    settings = {"ignore": {"enabled": False, "max_streak": 3}}
    assert not _should_ignore("irritable", 0, settings)


def test_should_ignore_respects_cooldown():
    from bot.handlers import _should_ignore

    settings = {"ignore": {"enabled": True, "max_streak": 3}}
    increment_ignore_streak()
    reset_ignore_streak()  # sets cooldown = 3
    # Cooldown is active — should never ignore
    for _ in range(20):
        assert not _should_ignore("irritable", 0, settings)


def test_should_ignore_respects_max_streak():
    from bot.handlers import _should_ignore

    settings = {"ignore": {"enabled": True, "max_streak": 2}}
    increment_ignore_streak()
    increment_ignore_streak()  # streak = 2 = max
    # Must not ignore again (force-break)
    for _ in range(20):
        assert not _should_ignore("irritable", 0, settings)


def test_should_ignore_zero_prob_at_stage_3_focused():
    """Focused mood at Stage 3 has 0% ignore probability."""
    from bot.handlers import _should_ignore

    settings = {"ignore": {"enabled": True, "max_streak": 3}}
    for _ in range(50):
        assert not _should_ignore("focused", 3, settings)


def test_should_ignore_zero_prob_good_mood_high_stage():
    """Weirdly good mood at Stage 2+ has 0% ignore probability."""
    from bot.handlers import _should_ignore

    settings = {"ignore": {"enabled": True, "max_streak": 3}}
    for _ in range(50):
        assert not _should_ignore("weirdly good", 2, settings)
        assert not _should_ignore("weirdly good", 3, settings)


def test_should_ignore_can_fire_irritable_stage0():
    """Irritable + Stage 0 (30%) should fire within many tries."""
    from bot.handlers import _should_ignore

    settings = {"ignore": {"enabled": True, "max_streak": 100}}
    fired = sum(_should_ignore("irritable", 0, settings) for _ in range(200))
    # At 30% probability over 200 tries, we expect ~60 fires; floor at 10 for flakiness margin
    assert fired > 10


# ---------------------------------------------------------------------------
# SOUL.md contains action line section
# ---------------------------------------------------------------------------


def test_soul_contains_action_lines_section():
    from bot.memory import read_soul

    soul = read_soul()
    assert "action lines" in soul.lower()
    assert "[ignores]" in soul
    assert "[surprised]" in soul
