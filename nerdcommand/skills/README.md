# NERDCOMMAND Skills

Custom Claude.ai skills for all NERDCOMMAND divisions.

## Available Skills

### `nerdcommand-system-design.skill`

**Architecture thinking framework for all divisions.**

Upload `nerdcommand-system-design.skill` to Claude.ai:
> Settings → Skills → Custom → Add Skill → Upload file

#### What's inside

| File | Contents |
|------|---------|
| `SKILL.md` | Full skill — 4 templates, decision trees, integration guide, failure modes |
| `test-cases.json` | 7 test scenarios to validate skill behavior |

#### Templates

| Template | Division | Triggers |
|----------|---------|---------|
| 1: Trading | NCI / Micro-Lot framework | "trading", "signals", "strategy", "capital" |
| 2: Studios | AI film production | "film", "render", "character", "AI video" |
| 3: Podcast | Content + monetization | "podcast", "episodes", "listeners", "monetize" |
| 4: Prompt Engineering | Multi-model AI generation | "prompts", "generation", "model routing", "batch" |

#### Routing Map

```
"Design trading system"       → Template 1 + micro-lot/ code
"Design film production"      → Template 2 + nerdcommand-writer + artlist-cinematic-director
                                           + banana-pro-director + nerdcommand-character-consistency
"Design podcast infrastructure" → Template 3 + stripe-integration
"Design prompt generation"    → Template 4 + banana-pro-director
```

#### How to install

1. Download `nerdcommand-system-design.skill` from this folder
2. Go to [claude.ai](https://claude.ai) → Settings → Skills → Custom
3. Click "Add Skill" → Upload the `.skill` file
4. Skill activates automatically in all conversations

#### How to use

Just describe what you need to build:

```
"Design architecture for a trading system starting with $500"
"How do we build an AI film pipeline on a $150 budget?"
"System design for podcast monetization with Stripe"
"We have a bottleneck in our prompt generation pipeline"
```

The skill will:
1. Route to the right template
2. Apply the 5-question quick-start framework
3. Return architecture diagram + component breakdown + tech stack + failure modes

---

## Adding More Skills

Place new skill directories here following the same pattern:
```
nerdcommand/skills/
├── nerdcommand-system-design/      # source files
│   ├── SKILL.md
│   └── test-cases.json
├── nerdcommand-system-design.skill # packaged (zip)
└── README.md                       # this file
```

To repackage after edits:
```bash
cd nerdcommand/skills
zip -r nerdcommand-system-design.skill nerdcommand-system-design/
```
