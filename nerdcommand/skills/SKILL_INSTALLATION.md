# nerdcommand-system-design Skill Installation

## What This Skill Does

**System design architect for all NERDCOMMAND divisions.**

Provides 4 domain templates:
- **Trading**: 4 strategies, micro-lots, triangle entries, unified stops, 3-trade scalps, capital preservation
- **Studios**: AI film production pipeline with skill handoffs
- **Podcast**: Content distribution + monetization
- **Prompt Engineering**: Multi-model orchestration and A/B testing

---

## Installation (One-Time Setup)

### Option 1: Download from Repository (Recommended)

```bash
# Clone or pull the repository
git clone https://github.com/[owner]/https-github.com-openclaw-openclaw.git
cd nerdcommand/skills/
```

Then follow Option 2 below.

### Option 2: Upload to Claude.ai

1. **Download the skill file** from repository:
   - Location: `nerdcommand/skills/nerdcommand-system-design.skill`
   - Size: 22 KB

2. **Go to Claude.ai**
   - Settings → Features (or Preferences)
   - Skills → Custom Skills
   - Click "Add Skill" or "Upload"

3. **Select the file**
   - Choose `nerdcommand-system-design.skill`
   - Click "Import" or "Install"

4. **Verify Installation**
   - Skill appears in your Skills list as "nerdcommand-system-design"
   - Status: Active

---

## Usage

The skill activates automatically when you:

- Ask: "Design architecture for [X]"
- Ask: "How should we build [X]"
- Ask: "What's the system design for [X]"
- Mention: "Design infrastructure for [X]"
- Describe a bottleneck or architecture problem

### Example Prompts

**Trading:**
```
Design a trading system for $500 starting capital with <$50/month costs.
Use the nerdcommand-system-design skill to provide the architecture.
```

**Studios:**
```
Design an AI film production pipeline from script to final edit.
```

**Podcast:**
```
Design a podcast distribution system with paywall monetization.
```

---

## What You Get When Triggered

The skill will automatically provide:

1. **Quick Summary** — one-paragraph overview of the architecture
2. **Core Components** — all critical pieces with 2-3 sentence descriptions
3. **Implementation Timeline** — week-by-week or phase-by-phase roadmap
4. **Tech Stack** — recommended tools and costs
5. **Decision Trees** — when to choose A vs B
6. **Failure Modes** — what can go wrong and how to recover
7. **Success Metrics** — how to measure if it's working
8. **Integration Points** — where other NERDCOMMAND skills hand off

---

## Trading Template (Locked In)

### 4 Strategies
| Strategy | Entry | Exit | Win Rate | Confidence |
|----------|-------|------|----------|-----------|
| Breakout | Price > 20-day high | Close < 50-day MA | 50-55% | 1.0x |
| Stat Arb | Pair correlation > 2σ | Spread < 1σ | 55-60% | 1.2x |
| Mean Reversion | RSI < 30 or > 70 | RSI cross 50 | 48-52% | 0.8x |
| Pairs | Spread diverges > 2σ | Spread < 1σ | 52-58% | 1.1x |

### Core Rules
- **Position Sizing**: 0.01 / 0.04 / 0.07 lots (confidence-based)
- **Triangle Entry**: Accumulate gradually (0.01 → +0.03 → +0.03)
- **Unified Stop**: Entry ± (ATR-14 × 2)
- **3-Trade Scalp**: Exit after 3 wins per setup
- **Daily Limits**: +$10 target, -$5 stop (capital first)
- **Timeline**: 6 weeks paper → live ($100-500)

### Expected Returns
- Conservative (10% monthly): $500 → $1,600 in 12 months
- Aggressive (20% monthly): $500 → $3,100+ in 12 months

---

## File Structure

```
nerdcommand/skills/
├── nerdcommand-system-design.skill    ← Upload this to Claude.ai
├── SKILL_INSTALLATION.md              ← This file
├── TRADING_COMPACT.md                 ← Quick reference (print & tape to monitor)
└── TRADING_ARCHITECTURE.md            ← Deep dive (13KB, full specs)
```

---

## Support & Customization

### Ask the Skill To:
- "Adapt this for $1000 starting capital"
- "What if we use [different broker]?"
- "How does this change if we add [this constraint]?"
- "What are the failure modes for [component]?"
- "How do we scale from $500 to $5000?"

### If You Get Stuck:
1. Ask in a new conversation: "I'm building [system]. Use system design skill to review."
2. Share your current architecture
3. Skill will provide gap analysis and recommendations

---

## Troubleshooting

### Skill Not Appearing
- **Check**: Settings → Features → Skills (should list "nerdcommand-system-design")
- **Restart**: Refresh the browser or restart Claude.ai
- **Re-upload**: Download skill again and re-import if corrupted

### Skill Not Triggering
- **Ensure**: You're in a conversation (not just settings)
- **Be explicit**: Say "Use the nerdcommand-system-design skill" in your prompt
- **Check context**: Skill triggers on architecture/design questions, not general coding

### Skill Gives Generic Answers
- **Provide context**: Share current constraints, capital, timeline, tech stack
- **Be specific**: "Design for micro-lot Forex trading" vs just "design trading"
- **Ask follow-ups**: "What's the first 2 weeks?" or "What could fail here?"

---

## What's Inside the .skill File

The skill is a packaged knowledge base (`.skill` is a ZIP archive) containing:

```
nerdcommand-system-design/
├── SKILL.md (1,292 lines)
│   ├── Quick Start Framework
│   ├── Template 1: Trading (4 strategies, detailed specs)
│   ├── Template 2: Studios (AI film pipeline)
│   ├── Template 3: Podcast (content + monetization)
│   ├── Template 4: Prompt Engineering (multi-model)
│   ├── Component Deep Dives (caching, DBs, load balancing, etc.)
│   ├── Decision Trees (build vs buy, scaling)
│   ├── Integration Guide (skill handoffs)
│   └── Glossary & Reference
│
└── test-cases.json (7 validation test scenarios)
```

---

## Next Steps

### Immediate
1. ✅ Install skill (this doc)
2. ⬜ Review TRADING_COMPACT.md (2-page quick ref)
3. ⬜ Ask skill in a conversation: "Design a trading system from the NERDCOMMAND template"

### For Trading Build
1. ⬜ Open Interactive Brokers account
2. ⬜ Test market data API
3. ⬜ Code Strategy #1 (Breakout, 20-day high)
4. ⬜ Backtest 6 months
5. ⬜ Paper trade 1 week
6. ⬜ Go live with $100-500

### For Studios / Podcast / Prompt Eng
- Use skill to design architecture
- Hand off to relevant NERDCOMMAND skills:
  - `nerdcommand-writer` (scripts)
  - `artlist-cinematic-director` (visuals)
  - `banana-pro-director` (renders)
  - `stripe-integration` (payments)

---

## Key Principle

**This skill is your architecture thinking partner.**

It doesn't write code or execute—it designs the blueprint. Use it to:
1. Clarify what you're building
2. Identify critical components
3. Plan the roadmap
4. Flag failure modes
5. Set success metrics

Then execute the plan with code or delegation.

---

## Questions?

Ask the skill directly in any conversation. It's built to handle follow-ups and adaptations.

**Ready to use immediately after installation.** 🚀

---

**Last updated**: June 5, 2026  
**Skill version**: 1.0 (Trading architecture finalized)  
**Repository**: [https-github.com-openclaw-openclaw](https://github.com/chapmancapital1-droid/https-github.com-openclaw-openclaw)
