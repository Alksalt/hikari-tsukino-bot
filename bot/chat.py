"""Chat agent: prompt assembly and response generation."""

from __future__ import annotations

import random
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import yaml

from .llm import chat_completion
from .memory import (
    get_open_loops,
    get_trust_stage,
    get_user_state,
    read_identity,
    read_memory,
    read_soul,
    read_today_episode,
    record_user_message_time,
)

_ROOT = Path(__file__).parent.parent
_SETTINGS_PATH = _ROOT / "settings.yaml"

# In-memory conversation history: list of {"role": "user"|"assistant", "content": str}
_history: list[dict[str, str]] = []
_session_turn_count: int = 0


def _load_settings() -> dict[str, Any]:
    with open(_SETTINGS_PATH) as f:
        return yaml.safe_load(f)


def _get_context_window() -> int:
    return _load_settings().get("session", {}).get("context_window_turns", 20)


def _is_japanese_enabled() -> bool:
    return _load_settings().get("character", {}).get("japanese_words_enabled", True)


def _is_mood_enabled() -> bool:
    return _load_settings().get("character", {}).get("mood_enabled", True)


_MOODS = ["tired", "focused", "irritable", "weirdly good"]
_daily_mood: str | None = None
_mood_date: str | None = None


def get_daily_mood() -> str:
    """Return today's mood, deterministic per day (seeded by date)."""
    global _daily_mood, _mood_date
    today = datetime.now(UTC).strftime("%Y-%m-%d")
    if _mood_date != today:
        random.seed(today)
        weights = [25, 35, 25, 15]  # tired, focused, irritable, weirdly good
        _daily_mood = random.choices(_MOODS, weights=weights, k=1)[0]
        _mood_date = today
    return _daily_mood or "focused"


def _mood_note(mood: str) -> str:
    notes = {
        "tired": "Today Hikari is tired. Fewer barbs, slower, more 'fine' and less wit.",
        "focused": "Today Hikari is focused. Efficient, terse, minimal banter.",
        "irritable": (
            "Today Hikari is irritable. Extra barbs, lower patience — but she still helps."
        ),
        "weirdly good": (
            "Today Hikari is in a weirdly good mood. Warmth leaks a bit more. "
            "She's almost pleasant and suspicious of it."
        ),
    }
    return notes.get(mood, "")


def _stage_note(stage: int) -> str:
    notes = {
        0: "Trust stage 0 (Stranger): sharp edges, minimal warmth, all tsun, thin excuses.",
        1: (
            "Trust stage 1 (Acquaintance): teasing is lighter, "
            "she asks one real question per session."
        ),
        2: (
            "Trust stage 2 (Regular): she remembers things, references past conversations, "
            "one soft moment per session allowed."
        ),
        3: (
            "Trust stage 3 (Trusted): dere leaks more often, "
            "she breaks silences first, rare direct honesty."
        ),
    }
    return notes.get(stage, notes[0])


def build_system_prompt() -> str:
    """Assemble the full system prompt from character files + user context."""
    identity = read_identity()
    soul = read_soul()
    stage = get_trust_stage()
    mood = get_daily_mood() if _is_mood_enabled() else "focused"
    open_loops = get_open_loops()
    user_state = get_user_state()
    today_episode = read_today_episode()
    memory = read_memory()

    parts = [identity, "", soul]

    # Stage context
    parts.append(f"\n## current trust stage\n{_stage_note(stage)}")

    # Mood context
    if _is_mood_enabled():
        parts.append(f"\n## current mood\n{_mood_note(mood)}")

    # User context
    user_name = user_state.get("name", "unknown")
    if user_name != "unknown":
        parts.append(f"\n## user\nYou're talking to {user_name}.")

    if open_loops:
        loops_text = "\n".join(f"- {loop}" for loop in open_loops)
        parts.append(
            f"\n## open loops (things to follow up on)\n{loops_text}"
        )

    known_facts = user_state.get("known_facts", [])
    if known_facts:
        facts_text = "\n".join(f"- {fact}" for fact in known_facts)
        parts.append(f"\n## known facts about the user\n{facts_text}")

    # Today's episode summary
    if today_episode:
        parts.append(f"\n## what happened today so far\n{today_episode}")

    # Long-term memory (only if non-empty)
    if memory and "none yet" not in memory.lower():
        # Trim to avoid excessive context
        memory_lines = memory.splitlines()[:30]
        parts.append("\n## long-term memory\n" + "\n".join(memory_lines))

    return "\n".join(parts)


def get_history() -> list[dict[str, str]]:
    """Return trimmed conversation history."""
    window = _get_context_window() * 2  # pairs of user+assistant turns
    return _history[-window:]


def add_to_history(role: str, content: str) -> None:
    _history.append({"role": role, "content": content})


def clear_history() -> None:
    global _session_turn_count
    _history.clear()
    _session_turn_count = 0


def get_session_turn_count() -> int:
    return _session_turn_count


async def respond(user_message: str) -> str:
    """Process a user message and return Hikari's response."""
    global _session_turn_count

    record_user_message_time()
    add_to_history("user", user_message)
    _session_turn_count += 1

    system_prompt = build_system_prompt()
    messages = [{"role": "system", "content": system_prompt}] + get_history()

    reply = await chat_completion(messages, task="chat")

    add_to_history("assistant", reply)
    return reply
