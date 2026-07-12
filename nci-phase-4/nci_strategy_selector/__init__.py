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
]
