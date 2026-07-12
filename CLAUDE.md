# Project guidance for Cowork / Claude Code

## Software development workflow

This repo ships a team of software-engineering subagents in `.claude/agents/`,
led by an orchestrator.

**For any non-trivial engineering task** (building a feature, service, or app;
fixing a hard bug; a multi-step change), route the work through the
**`super-developer`** agent. It plans the work, delegates each phase to the
right specialist, integrates the results, and drives the change to
built-run-reviewed done.

For small, single-domain tasks you may invoke a specialist directly:
`software-architect`, `backend-architect`, `frontend-developer`,
`senior-developer`, `database-optimizer`, `ai-engineer`, `devops-automator`,
`sre`, `rapid-prototyper`, `code-reviewer`, `git-workflow-master`,
`technical-writer`.

See `.claude/agents/README.md` for the full map and design notes.
