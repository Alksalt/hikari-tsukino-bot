"""Daily reflection agent — promotes stable facts to MEMORY.md and writes THOUGHTS.md."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

from .llm import chat_completion
from .memory import (
    append_thought,
    append_to_memory,
    get_trust_stage,
    prune_old_episodes,
    read_memory,
    read_recent_episodes,
)

_ROOT = Path(__file__).parent.parent
_SETTINGS_PATH = _ROOT / "settings.yaml"


def _load_settings() -> dict[str, Any]:
    with open(_SETTINGS_PATH) as f:
        return yaml.safe_load(f)


def _build_reflection_prompt(
    episodes: str, existing_memory: str, stage: int
) -> list[dict[str, str]]:
    system = """You are a memory reflection assistant for an AI character named Hikari Tsukino.
She is a 21-year-old tsundere who cares deeply but hides it.
Your job: analyze recent session episodes and existing memory, then output ONLY valid YAML.

Output structure:
new_memory_facts:
  - [stable confirmed fact about the user worth adding to long-term memory]
thought: |
  [2-5 sentences in Hikari's voice — private, honest, unguarded. What she notices about
   this person, what she won't say out loud, what she's actually thinking. First person,
   lowercase, no markdown. This is her diary, not chat output.]

Rules:
- Only add facts that appeared in multiple sessions or are clearly stable.
- The thought should sound like genuine private reflection, not chat messages.
- If no new stable facts, use: new_memory_facts: []
- If not enough data for a thought, write a brief honest observation anyway."""

    user_msg = (
        f"Recent sessions:\n{episodes or 'no sessions yet'}\n\n"
        f"Existing long-term memory:\n{existing_memory or 'none yet'}\n\n"
        f"Current trust stage: {stage}"
    )

    return [
        {"role": "system", "content": system},
        {"role": "user", "content": user_msg},
    ]


async def run_reflection() -> bool:
    """
    Run daily reflection. Promotes facts to MEMORY.md, writes THOUGHTS.md.
    Returns True if reflection ran.
    """
    settings = _load_settings()
    retention_days = settings.get("memory", {}).get("episode_retention_days", 30)

    episodes = read_recent_episodes(n=3)
    existing_memory = read_memory()
    stage = get_trust_stage()

    if not episodes:
        return False

    try:
        messages = _build_reflection_prompt(episodes, existing_memory, stage)
        raw_yaml = await chat_completion(messages, task="memory", temperature=0.5)

        raw_yaml = raw_yaml.strip()
        if raw_yaml.startswith("```"):
            raw_yaml = "\n".join(raw_yaml.splitlines()[1:])
        if raw_yaml.endswith("```"):
            raw_yaml = "\n".join(raw_yaml.splitlines()[:-1])

        data = yaml.safe_load(raw_yaml)
    except Exception:
        return False

    new_facts: list[str] = data.get("new_memory_facts", []) or []
    thought: str = (data.get("thought") or "").strip()

    # Promote stable facts to MEMORY.md
    for fact in new_facts:
        if fact and fact.strip():
            append_to_memory("about the user", fact.strip())

    # Write THOUGHTS.md entry (only at Stage 2+)
    if thought and stage >= 2:
        append_thought(thought)

    # Prune old episodes
    prune_old_episodes(retention_days)

    return True
