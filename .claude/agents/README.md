# Super Developer — agent team for Cowork / Claude Code

A "super agent software developer": one orchestrator that plans and delegates,
plus a curated team of specialist subagents. Adapted from the
[agency-agents](https://github.com/msitarzewski/agency-agents) engineering
division into the Claude Code / Cowork subagent format.

## How to use

Talk to Cowork (or Claude Code) in this repo and let it delegate:

> "Build a REST API for X with a React dashboard" → the main assistant hands
> off to **`super-developer`**, which plans the work and routes each phase to
> the right specialist.

Or invoke a specialist directly for a focused task:

> "Have `code-reviewer` look at my last change."
> "Ask `database-optimizer` why this query is slow."

## The team

| Agent | Model | Domain |
|---|---|---|
| **`super-developer`** | opus | **Orchestrator** — plans, delegates, integrates, ships |
| `software-architect` | opus | System design, patterns, domain modeling, ADRs |
| `backend-architect` | sonnet | APIs, services, auth, server-side logic |
| `frontend-developer` | sonnet | Components, state, responsive/accessible UI |
| `senior-developer` | sonnet | Premium full-stack features (rich UI + backend) |
| `database-optimizer` | sonnet | Schema, indexing, slow queries, scaling data |
| `ai-engineer` | opus | LLM/ML features — prompts, RAG, embeddings, evals |
| `devops-automator` | sonnet | CI/CD, Docker/K8s, IaC, deployments |
| `sre` | sonnet | Reliability, observability, incidents, hardening |
| `rapid-prototyper` | sonnet | Fast MVPs, spikes, demos |
| `code-reviewer` | opus | Correctness / security / maintainability review |
| `git-workflow-master` | sonnet | Branching, clean history, PR structure |
| `technical-writer` | sonnet | READMEs, API docs, runbooks |
| `ui-designer` | sonnet | Interface design, design systems, visual polish |
| `prompt-engineer` | opus | Craft/test/optimize LLM prompts into reliable behavior |
| `multi-agent-systems-architect` | opus | Orchestrate many agents/tools — routing, handoffs, state |
| `voice-ai-integration-engineer` | sonnet | Voice/speech AI — TTS/STT, voice cloning, audio pipelines |

## Design & visual

| Agent | Model | Domain |
|---|---|---|
| `image-prompt-engineer` | sonnet | AI image-generation prompting — ad creative, thumbnails, visuals |
| `visual-storyteller` | sonnet | Visual narrative — infographics, carousels, image-led content |
| `brand-guardian` | sonnet | Brand consistency — style guides, brand systems, asset review |

## Research & analysis

| Agent | Model | Domain |
|---|---|---|
| `statistician` | sonnet | Quantitative research, A/B design, surveys, data modeling |

## Finance desk

> All finance agents produce **educational analysis and tooling only — not
> licensed financial, tax, or investment advice.**

| Agent | Model | Domain |
|---|---|---|
| `investment-researcher` | opus | Stock/market research, due diligence, valuation |
| `options-trading-analyst` | opus | Options strategy, greeks, IV, risk/reward, options-analytics tooling (live data + news) |
| `financial-analyst` | opus | Financial modeling, forecasting, scenario analysis, valuation |
| `fpa-analyst` | sonnet | Budgeting, variance analysis, KPI/board reporting, forecasts |
| `tax-strategist` | sonnet | Tax planning and optimization, multi-jurisdictional considerations |
| `bookkeeper-controller` | sonnet | Day-to-day accounting, close, controls, reconciliations |

## Marketing & Social team

A separate crew for growth, content, and social — adapted from the source repo's
marketing division. (Not part of the software `super-developer` roster.)

| Agent | Model | Domain |
|---|---|---|
| `social-media-strategist` | sonnet | Cross-platform strategy, calendars, campaigns (lead) |
| `content-creator` | sonnet | Multi-format content: posts, captions, scripts, blogs |
| `growth-hacker` | sonnet | Viral loops, referrals, funnel & acquisition experiments |
| `seo-specialist` | sonnet | Keyword research, on-page/technical SEO, organic growth |
| `email-strategist` | sonnet | Newsletters, drip sequences, segmentation, deliverability |
| `tiktok-strategist` | sonnet | TikTok short-video hooks, trends, cadence |
| `instagram-curator` | sonnet | Feed/Reels/Stories strategy and visual curation |
| `twitter-engager` | sonnet | X/Twitter posts, threads, real-time engagement |
| `linkedin-content-creator` | sonnet | LinkedIn thought-leadership, B2B, personal brand |
| `reddit-community-builder` | sonnet | Authentic subreddit engagement and community building |
| `pr-communications-manager` | sonnet | Press releases, media outreach, crisis comms |
| `app-store-optimizer` | sonnet | ASO — titles, keywords, screenshots, store conversion |
| `book-co-author` | sonnet | Long-form/book writing — chapters, ghostwriting, voice preservation |
| `podcast-strategist` | sonnet | Podcast positioning, audience growth, monetization (Spotify/Apple/YouTube) |

### Video & livestream creators

Adapted from the source repo's video-focused agents, **translated to English and
generalized** off their original China platforms for broad use:

| Agent | Adapted from | Domain |
|---|---|---|
| `short-video-creator` | Douyin | Short-form vertical video (TikTok/Reels/Shorts) — hooks, retention, series |
| `livestream-commerce-strategist` | Kuaishou | Live-shopping — host coaching, session structure, trust-based conversion |
| `long-form-video-creator` | Bilibili | Long-form/YouTube-style video — watch-time, thumbnails/titles, community |

Other China-platform agents (WeChat, Weibo, Xiaohongshu, Zhihu, Baidu) were
intentionally left out. The China-market podcast agent was skipped in favor of
the platform-agnostic `podcast-strategist`. Add any with the same conversion
steps below.

## What was adapted from the source

Each source agent's **body was preserved**; the changes make them Cowork-native:

- **Frontmatter** rewritten to the Claude Code contract: kebab-case `name`,
  a **delegation-oriented `description`** (so the orchestrator auto-routes to
  the right one), and an explicit `model`.
- **`tools` omitted on purpose** — each subagent inherits the full Cowork
  toolset (files, bash, web, MCP servers) for maximum capability.
- The original persona `emoji` + `vibe` are preserved as a one-line note.
- Added **`super-developer`**, a new orchestrator that ties the team together.

## Extending the team

The source repo has ~49 engineering agents plus design, marketing, security,
testing, GIS, game-dev and more divisions. To add one, drop its `.md` in this
folder, convert the frontmatter to the format above, and (optionally) add it to
`super-developer`'s roster table.
