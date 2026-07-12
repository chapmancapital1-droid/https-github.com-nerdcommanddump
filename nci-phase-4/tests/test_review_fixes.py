"""
Regression tests for the code-review findings (2026-07-12 review pass).

Locks in the fixes for:
  - bear put spread mis-tagged as positive time decay
  - sign-inverted IV-trend alignment scoring
  - max_loss_dollars computed but never enforced
  - rollback corrupting knowledge history
  - short-premium strategies with vega 0.0
  - probability_profit floor of ~0.72 for poor fits
"""

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from nci_strategy_selector import (
    MarketContext,
    QuantumAIBrain,
    RiskProfile,
    StrategySelector,
    StrategyType,
    TradeOutcome,
    UserPreferences,
)
from nci_strategy_selector.claude_client import ClaudeReasoningClient


def make_context(**overrides) -> MarketContext:
    base = dict(
        symbol="SPY", price=450.0, iv_rank=65, iv_trend=0.2,
        spot_trend=0.4, expected_move=12.0, liquidity_score=0.92,
    )
    base.update(overrides)
    return MarketContext(**base)


def make_prefs(**overrides) -> UserPreferences:
    base = dict(
        symbol="SPY", risk_profile=RiskProfile.MODERATE,
        max_loss_pct=2.0, max_loss_dollars=1000.0,
        bias="bullish", time_horizon_days=30,
    )
    base.update(overrides)
    return UserPreferences(**base)


class TestStrategyAttributes(unittest.TestCase):
    """Finding: bear put spread tagged positive time decay (it's a debit spread)."""

    def setUp(self):
        self.db = StrategySelector().strategy_db

    def test_bear_put_spread_is_long_premium(self):
        attrs = self.db[StrategyType.BEAR_PUT_SPREAD]
        self.assertEqual(attrs["time_decay"], "negative")

    def test_debit_spread_twins_agree(self):
        # Bull call and bear put are the two debit verticals; their premium
        # profile must match.
        bull_call = self.db[StrategyType.BULL_CALL_SPREAD]
        bear_put = self.db[StrategyType.BEAR_PUT_SPREAD]
        self.assertEqual(bull_call["time_decay"], bear_put["time_decay"])
        self.assertEqual(bull_call["iv_preference"], bear_put["iv_preference"])

    def test_credit_verticals_are_positive_decay(self):
        for st in (StrategyType.BEAR_CALL_SPREAD, StrategyType.BULL_PUT_SPREAD):
            self.assertEqual(self.db[st]["time_decay"], "positive", st)


class TestIvTrendAlignment(unittest.TestCase):
    """Finding: rising IV rewarded short premium (backwards)."""

    def _score_of(self, strategy: StrategyType, iv_trend: float) -> float:
        selector = StrategySelector()
        context = make_context(iv_rank=50, iv_trend=iv_trend, spot_trend=0.0)
        prefs = make_prefs(bias="neutral")
        scores = dict(selector.select_strategies(context, prefs, top_n=13))
        return scores[strategy]

    def test_falling_iv_helps_short_premium(self):
        # Iron condor is short vega: falling IV must score >= rising IV.
        falling = self._score_of(StrategyType.IRON_CONDOR, iv_trend=-0.5)
        rising = self._score_of(StrategyType.IRON_CONDOR, iv_trend=+0.5)
        self.assertGreater(falling, rising)

    def test_rising_iv_helps_long_premium(self):
        # Long straddle is long vega: rising IV must score >= falling IV.
        rising = self._score_of(StrategyType.LONG_STRADDLE, iv_trend=+0.5)
        falling = self._score_of(StrategyType.LONG_STRADDLE, iv_trend=-0.5)
        self.assertGreater(rising, falling)


class TestMaxLossEnforcement(unittest.TestCase):
    """Finding: max_loss_dollars set risk_rating but never blocked anything."""

    def test_no_recommendation_exceeds_user_limit(self):
        brain = QuantumAIBrain(claude_client=ClaudeReasoningClient(api_key=""))
        prefs = make_prefs(bias="neutral", max_loss_dollars=500.0)
        result = brain.select_and_reason(
            make_context(symbol="QQQ", price=350.0), prefs, use_claude=False
        )
        self.assertGreater(len(result.recommendations), 0)
        for rec in result.recommendations:
            self.assertLessEqual(rec.max_loss, prefs.max_loss_dollars)

    def test_tiny_limit_yields_empty_but_reasoned_result(self):
        brain = QuantumAIBrain(claude_client=ClaudeReasoningClient(api_key=""))
        prefs = make_prefs(max_loss_dollars=1.0)
        result = brain.select_and_reason(make_context(), prefs, use_claude=True)
        self.assertEqual(len(result.recommendations), 0)
        self.assertIn("no strategy passed the risk gate", result.ai_reasoning)

    def test_reasoning_no_longer_makes_false_claims(self):
        brain = QuantumAIBrain(claude_client=ClaudeReasoningClient(api_key=""))
        prefs = make_prefs(max_loss_dollars=500.0)
        result = brain.select_and_reason(make_context(), prefs, use_claude=True)
        # Whatever is shown genuinely respects the limit now.
        for rec in result.recommendations:
            self.assertLessEqual(rec.max_loss, 500.0)


class TestRollbackHistoryIntegrity(unittest.TestCase):
    """Finding: rollback removed the target from history and broke ordering."""

    def _brain_with_versions(self):
        brain = QuantumAIBrain(claude_client=ClaudeReasoningClient(api_key=""))
        ids = [brain.knowledge.current_version.version_id]
        for i in range(2):
            brain.record_trade_outcome(TradeOutcome(
                recommendation_id=f"r{i}", symbol="SPY",
                strategy=StrategyType.BULL_CALL_SPREAD,
                entry_price=1.0, exit_price=1.5, pnl=50.0, pnl_pct=5.0,
                lessons_learned="", user_rating=5,
            ))
            ids.append(brain.create_knowledge_version(f"v{i}"))
        return brain, ids

    def test_rollback_keeps_target_in_history(self):
        brain, ids = self._brain_with_versions()
        history_before = [v.version_id for v in brain.knowledge.history]
        self.assertTrue(brain.rollback_knowledge(ids[0]))
        history_after = [v.version_id for v in brain.knowledge.history]
        # Append-only: previous entries unchanged, old current appended.
        self.assertEqual(history_after[:len(history_before)], history_before)
        self.assertIn(ids[0], history_after)

    def test_can_rollback_to_same_version_twice(self):
        brain, ids = self._brain_with_versions()
        self.assertTrue(brain.rollback_knowledge(ids[0]))
        brain.create_knowledge_version("after-first-rollback")
        self.assertTrue(brain.rollback_knowledge(ids[0]))

    def test_rollback_copy_is_isolated_from_history(self):
        brain, ids = self._brain_with_versions()
        brain.rollback_knowledge(ids[1])
        # Mutating the rolled-back current must not corrupt the history copy.
        brain.knowledge.current_version.user_learnings.append("mutation")
        historical = next(
            v for v in brain.knowledge.history if v.version_id == ids[1]
        )
        self.assertNotIn("mutation", historical.user_learnings)

    def test_version_ids_are_unique_even_in_same_second(self):
        brain, _ = self._brain_with_versions()
        new_ids = [brain.create_knowledge_version(f"burst-{i}") for i in range(5)]
        self.assertEqual(len(set(new_ids)), 5)


class TestShortPremiumGreeks(unittest.TestCase):
    """Finding: CSP / short straddle / short strangle defaulted to vega 0.0."""

    def setUp(self):
        self.selector = StrategySelector()
        self.context = make_context()
        self.prefs = make_prefs()

    def _greeks(self, strategy):
        return self.selector.estimate_greeks(strategy, self.context, self.prefs)

    def test_cash_secured_put_is_short_premium(self):
        g = self._greeks(StrategyType.CASH_SECURED_PUT)
        self.assertGreater(g.theta, 0)
        self.assertLess(g.vega, 0)

    def test_short_straddle_strangle_short_vega(self):
        for st in (StrategyType.SHORT_STRADDLE, StrategyType.SHORT_STRANGLE):
            g = self._greeks(st)
            self.assertGreater(g.theta, 0, st)
            self.assertLess(g.vega, 0, st)

    def test_long_straddle_strangle_long_vega(self):
        for st in (StrategyType.LONG_STRADDLE, StrategyType.LONG_STRANGLE):
            g = self._greeks(st)
            self.assertLess(g.theta, 0, st)
            self.assertGreater(g.vega, 0, st)

    def test_bear_spreads_have_negative_delta(self):
        for st in (StrategyType.BEAR_CALL_SPREAD, StrategyType.BEAR_PUT_SPREAD):
            self.assertLess(self._greeks(st).delta, 0, st)


class TestProbabilityFloor(unittest.TestCase):
    """Finding: probability_profit could never go below ~0.72."""

    def test_poor_fit_maps_below_coin_flip(self):
        selector = StrategySelector()
        rec = selector.build_recommendation(
            StrategyType.LONG_STRADDLE, make_context(), make_prefs(),
            fit_score=0.1, reasoning="poor fit",
        )
        self.assertLess(rec.probability_profit, 0.5)

    def test_strong_fit_still_reads_favorably(self):
        selector = StrategySelector()
        rec = selector.build_recommendation(
            StrategyType.BULL_CALL_SPREAD, make_context(), make_prefs(),
            fit_score=3.0, reasoning="strong fit",
        )
        self.assertGreater(rec.probability_profit, 0.7)
        self.assertLessEqual(rec.probability_profit, 0.95)


if __name__ == "__main__":
    unittest.main()
