# Hikari Tsukino Bot

Personal Telegram companion bot. Modern Japanese tsundere, 21, data science / AI / tech. Built to experiment with character + memory architecture on cheap LLMs.

MIT License. Designed for one user.

---

## Setup

**Requirements:** Python 3.12+, [uv](https://github.com/astral-sh/uv)

```bash
# Install dependencies
uv sync

# Copy env template
cp .env.example .env
# Edit .env — add your tokens
```

**`.env`:**
```
TELEGRAM_BOT_TOKEN=your_telegram_bot_token
OPENROUTER_API_KEY=your_openrouter_api_key
TELEGRAM_CHAT_ID=your_telegram_user_id  # optional, but required for heartbeat
```

Get your Telegram user ID: message [@userinfobot](https://t.me/userinfobot).

---

## Configuration

All settings live in `settings.yaml`. No code changes needed.

Key settings:
```yaml
models:
  chat: "openai/gpt-4o-mini"    # swap to any OpenRouter model ID

trust:
  progression_speed: "fast"     # slow | normal | fast | instant
  starting_stage: 0             # 0=stranger → 3=trusted

heartbeat:
  min_interval_hours: 4         # how often she reaches out
  max_interval_hours: 8
```

See [MODELS.md](MODELS.md) for model options and pricing.

---

## Run

```bash
uv run python -m bot.main
```

---

## Commands

| Command | What she says |
|---|---|
| `/start` | She's mildly annoyed you're bothering her |
| `/model [id]` | Switch the chat LLM at runtime |
| `/silence [minutes]` | She'll stop messaging for X minutes (default: 120) |
| `/unsilence` | Cancel silence mode |
| `/memory` | In-character: what she knows about you |
| `/mood` | In-character: how she's feeling today |
| `/forget [topic]` | Remove a topic from her memory |
| `/stats` | Out-of-character: trust stage, message count, current model |
| `/stage [0-3]` | Dev: manually set trust stage for testing |
| `/help` | Command list |

---

## Memory System

**Short-term:** Rolling 20-turn conversation window in context.

**Medium-term:** After 30 minutes of silence, a consolidation agent summarizes the session into `data/episodes/YYYY-MM-DD.md` and updates `data/USER.md`.

**Long-term:** Daily at 09:00, a reflection agent promotes stable facts to `data/MEMORY.md` and writes `data/THOUGHTS.md` (her private diary — developer-visible only, never accessible via chat).

---

## Trust Stages

She warms up over time. Speed is configurable.

| Stage | Behavior |
|---|---|
| 0 — Stranger | Sharp edges. All tsun. |
| 1 — Acquaintance | Lighter teasing. One real question per session. |
| 2 — Regular | References past things. One soft moment per session. |
| 3 — Trusted | Dere leaks more. She breaks silences first. She writes her diary about you. |

---

## Data Files

| File | Description |
|---|---|
| `data/USER.md` | Live user facts, trust stage, open loops — written by bot |
| `data/MEMORY.md` | Curated long-term facts — promoted by reflection agent |
| `data/THOUGHTS.md` | Her private diary — written by reflection agent, dev-only |
| `data/HEARTBEAT.md` | Scheduler state: silence, last sent, used excuses |
| `data/episodes/` | Session summaries |
| `character/IDENTITY.md` | Who she is — loaded every turn |
| `character/SOUL.md` | Response rules, voice, banned phrases — loaded every turn |

---

## Tests

```bash
uv run pytest                   # unit tests (no API key needed)
uv run pytest -k "integration"  # integration tests (requires OPENROUTER_API_KEY)
uv run ruff check .             # lint
uv run ruff format .            # format
```

---

## Adding Voice (v0.2)

Not in v0.1. Planned: Whisper for voice-to-text, TTS for text-to-voice.
