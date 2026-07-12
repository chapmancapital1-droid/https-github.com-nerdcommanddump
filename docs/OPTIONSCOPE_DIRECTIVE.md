# OptionScope — Product Completion Directive v1.0

> Educational analysis tooling — not investment advice. OptionScope proposes
> and explains; the human decides. Every probability shown is a model output,
> labeled with its assumptions.

## The prompt, perfected

Original intent (owner, 2026-07-12): complete **OptionScope** — the options
trading assistant with an AI brain that learns — governed by a board of five
(2 senior master program developers, 3 billionaire-grade business/options-algo
operators) who make the programming decisions.

Refined into an executable directive:

**When the user starts an Active Analysis on a ticker, OptionScope runs a
full AI-brain evaluation of that ticker using every data surface the
dashboard has curated — market context (price action, trend, IV rank/trend,
expected move, liquidity, events, news), all option Greeks, payoff curves,
backtest evidence, current portfolio state, and everything the brain has
learned from the user's own logged outcomes — and returns, clearly on the
dashboard: (1) which strategies fit and why, (2) at which strike structures,
(3) for each of the user's trade-type intents (income / directional /
volatility / hedge), (4) each with an explicit, honestly-derived probability
of profit and max loss vs the user's risk limits, (5) with the full
reasoning trail visible and interrogable via multi-turn Q&A.**

## What exists (built, tested, pushed — 215 tests green)

| Layer | Status |
|---|---|
| Strategy selector: 13 strategies, multi-factor fit scoring | ✅ Phase 4 |
| Quantum AI reasoning: live Claude + offline fallback, multi-turn sessions | ✅ Phase 5 |
| Confidence calibration: learns from user's real outcomes, re-ranks | ✅ Phase 5 |
| Payoff engine: real legs, curve-derived breakevens/max-loss (13/13) | ✅ Phase 6a |
| Backtest engine + Monte-Carlo statistical gate | ✅ Phase 6b |
| Portfolio engine: net Greeks, risk budget, concentration warnings | ✅ Phase 7 |
| Dashboard: strategy cards, ask-AI, Phoenix tab, live-data prefill (Alpaca/demo) | ✅ |
| Dashboard wiring of payoff charts / backtest tab / portfolio tab / persistence | 🔨 in flight |
| NCI Hybrid Phoenix Brain (separate module for C:\NCI\Brain) | ✅ v2.1 |

## The completion feature: **Active Analysis**

One button on the dashboard: **"Run Active Analysis"** for the current ticker.

Pipeline (all existing engines, orchestrated into one evaluation):

1. **Curate** — pull the freshest MarketContext (live or demo provider),
   the payoff-verified strategy set, calibration state, portfolio state,
   and (when available) backtest evidence for this symbol.
2. **Evaluate per trade-type intent** — for each of: income, directional,
   volatility, hedge → run the selector with intent-adjusted preferences,
   producing strike-level structures with Greeks and curve-verified numbers.
3. **Brain synthesis** — Quantum AI (Claude when keyed, offline otherwise)
   receives the complete curated bundle and produces the ticker verdict:
   ranked strategies per intent, the data points that drove each call,
   what would change its mind, and explicit uncertainty.
4. **Score honestly** — probability of profit from the payoff curve vs the
   expected-move distribution (label the model), adjusted by the calibrator's
   learned per-strategy factor; never present an unvalidated number as fact.
5. **Present** — an Active Analysis panel: verdict card per intent, PoP
   badges with derivation notes, strike ladders, the reasoning trail, and
   one-click handoff to "take this trade" (portfolio) or "interrogate" (Q&A).
6. **Learn** — every taken trade's outcome feeds calibration; every analysis
   is stored so the brain's future evaluations cite its own track record.

## Decision points reserved for the Board

- **D1. PoP methodology** — payoff-curve × expected-move distribution
  (current Bachelier assumption) vs. adding a lognormal/empirical option;
  how PoP must be labeled to stay honest.
- **D2. Intent mapping** — how the four trade-type intents translate into
  selector preference presets (bias/risk/IV weighting) without hidden magic.
- **D3. Learning boundary** — what the brain may learn autonomously
  (calibration factors) vs. what requires explicit user confirmation
  (knowledge-version promotion, strategy blacklisting).
- **D4. Evaluation depth vs. latency** — full backtest inside Active
  Analysis (slow, evidence-rich) vs. cached/on-demand (fast, staler).
- **D5. Presentation of uncertainty** — how PoP, confidence, and MC-gate
  results coexist on one card without misleading a retail-grade user.
- **D6. Architecture** — where Active Analysis orchestration lives
  (dashboard api layer vs. a new module in nci-phase-4) and its contract.

## Non-negotiable constraints (owner + prior board of one)

1. Zero runtime dependencies — stdlib Python; single self-contained page.
2. Max-loss limits are hard gates, never suggestions.
3. Every estimated number is labeled as estimated, with derivation notes.
4. The educational disclaimer ships on every surface.
5. Works fully offline (no keys) — live data/AI light up when keyed.
6. The brain's learning is inspectable and versioned; rollbacks append-only.

## Acceptance criteria

- Active Analysis runs end-to-end on any ticker in ≤ a few seconds (demo
  data) and produces all four intent verdicts with PoP + max loss on card.
- Every number on the panel traces to an engine output (no UI-invented math).
- Calibration provably alters a future analysis after logged outcomes.
- Full test coverage of the orchestration layer; suite stays green.
- Board sign-off recorded in `docs/OPTIONSCOPE_BOARD_MINUTES.md`.
