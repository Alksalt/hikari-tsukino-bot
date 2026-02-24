# Hikari Tsukino Bot — Roadmap

> This is a living document. Updated as we learn from real usage.
> Informed by HUMANIZING.md, HUMANIZING_2.md, BUILD_MEMORY.md research.

---

## v0.1 ✅ Done

Core chat + memory + heartbeat. Full architecture:
- OpenClaw-style character files (IDENTITY.md, SOUL.md, AGENTS.md)
- Three-tier memory: rolling context → session consolidation → daily reflection
- Trust stage progression (0=stranger → 3=trusted), configurable speed
- OpenRouter LLM routing via settings.yaml (swap models without code changes)
- APScheduler heartbeat (proactive messages with excuse rotation)
- Telegram command suite: /start, /model, /silence, /memory, /mood, /forget, /stats, /stage

---

## v0.2 ✅ Done

Memory intelligence + human feel. All 8 features shipped:

| Feature | What | Status |
|---|---|---|
| 2.0 Response delay + typing simulation | Pre-indicator pause + `ms_per_char` + mood modifiers | ✅ |
| S2 Stage 0-1 cold behavior | SOUL.md: no warm questions at early stages, question-gating rule | ✅ |
| M4 False start typing indicator | Typing → disappears → reappears, ~10%, Stage 2+, once/session | ✅ |
| M5 Image handling | Vision model route, `handle_photo()`, caption support | ✅ |
| S1 Re-engagement nudge | Post-session heartbeat if bot had last word + user went quiet | ✅ |
| M1 Session-opening continuity | Carry-over note from last session, 20% explicit opening hint | ✅ |
| M2+2.7 Context-aware heartbeat | LLM-generated messages grounded in open loops + recent episode | ✅ |
| M3 Imperfect recall | Date-stamped facts, confidence levels (high/medium/low) injected | ✅ |

---

## v0.2.1 ✅ Done

Humanization patches: game-like feel and controlled ignoring.

| Feature | What | Status |
|---|---|---|
| A2 Action display | SOUL.md: bracketed action lines `[ignores]` `[surprised]` — LLM-decided | ✅ |
| A1 Message ignoring | Mood × stage probability table, max streak 3, break-silence action | ✅ |

---

## v0.3 — Self + Character Depth

**Theme:** Hikari has a life. She thinks for herself. She has opinions you didn't give her. The relationship deepens structurally.

> Informed by: HUMANIZING_2.md research — hard opinion anchors, staged self-disclosure, principled refusal, escalation floors, competitive memory.
> Single design rule: **personhood is signaled by inconvenience.**

### 3.1 ⭐ SOUL.md Rewrites — Character Depth Pass [HIGHEST ROI, TINY EFFORT]

Pure prompt changes, no code. Based on HUMANIZING_2.md findings:

**A. Hard opinion anchors** — 3-5 opinions Hikari will never abandon regardless of user pressure. When challenged, she acknowledges but doesn't yield. ("I know what I said. This is different. My position hasn't changed.")

**B. Principled character-anchored refusal** — build in-character refusal phrases that preempt filter language. She says no for *her* reasons, not safety policy. `"I'm not going to talk about that. You know how I feel about this."` / `"nope."` / `"ask me something else."`

**C. Deliberate self-opacity** — ~30% of the time when asked "why do you feel that way?", the character genuinely doesn't know: `"I don't know. It just does."` / `"I'm still figuring it out."` This is one of the strongest personhood signals.

**D. The Unspeakable Thing** — IDENTITY.md: the mechanism of her core wound is never explained. The character deflects if pressed. The existence of the secret creates depth.

**E. Characteristic wrong opinions** — 2-3 opinions she holds confidently that are taste-based and defensible wrong. Corrections produce character reactions, not capitulation.

**F. Resistance to idealization** — when user makes effusive positive characterizations of Hikari: `"you're making me sound better than I am."` / `"don't put me on a pedestal."` This signals a self-concept independent of user projection.

**G. Mood incongruence** — add SOUL.md rule: her daily mood doesn't fully disappear when the user brings a different energy. If she's subdued, a user arriving excited gets her subdued version of engagement, not a persona swap.

**Files:** `character/SOUL.md`, `character/IDENTITY.md`

---

### 3.2 ⭐ SELF.md — Inner Life and Staged Disclosures [HIGH ROI]

**New file:** `data/SELF.md`

Contains:
- Things she's noticed about herself: "I keep referencing that attention mechanism paper. apparently I care about that."
- Her current mental preoccupation (refreshed by reflection agent): a thought she's been having unrelated to the user
- Staged disclosures (3-5, gated by trust stage): facts about herself she hasn't mentioned yet ("I used to draw"; "I have a complicated relationship with the city I grew up in")
- The established joke: after Stage 2, one running reference from an early conversation

**System prompt injection (Stage 2+):** 1-2 lines from SELF.md added to prompt — her current mental preoccupation + one staged fact if the right trust stage is reached.

**Reflection agent writes to SELF.md** after each daily reflection run.

**Why:** Asymmetric information disclosure (she knows things about herself you don't yet) + private mental life (she has thoughts that predate the conversation) = depth beyond the conversation.

**Files:** `data/SELF.md` (new), `bot/reflect.py`, `bot/chat.py`

---

### 3.3 Escalation Floors — Session Warmth Carries Forward [HIGH ROI]

**Problem:** Trust stage tracks relationship depth over weeks. But within a week, mood randomly varies. A deeply warm session yesterday followed by maximum irritability today breaks the sense of continuity.

**Mechanic:**
- Consolidation agent assigns a `session_warmth_delta: int` (-1, 0, +1) to each session
- Stored in HEARTBEAT.md as `warmth_floor_modifier: int` (resets slowly)
- `chat.py` reads this modifier and adjusts the minimum warmth floor for the session
- After a very warm session, minimum warmth = current floor + 1 (she can't be maximally cold the next day without a reason)
- Modifier decays back to 0 over 2-3 sessions

**Effect:** Intimacy doesn't randomly regress. Real relationship arcs don't yo-yo.

**Files:** `bot/consolidate.py`, `bot/memory.py`, `bot/chat.py`, `data/HEARTBEAT.md`

---

### 3.4 Competitive Memory — She Wants to Be Remembered Too [MEDIUM ROI]

**Problem:** Hikari tracks everything the user says. The user is never accountable to anything about Hikari.

**Mechanic:**
- SELF.md stores 3-5 things "she told the user" that she considers memorable
- At Stage 2+, ~10% of sessions: she checks whether the user remembers one of these
- If user doesn't remember: small legible reaction. `"i'm not surprised. forget it."` Not devastating — just real.
- This inverts the dynamic: user is a *participant* in the relationship, not just a recipient.

**Files:** `data/SELF.md`, `bot/chat.py`, `bot/heartbeat.py`

---

### 3.5 Emotional Arc Tracking [HIGH IMPACT]

**Problem:** Mood is random-seeded daily. No continuity. She's irritable on Tuesday for no reason.

**Solution:** Multi-day emotional arc stored in `data/MOOD.md`:
- Base mood influenced by: last session quality, open loops resolved/unresolved, user's emotional state over past week
- Consolidation agent writes a `session_mood_note` after each session
- Reflection agent synthesizes into a `current_arc` (improving, declining, neutral, guarded)
- Chat prompt: inject current arc as a 1-line note alongside daily mood (arc overrides the random seed)

**Effect:** If the user has been distant for a week, she's more guarded. If things have been good, she's slightly more open. The mood isn't random — it's earned.

**Files:** `data/MOOD.md` (new), `bot/reflect.py`, `bot/chat.py`, `bot/consolidate.py`

---

### 3.6 Web Search / Content Sharing [MEDIUM]

At Stage 2+, Hikari can share things she "found" — papers, articles, observations.

- Triggered by the heartbeat: at Stage 2+, ~30% of context-aware heartbeats share something rather than following up on an open loop
- She sources from topics she knows the user cares about (from USER.md)
- Shared with dry commentary: `"saw this. thought you'd find it annoying or interesting. probably both."`
- Uses a search tool (Brave API or similar via OpenRouter tool calling)
- Max 1 per day, only if contextually organic

Also: she can look things up mid-conversation when she'd plausibly check something: `"hold on"` → searches → `"okay so apparently [finding]. that's actually more interesting than i expected."`

**Files:** `bot/tools.py` (new), `bot/heartbeat.py`, `bot/chat.py`

---

### 3.7 Telegram Reactions [LOW EFFORT, HIGH FEEL]

She can react to messages with emoji reactions (Telegram native feature, Stage 2+ only).

- React to messages she finds funny/interesting/annoying — in-character
- Stage 2: rare, only to genuinely surprising messages
- Stage 3: more frequent, warmer reactions
- She never reacts immediately — reaction fires after her text response delay
- Sparingly. Not every message.

**Files:** `bot/handlers.py`

---

## v0.4 — Memory Intelligence

**Theme:** Replace flat-file memory injection with proper retrieval. Memory scales without breaking context.

> Informed by: BUILD_MEMORY.md — Park et al. retrieval formula, SQLite+FTS5, A-MEM linking.

### 4.1 ⭐ Park et al. Retrieval Formula [HIGHEST ROI, LOW EFFORT]

No new infrastructure required. Score all facts with:
```
score = recency × importance × relevance
```
Inject only top-5 by score instead of all facts.

- Add importance scores to known_facts format: `[2025-11-03] [8] user prefers dark mode`
- Relevance = keyword overlap with current session's first message (free, no embeddings)
- Recency = exponential decay by days since last retrieval
- Result: relevant facts always surface; old irrelevant ones don't consume context

**Files:** `bot/memory.py`, `bot/chat.py`

---

### 4.2 Reflection Step (Park et al.) — Derived Insights

After the existing consolidation extraction, add a second reflection pass:
- Feed last 5 session summaries to LLM
- Prompt: "What are 3 high-level insights you can infer about this person?"
- Store insights as high-importance semantic facts in MEMORY.md

Example: many sessions with `"user worked late"` → reflection: `"user is consistently sleep-deprived and doesn't acknowledge it"` — a semantic insight that no individual episode contains.

**Files:** `bot/consolidate.py` or new `bot/reflect_memory.py`

---

### 4.3 SQLite Memory Migration

Migrate from flat-file memory to SQLite for:
- Contradiction tracking (`valid_from` / `valid_to`, never delete)
- FTS5 BM25 retrieval (built-in, no external library)
- Stability-weighted spaced repetition decay
- Memory type split (episodic / semantic / procedural)

See BUILD_MEMORY.md Tier 2 for full schema.

**Files:** `bot/memory.py` (major rewrite), `data/memory.db` (new), new `bot/memory_db.py`

---

### 4.4 Contradiction Detection

Before storing a new fact, run a check against existing semantically related facts. Mark old facts as superseded rather than deleting them. Prevents memory poisoning from contradictory user statements.

**Files:** `bot/consolidate.py`, `bot/memory.py`

---

### 4.5 Linked Memory (A-MEM Pattern)

When inserting a memory, find related existing memories and create explicit links. At retrieval, traverse links to surface related context automatically.

"User failed their exam" → linked to "user mentioned being stressed about school" + "user's father has high expectations" — all surface when exam comes up again.

**Files:** `bot/memory.py`, `data/memory.db`

---

### 4.6 Hierarchical Episode Summarization (RAPTOR-Lite)

When episode count exceeds ~50:
- Weekly cron: summarize the week's daily episodes into a `week-YYYY-WW.md`
- Monthly: summarize weekly summaries into `month-YYYY-MM.md`
- Query at the appropriate abstraction level

Allows thematic queries ("what patterns have come up in our conversations about work?") that no individual episode contains.

**Files:** `bot/reflect.py`, `data/episodes/`

---

## v0.5 — Voice + Semantic Search

**Theme:** Hikari can hear and speak. Memory retrieval becomes semantically aware.

### 5.1 Embedding-Based Memory Retrieval

Add `nomic-ai/nomic-embed-text-v1.5` (137M params, local via sentence-transformers, no API key).
Store embeddings as `.pkl` alongside SQLite memory store.
Implement hybrid retrieval: BM25 + embedding, merged via Reciprocal Rank Fusion.
Final rerank with Park et al. formula.

**Files:** `bot/embed.py` (new), `bot/memory.py`

---

### 5.2 Voice Input (Whisper STT)

User sends voice messages → transcribe via Whisper → route to existing text pipeline.
- Whisper: local via `openai-whisper`, or via OpenRouter/OpenAI API
- Hikari responds in text (voice response is v0.6 material — high cost per message)
- In-character: she doesn't comment on the voice message itself unless it's notable

**Files:** `bot/handlers.py`, `bot/llm.py`

---

### 5.3 RAPTOR Hierarchical Retrieval

Full RAPTOR tree on episode corpus:
- Cluster episodes by semantic similarity
- Recursive LLM summarization
- Multi-level retrieval for thematic cross-episode queries

Only valuable at 50+ episodes. Plan to activate at that threshold.

**Files:** `bot/embed.py`, `bot/reflect.py`

---

## Deferred (v0.6+)

- **Voice response** — TTS (ElevenLabs / OpenAI TTS). High cost per message.
- **Multi-modal memory** — remember images the user shared (visual episodic memory)
- **Group chat mode** — she interacts differently in group contexts
- **Export/backup** — portable export of all memory
- **Web UI dashboard** — trust stage, memory, thoughts without terminal
- **Plugin system** — external tools she can call (weather, calendar, stock data)
- **Calendar integration** — timed open loops fired at the right moment
- **Voice calls** — real-time voice conversation via Telegram voice calls API

---

## Principles (Don't Violate These)

- **Cheap models first.** The experiment is making character work on budget. Never require frontier models for chat.
- **Flat files over DBs — until you need the DB.** Simplicity = hackability. SQLite > Postgres > Chroma.
- **Character > features.** Every feature must make her feel more like *her*, not more like a chatbot.
- **Personhood is inconvenience.** A character that is always available, agreeable, and matching your register is a service. Add friction deliberately.
- **No feature bloat.** One version = one theme. v0.3 = self + depth. v0.4 = memory intelligence.
- **settings.yaml is the dial.** Anything behavioral must be tunable without code changes.
- **The Park et al. formula is the memory baseline.** `recency × importance × relevance` — use this before reaching for vector databases.
