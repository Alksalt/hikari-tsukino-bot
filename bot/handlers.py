"""Telegram command and message handlers."""

from __future__ import annotations

import asyncio
import logging
import random
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import yaml
from telegram import Update
from telegram.constants import ChatAction
from telegram.ext import ContextTypes

from .chat import (
    consume_false_start,
    get_daily_mood,
    get_ignore_streak,
    increment_ignore_streak,
    is_ignore_cooldown,
    reset_ignore_streak,
    respond,
    tick_ignore_cooldown,
)
from .consolidate import run_consolidation
from .llm import chat_completion_vision, get_model, update_model_in_settings
from .memory import (
    forget_topic,
    get_heartbeat_state,
    get_meaningful_exchanges,
    get_trust_stage,
    get_user_state,
    read_identity,
    read_soul,
    record_user_message_time,
    set_silence,
    set_trust_stage,
)

logger = logging.getLogger(__name__)

_ROOT = Path(__file__).parent.parent
_SETTINGS_PATH = _ROOT / "settings.yaml"


def _load_settings() -> dict[str, Any]:
    with open(_SETTINGS_PATH) as f:
        return yaml.safe_load(f)


def _get_allowed_ids() -> list[int]:
    settings = _load_settings()
    return settings.get("telegram", {}).get("allowed_user_ids", [])


def _is_allowed(user_id: int) -> bool:
    allowed = _get_allowed_ids()
    if not allowed:
        return True
    return user_id in allowed


def _calculate_delay(response: str, mood: str, settings: dict[str, Any]) -> float:
    """Calculate realistic send delay in seconds based on response length and mood."""
    delay_cfg = settings.get("response_delay", {})
    if not delay_cfg.get("enabled", False):
        return 0.0

    base = float(delay_cfg.get("base_seconds", 1.0))
    ms_per_char = float(delay_cfg.get("ms_per_char", 35))
    cap = float(delay_cfg.get("cap_seconds", 10.0))

    total = base + (len(response) * ms_per_char / 1000.0)
    total = min(total, cap)

    if mood == "irritable":
        total *= float(delay_cfg.get("mood_irritable_factor", 0.7))
    elif mood == "tired":
        total *= float(delay_cfg.get("mood_tired_factor", 1.3))

    return total


async def _send_with_delay(update: Update, text: str, mood: str = "") -> None:
    """Send message with typing indicator and realistic delay if enabled."""
    settings = _load_settings()
    delay_cfg = settings.get("response_delay", {})

    if not delay_cfg.get("enabled", False):
        await update.message.reply_text(text)
        return

    pre_pause = float(delay_cfg.get("pre_indicator_pause", 0.5))
    total_delay = _calculate_delay(text, mood, settings)

    # Pre-indicator pause (she reacts before composing)
    if pre_pause > 0:
        await asyncio.sleep(pre_pause)

    # False start: typing → disappears → reappears (~10%, long msgs, Stage 2+, once/session)
    false_start_cfg = delay_cfg.get("false_start_enabled", True)
    stage = get_trust_stage()
    if (
        false_start_cfg
        and len(text) > 80
        and stage >= 2
        and random.random() < 0.10
        and consume_false_start()
    ):
        await update.message.chat.send_action(ChatAction.TYPING)
        await asyncio.sleep(2.5)
        # Let indicator expire naturally (~5s Telegram timeout), pause before restart
        await asyncio.sleep(1.5)
        # Remaining typing duration (subtract false start time already spent)
        remaining = max(0.0, total_delay - pre_pause - 4.0)
        if remaining > 0:
            await update.message.chat.send_action(ChatAction.TYPING)
            await asyncio.sleep(remaining)
    else:
        # Normal path: show typing for calculated duration
        typing_duration = max(0.0, total_delay - pre_pause)
        if typing_duration > 0:
            await update.message.chat.send_action(ChatAction.TYPING)
            await asyncio.sleep(typing_duration)

    await update.message.reply_text(text)


async def _send(update: Update, text: str) -> None:
    await update.message.reply_text(text)


# ---------------------------------------------------------------------------
# Ignore mechanic
# ---------------------------------------------------------------------------

# Probability of ignoring a message by mood × trust stage
_IGNORE_PROBS: dict[str, dict[int, float]] = {
    "irritable":    {0: 0.30, 1: 0.20, 2: 0.10, 3: 0.05},
    "tired":        {0: 0.20, 1: 0.12, 2: 0.05, 3: 0.02},
    "focused":      {0: 0.10, 1: 0.05, 2: 0.02, 3: 0.00},
    "weirdly good": {0: 0.05, 1: 0.02, 2: 0.00, 3: 0.00},
}

# What she sends when ignoring (action lines)
_IGNORE_ACTIONS = [
    "[ignores]",
    "[reads it. says nothing.]",
    "[doesn't answer]",
]

# What she sends when finally breaking silence
_BREAK_ACTIONS = [
    "...fine. what.",
    "ugh. what.",
    "i wasn't ignoring you.",
    "you're persistent. fine.",
]


def _should_ignore(mood: str, stage: int, settings: dict[str, Any]) -> bool:
    """Return True if this message should be ignored (no real response)."""
    ignore_cfg = settings.get("ignore", {})
    if not ignore_cfg.get("enabled", True):
        return False
    if is_ignore_cooldown():
        return False
    max_streak = int(ignore_cfg.get("max_streak", 3))
    if get_ignore_streak() >= max_streak:
        return False  # streak maxed — must break silence now
    prob_row = _IGNORE_PROBS.get(mood, _IGNORE_PROBS["focused"])
    prob = prob_row.get(stage, 0.0)
    return random.random() < prob


# ---------------------------------------------------------------------------
# Command handlers
# ---------------------------------------------------------------------------


async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not _is_allowed(update.effective_user.id):
        return

    reply = await respond(
        "__system: user just started the bot for the first time. give a brief intro as Hikari — "
        "annoyed but present. don't say 'I'm Hikari' — she doesn't introduce herself like an AI."
    )
    await _send(update, reply)


async def cmd_model(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not _is_allowed(update.effective_user.id):
        return

    args = context.args
    if not args:
        current = get_model("chat")
        await _send(update, f"current model: {current}\nusage: /model <openrouter-model-id>")
        return

    new_model = args[0].strip()
    update_model_in_settings("chat", new_model)
    # Hikari's in-character acknowledgment
    await _send(
        update,
        f"fine. switched to {new_model}. don't blame me if it's worse.",
    )


async def cmd_silence(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not _is_allowed(update.effective_user.id):
        return

    args = context.args
    minutes = 120  # default 2 hours

    if args:
        try:
            minutes = int(args[0])
        except ValueError:
            await _send(update, "...that's not a number. /silence [minutes]")
            return

    until = datetime.now(UTC) + timedelta(minutes=minutes)
    set_silence(until)

    hours = minutes // 60
    mins = minutes % 60
    duration_str = f"{hours}h {mins}m" if hours else f"{mins}m"
    msg = f"fine. i'll be quiet for {duration_str}. not like i was going to say anything anyway."
    await _send(update, msg)


async def cmd_unsilence(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not _is_allowed(update.effective_user.id):
        return
    set_silence(None)
    await _send(update, "...fine. silence mode off. not that you asked nicely.")


async def cmd_memory(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not _is_allowed(update.effective_user.id):
        return

    user_state = get_user_state()
    known_facts = user_state.get("known_facts", [])
    open_loops = user_state.get("open_loops", [])
    stage = get_trust_stage()

    if not known_facts and not open_loops:
        await _send(
            update,
            "i don't know much about you yet. you haven't told me anything worth remembering.",
        )
        return

    # In-character summary
    prompt_parts = [
        "__system: summarize what you know about the user in Hikari's voice. "
        "in-character, short, dry. no markdown."
    ]
    if known_facts:
        prompt_parts.append("known facts: " + "; ".join(known_facts))
    if open_loops:
        prompt_parts.append("things to follow up on: " + "; ".join(open_loops))
    prompt_parts.append(f"trust stage: {stage}")

    reply = await respond("\n".join(prompt_parts))
    await _send(update, reply)


async def cmd_mood(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not _is_allowed(update.effective_user.id):
        return
    mood = get_daily_mood()
    reply = await respond(
        f"__system: user asked about your current mood. your mood today is '{mood}'. "
        "describe it in-character, briefly, in Hikari's voice. stay in character."
    )
    await _send(update, reply)


async def cmd_forget(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not _is_allowed(update.effective_user.id):
        return

    args = context.args
    if not args:
        await _send(update, "forget what? /forget [topic]")
        return

    topic = " ".join(args).strip()
    forget_topic(topic)
    await _send(update, f"fine. forgot anything about '{topic}'. it's gone.")


async def cmd_stats(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not _is_allowed(update.effective_user.id):
        return

    stage = get_trust_stage()
    exchanges = get_meaningful_exchanges()
    chat_model = get_model("chat")
    memory_model = get_model("memory")
    hb_state = get_heartbeat_state()
    proactive_count = hb_state.get("proactive_count", 0)

    stage_names = {0: "stranger", 1: "acquaintance", 2: "regular", 3: "trusted"}
    stage_name = stage_names.get(stage, "unknown")

    text = (
        f"[stats — out of character]\n"
        f"trust stage: {stage} ({stage_name})\n"
        f"meaningful sessions: {exchanges}\n"
        f"proactive messages sent: {proactive_count}\n"
        f"chat model: {chat_model}\n"
        f"memory model: {memory_model}"
    )
    await _send(update, text)


async def cmd_stage(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Dev command: manually set trust stage."""
    if not _is_allowed(update.effective_user.id):
        return

    args = context.args
    if not args:
        current = get_trust_stage()
        await _send(update, f"current trust stage: {current}\nusage: /stage [0-3]")
        return

    try:
        stage = int(args[0])
        if stage not in (0, 1, 2, 3):
            raise ValueError
    except ValueError:
        await _send(update, "stage must be 0, 1, 2, or 3.")
        return

    set_trust_stage(stage)
    await _send(update, f"[dev] trust stage set to {stage}.")


async def cmd_help(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not _is_allowed(update.effective_user.id):
        return

    text = (
        "commands. you're welcome.\n\n"
        "/model [id] — switch chat model\n"
        "/silence [minutes] — i'll stop bothering you\n"
        "/unsilence — i can talk again\n"
        "/memory — what i know about you\n"
        "/mood — how i'm feeling today\n"
        "/forget [topic] — i'll pretend i never knew\n"
        "/stats — boring numbers\n"
        "/stage [0-3] — dev: set trust stage\n"
        "/help — this"
    )
    await _send(update, text)


# ---------------------------------------------------------------------------
# Message handler
# ---------------------------------------------------------------------------


async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not update.message or not update.message.text:
        return
    if not _is_allowed(update.effective_user.id):
        return

    user_text = update.message.text.strip()
    if not user_text:
        return

    try:
        settings = _load_settings()
        mood = get_daily_mood()
        stage = get_trust_stage()

        # Count down post-break cooldown (once per incoming message)
        tick_ignore_cooldown()

        # Ignore mechanic: sometimes she just doesn't answer
        if _should_ignore(mood, stage, settings):
            increment_ignore_streak()
            record_user_message_time()  # still update heartbeat state
            action = random.choice(_IGNORE_ACTIONS)
            await _send_with_delay(update, action, mood=mood)
            return

        # If a streak was active: break silence with a short line before responding
        if get_ignore_streak() > 0:
            break_text = random.choice(_BREAK_ACTIONS)
            await _send_with_delay(update, break_text, mood=mood)
            reset_ignore_streak()

        reply = await respond(user_text)
        await _send_with_delay(update, reply, mood=mood)
    except Exception as e:
        logger.error("Chat response failed: %s", e)
        # Silent failure — Hikari goes quiet rather than sending an error


# ---------------------------------------------------------------------------
# Photo handler
# ---------------------------------------------------------------------------


async def handle_photo(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle incoming photos — Hikari reacts in-character via vision model."""
    if not update.message or not update.message.photo:
        return
    if not _is_allowed(update.effective_user.id):
        return

    try:
        # Highest-resolution version
        photo = update.message.photo[-1]
        file = await context.bot.get_file(photo.file_id)
        image_url = file.file_path  # Telegram CDN URL

        # Build prompt: system context + optional caption
        identity = read_identity()
        soul = read_soul()
        caption = update.message.caption or ""
        caption_note = f' The user added a caption: "{caption}".' if caption else ""

        prompt = (
            f"{identity}\n\n{soul}\n\n"
            "You just received an image from the user."
            f"{caption_note} "
            "React in-character as Hikari. You have opinions. "
            "1-3 sentences max. No markdown. Not impressed by default."
        )

        mood = get_daily_mood()
        reply = await chat_completion_vision(prompt, image_url, task="vision")
        await _send_with_delay(update, reply, mood=mood)
    except Exception as e:
        logger.error("Photo handler failed: %s", e)


# ---------------------------------------------------------------------------
# Session timeout callback (called from main.py scheduler)
# ---------------------------------------------------------------------------


async def session_timeout_callback() -> None:
    """Called when session timeout fires — triggers memory consolidation."""
    try:
        ran = await run_consolidation()
        if ran:
            logger.info("Memory consolidation completed.")
    except Exception as e:
        logger.error("Consolidation failed: %s", e)
