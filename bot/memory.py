"""All file I/O for character data: USER.md, MEMORY.md, THOUGHTS.md, HEARTBEAT.md, episodes/."""

from __future__ import annotations

import re
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Any

import yaml

# Paths
_ROOT = Path(__file__).parent.parent
DATA_DIR = _ROOT / "data"
EPISODES_DIR = DATA_DIR / "episodes"
CHARACTER_DIR = _ROOT / "character"

USER_MD = DATA_DIR / "USER.md"
MEMORY_MD = DATA_DIR / "MEMORY.md"
THOUGHTS_MD = DATA_DIR / "THOUGHTS.md"
HEARTBEAT_MD = DATA_DIR / "HEARTBEAT.md"
SELF_MD = DATA_DIR / "SELF.md"
MOOD_MD = DATA_DIR / "MOOD.md"

IDENTITY_MD = CHARACTER_DIR / "IDENTITY.md"
SOUL_MD = CHARACTER_DIR / "SOUL.md"
HEARTBEAT_TEMPLATE_MD = CHARACTER_DIR / "HEARTBEAT_TEMPLATE.md"
LORE_MD = CHARACTER_DIR / "LORE.md"


# ---------------------------------------------------------------------------
# Simple file readers
# ---------------------------------------------------------------------------


def read_file(path: Path) -> str:
    """Read a file and return its contents, or empty string if not found."""
    try:
        return path.read_text(encoding="utf-8").strip()
    except FileNotFoundError:
        return ""


def read_identity() -> str:
    return read_file(IDENTITY_MD)


def read_soul() -> str:
    return read_file(SOUL_MD)


def read_memory() -> str:
    return read_file(MEMORY_MD)


def read_heartbeat_templates() -> str:
    return read_file(HEARTBEAT_TEMPLATE_MD)


def read_lore(n: int = 3) -> str:
    """Return up to n randomly selected lore items from LORE.md for system prompt injection."""
    import random

    content = read_file(LORE_MD)
    if not content:
        return ""
    # Extract individual bullet items (lines starting with "- ")
    items = [
        ln.strip()[2:].strip()
        for ln in content.splitlines()
        if ln.strip().startswith("- ")
    ]
    if not items:
        return ""
    sample = random.sample(items, min(n, len(items)))
    return "\n".join(f"- {item}" for item in sample)


# ---------------------------------------------------------------------------
# USER.md — structured state
# ---------------------------------------------------------------------------


def _parse_user_md() -> dict[str, Any]:
    """Parse USER.md into a dict. Handles missing file gracefully."""
    content = read_file(USER_MD)
    if not content:
        return {
            "name": "unknown",
            "relationship_stage": 0,
            "meaningful_exchanges": 0,
            "open_loops": [],
            "known_facts": [],
        }

    state: dict[str, Any] = {
        "name": "unknown",
        "relationship_stage": 0,
        "meaningful_exchanges": 0,
        "open_loops": [],
        "known_facts": [],
        "raw": content,
    }

    # Extract relationship_stage
    m = re.search(r"relationship_stage:\s*(\d+)", content)
    if m:
        state["relationship_stage"] = int(m.group(1))

    # Extract meaningful_exchanges
    m = re.search(r"meaningful_exchanges:\s*(\d+)", content)
    if m:
        state["meaningful_exchanges"] = int(m.group(1))

    # Extract name
    m = re.search(r"- name:\s*(.+)", content)
    if m:
        state["name"] = m.group(1).strip()

    # Extract open_loops section
    loops_match = re.search(r"## open_loops\n(.*?)(?=\n##|\Z)", content, re.DOTALL)
    if loops_match:
        loops_text = loops_match.group(1).strip()
        if loops_text and loops_text.lower() != "none":
            state["open_loops"] = [
                line.lstrip("- ").strip()
                for line in loops_text.splitlines()
                if line.strip() and not line.strip().startswith("#")
            ]

    # Extract known_facts section
    facts_match = re.search(r"## known_facts\n(.*?)(?=\n##|\Z)", content, re.DOTALL)
    if facts_match:
        facts_text = facts_match.group(1).strip()
        if facts_text and facts_text.lower() != "none yet":
            state["known_facts"] = [
                line.lstrip("- ").strip()
                for line in facts_text.splitlines()
                if line.strip() and not line.strip().startswith("#")
            ]

    return state


def get_user_state() -> dict[str, Any]:
    return _parse_user_md()


def get_trust_stage() -> int:
    return _parse_user_md()["relationship_stage"]


def get_meaningful_exchanges() -> int:
    return _parse_user_md()["meaningful_exchanges"]


def get_open_loops() -> list[str]:
    return _parse_user_md()["open_loops"]


def update_user_field(key: str, value: Any) -> None:
    """Update a single key: value line in the ## basics section of USER.md."""
    content = read_file(USER_MD)
    if not content:
        return

    pattern = rf"(- {re.escape(key)}:\s*)(.+)"
    replacement = rf"\g<1>{value}"
    new_content = re.sub(pattern, replacement, content)
    USER_MD.write_text(new_content, encoding="utf-8")


def increment_meaningful_exchanges() -> int:
    """Increment meaningful_exchanges counter and return new value."""
    state = _parse_user_md()
    new_count = state["meaningful_exchanges"] + 1
    update_user_field("meaningful_exchanges", new_count)
    return new_count


def set_trust_stage(stage: int) -> None:
    update_user_field("relationship_stage", stage)


def add_open_loop(loop: str) -> None:
    """Append an open loop to USER.md."""
    content = read_file(USER_MD)
    if not content:
        return

    loops_match = re.search(r"(## open_loops\n)(.*?)(?=\n##|\Z)", content, re.DOTALL)
    if not loops_match:
        return

    existing = loops_match.group(2).strip()
    if existing.lower() == "none":
        new_loops = f"- {loop}"
    else:
        new_loops = existing + f"\n- {loop}"

    new_content = content[: loops_match.start(2)] + new_loops + content[loops_match.end(2) :]
    USER_MD.write_text(new_content, encoding="utf-8")


def clear_open_loops() -> None:
    """Clear all open loops in USER.md."""
    content = read_file(USER_MD)
    if not content:
        return
    new_content = re.sub(
        r"(## open_loops\n)(.*?)(?=\n##|\Z)",
        r"\1none\n",
        content,
        flags=re.DOTALL,
    )
    USER_MD.write_text(new_content, encoding="utf-8")


def add_known_fact(fact: str) -> None:
    """Append a known fact to USER.md, prefixed with today's date for age tracking."""
    content = read_file(USER_MD)
    if not content:
        return

    facts_match = re.search(r"(## known_facts\n)(.*?)(?=\n##|\Z)", content, re.DOTALL)
    if not facts_match:
        return

    dated_fact = f"[{date.today().isoformat()}] {fact}"
    existing = facts_match.group(2).strip()
    if existing.lower() in ("none yet", "none"):
        new_facts = f"- {dated_fact}"
    else:
        new_facts = existing + f"\n- {dated_fact}"

    new_content = (
        content[: facts_match.start(2)] + new_facts + content[facts_match.end(2) :]
    )
    USER_MD.write_text(new_content, encoding="utf-8")


def get_facts_with_age() -> list[dict[str, Any]]:
    """Return known facts with age metadata for imperfect recall injection.

    Returns list of dicts: {text, age_days, confidence}
    confidence: "high" (<7d), "medium" (7-30d), "low" (30+d or undated)
    Backward-compatible: undated facts are treated as low confidence.
    """
    raw_facts = get_user_state().get("known_facts", [])
    today = date.today()
    result = []

    date_pattern = re.compile(r"^\[(\d{4}-\d{2}-\d{2})\]\s+(.*)")

    for fact in raw_facts:
        m = date_pattern.match(fact)
        if m:
            try:
                fact_date = date.fromisoformat(m.group(1))
                age_days = (today - fact_date).days
                text = m.group(2).strip()
            except ValueError:
                age_days = 999
                text = fact
        else:
            age_days = 999  # undated = treat as old
            text = fact

        if age_days < 7:
            confidence = "high"
        elif age_days < 30:
            confidence = "medium"
        else:
            confidence = "low"

        result.append({"text": text, "age_days": age_days, "confidence": confidence})

    return result


def forget_topic(topic: str) -> None:
    """Remove lines containing topic from known_facts and open_loops in USER.md."""
    content = read_file(USER_MD)
    if not content:
        return

    lines = content.splitlines()
    filtered = [
        line
        for line in lines
        if topic.lower() not in line.lower()
        or not line.strip().startswith("- ")
    ]
    USER_MD.write_text("\n".join(filtered), encoding="utf-8")

    # Also clean MEMORY.md
    mem_content = read_file(MEMORY_MD)
    if mem_content:
        mem_lines = mem_content.splitlines()
        filtered_mem = [
            line
            for line in mem_lines
            if topic.lower() not in line.lower() or not line.strip().startswith("- ")
        ]
        MEMORY_MD.write_text("\n".join(filtered_mem), encoding="utf-8")


def update_last_updated() -> None:
    update_user_field("last_updated", datetime.now(UTC).strftime("%Y-%m-%d %H:%M UTC"))


# ---------------------------------------------------------------------------
# HEARTBEAT.md — runtime state as YAML front-matter
# ---------------------------------------------------------------------------


def _read_heartbeat_yaml() -> dict[str, Any]:
    content = read_file(HEARTBEAT_MD)
    if not content:
        return {}
    try:
        # Parse the YAML lines at the top (non-comment, non-section-header lines)
        lines = []
        for line in content.splitlines():
            stripped = line.strip()
            if stripped.startswith("#") or not stripped:
                continue
            lines.append(line)
        return yaml.safe_load("\n".join(lines)) or {}
    except yaml.YAMLError:
        return {}


def _write_heartbeat_yaml(state: dict[str, Any]) -> None:
    """Rewrite HEARTBEAT.md preserving comments, updating YAML fields."""
    content = read_file(HEARTBEAT_MD)
    if not content:
        content = ""

    # Rebuild: comments first, then YAML fields, then any section below
    header_lines = []
    section_lines = []
    in_section = False
    for line in content.splitlines():
        stripped = line.strip()
        if stripped.startswith("# Last 5") or stripped.startswith("# Total") or in_section:
            in_section = True
            section_lines.append(line)
        elif stripped.startswith("#") or not stripped:
            header_lines.append(line)

    yaml_block = yaml.dump(state, default_flow_style=False, allow_unicode=True, sort_keys=False)
    parts = ["\n".join(header_lines), yaml_block.rstrip()]
    if section_lines:
        parts.append("\n".join(section_lines))
    HEARTBEAT_MD.write_text("\n".join(parts) + "\n", encoding="utf-8")


def get_heartbeat_state() -> dict[str, Any]:
    state = _read_heartbeat_yaml()
    return {
        "silence_until": state.get("silence_until"),
        "last_proactive_sent": state.get("last_proactive_sent"),
        "last_user_message": state.get("last_user_message"),
        "used_excuses": state.get("used_excuses", []),
        "proactive_count": state.get("proactive_count", 0),
        # Re-engagement fields
        "bot_had_last_word": bool(state.get("bot_had_last_word", False)),
        "last_session_ended_at": state.get("last_session_ended_at"),
        "reengagement_sent_at": state.get("reengagement_sent_at"),
        # Escalation floor modifier (-1, 0, +1, +2)
        "warmth_floor_modifier": int(state.get("warmth_floor_modifier", 0)),
        # Photo daily counter
        "photos_sent_today": int(state.get("photos_sent_today", 0)),
        "photos_sent_date": state.get("photos_sent_date"),
    }


def update_heartbeat_state(**kwargs: Any) -> None:
    state = _read_heartbeat_yaml()
    state.update(kwargs)
    _write_heartbeat_yaml(state)


def set_silence(until: datetime | None) -> None:
    update_heartbeat_state(silence_until=until.isoformat() if until else None)


def record_user_message_time() -> None:
    update_heartbeat_state(last_user_message=datetime.now(UTC).isoformat())


def set_session_ended(bot_had_last_word: bool) -> None:
    """Record that a session just ended and whether bot's message was last."""
    update_heartbeat_state(
        bot_had_last_word=bot_had_last_word,
        last_session_ended_at=datetime.now(UTC).isoformat(),
        reengagement_sent_at=None,  # reset for this new session gap
    )


def set_reengagement_sent() -> None:
    """Mark that a re-engagement nudge was sent for the current dead session."""
    update_heartbeat_state(reengagement_sent_at=datetime.now(UTC).isoformat())


def record_proactive_sent(excuse_index: int) -> None:
    state = get_heartbeat_state()
    used = state["used_excuses"]
    used.append(excuse_index)
    used = used[-5:]  # keep last 5 only
    update_heartbeat_state(
        last_proactive_sent=datetime.now(UTC).isoformat(),
        used_excuses=used,
        proactive_count=state["proactive_count"] + 1,
    )


# ---------------------------------------------------------------------------
# Episodes
# ---------------------------------------------------------------------------


def today_episode_path() -> Path:
    return EPISODES_DIR / f"{date.today().isoformat()}.md"


def read_today_episode() -> str:
    return read_file(today_episode_path())


def write_episode(content: str, episode_date: date | None = None) -> Path:
    target_date = episode_date or date.today()
    path = EPISODES_DIR / f"{target_date.isoformat()}.md"
    EPISODES_DIR.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
    return path


def list_recent_episodes(n: int = 3) -> list[Path]:
    """Return up to n most recent episode files, newest first."""
    episodes = sorted(EPISODES_DIR.glob("????-??-??.md"), reverse=True)
    return episodes[:n]


def read_recent_episodes(n: int = 3) -> str:
    """Return concatenated content of n most recent episodes."""
    parts = []
    for path in list_recent_episodes(n):
        content = read_file(path)
        if content:
            parts.append(content)
    return "\n\n---\n\n".join(parts)


def read_last_episode_carry_over() -> str:
    """Return the carry_over line from the most recent episode file, or empty string."""
    episodes = sorted(EPISODES_DIR.glob("????-??-??.md"), reverse=True)
    for path in episodes:
        content = read_file(path)
        m = re.search(r"## carry_over\n(.+?)(?:\n##|\Z)", content, re.DOTALL)
        if m:
            return m.group(1).strip()
    return ""


def prune_old_episodes(retention_days: int) -> int:
    """Delete episode files older than retention_days. Returns count deleted."""
    cutoff = date.today().toordinal() - retention_days
    deleted = 0
    for path in EPISODES_DIR.glob("????-??-??.md"):
        try:
            episode_date = date.fromisoformat(path.stem)
            if episode_date.toordinal() < cutoff:
                path.unlink()
                deleted += 1
        except ValueError:
            pass
    return deleted


# ---------------------------------------------------------------------------
# MEMORY.md
# ---------------------------------------------------------------------------


def append_to_memory(section: str, fact: str) -> None:
    """Add a fact under a section in MEMORY.md."""
    content = read_file(MEMORY_MD)
    if not content:
        content = "# Long-Term Memory\n\n"

    section_pattern = rf"(## {re.escape(section)}\n)(.*?)(?=\n##|\Z)"
    m = re.search(section_pattern, content, re.DOTALL)
    if m:
        existing = m.group(2).strip()
        if existing.lower() in ("none yet", "none"):
            new_body = f"- {fact}\n"
        else:
            new_body = existing + f"\n- {fact}\n"
        content = content[: m.start(2)] + new_body + content[m.end(2) :]
    else:
        content += f"\n## {section}\n- {fact}\n"

    MEMORY_MD.write_text(content, encoding="utf-8")


# ---------------------------------------------------------------------------
# THOUGHTS.md
# ---------------------------------------------------------------------------


def append_thought(thought: str) -> None:
    """Append a dated thought entry to THOUGHTS.md."""
    content = read_file(THOUGHTS_MD)
    today = date.today().isoformat()
    entry = f"\n## {today}\n{thought}\n"
    THOUGHTS_MD.write_text((content or "") + entry, encoding="utf-8")


# ---------------------------------------------------------------------------
# SELF.md — Hikari's inner life (preoccupation, staged disclosures, competitive memory)
# ---------------------------------------------------------------------------


def read_self_md() -> str:
    """Return the full content of SELF.md, or empty string if not found."""
    return read_file(SELF_MD)


def write_self_preoccupation(thought: str) -> None:
    """Update the ## preoccupation section in SELF.md."""
    content = read_file(SELF_MD)
    if not content:
        SELF_MD.write_text(
            f"# Hikari's Self-Model\n\n## preoccupation\n{thought}\n\n"
            "## staged disclosures\nnone yet.\n\n"
            "## things she told the user\nnone yet.\n\n"
            "## established joke\nnone yet.\n",
            encoding="utf-8",
        )
        return

    new_content = re.sub(
        r"(## preoccupation\n)(.*?)(?=\n##|\Z)",
        rf"\g<1>{thought}\n",
        content,
        flags=re.DOTALL,
    )
    SELF_MD.write_text(new_content, encoding="utf-8")


def get_self_preoccupation() -> str:
    """Return current preoccupation line, or empty string."""
    content = read_file(SELF_MD)
    if not content:
        return ""
    m = re.search(r"## preoccupation\n(.+?)(?=\n##|\Z)", content, re.DOTALL)
    if m:
        text = m.group(1).strip()
        return "" if text.lower() in ("none yet.", "none yet", "none") else text
    return ""


def get_staged_disclosure(stage: int) -> str | None:
    """Return first unused staged disclosure at or below current trust stage, or None."""
    content = read_file(SELF_MD)
    if not content:
        return None
    m = re.search(r"## staged disclosures\n(.*?)(?=\n##|\Z)", content, re.DOTALL)
    if not m:
        return None
    for line in m.group(1).splitlines():
        line = line.strip().lstrip("- ")
        # Format: [stage N] used: false | disclosure text
        dm = re.match(r"\[stage (\d+)\] used: (true|false) \| (.+)", line, re.IGNORECASE)
        if dm and int(dm.group(1)) <= stage and dm.group(2).lower() == "false":
            return dm.group(3).strip()
    return None


def mark_disclosure_used(disclosure_text: str) -> None:
    """Mark a staged disclosure as used by text match."""
    content = read_file(SELF_MD)
    if not content:
        return
    new_content = re.sub(
        rf"(\[stage \d+\] used: )false( \| {re.escape(disclosure_text)})",
        r"\1true\2",
        content,
        flags=re.IGNORECASE,
    )
    SELF_MD.write_text(new_content, encoding="utf-8")


def add_self_disclosure(text: str) -> None:
    """Add something Hikari told the user to the competitive memory list."""
    content = read_file(SELF_MD)
    if not content:
        return
    dated_entry = f"[{date.today().isoformat()}] {text}"
    m = re.search(r"(## things she told the user\n)(.*?)(?=\n##|\Z)", content, re.DOTALL)
    if not m:
        return
    existing = m.group(2).strip()
    if existing.lower() in ("none yet.", "none yet", "none"):
        new_body = f"- {dated_entry}\n"
    else:
        new_body = existing + f"\n- {dated_entry}\n"
    new_content = content[: m.start(2)] + new_body + content[m.end(2) :]
    SELF_MD.write_text(new_content, encoding="utf-8")


def get_self_disclosures() -> list[dict[str, str]]:
    """Return list of things Hikari told the user: [{date, text}]."""
    content = read_file(SELF_MD)
    if not content:
        return []
    m = re.search(r"## things she told the user\n(.*?)(?=\n##|\Z)", content, re.DOTALL)
    if not m:
        return []
    results = []
    for line in m.group(1).splitlines():
        line = line.strip().lstrip("- ")
        dm = re.match(r"\[(\d{4}-\d{2}-\d{2})\] (.+)", line)
        if dm:
            results.append({"date": dm.group(1), "text": dm.group(2).strip()})
    return results


# ---------------------------------------------------------------------------
# MOOD.md — emotional arc tracking
# ---------------------------------------------------------------------------

_MOOD_MD_TEMPLATE = """\
# Hikari's Emotional Arc
# Written by consolidate.py + reflect.py. Read by chat.py.

current_arc: stable
arc_detected_at: {today}
arc_note: |
  not enough sessions to detect a trend yet.
recent_session_temperatures: []
"""


def _ensure_mood_md() -> None:
    if not MOOD_MD.exists():
        MOOD_MD.write_text(
            _MOOD_MD_TEMPLATE.format(today=date.today().isoformat()), encoding="utf-8"
        )


def read_mood_arc() -> dict[str, Any]:
    """Return parsed MOOD.md state."""
    _ensure_mood_md()
    content = read_file(MOOD_MD)
    try:
        # Strip comment lines then parse YAML
        lines = [ln for ln in content.splitlines() if not ln.strip().startswith("#")]
        data = yaml.safe_load("\n".join(lines)) or {}
    except yaml.YAMLError:
        data = {}
    return {
        "current_arc": data.get("current_arc", "stable"),
        "arc_note": str(data.get("arc_note", "")).strip(),
        "recent_session_temperatures": data.get("recent_session_temperatures", []),
    }


def append_session_temperature(session_date: date, temperature: str) -> None:
    """Append a session temperature to MOOD.md, keeping last 5."""
    _ensure_mood_md()
    arc_data = read_mood_arc()
    temps: list[str] = list(arc_data["recent_session_temperatures"])
    temps.append(f"[{session_date.isoformat()}] {temperature}")
    temps = temps[-5:]  # keep last 5

    content = read_file(MOOD_MD)
    # Rebuild the file with updated temperatures
    comment_lines = [ln for ln in content.splitlines() if ln.strip().startswith("#")]
    data_lines = [ln for ln in content.splitlines() if not ln.strip().startswith("#")]
    try:
        data = yaml.safe_load("\n".join(data_lines)) or {}
    except yaml.YAMLError:
        data = {}
    data["recent_session_temperatures"] = temps
    yaml_block = yaml.dump(data, default_flow_style=False, allow_unicode=True, sort_keys=False)
    MOOD_MD.write_text(
        "\n".join(comment_lines) + "\n" + yaml_block, encoding="utf-8"
    )


def write_mood_arc(arc: str, arc_note: str) -> None:
    """Update current_arc and arc_note in MOOD.md."""
    _ensure_mood_md()
    content = read_file(MOOD_MD)
    comment_lines = [ln for ln in content.splitlines() if ln.strip().startswith("#")]
    data_lines = [ln for ln in content.splitlines() if not ln.strip().startswith("#")]
    try:
        data = yaml.safe_load("\n".join(data_lines)) or {}
    except yaml.YAMLError:
        data = {}
    data["current_arc"] = arc
    data["arc_detected_at"] = date.today().isoformat()
    data["arc_note"] = arc_note
    yaml_block = yaml.dump(data, default_flow_style=False, allow_unicode=True, sort_keys=False)
    MOOD_MD.write_text(
        "\n".join(comment_lines) + "\n" + yaml_block, encoding="utf-8"
    )


# ---------------------------------------------------------------------------
# Photo daily counter
# ---------------------------------------------------------------------------


def record_photo_sent() -> None:
    """Increment the daily photo counter in HEARTBEAT.md."""
    state = _read_heartbeat_yaml()
    today_str = date.today().isoformat()
    # Reset if it's a new day
    if state.get("photos_sent_date") != today_str:
        state["photos_sent_today"] = 0
        state["photos_sent_date"] = today_str
    state["photos_sent_today"] = int(state.get("photos_sent_today", 0)) + 1
    _write_heartbeat_yaml(state)


def get_photos_sent_today() -> int:
    """Return number of photos sent today."""
    state = _read_heartbeat_yaml()
    today_str = date.today().isoformat()
    if state.get("photos_sent_date") != today_str:
        return 0
    return int(state.get("photos_sent_today", 0))
