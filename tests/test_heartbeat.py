"""Heartbeat scheduler tests."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from bot.heartbeat import (
    _extract_templates,
    _is_quiet_hours,
    pick_excuse,
    should_send_heartbeat,
)

SAMPLE_SETTINGS = {
    "heartbeat": {
        "min_interval_hours": 4,
        "max_interval_hours": 8,
        "quiet_start": "23:00",
        "quiet_end": "08:00",
        "skip_if_user_active_minutes": 60,
    }
}


# ---------------------------------------------------------------------------
# Quiet hours
# ---------------------------------------------------------------------------


def test_quiet_hours_during_night():
    # 02:30 is in quiet hours (23:00-08:00)
    assert _is_quiet_hours("23:00", "08:00") in (True, False)  # time-dependent
    # Test specific times with mocked datetime
    from unittest.mock import patch


    with patch("bot.heartbeat.datetime") as mock_dt:
        mock_dt.now.return_value = MagicMock(hour=2, minute=30)
        assert _is_quiet_hours("23:00", "08:00") is True


def test_quiet_hours_during_day():
    from unittest.mock import patch


    with patch("bot.heartbeat.datetime") as mock_dt:
        mock_dt.now.return_value = MagicMock(hour=14, minute=0)
        assert _is_quiet_hours("23:00", "08:00") is False


def test_quiet_hours_at_boundary():
    from unittest.mock import patch

    with patch("bot.heartbeat.datetime") as mock_dt:
        mock_dt.now.return_value = MagicMock(hour=23, minute=0)
        assert _is_quiet_hours("23:00", "08:00") is True

        mock_dt.now.return_value = MagicMock(hour=8, minute=0)
        assert _is_quiet_hours("23:00", "08:00") is False


# ---------------------------------------------------------------------------
# should_send_heartbeat
# ---------------------------------------------------------------------------


def _make_state(
    silence_until=None,
    last_proactive_sent=None,
    last_user_message=None,
    used_excuses=None,
    proactive_count=0,
):
    return {
        "silence_until": silence_until,
        "last_proactive_sent": last_proactive_sent,
        "last_user_message": last_user_message,
        "used_excuses": used_excuses or [],
        "proactive_count": proactive_count,
    }


def test_should_send_silence_active():
    future = (datetime.now(UTC) + timedelta(hours=2)).isoformat()
    state = _make_state(silence_until=future)

    with (
        patch("bot.heartbeat.get_heartbeat_state", return_value=state),
        patch("bot.heartbeat._is_quiet_hours", return_value=False),
    ):
        assert should_send_heartbeat(SAMPLE_SETTINGS) is False


def test_should_send_quiet_hours():
    state = _make_state()

    with (
        patch("bot.heartbeat.get_heartbeat_state", return_value=state),
        patch("bot.heartbeat._is_quiet_hours", return_value=True),
    ):
        assert should_send_heartbeat(SAMPLE_SETTINGS) is False


def test_should_send_user_active_recently():
    recent = (datetime.now(UTC) - timedelta(minutes=30)).isoformat()
    state = _make_state(last_user_message=recent)

    with (
        patch("bot.heartbeat.get_heartbeat_state", return_value=state),
        patch("bot.heartbeat._is_quiet_hours", return_value=False),
    ):
        assert should_send_heartbeat(SAMPLE_SETTINGS) is False


def test_should_send_min_interval_not_elapsed():
    recent_proactive = (datetime.now(UTC) - timedelta(hours=2)).isoformat()
    state = _make_state(last_proactive_sent=recent_proactive)

    with (
        patch("bot.heartbeat.get_heartbeat_state", return_value=state),
        patch("bot.heartbeat._is_quiet_hours", return_value=False),
    ):
        assert should_send_heartbeat(SAMPLE_SETTINGS) is False


def test_should_send_all_clear():
    old_proactive = (datetime.now(UTC) - timedelta(hours=6)).isoformat()
    old_user = (datetime.now(UTC) - timedelta(hours=3)).isoformat()
    state = _make_state(last_proactive_sent=old_proactive, last_user_message=old_user)

    with (
        patch("bot.heartbeat.get_heartbeat_state", return_value=state),
        patch("bot.heartbeat._is_quiet_hours", return_value=False),
    ):
        assert should_send_heartbeat(SAMPLE_SETTINGS) is True


def test_should_send_no_prior_messages():
    state = _make_state()  # null timestamps

    with (
        patch("bot.heartbeat.get_heartbeat_state", return_value=state),
        patch("bot.heartbeat._is_quiet_hours", return_value=False),
    ):
        assert should_send_heartbeat(SAMPLE_SETTINGS) is True


# ---------------------------------------------------------------------------
# Template parsing
# ---------------------------------------------------------------------------

SAMPLE_TEMPLATES = """## templates

1. testing notifications. yours worked. congrats.
2. you went quiet. suspicious.
3. did you eat? not because i care — blood sugar thing.
4. just making sure you didn't break anything. again.
5. i was bored. don't read into it.
"""


def test_extract_templates():
    templates = _extract_templates(SAMPLE_TEMPLATES)
    assert len(templates) == 5
    assert templates[0] == (1, "testing notifications. yours worked. congrats.")
    assert templates[1] == (2, "you went quiet. suspicious.")


def test_extract_templates_empty():
    assert _extract_templates("no templates here") == []


# ---------------------------------------------------------------------------
# Excuse picker
# ---------------------------------------------------------------------------


def test_pick_excuse_avoids_used():
    templates = [(i, f"excuse {i}") for i in range(1, 6)]
    used = [1, 2, 3, 4]
    idx, text = pick_excuse(templates, used)
    assert idx == 5


def test_pick_excuse_resets_when_all_used():
    templates = [(i, f"excuse {i}") for i in range(1, 4)]
    used = [1, 2, 3]
    idx, text = pick_excuse(templates, used)
    assert (idx, text) in templates


def test_pick_excuse_from_empty_used():
    templates = [(1, "excuse 1"), (2, "excuse 2")]
    idx, text = pick_excuse(templates, [])
    assert (idx, text) in templates


# ---------------------------------------------------------------------------
# Integration: run_heartbeat
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_run_heartbeat_sends_when_conditions_met():
    sent_messages = []

    async def mock_send(text: str) -> None:
        sent_messages.append(text)

    with (
        patch("bot.heartbeat.should_send_heartbeat", return_value=True),
        patch(
            "bot.heartbeat.read_heartbeat_templates",
            return_value=SAMPLE_TEMPLATES,
        ),
        patch("bot.heartbeat.get_heartbeat_state", return_value=_make_state()),
        patch("bot.heartbeat.get_trust_stage", return_value=0),
        patch("bot.heartbeat.get_daily_mood", return_value="focused"),
        patch("bot.heartbeat.record_proactive_sent"),
        patch(
            "bot.heartbeat.generate_proactive_message",
            new=AsyncMock(return_value="you went quiet. suspicious."),
        ),
    ):
        from bot.heartbeat import run_heartbeat

        result = await run_heartbeat(mock_send)

    assert result is True
    assert len(sent_messages) == 1


@pytest.mark.asyncio
async def test_run_heartbeat_skips_when_conditions_not_met():
    sent_messages = []

    async def mock_send(text: str) -> None:
        sent_messages.append(text)

    with patch("bot.heartbeat.should_send_heartbeat", return_value=False):
        from bot.heartbeat import run_heartbeat

        result = await run_heartbeat(mock_send)

    assert result is False
    assert len(sent_messages) == 0
