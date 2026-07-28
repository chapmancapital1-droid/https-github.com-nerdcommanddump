# NERDCOMMAND System Design Skill

**Version**: 1.0  
**Owner**: NERDCOMMAND — GangsterNerds LLC  
**Divisions**: Trading · Studios · Podcast · Prompt Engineering

---

## Activation Triggers

This skill activates automatically when you say:
- "Design architecture for…"
- "How do we build…"
- "System design for…"
- "Design a trading system / film pipeline / podcast / prompt engine"
- Or describe a bottleneck, scaling problem, or infrastructure question

---

## Quick Start: 5-Question Framework

Before designing anything, answer these 5 questions:

1. **Who uses it?** — Solo operator, small team, or external users?
2. **What scale?** — 10 requests/day or 10,000?
3. **What budget?** — $0, <$50/mo, <$500/mo?
4. **What's the failure cost?** — Lost trade? Missed episode? Broken render?
5. **What exists already?** — Don't rebuild what's working.

These answers determine which template applies and how much infrastructure you need.

---

## Routing Map

```
User request
  │
  ├─ "trading / signals / capital / strategy"
  │     └─ Template 1: Trading  →  micro-lot framework (nerdcommand/micro-lot/)
  │
  ├─ "film / video / AI production / render / character"
  │     └─ Template 2: Studios  →  nerdcommand-writer + artlist-cinematic-director
  │                                + banana-pro-director + nerdcommand-character-consistency
  │
  ├─ "podcast / audio / episodes / listeners / monetize"
  │     └─ Template 3: Podcast  →  stripe-integration (for subscriptions)
  │
  └─ "prompts / AI generation / model routing / batch"
        └─ Template 4: Prompt Engineering  →  banana-pro-director
```

---

## Template 1: NERDCOMMAND Trading

### Philosophy
Capital preservation first. Growth second. Start from $100-500, compound to $3000+ over 12 months using micro-lots (0.01-0.07). Never risk what you can't afford to lose twice in a row.

### The 4 Strategies

| Strategy | Entry | Exit | Win Rate | Conf Weight |
|----------|-------|------|----------|-------------|
| Breakout Trader | Price > 20-day high / < 20-day low | Close below 50-day MA | 50-55% | 1.0× |
| Statistical Arbitrage | Pair z-score > +2σ or < -2σ | \|z\| < 1σ | 55-60% | 1.2× |
| Crypto Mean Reversion | RSI(14) < 30 (buy) / > 70 (sell) | RSI crosses 50 | 48-52% | 0.8× |
| Pairs Trading | Spread > 2σ (long under / short over) | Spread < 1σ | 52-58% | 1.1× |

### Signal Fusion (Position Sizing)

```
Collect active signals from all 4 strategies
→ Sum confidence weights for agreeing direction
→ Confidence ≤ 0.8  → SKIP (single weak signal)
→ Confidence ≥ 1.8  → 0.04 lots (2 strategies agree)
→ Confidence ≥ 3.0  → 0.07 lots (3+ strategies agree)
```

### Triangle Entry (Risk Management)

```
Step 1: Open 0.01 lots at signal
Step 2: If +20 pips favorable → add 0.03 lots (total 0.04)
Step 3: If +40 pips favorable → add 0.03 lots (total 0.07)

RULE: If stop hit at ANY step → close ALL, no averaging down
```

### Unified Dynamic Stop Loss

```
Stop = Entry ± (ATR-14 × 2)
Trail UP only (never moves against position)
One stop for ALL lots — no per-strategy stops
Stop hit → CLOSE ENTIRE POSITION, no exceptions
```

### 3-Trade Scalp Exit

```
Count winning trades in session
After 3 wins → CLOSE ALL, stand down
Reason: locks profit, prevents reversal from giving it back
```

### Daily P&L Limits

```
Daily target: +$10 (2% of $500) → reduce risk or stop for day
Daily max loss: -$5 (1% of $500) → STOP TRADING immediately
```

### Architecture Diagram

```
yfinance / IB API
       │
       ▼
  data_feed.py (OHLCV bars)
       │
       ├──► breakout.py       ─┐
       ├──► mean_reversion.py  ├──► fusion.py ──► fused_signal (direction, lots)
       ├──► stat_arb.py        │                       │
       └──► pairs_trading.py  ─┘                       ▼
                                                   risk.py
                                                  (triangle entry
                                                   ATR stop
                                                   daily limits)
                                                       │
                                                       ▼
                                              position_tracker.py
                                                (SQLite log)
                                                       │
                                                       ▼
                                                   main.py
                                               (5-min loop)
```

### NCI Integration (MT4 EA Bridge)

```
MT4 EA (NCI_GodMode_v3_2_Fusion.mq4)
       │  writes every bar
       ├──► NCI_LiveData.json       (balance, equity, ABC stage, ADX, FER)
       └──► signal_proposal.json   (symbol, action, score, qualifies)
                    │
                    ▼
            nci_live.py (polls)
                    │
                    ▼
        nci_signal_approval.py ──► LLM (Ollama or llama-cpp)
                    │                   APPROVE / REJECT
                    ▼
            signals/approvals.jsonl (audit log)
```

### Tech Stack

| Component | Technology | Cost |
|-----------|-----------|------|
| Market data | yfinance (default) / IB API | $0 / $10/mo |
| Trading engine | Python + numpy | $0 |
| MT4 EA | NCI_GodMode_v3_2_Fusion.mq4 | already built |
| LLM second opinion | Ollama (qwen2.5-coder:7b) / llama-cpp | $0 |
| Trade log | SQLite | $0 |
| **Total** | | **<$10/mo** |

### Implementation Files

```
nerdcommand/
├── trading-brain/
│   └── nci/
│       ├── config.py               # env-var settings
│       ├── nci_live.py             # MT4 JSON reader
│       ├── nci_signal_approval.py  # LLM approval loop
│       ├── nci_agent.py            # Ollama/llama-cpp router
│       ├── nci_agent_ollama.py     # Ollama backend
│       ├── nci_agent_local.py      # llama-cpp backend
│       ├── benchmark.py            # latency tester
│       └── analysis/
│           └── loss_pattern.py     # loss cross-tab analyzer
└── micro-lot/
    ├── config.py
    ├── strategies/
    │   ├── breakout.py
    │   ├── mean_reversion.py
    │   ├── stat_arb.py
    │   └── pairs_trading.py
    ├── fusion.py
    ├── risk.py
    ├── position_tracker.py
    ├── data_feed.py
    ├── main.py
    └── backtest.py
```

### Expected Returns

| Scenario | Monthly | Month 12 |
|----------|---------|---------|
| Conservative (10%) | +$50 | $500 → $1,600 |
| Realistic (15%) | +$75 | $500 → $2,400 |
| Aggressive (20%) | +$100 | $500 → $3,100+ |

### Failure Modes & Recovery

| Failure | Cause | Recovery |
|---------|-------|---------|
| Daily -$5 hit | Bad setup / wrong regime | Stop. Reset tomorrow. |
| Ollama model wrong | keep_alive expired | Set `OLLAMA_KEEP_ALIVE=2h` system env |
| Strategy fires opposite signals | Market regime change | Reduce to single-strategy mode |
| Data feed down | yfinance rate-limit | Switch to IB: `DATA_PROVIDER=ib` |
| Position stuck open | MT4 connection lost | Manual close in MT4, reconcile in SQLite |

---

## Template 2: NERDCOMMAND Studios

### Use Case
AI-powered film/video production pipeline from script concept to final render, with consistent character visuals across shots.

### Architecture

```
Concept / Brief
      │
      ▼
nerdcommand-writer ──────────── Script generation + scene breakdown
      │                          Character bibles, dialogue, shot lists
      ▼
artlist-cinematic-director ───── Visual style direction
      │                          Mood boards, color palettes, camera angles
      ▼
nerdcommand-character-consistency ─── Lock character visuals
      │                               Face/costume embeddings, LoRA references
      ▼
banana-pro-director ─────────── Batch prompt generation + render orchestration
      │                          Sends to image/video model APIs
      ▼
Output Assets
  ├── Storyboard frames
  ├── Character renders (consistent)
  ├── Scene backgrounds
  └── Final video assembly
```

### Component Deep Dive

**nerdcommand-writer**
- Input: concept, genre, target length, tone
- Output: script with act structure, scene descriptions, character dialogue
- Handoff: scene list → artlist-cinematic-director

**artlist-cinematic-director**
- Input: scene descriptions from script
- Output: shot-by-shot visual prompts (angle, lighting, mood, style)
- Decision: cinematic style (noir, sci-fi, documentary, anime, etc.)

**nerdcommand-character-consistency**
- Input: character bible + reference images
- Output: locked visual embeddings / LoRA weights
- Critical: ensures the same character looks identical across 50+ shots
- Technique: negative prompting + seed locking + LoRA fine-tune

**banana-pro-director**
- Input: visual prompts + character embeddings
- Output: rendered images/video frames via API (Stable Diffusion, Runway, etc.)
- Handles: batch queuing, retry logic, upscaling, frame assembly

### Production Pipeline

```
Week 1: Script + Characters
  - nerdcommand-writer: script v1
  - nerdcommand-character-consistency: lock 2-3 main characters

Week 2: Visual Development
  - artlist-cinematic-director: style guide + shot list
  - Test renders for each scene type

Week 3-4: Full Render
  - banana-pro-director: batch all shots
  - QA: character consistency check per scene

Week 5: Assembly
  - Import frames into editing software
  - Add audio, music, titles
  - Export final cut
```

### Tech Stack

| Component | Technology | Cost |
|-----------|-----------|------|
| Script generation | nerdcommand-writer skill | $0 |
| Visual direction | artlist-cinematic-director skill | $0 |
| Character locking | nerdcommand-character-consistency skill | $0 |
| Render orchestration | banana-pro-director skill | $0 |
| Image generation | Stable Diffusion API / Runway / Midjourney | $20-100/project |
| Video assembly | DaVinci Resolve (free) / Premiere | $0 / $55/mo |
| **Total per short film** | | **$20-150** |

### Failure Modes & Recovery

| Failure | Cause | Recovery |
|---------|-------|---------|
| Character looks different | Embedding drift | Re-run nerdcommand-character-consistency lock step |
| Style inconsistent across scenes | Different prompts | Apply artlist style prefix to every prompt |
| Render batch fails | API quota | Stagger requests, use retry logic in banana-pro |
| Script is generic | Weak brief | Add more specific tone/reference examples to nerdcommand-writer |

---

## Template 3: NERDCOMMAND Podcast

### Use Case
End-to-end podcast infrastructure: recording → editing → distribution → monetization → analytics.

### Architecture

```
Recording (local)
      │
      ▼
Audio Processing
  ├── Noise reduction
  ├── Level normalization
  └── Intro/outro insertion
      │
      ▼
Content Metadata
  ├── Episode title, description, chapters
  ├── Show notes (AI-generated summary)
  └── Transcript (Whisper / Deepgram)
      │
      ├──► Free distribution: Spotify / Apple / RSS
      │
      └──► Paid tier: stripe-integration
               ├── Subscription plans ($5/$10/$20 per month)
               ├── Early access episodes
               ├── Bonus content paywall
               └── Member-only Discord/community gate
```

### Monetization Tiers (via stripe-integration)

| Tier | Price | Content |
|------|-------|---------|
| Free | $0 | Public episodes (1-week delay) |
| Supporter | $5/mo | Ad-free + early access |
| Member | $10/mo | Bonus episodes + Discord |
| Founding | $20/mo | 1-on-1 access + everything |

### Distribution Checklist

```
□ RSS feed (Buzzsprout / Anchor / self-hosted)
□ Spotify for Podcasters
□ Apple Podcasts Connect
□ YouTube (audiogram / full video)
□ Transcript page (SEO)
□ Newsletter (Substack / ConvertKit) — episode summary
□ Stripe webhook → member gate (stripe-integration skill)
```

### Analytics Stack (zero cost)

```
Buzzsprout / Anchor stats → Episode downloads, listener location
Spotify for Podcasters → Streaming plays
YouTube Analytics → Views, watch time
Stripe Dashboard → MRR, churn, subscriber growth
```

### Content Calendar (minimum viable)

```
Weekly cadence:
  Monday:   Record episode
  Tuesday:  Edit + transcribe
  Wednesday: Write show notes + schedule
  Thursday: Publish (members early access)
  Friday:   Public release + social clips
```

### Tech Stack

| Component | Technology | Cost |
|-----------|-----------|------|
| Recording | Riverside / Zencastr / Audacity | $0-15/mo |
| Audio editing | Descript / Audacity | $0-24/mo |
| Transcription | Whisper (local) / Deepgram | $0 / $0.01/min |
| Hosting + RSS | Buzzsprout / Anchor | $0-12/mo |
| Monetization | stripe-integration skill + Stripe | 2.9% + $0.30 |
| **Total** | | **$0-50/mo** |

### Failure Modes & Recovery

| Failure | Cause | Recovery |
|---------|-------|---------|
| Low downloads | Bad title/thumbnail | A/B test titles, improve SEO on transcript page |
| No paid conversions | Free content too good | Move best episodes to member tier |
| Stripe webhook fails | Endpoint down | Retry queue + manual member audit monthly |
| Recording quality bad | Mic/room issues | Use Descript Studio Sound, add acoustic foam |

---

## Template 4: NERDCOMMAND Prompt Engineering

### Use Case
Multi-model AI prompt orchestration: generate, test, batch, A/B, and store prompts for consistent asset generation across all divisions.

### Architecture

```
Intent / Brief
      │
      ▼
Prompt Generator
  ├── Base template (style, quality, negative)
  ├── Variable injection (character name, scene, mood)
  └── Model-specific formatting (SD, Midjourney, DALL-E, Runway)
      │
      ▼
Model Router ─────── banana-pro-director (orchestration)
  ├──► Stable Diffusion (local or API) — fastest, most control
  ├──► Midjourney — best aesthetics, slower
  ├──► DALL-E 3 — best text rendering
  └──► Runway / Pika — video generation
      │
      ▼
A/B Tester
  ├── Generate N variants per prompt
  ├── Score: aesthetic, accuracy, consistency
  └── Lock winner → prompt library
      │
      ▼
Asset Library (versioned)
  ├── prompts.json (prompt → model → settings → output)
  ├── winners/ (best output per category)
  └── character_locks/ (consistent character prompts)
```

### Prompt Template Structure

```json
{
  "id": "char_hero_portrait_v3",
  "intent": "hero character portrait",
  "positive": "{character_name}, {style_prefix}, detailed face, dramatic lighting, {quality_suffix}",
  "negative": "blurry, deformed, extra limbs, watermark",
  "model": "stable-diffusion-xl",
  "settings": {
    "steps": 30,
    "cfg_scale": 7.5,
    "seed": 42
  },
  "variants_tested": 12,
  "winner": true,
  "locked": true
}
```

### Model Selection Decision Tree

```
Need text in image?          → DALL-E 3
Need video?                  → Runway Gen-3 / Pika
Need character consistency?  → SD + LoRA (nerdcommand-character-consistency)
Need fastest iteration?      → SD local (AUTOMATIC1111 / ComfyUI)
Need best aesthetics?        → Midjourney
Need cheapest batch?         → SD API (Replicate $0.0023/run)
```

### A/B Testing Process

```
1. Write 3-5 prompt variants for same intent
2. Generate 4 outputs per variant (different seeds)
3. Score each: composition (1-5), accuracy (1-5), consistency (1-5)
4. Pick winner, lock seed + settings
5. Save to prompt library with version number
6. Never change a locked prompt — create v2 instead
```

### Batch Processing Pipeline

```python
# banana-pro-director handles this pattern:
tasks = [
  { "prompt": render_template(p, vars), "model": p["model"], ...}
  for p in prompt_library
  for vars in scene_variables
]
# Queue → API → collect → store → QA
```

### Tech Stack

| Component | Technology | Cost |
|-----------|-----------|------|
| Prompt generation | This skill + nerdcommand-writer | $0 |
| Orchestration | banana-pro-director skill | $0 |
| Image generation | SD local / Replicate | $0 / $0.002/run |
| Video generation | Runway API | $0.05/sec |
| Prompt library | Git repo (JSON files) | $0 |
| A/B scoring | Manual / Claude review | $0 |
| **Total** | | **$0-50/project** |

### Failure Modes & Recovery

| Failure | Cause | Recovery |
|---------|-------|---------|
| Inconsistent outputs | Prompts drifting | Lock seed + use negative prompts |
| Wrong model for job | No routing logic | Use decision tree above explicitly |
| API rate limit | Too many concurrent | Queue with 1s delay between requests |
| Prompt library bloat | Too many versions | Archive unused, keep <50 active |

---

## Component Deep Dives

### Caching Strategy

```
When to cache:
  - Same prompt + same model → cache output for 24h
  - Market data → cache for 5 minutes (trading)
  - LLM responses to same signal → cache for 1 bar

When NOT to cache:
  - Live trade signals (always fresh)
  - RSI/ATR calculations (need latest bar)
  - Stripe webhook events (always process)
```

### Database Selection

| Need | Use | Why |
|------|-----|-----|
| Trade log (append only) | SQLite | Simple, no server, portable |
| Episode metadata | SQLite or JSON files | Low volume |
| Prompt library | JSON in git | Versioned, diffable |
| User subscriptions | Stripe (built-in) | Don't build your own |
| Analytics | Spreadsheet / Grafana | Don't over-engineer |

### Load Balancing (When You Need It)

```
< 100 users:    Single process, no load balancer
100-1K users:   Nginx + 2 app instances
1K-10K users:   AWS ALB + auto-scaling group
> 10K users:    You have revenue — hire someone
```

### Disaster Recovery

```
Trading:
  - Daily: commit trades.db to git
  - Weekly: export CSV from SQLite
  - MT4 backup: sync files to cloud storage

Studios:
  - Renders: cloud storage (Backblaze B2, $6/TB)
  - Scripts: git repo
  - Character locks: git repo (embeddings as files)

Podcast:
  - Audio masters: Backblaze B2
  - Transcripts: git repo
  - Stripe: Stripe handles its own backup
```

---

## Integration Guide

### How Skills Hand Off

```
System Design Skill (this one)
  │
  │  "I need a trading system"
  ├──► Trading template → implement using nerdcommand/micro-lot/ code
  │
  │  "I need a film pipeline"
  ├──► Studios template → invoke nerdcommand-writer first
  │        └─► nerdcommand-writer produces script
  │        └─► artlist-cinematic-director produces visual briefs
  │        └─► nerdcommand-character-consistency locks characters
  │        └─► banana-pro-director orchestrates renders
  │
  │  "I need podcast monetization"
  ├──► Podcast template → invoke stripe-integration for paywall
  │        └─► stripe-integration sets up subscription tiers
  │        └─► webhook gates content access
  │
  │  "I need a prompt library"
  └──► Prompt Engineering template → invoke banana-pro-director
           └─► banana-pro-director handles batch + routing
```

### Cross-Division Shared Components

| Component | Used by | Implementation |
|-----------|---------|---------------|
| Stripe payments | Podcast (subscriptions), Studios (commissions) | stripe-integration skill |
| LLM generation | Trading (NCI brain), Studios (scripts), Prompt Eng | Ollama / llama-cpp |
| SQLite logging | Trading (trades), Podcast (analytics), all | built-in Python |
| Git versioning | All divisions | standard git workflow |

### Handoff Protocol

When handing off to another skill, always pass:
1. **Context**: what's already been decided
2. **Constraints**: budget, timeline, existing tech
3. **Output format**: what you need back (code, prompts, plan, etc.)

Example handoff to nerdcommand-writer:
```
Context: NERDCOMMAND Studios, sci-fi short film, 5 minutes
Constraints: $50 render budget, Stable Diffusion XL only
Characters: 2 (hero, villain) — locked visuals needed
Output: Script with scene breakdown + character bible
```

---

## Decision Trees

### Should I Build This?

```
Is there an existing tool that does 80% of this?
  YES → Use the existing tool, don't build
  NO  → Continue

Will this earn money or save money in 30 days?
  NO  → Defer, not now
  YES → Continue

Can 1 person maintain it?
  NO  → Simplify until yes
  YES → Build it
```

### Which Template?

```
Does it involve money / trades / signals?  → Template 1: Trading
Does it involve video / images / renders?  → Template 2: Studios
Does it involve audio / episodes / fans?   → Template 3: Podcast
Does it involve AI prompts / generation?   → Template 4: Prompt Engineering
More than one division?  → Use multiple templates, route via Integration Guide
```

### How Much Infrastructure?

```
Users < 5 (just you)?      → Single script, SQLite, no server
Users 5-50?                → Simple web app, SQLite or Postgres, 1 server
Users 50-500?              → Proper web app, managed DB, basic monitoring
Users > 500?               → Hire someone, you can afford it
```

---

## Success Metrics

### Trading
- Win rate > 50% across all strategies
- Monthly P&L > +$50 (10% on $500)
- Max daily drawdown < $5
- Zero blown accounts

### Studios
- Project delivery in < 5 weeks per short
- Character consistency score > 90% across shots
- Render cost < $150 per project
- Zero lost assets (everything in git + cloud)

### Podcast
- 100 downloads per episode (month 3)
- 10 paying subscribers (month 3)
- 1 episode shipped per week consistently
- MRR > $100 (month 6)

### Prompt Engineering
- Prompt library: < 50 active prompts
- A/B winner rate > 70% (locked prompts stay good)
- Generation cost < $0.10 per final asset
- Zero repeated work (everything is reusable)

---

## Appendix: Quick Reference Cards

### Trading Quick Ref

```
ENTRY  → Signal from 2+ strategies, confidence ≥ 1.8
SIZE   → 0.04 (med) or 0.07 (high conf)
TRIANGLE → 0.01 → +0.03 → +0.03 on +20 pip moves
STOP   → Entry ± ATR×2, trail in winning direction only
EXIT   → 3 scalps OR stop hit OR strategy exit signal
DAILY  → Stop at -$5 loss / +$10 target
```

### Studios Quick Ref

```
SCRIPT → nerdcommand-writer (concept + constraints)
STYLE  → artlist-cinematic-director (scene prompts)
CHARS  → nerdcommand-character-consistency (lock visuals)
RENDER → banana-pro-director (batch API calls)
QA     → Character consistency check every 10 shots
```

### Podcast Quick Ref

```
RECORD  → Monday
EDIT    → Tuesday (Descript / Audacity)
PUBLISH → Thursday (members) / Friday (public)
MONEY   → stripe-integration skill → $5/$10/$20 tiers
GROW    → YouTube audiograms + newsletter + transcript SEO
```

### Prompt Engineering Quick Ref

```
GENERATE → Write 3-5 variants per intent
TEST     → 4 outputs per variant
SCORE    → Composition + Accuracy + Consistency (1-5 each)
LOCK     → Winner gets fixed seed + saved to library
VERSION  → Never modify locked prompts — make v2
```
