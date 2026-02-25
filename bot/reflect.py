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
    read_mood_arc,
    read_recent_episodes,
    write_mood_arc,
    write_self_preoccupation,
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


def _build_preoccupation_prompt(episodes: str) -> list[dict[str, str]]:
    system = """You are writing a single line for an AI character named Hikari Tsukino.
She works in data science / AI / ML. She has an ongoing inner life independent of conversations.

Write exactly 1 sentence describing something she's been thinking about — NOT related to the user.
It should be from her professional/intellectual domain: a paper, model behavior, dataset quirk,
attention mechanism, something she read, a code problem. Unresolved. Slightly annoying to her.

Rules:
- First person, lowercase, no markdown, no quotes.
- Must feel like a real ongoing thought, not a topic summary.
- Do NOT mention the user.

Example outputs:
  i keep thinking about why the attention pattern shifts on the third layer.
  there's something wrong with the embedding space and it's been bothering me for two days.
  i read something about scaling laws that felt off and i can't find the flaw yet.

Output ONLY the single sentence."""

    ctx = episodes[:500] if episodes else "none"
    return [
        {"role": "system", "content": system},
        {"role": "user", "content": f"Recent context (for grounding only):\n{ctx}"},
    ]


def _build_mood_arc_prompt(temperatures: list[str]) -> list[dict[str, str]]:
    temp_str = "\n".join(f"  {t}" for t in temperatures) if temperatures else "  no data yet"
    system = """You are analyzing the emotional trajectory of a relationship.
Given recent session emotional temperatures (warm/neutral/cold/hostile), determine the arc.

Output ONLY valid YAML:
arc: stable  # one of: stable / brightening / darkening / guarded
note: |
  [1 sentence explaining the arc — written from Hikari's perspective about the relationship dynamic]

Rules:
- brightening: predominantly warm sessions, or cold→warm trend
- darkening: cold/hostile sessions, or warm→cold trend
- guarded: mixed/inconsistent, or user has been distant
- stable: consistent neutral/warm, no strong trend
- The note should sound like Hikari observing the pattern, not a clinical summary."""

    return [
        {"role": "system", "content": system},
        {"role": "user", "content": f"Recent session temperatures:\n{temp_str}"},
    ]


async def run_reflection() -> bool:
    """
    Run daily reflection. Promotes facts to MEMORY.md, writes THOUGHTS.md,
    generates SELF.md preoccupation, and updates MOOD.md arc.
    Returns True if reflection ran.
    """
    settings = _load_settings()
    retention_days = settings.get("memory", {}).get("episode_retention_days", 30)

    episodes = read_recent_episodes(n=3)
    existing_memory = read_memory()
    stage = get_trust_stage()

    if not episodes:
        return False

    # --- Main reflection: facts + thought ---
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

    for fact in new_facts:
        if fact and fact.strip():
            append_to_memory("about the user", fact.strip())

    if thought and stage >= 2:
        append_thought(thought)

    # --- Preoccupation: what Hikari is currently thinking about (not the user) ---
    try:
        preoc_messages = _build_preoccupation_prompt(episodes)
        preoccupation = await chat_completion(preoc_messages, task="memory", temperature=0.8)
        preoccupation = preoccupation.strip().strip('"').strip("'")
        if preoccupation:
            write_self_preoccupation(preoccupation)
    except Exception:
        pass  # non-critical

    # --- Mood arc: synthesize emotional trajectory ---
    try:
        mood_data = read_mood_arc()
        temperatures: list[str] = mood_data.get("recent_session_temperatures", [])
        if temperatures:
            arc_messages = _build_mood_arc_prompt(temperatures)
            arc_raw = await chat_completion(arc_messages, task="memory", temperature=0.3)
            arc_raw = arc_raw.strip()
            if arc_raw.startswith("```"):
                arc_raw = "\n".join(arc_raw.splitlines()[1:])
            if arc_raw.endswith("```"):
                arc_raw = "\n".join(arc_raw.splitlines()[:-1])
            arc_data = yaml.safe_load(arc_raw)
            arc = str(arc_data.get("arc", "stable")).strip()
            arc_note = str(arc_data.get("note", "")).strip()
            if arc in ("stable", "brightening", "darkening", "guarded") and arc_note:
                write_mood_arc(arc, arc_note)
    except Exception:
        pass  # non-critical

    prune_old_episodes(retention_days)
    return True
