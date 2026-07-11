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
