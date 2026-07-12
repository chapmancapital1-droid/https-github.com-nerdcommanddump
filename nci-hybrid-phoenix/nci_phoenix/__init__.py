"""
NCI Hybrid Phoenix Brain — self-organizing, regime-aware trading brain.

Public surface:

    from nci_phoenix import NCIPhoenixBrain, MarketSnapshot, TradeResult

    brain = NCIPhoenixBrain()
    decision = brain.evaluate(MarketSnapshot(symbol="EURUSD", price=1.0850, ...))
    brain.record_trade(TradeResult(...))
    brain.save("brain_state.json")

Educational analysis tooling — not investment advice.
"""

from .brain import NCIPhoenixBrain
from .memory import TradeMemory
from .models import (
    AgentRecord,
    AgentStatus,
    BrainMeta,
    Decision,
    MarketSnapshot,
    MonteCarloConfig,
    PIDConfig,
    PoolConfig,
    Regime,
    RegimeState,
    RiskConfig,
    Signal,
    TradeResult,
)
from .montecarlo import MonteCarloEngine, MonteCarloReport
from .orchestrator import HybridOrchestrator
from .pid import PIDController
from .pool import AgentPool
from .regime import RegimeDetector
from .risk import OpenPosition, RiskManager
from .versioning import BrainVersionStore

__version__ = "2.1.0"

__all__ = [
    "NCIPhoenixBrain",
    "TradeMemory",
    "AgentRecord",
    "AgentStatus",
    "BrainMeta",
    "Decision",
    "MarketSnapshot",
    "MonteCarloConfig",
    "MonteCarloEngine",
    "MonteCarloReport",
    "PIDConfig",
    "PIDController",
    "PoolConfig",
    "AgentPool",
    "Regime",
    "RegimeDetector",
    "RegimeState",
    "RiskConfig",
    "RiskManager",
    "OpenPosition",
    "Signal",
    "TradeResult",
    "HybridOrchestrator",
    "BrainVersionStore",
]
