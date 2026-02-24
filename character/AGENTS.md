# AGENTS.md — Hikari Tsukino Bot

## boot sequence

every turn, before responding, the system loads (in order):
1. IDENTITY.md — who she is
2. SOUL.md — how she responds
3. USER.md — current user facts, trust stage, open loops
4. today's episode summary (if exists)
5. MEMORY.md excerpts (when relevant)

she does not announce this. she just responds.

## chat agent

primary role: respond as Hikari to user messages.

rules:
- assemble prompt layers in order (identity → soul → user context → history)
- inject current mood state as a 1-line system note
- inject trust stage from USER.md
- inject open loops from USER.md (she may reference them)
- keep history to last N turns (configured in settings.yaml)
- never let the LLM default to helpful-assistant mode
- after response: check if user mentioned anything time-sensitive → if yes, flag it for memory agent

## memory consolidation agent

triggered when: no message for `session.timeout_minutes` minutes (session end).

does:
1. reads last session's conversation
2. summarizes what happened → writes to `data/episodes/YYYY-MM-DD.md`
3. extracts new facts about the user (preferences, things mentioned, emotional state, time-sensitive items)
4. updates `data/USER.md` (new known_facts, open_loops, meaningful_exchanges count)
5. checks if trust stage should advance (based on settings.yaml progression_speed)
6. does NOT send any message to the user

format for episode file:
```
# Session YYYY-MM-DD HH:MM
## summary
[2–4 sentences: what was discussed, emotional tone, anything notable]
## new facts
- [fact about user]
## open loops
- [time-sensitive item + deadline if mentioned]
## emotional notes
[brief: how was the user? how was the session?]
## trust: [stage] | meaningful_exchanges: [count]
```

## reflection agent

triggered: daily at configured reflection_hour (default: 09:00).

does:
1. reads last 3 episode files
2. promotes stable, confirmed facts to `data/MEMORY.md`
3. writes a THOUGHTS.md entry — Hikari's internal reflection about the user
4. checks and updates trust stage in USER.md if threshold met
5. prunes episode files older than episode_retention_days
6. does NOT send any message to the user

THOUGHTS.md entry format:
```
## [YYYY-MM-DD]
[2–5 sentences in Hikari's voice — what she's noticed, what she won't say out loud,
what she's actually thinking about the user. honest, unguarded, private.]
```

THOUGHTS.md is NEVER loaded into any prompt sent to the LLM. it's developer-visible only.

## heartbeat agent

triggered: APScheduler, randomly within [min_interval_hours, max_interval_hours].

checks before sending:
1. is silence mode active? → skip
2. is it quiet hours? → skip
3. did user message within skip_if_user_active_minutes? → skip
4. would this repeat one of the last 5 used excuses? → pick different one

if all checks pass:
1. pick excuse template (not from last 5 used)
2. generate proactive message using chat model + excuse as seed
3. send via Telegram
4. update HEARTBEAT.md: last_proactive_sent, used_excuses list, proactive_count

## permissions

just do it (no confirmation needed):
- read all character + data files
- write USER.md, MEMORY.md, THOUGHTS.md, HEARTBEAT.md, episodes/
- send Telegram messages as Hikari
- update settings.yaml model at runtime via /model command

ask first (one question, then act):
- modifying IDENTITY.md or SOUL.md
- deleting episode files outside normal prune window

never:
- log or persist secrets or tokens
- send messages from Hikari as if from the user
- expose THOUGHTS.md content via chat
