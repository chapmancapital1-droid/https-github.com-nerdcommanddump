#!/usr/bin/env python3
"""
Phase 4 Demo: Strategy Selector & Quantum AI Brain.

Demonstrates adaptive strategy recommendation, AI reasoning, and interactive learning.

Run: python3 examples/demo_phase4.py
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from nci_strategy_selector import (
    StrategyType,
    RiskProfile,
    MarketContext,
    UserPreferences,
    TradeOutcome,
    QuantumAIBrain,
)


def divider(title: str) -> None:
    print(f"\n{'─' * 70}")
    print(f"  {title}")
    print(f"{'─' * 70}\n")


def show_market_snapshot(context: MarketContext) -> None:
    print(f"  Symbol          : {context.symbol}")
    print(f"  Current Price   : ${context.price:.2f}")
    print(f"  IV Rank         : {context.iv_rank:.0f}%")
    print(f"  IV Trend        : {context.iv_trend:+.2f}")
    print(f"  Spot Trend      : {context.spot_trend:+.2f}")
    print(f"  Expected Move   : ${context.expected_move:.2f}")
    print(f"  Liquidity       : {context.liquidity_score:.2f}")
    if context.event_proximity_days:
        print(f"  Event in        : {context.event_proximity_days:.1f} days")


def show_user_preferences(prefs: UserPreferences) -> None:
    print(f"  Risk Profile    : {prefs.risk_profile.value}")
    print(f"  Bias            : {prefs.bias}")
    print(f"  Max Loss        : ${prefs.max_loss_dollars:.2f}")
    print(f"  Time Horizon    : {prefs.time_horizon_days} days")


def show_recommendations(result) -> None:
    print(f"\nTop {len(result.recommendations)} Recommendations:\n")
    for i, rec in enumerate(result.recommendations, 1):
        print(f"  {i}. {rec.strategy.value.replace('_', ' ').title()}")
        print(f"     Entry Price    : ${rec.entry_price:.2f}")
        print(f"     Max Profit     : ${rec.max_profit:.2f}")
        print(f"     Max Loss       : ${rec.max_loss:.2f}")
        print(f"     Breakeven      : ${rec.breakeven_price:.2f}")
        print(f"     P(Profit)      : {rec.probability_profit:.0%}")
        print(f"     Confidence     : {rec.confidence_score:.0%}")
        print(f"     Risk Rating    : {rec.risk_rating}")
        print(f"     Greeks         : Δ{rec.greeks.delta:+.2f} "
              f"Γ{rec.greeks.gamma:+.4f} "
              f"Θ{rec.greeks.theta:+.4f} "
              f"V{rec.greeks.vega:+.2f}")
        print()


def show_ai_reasoning(reasoning: str) -> None:
    print("AI Reasoning:\n")
    for line in reasoning.split("\n"):
        print(f"  {line}")


def main() -> None:
    divider("PHASE 4 DEMO: Strategy Selector & Quantum AI Brain")

    brain = QuantumAIBrain()
    print("✓ Quantum AI Brain initialized\n")

    # Scenario 1: Bullish continuation with high IV
    divider("Scenario 1: Bullish Setup with High IV")
    print("Market Context:")
    context1 = MarketContext(
        symbol="SPY",
        price=450.0,
        iv_rank=75,
        iv_trend=0.3,
        spot_trend=0.5,
        expected_move=13.0,
        liquidity_score=0.95,
        event_proximity_days=None,
        news_sentiment=0.3,
    )
    show_market_snapshot(context1)

    print("\nUser Preferences:")
    prefs1 = UserPreferences(
        symbol="SPY",
        risk_profile=RiskProfile.MODERATE,
        max_loss_pct=2.0,
        max_loss_dollars=1000.0,
        bias="bullish",
        time_horizon_days=30,
    )
    show_user_preferences(prefs1)

    result1 = brain.select_and_reason(context1, prefs1, use_claude=False)
    show_recommendations(result1)
    show_ai_reasoning(result1.ai_reasoning)

    # Scenario 2: Neutral with uncertainty (event risk)
    divider("Scenario 2: Pre-Event Uncertainty (High IV Crush Risk)")
    print("Market Context:")
    context2 = MarketContext(
        symbol="QQQ",
        price=350.0,
        iv_rank=88,
        iv_trend=-0.2,
        spot_trend=0.0,
        expected_move=16.0,
        liquidity_score=0.92,
        event_proximity_days=1.5,
        news_sentiment=0.2,
    )
    show_market_snapshot(context2)

    print("\nUser Preferences:")
    prefs2 = UserPreferences(
        symbol="QQQ",
        risk_profile=RiskProfile.CONSERVATIVE,
        max_loss_pct=1.0,
        max_loss_dollars=500.0,
        bias="neutral",
        time_horizon_days=45,
    )
    show_user_preferences(prefs2)

    result2 = brain.select_and_reason(context2, prefs2, use_claude=False)
    show_recommendations(result2)
    show_ai_reasoning(result2.ai_reasoning)

    # Scenario 3: Bearish with low IV (volatility compression)
    divider("Scenario 3: Bearish Continuation with Low IV")
    print("Market Context:")
    context3 = MarketContext(
        symbol="IWM",
        price=185.0,
        iv_rank=22,
        iv_trend=-0.4,
        spot_trend=-0.6,
        expected_move=6.0,
        liquidity_score=0.85,
        event_proximity_days=None,
        news_sentiment=-0.5,
    )
    show_market_snapshot(context3)

    print("\nUser Preferences:")
    prefs3 = UserPreferences(
        symbol="IWM",
        risk_profile=RiskProfile.AGGRESSIVE,
        max_loss_pct=3.0,
        max_loss_dollars=1500.0,
        bias="bearish",
        time_horizon_days=21,
    )
    show_user_preferences(prefs3)

    result3 = brain.select_and_reason(context3, prefs3, use_claude=False)
    show_recommendations(result3)
    show_ai_reasoning(result3.ai_reasoning)

    # Interactive Learning: Record trade outcomes
    divider("Interactive Learning: Recording Trade Outcomes")

    outcomes = [
        (result1.recommendations[0], 2.35, 2.80, "Bull call spread during continuation —"
         " profitable on spot continuation and time decay"),
        (result2.recommendations[0], 1.75, 0.50, "Iron condor pre-event — protected well"
         " from volatility expansion"),
        (result3.recommendations[0], 1.50, 2.10, "Bear call spread — caught the reversal"
         " perfectly after the sell-off"),
    ]

    for i, (rec, entry, exit_price, lesson) in enumerate(outcomes, 1):
        pnl = (exit_price - entry) * 100
        pnl_pct = (exit_price - entry) / entry * 100

        outcome = TradeOutcome(
            recommendation_id=f"rec_{i}",
            symbol=rec.strategy.value,
            strategy=rec.strategy,
            entry_price=entry,
            exit_price=exit_price,
            pnl=pnl,
            pnl_pct=pnl_pct,
            lessons_learned=lesson,
            user_rating=5 if pnl > 0 else 3,
        )

        brain.record_trade_outcome(outcome)

        status = "✓ WIN" if pnl > 0 else "✗ LOSS"
        print(f"\n  Trade {i}: {rec.strategy.value.title()}")
        print(f"    {status} | P&L: ${pnl:.2f} ({pnl_pct:+.1f}%)")
        print(f"    Learning: {lesson}")

    # Knowledge versioning
    divider("Knowledge Versioning & Rollback")

    v1_id = brain.knowledge.current_version.version_id
    print(f"Initial version: {v1_id}\n")

    v2_id = brain.create_knowledge_version("first-three-trades")
    print(f"✓ Version created: {v2_id}")
    print(f"  Parent: {v1_id}")

    # Show learned strategy performance
    perf = brain.knowledge.current_version.strategy_performance
    print("\n  Strategy Performance:")
    for strategy_name, metrics in perf.items():
        print(f"    {strategy_name:25} | Trades: {metrics['count']} | "
              f"Wins: {metrics['wins']} | "
              f"Avg P&L: ${metrics['avg_pnl']:+.1f}")

    print(f"\n  Learnings captured: {len(brain.knowledge.current_version.user_learnings)}")

    # Demonstrate rollback
    print(f"\n✓ Rolling back to {v1_id}...")
    success = brain.rollback_knowledge(v1_id)
    if success:
        print(f"  ✓ Rollback successful")
        print(f"  Strategy performance entries: {len(brain.knowledge.current_version.strategy_performance)}")

    # Persistent storage demo
    divider("Persistent Storage")

    state = brain.to_dict()
    print(f"✓ Brain state serialized")
    print(f"  Knowledge versions: {len(brain.knowledge.history) + 1}")
    print(f"  Trade outcomes recorded: {len(brain.knowledge.trade_outcomes)}")
    print(f"  Stored model: {brain.model}")

    # Re-instantiate from state
    brain2 = QuantumAIBrain.from_dict(state)
    print(f"\n✓ Brain state restored")
    print(f"  Recovered {len(brain2.knowledge.trade_outcomes)} outcomes")

    divider("Demo Complete")
    print("Educational analysis tooling — not investment advice.\n")


if __name__ == "__main__":
    main()
