"""OpenRouter LLM client with model routing from settings.yaml."""

from __future__ import annotations

import os
from typing import Any

import httpx
import yaml
from dotenv import load_dotenv

load_dotenv()

OPENROUTER_API_URL = "https://openrouter.ai/api/v1/chat/completions"
_settings_cache: dict[str, Any] | None = None


def _load_settings() -> dict[str, Any]:
    global _settings_cache
    if _settings_cache is None:
        settings_path = os.path.join(os.path.dirname(__file__), "..", "settings.yaml")
        with open(settings_path) as f:
            _settings_cache = yaml.safe_load(f)
    return _settings_cache


def reload_settings() -> None:
    """Force reload of settings.yaml (used after /model command)."""
    global _settings_cache
    _settings_cache = None


def get_model(task: str = "chat") -> str:
    """Return the model ID for a given task from settings.yaml."""
    settings = _load_settings()
    models = settings.get("models", {})
    return models.get(task, models.get("chat", "openai/gpt-4o-mini"))


async def chat_completion(
    messages: list[dict[str, str]],
    task: str = "chat",
    temperature: float = 0.85,
) -> str:
    """Send messages to OpenRouter and return the response text."""
    api_key = os.environ.get("OPENROUTER_API_KEY")
    if not api_key:
        raise ValueError("OPENROUTER_API_KEY not set in environment")

    model = get_model(task)
    payload = {
        "model": model,
        "messages": messages,
        "temperature": temperature,
    }
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
        "HTTP-Referer": "https://github.com/hikari-tsukino-bot",
        "X-Title": "Hikari Tsukino Bot",
    }

    async with httpx.AsyncClient(timeout=60.0) as client:
        response = await client.post(OPENROUTER_API_URL, json=payload, headers=headers)
        response.raise_for_status()
        data = response.json()

    return data["choices"][0]["message"]["content"].strip()


async def chat_completion_vision(
    text_prompt: str,
    image_url: str,
    task: str = "vision",
    temperature: float = 0.85,
) -> str:
    """Send a vision request (text + image URL) to OpenRouter."""
    api_key = os.environ.get("OPENROUTER_API_KEY")
    if not api_key:
        raise ValueError("OPENROUTER_API_KEY not set in environment")

    model = get_model(task)
    payload = {
        "model": model,
        "messages": [
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": text_prompt},
                    {"type": "image_url", "image_url": {"url": image_url}},
                ],
            }
        ],
        "temperature": temperature,
    }
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
        "HTTP-Referer": "https://github.com/hikari-tsukino-bot",
        "X-Title": "Hikari Tsukino Bot",
    }

    async with httpx.AsyncClient(timeout=60.0) as client:
        response = await client.post(OPENROUTER_API_URL, json=payload, headers=headers)
        response.raise_for_status()
        data = response.json()

    return data["choices"][0]["message"]["content"].strip()


def update_model_in_settings(task: str, model_id: str) -> None:
    """Update a model ID in settings.yaml and reload the cache."""
    settings_path = os.path.join(os.path.dirname(__file__), "..", "settings.yaml")
    with open(settings_path) as f:
        content = f.read()
        settings = yaml.safe_load(content)

    settings.setdefault("models", {})[task] = model_id

    with open(settings_path, "w") as f:
        yaml.dump(settings, f, default_flow_style=False, allow_unicode=True, sort_keys=False)

    reload_settings()
