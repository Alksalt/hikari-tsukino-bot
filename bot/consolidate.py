"""Memory consolidation agent — runs at session end (triggered by timeout)."""

from __future__ import annotations

from datetime import date
from pathlib import Path
from typing import Any

import yaml

from .chat import clear_history, get_history, get_session_turn_count
from .llm import chat_completion
from .memory import (
    add_known_fact,
    add_open_loop,
    clear_open_loops,
    get_meaningful_exchanges,
    get_trust_stage,
    increment_meaningful_exchanges,
    set_trust_stage,
    update_last_updated,
    write_episode,
)

_ROOT = Path(__file__).parent.parent
_SETTINGS_PATH = _ROOT / "settings.yaml"

_CONSOLIDATION_SYSTEM = """\
You are a memory consolidation assistant for a chatbot. \
Your job: analyze a conversation and extract structured information.

Output ONLY valid YAML (no markdown code fences, no extra text):

summary: |
  [2-4 sentence summary: what was discussed, emotional tone, anything notable]
new_facts:
  - [fact about the user: preference, detail, background info]
open_loops:
  - [time-sensitive item the user mentioned, e.g. "has an interview on Friday"]
emotional_notes: |
  [brief: how was the user? how was the session overall?]
is_meaningful: true  # true if >3 substantive turns, false if just commands/short

If a list has no items, use an empty list: []"""


def _load_settings() -> dict[str, Any]:
    with open(_SETTINGS_PATH) as f:
        return yaml.safe_load(f)


def _exchanges_per_stage(speed: str) -> int:
    return {"slow": 50, "normal": 20, "fast": 5, "instant": 0}.get(speed, 20)


def _build_consolidation_prompt(history: list[dict[str, str]]) -> list[dict[str, str]]:
    conversation_text = "\n".join(
        f"{msg['role'].upper()}: {msg['content']}" for msg in history
    )
    today = date.today().isoformat()
    user_msg = f"Conversation from {today}:\n\n{conversation_text}"
    return [
        {"role": "system", "content": _CONSOLIDATION_SYSTEM},
        {"role": "user", "content": user_msg},
    ]


async def run_consolidation() -> bool:
    """
    Run memory consolidation for the current session.
    Returns True if consolidation ran, False if session was too short.
    """
    history = get_history()
    turn_count = get_session_turn_count()

    if turn_count < 2:
        clear_history()
        return False

    try:
        messages = _build_consolidation_prompt(history)
        raw_yaml = await chat_completion(messages, task="memory", temperature=0.3)

        raw_yaml = raw_yaml.strip()
        if raw_yaml.startswith("```"):
            raw_yaml = "\n".join(raw_yaml.splitlines()[1:])
        if raw_yaml.endswith("```"):
            raw_yaml = "\n".join(raw_yaml.splitlines()[:-1])

        data = yaml.safe_load(raw_yaml)
    except Exception:
        clear_history()
        return False

    summary = data.get("summary", "").strip()
    new_facts: list[str] = data.get("new_facts", []) or []
    open_loops: list[str] = data.get("open_loops", []) or []
    emotional_notes = data.get("emotional_notes", "").strip()
    is_meaningful: bool = data.get("is_meaningful", False)

    settings = _load_settings()
    stage = get_trust_stage()

    if summary:
        exchanges = get_meaningful_exchanges()
        facts_text = "".join(f"- {f}\n" for f in new_facts) or "none\n"
        loops_text = "".join(f"- {loop}\n" for loop in open_loops) or "none\n"
        episode_content = (
            f"# Session {date.today().isoformat()}\n\n"
            f"## summary\n{summary}\n\n"
            f"## new facts\n{facts_text}"
            f"\n## open loops\n{loops_text}"
            f"\n## emotional notes\n{emotional_notes or 'none'}\n\n"
            f"## trust: {stage} | meaningful_exchanges: {exchanges}\n"
        )
        write_episode(episode_content)

    for fact in new_facts:
        if fact and fact.strip():
            add_known_fact(fact.strip())

    if open_loops:
        clear_open_loops()
        for loop in open_loops:
            if loop and loop.strip():
                add_open_loop(loop.strip())

    if is_meaningful:
        count = increment_meaningful_exchanges()
        speed = settings.get("trust", {}).get("progression_speed", "normal")
        threshold = _exchanges_per_stage(speed)

        if speed != "instant" and stage < 3:
            stage_start_count = stage * threshold
            if count - stage_start_count >= threshold:
                new_stage = min(stage + 1, 3)
                set_trust_stage(new_stage)

    update_last_updated()
    clear_history()
    return True
