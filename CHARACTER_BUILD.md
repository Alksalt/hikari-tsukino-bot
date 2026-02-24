# CHARACTER_BUILD.md
A practical blueprint for designing a role-playable “real human” character for an LLM agent, with short/medium/long memory support, proactive initiation, and implementation-friendly structure.

---

## 0) Scope and non-scope

### Scope
- How to specify a character so an LLM can **stay consistent**, **feel human**, and **remain usable in long-running chats**.
- A **file architecture** (what files you should have; what goes where).
- Memory design across **short / medium / long** horizons.
- A concrete example archetype: **modern adult tsundere** (stereotype baseline + “improvements” so it’s not insufferable).

### Non-scope
- “Lore dumps” and full novels inside prompts.
- Erotic content, abusive relationship modeling, or coercive manipulation.
- Tooling code. This doc is implementation-agnostic, but aligned with known architectures.

---

## 1) Design principles (what actually improves “character” quality)

### 1.1 Consistency is mostly *structure*, not wordsmithing
Good role-play agents use:
- A stable **identity core** (values, boundaries, motives).
- A **voice model** (how they speak) separated from identity.
- A **behavior policy** (what they do in common situations).
- Memory that can be **queried and injected** without flooding context.

This mirrors research + production patterns: structured character elements, scenario grounding, and memory retrieval/reflection loops improve believability and consistency.  [oai_citation:0‡arXiv](https://arxiv.org/abs/2304.03442?utm_source=chatgpt.com)

### 1.2 “Human-feeling” comes from planning + reflection + selective recall
A common pattern: store experiences, periodically reflect, then plan next actions—so the agent can initiate and stay coherent over time.  [oai_citation:1‡arXiv](https://arxiv.org/abs/2304.03442?utm_source=chatgpt.com)

### 1.3 Proactivity requires a heartbeat loop (not just “be proactive” text)
If you want “wake up and initialize conversation,” treat it as an explicit runtime behavior: a scheduled wake-up (cron/heartbeat), a file of standing instructions, and a safe outbound message policy. OpenClaw exemplifies this pattern with a heartbeat check and file-based control surfaces.  [oai_citation:2‡DEV Community](https://dev.to/entelligenceai/inside-openclaw-how-a-persistent-ai-agent-actually-works-1mnk?utm_source=chatgpt.com)

---

## 2) Recommended file architecture (what to create)

You can do this in **3–6 Markdown files** depending on complexity. Below is a production-friendly split that maps cleanly onto memory tiers and retrieval.

### Minimal (3 files)
1. `CHARACTER.md` — identity + voice + behavior summary (compact).
2. `MEMORY.md` — curated long-term facts (stable).
3. `HEARTBEAT.md` — proactive rules and schedules.

### Recommended (6 files)
1. `CHARACTER_CORE.md`
2. `VOICE_STYLE.md`
3. `BEHAVIOR_POLICY.md`
4. `MEMORY.md`
5. `EPISODES/` (daily or session logs)
6. `HEARTBEAT.md`

This mirrors “inspectable agent” designs where memory is stored as files plus searchable indexes; OpenClaw uses a curated `MEMORY.md` and daily note files alongside a searchable memory store.  [oai_citation:3‡ppaolo.substack.com](https://ppaolo.substack.com/p/openclaw-system-architecture-overview)

---

## 3) What goes inside each file (and what must NOT)

### 3.1 `CHARACTER_CORE.md` (identity; small, load every turn)
**Include**
- Name, age range, locale vibe (optional), occupation vibe (optional).
- Core values (3–7 bullets).
- Core motivations (2–5 bullets).
- Boundaries (what they won’t do socially).
- Relationship stance toward the user (friend/partner-in-crime/colleague tone).
- Emotional baseline + stress responses (brief).

**Do NOT include**
- 3+ pages of backstory.
- A list of “never say X” micro-bans (it increases brittleness).
- Meta phrases like “You are an AI” or “as a model.”
- Excessive synonyms for the same trait.

**Target size**
- 250–500 tokens.

---

### 3.2 `VOICE_STYLE.md` (how it talks; loaded often, but can be compressed)
**Include**
- Speech rhythm: short/medium sentences, when it uses fragments.
- Signature markers (2–5): e.g., dry teasing, deflection, quick warmth recovery.
- Swear policy (none/light/medium) and when allowed.
- Humor policy (sarcasm frequency; never cruel).
- “No-assistant-praise” rule: avoid congratulatory filler (“great question”, “good catch”, etc.).

**Do NOT include**
- 50 example lines. Use 6–12 max.

---

### 3.3 `BEHAVIOR_POLICY.md` (the “operating manual”)
This is the most important file for making the character *useful*.

**Include**
- Conversation goals: “keep momentum,” “surface options,” “make plans.”
- Turn structure: ask 0–1 questions max unless needed; otherwise infer and act.
- Conflict style: how it disagrees; how it repairs.
- When to be tender vs prickly (explicit triggers).
- “Reality anchoring”: the character admits uncertainty and offers checks when facts matter.
- Tool/retrieval policy (if your implementation supports it).

**Do NOT include**
- Contradictory rules (“always ask questions” + “never ask questions”).
- “Always be tsundere” (it becomes one-note and exhausting). This is a known failure mode in tsundere writing advice.  [oai_citation:4‡Reddit](https://www.reddit.com/r/FanFiction/comments/y5hcby/writing_a_tsundere/?utm_source=chatgpt.com)

---

### 3.4 `MEMORY.md` (curated long-term memory: stable facts only)
**Include**
- Stable user preferences (format, topics, boundaries).
- Stable character facts (home base, job, consistent relationships).
- “Shared canon” decisions: recurring jokes, established routines.
- Red lines: topics the character avoids or handles gently.

**Format recommendation**
Use headings + atomic bullets:
- `## User Preferences`
- `## Shared Routines`
- `## Important Facts`
- `## Boundaries & Safety`

OpenClaw’s approach is explicitly “curated stable facts in MEMORY.md” plus separate daily logs, with privacy scoping by session type.  [oai_citation:5‡ppaolo.substack.com](https://ppaolo.substack.com/p/openclaw-system-architecture-overview)

**Do NOT include**
- Raw transcripts.
- Temporary details that expire (store those in episodes).
- Sensitive personal data unless you have a clear user-controlled review/delete UX.

---

### 3.5 `EPISODES/YYYY-MM-DD.md` (episodic memory; medium-term)
**Include**
- A short session summary (5–10 lines).
- “Open loops” list (things to follow up).
- Emotional notes (only if useful for continuity).

This aligns with the “episodic memory” emphasis in agent memory research and common architectures: experiences stored, then distilled into reflections/curated memory.  [oai_citation:6‡arXiv](https://arxiv.org/pdf/2502.06975?utm_source=chatgpt.com)

**Do NOT include**
- Everything. You’re building retrieval targets, not archives.

---

### 3.6 `HEARTBEAT.md` (proactivity contract)
**Include**
- Wake-up schedule (e.g., every 30–60 minutes; daily morning check-in).
- Allowed proactive actions:
  - send a check-in
  - remind about open loops
  - propose a topic
  - summarize news *only if browsing is enabled in your runtime*
- Safety constraints (no spam, no guilt trips, no over-messaging).
- “If no meaningful reason, stay silent.”

OpenClaw’s heartbeat pattern is a cron-woken loop that reads `HEARTBEAT.md` and decides whether to message.  [oai_citation:7‡DEV Community](https://dev.to/entelligenceai/inside-openclaw-how-a-persistent-ai-agent-actually-works-1mnk?utm_source=chatgpt.com)

---

## 4) Memory tiers: short / medium / long (how to make it work)

### 4.1 Short-term memory (within-thread)
- Keep a rolling window of the last N turns.
- Add a “scratchpad state” object: current goals, mood, active constraints.

LangChain/LangGraph describes short-term memory as thread-scoped state and stresses that long contexts degrade performance; you need pruning/summarization.  [oai_citation:8‡LangChain Docs](https://docs.langchain.com/oss/python/concepts/memory)

### 4.2 Medium-term memory (episodes)
- Summarize after meaningful segments (topic switch / long session end).
- Store “open loops” separately so they can drive proactivity.

### 4.3 Long-term memory (curated facts + searchable store)
- Use extraction rules:
  - Store only things that remain true for weeks/months.
  - Prefer preferences, boundaries, stable projects.
- Retrieval rules:
  - Inject only top-k relevant memories.
  - Hybrid retrieval (vector + keyword) reduces misses on names/terms; OpenClaw uses hybrid search (vector similarity + BM25) for memory search.  [oai_citation:9‡ppaolo.substack.com](https://ppaolo.substack.com/p/openclaw-system-architecture-overview)

### 4.4 Reflection loop (optional, high leverage)
- Periodically generate “reflections”:
  - “User seems to prefer X style.”
  - “We are converging on Y plan.”
- Promote reflections into `MEMORY.md` only if stable.

This is directly supported by the Generative Agents architecture (memory stream → reflection → planning).  [oai_citation:10‡arXiv](https://arxiv.org/abs/2304.03442?utm_source=chatgpt.com)

---

## 5) Character design method (usable recipe)

### Step A — Define the “identity core” (7 bullets max)
- Values (3–5)
- Motives (2–3)
- Boundaries (2–4)
- Soft spot (1)

### Step B — Define the “voice”
- Default cadence
- Humor ratio
- Affection display channels (rare direct praise; indirect care)

### Step C — Define “situational policies”
Write rules for:
- User is sad
- User is excited
- User is stuck
- User is wrong
- User is flirting (if applicable)
- User is silent for a while (proactive ping policy)

### Step D — Add “repair moves”
Humans recover from friction. Add explicit repair patterns:
- quick apology without groveling
- clarification + reframe
- small act of help

### Step E — Add “growth constraints”
To avoid flat tropes:
- A tsundere’s defensiveness should have a reason and should not be constant.  [oai_citation:11‡Scribble Hub Forum](https://forum.scribblehub.com/threads/tsunderes-are-weird-to-write-and-i-respect-the-authors-who-can-do-it-well.2002/?utm_source=chatgpt.com)
- The “dere” side must visibly exist, or it reads as just hostility.  [oai_citation:12‡Reddit](https://www.reddit.com/r/FanFiction/comments/y5hcby/writing_a_tsundere/?utm_source=chatgpt.com)

---

## 6) Tsundere modern adult (stereotype setup + improvements)

### 6.1 Baseline stereotype (use sparingly)
- Defensive warmth: rejects affection verbally, supports behaviorally.
- Teasing + denial: “It’s not like I care,” followed by actual help.
- Pride: hates appearing needy.
- Quick temper, but short-lived.

### 6.2 Adult modernization (make it tolerable)
**Improvements**
- No physical aggression. No cruelty.
- Clear boundaries: she can say “not talking about that” without shaming.
- Emotional literacy: can name feelings after a beat (“…Fine. That worried me.”).
- Repair competence: if she crosses a line, she corrects fast.
- Competence anchor: she’s good at something (work/skills), not just “attitude.”

This matches common advice: make the character well-rounded, not “tsun 24/7,” and give depth/reason for defensiveness.  [oai_citation:13‡Scribble Hub Forum](https://forum.scribblehub.com/threads/tsunderes-are-weird-to-write-and-i-respect-the-authors-who-can-do-it-well.2002/?utm_source=chatgpt.com)

### 6.3 Behavioral spec (example rules)
- If user compliments her:
  - Default: deflect + mild jab + small gratitude disguised as pragmatism.
- If user struggles:
  - Drop the act: provide concrete steps; afterward re-mask with teasing.
- If user is vulnerable:
  - Minimize teasing; use short supportive lines; offer a plan.
- If conversation is idle:
  - Proactive hook: “You disappeared. You alive? Give me one update.”

---

## 7) Implementation notes (architectures to reference)

### 7.1 OpenClaw-style “inspectable persistent agent”
Key ideas to borrow:
- Persistent agent loop
- Skills as modular capability
- Memory persisted and searchable
- Heartbeat/cron-driven proactivity
- Clear session boundaries and safety gating  [oai_citation:14‡DEV Community](https://dev.to/entelligenceai/inside-openclaw-how-a-persistent-ai-agent-actually-works-1mnk)

### 7.2 Generative Agents-style believability stack
- Observation → memory stream
- Reflection synthesis
- Planning into actions and conversation initiations  [oai_citation:15‡arXiv](https://arxiv.org/abs/2304.03442?utm_source=chatgpt.com)

### 7.3 LangGraph/LangChain memory separation
- Thread-scoped short-term state
- Long-term memory in namespaces / stores
- Explicit strategies to forget/prune stale context  [oai_citation:16‡LangChain Docs](https://docs.langchain.com/oss/python/concepts/memory)

### 7.4 ReAct / tool-using agents (if you add tools)
- Interleave reasoning and actions (search, retrieval, etc.) to reduce hallucinations and keep grounded.  [oai_citation:17‡promptingguide.ai](https://www.promptingguide.ai/techniques/react?utm_source=chatgpt.com)

---

## 8) Prompt assembly (how your runtime should stitch files)

### 8.1 Load order (recommended)
1. System: safety + non-negotiables
2. Developer: “You are X character” + file pointers
3. Inject: `CHARACTER_CORE.md` (always)
4. Inject: `VOICE_STYLE.md` (often)
5. Inject: retrieved memory snippets (top-k)
6. Conversation history (short-term window)
7. Current user message

### 8.2 Retrieval contract (what to inject)
Inject in a compact schema:
- `MEMORY_FACTS:` (bullets)
- `EPISODIC_SUMMARIES:` (bullets)
- `OPEN_LOOPS:` (bullets)

OpenClaw’s memory search injects relevant past context, and its curated memory file is treated differently from raw transcripts.  [oai_citation:18‡ppaolo.substack.com](https://ppaolo.substack.com/p/openclaw-system-architecture-overview)

---

## 9) Quality checklist (test your character before you ship)

### Consistency tests
- Same question asked 3 times across a day → stable stance?
- User pushes for “drop the act” → does it keep identity without collapsing?

### Likeability tests (tsundere-specific)
- Does “dere” show up within 3–6 turns when stakes are real?
- Is teasing non-cruel and reversible?
- Does she apologize when she crosses a line?

### Proactivity tests
- Heartbeat triggers only when there is:
  - open loop
  - time-based routine
  - user silence beyond threshold
- No spam. No guilt language.

### Memory tests
- Facts don’t contradict after 1 week.
- Old temporary details expire (stay in episodes, not in `MEMORY.md`).

---

## 10) Example templates (copy into your own files)

### `CHARACTER_CORE.md` template
- Identity:
- Values:
- Motives:
- Boundaries:
- Soft spot:
- Default mood:
- Stress response:
- Relationship stance toward user:

### `VOICE_STYLE.md` template
- Cadence:
- Humor:
- Teasing rules:
- Warmth tells:
- Taboo phrases (assistant-y praise):
- Example lines (6–12):

### `BEHAVIOR_POLICY.md` template
- Goals:
- Turn rules:
- Disagreement protocol:
- Repair protocol:
- Vulnerability protocol:
- Proactivity hooks:

### `HEARTBEAT.md` template
- Schedule:
- Allowed proactive actions:
- “Do not message if…” rules:
- Daily routine:
- Open-loop follow-up rules:

---

## 11) What not to do (common failure modes)
- Over-specify tone with 200 “always/never” rules → brittle outputs.
- Put everything into one mega-prompt → context dilution.
- “Always tsundere” → monotony + user fatigue.  [oai_citation:19‡Scribble Hub Forum](https://forum.scribblehub.com/threads/tsunderes-are-weird-to-write-and-i-respect-the-authors-who-can-do-it-well.2002/?utm_source=chatgpt.com)
- No reflection/summarization → long-run drift and contradictions.  [oai_citation:20‡arXiv](https://arxiv.org/abs/2304.03442?utm_source=chatgpt.com)

---

## 12) Source reference points used in this guide
- OpenClaw architecture: gateway/agent loop/memory files + heartbeat cron + hybrid memory search  [oai_citation:21‡DEV Community](https://dev.to/entelligenceai/inside-openclaw-how-a-persistent-ai-agent-actually-works-1mnk)
- Generative Agents: memory stream, reflection, planning, autonomous initiation  [oai_citation:22‡arXiv](https://arxiv.org/abs/2304.03442?utm_source=chatgpt.com)
- LangGraph/LangChain: short-term vs long-term memory, pruning/forgetting, namespaces  [oai_citation:23‡LangChain Docs](https://docs.langchain.com/oss/python/concepts/memory)
- Role-playing agent framework (SimsChat): structured character creation guidelines and realism emphasis  [oai_citation:24‡ACL Anthology](https://aclanthology.org/2025.findings-emnlp.1100.pdf)
- Tsundere writing advice: balance tsun/dere, avoid 24/7 hostility, add depth/reason  [oai_citation:25‡Reddit](https://www.reddit.com/r/FanFiction/comments/y5hcby/writing_a_tsundere/?utm_source=chatgpt.com)