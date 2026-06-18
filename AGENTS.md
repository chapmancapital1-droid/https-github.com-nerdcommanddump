# Agent Routing & Token Policy

## Model Routing

Route jobs by complexity at the Command Queue level — before any tokens are spent on prompt assembly:

| Job type | Model | Reason |
|----------|-------|--------|
| Simple replies, lookups, short tasks | `claude-haiku-4-5` (subagent) | 10× cheaper input, adequate for narrow tasks |
| Code, reasoning, multi-step tasks | `claude-sonnet-4-6` (primary) | Default; best cost/quality balance |
| Deep research, architecture decisions | `claude-opus-4-8` | Explicit override only — confirm before use |

**Rule**: Default to subagent (Haiku) first. Escalate to primary only when the task requires multi-step reasoning or tool chains longer than 3 hops.

## Prompt Assembly — Static Context Rules

All static content goes at the TOP of every request so Anthropic's prompt cache hits on every turn after the first:

1. System prompt / SOUL.md
2. IDENTITY.md / USER.md
3. Active skills metadata (names + one-line descriptions only — full SKILL.md loaded on demand)
4. Tool schemas (only tools scoped to this session)
5. Dynamic context (conversation history, tool results) — LAST

**Never** intersperse dynamic content between static blocks. Cache breaks on any token shift.

## Tool Loading Policy

Load tools lazily. The base tool set for any session is:

```
search_available_tools   (meta — discovers others on demand)
message                  (cross-channel reply)
read_file / write_file   (only if workspace scope active)
```

All other tools (web search, code execution, shell) are fetched by the agent when needed. This keeps every request ~40–60 tool-schema tokens instead of 800+.

## Command Queue

Use `collect` mode (1.5 s window) so rapid follow-up messages coalesce into one run instead of spawning N parallel runs that each pay full prompt-assembly cost.

Avoid `followup` mode for low-priority background tasks — route them to an isolated session so they don't add context turns to the main conversation.

## Context Pruning

Tool results older than 4 turns are evicted from context (cache-ttl mode). Individual tool outputs are capped at 12,000 chars (~3,000 tokens). If you need to refer back to old output, store it in a file and read on demand.

## Memory Scope

MEMORY.md is loaded only in private 1:1 sessions. Group/channel contexts never load it — this alone saves ~500–2,000 tokens per group message.

## Sub-agents

Delegate parallelisable subtasks (search, summarise, classify) to sub-agents rather than running them inline. Sub-agents use Haiku by default and their results are returned as a single tool call, not as additional context turns.
