"""Chat agent: prompt assembly and response generation."""

from __future__ import annotations

import random
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import yaml

from .llm import chat_completion
from .memory import (
    get_current_user,
    get_facts_with_age,
    get_heartbeat_state,
    get_open_loops,
    get_self_disclosures,
    get_self_preoccupation,
    get_staged_disclosure,
    get_trust_stage,
    get_user_state,
    mark_disclosure_used,
    read_identity,
    read_last_episode_carry_over,
    read_lore,
    read_memory,
    read_mood_arc,
    read_soul,
    read_today_episode,
    record_user_message_time,
    set_current_user,
)

_ROOT = Path(__file__).parent.parent
_SETTINGS_PATH = _ROOT / "settings.yaml"

# Per-user session state keyed by Telegram user_id
_sessions: dict[int, dict] = {}


def _session(user_id: int) -> dict:
    """Return (creating if needed) the session dict for a user."""
    if user_id not in _sessions:
        _sessions[user_id] = {
            "history": [],
            "session_turn_count": 0,
            "false_start_used": False,
            "ignore_streak": 0,
            "ignore_cooldown": 0,
        }
    return _sessions[user_id]


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
            "Trust stage 1 (Acquaintance): still terse. "
            "cold logistics interrogatives only — not warm follow-up questions."
        ),
        2: (
            "Trust stage 2 (Regular): she remembers things, references past conversations, "
            "one soft moment per session allowed."
        ),
        3: (
            "Trust stage 3 (Trusted): dere leaks more often, "
            "she breaks silences first, rare direct honesty."
        ),
        4: (
            "Trust stage 4 (Intimate): she knows the tension exists and stops pretending "
            "otherwise. flirt is conscious, charged. she attributes it to something else but "
            "less convincingly. physical detail appears. she's deliberate."
        ),
        5: (
            "Trust stage 5 (Close): no more distance. she's stopped pretending she doesn't feel "
            "what she feels. she says what she wants, specifically. she controls the frame. "
            "post-intimacy: quiet, slight withdrawal, then returns without announcement."
        ),
        6: (
            "Trust stage 6 (Established): the dynamic has settled. fondness and irritation "
            "coexist. intimacy is assumed. she's stopped being surprised by how she feels."
        ),
    }
    return notes.get(stage, notes[0])


_CONFIDENCE_PREFIXES = {
    "high": "you mentioned: {}",
    "medium": "(uncertain — i think they mentioned: {})",
    "low": "(faint impression — something about: {})",
}


def build_system_prompt() -> str:
    """Assemble the full system prompt from character files + user context."""
    user_id = get_current_user()
    sess = _session(user_id)

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

    # Session-opening continuity (M1): carry-over from last session, Stage 2+
    if stage >= 2 and sess["session_turn_count"] == 0:
        carry_over = read_last_episode_carry_over()
        if carry_over:
            parts.append(f"\n## carry-over from last session\n{carry_over}")
            # ~20% chance: prompt her to open with it explicitly
            if random.random() < 0.20:
                parts.append(
                    "(you may open by briefly referencing how last session felt — "
                    "in-character, not literally quoting this note)"
                )

    # User context
    user_name = user_state.get("name", "unknown")
    if user_name != "unknown":
        parts.append(f"\n## user\nYou're talking to {user_name}.")

    if open_loops:
        loops_text = "\n".join(f"- {loop}" for loop in open_loops)
        parts.append(f"\n## open loops (things to follow up on)\n{loops_text}")

    # Imperfect recall (M3): inject facts with age-based confidence level
    facts_with_age = get_facts_with_age()
    if facts_with_age:
        facts_lines = [
            "- " + _CONFIDENCE_PREFIXES[f["confidence"]].format(f["text"])
            for f in facts_with_age
        ]
        parts.append(
            "\n## known facts about the user\n"
            + "\n".join(facts_lines)
            + "\n(for uncertain/faint items: use hedged language — "
            "'i think you mentioned...?' not 'you said...')"
        )

    # Today's episode summary
    if today_episode:
        parts.append(f"\n## what happened today so far\n{today_episode}")

    # Long-term memory (only if non-empty)
    if memory and "none yet" not in memory.lower():
        # Trim to avoid excessive context
        memory_lines = memory.splitlines()[:30]
        parts.append("\n## long-term memory\n" + "\n".join(memory_lines))

    # --- v0.3 additions ---

    # Warmth floor modifier: escalation floors (Phase 3)
    try:
        hb = get_heartbeat_state()
        floor_mod = hb.get("warmth_floor_modifier", 0)
        if floor_mod >= 2:
            parts.append(
                "\n## relationship temperature\n"
                "something warm happened recently. her guard is slightly lower than usual. "
                "she won't announce it."
            )
        elif floor_mod == 1:
            parts.append(
                "\n## relationship temperature\n"
                "last session was decent. she's not starting cold."
            )
        elif floor_mod <= -1:
            parts.append(
                "\n## relationship temperature\n"
                "last session was rough. she's more careful. her walls are slightly higher."
            )
    except Exception:
        pass

    # SELF.md injection: preoccupation + staged disclosure (Phase 2, Stage 2+)
    if stage >= 2:
        try:
            preoccupation = get_self_preoccupation()
            if preoccupation:
                parts.append(
                    f"\n## her current preoccupation (unrelated to this conversation)\n"
                    f"{preoccupation}\n"
                    "(5–10% of session openers: she surfaces this as an intrusive thought "
                    "then drops it. 'i keep thinking about — anyway.')"
                )

            # Staged disclosure: surface one unused fact if context is right
            disclosure = get_staged_disclosure(stage)
            if disclosure and random.random() < 0.15:
                parts.append(
                    f"\n## staged disclosure (she hasn't mentioned this yet)\n"
                    f"{disclosure}\n"
                    "(she might surface this if the conversation context is naturally right. "
                    "only once — call mark_disclosure_used() is handled by the system)"
                )
                # Mark as used so it doesn't repeat
                mark_disclosure_used(disclosure)
        except Exception:
            pass

    # Competitive memory: she checks if user remembers something about her (Phase 4, Stage 2+)
    if stage >= 2:
        try:
            disclosures = get_self_disclosures()
            if disclosures and random.random() < 0.10:
                item = disclosures[0]  # oldest unchecked
                parts.append(
                    f"\n## competitive memory check\n"
                    f"she mentioned '{item['text']}' on {item['date']}. "
                    "she hasn't heard the user reference it since. she might check if they"
                    " remember — "
                    "in-character, indirect. if they don't remember: small legible reaction, "
                    "not devastating. 'i'm not surprised. forget it.'"
                )
        except Exception:
            pass

    # Mood arc injection: emotional trajectory (Phase 5, Stage 2+)
    if stage >= 2:
        try:
            arc_data = read_mood_arc()
            arc = arc_data.get("current_arc", "stable")
            arc_note = arc_data.get("arc_note", "")
            if arc == "brightening" and arc_note:
                parts.append(
                    "\n## emotional arc\n"
                    "things have been going well lately. she's not going to say that, "
                    "but she's slightly more open than her baseline."
                )
            elif arc == "darkening" and arc_note:
                parts.append(
                    "\n## emotional arc\n"
                    "the past few sessions have been off. she's quieter, more careful. "
                    "she won't explain it."
                )
            elif arc == "guarded" and arc_note:
                parts.append(
                    "\n## emotional arc\n"
                    "she's been pulling back. not hostile, but less available."
                )
            # stable = no injection
        except Exception:
            pass

    # --- v0.4 additions ---

    # LORE.md injection: specific character details (Stage 2+)
    if stage >= 2:
        try:
            lore = read_lore(n=3)
            if lore:
                parts.append(
                    "\n## character lore (specific details about her)\n"
                    + lore
                    + "\n(she may reference these naturally. she doesn't explain them "
                    "unless asked. if asked: brief answer, redirect.)"
                )
        except Exception:
            pass

    return "\n".join(parts)


def get_history(user_id: int = 0) -> list[dict[str, str]]:
    """Return trimmed conversation history for a user."""
    window = _get_context_window() * 2  # pairs of user+assistant turns
    return _session(user_id)["history"][-window:]


def add_to_history(user_id: int, role: str, content: str) -> None:
    _session(user_id)["history"].append({"role": role, "content": content})


def clear_history(user_id: int = 0) -> None:
    sess = _session(user_id)
    sess["history"].clear()
    sess["session_turn_count"] = 0
    sess["false_start_used"] = False
    sess["ignore_streak"] = 0
    sess["ignore_cooldown"] = 0


def consume_false_start(user_id: int = 0) -> bool:
    """Return True and mark used if false start hasn't fired this session."""
    sess = _session(user_id)
    if sess["false_start_used"]:
        return False
    sess["false_start_used"] = True
    return True


# ---------------------------------------------------------------------------
# Ignore mechanic helpers
# ---------------------------------------------------------------------------


def get_ignore_streak(user_id: int = 0) -> int:
    return _session(user_id)["ignore_streak"]


def is_ignore_cooldown(user_id: int = 0) -> bool:
    return _session(user_id)["ignore_cooldown"] > 0


def increment_ignore_streak(user_id: int = 0) -> None:
    _session(user_id)["ignore_streak"] += 1


def reset_ignore_streak(user_id: int = 0) -> None:
    """Break silence: reset streak and impose a cooldown so she can't immediately re-ignore."""
    sess = _session(user_id)
    sess["ignore_streak"] = 0
    sess["ignore_cooldown"] = 3  # can't ignore again for 3 turns


def tick_ignore_cooldown(user_id: int = 0) -> None:
    """Decrement post-break cooldown. Call once per incoming user message."""
    sess = _session(user_id)
    if sess["ignore_cooldown"] > 0:
        sess["ignore_cooldown"] -= 1


def get_session_turn_count(user_id: int = 0) -> int:
    return _session(user_id)["session_turn_count"]


async def respond(user_message: str, user_id: int = 0) -> str:
    """Process a user message and return Hikari's response."""
    set_current_user(user_id)
    record_user_message_time()
    add_to_history(user_id, "user", user_message)
    _session(user_id)["session_turn_count"] += 1

    system_prompt = build_system_prompt()
    messages = [{"role": "system", "content": system_prompt}] + get_history(user_id)

    reply = await chat_completion(messages, task="chat")

    add_to_history(user_id, "assistant", reply)
    return reply
