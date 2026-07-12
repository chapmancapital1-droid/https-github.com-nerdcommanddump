"""
NCI Phase 4: Strategy Selector & Quantum AI Brain.

Adaptive strategy recommendation engine with Claude AI reasoning and interactive learning.
"""

from .models import (
    StrategyType,
    RiskProfile,
    MarketContext,
    UserPreferences,
    GreeksSummary,
    StrategyRecommendation,
    StrategySelectionResult,
    TradeOutcome,
    VersionedKnowledge,
    KnowledgeStore,
)
from .strategy_selector import StrategySelector
from .quantum_ai import QuantumAIBrain
from .claude_client import ClaudeReasoningClient, ClaudeResponse
from .reasoning_engine import ReasoningSession, DialogueTurn
from .feedback import ConfidenceCalibrator, CalibrationRecord
from .payoff import (
    Leg,
    PayoffCurve,
    ReconciledPayoff,
    build_legs,
    payoff_curve,
    default_price_range,
    bachelier_price,
    price_leg,
    net_entry_price,
    reconcile_payoff,
    curve_from_recommendation,
    legs_from_dicts,
    CONTRACT_MULTIPLIER,
)
from .backtest import (
    Bar,
    BacktestPlan,
    BacktestTrade,
    BacktestResult,
    BacktestEngine,
    MCConfig,
    MCReport,
    synthetic_bars,
    bars_from_csv,
    realized_vol,
    reconstruct_context,
    validate,
)
from .portfolio import (
    Position,
    Portfolio,
    PortfolioAggregates,
    strategy_direction,
)

__all__ = [
    "ClaudeReasoningClient",
    "ClaudeResponse",
    "ReasoningSession",
    "DialogueTurn",
    "ConfidenceCalibrator",
    "CalibrationRecord",
    "StrategyType",
    "RiskProfile",
    "MarketContext",
    "UserPreferences",
    "GreeksSummary",
    "StrategyRecommendation",
    "StrategySelectionResult",
    "TradeOutcome",
    "VersionedKnowledge",
    "KnowledgeStore",
    "StrategySelector",
    "QuantumAIBrain",
    # Phase 6a — payoff engine
    "Leg",
    "PayoffCurve",
    "ReconciledPayoff",
    "build_legs",
    "payoff_curve",
    "default_price_range",
    "bachelier_price",
    "price_leg",
    "net_entry_price",
    "reconcile_payoff",
    "curve_from_recommendation",
    "legs_from_dicts",
    "CONTRACT_MULTIPLIER",
    # Phase 6b — backtest engine
    "Bar",
    "BacktestPlan",
    "BacktestTrade",
    "BacktestResult",
    "BacktestEngine",
    "MCConfig",
    "MCReport",
    "synthetic_bars",
    "bars_from_csv",
    "realized_vol",
    "reconstruct_context",
    "validate",
    # Phase 7 — portfolio engine
    "Position",
    "Portfolio",
    "PortfolioAggregates",
    "strategy_direction",
]
