"""Entry point: Telegram application + APScheduler boot."""

from __future__ import annotations

import logging
import os  # kept for TELEGRAM_BOT_TOKEN
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import yaml
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.interval import IntervalTrigger
from dotenv import load_dotenv
from telegram import BotCommand
from telegram.ext import Application, CommandHandler, MessageHandler, filters

from .handlers import (
    cmd_forget,
    cmd_help,
    cmd_memory,
    cmd_model,
    cmd_mood,
    cmd_photo,
    cmd_silence,
    cmd_stage,
    cmd_start,
    cmd_stats,
    cmd_unsilence,
    handle_message,
    handle_photo,
    session_timeout_callback,
)
from .heartbeat import run_heartbeat
from .memory import get_heartbeat_state, list_all_user_ids, set_current_user
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
    app.add_handler(CommandHandler("photo", cmd_photo))
    app.add_handler(CommandHandler("help", cmd_help))

    # Messages
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    app.add_handler(MessageHandler(filters.PHOTO, handle_photo))

    return app


async def _setup_scheduler(app: Application) -> AsyncIOScheduler:
    settings = _load_settings()
    scheduler = AsyncIOScheduler()

    # Session timeout: check every minute per user if we should consolidate
    session_timeout = settings.get("session", {}).get("timeout_minutes", 30)
    # Track last seen message timestamp per user to avoid double-firing
    _last_seen: dict[int, Any] = {}

    async def session_check() -> None:
        for uid in list_all_user_ids():
            set_current_user(uid)
            state = get_heartbeat_state()
            last_user_raw = state.get("last_user_message")
            if not last_user_raw:
                continue

            try:
                last_user = datetime.fromisoformat(str(last_user_raw))
                if last_user.tzinfo is None:
                    last_user = last_user.replace(tzinfo=UTC)
            except (ValueError, TypeError):
                continue

            elapsed = (datetime.now(UTC) - last_user).total_seconds()
            if elapsed >= session_timeout * 60:
                prev = _last_seen.get(uid)
                if prev != last_user_raw:
                    _last_seen[uid] = last_user_raw
                    await session_timeout_callback(uid)

    scheduler.add_job(session_check, IntervalTrigger(minutes=1), id="session_check")

    # Heartbeat: check every 15 minutes per user
    async def heartbeat_check() -> None:
        for uid in list_all_user_ids():
            set_current_user(uid)

            async def send_fn(text: str, _uid: int = uid) -> None:
                await app.bot.send_message(chat_id=_uid, text=text)

            await run_heartbeat(send_fn)

    scheduler.add_job(heartbeat_check, IntervalTrigger(minutes=15), id="heartbeat_check")

    # Daily reflection: run at configured hour for each user
    reflection_hour = settings.get("memory", {}).get("reflection_hour", 9)

    async def daily_reflection() -> None:
        for uid in list_all_user_ids():
            await run_reflection(uid)

    scheduler.add_job(
        daily_reflection,
        "cron",
        hour=reflection_hour,
        minute=0,
        id="daily_reflection",
    )

    return scheduler


def main() -> None:
    app = build_application()

    async def post_init(application: Application) -> None:
        await application.bot.set_my_commands([
            BotCommand("start", "wake her up"),
            BotCommand("help", "list commands"),
            BotCommand("mood", "what mood she's in today"),
            BotCommand("memory", "what she remembers about you"),
            BotCommand("forget", "make her forget a topic"),
            BotCommand("silence", "stop proactive messages for a while"),
            BotCommand("unsilence", "let her talk again"),
            BotCommand("stats", "numbers — trust stage, sessions, models"),
            BotCommand("model", "switch the chat model"),
            BotCommand("stage", "[dev] set trust stage manually"),
            BotCommand("photo", "[dev] force-generate a test photo"),
        ])
        scheduler = await _setup_scheduler(application)
        scheduler.start()
        logger.info("Scheduler started.")

    app.post_init = post_init

    logger.info("Starting Hikari Tsukino bot...")
    app.run_polling(drop_pending_updates=True)


if __name__ == "__main__":
    main()
