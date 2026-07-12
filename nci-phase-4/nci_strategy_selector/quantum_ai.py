"""
Quantum AI Brain — Claude-powered reasoning for strategy selection.

Provides intelligent, context-aware strategy recommendations with
interactive learning and versioned knowledge.
"""

from __future__ import annotations

from .models import (
    StrategyType, MarketContext, UserPreferences, StrategySelectionResult,
    StrategyRecommendation, TradeOutcome, KnowledgeStore, VersionedKnowledge,
)
from .strategy_selector import StrategySelector
from .claude_client import ClaudeReasoningClient
from .feedback import ConfidenceCalibrator
from .reasoning_engine import ReasoningSession
from typing import Optional
import json
import time
import uuid
import copy


class QuantumAIBrain:
    """Claude-powered AI brain for intelligent strategy selection."""

    def __init__(
        self,
        knowledge_store: Optional[KnowledgeStore] = None,
        claude_client: Optional[ClaudeReasoningClient] = None,
        calibrator: Optional[ConfidenceCalibrator] = None,
    ):
        self.selector = StrategySelector()
        self.knowledge = knowledge_store or self._init_knowledge_store()
        self.claude = claude_client or ClaudeReasoningClient()
        self.calibrator = calibrator or ConfidenceCalibrator()
        self.model = self.claude.model
        # Maps recommendation_id → predicted confidence, so outcomes can
        # be matched back for calibration.
        self._pending_predictions: dict[str, tuple[StrategyType, float]] = {}

    def _init_knowledge_store(self) -> KnowledgeStore:
        """Initialize a new knowledge store."""
        initial_version = VersionedKnowledge(
            version_id=f"v1.0-{int(time.time())}",
            created_at=time.time(),
            parent_version=None,
            strategy_performance={},
            context_patterns={},
            user_learnings=[],
            mc_validated=False,
        )
        return KnowledgeStore(current_version=initial_version)

    def select_and_reason(
        self,
        context: MarketContext,
        prefs: UserPreferences,
        use_claude: bool = True,
    ) -> StrategySelectionResult:
        """
        Select strategies and provide AI reasoning.

        Args:
            context: Current market conditions
            prefs: User preferences and constraints
            use_claude: Whether to use Claude API (True) or fallback reasoning (False)

        Returns:
            StrategySelectionResult with recommendations and AI explanation
        """
        # Get strategy candidates
        candidates = self.selector.select_strategies(context, prefs, top_n=5)

        # Build initial recommendations with calibrated confidence
        recommendations = []
        for strategy, fit_score in candidates[:3]:
            reasoning_text = self._generate_initial_reasoning(strategy, context, prefs, fit_score)
            rec = self.selector.build_recommendation(
                strategy, context, prefs, fit_score, reasoning_text
            )
            # Phase 5: adjust confidence by learned calibration factor
            rec.confidence_score = self.calibrator.adjust(strategy, rec.confidence_score)
            recommendations.append(rec)

        # Re-rank by calibrated confidence so learning affects ordering
        recommendations.sort(key=lambda r: r.confidence_score, reverse=True)

        # Get AI reasoning
        if use_claude:
            ai_reasoning = self._get_claude_reasoning(context, prefs, recommendations)
        else:
            ai_reasoning = self._fallback_reasoning(context, prefs, recommendations)

        return StrategySelectionResult(
            symbol=context.symbol,
            recommendations=recommendations,
            ai_reasoning=ai_reasoning,
            model_used=self.model if use_claude else "fallback",
        )

    def _generate_initial_reasoning(
        self,
        strategy: StrategyType,
        context: MarketContext,
        prefs: UserPreferences,
        fit_score: float,
    ) -> str:
        """Generate initial reasoning for a strategy."""
        reasons = []

        if prefs.bias == "bullish" and strategy in [
            StrategyType.BULL_CALL_SPREAD,
            StrategyType.BULL_PUT_SPREAD,
        ]:
            reasons.append("Aligns with bullish bias")

        if prefs.bias == "bearish" and strategy in [
            StrategyType.BEAR_CALL_SPREAD,
            StrategyType.BEAR_PUT_SPREAD,
        ]:
            reasons.append("Aligns with bearish bias")

        if context.iv_rank > 70:
            reasons.append("High IV environment — favors premium selling strategies")
        elif context.iv_rank < 30:
            reasons.append("Low IV environment — consider premium buying strategies")

        if context.event_proximity_days and context.event_proximity_days < 3:
            reasons.append(f"Near-term event ({context.event_proximity_days:.1f} days)")

        if context.liquidity_score > 0.8:
            reasons.append("High liquidity — tight spreads expected")

        if abs(context.news_sentiment) > 0.6:
            direction = "positive" if context.news_sentiment > 0 else "negative"
            reasons.append(f"Strong {direction} news sentiment")

        return " • ".join(reasons) if reasons else "Technical fit detected"

    def _get_claude_reasoning(
        self,
        context: MarketContext,
        prefs: UserPreferences,
        recommendations: list[StrategyRecommendation],
    ) -> str:
        """
        Get reasoning from Claude API (Phase 5: live integration).

        Makes a real Messages API call through ClaudeReasoningClient when
        ANTHROPIC_API_KEY is configured; otherwise returns the structured
        template so the product keeps working offline.
        """
        prompt = self._build_reasoning_prompt(context, prefs, recommendations)

        if self.claude.available:
            resp = self.claude.complete(
                messages=[{"role": "user", "content": prompt}],
                system=(
                    "You are Quantum AI, the options-strategy reasoning layer of "
                    "the NCI nerdcommand trading assistant. Analyze the provided "
                    "recommendations against the market context and user "
                    "constraints. Be quantitative and honest about risk. End "
                    "with a one-line educational-use disclaimer."
                ),
            )
            if resp.ok and resp.text.strip():
                return resp.text.strip()
            # fall through to template with a note
            return (
                f"[Claude unavailable ({resp.error}) — structured fallback]\n"
                + self._template_reasoning(context, prefs, recommendations)
            )

        return self._template_reasoning(context, prefs, recommendations)

    def _template_reasoning(
        self,
        context: MarketContext,
        prefs: UserPreferences,
        recommendations: list[StrategyRecommendation],
    ) -> str:
        """Deterministic structured reasoning used when the API is offline."""
        reasoning = f"""
Based on market conditions ({context.symbol} at ${context.price:.2f}):

1. **Market Assessment**: IV Rank at {context.iv_rank:.0f}% suggests a {self._iv_regime(context.iv_rank)}
   regime, with {self._trend_description(context.spot_trend)} directional bias.

2. **Strategy Fit**:
   - {recommendations[0].strategy.value.replace('_', ' ').title()} (Confidence: {recommendations[0].confidence_score:.0%})
     Rationale: {recommendations[0].reasoning}

   - {recommendations[1].strategy.value.replace('_', ' ').title()} (Confidence: {recommendations[1].confidence_score:.0%})
     Rationale: {recommendations[1].reasoning}

   - {recommendations[2].strategy.value.replace('_', ' ').title()} (Confidence: {recommendations[2].confidence_score:.0%})
     Rationale: {recommendations[2].reasoning}

3. **Risk-Adjusted Priority**: Recommend {recommendations[0].strategy.value.replace('_', ' ').title()}
   for a {self._probability_description(recommendations[0].probability_profit)} probability of profit.

4. **Portfolio Fit**: All recommendations respect ${prefs.max_loss_dollars:.2f} max loss constraint.
   Current expected move: ${context.expected_move:.2f}
"""
        return reasoning.strip()

    def _fallback_reasoning(
        self,
        context: MarketContext,
        prefs: UserPreferences,
        recommendations: list[StrategyRecommendation],
    ) -> str:
        """Fallback reasoning when Claude API unavailable."""
        lines = [
            f"Strategy selection for {context.symbol} at ${context.price:.2f}",
            f"IV Rank: {context.iv_rank:.0f}% | IV Trend: {context.iv_trend:+.2f}",
            f"Expected Move: ${context.expected_move:.2f}",
            "",
            "Top Recommendations:",
        ]

        for i, rec in enumerate(recommendations, 1):
            lines.append(f"  {i}. {rec.strategy.value.title()}")
            lines.append(f"     Confidence: {rec.confidence_score:.0%} | Risk: {rec.risk_rating}")
            lines.append(f"     Max Profit: ${rec.max_profit:.2f} | Max Loss: ${rec.max_loss:.2f}")

        return "\n".join(lines)

    def _build_reasoning_prompt(
        self,
        context: MarketContext,
        prefs: UserPreferences,
        recommendations: list[StrategyRecommendation],
    ) -> str:
        """Build prompt for Claude API."""
        rec_text = "\n".join([
            f"- {r.strategy.value}: ${r.entry_price:.2f} entry, "
            f"${r.max_profit:.2f} max profit, ${r.max_loss:.2f} max loss"
            for r in recommendations
        ])

        return f"""
As an options trading advisor, analyze these strategy recommendations:

Market Context:
- Symbol: {context.symbol} @ ${context.price:.2f}
- IV Rank: {context.iv_rank:.0f}% ({self._iv_regime(context.iv_rank)})
- Expected Move: ${context.expected_move:.2f}
- Liquidity Score: {context.liquidity_score:.2f}
- News Sentiment: {context.news_sentiment:+.2f}

User Preferences:
- Risk Profile: {prefs.risk_profile.value}
- Bias: {prefs.bias}
- Max Loss: ${prefs.max_loss_dollars:.2f}
- Time Horizon: {prefs.time_horizon_days} days

Recommended Strategies:
{rec_text}

Provide concise reasoning for the top recommendation and why it fits the current market environment.
Focus on risk-adjusted probability and alignment with user constraints.
"""

    def _iv_regime(self, iv_rank: float) -> str:
        if iv_rank > 70:
            return "high IV (premium selling favored)"
        elif iv_rank < 30:
            return "low IV (premium buying favored)"
        else:
            return "moderate IV"

    def _trend_description(self, spot_trend: float) -> str:
        if spot_trend > 0.3:
            return "strong bullish"
        elif spot_trend > 0:
            return "mild bullish"
        elif spot_trend < -0.3:
            return "strong bearish"
        elif spot_trend < 0:
            return "mild bearish"
        else:
            return "neutral"

    def _probability_description(self, prob: float) -> str:
        if prob > 0.75:
            return "high"
        elif prob > 0.60:
            return "moderate-to-good"
        elif prob > 0.50:
            return "moderate"
        else:
            return "low"

    def start_reasoning_session(
        self,
        context: MarketContext,
        prefs: UserPreferences,
        result: StrategySelectionResult,
    ) -> ReasoningSession:
        """
        Phase 5: open a multi-turn dialogue about a selection.

        The returned session keeps full conversation history; call
        session.ask("...") repeatedly to interrogate the recommendation.
        """
        return ReasoningSession(self.claude, context, prefs, result)

    def register_prediction(
        self, recommendation_id: str, rec: StrategyRecommendation
    ) -> None:
        """
        Phase 5: remember a recommendation's predicted confidence so the
        eventual outcome can calibrate future confidence for that strategy.
        Call this when the user actually takes the trade.
        """
        self._pending_predictions[recommendation_id] = (
            rec.strategy,
            rec.confidence_score,
        )

    def record_trade_outcome(self, outcome: TradeOutcome) -> None:
        """Record a trade outcome for learning."""
        self.knowledge.trade_outcomes.append(outcome)

        # Phase 5: close the calibration loop if we tracked the prediction.
        pending = self._pending_predictions.pop(outcome.recommendation_id, None)
        if pending is not None:
            strategy, predicted_confidence = pending
            self.calibrator.observe(strategy, predicted_confidence, outcome)

        # Update strategy performance tracking
        strategy_name = outcome.strategy.value
        if strategy_name not in self.knowledge.current_version.strategy_performance:
            self.knowledge.current_version.strategy_performance[strategy_name] = {
                "count": 0,
                "wins": 0,
                "avg_pnl": 0.0,
                "avg_pnl_pct": 0.0,
            }

        perf = self.knowledge.current_version.strategy_performance[strategy_name]
        perf["count"] += 1
        if outcome.pnl > 0:
            perf["wins"] += 1
        perf["avg_pnl"] = (perf["avg_pnl"] * (perf["count"] - 1) + outcome.pnl) / perf["count"]
        perf["avg_pnl_pct"] = (
            (perf["avg_pnl_pct"] * (perf["count"] - 1) + outcome.pnl_pct) / perf["count"]
        )

        # Extract learnings
        if outcome.lessons_learned:
            self.knowledge.current_version.user_learnings.append(
                f"{outcome.strategy.value}: {outcome.lessons_learned}"
            )

    def create_knowledge_version(self, notes: str = "") -> str:
        """Create new versioned knowledge snapshot."""
        new_version = VersionedKnowledge(
            version_id=f"v{len(self.knowledge.history) + 1.1}-{int(time.time())}",
            created_at=time.time(),
            parent_version=self.knowledge.current_version.version_id,
            strategy_performance=copy.deepcopy(self.knowledge.current_version.strategy_performance),
            context_patterns=copy.deepcopy(self.knowledge.current_version.context_patterns),
            user_learnings=copy.deepcopy(self.knowledge.current_version.user_learnings),
            mc_validated=False,
        )
        self.knowledge.history.append(self.knowledge.current_version)
        self.knowledge.current_version = new_version
        return new_version.version_id

    def rollback_knowledge(self, version_id: str) -> bool:
        """Rollback to a previous knowledge version."""
        for version in self.knowledge.history:
            if version.version_id == version_id:
                self.knowledge.history.remove(version)
                self.knowledge.history.append(self.knowledge.current_version)
                self.knowledge.current_version = version
                return True
        return False

    def to_dict(self) -> dict:
        """Serialize to dict."""
        return {
            "knowledge": self.knowledge.to_dict(),
            "model": self.model,
            "calibration": self.calibrator.to_dict(),
        }

    @classmethod
    def from_dict(cls, d: dict) -> QuantumAIBrain:
        """Deserialize from dict."""
        brain = cls(
            knowledge_store=KnowledgeStore.from_dict(d["knowledge"]),
            calibrator=ConfidenceCalibrator.from_dict(d.get("calibration", {})),
        )
        brain.model = d.get("model", brain.model)
        return brain
