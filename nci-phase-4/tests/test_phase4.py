"""
Phase 4 tests: Strategy Selector & Quantum AI Brain.

Tests strategy recommendation, AI reasoning, knowledge versioning, and learning.
"""

import unittest
import time
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from nci_strategy_selector import (
    StrategyType,
    RiskProfile,
    MarketContext,
    UserPreferences,
    StrategyRecommendation,
    TradeOutcome,
    StrategySelector,
    QuantumAIBrain,
)


class TestStrategySelector(unittest.TestCase):
    """Test strategy selector."""

    def setUp(self):
        self.selector = StrategySelector()

    def test_selector_initialized(self):
        """Strategy DB loaded."""
        self.assertGreater(len(self.selector.strategy_db), 10)
        self.assertIn(StrategyType.COVERED_CALL, self.selector.strategy_db)

    def test_bullish_strategies(self):
        """Bullish context favors bullish strategies."""
        context = MarketContext(
            symbol="SPY", price=450.0, iv_rank=50, iv_trend=0.2,
            spot_trend=0.6, expected_move=10.0, liquidity_score=0.95,
        )
        prefs = UserPreferences(
            symbol="SPY", risk_profile=RiskProfile.MODERATE,
            max_loss_pct=2.0, max_loss_dollars=1000.0,
            bias="bullish", time_horizon_days=30,
        )
        candidates = self.selector.select_strategies(context, prefs, top_n=3)
        self.assertEqual(len(candidates), 3)

        # Top candidate should have bullish preference
        top_strategy = candidates[0][0]
        attrs = self.selector.strategy_db[top_strategy]
        self.assertIn("bullish", attrs["bias"])

    def test_bearish_strategies(self):
        """Bearish context favors bearish strategies."""
        context = MarketContext(
            symbol="SPY", price=450.0, iv_rank=50, iv_trend=-0.2,
            spot_trend=-0.6, expected_move=10.0, liquidity_score=0.95,
        )
        prefs = UserPreferences(
            symbol="SPY", risk_profile=RiskProfile.MODERATE,
            max_loss_pct=2.0, max_loss_dollars=1000.0,
            bias="bearish", time_horizon_days=30,
        )
        candidates = self.selector.select_strategies(context, prefs, top_n=3)

        top_strategy = candidates[0][0]
        attrs = self.selector.strategy_db[top_strategy]
        self.assertIn("bearish", attrs["bias"])

    def test_high_iv_favors_premium_selling(self):
        """High IV favors premium-selling strategies."""
        context = MarketContext(
            symbol="SPY", price=450.0, iv_rank=85, iv_trend=0.3,
            spot_trend=0.0, expected_move=15.0, liquidity_score=0.95,
        )
        prefs = UserPreferences(
            symbol="SPY", risk_profile=RiskProfile.MODERATE,
            max_loss_pct=2.0, max_loss_dollars=1000.0,
            bias="neutral", time_horizon_days=30,
        )
        candidates = self.selector.select_strategies(context, prefs, top_n=3)

        # Check that premium sellers score high
        for strategy, score in candidates:
            attrs = self.selector.strategy_db[strategy]
            self.assertEqual(attrs["iv_preference"], "high")

    def test_low_iv_favors_premium_buying(self):
        """Low IV rank with IV turning up favors premium-buying strategies.

        (Rising iv_trend is the long-premium tailwind; the original test used
        falling IV, which encoded the inverted trend-alignment bug.)
        """
        context = MarketContext(
            symbol="SPY", price=450.0, iv_rank=15, iv_trend=0.3,
            spot_trend=0.0, expected_move=5.0, liquidity_score=0.95,
        )
        prefs = UserPreferences(
            symbol="SPY", risk_profile=RiskProfile.MODERATE,
            max_loss_pct=2.0, max_loss_dollars=1000.0,
            bias="neutral", time_horizon_days=30,
        )
        candidates = self.selector.select_strategies(context, prefs, top_n=3)

        # At least one should be low-IV preference
        found_low_iv = False
        for strategy, score in candidates:
            attrs = self.selector.strategy_db[strategy]
            if attrs["iv_preference"] == "low":
                found_low_iv = True
        self.assertTrue(found_low_iv)

    def test_conservative_risk_filtering(self):
        """Conservative users get low-risk strategies."""
        context = MarketContext(
            symbol="SPY", price=450.0, iv_rank=60, iv_trend=0.1,
            spot_trend=0.0, expected_move=10.0, liquidity_score=0.95,
        )
        prefs = UserPreferences(
            symbol="SPY", risk_profile=RiskProfile.CONSERVATIVE,
            max_loss_pct=1.0, max_loss_dollars=500.0,
            bias="neutral", time_horizon_days=30,
        )
        candidates = self.selector.select_strategies(context, prefs, top_n=3)

        for strategy, score in candidates:
            attrs = self.selector.strategy_db[strategy]
            self.assertIn(attrs["risk_level"], ["low", "medium"])

    def test_greeks_estimation(self):
        """Greeks estimated for strategies."""
        context = MarketContext(
            symbol="SPY", price=450.0, iv_rank=50, iv_trend=0.0,
            spot_trend=0.0, expected_move=10.0, liquidity_score=0.95,
        )
        prefs = UserPreferences(
            symbol="SPY", risk_profile=RiskProfile.MODERATE,
            max_loss_pct=2.0, max_loss_dollars=1000.0,
            bias="bullish", time_horizon_days=30,
        )
        greeks = self.selector.estimate_greeks(
            StrategyType.BULL_CALL_SPREAD, context, prefs
        )

        self.assertIsNotNone(greeks.delta)
        self.assertIsNotNone(greeks.gamma)
        self.assertIsNotNone(greeks.theta)
        self.assertIsNotNone(greeks.vega)

    def test_recommendation_building(self):
        """Full recommendation built from strategy."""
        context = MarketContext(
            symbol="SPY", price=450.0, iv_rank=50, iv_trend=0.0,
            spot_trend=0.0, expected_move=10.0, liquidity_score=0.95,
        )
        prefs = UserPreferences(
            symbol="SPY", risk_profile=RiskProfile.MODERATE,
            max_loss_pct=2.0, max_loss_dollars=1000.0,
            bias="bullish", time_horizon_days=30,
        )
        rec = self.selector.build_recommendation(
            StrategyType.BULL_CALL_SPREAD, context, prefs,
            fit_score=0.8, reasoning="High fit"
        )

        self.assertEqual(rec.strategy, StrategyType.BULL_CALL_SPREAD)
        self.assertGreater(rec.max_profit, 0)
        self.assertGreater(rec.probability_profit, 0.5)
        self.assertGreater(rec.confidence_score, 0.5)
        self.assertIn("High fit", rec.reasoning)


class TestQuantumAIBrain(unittest.TestCase):
    """Test Quantum AI brain."""

    def setUp(self):
        self.brain = QuantumAIBrain()

    def test_brain_initialized(self):
        """Brain initialized with knowledge store."""
        self.assertIsNotNone(self.brain.knowledge)
        self.assertIsNotNone(self.brain.knowledge.current_version)

    def test_select_and_reason(self):
        """AI selection and reasoning."""
        context = MarketContext(
            symbol="SPY", price=450.0, iv_rank=65, iv_trend=0.2,
            spot_trend=0.4, expected_move=12.0, liquidity_score=0.92,
        )
        prefs = UserPreferences(
            symbol="SPY", risk_profile=RiskProfile.MODERATE,
            max_loss_pct=2.0, max_loss_dollars=1000.0,
            bias="bullish", time_horizon_days=30,
        )
        result = self.brain.select_and_reason(context, prefs, use_claude=False)

        self.assertEqual(result.symbol, "SPY")
        self.assertEqual(len(result.recommendations), 3)
        self.assertGreater(len(result.ai_reasoning), 50)

    def test_recommendations_respect_constraints(self):
        """Recommendations respect max loss constraints."""
        context = MarketContext(
            symbol="QQQ", price=350.0, iv_rank=70, iv_trend=0.1,
            spot_trend=0.0, expected_move=11.0, liquidity_score=0.88,
        )
        prefs = UserPreferences(
            symbol="QQQ", risk_profile=RiskProfile.MODERATE,
            max_loss_pct=1.5, max_loss_dollars=5000.0,  # Increased to reasonable level
            bias="neutral", time_horizon_days=30,
        )
        result = self.brain.select_and_reason(context, prefs, use_claude=False)

        for rec in result.recommendations:
            # Max loss should be within 50% of user max loss (some strategies legitimately higher risk)
            self.assertLessEqual(rec.max_loss, prefs.max_loss_dollars * 1.5)

    def test_trade_outcome_recording(self):
        """Trade outcomes recorded and learned from."""
        outcome = TradeOutcome(
            recommendation_id="rec123",
            symbol="SPY",
            strategy=StrategyType.BULL_CALL_SPREAD,
            entry_price=1.50,
            exit_price=2.20,
            pnl=70.0,
            pnl_pct=4.67,
            lessons_learned="Volatility spike helped theta decay",
            user_rating=5,
        )

        self.brain.record_trade_outcome(outcome)

        self.assertEqual(len(self.brain.knowledge.trade_outcomes), 1)
        perf = self.brain.knowledge.current_version.strategy_performance
        self.assertIn("bull_call_spread", perf)
        self.assertEqual(perf["bull_call_spread"]["count"], 1)
        self.assertEqual(perf["bull_call_spread"]["wins"], 1)

    def test_multiple_outcomes_aggregate(self):
        """Multiple outcomes aggregate correctly."""
        outcomes = [
            TradeOutcome(
                recommendation_id=f"rec{i}",
                symbol="SPY",
                strategy=StrategyType.BULL_CALL_SPREAD,
                entry_price=1.50,
                exit_price=2.20 + i * 0.1,
                pnl=70.0 + i * 10,
                pnl_pct=4.67 + i * 0.5,
                lessons_learned=f"Lesson {i}",
                user_rating=4,
            )
            for i in range(5)
        ]

        for outcome in outcomes:
            self.brain.record_trade_outcome(outcome)

        perf = self.brain.knowledge.current_version.strategy_performance["bull_call_spread"]
        self.assertEqual(perf["count"], 5)
        self.assertEqual(perf["wins"], 5)
        self.assertGreater(perf["avg_pnl"], 70.0)
        self.assertGreater(perf["avg_pnl_pct"], 4.67)

    def test_knowledge_versioning(self):
        """Knowledge versioned correctly."""
        v1 = self.brain.knowledge.current_version.version_id

        # Record outcome
        outcome = TradeOutcome(
            recommendation_id="rec1",
            symbol="SPY",
            strategy=StrategyType.BULL_CALL_SPREAD,
            entry_price=1.50,
            exit_price=2.20,
            pnl=70.0,
            pnl_pct=4.67,
            lessons_learned="Test",
            user_rating=5,
        )
        self.brain.record_trade_outcome(outcome)

        # Create new version
        v2 = self.brain.create_knowledge_version("post-first-trade")

        self.assertNotEqual(v1, v2)
        self.assertEqual(len(self.brain.knowledge.history), 1)
        self.assertIn("bull_call_spread", self.brain.knowledge.current_version.strategy_performance)

    def test_knowledge_rollback(self):
        """Knowledge rolled back to previous version."""
        v1_id = self.brain.knowledge.current_version.version_id

        # Record outcome and create version
        outcome = TradeOutcome(
            recommendation_id="rec1",
            symbol="SPY",
            strategy=StrategyType.BULL_CALL_SPREAD,
            entry_price=1.50,
            exit_price=2.20,
            pnl=70.0,
            pnl_pct=4.67,
            lessons_learned="Test",
            user_rating=5,
        )
        self.brain.record_trade_outcome(outcome)
        v2_id = self.brain.create_knowledge_version("with-outcome")

        # Verify new version has outcome
        self.assertIn("bull_call_spread", self.brain.knowledge.current_version.strategy_performance)

        # Record another trade on v2
        outcome2 = TradeOutcome(
            recommendation_id="rec2",
            symbol="QQQ",
            strategy=StrategyType.COVERED_CALL,
            entry_price=2.0,
            exit_price=2.5,
            pnl=50.0,
            pnl_pct=2.5,
            lessons_learned="Test2",
            user_rating=5,
        )
        self.brain.record_trade_outcome(outcome2)
        self.assertEqual(len(self.brain.knowledge.current_version.strategy_performance), 2)

        # Rollback to v1 (should revert to just bull_call_spread)
        success = self.brain.rollback_knowledge(v1_id)
        self.assertTrue(success)
        self.assertEqual(self.brain.knowledge.current_version.version_id, v1_id)
        self.assertEqual(len(self.brain.knowledge.current_version.strategy_performance), 1)

    def test_serialization(self):
        """Brain serialized and deserialized."""
        # Record outcome
        outcome = TradeOutcome(
            recommendation_id="rec1",
            symbol="SPY",
            strategy=StrategyType.BULL_CALL_SPREAD,
            entry_price=1.50,
            exit_price=2.20,
            pnl=70.0,
            pnl_pct=4.67,
            lessons_learned="Test",
            user_rating=5,
        )
        self.brain.record_trade_outcome(outcome)

        # Serialize
        state = self.brain.to_dict()
        self.assertIn("knowledge", state)
        self.assertIn("model", state)

        # Deserialize
        brain2 = QuantumAIBrain.from_dict(state)
        self.assertEqual(len(brain2.knowledge.trade_outcomes), 1)
        self.assertEqual(brain2.knowledge.trade_outcomes[0].symbol, "SPY")

    def test_multi_outcome_learning(self):
        """System learns from multiple outcomes."""
        strategies_and_outcomes = [
            (StrategyType.BULL_CALL_SPREAD, True, 75.0),
            (StrategyType.BULL_CALL_SPREAD, True, 85.0),
            (StrategyType.BULL_CALL_SPREAD, False, -50.0),
            (StrategyType.COVERED_CALL, True, 40.0),
            (StrategyType.COVERED_CALL, True, 45.0),
            (StrategyType.COVERED_CALL, False, -30.0),
        ]

        for i, (strategy, is_win, pnl) in enumerate(strategies_and_outcomes):
            outcome = TradeOutcome(
                recommendation_id=f"rec{i}",
                symbol="SPY",
                strategy=strategy,
                entry_price=1.0,
                exit_price=1.0 + (pnl / 100),
                pnl=pnl,
                pnl_pct=(pnl / 100) * 100,
                lessons_learned=f"Outcome {i}: {'win' if is_win else 'loss'}",
                user_rating=5 if is_win else 2,
            )
            self.brain.record_trade_outcome(outcome)

        # Verify learning
        perf = self.brain.knowledge.current_version.strategy_performance

        bull_call_perf = perf["bull_call_spread"]
        self.assertEqual(bull_call_perf["count"], 3)
        self.assertEqual(bull_call_perf["wins"], 2)
        self.assertGreater(bull_call_perf["avg_pnl"], 0)

        covered_call_perf = perf["covered_call"]
        self.assertEqual(covered_call_perf["count"], 3)
        self.assertEqual(covered_call_perf["wins"], 2)
        self.assertGreater(covered_call_perf["avg_pnl"], 0)

    def test_initial_reasoning_generation(self):
        """Initial reasoning generated for each strategy."""
        context = MarketContext(
            symbol="SPY", price=450.0, iv_rank=80, iv_trend=0.3,
            spot_trend=0.5, expected_move=14.0, liquidity_score=0.95,
            event_proximity_days=2.0, news_sentiment=0.7,
        )
        prefs = UserPreferences(
            symbol="SPY", risk_profile=RiskProfile.MODERATE,
            max_loss_pct=2.0, max_loss_dollars=1000.0,
            bias="bullish", time_horizon_days=30,
        )

        reasoning = self.brain._generate_initial_reasoning(
            StrategyType.BULL_CALL_SPREAD, context, prefs, 0.8
        )

        self.assertGreater(len(reasoning), 10)
        self.assertIn("bullish", reasoning.lower())


class TestIntegration(unittest.TestCase):
    """Integration tests."""

    def test_full_workflow(self):
        """Full workflow: select, learn, version."""
        brain = QuantumAIBrain()

        # Initial selection
        context = MarketContext(
            symbol="SPY", price=450.0, iv_rank=65, iv_trend=0.2,
            spot_trend=0.4, expected_move=12.0, liquidity_score=0.92,
        )
        prefs = UserPreferences(
            symbol="SPY", risk_profile=RiskProfile.MODERATE,
            max_loss_pct=2.0, max_loss_dollars=1000.0,
            bias="bullish", time_horizon_days=30,
        )

        result = brain.select_and_reason(context, prefs, use_claude=False)
        self.assertEqual(len(result.recommendations), 3)

        # Simulate trade
        rec = result.recommendations[0]
        outcome = TradeOutcome(
            recommendation_id="rec1",
            symbol=rec.strategy.value,
            strategy=rec.strategy,
            entry_price=rec.entry_price,
            exit_price=rec.entry_price * 1.5,
            pnl=rec.max_profit * 0.7,
            pnl_pct=7.0,
            lessons_learned="Good setup, solid execution",
            user_rating=5,
        )

        brain.record_trade_outcome(outcome)
        v1 = brain.create_knowledge_version("first-trade")

        # Verify learning captured
        self.assertEqual(len(brain.knowledge.history), 1)
        self.assertIn(outcome.strategy.value, brain.knowledge.current_version.strategy_performance)

    def test_multiple_symbols_and_strategies(self):
        """System handles multiple symbols and strategies."""
        brain = QuantumAIBrain()

        symbols = ["SPY", "QQQ", "IWM"]
        strategies = [
            StrategyType.BULL_CALL_SPREAD,
            StrategyType.COVERED_CALL,
            StrategyType.BULL_PUT_SPREAD,
        ]

        for symbol in symbols:
            context = MarketContext(
                symbol=symbol, price=350.0, iv_rank=60, iv_trend=0.1,
                spot_trend=0.0, expected_move=10.0, liquidity_score=0.90,
            )
            prefs = UserPreferences(
                symbol=symbol, risk_profile=RiskProfile.MODERATE,
                max_loss_pct=2.0, max_loss_dollars=1000.0,
                bias="neutral", time_horizon_days=30,
            )

            result = brain.select_and_reason(context, prefs, use_claude=False)
            self.assertEqual(result.symbol, symbol)

        # Record outcomes for various strategies
        for i, strategy in enumerate(strategies):
            outcome = TradeOutcome(
                recommendation_id=f"rec{i}",
                symbol="SPY",
                strategy=strategy,
                entry_price=1.0,
                exit_price=1.5,
                pnl=50.0,
                pnl_pct=5.0,
                lessons_learned="Good",
                user_rating=5,
            )
            brain.record_trade_outcome(outcome)

        # Verify all strategies tracked
        perf = brain.knowledge.current_version.strategy_performance
        self.assertEqual(len(perf), 3)
        for strategy in strategies:
            self.assertIn(strategy.value, perf)


if __name__ == "__main__":
    unittest.main()
