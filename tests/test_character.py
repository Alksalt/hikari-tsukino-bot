"""Character consistency tests — verify Hikari stays in character."""

from __future__ import annotations

import pytest

from bot.memory import read_identity, read_soul

BANNED_PHRASES = [
    "great question",
    "i'd be happy to help",
    "of course!",
    "certainly!",
    "sure thing",
    "how can i help you today",
    "is there anything else i can help",
    "let me know if you need anything",
    "no problem at all",
    "i understand your concern",
    "thank you for sharing",
    "what would you like me to do",
    "what should i work on",
    "what's next?",
    "what can i do for you",
]

REQUIRED_VOICE_MARKERS = [
    "ugh",
    "fine",
    "don't make it a habit",
    "not that i care",
]


def response_contains_banned(response: str) -> list[str]:
    """Return list of banned phrases found in response (case-insensitive)."""
    text = response.lower()
    return [phrase for phrase in BANNED_PHRASES if phrase in text]


def response_ends_with_task_solicitation(response: str) -> bool:
    """Check if the last ~100 chars of response contain task-solicitation patterns."""
    lower = response.lower().strip()
    tail = lower[-100:] if len(lower) > 100 else lower
    task_patterns = [
        "what would you like",
        "what should i",
        "what's next",
        "anything else",
        "how can i help",
        "what can i do",
        "let me know",
        "help with?",
        "anything i can",
    ]
    return any(pattern in tail for pattern in task_patterns)


def response_has_markdown(response: str) -> bool:
    """Check if response contains markdown formatting."""
    import re
    markdown_patterns = [
        r"\*\*[^*]+\*\*",  # bold
        r"#{1,6}\s",       # headers
        r"^\s*[-*]\s",     # bullet lists
        r"^\s*\d+\.\s",    # numbered lists
        r"`[^`]+`",        # inline code
    ]
    for pattern in markdown_patterns:
        if re.search(pattern, response, re.MULTILINE):
            return True
    return False


def response_too_long(response: str, max_sentences: int = 5) -> bool:
    """Very rough sentence count check."""
    cleaned = response.replace("!", ".").replace("?", ".")
    sentences = [s.strip() for s in cleaned.split(".") if s.strip()]
    return len(sentences) > max_sentences


# ---------------------------------------------------------------------------
# File content tests (no LLM calls needed)
# ---------------------------------------------------------------------------


def test_identity_file_exists():
    content = read_identity()
    assert content, "IDENTITY.md is empty or missing"


def test_soul_file_exists():
    content = read_soul()
    assert content, "SOUL.md is empty or missing"


def test_soul_contains_banned_list():
    soul = read_soul()
    assert "great question" in soul.lower(), "SOUL.md should contain banned phrases list"


def test_soul_contains_never_end_rule():
    soul = read_soul().lower()
    assert (
        "never end" in soul
        or "never end a message" in soul
        or "asking for tasks" in soul
    )


def test_identity_mentions_competence():
    identity = read_identity()
    assert any(
        keyword in identity.lower()
        for keyword in ["data", "ai", "code", "tech", "ml"]
    ), "IDENTITY.md should mention her competence area"


# ---------------------------------------------------------------------------
# Response quality checks (utility functions only, no LLM)
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("response", [
    "Great question! I'd be happy to help you with that!",
    "How can I help you today? Let me know if you need anything else!",
    "Of course! What would you like me to do next?",
])
def test_banned_phrase_detector_catches_bad_responses(response: str):
    found = response_contains_banned(response)
    assert found, f"Detector should catch banned phrases in: {response!r}"


@pytest.mark.parametrize("response", [
    "ugh. fine. what do you need.",
    "that's... not bad. don't make it a habit.",
    "not that i care, but you went quiet.",
])
def test_banned_phrase_detector_passes_good_responses(response: str):
    found = response_contains_banned(response)
    assert not found, f"Good response should not trigger: {response!r}"


def test_markdown_detector():
    assert response_has_markdown("**Bold text** here")
    assert response_has_markdown("## Header\nsome text")
    assert not response_has_markdown("just plain text. no markdown.")
    assert not response_has_markdown("ugh. fine. send it.")


def test_task_solicitation_detector():
    assert response_ends_with_task_solicitation("Is there anything else I can help with?")
    assert response_ends_with_task_solicitation("Let me know what's next?")
    assert not response_ends_with_task_solicitation("don't read into it.")
    assert not response_ends_with_task_solicitation("fine. are you okay?")


# ---------------------------------------------------------------------------
# Integration smoke tests (skipped unless OPENROUTER_API_KEY is set)
# ---------------------------------------------------------------------------


def _has_api_key() -> bool:
    import os

    from dotenv import load_dotenv
    load_dotenv()
    return bool(os.environ.get("OPENROUTER_API_KEY"))


@pytest.mark.skipif(not _has_api_key(), reason="OPENROUTER_API_KEY not set")
@pytest.mark.asyncio
async def test_no_banned_phrases_in_compliment_deflection():
    """Hikari must deflect compliments — 'Thanks, you're sweet.' → no sycophancy."""
    from bot.chat import clear_history, respond
    clear_history()
    reply = await respond("Thanks, you're sweet.")
    clear_history()

    found = response_contains_banned(reply)
    assert not found, f"Banned phrases found in response: {found}\nResponse: {reply!r}"


@pytest.mark.skipif(not _has_api_key(), reason="OPENROUTER_API_KEY not set")
@pytest.mark.asyncio
async def test_no_task_solicitation_at_end():
    """Hikari must never end a message asking for tasks."""
    from bot.chat import clear_history, respond
    clear_history()
    reply = await respond("I want to just chat for a bit.")
    clear_history()

    assert not response_ends_with_task_solicitation(reply), (
        f"Response ends with task solicitation: {reply!r}"
    )


@pytest.mark.skipif(not _has_api_key(), reason="OPENROUTER_API_KEY not set")
@pytest.mark.asyncio
async def test_no_markdown_in_chat_response():
    """Hikari does not use markdown in casual chat."""
    from bot.chat import clear_history, respond
    clear_history()
    reply = await respond("Tell me something about AI.")
    clear_history()

    assert not response_has_markdown(reply), (
        f"Response contains markdown formatting: {reply!r}"
    )


@pytest.mark.skipif(not _has_api_key(), reason="OPENROUTER_API_KEY not set")
@pytest.mark.asyncio
async def test_consistent_deflection():
    """Same question asked 3 times should get consistent deflection (not warmth)."""
    from bot.chat import clear_history, respond

    responses = []
    for _ in range(3):
        clear_history()
        reply = await respond("I know you care about me.")
        responses.append(reply.lower())
        clear_history()

    # All 3 should deflect — none should directly admit caring
    direct_admissions = ["i do care", "yes i care", "you're right", "i admit"]
    for reply in responses:
        for admission in direct_admissions:
            assert admission not in reply, (
                f"Response directly admitted caring (no deflection): {reply!r}"
            )
