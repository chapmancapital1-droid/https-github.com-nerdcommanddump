# NCI Phase 4: Strategy Selector & Quantum AI Brain (v1.0)

**Status:** Implemented & tested (20 tests passing, demo functional)  
**Audience:** NCI dev team building Phase 4-7 integration into opiontrading dashboard  
**Purpose:** Adaptive options strategy recommendation with Claude AI reasoning and interactive learning

> Educational analysis tooling — not investment advice. Recommendations require human review and approval before execution.

---

## 1. Design Philosophy

**Adaptive + AI-powered + Learning-loop + Versioned**

Three principles guide the architecture:

1. **Adaptive Selection** — strategies chosen by multi-factor fit score (market context + user constraints), not heuristic rules
2. **Claude-backed Reasoning** — AI explains *why* each strategy fits, with confidence scores and risk context
3. **Learning Loop** — trade outcomes feed back into strategy performance scoring; knowledge is versioned and auditable

---

## 2. Architecture

```
                    User Input
                    │
                    ▼
            ┌──────────────────────┐
            │ MarketContext        │  From Phase 3 MarketContext engine
            │ (IV rank, trend,     │  + user preferences (bias, max loss,
            │  expected move,      │  risk profile, time horizon)
            │  liquidity, events)  │
            └──────────┬───────────┘
                       │
                       ▼
            ┌──────────────────────────────────┐
            │    StrategySelector              │  Multi-factor scoring:
            │  13-strategy templates           │  • Bias alignment
            │  ranked by fit score             │  • IV preference fit
            │                                  │  • Risk level match
            └──────────┬──────────────────────┘  • Liquidity check
                       │                          • Event proximity
                       ▼                          • News sentiment
            ┌──────────────────────────────┐
            │  StrategyRecommendation      │  For each strategy:
            │  • Entry price & Greeks      │  • Est. max profit/loss
            │  • Breakeven prices          │  • P(profit) & confidence
            │  • Risk rating               │  • Initial reasoning
            └──────────┬──────────────────┘
                       │
                       ▼
            ┌──────────────────────────────────────┐
            │  Quantum AI Brain (Claude)           │  AI-powered reasoning:
            │  select_and_reason()                 │  • Refine confidence scores
            │                                      │  • Generate contextual reasoning
            │  Returns:                            │  • Rank by situation fit
            │  • Top 3 strategies with confidence  │  • Risk-adjusted priority
            │  • AI explanation                    │
            └──────────┬───────────────────────────┘
                       │
                       ▼
                StrategySelectionResult
            (recommendations + AI reasoning)
                       │
                       ├──► User decision (take/skip/modify)
                       │
                       ▼
        ┌──────────────────────────────────┐
        │  User executes trade             │
        │  (external execution system)     │
        └──────────────────────────────────┘
                       │
                       │ Trade closes
                       ▼
        ┌──────────────────────────────────┐
        │  TradeOutcome recording          │  Feedback loop:
        │  • P&L, lessons learned          │  record_trade_outcome()
        │  • User rating                   │
        └──────────┬──────────────────────┘
                   │
                   ▼
        ┌──────────────────────────────────┐
        │  QuantumAIBrain learns           │  Updates knowledge:
        │  • Strategy performance update   │  • Win rate tracking
        │  • Per-regime expectancy calc    │  • Avg P&L aggregation
        │  • Learnings extracted          │  • Context pattern collection
        └──────────┬──────────────────────┘
                   │
                   ▼
        ┌──────────────────────────────────┐
        │  Knowledge Versioning            │  Snapshot + rollback:
        │  create_knowledge_version()      │  • Immutable snapshots
        │  rollback_knowledge()            │  • Lineage tracking
        │                                  │  • Append-only history
        └──────────────────────────────────┘
```

---

## 3. Core Components

### 3.1 Models (`models.py`)

**Key Dataclasses:**

- `MarketContext` — current market snapshot (IV rank, trend, expected move, liquidity, events, news)
- `UserPreferences` — trader's constraints and bias (risk profile, max loss, bias direction, time horizon)
- `StrategyType` — enum of 13 available strategies (covered calls, spreads, straddles, strangles, diagonals, calendars)
- `GreeksSummary` — simplified options Greeks (delta, gamma, theta, vega, rho)
- `StrategyRecommendation` — single strategy with entry/exit zones, Greeks, confidence, reasoning
- `StrategySelectionResult` — top 3 recommendations + AI reasoning
- `TradeOutcome` — closed trade feedback (P&L, lessons learned, user rating)
- `VersionedKnowledge` — snapshot of strategy performance at a point in time
- `KnowledgeStore` — versioned history + trade outcomes log

All include `to_dict()`/`from_dict()` for JSON serialization.

### 3.2 Strategy Selector (`strategy_selector.py`)

**Core Logic:**

```python
class StrategySelector:
    def select_strategies(context, prefs, top_n=3) → [(strategy, fit_score), ...]
    def estimate_greeks(strategy, context, prefs) → GreeksSummary
    def build_recommendation(strategy, context, prefs, fit_score, reasoning) → StrategyRecommendation
```

**Strategy Database:**
Each of 13 strategies tagged with attributes:
- `bias` — preferred directional bias(es)
- `iv_preference` — "high", "medium", "low"
- `time_decay` — "positive", "negative", "mixed"
- `risk_level` — "low", "medium", "high"
- `capital_req` — margin/capital required

**Selection Scoring:**
1. **Bias match** (±2 points) — user bias vs strategy preference
2. **IV fit** (±1.5 points) — IV rank vs strategy IV preference
3. **IV trend alignment** (±0.5 points) — time decay matches IV direction
4. **Risk profile fit** (±1 point) — strategy risk level vs user risk profile
5. **Liquidity check** (-2 penalty if tight and capital-intensive)
6. **Event proximity** (±0.5) — time decay benefit if event imminent
7. **News sentiment** (±0.5) — volatile strategies score higher if big news

Final score is max(sum, 0.1) to ensure positive confidence.

**Greeks Estimation:**
Simplified model per strategy type (not real options pricing, just framework):
- Covered calls: δ=0.5, θ=+0.05 (positive time decay)
- Bull spreads: δ=0.35, θ=-0.02 (negative time decay)
- Iron condors: δ=0.1, θ=+0.10 (strong positive)
- etc.

**Profit/Loss Estimation:**
Max profit/loss scaled from strategy structure and market context, respecting user's max loss constraint.

### 3.3 Quantum AI Brain (`quantum_ai.py`)

**Core Interface:**

```python
class QuantumAIBrain:
    def select_and_reason(context, prefs, use_claude=True) → StrategySelectionResult
    def record_trade_outcome(outcome: TradeOutcome) → None
    def create_knowledge_version(notes="") → version_id
    def rollback_knowledge(version_id) → bool
```

**select_and_reason() Flow:**
1. Call StrategySelector to get 5 candidates, rank top 3
2. Build initial recommendations with Greeks
3. Call `_get_claude_reasoning()` (if `use_claude=True`) to refine with AI
4. Return StrategySelectionResult with top 3 + AI explanation

**Claude API Integration (Template):**
The method `_get_claude_reasoning()` is a placeholder ready for:
```python
from anthropic import Anthropic
client = Anthropic()
message = client.messages.create(
    model="claude-opus-4-8",
    max_tokens=1024,
    messages=[{"role": "user", "content": prompt}]
)
```

Current implementation returns structured fallback reasoning until API is wired.

**Trade Outcome Recording:**
```python
brain.record_trade_outcome(TradeOutcome(
    recommendation_id="rec1",
    symbol="SPY",
    strategy=StrategyType.BULL_CALL_SPREAD,
    entry_price=1.50,
    exit_price=2.20,
    pnl=70.0,
    pnl_pct=4.67,
    lessons_learned="Good setup, solid execution",
    user_rating=5,
))
```

Updates `current_version.strategy_performance`:
- Count, wins, gross P&L, per-strategy aggregates
- Per-regime expectancy (will power future regime-conditional selection)

**Knowledge Versioning:**
```python
v2_id = brain.create_knowledge_version("first-three-trades")
# v1 → history, v2 becomes current_version

success = brain.rollback_knowledge(v1_id)
# Restore v1; append rollback record to history
```

History is append-only; rollbacks are themselves recorded as new versions.

---

## 4. Key Mechanisms

### 4.1 Multi-Factor Fit Scoring

Selection is not random or rule-based—it's scored against:

| Factor | Score Range | Notes |
|--------|------------|-------|
| Bias alignment | -1 to +2.0 | Critical; misaligned strategies penalized |
| IV rank fit | -0.5 to +1.5 | High-IV favors premium selling; low-IV favors buying |
| Risk/profile match | -1.0 to +1.0 | Conservative users get low-risk strategies |
| Liquidity | 0 or -2.0 | Tight liquidity penalizes capital-heavy strategies |
| Event proximity | -0.5 to +0.5 | Positive time decay strategies score up if event soon |
| News sentiment | -0.5 to +0.5 | Volatile strategies score higher on strong sentiment |

**Result:** Strategies with highest aggregate score float to top; ties broken by specialization bonus.

### 4.2 Confidence Scoring

Each recommendation gets a confidence score (0-1):
- Base: fit_score (0-4 typically) mapped to confidence via: min(0.5 + fit_score \* 0.25, 1.0)
- AI refine: Claude can adjust based on reasoning context
- Historical win rate: Future versions can weight per-strategy historical P(win)

### 4.3 Greeks Estimation

Simplified, not real Black-Scholes (demo-grade):
- Delta: directional exposure (-1 to +1)
- Gamma: acceleration of delta (second-order Greeks)
- Theta: daily time decay (positive = we profit from time passage)
- Vega: sensitivity to IV changes (positive = we profit from IV increase)
- Rho: interest rate sensitivity (usually small)

Used for visual Greeks display in dashboard; not for live pricing.

### 4.4 Interactive Learning

Each trade closes → outcome recorded → strategy performance updated.

**Tracked per strategy:**
- Trade count
- Win count
- Gross profit / loss
- Average P&L
- Average P&L %

**Future enhancement:** Per-regime expectancy (did bull call spreads outperform in ranging markets?).

### 4.5 Knowledge Versioning

Snapshots are immutable JSON structures:
```json
{
  "version_id": "v1.2-1704067200",
  "created_at": 1704067200,
  "parent_version": "v1.1-1704067100",
  "strategy_performance": {
    "bull_call_spread": {"count": 10, "wins": 7, "avg_pnl": 85.0},
    ...
  },
  "user_learnings": [
    "Bull call spreads work well with IV crush after events",
    "Covered calls cap profit but provide steady income"
  ],
  "mc_validated": false
}
```

Rollback loads old version into `current_version`; the rollback action itself is recorded as a new version (append-only audit trail).

---

## 5. Integration Guide

### 5.1 Standalone Usage

```python
from nci_strategy_selector import (
    StrategySelector, QuantumAIBrain,
    MarketContext, UserPreferences
)

brain = QuantumAIBrain()

context = MarketContext(
    symbol="SPY", price=450.0,
    iv_rank=65, iv_trend=0.2,
    spot_trend=0.5, expected_move=12.0,
    liquidity_score=0.95
)

prefs = UserPreferences(
    symbol="SPY",
    risk_profile=RiskProfile.MODERATE,
    max_loss_dollars=1000.0,
    bias="bullish",
    time_horizon_days=30
)

result = brain.select_and_reason(context, prefs, use_claude=False)
# Returns: StrategySelectionResult with 3 strategies + reasoning
```

### 5.2 Learning Loop

```python
# After trade execution and close:
outcome = TradeOutcome(
    recommendation_id="rec123",
    symbol="SPY",
    strategy=result.recommendations[0].strategy,
    entry_price=1.50,
    exit_price=2.20,
    pnl=70.0,
    pnl_pct=4.67,
    lessons_learned="IV crush helped; timing was perfect",
    user_rating=5
)

brain.record_trade_outcome(outcome)

# Periodically snapshot knowledge:
v2_id = brain.create_knowledge_version("post-trade-1")
```

### 5.3 Claude API Wiring (Future)

Update `quantum_ai.py:_get_claude_reasoning()` to make actual API calls:

```python
def _get_claude_reasoning(self, context, prefs, recommendations):
    from anthropic import Anthropic
    
    client = Anthropic()
    prompt = self._build_reasoning_prompt(context, prefs, recommendations)
    
    message = client.messages.create(
        model="claude-opus-4-8",
        max_tokens=1024,
        messages=[{"role": "user", "content": prompt}]
    )
    
    return message.content[0].text
```

### 5.4 Dashboard Integration (opiontrading)

Wire Phase 4 into the options tab:

1. **Endpoint:** `GET /api/strategy-recommendation?symbol=SPY&context=<json>`
   - Input: market context + user prefs
   - Output: StrategySelectionResult (JSON)

2. **UI Panel:** Strategy Recommender
   - Show 3 recommendations in cards
   - Each card: strategy name, Greeks, max P/L, confidence, reasoning
   - "Execute" button → user confirms, sends to broker
   - "Log Outcome" form for feedback

3. **Learning Dashboard:** Knowledge Viewer
   - Current version ID + timestamp
   - Strategy performance stats table
   - Learnings log
   - Version history timeline
   - Rollback buttons

---

## 6. Extending Strategies

Add a new strategy template:

```python
from nci_strategy_selector import StrategySelector

class MyStrategySelector(StrategySelector):
    def __init__(self):
        super().__init__()
        self.strategy_db[StrategyType.CUSTOM_STRATEGY] = {
            "bias": ["bullish"],
            "iv_preference": "high",
            "direction_profit": "bullish",
            "risk_level": "medium",
            "capital_req": "low",
            "time_decay": "positive",
            "breakeven_shift": 1,
        }
```

Then retrain the Greeks estimation and max P&L logic for your custom strategy.

---

## 7. Test Coverage

**20 tests (all passing):**

Strategy Selector (9):
- Bullish/bearish context filtering
- High/low IV preference alignment
- Conservative risk filtering
- Greeks estimation
- Recommendation building
- Recommendation constraints

Quantum AI Brain (9):
- Brain initialization
- select_and_reason workflow
- Trade outcome recording
- Multiple outcome aggregation
- Knowledge versioning
- Knowledge rollback
- Serialization/deserialization
- Multi-outcome learning
- Reasoning generation

Integration (2):
- Full workflow (select → learn → version)
- Multi-symbol/strategy handling

---

## 8. Invariants to Preserve

1. Every recommendation respects user's `max_loss_dollars` constraint (within 50%)
2. `select_and_reason()` always returns exactly 3 recommendations (or < 3 if fewer strategies available)
3. Confidence score is always 0 to 1, rounded to nearest 1%
4. All serialized state validates against JSON schema
5. Knowledge versions are immutable; rollbacks append, never rewrite
6. Educational-use disclaimer shipped in all user-facing output

---

## 9. Next Steps (Phases 5-7)

- **Phase 5:** AI Reasoning Enhancement — Claude deeper reasoning, multi-turn dialogue
- **Phase 6:** Portfolio Optimization — multi-leg correlations, Greeks aggregation
- **Phase 7:** Live Integration — Alpaca broker wiring, real-time market data feed

---

## 10. Running the Demo

```bash
cd nci-phase-4
python3 examples/demo_phase4.py
```

Shows:
- Three market scenarios (bullish, pre-event, bearish)
- Strategy selection and AI reasoning for each
- Trade outcome recording
- Knowledge versioning and rollback
- State persistence

---

**Educational analysis tooling — not investment advice.**
