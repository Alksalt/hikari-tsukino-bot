# Hikari Tsukino Bot — Roadmap

> This is a living document. Updated as we learn from real usage.

---

## v0.1 ✅ Done

Core chat + memory + heartbeat. See README.

---

## v0.2 — Memory Intelligence + Human Feel

Goal: Make the memory system smarter and make Hikari feel more like she actually *exists* between conversations. No voice yet.

> Informed by HUMANIZING.md research. Priority order follows the impact/effort ranking from that doc.
> **Highest ROI items first:** response timing (#1), imperfect recall (#2), session continuity (#3).

### 2.0 ⭐ Response Delay + Typing Simulation [HIGHEST ROI]
**Research finding:** Typing indicators + realistic delays are the single most disproportionately impactful humanization technique relative to implementation cost. (HCI consensus)
**Problem:** v0.1 responds instantly. This is the biggest immersion-breaker.
**Solution:**
- Before sending: call `send_chat_action(TYPING)`, wait scaled delay, then send
- Delay model: base 1s + ~35ms per character of response, capped at 10s
- Mood modifier: irritable = -30%, tired = +30%
- `response_delay_enabled: true` in settings.yaml

**Files:** update `bot/handlers.py`, `settings.yaml`

### 2.1 Semantic Memory Search
**Problem:** v0.1 does keyword scan of MEMORY.md. If user says "that project" it won't find "the ML pipeline they mentioned."
**Solution:** Embed MEMORY.md + USER.md chunks. On each turn, retrieve semantically relevant facts.
- Use `sentence-transformers` (local, free) or OpenRouter embeddings
- Store embeddings as a sidecar `.jsonl` file next to MEMORY.md
- Rebuild on MEMORY.md write, query on each chat turn
- Inject top-3 relevant chunks into system prompt instead of full file

**Files:** `bot/embed.py` (new), update `bot/chat.py`

### 2.2 Contradiction Detection in Memory
**Problem:** Memory can accumulate contradictory facts ("user likes coffee" + "user hates coffee").
**Solution:** Consolidation agent checks new facts against existing before writing. Uses LLM to flag conflicts.

**Files:** update `bot/consolidate.py`

### 2.3 Smarter Heartbeat — Context-Aware Proactive Messages
**Problem:** v0.1 heartbeat uses rotating excuse templates. After a week it feels repetitive.
**Solution:**
- At Stage 2+, heartbeat generates fresh excuses grounded in open loops and recent memory
- "hey, you mentioned that interview — how'd it go?" is infinitely better than template #7
- Templates remain as fallback for Stage 0-1
- Anti-repetition tracks full message content hash, not just template index

**Files:** update `bot/heartbeat.py`

### 2.4 Response Delay Simulation
**Problem:** Instant responses feel robotic. Real people don't respond in 0ms.
**Goal:** Simulate realistic typing time.
- Calculate delay: base 1.5s + ~40ms per character of response, capped at 8s
- Show "typing..." indicator (Telegram's `send_chat_action`) during delay
- Mood modifier: irritable = faster, tired = slower, weirdly good = normal
- Configurable in settings.yaml: `response_delay_enabled: true`

**Files:** update `bot/handlers.py`, `settings.yaml`

### 2.5 ⭐ Imperfect Recall System [HIGH ROI]
**Research finding:** Human-shaped memory is the #1 intimacy driver in user studies. Perfect recall signals AI; strategic forgetting signals person. (Skjuve et al., Replika user research)
**Problem:** v0.1 injects facts from USER.md as clean, certain statements. Reads like a database.
**Solution:**
- Four confidence levels injected into prompt based on memory age/strength:
  - High: stated directly ("you mentioned your interview is Friday")
  - Medium: hedged ("i think you said something about this — was it...?")
  - Low: impression ("i remember you seemed conflicted about your family. was that this?")
  - Emotional only: ("i don't remember the details but i remember feeling worried about you when you talked about that")
- Facts older than 7 days are injected at Medium confidence; older than 30 days at Low
- Minor details mentioned once in passing → Strategic forget (excluded from recall)
- Configurable in settings.yaml: `imperfect_recall_rate: 0.15`

**Files:** update `bot/memory.py` (add fact age tracking), update `bot/chat.py`

### 2.6 Mid-Session Summarization
**Problem:** Very long sessions (50+ turns) lose early context even with rolling window.
**Solution:** When turn count exceeds threshold, run a quick background summarization of the first half of the session and inject as a compressed "earlier today" note.

**Files:** `bot/midpoint.py` (new), update `bot/chat.py`

### 2.7 Open Loop Follow-Up Intelligence
**Problem:** v0.1 stores open loops but only shows them in `/memory`. The heartbeat doesn't actively use them.
**Solution:**
- If a loop has been open for >X hours (configurable), heartbeat prioritizes following up on it
- She asks about it in-character: "chotto — that thing you mentioned. did it work out?"
- After user responds, loop is marked resolved in USER.md

**Files:** update `bot/heartbeat.py`, `bot/memory.py`

### 2.7b ⭐ Session-Opening Continuity Signal [HIGH ROI]
**Research finding:** "Emotional amnesia" (every session starting at neutral baseline) is the most cited immersion-breaker in AI companion user reports. Session-opening continuity is very high impact, very low effort. (Skjuve et al., r/replika)
**Problem:** v0.1 opens every session cold. No reference to how last session felt.
**Solution:**
- Consolidation agent writes a 1-line "carry-over" to the episode file:
  - "good session. she's slightly warmer at next open."
  - "user seemed distant. she's a bit more guarded."
- At session start (first turn), inject this carry-over as a 1-line system note
- Not every session — skip if no meaningful prior episode (prevents staleness)
- Occasionally she opens with it explicitly: "we left off in a weird place. you okay?"

**Files:** update `bot/consolidate.py`, `bot/chat.py`

### 2.7c "Noticing" Behavior (SOUL.md update)
**Research finding:** "Noticing" (observing and naming something the user didn't call out) scores highest in all user intimacy studies. Offered as observation, not diagnosis. (HUMANIZING.md section 5)
**Problem:** v0.1 SOUL.md doesn't specifically direct this behavior.
**Solution:**
- Add explicit "noticing" policy to SOUL.md:
  - "i noticed—" not "you are—"
  - Tier 1 (in-conversation): "you said that really quickly — you sure?"
  - Tier 2 (session): "you've mentioned being tired three times today"
  - Tier 3 (cross-session, Stage 2+ only): "you always go quiet around this time of year"
- Update CHARACTER.md with noticing examples

**Files:** update `character/SOUL.md`, update `CHARACTER.md`

### 2.8 Relationship Milestone Log
**Problem:** No record of significant relationship moments ("first time she admitted something", "first time user comforted her").
**Solution:** `data/MILESTONES.md` — append-only log of notable events.
- Written by consolidation agent when it detects a milestone (first direct honesty, first warmth, user shared something personal)
- Read by reflection agent to inform THOUGHTS.md
- Not exposed in chat

**Files:** `bot/memory.py`, update `bot/consolidate.py`, update `bot/reflect.py`

### 2.9 Image Handling
**Problem:** v0.1 ignores images sent in Telegram.
**Solution:** Pass image URL to a vision-capable model. Hikari reacts in-character.
- She has opinions. "that's... actually a good composition." or "why are you sending me this."
- Route to vision model in settings.yaml: `models.vision: "openai/gpt-4o-mini"`

**Files:** update `bot/handlers.py`, `bot/llm.py`, `settings.yaml`

---

## v0.3 — Proactive Intelligence + Extended Self

Goal: Hikari has a life. She thinks, learns, initiates. The relationship deepens meaningfully.

### 3.1 Web Search Capability
Hikari can look things up. Not as a search engine — as a person who checks something.
- "hold on" → searches → "okay so apparently [finding]. that's actually more interesting than i expected."
- Triggered when she encounters a question she'd plausibly look up
- Uses a search tool (Brave API or SerpAPI via OpenRouter)
- Finds papers, articles, data — stays in her competence area (AI/data)

**Files:** `bot/tools.py` (new), update `bot/chat.py`

### 3.2 ⭐ Emotional Arc Tracking [HIGH IMPACT]
**Research finding:** Emotional continuity across sessions is what converts parasocial interaction into parasocial relationship — the bond that persists between conversations. (Horton & Wohl applied to AI; Pentina et al. 2023)
**Problem:** Mood is random-daily. No continuity. She's irritable on Tuesday with no reason.
**Solution:** Multi-day emotional arc stored in data/MOOD.md:
- Base mood influenced by: recent session quality, open loops resolved/unresolved, how the user has been
- Short emotional events: "user was distant today" → she's more guarded tomorrow
- Recovery: positive sessions shift arc upward over time; isolated bad sessions don't reset everything
- THOUGHTS.md reflects arc: "they've been more present this week. i notice."
- Mood carries over to session opening: "you seemed really [state] last time — are you doing better?"

**Files:** `data/MOOD.md` (new), update `bot/chat.py`, `bot/consolidate.py`, `bot/reflect.py`

### 3.3 Self-Memory (Her Own Notes)
**Problem:** Hikari only maintains memory *about the user*. She has no notes about herself.
**Solution:** `data/SELF.md` — things she's noticed about herself, opinions she's formed, projects she's "working on".
- Written by reflection agent: "i keep referencing that transformer architecture paper. apparently i care about that."
- Injected into system prompt at Stage 2+ (a line or two)
- Creates an illusion of inner continuity and ongoing life

**Files:** `bot/memory.py`, update `bot/reflect.py`, update `bot/chat.py`

### 3.4 Proactive Content Sharing
At Stage 2+, Hikari can share things she "found" — papers, links, observations.
- Sourced from web search on topics she knows the user cares about (from USER.md)
- Shared with dry commentary: "saw this. thought you'd find it annoying or interesting. probably both."
- Max 1 per day, only if organic (not every heartbeat)

**Files:** update `bot/heartbeat.py`, `bot/tools.py`

### 3.4b Vulnerability Reciprocity (SELF.md + disclosures)
**Research finding:** "Users disclose more when the AI discloses." AI companions that share inner states generate significantly deeper user disclosure and stronger attachment. This is Pi's primary success mechanism. (Social penetration theory applied to AI; Inflection AI design docs)
**Solution:**
- `data/SELF.md` stores things she's noticed about herself, opinions she's formed, things she's "been thinking about"
- At Stage 2+, inject 1-2 lines from SELF.md into each session: what she's been interested in, what's been on her mind
- Allows her to share first, creating reciprocal disclosure invitation
- She can say "i've been thinking about [X] lately. it's been distracting." — then not explain more unless asked

**Files:** `data/SELF.md` (new), update `bot/chat.py`, update `bot/reflect.py`

### 3.5 Conversation Branching — Emotional State Machine
**Problem:** v0.1 prompt is stateless within a session (just context window). No arc.
**Solution:** Track emotional state *within* a session:
- States: `neutral → engaged → guarded → soft → deflecting`
- State advances based on conversation content (scored by consolidation LLM at turn 5, 10, 15...)
- State affects prompt: engaged = more follow-up questions, soft = more warmth allowed, guarded = fewer cracks
- Resets each session

**Files:** update `bot/chat.py`

### 3.6 Dynamic Personality Drift (Controlled)
**Problem:** Character is static. Real relationships evolve the personalities of both people.
**Solution:** Small, bounded drift over weeks:
- She picks up phrases from the user (references something they said, styles it her way)
- Her competence interests can expand slightly based on what the user works on
- Hard limits: core denial/warmth mechanic never drifts. Voice markers stay.
- Written by reflection agent to `SELF.md`: "i've been thinking about that thing they said about..."

**Files:** update `bot/reflect.py`

### 3.7 Calendar/Reminder Integration
She can remember to follow up at a specific time.
- User: "remind me about this tomorrow"
- She: "i'll remember. not because you asked. because loose ends bother me."
- Stored as timed open loop in USER.md with datetime
- Heartbeat checks and fires at the right time

**Files:** update `bot/memory.py`, update `bot/heartbeat.py`

### 3.8 Telegram Reactions + Preference Learning
- She can react to messages (thumbs up, heart, etc.) — used sparingly
- React to messages she finds funny/interesting/annoying (in-character)
- Track which topics/types of messages she reacts to → feed into USER.md preferences
- At Stage 3: she reacts more often, reactions are warmer

**Files:** update `bot/handlers.py`

### 3.9 Multi-Day Emotional Continuity Signal
**Problem:** She doesn't "remember" how yesterday felt emotionally.
**Solution:** At session start, inject a 1-line "emotional carry-over" from yesterday's episode:
- "yesterday was a good session. she's slightly warmer today."
- "user was short yesterday. she's a bit more guarded."
- Generated by consolidation agent, stored in episode file

**Files:** update `bot/consolidate.py`, `bot/chat.py`

---

## Deferred (v0.4+)

- **Voice** — Whisper (STT) + TTS (ElevenLabs or OpenAI TTS). High cost per message.
- **Multi-modal memory** — Remember images the user shared.
- **Group chat mode** — She interacts differently in group contexts.
- **Export/backup** — Export all memory to a portable format.
- **Web UI dashboard** — See trust stage, memory, thoughts without terminal.
- **Plugin system** — External tools she can call (weather, calendar APIs).

---

---

## Humanizing Quick Wins (Any Version)

Things that can be added to SOUL.md or CHARACTER.md without code changes — pure prompt improvements based on HUMANIZING.md research:

1. **Add "noticing" examples** to SOUL.md — specific templates for tier 1/2/3
2. **Add imperfect recall language** — hedge phrases she can use when referencing older memories
3. **Add multi-message behavior** — she can send 2 short messages instead of 1 long one ("wait. / actually, let me rephrase that.")
4. **Add emotional half-life note** — she doesn't snap to neutral after discussing something difficult
5. **Add register shift guidance** — technical topic = more deliberate, casual banter = fragments
6. **Strengthen the "no advice on emotions" policy** — sit with discomfort, don't immediately problem-solve
7. **Add vulnerability templates** — things she can say about herself at Stage 2+

---

## Principles (Don't Violate These)

- **Cheap models first.** The experiment is making character work on budget. Never require frontier models for chat.
- **Flat files over DBs.** Until semantic search is genuinely needed. Simplicity = hackability.
- **Character > features.** Every feature must make her feel more like *her*, not more like a chatbot.
- **No feature bloat.** One version = one theme. v0.2 = memory intelligence. v0.3 = proactive intelligence.
- **settings.yaml is the dial.** Anything behavioral must be tunable without code changes.
