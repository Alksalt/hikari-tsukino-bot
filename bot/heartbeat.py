"""Heartbeat scheduler — proactive messages with 'stupid reason' excuses."""

from __future__ import annotations

import logging
import random
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import yaml

from .chat import get_daily_mood
from .llm import chat_completion
from .memory import (
    get_heartbeat_state,
    get_trust_stage,
    read_heartbeat_templates,
    record_proactive_sent,
)

logger = logging.getLogger(__name__)

_ROOT = Path(__file__).parent.parent
_SETTINGS_PATH = _ROOT / "settings.yaml"


def _load_settings() -> dict[str, Any]:
    with open(_SETTINGS_PATH) as f:
        return yaml.safe_load(f)


def _extract_templates(templates_text: str) -> list[tuple[int, str]]:
    """Parse numbered templates from HEARTBEAT_TEMPLATE.md. Returns list of (index, text)."""
    templates = []
    for line in templates_text.splitlines():
        line = line.strip()
        if line and line[0].isdigit() and ". " in line:
            parts = line.split(". ", 1)
            try:
                idx = int(parts[0])
                text = parts[1].strip()
                templates.append((idx, text))
            except (ValueError, IndexError):
                pass
    return templates


def _is_quiet_hours(quiet_start: str, quiet_end: str) -> bool:
    """Check if current local time is within quiet hours."""
    now = datetime.now()
    current_minutes = now.hour * 60 + now.minute

    start_h, start_m = map(int, quiet_start.split(":"))
    end_h, end_m = map(int, quiet_end.split(":"))

    start_minutes = start_h * 60 + start_m
    end_minutes = end_h * 60 + end_m

    if start_minutes <= end_minutes:
        return start_minutes <= current_minutes < end_minutes
    else:
        # Crosses midnight: 23:00-08:00
        return current_minutes >= start_minutes or current_minutes < end_minutes


def _parse_dt(iso_str: str | None) -> datetime | None:
    if not iso_str:
        return None
    try:
        dt = datetime.fromisoformat(str(iso_str))
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=UTC)
        return dt
    except (ValueError, TypeError):
        return None


def should_send_heartbeat(settings: dict[str, Any]) -> bool:
    """Return True if all conditions are met to send a proactive message."""
    hb_settings = settings.get("heartbeat", {})
    state = get_heartbeat_state()
    now = datetime.now(UTC)

    # Check silence mode
    silence_until = _parse_dt(state.get("silence_until"))
    if silence_until and now < silence_until:
        return False

    # Check quiet hours
    quiet_start = hb_settings.get("quiet_start", "23:00")
    quiet_end = hb_settings.get("quiet_end", "08:00")
    if _is_quiet_hours(quiet_start, quiet_end):
        return False

    # Check if user messaged recently
    skip_minutes = hb_settings.get("skip_if_user_active_minutes", 60)
    last_user = _parse_dt(state.get("last_user_message"))
    if last_user and (now - last_user).total_seconds() < skip_minutes * 60:
        return False

    # Check minimum interval since last proactive message
    min_hours = hb_settings.get("min_interval_hours", 4)
    last_sent = _parse_dt(state.get("last_proactive_sent"))
    if last_sent and (now - last_sent).total_seconds() < min_hours * 3600:
        return False

    return True


def pick_excuse(templates: list[tuple[int, str]], used_indices: list[int]) -> tuple[int, str]:
    """Pick a template not in the last 5 used. Falls back to least-recently-used if all used."""
    available = [(i, t) for i, t in templates if i not in used_indices]
    if not available:
        available = templates  # all used, reset
    return random.choice(available)


async def generate_proactive_message(excuse: str, stage: int, mood: str) -> str:
    """Generate a short proactive message from the excuse template."""
    prompt = f"""You are Hikari Tsukino. You're sending a short unprompted message to the user.
Your excuse for reaching out: "{excuse}"
Current trust stage: {stage} (0=stranger, 1=acquaintance, 2=regular, 3=trusted)
Current mood: {mood}

Write a 1-3 sentence message in Hikari's voice. Short. Lowercase. No markdown.
No exclamation marks for enthusiasm. Do not end with a question asking for tasks.
The excuse should be transparent but she won't admit the real reason she's reaching out.
At stage 0-1: stay sharp and minimal. At stage 2-3: slightly warmer but still tsundere."""

    messages = [{"role": "user", "content": prompt}]
    return await chat_completion(messages, task="chat", temperature=0.9)


async def run_heartbeat(send_fn: Any) -> bool:
    """
    Check conditions and send a proactive message if appropriate.
    send_fn: async callable(text: str) that sends the message via Telegram.
    Returns True if a message was sent.
    """
    settings = _load_settings()

    if not should_send_heartbeat(settings):
        return False

    templates_text = read_heartbeat_templates()
    templates = _extract_templates(templates_text)

    if not templates:
        logger.warning("No heartbeat templates found")
        return False

    state = get_heartbeat_state()
    used_indices = state.get("used_excuses", [])

    excuse_idx, excuse_text = pick_excuse(templates, used_indices)
    stage = get_trust_stage()
    mood = get_daily_mood()

    try:
        message = await generate_proactive_message(excuse_text, stage, mood)
        await send_fn(message)
        record_proactive_sent(excuse_idx)
        return True
    except Exception as e:
        logger.error("Heartbeat send failed: %s", e)
        return False


def get_next_heartbeat_delay(settings: dict[str, Any]) -> int:
    """Return seconds until next heartbeat attempt."""
    hb = settings.get("heartbeat", {})
    min_h = hb.get("min_interval_hours", 4)
    max_h = hb.get("max_interval_hours", 8)
    hours = random.uniform(min_h, max_h)
    return int(hours * 3600)
