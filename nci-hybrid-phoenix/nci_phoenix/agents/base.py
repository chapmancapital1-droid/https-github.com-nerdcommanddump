"""
BaseTradingAgent — the contract every Phoenix agent implements.

The pool, orchestrator, and brain only ever talk to this interface, so the
dev team can wrap existing EA strategy logic (scalper, breakout, mean
reversion, ...) without rewriting it: subclass, implement four methods,
register with the pool.
"""

from __future__ import annotations

from abc import ABC, abstractmethod

from ..models import (
    MarketSnapshot,
    Regime,
    RegimeState,
    Signal,
    TradeResult,
)


class BaseTradingAgent(ABC):
    """Abstract strategy module managed by the AgentPool."""

    #: unique, stable identifier (also the AgentRecord key)
    name: str = "base"
    version: str = "1.0"
    #: regimes this agent claims edge in (earns a selection bonus there)
    specializations: tuple[Regime, ...] = ()

    # -- decisions ---------------------------------------------------------

    @abstractmethod
    def propose(self, regime: RegimeState, snap: MarketSnapshot) -> Signal:
        """Return LONG / SHORT / FLAT for the current snapshot."""

    def risk_fraction(self, regime: RegimeState, snap: MarketSnapshot) -> float:
        """
        Fraction of the brain's allowed risk this agent wants (0–1).
        Default: full allocation; conservative agents can dial down.
        """
        return 1.0

    # -- learning ----------------------------------------------------------

    def on_trade_closed(self, result: TradeResult) -> None:
        """Hook for per-agent adaptation after a closed trade. Optional."""

    # -- identity ----------------------------------------------------------

    def __repr__(self) -> str:  # pragma: no cover
        return f"<{type(self).__name__} {self.name} v{self.version}>"
