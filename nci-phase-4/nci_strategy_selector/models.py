"""
Phase 4 Strategy Selector & Quantum AI Brain Models.

Models for strategy recommendations, AI reasoning, and interactive learning.
"""

from __future__ import annotations

from dataclasses import dataclass, field, asdict
from enum import Enum
from typing import Optional
import json
import time


class StrategyType(Enum):
    """Available options strategies."""
    COVERED_CALL = "covered_call"
    CASH_SECURED_PUT = "cash_secured_put"
    BULL_CALL_SPREAD = "bull_call_spread"
    BEAR_CALL_SPREAD = "bear_call_spread"
    BULL_PUT_SPREAD = "bull_put_spread"
    BEAR_PUT_SPREAD = "bear_put_spread"
    IRON_CONDOR = "iron_condor"
    LONG_STRADDLE = "long_straddle"
    SHORT_STRADDLE = "short_straddle"
    LONG_STRANGLE = "long_strangle"
    SHORT_STRANGLE = "short_strangle"
    DIAGONAL_SPREAD = "diagonal_spread"
    CALENDAR_SPREAD = "calendar_spread"


class RiskProfile(Enum):
    """User risk tolerance."""
    CONSERVATIVE = "conservative"
    MODERATE = "moderate"
    AGGRESSIVE = "aggressive"


@dataclass
class MarketContext:
    """Current market conditions from Phase 3."""
    symbol: str
    price: float
    iv_rank: float  # 0-100
    iv_trend: float  # -1 to +1
    spot_trend: float  # -1 to +1
    expected_move: float  # in dollars
    liquidity_score: float  # 0-1
    event_proximity_days: Optional[float] = None  # days to next event
    news_sentiment: float = 0.0  # -1 to +1
    timestamp: float = field(default_factory=time.time)

    def to_dict(self):
        return asdict(self)

    @classmethod
    def from_dict(cls, d: dict):
        return cls(**d)


@dataclass
class UserPreferences:
    """User's trading preferences and constraints."""
    symbol: str
    risk_profile: RiskProfile
    max_loss_pct: float  # max loss as % of account
    max_loss_dollars: float  # max loss in dollars
    bias: str  # "bullish", "bearish", "neutral"
    time_horizon_days: int  # days to expiration preference
    min_probability_itm: float = 0.5  # minimum probability ITM for short strikes
    credit_requirement: Optional[float] = None  # min credit for credit spreads
    timestamp: float = field(default_factory=time.time)

    def to_dict(self):
        d = asdict(self)
        d["risk_profile"] = self.risk_profile.value
        return d

    @classmethod
    def from_dict(cls, d: dict):
        d_copy = d.copy()
        d_copy["risk_profile"] = RiskProfile(d_copy["risk_profile"])
        return cls(**d_copy)


@dataclass
class GreeksSummary:
    """Options Greeks for a strategy."""
    delta: float
    gamma: float
    theta: float  # daily theta
    vega: float
    rho: float

    def to_dict(self):
        return asdict(self)

    @classmethod
    def from_dict(cls, d: dict):
        return cls(**d)


@dataclass
class StrategyRecommendation:
    """A single strategy recommendation."""
    strategy: StrategyType
    legs: list[dict]  # [{symbol, right, strike, qty, expiration}, ...]
    entry_price: float  # net debit (positive) or credit (negative)
    max_profit: float
    max_loss: float
    breakeven_price: float
    probability_profit: float  # 0-1
    greeks: GreeksSummary
    confidence_score: float  # 0-1 from Quantum AI
    reasoning: str  # why this strategy
    risk_rating: str  # "low", "medium", "high"

    def to_dict(self):
        d = asdict(self)
        d["strategy"] = self.strategy.value
        d["greeks"] = self.greeks.to_dict()
        return d

    @classmethod
    def from_dict(cls, d: dict):
        d_copy = d.copy()
        d_copy["strategy"] = StrategyType(d_copy["strategy"])
        d_copy["greeks"] = GreeksSummary.from_dict(d_copy["greeks"])
        return cls(**d_copy)


@dataclass
class StrategySelectionResult:
    """Result of strategy selection process."""
    symbol: str
    recommendations: list[StrategyRecommendation]
    ai_reasoning: str
    model_used: str
    timestamp: float = field(default_factory=time.time)

    def to_dict(self):
        return {
            "symbol": self.symbol,
            "recommendations": [r.to_dict() for r in self.recommendations],
            "ai_reasoning": self.ai_reasoning,
            "model_used": self.model_used,
            "timestamp": self.timestamp,
        }

    @classmethod
    def from_dict(cls, d: dict):
        return cls(
            symbol=d["symbol"],
            recommendations=[StrategyRecommendation.from_dict(r) for r in d["recommendations"]],
            ai_reasoning=d["ai_reasoning"],
            model_used=d["model_used"],
            timestamp=d["timestamp"],
        )


@dataclass
class TradeOutcome:
    """User feedback on a trade."""
    recommendation_id: str
    symbol: str
    strategy: StrategyType
    entry_price: float
    exit_price: Optional[float]
    pnl: float
    pnl_pct: float
    lessons_learned: str
    user_rating: int  # 1-5 stars
    timestamp: float = field(default_factory=time.time)

    def to_dict(self):
        d = asdict(self)
        d["strategy"] = self.strategy.value
        return d

    @classmethod
    def from_dict(cls, d: dict):
        d_copy = d.copy()
        d_copy["strategy"] = StrategyType(d_copy["strategy"])
        return cls(**d_copy)


@dataclass
class VersionedKnowledge:
    """Versioned strategy knowledge base."""
    version_id: str
    created_at: float
    parent_version: Optional[str]
    strategy_performance: dict[str, dict]  # {strategy: {metric: value}}
    context_patterns: dict[str, list]  # {pattern: [contexts where successful]}
    user_learnings: list[str]  # discovered patterns
    mc_validated: bool = False

    def to_dict(self):
        return asdict(self)

    @classmethod
    def from_dict(cls, d: dict):
        return cls(**d)


@dataclass
class KnowledgeStore:
    """Persistent knowledge store with versioning."""
    current_version: VersionedKnowledge
    history: list[VersionedKnowledge] = field(default_factory=list)
    trade_outcomes: list[TradeOutcome] = field(default_factory=list)

    def to_dict(self):
        return {
            "current_version": self.current_version.to_dict(),
            "history": [v.to_dict() for v in self.history],
            "trade_outcomes": [t.to_dict() for t in self.trade_outcomes],
        }

    @classmethod
    def from_dict(cls, d: dict):
        return cls(
            current_version=VersionedKnowledge.from_dict(d["current_version"]),
            history=[VersionedKnowledge.from_dict(v) for v in d.get("history", [])],
            trade_outcomes=[TradeOutcome.from_dict(t) for t in d.get("trade_outcomes", [])],
        )
