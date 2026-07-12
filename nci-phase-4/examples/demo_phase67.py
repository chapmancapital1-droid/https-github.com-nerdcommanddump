"""
Phase 6/7 end-to-end sanity demo.

Backtests ~2 years of synthetic SPY, prints stats, runs the Monte Carlo
promotion gate, then builds a small portfolio and prints its risk view.

Educational analysis tooling — not investment advice.

Run: python3 examples/demo_phase67.py
"""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from nci_strategy_selector import (
    StrategySelector, StrategyType, MarketContext, UserPreferences, RiskProfile,
    synthetic_bars, BacktestEngine, BacktestPlan, validate,
    Portfolio, Position, reconcile_payoff,
)


def main():
    print("=" * 68)
    print("NCI Phase 6/7 — payoff + backtest + portfolio sanity run")
    print("=" * 68)

    # 1. Backtest ~2 years of synthetic SPY -------------------------------
    bars = synthetic_bars("SPY", days=504, seed=7, start_price=440.0)
    print(f"\nBars: {len(bars)}  {bars[0].date}..{bars[-1].date}  "
          f"({bars[0].close} -> {bars[-1].close})")

    plan = BacktestPlan(
        entry_every_n_days=21, holding_days=21,
        bias="neutral", risk_profile=RiskProfile.MODERATE,
        max_loss_dollars=5000.0, max_loss_stop=1000.0,
    )
    result = BacktestEngine().run("SPY", bars, plan)

    print("\n--- Backtest stats ---")
    print(json.dumps(result.stats, indent=2))
    strategies = sorted({t.strategy for t in result.trades})
    print("strategies traded:", strategies)
    print("exit reasons:", sorted({t.exit_reason for t in result.trades}))

    # 2. Monte Carlo promotion gate --------------------------------------
    report = validate(result)
    print("\n--- Monte Carlo gate ---")
    print(json.dumps(report.to_dict(), indent=2))

    # 3. Portfolio risk view ---------------------------------------------
    selector = StrategySelector()
    ctx = MarketContext(symbol="SPY", price=440.0, iv_rank=55, iv_trend=0.1,
                        spot_trend=0.2, expected_move=12.0, liquidity_score=0.96)
    prefs = UserPreferences(symbol="SPY", risk_profile=RiskProfile.MODERATE,
                            max_loss_pct=2.0, max_loss_dollars=5000.0,
                            bias="neutral", time_horizon_days=21)

    pf = Portfolio(account_size=50000.0)
    for st in (StrategyType.IRON_CONDOR, StrategyType.BULL_PUT_SPREAD):
        rec = selector.build_recommendation(st, ctx, prefs, fit_score=1.5, reasoning="demo")
        pf.add(Position(rec, qty=2))

    print("\n--- Portfolio aggregates ---")
    print(json.dumps(pf.aggregates().to_dict(), indent=2))

    candidate_rec = selector.build_recommendation(
        StrategyType.BULL_CALL_SPREAD, ctx, prefs, fit_score=1.5, reasoning="candidate")
    cand = Position(candidate_rec, qty=8)
    print("\n--- check() on an oversized bullish candidate ---")
    for w in pf.check(cand):
        print("  !", w)

    print("\n--- suggest() ---")
    for s in pf.suggest():
        print("  -", s)

    print("\nDone.")


if __name__ == "__main__":
    main()
