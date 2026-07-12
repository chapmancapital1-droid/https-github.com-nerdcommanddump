"""
NCI Hybrid Phoenix Brain — core data models.

Single source of truth for every structure the brain reads or writes.
Stdlib-only (dataclasses) so the package runs on any host — local machine,
VPS, or inside the NCI dashboard backend — with zero installs.

Every model serializes to/from plain dicts (see `to_dict` / `from_dict`),
which is what the JSON brain-state file, the versioning system, and the
dashboard tab all consume.

Educational analysis tooling — not investment advice.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field, asdict
from enum import Enum
from typing import Any


SCHEMA_VERSION = "2.1"


# --------------------------------------------------------------------------
# Enums — closed vocabularies shared across every module
# --------------------------------------------------------------------------

class Regime(str, Enum):
    TRENDING_BULLISH = "trending_bullish"
    TRENDING_BEARISH = "trending_bearish"
    RANGING_CHOPPY = "ranging_choppy"
    HIGH_VOL_EXPANSION = "high_volatility_expansion"
    LOW_VOL_COMPRESSION = "low_volatility_compression"
    PRE_BREAKOUT_COIL = "pre_breakout_coil"
    NEWS_DRIVEN = "news_driven"
    UNKNOWN = "unknown"


class AgentStatus(str, Enum):
    ACTIVE = "active"          # eligible for primary selection
    PROBATION = "probation"    # recently demoted; reduced allocation
    DORMANT = "dormant"        # sidelined; only touched via exploration
    RETIRED = "retired"        # never selected; kept for history


class Signal(str, Enum):
    LONG = "long"
    SHORT = "short"
    FLAT = "flat"


# --------------------------------------------------------------------------
# Market inputs
# --------------------------------------------------------------------------

@dataclass
class MarketSnapshot:
    """One tick/bar of everything the brain needs to decide."""
    symbol: str
    price: float
    atr: float = 0.0                  # average true range (volatility proxy)
    atr_baseline: float = 0.0         # long-run ATR for expansion/compression ratio
    adx: float = 0.0                  # trend strength 0–100
    trend_direction: int = 0          # +1 up, -1 down, 0 flat (structure-based)
    range_width_pct: float = 0.0      # recent high-low range as % of price
    news_impact: float = 0.0          # 0–1, scheduled/breaking news pressure
    session: str = "unknown"          # asian | london | newyork | overlap | unknown
    spread_pts: float = 0.0
    timestamp: float = field(default_factory=time.time)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class RegimeState:
    """Output of the RegimeDetector: what market are we actually in."""
    regime: Regime = Regime.UNKNOWN
    confidence: float = 0.0                       # 0–1
    scores: dict[str, float] = field(default_factory=dict)  # regime -> raw score
    detected_at: float = field(default_factory=time.time)
    notes: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        d["regime"] = self.regime.value
        return d

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> "RegimeState":
        return cls(
            regime=Regime(d.get("regime", "unknown")),
            confidence=float(d.get("confidence", 0.0)),
            scores=dict(d.get("scores", {})),
            detected_at=float(d.get("detected_at", time.time())),
            notes=list(d.get("notes", [])),
        )


# --------------------------------------------------------------------------
# Trades & agent performance
# --------------------------------------------------------------------------

@dataclass
class TradeResult:
    """Closed-trade record fed back into agents, memory, and the pool."""
    agent_name: str
    symbol: str
    signal: Signal
    pnl: float                         # account currency
    pnl_r: float                       # multiples of initial risk (R)
    regime: Regime = Regime.UNKNOWN
    opened_at: float = 0.0
    closed_at: float = field(default_factory=time.time)
    tags: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        d["signal"] = self.signal.value
        d["regime"] = self.regime.value
        return d

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> "TradeResult":
        return cls(
            agent_name=d["agent_name"],
            symbol=d.get("symbol", ""),
            signal=Signal(d.get("signal", "flat")),
            pnl=float(d.get("pnl", 0.0)),
            pnl_r=float(d.get("pnl_r", 0.0)),
            regime=Regime(d.get("regime", "unknown")),
            opened_at=float(d.get("opened_at", 0.0)),
            closed_at=float(d.get("closed_at", time.time())),
            tags=list(d.get("tags", [])),
        )


@dataclass
class AgentPerformance:
    """Rolling performance ledger for one agent."""
    trades: int = 0
    wins: int = 0
    gross_profit: float = 0.0
    gross_loss: float = 0.0            # stored as positive magnitude
    sum_r: float = 0.0
    # per-regime R totals so specialization is earned, not asserted
    regime_r: dict[str, float] = field(default_factory=dict)
    regime_trades: dict[str, int] = field(default_factory=dict)

    @property
    def win_rate(self) -> float:
        return self.wins / self.trades if self.trades else 0.0

    @property
    def profit_factor(self) -> float:
        if self.gross_loss <= 0:
            return float(self.trades and self.gross_profit > 0) * 99.0
        return self.gross_profit / self.gross_loss

    @property
    def expectancy_r(self) -> float:
        return self.sum_r / self.trades if self.trades else 0.0

    def record(self, tr: TradeResult) -> None:
        self.trades += 1
        if tr.pnl > 0:
            self.wins += 1
            self.gross_profit += tr.pnl
        else:
            self.gross_loss += -tr.pnl
        self.sum_r += tr.pnl_r
        key = tr.regime.value
        self.regime_r[key] = self.regime_r.get(key, 0.0) + tr.pnl_r
        self.regime_trades[key] = self.regime_trades.get(key, 0) + 1

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> "AgentPerformance":
        return cls(
            trades=int(d.get("trades", 0)),
            wins=int(d.get("wins", 0)),
            gross_profit=float(d.get("gross_profit", 0.0)),
            gross_loss=float(d.get("gross_loss", 0.0)),
            sum_r=float(d.get("sum_r", 0.0)),
            regime_r=dict(d.get("regime_r", {})),
            regime_trades=dict(d.get("regime_trades", {})),
        )


@dataclass
class AgentRecord:
    """Pool-side record of one agent: identity, status, score, performance."""
    name: str
    version: str = "1.0"
    status: AgentStatus = AgentStatus.ACTIVE
    score: float = 0.5                          # 0–1 composite fitness
    specializations: list[Regime] = field(default_factory=list)
    performance: AgentPerformance = field(default_factory=AgentPerformance)
    last_selected_at: float = 0.0
    demotions: int = 0
    promotions: int = 0

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "version": self.version,
            "status": self.status.value,
            "score": self.score,
            "specializations": [r.value for r in self.specializations],
            "performance": self.performance.to_dict(),
            "last_selected_at": self.last_selected_at,
            "demotions": self.demotions,
            "promotions": self.promotions,
        }

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> "AgentRecord":
        return cls(
            name=d["name"],
            version=d.get("version", "1.0"),
            status=AgentStatus(d.get("status", "active")),
            score=float(d.get("score", 0.5)),
            specializations=[Regime(r) for r in d.get("specializations", [])],
            performance=AgentPerformance.from_dict(d.get("performance", {})),
            last_selected_at=float(d.get("last_selected_at", 0.0)),
            demotions=int(d.get("demotions", 0)),
            promotions=int(d.get("promotions", 0)),
        )


# --------------------------------------------------------------------------
# Decisions
# --------------------------------------------------------------------------

@dataclass
class Decision:
    """What the brain hands back to the EA / dashboard on each evaluation."""
    signal: Signal = Signal.FLAT
    agent: str = ""
    regime: Regime = Regime.UNKNOWN
    lot_multiplier: float = 0.0        # 0 when blocked; EA multiplies its base lot
    rescue_mode: bool = False
    blocked_by: list[str] = field(default_factory=list)  # risk gates that said no
    reasoning: list[str] = field(default_factory=list)   # human-readable trail
    timestamp: float = field(default_factory=time.time)

    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        d["signal"] = self.signal.value
        d["regime"] = self.regime.value
        return d


# --------------------------------------------------------------------------
# Configuration blocks
# --------------------------------------------------------------------------

@dataclass
class PoolConfig:
    promotion_score_threshold: float = 0.65
    demotion_score_threshold: float = 0.35
    exploration_rate: float = 0.05      # chance a dormant agent gets a look
    specialization_bonus: float = 0.15  # score bonus when regime matches
    min_trades_for_promotion: int = 10
    score_smoothing: float = 0.30       # EMA weight for new evidence

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> "PoolConfig":
        return cls(**{k: d[k] for k in cls().to_dict() if k in d})


@dataclass
class PIDConfig:
    kp: float = 0.8
    ki: float = 0.15
    kd: float = 0.25
    setpoint_r_per_day: float = 0.5     # target equity slope in R/day
    output_min: float = 0.10            # never below 10% of base lot
    output_max: float = 2.00            # never above 2x base lot
    integral_limit: float = 5.0         # anti-windup clamp

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> "PIDConfig":
        return cls(**{k: d[k] for k in cls().to_dict() if k in d})


@dataclass
class RiskConfig:
    daily_loss_limit_r: float = 3.0     # stop trading after -3R on the day
    weekly_loss_limit_r: float = 8.0
    max_drawdown_pct: float = 12.0      # equity circuit breaker
    max_concurrent_positions: int = 4
    max_correlated_exposure: int = 2    # same-direction positions in correlated pairs
    news_blackout_minutes: int = 15     # no entries this close to red news
    news_impact_block: float = 0.75     # block entries when news_impact >= this

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> "RiskConfig":
        return cls(**{k: d[k] for k in cls().to_dict() if k in d})


@dataclass
class MonteCarloConfig:
    simulations: int = 7500
    block_size: int = 10                # block bootstrap preserves streaks
    ruin_threshold_pct: float = 30.0    # equity loss that counts as ruin
    max_ruin_probability: float = 0.02  # accept only if P(ruin) <= 2%
    min_expectancy_r: float = 0.05      # accept only if median expectancy > this
    max_median_drawdown_r: float = 12.0

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> "MonteCarloConfig":
        return cls(**{k: d[k] for k in cls().to_dict() if k in d})


@dataclass
class BrainMeta:
    name: str = "NCI Hybrid Phoenix Brain"
    version: str = "2.1.0"
    schema_version: str = SCHEMA_VERSION
    created_at: float = field(default_factory=time.time)
    philosophy: str = (
        "Self-organizing, regime-aware, Monte-Carlo-validated, human-aligned risk. "
        "Educational analysis tooling — not investment advice."
    )

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> "BrainMeta":
        return cls(**{k: d[k] for k in cls().to_dict() if k in d})
