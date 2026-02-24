"""Entry point: Telegram application + APScheduler boot."""

from __future__ import annotations

import logging
import os
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import yaml
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.interval import IntervalTrigger
from dotenv import load_dotenv
from telegram.ext import Application, CommandHandler, MessageHandler, filters

from .handlers import (
    cmd_forget,
    cmd_help,
    cmd_memory,
    cmd_model,
    cmd_mood,
    cmd_silence,
    cmd_stage,
    cmd_start,
    cmd_stats,
    cmd_unsilence,
    handle_message,
    session_timeout_callback,
)
from .heartbeat import run_heartbeat
from .memory import get_heartbeat_state
from .reflect import run_reflection

load_dotenv()

logging.basicConfig(
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)

_ROOT = Path(__file__).parent.parent
_SETTINGS_PATH = _ROOT / "settings.yaml"


def _load_settings() -> dict[str, Any]:
    with open(_SETTINGS_PATH) as f:
        return yaml.safe_load(f)


def _get_chat_id() -> int | None:
    """Get the configured Telegram chat ID (first allowed user or env override)."""
    chat_id_env = os.environ.get("TELEGRAM_CHAT_ID")
    if chat_id_env:
        try:
            return int(chat_id_env)
        except ValueError:
            pass

    settings = _load_settings()
    allowed = settings.get("telegram", {}).get("allowed_user_ids", [])
    if allowed:
        return allowed[0]
    return None


def build_application() -> Application:
    token = os.environ.get("TELEGRAM_BOT_TOKEN")
    if not token:
        raise ValueError("TELEGRAM_BOT_TOKEN not set in environment")

    app = Application.builder().token(token).build()

    # Commands
    app.add_handler(CommandHandler("start", cmd_start))
    app.add_handler(CommandHandler("model", cmd_model))
    app.add_handler(CommandHandler("silence", cmd_silence))
    app.add_handler(CommandHandler("unsilence", cmd_unsilence))
    app.add_handler(CommandHandler("memory", cmd_memory))
    app.add_handler(CommandHandler("mood", cmd_mood))
    app.add_handler(CommandHandler("forget", cmd_forget))
    app.add_handler(CommandHandler("stats", cmd_stats))
    app.add_handler(CommandHandler("stage", cmd_stage))
    app.add_handler(CommandHandler("help", cmd_help))

    # Messages
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    return app


async def _setup_scheduler(app: Application) -> AsyncIOScheduler:
    settings = _load_settings()
    scheduler = AsyncIOScheduler()

    # Session timeout: check every minute if we should consolidate
    session_timeout = settings.get("session", {}).get("timeout_minutes", 30)
    last_check: dict[str, Any] = {"last_message_ts": None}

    async def session_check() -> None:
        state = get_heartbeat_state()
        last_user_raw = state.get("last_user_message")
        if not last_user_raw:
            return

        try:
            last_user = datetime.fromisoformat(str(last_user_raw))
            if last_user.tzinfo is None:
                last_user = last_user.replace(tzinfo=UTC)
        except (ValueError, TypeError):
            return

        elapsed = (datetime.now(UTC) - last_user).total_seconds()
        if elapsed >= session_timeout * 60:
            # Only trigger once per session (check if it's a new timeout event)
            prev = last_check.get("last_message_ts")
            if prev != last_user_raw:
                last_check["last_message_ts"] = last_user_raw
                await session_timeout_callback()

    scheduler.add_job(session_check, IntervalTrigger(minutes=1), id="session_check")

    # Heartbeat: check every 15 minutes (actual send respects the interval setting)
    chat_id = _get_chat_id()

    async def heartbeat_check() -> None:
        if chat_id is None:
            return

        async def send_fn(text: str) -> None:
            await app.bot.send_message(chat_id=chat_id, text=text)

        await run_heartbeat(send_fn)

    scheduler.add_job(heartbeat_check, IntervalTrigger(minutes=15), id="heartbeat_check")

    # Daily reflection: run at configured hour
    reflection_hour = settings.get("memory", {}).get("reflection_hour", 9)

    async def daily_reflection() -> None:
        await run_reflection()

    scheduler.add_job(
        daily_reflection,
        "cron",
        hour=reflection_hour,
        minute=0,
        id="daily_reflection",
    )

    return scheduler


def main() -> None:
    settings = _load_settings()
    starting_stage_env = settings.get("trust", {}).get("starting_stage", 0)

    # Set initial trust stage if starting fresh
    from .memory import set_trust_stage
    if starting_stage_env == 3:
        set_trust_stage(3)

    app = build_application()

    async def post_init(application: Application) -> None:
        scheduler = await _setup_scheduler(application)
        scheduler.start()
        logger.info("Scheduler started.")

    app.post_init = post_init

    logger.info("Starting Hikari Tsukino bot...")
    app.run_polling(drop_pending_updates=True)


if __name__ == "__main__":
    main()
