# Agent roster evaluation for NerdCommand

_How the 30 subagents in `.claude/agents/` map onto NerdCommand.ai._

## What NerdCommand is (the lens)

NerdCommand.ai is an **all-in-one AI command center** — "one AI command center for
writing, images, video, audio, voice, agents, workflows, and more," bundling
**5,000+ tools** across **video, images, audio, voice, agents, writing, research,
and automation**. It sells to three tiers: **individual creators** (Basic),
**small teams** (Studio), and **agencies/enterprises** (Agency Mode), and ships
recurring output ("52 weekly campaign themes," daily multi-format content packs).

That makes this roster unusually well-aligned, because NerdCommand is **both**:
1. a **software product** that has to be built and operated, and
2. an **AI-agent + content platform** whose value *is* a library of capable agents.

So the roster splits cleanly across three lenses:

- **A — Build & run** the platform (engineering agents)
- **B — Ship as product** (content/media agents become customer-facing bundled agents)
- **C — Grow the business** (marketing agents used on NerdCommand itself)

Fit key: 🟢 High · 🟡 Medium · ⚪ Situational.

---

## A. Build & run NerdCommand (engineering)

NerdCommand is a real SaaS with tiers, billing, and "developer-ready
infrastructure (Python, JSON calendar architecture)." The whole software team applies.

| Agent | Fit | Role on NerdCommand |
|---|---|---|
| `super-developer` | 🟢 | Lead orchestrator for any NerdCommand feature/build — the entry point |
| `ai-engineer` | 🟢 | **Core.** The 5,000+ "AI tools/agents" — prompt pipelines, RAG, model routing, evals, agent integration |
| `backend-architect` | 🟢 | APIs, subscription/billing tiers, tool-orchestration services, shared knowledge bases |
| `software-architect` | 🟢 | System design for a multi-tenant, multi-tier platform; agent-execution architecture |
| `frontend-developer` | 🟢 | The "command center" dashboard, tool catalog, content-pack UI |
| `senior-developer` | 🟢 | Polished full-stack build-out of high-value creator-facing surfaces |
| `devops-automator` | 🟢 | CI/CD, containerized tool execution, campaign-automation infra |
| `database-optimizer` | 🟢 | Content/asset storage, per-tenant data, usage metering at scale |
| `sre` | 🟡 | Reliability/SLOs once there's real traffic across tiers |
| `code-reviewer` | 🟢 | Quality gate on every change before it ships |
| `rapid-prototyper` | 🟢 | Spin up new "tools" as fast MVPs to test demand |
| `git-workflow-master` | 🟡 | Clean history / PR flow as the team grows |
| `technical-writer` | 🟢 | Tool docs, API docs, onboarding for creators/agencies |

**Takeaway:** every engineering agent has a clear job here; `ai-engineer` and
`backend-architect` are the load-bearing ones for the platform's core promise.

---

## B. Ship as product — bundled agents customers use

This is where the roster becomes **inventory you can sell**. NerdCommand's pillars
map almost 1:1 onto the marketing/media agents. Each becomes a "tool/agent" in the
catalog.

| Agent | Fit | NerdCommand pillar | Sold to |
|---|---|---|---|
| `content-creator` | 🟢 | Writing / multi-format | Creator, Team, Agency |
| `social-media-strategist` | 🟢 | Automation / agents (campaign brain) | Team, Agency |
| `short-video-creator` | 🟢 | **Video** | Creator, Team, Agency |
| `long-form-video-creator` | 🟢 | **Video** | Creator, Team, Agency |
| `livestream-commerce-strategist` | 🟢 | Video / commerce | Team, Agency |
| `podcast-strategist` | 🟢 | **Audio / voice** | Creator, Team, Agency |
| `book-co-author` | 🟢 | **Writing** (long-form) | Creator |
| `email-strategist` | 🟢 | Writing / automation | Team, Agency |
| `seo-specialist` | 🟢 | **Research** / writing | Team, Agency |
| `tiktok-strategist` | 🟢 | Video / social | Creator, Team |
| `instagram-curator` | 🟢 | Images / social | Creator, Team |
| `twitter-engager` | 🟢 | Writing / social | Creator, Team |
| `linkedin-content-creator` | 🟢 | Writing / social (B2B) | Team, Agency |
| `reddit-community-builder` | 🟡 | Social / community | Creator, Team |
| `pr-communications-manager` | 🟡 | Writing / comms | Agency |
| `app-store-optimizer` | 🟡 | Research / writing (niche) | Team, Agency |

**Takeaway:** 16 ready-to-bundle agents already cover the **writing, video, audio,
and social** pillars — enough to seed the "daily content pack" and "52 weekly
campaign themes" engine. `social-media-strategist` is the natural **orchestrator**
that turns the others into an automated campaign (mirrors `super-developer` on the
content side).

---

## C. Grow NerdCommand's own business (dual-use)

The same agents you sell, you also run internally for GTM:

- `growth-hacker` 🟢 — acquisition loops, referral, funnel for the subscription
- `seo-specialist` 🟢 — rank "AI tools / AI command center" search intent
- `content-creator` + `social-media-strategist` 🟢 — market NerdCommand with NerdCommand (great proof-of-product / dogfooding story)
- `pr-communications-manager` 🟡 — launch announcements, positioning
- `email-strategist` 🟢 — trial→paid lifecycle across tiers

---

## Pillar coverage — gaps now filled ✅

The image/voice/research/orchestration gaps have been wired in. NerdCommand now
has **full pillar coverage**:

| Pillar | Status | Covering agents |
|---|---|---|
| Video | ✅ | `short-video-creator`, `long-form-video-creator`, `livestream-commerce-strategist` |
| **Images** | ✅ (new) | `image-prompt-engineer`, `visual-storyteller`, `brand-guardian` |
| Audio | ✅ | `podcast-strategist` |
| **Voice** | ✅ (new) | `voice-ai-integration-engineer` |
| Agents | ✅ | `ai-engineer`, `prompt-engineer` (new), `multi-agent-systems-architect` (new) |
| Writing | ✅ | `content-creator`, `book-co-author`, `email-strategist`, platform social agents |
| **Research** | ✅ (new) | `statistician`, `seo-specialist`; `investment-researcher` for finance |
| Automation | ✅ | `social-media-strategist`, `devops-automator`, `super-developer` |

Bonus: `investment-researcher` covers **stock-market / investment research** — a
NerdCommand vertical beyond the eight core pillars (research/analysis only, not
licensed financial advice).

---

## Recommended next moves

1. **Keep the whole engineering team** — it builds and runs the platform (Lens A).
2. **Treat the media/marketing/design agents as launch inventory** (Lens B) and
   wire `social-media-strategist` as the campaign orchestrator, with
   `multi-agent-systems-architect` designing how the catalog agents coordinate.
3. **Gaps are filled** — every advertised pillar (video, images, audio, voice,
   agents, writing, research, automation) now has at least one agent.
4. **Dogfood** — run NerdCommand's own marketing through these agents (Lens C) as
   living proof the product works.
