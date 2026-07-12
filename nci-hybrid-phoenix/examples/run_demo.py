#!/usr/bin/env python3
"""
NCI Hybrid Phoenix Brain — end-to-end demo.

Simulates a trading week: regime shifts, wins/losses, a drawdown that
triggers rescue mode, recovery, a Monte Carlo validation, and a version
snapshot + rollback. Prints the decision trail so you can watch the brain
think.

Run:  python3 examples/run_demo.py
"""

from __future__ import annotations

import random
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from nci_phoenix import (  # noqa: E402
    BrainVersionStore,
    MarketSnapshot,
    MonteCarloConfig,
    NCIPhoenixBrain,
    Regime,
    RiskConfig,
    Signal,
    TradeResult,
)

OUT = Path(__file__).resolve().parent


def show(title: str, decision) -> None:
    print(f"\n── {title} " + "─" * max(0, 58 - len(title)))
    print(f"  regime   : {decision.regime.value}")
    print(f"  agent    : {decision.agent or '—'}")
    print(f"  signal   : {decision.signal.value}")
    print(f"  size     : {decision.lot_multiplier}× base lot")
    print(f"  rescue   : {decision.rescue_mode}")
    if decision.blocked_by:
        print(f"  BLOCKED  : {decision.blocked_by}")
    for line in decision.reasoning:
        print(f"    · {line}")


def main() -> None:
    rng = random.Random(11)
    brain = NCIPhoenixBrain(
        risk_config=RiskConfig(daily_loss_limit_r=6.0),
        mc_config=MonteCarloConfig(simulations=1000),
        mc_seed=11,
    )
    store = BrainVersionStore(OUT / "versions")
    v_base = store.snapshot(brain.to_state(), "v2.1.0", "baseline roster")
    print(f"snapshotted baseline brain as {v_base}")

    # Monday: clean bullish trend
    show("Mon — trending bull", brain.evaluate(MarketSnapshot(
        symbol="EURUSD", price=1.0850, adx=38, trend_direction=1,
        atr=0.0011, atr_baseline=0.0010, session="london",
    )))

    # Tuesday: red news minutes away — risk gate slams shut
    show("Tue — NFP in 5 minutes", brain.evaluate(MarketSnapshot(
        symbol="EURUSD", price=1.0870, adx=38, trend_direction=1,
        session="newyork",
    ), minutes_to_news=5))

    # Feed a profitable run for the trend rider
    for _ in range(30):
        brain.record_trade(TradeResult(
            agent_name="Trend_Rider_Quantum", symbol="EURUSD",
            signal=Signal.LONG, pnl=rng.choice([220, 180, -100]),
            pnl_r=rng.choice([2.2, 1.8, -1.0]),
            regime=Regime.TRENDING_BULLISH,
        ))
    rec = brain.pool.records["Trend_Rider_Quantum"]
    print(f"\nTrend_Rider_Quantum after hot run → score {rec.score:.2f}, "
          f"status {rec.status.value}, trades {rec.performance.trades}")

    report = brain.validate_agent("Trend_Rider_Quantum")
    print(f"Monte Carlo gate: accepted={report.accepted}  "
          f"P(ruin)={report.ruin_probability:.3f}  "
          f"medianExp={report.median_expectancy_r:.2f}R")
    store.snapshot(brain.to_state(), "v2.1.1", "trend rider validated hot")

    # Wednesday: losing streak → rescue mode
    for _ in range(4):
        brain.record_trade(TradeResult(
            agent_name="Trend_Rider_Quantum", symbol="EURUSD",
            signal=Signal.LONG, pnl=-90, pnl_r=-0.9,
            regime=Regime.RANGING_CHOPPY,
        ))
    show("Wed — after 4 straight losses", brain.evaluate(MarketSnapshot(
        symbol="EURUSD", price=1.0800, adx=40, trend_direction=-1,
        session="london",
    )))

    # PID trims size while equity slope is negative
    m = brain.update_sizing(r_per_day=-1.5)
    print(f"\nPID lot multiplier after -1.5R/day slope: {m:.2f}×")

    # Recovery under rescue, then normal selection resumes
    for _ in range(6):
        brain.record_trade(TradeResult(
            agent_name="Hybrid_Rescue", symbol="EURUSD",
            signal=Signal.SHORT, pnl=70, pnl_r=0.7,
            regime=Regime.TRENDING_BEARISH,
        ))
    show("Thu — recovered", brain.evaluate(MarketSnapshot(
        symbol="EURUSD", price=1.0760, adx=41, trend_direction=-1,
        session="newyork",
    )))

    # Friday: version history + rollback demo
    print("\nversion history:")
    for v in store.list_versions():
        print(f"  {v['id']}  ← parent {v['parent']}")
    store.rollback(v_base, reason="demo rollback to baseline")
    print(f"rolled back to {v_base}; history now has "
          f"{len(store.list_versions())} entries (append-only)")

    brain.save(OUT / "brain_state.example.json")
    print(f"\nfull brain state written → {OUT / 'brain_state.example.json'}")
    print("\nEducational analysis tooling — not investment advice.")


if __name__ == "__main__":
    main()
