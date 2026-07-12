# NCI Hybrid Phoenix Brain — Design Document (v2.1)

**Status:** Implemented & tested (47 tests, stdlib-only Python 3.11+)
**Audience:** NCI dev team enhancing the main brain at `C:\NCI\Brain`
**Position in NCI:** Phoenix is a self-contained module — the "Hybrid Phoenix"
tab of the main brain. It has zero dependencies, so it drops into any host:
the EA's VPS, a local machine, or the NCI nerdcommand dashboard backend.

> Educational analysis tooling — not investment advice. The brain proposes;
> a human-approved risk envelope disposes.

---

## 1. Design philosophy

Self-organizing + regime-aware + Monte-Carlo-validated + human-aligned risk.

Four principles drive every structural choice:

1. **Evidence over opinion.** Agents earn allocation from realized R-multiples,
   not from anyone's belief in them. Specialization is a *bonus* on top of an
   earned score, never a substitute for it.
2. **The risk layer can always say no.** RiskManager sits between every signal
   and the market. It only blocks or passes — it never sizes up. Sizing is the
   PID controller's job. Separating "may we?" from "how much?" keeps both
   auditable.
3. **Nothing gets promoted without surviving Monte Carlo.** Block-bootstrap
   resampling (streak-preserving) gates every agent promotion and parameter
   change: P(ruin) ≤ 2%, median expectancy ≥ 0.05R, median max DD ≤ 12R.
4. **History is append-only.** Version snapshots are immutable; a rollback is
   itself recorded as a new snapshot. You can always answer "what did the
   brain believe on Tuesday, and why?"

---

## 2. Architecture

```
                          ┌────────────────────────────┐
   MarketSnapshot ──────► │      RegimeDetector        │  5 weighted votes:
   (price, ATR, ADX,      │  volatility · trend ·      │  regime + confidence
    structure, news,      │  range · news · coil       │  + evidence notes
    session, spread)      └─────────────┬──────────────┘
                                        │ RegimeState
                                        ▼
                          ┌────────────────────────────┐
                          │    HybridOrchestrator      │  rescue state machine
                          │  normal: AgentPool select  │  triggers: loss streak,
                          │  rescue: Hybrid_Rescue     │  pool degraded, drawdown
                          └─────────────┬──────────────┘
                                        │ (agent, Signal)
                                        ▼
                          ┌────────────────────────────┐
                          │       RiskManager          │  daily/weekly R limits,
                          │   gates — can only block   │  DD circuit breaker,
                          └─────────────┬──────────────┘  position/correlation
                                        │ pass            caps, news blackout
                                        ▼
                          ┌────────────────────────────┐
                          │      PIDController         │  lot multiplier from
                          │  equity-slope → sizing     │  equity slope vs target,
                          └─────────────┬──────────────┘  anti-windup, clamped
                                        │
                                        ▼
                                   Decision  ──────►  EA / dashboard tab
                          (signal, agent, regime, size,
                           rescue flag, blocked_by, full
                           reasoning trail)

   Learning loop (per closed trade):
   TradeResult ─► TradeMemory (ring 250) ─► AgentPool.record_trade (EMA score,
                promote/demote) ─► RiskManager ledger
   TradeMemory.r_series() ─► MonteCarloEngine.validate ─► promotion gate

   Persistence:
   NCIPhoenixBrain.to_state()/load_state()  ⇄  brain_state.json
   BrainVersionStore.snapshot()/rollback()  →  versions/*.json + index.json
```

## 3. Module map & responsibilities

| Module | Class(es) | Responsibility |
|---|---|---|
| `models.py` | all dataclasses + enums | Single source of truth for every structure; dict/JSON round-trip |
| `regime.py` | `RegimeDetector` | Pure, deterministic multi-method regime scoring |
| `agents/base.py` | `BaseTradingAgent` | The 4-method contract every strategy implements |
| `agents/library.py` | 6 reference agents | Working templates the team swaps EA logic into |
| `pool.py` | `AgentPool` | Scores (EMA), promotes/demotes, selects with specialization bonus + exploration |
| `orchestrator.py` | `HybridOrchestrator` | Who trades; rescue engage/recover state machine |
| `risk.py` | `RiskManager`, `OpenPosition` | All hard gates & circuit breakers; block-only |
| `pid.py` | `PIDController` | Lot multiplier from equity slope; anti-windup; clamped |
| `montecarlo.py` | `MonteCarloEngine`, `MonteCarloReport` | Block-bootstrap validation; the promotion gate |
| `memory.py` | `TradeMemory` | Last-250 ring buffer; streaks; per-(agent, regime) expectancy |
| `versioning.py` | `BrainVersionStore` | Immutable snapshots, lineage index, append-only rollback |
| `brain.py` | `NCIPhoenixBrain` | Facade wiring it all; the only class hosts need to touch |

## 4. Key mechanisms (the parts worth studying)

### 4.1 Agent scoring — earned, smoothed, bounded
Evidence per trade maps R → [0,1] (`0.5 + 0.25·R`, clamped), then EMA:
`score ← (1−s)·score + s·evidence` with `s = 0.30`. One great trade can't
crown an agent; one bad trade can't kill it. Status transitions:

```
ACTIVE ──(score ≤ 0.35)──► PROBATION ──(score ≤ 0.35)──► DORMANT
  ▲                                                        │
  └──(score ≥ 0.65 AND ≥ 10 trades)────────────────────────┘
```

Dormant agents re-enter only through the **exploration channel** (default 5%
of selections) — they must rebuild a record at market, exactly like a trader
coming back from a blowup.

### 4.2 Rescue mode — the system's own stop-loss
Triggers (any): loss streak ≥ 4 · pool degraded (no ACTIVE agents) ·
drawdown ≥ 8% (before the 12% hard breaker). While engaged, `Hybrid_Rescue`
(A+ setups only, 0.35 risk fraction) holds the book. Exit requires ≥ 5 trades
with **net-positive R and no live loss streak** — recovery is proven, not
declared.

### 4.3 Monte Carlo gate — why block bootstrap
Naive shuffling destroys streak structure and understates drawdown risk.
Phoenix resamples contiguous blocks (default 10 trades), preserving the
win/loss clustering that actually produces deep drawdowns. 7,500 paths;
acceptance requires all three criteria. In testing, the default gate
correctly rejects a 55%-win ±1R system (marginal) and accepts 60% (real edge)
— that discrimination is the feature.

### 4.4 PID sizing — follow performance, don't fight it
`error = setpoint − measured R/day`. Underperformance → positive error →
multiplier trims (floor 0.10×). Outperformance eases size back up (cap
2.00×). Integral clamped at ±5 (anti-windup) so a long bad stretch can't
build unbounded correction that whipsaws sizing when conditions turn.

## 5. Integration guide

### 5.1 Drop into the main brain (`C:\NCI\Brain`)
```
C:\NCI\Brain\
  phoenix\                 ← copy the nci_phoenix/ package here
  brain_state.json         ← live state (brain.save / NCIPhoenixBrain.open)
  versions\                ← BrainVersionStore root
```
No pip installs. Python 3.11+ only.

### 5.2 EA decision loop (per bar close or timer)
```python
from nci_phoenix import NCIPhoenixBrain, MarketSnapshot, TradeResult

brain = NCIPhoenixBrain.open(r"C:\NCI\Brain\brain_state.json")

def on_bar(bar):                          # ← your EA's callback
    d = brain.evaluate(MarketSnapshot(
        symbol=bar.symbol, price=bar.close,
        atr=bar.atr14, atr_baseline=bar.atr100,
        adx=bar.adx14, trend_direction=bar.structure_dir,
        range_width_pct=bar.range_pct, news_impact=news_feed.impact(),
        session=session_of(bar.time), spread_pts=bar.spread,
    ), minutes_to_news=news_feed.minutes_to_next_red())
    if d.signal.value != "flat":
        ea.submit(d.signal.value, lots=base_lot * d.lot_multiplier)
    log(d.reasoning)                      # full audit trail, every decision

def on_trade_closed(t):
    brain.record_trade(TradeResult(
        agent_name=brain.last_decision.agent, symbol=t.symbol,
        signal=..., pnl=t.profit, pnl_r=t.profit / t.initial_risk,
        regime=brain.last_regime.regime,
    ))
    brain.update_equity(account.equity)
    brain.save(r"C:\NCI\Brain\brain_state.json")

def nightly():
    brain.update_sizing(r_per_day=equity_slope_R())
    report = brain.validate_book()        # Monte Carlo health check
    store.snapshot(brain.to_state(), label=next_version(), notes=...)
```

### 5.3 Dashboard tab (NCI nerdcommand / opiontrading app)
The **Phoenix tab** is a pure reader of `brain_state.json` — schema in
`schemas/nci_brain_schema.json`. Serve it via one API route
(`GET /api/phoenix` → file contents) and render four panels:

1. **Regime** — current regime, confidence bar, evidence notes
2. **Agent pool** — roster table: score, status chip, per-regime expectancy
   (from `memory` → `expectancy_by_agent_regime`), promotions/demotions
3. **Risk & sizing** — drawdown vs breaker, gates recently hit
   (`last_decision.blocked_by`), PID multiplier, rescue flag
4. **Versions** — `versions/index.json` lineage chain; a "roll back" action
   posts the version id to the brain host

Wire-up lands in the opiontrading repo after the Phase 4 agent completes
(avoids collisions with its in-flight work).

### 5.4 Viktor AI / currency-strength fusion (extension point)
External signal sources plug in as inputs, not as agents: enrich
`MarketSnapshot` (e.g. add `viktor_bias: float`) and let agents consume it in
`propose()`. Keeping external signals out of the pool means they can't be
promoted/demoted — they're evidence, not actors. If Viktor should *act*,
wrap it as a `BaseTradingAgent` instead and let it earn score like everyone.

## 6. Extending the roster

```python
from nci_phoenix.agents.base import BaseTradingAgent
from nci_phoenix.models import Regime, Signal

class MyProductionScalper(BaseTradingAgent):
    name = "MyProductionScalper"
    version = "1.0"
    specializations = (Regime.RANGING_CHOPPY,)

    def propose(self, regime, snap):
        # ← port the existing EA entry logic here, condition by condition
        return Signal.FLAT

    def risk_fraction(self, regime, snap):
        return 0.5

brain = NCIPhoenixBrain(agents=[*default_roster(), MyProductionScalper()])
```
Then **gate it**: run shadow (record trades, size 0) until
`brain.validate_agent("MyProductionScalper").accepted` is true, snapshot a
version, and only then let the pool allocate to it.

## 7. Invariants the dev team must preserve

1. `RiskManager.check()` runs on **every** non-flat signal — no bypass path.
2. Sizing never exceeds `pid.output_max × max(agent risk_fraction)`.
3. `record_trade` fans out to memory + pool + risk **atomically** (one call:
   `NCIPhoenixBrain.record_trade`). Never write to one surface directly.
4. Version snapshots are immutable; rollbacks append, never rewrite.
5. Agents can only be promoted with `min_trades_for_promotion` real trades
   AND a passing Monte Carlo report.
6. Every serialized state validates against `schemas/nci_brain_schema.json`.
7. The educational-use disclaimer ships in every user-facing surface.

## 8. Roadmap hooks (designed-for, not yet built)

- **Regime-conditional scoring:** pool selection using per-regime expectancy
  from `TradeMemory` instead of the flat specialization bonus (data already
  collected; swap `effective_score`).
- **Agent mutation:** spawn parameter-perturbed variants of top agents into
  DORMANT status; exploration channel + MC gate handle the rest.
- **Multi-symbol books:** one `AgentPool` per symbol group sharing a global
  `RiskManager` (correlation groups already modeled).
- **Options mode:** `MarketSnapshot` gains IV-rank/expected-move fields from
  the Phase-3 MarketContext engine in opiontrading — Phoenix regimes and the
  options MarketContext are deliberately shape-compatible.
