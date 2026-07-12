"""
Risk gates & circuit breakers — the layer that can always say NO.

Every decision passes through RiskManager.check() before the orchestrator's
signal is allowed out. Gates:

  * daily / weekly loss limits (in R)
  * max-drawdown circuit breaker (% from equity high-water mark)
  * concurrent-position cap
  * correlated-exposure cap
  * news blackout (impact score and/or minutes-to-event)

The manager never sizes up — it only blocks or passes. Sizing belongs to
the PID controller; separation keeps both auditable.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field

from .models import RiskConfig, TradeResult

DAY_SECONDS = 86_400.0
WEEK_SECONDS = 7 * DAY_SECONDS


@dataclass
class OpenPosition:
    symbol: str
    direction: int              # +1 long, -1 short
    correlation_group: str = "" # e.g. "usd-majors"; empty = uncorrelated
    opened_at: float = field(default_factory=time.time)


class RiskManager:
    def __init__(self, config: RiskConfig | None = None):
        self.config = config or RiskConfig()
        self._closed: list[TradeResult] = []
        self.open_positions: list[OpenPosition] = []
        self.equity_high_water: float = 0.0
        self.current_equity: float = 0.0
        self.halted_reason: str | None = None

    # -- bookkeeping ---------------------------------------------------------

    def record_trade(self, result: TradeResult) -> None:
        self._closed.append(result)
        # Only the weekly window matters to the gates — prune older entries
        # so the ledger can't grow unbounded over a long session.
        cutoff = time.time() - WEEK_SECONDS
        if self._closed and self._closed[0].closed_at < cutoff:
            self._closed = [t for t in self._closed if t.closed_at >= cutoff]

    def update_equity(self, equity: float) -> None:
        self.current_equity = equity
        self.equity_high_water = max(self.equity_high_water, equity)
        dd = self.drawdown_pct()
        if dd >= self.config.max_drawdown_pct:
            self.halted_reason = (
                f"max drawdown circuit breaker: {dd:.1f}% "
                f">= {self.config.max_drawdown_pct:.1f}%"
            )

    def drawdown_pct(self) -> float:
        if self.equity_high_water <= 0:
            return 0.0
        return (1 - self.current_equity / self.equity_high_water) * 100.0

    def _r_in_window(self, window_seconds: float, now: float) -> float:
        cutoff = now - window_seconds
        return sum(t.pnl_r for t in self._closed if t.closed_at >= cutoff)

    # -- the gate ---------------------------------------------------------------

    def check(
        self,
        news_impact: float = 0.0,
        minutes_to_news: float | None = None,
        direction: int = 0,
        correlation_group: str = "",
        now: float | None = None,
    ) -> list[str]:
        """
        Return the list of violated gates (empty list == trade may proceed).
        """
        cfg = self.config
        now = now if now is not None else time.time()
        blocked: list[str] = []

        if self.halted_reason:
            blocked.append(self.halted_reason)

        daily_r = self._r_in_window(DAY_SECONDS, now)
        if daily_r <= -cfg.daily_loss_limit_r:
            blocked.append(
                f"daily loss limit: {daily_r:.1f}R <= -{cfg.daily_loss_limit_r}R"
            )

        weekly_r = self._r_in_window(WEEK_SECONDS, now)
        if weekly_r <= -cfg.weekly_loss_limit_r:
            blocked.append(
                f"weekly loss limit: {weekly_r:.1f}R <= -{cfg.weekly_loss_limit_r}R"
            )

        if len(self.open_positions) >= cfg.max_concurrent_positions:
            blocked.append(
                f"max concurrent positions ({cfg.max_concurrent_positions}) reached"
            )

        if direction != 0 and correlation_group:
            same = sum(
                1
                for p in self.open_positions
                if p.correlation_group == correlation_group
                and p.direction == direction
            )
            if same >= cfg.max_correlated_exposure:
                blocked.append(
                    f"correlated exposure cap in '{correlation_group}' "
                    f"({same} same-direction positions)"
                )

        if news_impact >= cfg.news_impact_block:
            blocked.append(f"news impact {news_impact:.2f} in blackout zone")
        if (
            minutes_to_news is not None
            and 0 <= minutes_to_news <= cfg.news_blackout_minutes
        ):
            blocked.append(
                f"news blackout: event in {minutes_to_news:.0f}m "
                f"(window {cfg.news_blackout_minutes}m)"
            )

        return blocked

    # -- ops -----------------------------------------------------------------------

    def clear_halt(self) -> None:
        """Manual human reset of the circuit breaker (deliberate action only)."""
        self.halted_reason = None

    def state(self) -> dict:
        return {
            "open_positions": len(self.open_positions),
            "drawdown_pct": round(self.drawdown_pct(), 2),
            "halted_reason": self.halted_reason,
            "equity_high_water": self.equity_high_water,
            "current_equity": self.current_equity,
            # Ledger for the daily/weekly loss windows — without it, a reload
            # would silently reset the loss limits.
            "closed": [t.to_dict() for t in self._closed],
            "config": self.config.to_dict(),
        }

    def restore(self, state: dict) -> None:
        """Rehydrate safety state from a state() dump (config handled by caller)."""
        self.halted_reason = state.get("halted_reason")
        self.equity_high_water = float(state.get("equity_high_water", 0.0))
        self.current_equity = float(state.get("current_equity", 0.0))
        self._closed = [
            TradeResult.from_dict(t) for t in state.get("closed", [])
        ]
