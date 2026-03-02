"""VisualSelf — image generation for Hikari sending photos."""

from __future__ import annotations

import base64
import os
import random
import re
from pathlib import Path
from typing import Any

import httpx
import yaml
from dotenv import load_dotenv

load_dotenv()

_ROOT = Path(__file__).parent.parent
_SETTINGS_PATH = _ROOT / "settings.yaml"
_APPEARANCE_MD = _ROOT / "character" / "APPEARANCE.md"

OPENROUTER_API_URL = "https://openrouter.ai/api/v1/images/generations"


def _load_settings() -> dict[str, Any]:
    with open(_SETTINGS_PATH) as f:
        return yaml.safe_load(f)


def _read_appearance_base() -> str:
    """Return the base appearance prompt from APPEARANCE.md."""
    try:
        content = _APPEARANCE_MD.read_text(encoding="utf-8")
        m = re.search(r"## base prompt\n\n(.+?)(?=\n##|\Z)", content, re.DOTALL)
        if m:
            return m.group(1).strip()
    except FileNotFoundError:
        pass
    return (
        "young japanese woman, 21, dark hair, urban style, realistic, "
        "natural lighting, authentic candid expression"
    )


# Scene suffixes keyed by (mood, stage) — returns a scene type key
_SCENE_MAP: dict[tuple[str, int], list[str]] = {
    # Stage 2
    ("tired", 2): ["late_night"],
    ("focused", 2): ["casual_desk"],
    ("irritable", 2): ["casual_desk"],
    ("weirdly good", 2): ["casual_desk", "outdoor_brief"],
    # Stage 3
    ("tired", 3): ["late_night", "soft_rare"],
    ("focused", 3): ["casual_desk", "outdoor_brief"],
    ("irritable", 3): ["casual_desk"],
    ("weirdly good", 3): ["soft_rare", "outdoor_brief", "intimate_stage3"],
    # Stage 4
    ("tired", 4): ["late_night", "stage4_charged"],
    ("focused", 4): ["casual_desk", "stage4_charged"],
    ("irritable", 4): ["casual_desk"],
    ("weirdly good", 4): ["stage4_charged", "outdoor_brief"],
}

_SCENE_SUFFIXES = {
    "casual_desk": (
        "at her desk, multiple monitors behind her, earphones around neck, "
        "side-lit, slight frown of concentration"
    ),
    "late_night": (
        "dim room, phone camera, tired eyes, oversized hoodie, "
        "no overhead light, slight shadows under eyes"
    ),
    "outdoor_brief": (
        "city street, natural daylight, not looking at camera, "
        "caught mid-thought, jacket"
    ),
    "soft_rare": (
        "soft diffuse light, slight almost-smile, not quite looking at camera, window light"
    ),
    "intimate_stage3": (
        "tasteful, close frame, natural light, she controls what she's showing, "
        "ambiguous — could be getting ready or just casual"
    ),
    "stage4_charged": (
        "dim room, late, looking at camera for once, slight flush, "
        "not explaining herself, phone camera, natural"
    ),
}


def get_photo_scene(mood: str, stage: int) -> str:
    """Return a scene description string for the given mood and stage."""
    capped = min(stage, 4)
    key = (mood, capped)
    scenes = _SCENE_MAP.get(key)
    if not scenes:
        # Fallback: pick by stage
        if stage >= 4:
            scenes = ["stage4_charged"]
        elif stage >= 3:
            scenes = ["casual_desk", "outdoor_brief"]
        else:
            scenes = ["casual_desk"]
    scene_key = random.choice(scenes)
    return _SCENE_SUFFIXES.get(scene_key, _SCENE_SUFFIXES["casual_desk"])


def _is_photo_enabled(settings: dict[str, Any]) -> bool:
    return bool(settings.get("photo", {}).get("enabled", False))


def _get_photo_model(settings: dict[str, Any]) -> str:
    return settings.get("photo", {}).get("model", "black-forest-labs/flux.2-klein")


def _get_max_per_day(settings: dict[str, Any]) -> int:
    return int(settings.get("photo", {}).get("max_per_day", 2))


def _get_stage_threshold(settings: dict[str, Any]) -> int:
    return int(settings.get("photo", {}).get("stage_threshold", 2))


def _get_heartbeat_probability(settings: dict[str, Any]) -> float:
    return float(settings.get("photo", {}).get("heartbeat_probability", 0.15))


def should_send_proactive_photo(stage: int, mood: str, settings: dict[str, Any]) -> bool:
    """True if a proactive photo should be sent in a heartbeat context."""
    if not _is_photo_enabled(settings):
        return False
    if stage < 3:
        return False
    if mood == "irritable":
        return False
    if random.random() >= _get_heartbeat_probability(settings):
        return False
    from .memory import get_photos_sent_today
    if get_photos_sent_today() >= _get_max_per_day(settings):
        return False
    return True


def can_send_photo(stage: int, mood: str, settings: dict[str, Any]) -> bool:
    """True if she can send a photo at all (user-requested or reactive)."""
    if not _is_photo_enabled(settings):
        return False
    if stage < _get_stage_threshold(settings):
        return False
    if mood == "irritable":
        return False
    from .memory import get_photos_sent_today
    if get_photos_sent_today() >= _get_max_per_day(settings):
        return False
    return True


async def _generate_photo_openrouter(prompt: str, model: str) -> bytes | None:
    """Generate a photo via OpenRouter images API."""
    api_key = os.getenv("OPENROUTER_API_KEY", "")
    if not api_key:
        return None
    try:
        async with httpx.AsyncClient(timeout=60.0) as client:
            resp = await client.post(
                OPENROUTER_API_URL,
                headers={
                    "Authorization": f"Bearer {api_key}",
                    "Content-Type": "application/json",
                },
                json={"model": model, "prompt": prompt, "n": 1},
            )
            resp.raise_for_status()
            data = resp.json()
            item = data.get("data", [{}])[0]
            if "b64_json" in item:
                return base64.b64decode(item["b64_json"])
            if "url" in item:
                img_resp = await client.get(item["url"])
                img_resp.raise_for_status()
                return img_resp.content
    except Exception:
        return None


async def generate_photo(mood: str, stage: int) -> bytes | None:
    """Generate a photo via OpenRouter. Returns raw bytes or None."""
    settings = _load_settings()
    appearance_base = _read_appearance_base()
    scene = get_photo_scene(mood, stage)
    prompt = f"{appearance_base}, {scene}"
    model = _get_photo_model(settings)
    return await _generate_photo_openrouter(prompt, model)
