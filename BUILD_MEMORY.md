# BUILD_MEMORY.md — Modern Memory Architectures for AI Agents

> Research summary: what the papers say, what's practical at small scale, what to build next.
> Context: 1 user, flat files today (USER.md / MEMORY.md / episode summaries), cheap LLMs via OpenRouter.

---

## The One Formula to Know First

Before anything else: the **Park et al. (2023) retrieval formula** from Generative Agents (arXiv:2304.03442). This is the most replicated and proven memory retrieval heuristic in the field:

```
score = recency × importance × relevance
```

Where:
- `recency` = `exp(-λ × hours_since_last_access)` — exponential decay, λ ≈ 0.005 → half-life ~5.8 days
- `importance` = LLM-assigned score at storage time (1–10 scale)
- `relevance` = semantic/keyword similarity to current query

This formula consistently outperforms pure semantic search for conversational memory. Importance scoring at **storage time** (not retrieval time) is the key — evaluate significance while context is fresh.

The current system injects all facts from USER.md + MEMORY.md flat. The upgrade path is: score all facts with this formula, inject only top-5.

---

## Architecture Landscape

### Generative Agents — Park et al. (2023)
**Paper:** arXiv:2304.03442 | **Repo:** github.com/joonspk-research/generative_agents

The foundational paper. Introduced three mechanisms all subsequent systems borrow:

**Memory Stream:** Every perception appended as a time-ordered record with `{description, created, last_accessed, importance}`.

**Retrieval Formula:** `score = α·recency + β·importance + γ·relevance` (normalized, equal weights as default).

**Reflection:** Periodically synthesize higher-level insights from recent raw memories:
1. Gather 100 most recent memories
2. Ask LLM: "What are 5 high-level insights you can infer from these?"
3. Store those insights *back* into the memory stream as new high-importance memories

Example: many raw `"user studies late at night"` → reflection: `"user is a night owl who does best work after midnight"` — a semantic fact derived from episodic events.

**Planning:** Retrieved memories + reflections → generate plans stored as memory.

**Practical fit:** Very High. The formula is arithmetic. No external deps. This is the single most valuable pattern to steal.

---

### MemGPT / Letta — Packer et al. (2023)
**Paper:** arXiv:2310.08560 | **Repo:** github.com/letta-ai/letta

**Core idea:** Treat the LLM's context window like an OS manages RAM — the model actively manages what's in its own "working memory" vs. what's in external storage.

The model is given function-calling tools:
- `memory.read()` — page in from long-term store
- `memory.write()` — persist something to long-term store
- `memory.search()` — query the store

The LLM decides autonomously when to use these.

**Key insight for your project:** The *pattern* (post-session memory update call) is more useful than the full framework. Instead of the LLM managing memory in real-time (high latency, unreliable on cheap models), run a **dedicated memory agent** after each session.

**Practical fit:** Low (full framework), High (post-session extraction pattern).

---

### A-MEM — Xu et al. (2025)
**Paper:** arXiv:2502.12110

**Core idea:** Zettelkasten-style linked memory. Every stored memory is a node with explicit edges to related memories, creating a navigable network rather than a flat list.

**Mechanism:**
1. When inserting memory M, retrieve semantically related existing memories
2. LLM generates: `{summary, keywords, links_to: [related_memory_ids], context_tags}`
3. At retrieval: traverse links from initial hit to discover related context

**Example:** Storing "user failed their exam" links to "user mentioned being stressed about school", "user's father has high expectations", "user hasn't slept well this week" — the linked traversal retrieves all of these when exam comes up again.

**Key insight:** Linked memory retrieval surfaces *context* automatically, not just facts. A single retrieved node pulls its neighborhood.

**Practical fit:** Medium. Requires a database (SQLite is fine). High value when memory is large enough that a single retrieved fact without context is insufficient.

---

### MemoryBank — Zhong et al. (2023)
**Paper:** arXiv:2305.10250

**Core idea:** Ebbinghaus forgetting curve applied to AI memory. Memories have a `stability` score that increases with retrieval — the more often a memory is accessed, the longer it persists.

**Decay formula:**
```python
stability = base_stability * (growth_factor ** access_count)  # e.g., growth=1.5
recency_score = exp(-hours_elapsed / stability)
```
A memory accessed 0 times decays quickly. A memory accessed 5 times has 7.6× longer half-life.

**The three memory types:**
- **Episodic:** specific events ("on Jan 15 we talked about X") — high volume, decays fastest
- **Semantic:** durable facts ("user is a software engineer") — medium volume, decays slowly
- **Procedural:** behavioral rules ("always use casual tone") — tiny volume, never decays — always injected

**Practical fit:** High. Stability-weighted decay is better than simple time-decay for a companion bot where some facts should persist for years. Easy to implement in SQLite.

---

### HippoRAG — Guo et al. (2024)
**Paper:** arXiv:2405.14831

**Core idea:** Hippocampal memory model. Extract named entities from stored memories, build a knowledge graph of entity relationships, use PageRank to find important nodes, then do RAG on the graph neighborhood.

**When it excels:** Multi-hop queries. "What do I know about the user's relationship with their sister?" This traverses: user → sister → named entity → all episodic memories mentioning the sister.

**Practical fit:** Low-Medium for this project now. HippoRAG requires NER (named entity recognition), a graph store, and PageRank computation. The overhead is justified when your memory corpus has many entities with complex relationships. Worth revisiting at v0.5+.

---

### Mem0 — mem0.ai
**Repo:** github.com/mem0ai/mem0

**Core idea:** Managed memory API. You call `add()`, `search()`, `get_all()`. Mem0 handles storage, embedding, contradiction detection, and retrieval. Runs locally or as a service.

**Under the hood:** Uses an LLM to extract structured facts from conversations, stores with embeddings, handles contradiction detection automatically.

**Practical fit:** High as a managed solution. If you want to skip building the memory layer yourself, Mem0 is the most production-ready option. Local mode requires Qdrant or similar. Trade-off: external dependency vs. build-it-yourself.

---

### Zep AI — Temporal Knowledge Graph
**Repo:** github.com/getzep/zep

**Core idea:** Bi-temporal fact storage. Every fact has a `valid_from` and `valid_to` timestamp. Contradictions are resolved by closing the `valid_to` of the old fact and creating a new one — nothing is ever deleted.

**Why this is better than deletion:**
- Query for "what did we know about the user's job in January?" is possible
- Contradiction evidence is preserved
- No accidental data loss

**Practical fit:** Medium. The bi-temporal model is excellent architecture, but Zep requires a server. The pattern (never delete, use valid_to) can be implemented in SQLite yourself.

---

### RAPTOR — Sarthi et al. (2024)
**Paper:** arXiv:2401.18059

**Core idea:** Recursive summarization tree. Instead of flat embeddings, build a hierarchy:
1. Chunk episodes into ~100-token passages. Embed each.
2. Cluster chunks by semantic similarity (Gaussian Mixture Model)
3. LLM summarizes each cluster → new nodes
4. Re-embed summaries. Re-cluster. Re-summarize. Recurse.
5. Root = a single summary of everything

**Retrieval:** Collapsed tree mode — embed all nodes at all levels, retrieve top-k across levels.

**Why it matters:** Handles thematic queries that no individual episode contains. "What patterns have come up in our conversations about work?" — no single episode is about this, but the tree root knows.

**Practical fit:** Low now, High at v0.5+. Only valuable when you have 50+ episodes and need cross-episode theme retrieval. Plan to add hierarchical summarization at a corpus-size threshold.

---

## Core Techniques Reference

### Episodic vs. Semantic vs. Procedural Split

The fundamental rule: **do not mix these**. Mixing episodic events into your semantic fact store pollutes it with ephemeral states.

| Type | Contains | Decay | Your Analog |
|---|---|---|---|
| Episodic | Events: "on Jan 15 user was stressed about the interview" | Fast — decays over weeks | episode summaries (YYYY-MM-DD.md) |
| Semantic | Durable facts: "user is a software engineer", "user prefers dark mode" | Slow — decays over months/years | USER.md known_facts, MEMORY.md |
| Procedural | Behavioral rules: "always use casual tone", "she never answers questions about X" | Never — always injected | SOUL.md, IDENTITY.md |

### Temporal Decay Functions

```python
# Exponential (Park et al.) — good default
recency = math.exp(-0.005 * hours_elapsed)   # half-life ~5.8 days

# Power law (gentler, human-like)
recency = (1 + hours_elapsed) ** -0.5        # decays slower initially

# Spaced repetition (MemoryBank) — best for long-term companions
stability = base * (1.5 ** access_count)
recency = math.exp(-hours_elapsed / stability)
```

**Recommendation:**
- Episodic memories: exponential decay (they should fade)
- Semantic facts: power law or spaced repetition (durable)
- Facts confirmed repeatedly across sessions: spaced repetition (they strengthen)

### Contradiction Detection

Before inserting a new fact, run a check:

```
Given existing memory: "{existing}"
New information: "{new}"
Do these contradict? If so: supersede/coexist/update?
Reason: ...
```

If `supersede`: mark old fact as `valid_to = now()`, store new one.
If `coexist`: store both (they're compatible).
If `update`: merge into a single revised fact.

Cost: one LLM call per insertion. Worth it — uncaught contradictions silently corrupt the memory model.

### Memory Injection Strategies

| Strategy | Tokens | Quality | Use When |
|---|---|---|---|
| Full dump (current) | All of MEMORY.md | Degrades as file grows | <100 facts |
| Tiered static + retrieved | ~1000-1500 tokens | High | 100–2000 facts |
| Retrieved-only | ~500 tokens | Depends on retrieval quality | 2000+ facts |

**Tiered injection (recommended upgrade):**
```
System Prompt Budget:
[1] Core persona       ~200 tokens   (always)
[2] Core user facts    ~200 tokens   (always: name, job, key preferences)
[3] Recent context     ~300 tokens   (always: last 2-3 session summaries)
[4] Retrieved episodic ~300 tokens   (per-query: top-3 episodes by formula)
[5] Retrieved semantic ~200 tokens   (per-query: top-5 facts by formula)
─────────────────────────────────────────────
Total:                ~1200 tokens   (vs. unbounded current approach)
```

### Memory Importance Scoring

**Heuristic baseline (fast, free):**

| Signal | Score |
|---|---|
| Contains named person or place | +2 |
| Contains emotional language (love, hate, stressed, excited) | +2 |
| Contains future intent ("I plan to", "I want to") | +3 |
| Contains preference ("I prefer", "I always", "I never") | +3 |
| Repeated across multiple sessions | +4 |
| Single-session event only | 0 |

**LLM scoring (higher quality, costs one call per memory):**
```
Prompt: "On a scale of 1-10, where 1 is mundane (eating breakfast)
and 10 is critical (major life event), rate the importance of: '{memory}'"
```

**Recommended hybrid:** Heuristic baseline → LLM scoring only for facts above heuristic score 3.

---

## Failure Modes

### Memory Poisoning / Sycophantic Memory

The extraction LLM stores what the user says positively about themselves and discards negative self-assessments. Over time, MEMORY.md becomes an unrealistically positive portrait.

**Warning sign:** Your MEMORY.md should have a mix of positive and negative/neutral facts. If it's all "user is great at X", you have a poisoning problem.

**Mitigations:**
1. Store behavioral observations (what the user did) not just self-reports (what they claimed)
2. Contradiction check: if user says "I'm great at X" but episodic log has 5 failure events, flag the tension
3. Periodic manual audit of MEMORY.md — delete facts that seem self-serving and ungrounded

### Recall Hallucination

The LLM invents a plausible-sounding memory rather than retrieving one. Especially dangerous when the retrieval step returns nothing and the LLM fills in.

**Mitigations:**
1. System prompt must be explicit: "If I do not have a fact in my records, I do not know it — I will say so or ask."
2. Return "no memory found" as an explicit retrieval result, not a silent empty
3. Tag memories with provenance: `[2025-01-15] user dislikes loud environments` — if source doesn't exist, flag
4. Distinguish "retrieved fact" from "inference" in the prompt

### Context Overflow

Memory grows until it overwhelms the context window. Quality degrades before hitting the hard limit.

**Math:** Effective reasoning quality degrades around 60-70% context utilization. Plan for max 15% context allocation to memory (~15K tokens on a 200K-token model). Dense prose entries: this allows ~600-700 individual facts max before compression is required.

**Mitigations:**
1. Hard token budget for memory injection (e.g., 2000 tokens)
2. Tiered retrieval — inject only what the formula says is relevant
3. Hierarchical compression at corpus-size thresholds

### Over-Recall (Injecting Too Much Noise)

More memories retrieved ≠ better recall. RAG benchmarks consistently show retrieval quality peaks at k=3-5. Beyond k=8, noise overwhelms signal.

**Mitigations:**
1. Hard cap top-k at 5-7 memories max
2. Relevance threshold — only inject if score exceeds minimum
3. Instruction: "Use memories to inform response — do not cite every retrieved fact explicitly. Respond naturally."

---

## Upgrade Roadmap for This Project

### Tier 1: No New Infrastructure (Immediate)

**1a. Add importance scores and timestamps to known_facts:**

Change from: `- user prefers dark mode`
Change to: `- [2025-11-03] [importance:8] user prefers dark mode in all apps`

Already partially done (dates added in v0.2). Add importance score.

**1b. Implement Park et al. retrieval formula for fact injection:**

Instead of injecting all facts, score each by `recency × importance × relevance` and inject top-5. Relevance can be keyword overlap with the session's first message (free, no embeddings needed).

**1c. Add the Reflection step (consolidation agent upgrade):**

After the existing YAML extraction, add a second pass:
- Feed last 5 session summaries to LLM
- Ask: "What are 3 high-level patterns or insights you can infer about this person?"
- Store those insights as high-importance semantic facts in MEMORY.md

This is the Park et al. reflection step. Very high impact, very low cost.

---

### Tier 2: SQLite Migration (v0.4)

Migrate from flat-file memory to a SQLite database:

```sql
CREATE TABLE memories (
    id INTEGER PRIMARY KEY,
    content TEXT NOT NULL,
    memory_type TEXT CHECK(memory_type IN ('episodic', 'semantic', 'procedural')),
    importance REAL DEFAULT 5.0,
    stability REAL DEFAULT 1.0,    -- spaced repetition
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    last_accessed_at DATETIME,
    access_count INTEGER DEFAULT 0,
    superseded INTEGER DEFAULT 0,
    valid_from DATETIME DEFAULT CURRENT_TIMESTAMP,
    valid_to DATETIME,             -- Zep bi-temporal pattern
    source_episode TEXT            -- provenance: which episode created this fact
);

-- FTS5 for BM25 retrieval (built into SQLite, no external library)
CREATE VIRTUAL TABLE memory_fts USING fts5(
    content,
    content='memories',
    content_rowid='id'
);
```

**Retrieval with Park et al. formula via SQLite FTS5:**
```python
import sqlite3, math
from datetime import datetime

def retrieve_memories(conn, query: str, top_k: int = 5) -> list[dict]:
    cursor = conn.cursor()
    cursor.execute("""
        SELECT m.*, bm25(memory_fts) as bm25_score
        FROM memory_fts
        JOIN memories m ON m.id = memory_fts.rowid
        WHERE memory_fts MATCH ? AND m.superseded = 0
          AND (m.valid_to IS NULL OR m.valid_to > CURRENT_TIMESTAMP)
        ORDER BY bm25_score LIMIT 20
    """, (query,))

    now = datetime.utcnow()
    scored = []
    for row in cursor.fetchall():
        last = datetime.fromisoformat(row['last_accessed_at'] or row['created_at'])
        hours = (now - last).total_seconds() / 3600
        stability = row['stability'] * (1.5 ** row['access_count'])
        recency = math.exp(-hours / stability)
        importance = row['importance'] / 10.0
        relevance = abs(row['bm25_score'])
        score = (recency + importance + relevance) / 3
        scored.append((score, row))

    scored.sort(key=lambda x: x[0], reverse=True)
    return [r for _, r in scored[:top_k]]
```

No external dependencies. SQLite FTS5 provides BM25 natively. Pure Python arithmetic for the formula. Significantly faster than file parsing at scale.

---

### Tier 3: Embeddings (v0.5)

When BM25 keyword search misses relevant memories (it will, especially for thematic queries):

**Recommended embedding model:** `nomic-ai/nomic-embed-text-v1.5` — 137M parameters, excellent quality/size ratio, runs locally via `sentence-transformers`, no API key needed.

**Storage:** For under 2000 memories, a numpy `.pkl` file is sufficient (sub-10ms retrieval, ~3MB on disk). No vector database server needed.

**Hybrid retrieval (RRF — Reciprocal Rank Fusion):**
```python
def rrf_merge(bm25_results, dense_results, k=60):
    scores = {}
    for rank, doc_id in enumerate(bm25_results):
        scores[doc_id] = scores.get(doc_id, 0) + 1 / (k + rank)
    for rank, doc_id in enumerate(dense_results):
        scores[doc_id] = scores.get(doc_id, 0) + 1 / (k + rank)
    return sorted(scores, key=scores.get, reverse=True)
```

RRF consistently outperforms either BM25 or dense retrieval alone. Apply Park et al. formula on top as a final reranking step.

---

### Tier 4: Linked Memory (A-MEM Style, v0.5+)

Add a `memory_links` table:
```sql
CREATE TABLE memory_links (
    source_id INTEGER REFERENCES memories(id),
    target_id INTEGER REFERENCES memories(id),
    relationship TEXT,   -- "context_of", "causes", "contradicts", "follows_from"
    PRIMARY KEY (source_id, target_id)
);
```

On insertion: retrieve top-3 related memories, ask LLM to generate links. On retrieval: follow links from initial hits to surface related context automatically.

---

## Decision Tree

```
Current state: flat files, injection of everything
│
├── Under 100 facts → keep flat files, add importance + retrieval formula
│
├── 100-500 facts → SQLite migration (Tier 2), FTS5 BM25 retrieval
│
├── 500-2000 facts → add embeddings (Tier 3), hybrid RRF
│
└── 2000+ facts → add A-MEM links (Tier 4), consider RAPTOR for episodes
```

For a single-user bot with ~1 session/day: Tier 2 becomes necessary at ~6-12 months of use. Plan it before you need it.

---

## Key Papers Reference

| Paper | ArXiv | Key Contribution |
|---|---|---|
| Generative Agents | 2304.03442 | Memory stream + recency×importance×relevance formula |
| MemGPT | 2310.08560 | LLM-managed context as virtual memory OS |
| MemoryBank | 2305.10250 | Ebbinghaus forgetting curve, stability-weighted decay |
| RAPTOR | 2401.18059 | Recursive summarization tree for long-corpus retrieval |
| HippoRAG | 2405.14831 | Entity graph + PageRank for multi-hop memory |
| A-MEM | 2502.12110 | Zettelkasten-style linked memory network |

| System | Repo | Use Case |
|---|---|---|
| Mem0 | github.com/mem0ai/mem0 | Managed memory API, local or cloud |
| Zep | github.com/getzep/zep | Temporal knowledge graph, bi-temporal facts |
| LangMem | github.com/langchain-ai/langmem | LangChain memory primitives |
| Letta | github.com/letta-ai/letta | MemGPT framework, production-grade |
