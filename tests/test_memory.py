"""Memory read/write tests."""

from __future__ import annotations

from datetime import UTC, date
from pathlib import Path

import pytest

# Patch DATA_DIR to a temp dir for all tests in this module
_TEMP_DIR: Path | None = None
_ORIG_DATA_DIR: Path | None = None


@pytest.fixture(autouse=True)
def isolated_data_dir(monkeypatch, tmp_path):
    """Redirect all data file paths to a temp directory."""
    import bot.memory as mem

    (tmp_path / "episodes").mkdir()
    (tmp_path / "USER.md").write_text(
        "# User Profile\n\n"
        "## basics\n"
        "- name: unknown\n"
        "- relationship_stage: 0\n"
        "- meaningful_exchanges: 0\n\n"
        "## open_loops\nnone\n\n"
        "## known_facts\nnone yet\n\n"
        "## last_updated: never\n",
        encoding="utf-8",
    )
    (tmp_path / "MEMORY.md").write_text(
        "# Long-Term Memory\n\n## about the user\nnone yet\n\n## shared canon\nnone yet\n",
        encoding="utf-8",
    )
    (tmp_path / "THOUGHTS.md").write_text("# Hikari's Thoughts\nnone yet\n", encoding="utf-8")
    hb_content = (
        "# Heartbeat State\n\n"
        "silence_until: null\nlast_proactive_sent: null\n"
        "last_user_message: null\nused_excuses: []\nproactive_count: 0\n"
    )
    (tmp_path / "HEARTBEAT.md").write_text(hb_content, encoding="utf-8")

    monkeypatch.setattr(mem, "DATA_DIR", tmp_path)
    monkeypatch.setattr(mem, "EPISODES_DIR", tmp_path / "episodes")
    monkeypatch.setattr(mem, "USER_MD", tmp_path / "USER.md")
    monkeypatch.setattr(mem, "MEMORY_MD", tmp_path / "MEMORY.md")
    monkeypatch.setattr(mem, "THOUGHTS_MD", tmp_path / "THOUGHTS.md")
    monkeypatch.setattr(mem, "HEARTBEAT_MD", tmp_path / "HEARTBEAT.md")

    yield tmp_path


# ---------------------------------------------------------------------------
# USER.md tests
# ---------------------------------------------------------------------------


def test_get_trust_stage_default():
    from bot.memory import get_trust_stage
    assert get_trust_stage() == 0


def test_set_trust_stage():
    from bot.memory import get_trust_stage, set_trust_stage
    set_trust_stage(2)
    assert get_trust_stage() == 2


def test_increment_meaningful_exchanges():
    from bot.memory import get_meaningful_exchanges, increment_meaningful_exchanges
    assert get_meaningful_exchanges() == 0
    count = increment_meaningful_exchanges()
    assert count == 1
    assert get_meaningful_exchanges() == 1


def test_add_known_fact():
    from bot.memory import add_known_fact, get_user_state
    add_known_fact("likes coffee")
    state = get_user_state()
    # Facts are now stored with a date prefix: "[YYYY-MM-DD] likes coffee"
    assert any("likes coffee" in f for f in state["known_facts"])


def test_add_multiple_facts():
    from bot.memory import add_known_fact, get_user_state
    add_known_fact("works in tech")
    add_known_fact("has a cat")
    state = get_user_state()
    assert any("works in tech" in f for f in state["known_facts"])
    assert any("has a cat" in f for f in state["known_facts"])


def test_add_open_loop():
    from bot.memory import add_open_loop, get_open_loops
    add_open_loop("interview on Friday")
    loops = get_open_loops()
    assert "interview on Friday" in loops


def test_clear_open_loops():
    from bot.memory import add_open_loop, clear_open_loops, get_open_loops
    add_open_loop("thing 1")
    add_open_loop("thing 2")
    clear_open_loops()
    assert get_open_loops() == []


def test_forget_topic_removes_from_facts(isolated_data_dir):
    from bot.memory import add_known_fact, forget_topic, get_user_state
    add_known_fact("loves sushi")
    add_known_fact("works at a startup")
    forget_topic("sushi")
    state = get_user_state()
    facts = state["known_facts"]
    assert not any("sushi" in f.lower() for f in facts)
    assert any("startup" in f.lower() for f in facts)


# ---------------------------------------------------------------------------
# Episode tests
# ---------------------------------------------------------------------------


def test_write_and_read_episode():
    from bot.memory import read_today_episode, write_episode
    content = "# Session 2026-02-23\n\n## summary\nWe talked about data science.\n"
    write_episode(content)
    read_back = read_today_episode()
    assert "data science" in read_back


def test_list_recent_episodes():
    from bot.memory import list_recent_episodes, write_episode
    write_episode("ep1", episode_date=date(2026, 2, 21))
    write_episode("ep2", episode_date=date(2026, 2, 22))
    write_episode("ep3", episode_date=date(2026, 2, 23))
    episodes = list_recent_episodes(n=3)
    assert len(episodes) == 3


def test_prune_old_episodes():
    from bot.memory import list_recent_episodes, prune_old_episodes, write_episode
    write_episode("old ep", episode_date=date(2025, 1, 1))
    write_episode("recent ep", episode_date=date(2026, 2, 23))
    deleted = prune_old_episodes(retention_days=30)
    assert deleted >= 1
    remaining = list_recent_episodes(n=10)
    assert all("2025-01-01" not in str(p) for p in remaining)


# ---------------------------------------------------------------------------
# MEMORY.md tests
# ---------------------------------------------------------------------------


def test_append_to_memory():
    from bot.memory import append_to_memory, read_memory
    append_to_memory("about the user", "enjoys hiking")
    memory = read_memory()
    assert "enjoys hiking" in memory


# ---------------------------------------------------------------------------
# HEARTBEAT.md tests
# ---------------------------------------------------------------------------


def test_heartbeat_state_defaults():
    from bot.memory import get_heartbeat_state
    state = get_heartbeat_state()
    assert state["proactive_count"] == 0
    assert state["used_excuses"] == []
    assert state["silence_until"] is None


def test_set_silence():
    from datetime import datetime, timedelta

    from bot.memory import get_heartbeat_state, set_silence
    future = datetime.now(UTC) + timedelta(hours=2)
    set_silence(future)
    state = get_heartbeat_state()
    assert state["silence_until"] is not None


def test_record_proactive_sent():
    from bot.memory import get_heartbeat_state, record_proactive_sent
    record_proactive_sent(3)
    record_proactive_sent(7)
    state = get_heartbeat_state()
    assert state["proactive_count"] == 2
    assert 3 in state["used_excuses"]
    assert 7 in state["used_excuses"]


def test_used_excuses_capped_at_5():
    from bot.memory import get_heartbeat_state, record_proactive_sent
    for i in range(7):
        record_proactive_sent(i)
    state = get_heartbeat_state()
    assert len(state["used_excuses"]) <= 5


# ---------------------------------------------------------------------------
# THOUGHTS.md tests
# ---------------------------------------------------------------------------


def test_append_thought():
    from bot.memory import THOUGHTS_MD, append_thought, read_file
    append_thought("i keep thinking about what they said about that dataset.")
    content = read_file(THOUGHTS_MD)
    assert "dataset" in content
