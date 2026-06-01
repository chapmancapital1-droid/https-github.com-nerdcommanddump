# OpenClaw — Usage & Token Optimization Guide

## What is OpenClaw?

OpenClaw is an open-source, local-first personal AI assistant. It runs on your own devices and connects to the channels you already use (WhatsApp, Telegram, Slack, Discord, iMessage, and more) with multi-agent routing and session management.

---

## How We Can Use This

### 1. Token & Credit Preservation

#### Prompt Caching (up to 90% savings)
The [OpenClaw Token Optimizer](https://github.com/openclaw-token-optimizer/openclaw-token-optimizer) patches the agent runtime with two strategies:

- **Native prompt caching** — Static context (system prompts, tool schemas, long documents) is moved to the top of every request and tagged with cache_control markers. Providers like Anthropic cache this prefix so subsequent requests only bill for the delta, not the full context.
- **Dynamic tool loading** — Instead of sending 50+ tool schemas on every request, a single `search_available_tools` meta-function is registered. Tools are fetched on-demand, keeping the context window lean.

#### Cost Tracking (no API keys required)
The [openclaw-cost-tracker](https://github.com/pfrederiksen/openclaw-cost-tracker) skill reads local session `.jsonl` files and produces:
- Per-model token breakdown (input, output, cache hits/writes)
- Daily spend trends via text chart or JSON export
- Filter by `--days N` or `--since YYYY-MM-DD`

This gives full visibility into where credits are actually being consumed without needing to expose API credentials.

#### Multi-Provider Credit Dashboard
The `api-credits-lite` skill surfaces live credit balances across Anthropic, OpenAI, OpenRouter, Mistral, and Groq in one view — useful for knowing when to rotate providers before hitting a limit.

---

### 2. Work Organization

#### AGENTS.md Governance
OpenClaw uses a hierarchical `AGENTS.md` pattern:
- **Root** `AGENTS.md` owns hard policy and agent routing rules
- **Subdirectory** `AGENTS.md` files own local workflow conventions
- Skills own their own workflows; root only sets seams and routing

This maps directly to how Claude Code sessions can be structured: root-level rules define what agents can and cannot do, scoped files define task-specific behavior.

#### Multi-Agent Routing
Different channels, accounts, or task types can be routed to isolated agents with separate session state. Each agent has controlled tool access based on its security scope — a coding agent gets file tools, a messaging agent gets channel tools, etc.

#### Session Sandboxing
Non-primary sessions run sandboxed with restricted tool access. This prevents runaway tool calls from burning credits on background or low-priority tasks.

#### Persistent State via SQLite
OpenClaw uses a local SQLite database for persistent state. One migration owner per concept ensures no state duplication and clean upgrades.

---

## Recommended Integration Path

| Priority | Tool | Benefit |
|----------|------|---------|
| High | Token Optimizer | Up to 90% reduction on repeated-context API calls |
| High | Cost Tracker skill | Daily visibility into token spend per model |
| Medium | AGENTS.md structure | Cleaner routing, less accidental tool sprawl |
| Medium | api-credits-lite | Know your balance before hitting provider limits |
| Low | Multi-agent routing | Isolate workloads once the above are stable |

---

## References

- [openclaw/openclaw](https://github.com/openclaw/openclaw)
- [openclaw-token-optimizer](https://github.com/openclaw-token-optimizer/openclaw-token-optimizer)
- [openclaw-cost-tracker](https://github.com/pfrederiksen/openclaw-cost-tracker)
- [explain-openclaw: cost & token optimization](https://github.com/centminmod/explain-openclaw/blob/master/06-optimizations/cost-token-optimization.md)
- [awesome-openclaw-skills](https://github.com/VoltAgent/awesome-openclaw-skills)
