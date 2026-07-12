"""
Portfolio aggregation and risk budget for the NCI nerdcommand options assistant
(Phase 7).

Aggregates taken :class:`StrategyRecommendation` positions into a single view:
net Greeks, total modeled max loss against a configurable risk budget, per-symbol
and per-direction concentration, and expiration clustering.

Two advisory surfaces, in the spirit of the Phoenix ``RiskManager`` — they
*warn and block*, they never size a trade:

  * :func:`Portfolio.check` — block-style warnings for a candidate before you add
    it (budget exceeded, single-name concentration, over-clustered expiries,
    correlated direction stacking).
  * :func:`Portfolio.suggest` — deterministic textual suggestions derived from
    the current aggregations (trim the biggest risk, diversify expiry,
    delta-neutralize).

Educational analysis tooling — not investment advice.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field, asdict

from .models import StrategyRecommendation, GreeksSummary, StrategyType


# ── direction map: does the strategy lean bullish / bearish / neutral ──
_BULLISH = {
    StrategyType.COVERED_CALL, StrategyType.CASH_SECURED_PUT,
    StrategyType.BULL_CALL_SPREAD, StrategyType.BULL_PUT_SPREAD,
}
_BEARISH = {
    StrategyType.BEAR_CALL_SPREAD, StrategyType.BEAR_PUT_SPREAD,
}
# everything else (condor, straddles, strangles, calendar, diagonal) is neutral/vol


def strategy_direction(strategy: StrategyType) -> str:
    """Coarse directional lean used for concentration checks."""
    if strategy in _BULLISH:
        return "bullish"
    if strategy in _BEARISH:
        return "bearish"
    return "neutral"


# ── position ──────────────────────────────────────────────────────────
@dataclass
class Position:
    """A taken recommendation, plus how much of it and its lifecycle state."""

    recommendation: StrategyRecommendation
    qty: int
    opened_at: float = field(default_factory=time.time)
    status: str = "open"          # "open" | "closed"
    symbol: str = ""              # falls back to the recommendation's leg symbol

    def __post_init__(self):
        if not self.symbol:
            self.symbol = self._infer_symbol()

    def _infer_symbol(self) -> str:
        for leg in self.recommendation.legs:
            if leg.get("symbol"):
                return leg["symbol"]
        return "?"

    def modeled_max_loss(self) -> float:
        """Dollar max loss for the whole position (per-unit x qty)."""
        return self.recommendation.max_loss * self.qty

    def net_greeks(self) -> GreeksSummary:
        """Position Greeks: recommendation Greeks scaled by quantity."""
        g = self.recommendation.greeks
        q = self.qty
        return GreeksSummary(
            delta=g.delta * q, gamma=g.gamma * q, theta=g.theta * q,
            vega=g.vega * q, rho=g.rho * q,
        )

    def expirations(self) -> list[str]:
        """Distinct expiration labels across the position's legs."""
        seen = []
        for leg in self.recommendation.legs:
            exp = str(leg.get("expiration", "near"))
            if exp not in seen:
                seen.append(exp)
        return seen

    def to_dict(self) -> dict:
        return {
            "recommendation": self.recommendation.to_dict(),
            "qty": self.qty,
            "opened_at": self.opened_at,
            "status": self.status,
            "symbol": self.symbol,
        }

    @classmethod
    def from_dict(cls, d: dict) -> "Position":
        return cls(
            recommendation=StrategyRecommendation.from_dict(d["recommendation"]),
            qty=int(d["qty"]),
            opened_at=d.get("opened_at", time.time()),
            status=d.get("status", "open"),
            symbol=d.get("symbol", ""),
        )


# ── aggregations ──────────────────────────────────────────────────────
@dataclass
class PortfolioAggregates:
    """Snapshot of everything the checks and suggestions read from."""

    net_greeks: GreeksSummary
    total_max_loss: float
    risk_budget: float
    budget_used_pct: float
    per_symbol_risk: dict[str, float]
    per_direction_risk: dict[str, float]
    expiry_clusters: dict[str, float]
    open_positions: int

    def to_dict(self) -> dict:
        return {
            "net_greeks": self.net_greeks.to_dict(),
            "total_max_loss": round(self.total_max_loss, 2),
            "risk_budget": round(self.risk_budget, 2),
            "budget_used_pct": round(self.budget_used_pct, 2),
            "per_symbol_risk": {k: round(v, 2) for k, v in self.per_symbol_risk.items()},
            "per_direction_risk": {k: round(v, 2) for k, v in self.per_direction_risk.items()},
            "expiry_clusters": {k: round(v, 2) for k, v in self.expiry_clusters.items()},
            "open_positions": self.open_positions,
        }


# ── portfolio ─────────────────────────────────────────────────────────
@dataclass
class Portfolio:
    """
    Account-level container: open positions, closed trades, and a risk budget
    expressed as a fraction of account size (default 15%).
    """

    account_size: float
    positions: list[Position] = field(default_factory=list)
    closed_trades: list[Position] = field(default_factory=list)
    risk_budget_pct: float = 0.15               # max 15% of account at risk
    max_symbol_pct: float = 0.40                # single-name cap (of the budget)
    max_direction_pct: float = 0.60             # directional-stack cap (of budget)
    max_expiry_cluster_pct: float = 0.50        # same-expiry cap (of budget)

    # ── budget ────────────────────────────────────────────────────────
    def risk_budget(self) -> float:
        return self.account_size * self.risk_budget_pct

    def open_positions(self) -> list[Position]:
        return [p for p in self.positions if p.status == "open"]

    # ── aggregations ──────────────────────────────────────────────────
    def net_greeks(self) -> GreeksSummary:
        total = GreeksSummary(0.0, 0.0, 0.0, 0.0, 0.0)
        for p in self.open_positions():
            g = p.net_greeks()
            total = GreeksSummary(
                delta=total.delta + g.delta, gamma=total.gamma + g.gamma,
                theta=total.theta + g.theta, vega=total.vega + g.vega,
                rho=total.rho + g.rho,
            )
        return GreeksSummary(
            delta=round(total.delta, 4), gamma=round(total.gamma, 4),
            theta=round(total.theta, 4), vega=round(total.vega, 4),
            rho=round(total.rho, 4),
        )

    def total_max_loss(self) -> float:
        return sum(p.modeled_max_loss() for p in self.open_positions())

    def per_symbol_risk(self) -> dict[str, float]:
        out: dict[str, float] = {}
        for p in self.open_positions():
            out[p.symbol] = out.get(p.symbol, 0.0) + p.modeled_max_loss()
        return out

    def per_direction_risk(self) -> dict[str, float]:
        out: dict[str, float] = {}
        for p in self.open_positions():
            d = strategy_direction(p.recommendation.strategy)
            out[d] = out.get(d, 0.0) + p.modeled_max_loss()
        return out

    def expiry_clusters(self) -> dict[str, float]:
        """Modeled risk grouped by expiration label (how much expires together)."""
        out: dict[str, float] = {}
        for p in self.open_positions():
            exps = p.expirations() or ["near"]
            share = p.modeled_max_loss() / len(exps)
            for e in exps:
                out[e] = out.get(e, 0.0) + share
        return out

    def aggregates(self) -> PortfolioAggregates:
        budget = self.risk_budget()
        total = self.total_max_loss()
        return PortfolioAggregates(
            net_greeks=self.net_greeks(),
            total_max_loss=total,
            risk_budget=budget,
            budget_used_pct=(100.0 * total / budget) if budget > 0 else 0.0,
            per_symbol_risk=self.per_symbol_risk(),
            per_direction_risk=self.per_direction_risk(),
            expiry_clusters=self.expiry_clusters(),
            open_positions=len(self.open_positions()),
        )

    # ── mutation ──────────────────────────────────────────────────────
    def add(self, position: Position) -> None:
        self.positions.append(position)

    def close(self, index: int) -> None:
        """Mark an open position closed and move it to ``closed_trades``."""
        p = self.positions[index]
        p.status = "closed"
        self.closed_trades.append(p)

    # ── candidate check (warn / block only) ───────────────────────────
    def check(self, candidate: Position) -> list[str]:
        """
        Block-style warnings for adding ``candidate`` on top of the current book.
        Returns a list of human-readable warnings (empty == clear). Never sizes.
        """
        warnings: list[str] = []
        budget = self.risk_budget()
        cand_risk = candidate.modeled_max_loss()

        # 1. total budget
        projected = self.total_max_loss() + cand_risk
        if budget > 0 and projected > budget:
            warnings.append(
                f"BUDGET: adding {candidate.symbol} pushes modeled risk to "
                f"${projected:,.0f}, over the ${budget:,.0f} budget "
                f"({self.risk_budget_pct:.0%} of account)."
            )

        # 2. single-name concentration
        sym_risk = self.per_symbol_risk().get(candidate.symbol, 0.0) + cand_risk
        if budget > 0 and sym_risk > self.max_symbol_pct * budget:
            warnings.append(
                f"CONCENTRATION: {candidate.symbol} would hold ${sym_risk:,.0f} "
                f"of risk, over the {self.max_symbol_pct:.0%}-of-budget single-name cap."
            )

        # 3. correlated direction stacking
        direction = strategy_direction(candidate.recommendation.strategy)
        dir_risk = self.per_direction_risk().get(direction, 0.0) + cand_risk
        if budget > 0 and direction != "neutral" and dir_risk > self.max_direction_pct * budget:
            warnings.append(
                f"DIRECTION: stacking another {direction} trade brings {direction} "
                f"risk to ${dir_risk:,.0f}, over the {self.max_direction_pct:.0%}-of-budget "
                f"directional cap — the book is leaning one way."
            )

        # 4. expiration clustering
        clusters = self.expiry_clusters()
        cand_exps = candidate.expirations() or ["near"]
        cand_share = cand_risk / len(cand_exps)
        for e in cand_exps:
            clustered = clusters.get(e, 0.0) + cand_share
            if budget > 0 and clustered > self.max_expiry_cluster_pct * budget:
                warnings.append(
                    f"EXPIRY: ${clustered:,.0f} of risk would expire in the "
                    f"'{e}' window, over the {self.max_expiry_cluster_pct:.0%}-of-budget "
                    f"clustering cap — a single expiry could hit the whole book at once."
                )

        return warnings

    # ── suggestions (deterministic, derived from aggregates) ──────────
    def suggest(self) -> list[str]:
        """Deterministic textual suggestions derived from the aggregations."""
        suggestions: list[str] = []
        agg = self.aggregates()
        budget = agg.risk_budget

        if agg.open_positions == 0:
            return ["Portfolio is flat — no risk deployed."]

        # over budget → trim the biggest single risk
        if budget > 0 and agg.total_max_loss > budget:
            biggest_sym = max(agg.per_symbol_risk.items(), key=lambda kv: kv[1])
            suggestions.append(
                f"Over risk budget ({agg.budget_used_pct:.0f}% used). Trim the "
                f"largest exposure first: {biggest_sym[0]} at ${biggest_sym[1]:,.0f}."
            )

        # single-name concentration
        if budget > 0:
            for sym, risk in sorted(agg.per_symbol_risk.items(), key=lambda kv: -kv[1]):
                if risk > self.max_symbol_pct * budget:
                    suggestions.append(
                        f"Diversify away from {sym}: it carries ${risk:,.0f} "
                        f"({100 * risk / budget:.0f}% of budget)."
                    )
                    break

        # directional lean → suggest delta-neutralizing
        net_delta = agg.net_greeks.delta
        if abs(net_delta) >= 0.5:
            lean = "long" if net_delta > 0 else "short"
            hedge = "bearish" if net_delta > 0 else "bullish"
            suggestions.append(
                f"Book is net {lean} delta ({net_delta:+.2f}). Consider a "
                f"{hedge} or neutral structure to delta-neutralize."
            )

        # expiry clustering → spread expiries
        if budget > 0:
            for exp, risk in sorted(agg.expiry_clusters.items(), key=lambda kv: -kv[1]):
                if risk > self.max_expiry_cluster_pct * budget:
                    suggestions.append(
                        f"Expiry '{exp}' concentrates ${risk:,.0f} of risk — "
                        f"stagger new trades into a different expiration."
                    )
                    break

        if not suggestions:
            suggestions.append(
                f"Book looks balanced: {agg.budget_used_pct:.0f}% of budget used, "
                f"net delta {net_delta:+.2f}."
            )
        return suggestions

    # ── serialization ─────────────────────────────────────────────────
    def to_dict(self) -> dict:
        return {
            "account_size": self.account_size,
            "positions": [p.to_dict() for p in self.positions],
            "closed_trades": [p.to_dict() for p in self.closed_trades],
            "risk_budget_pct": self.risk_budget_pct,
            "max_symbol_pct": self.max_symbol_pct,
            "max_direction_pct": self.max_direction_pct,
            "max_expiry_cluster_pct": self.max_expiry_cluster_pct,
        }

    @classmethod
    def from_dict(cls, d: dict) -> "Portfolio":
        return cls(
            account_size=d["account_size"],
            positions=[Position.from_dict(p) for p in d.get("positions", [])],
            closed_trades=[Position.from_dict(p) for p in d.get("closed_trades", [])],
            risk_budget_pct=d.get("risk_budget_pct", 0.15),
            max_symbol_pct=d.get("max_symbol_pct", 0.40),
            max_direction_pct=d.get("max_direction_pct", 0.60),
            max_expiry_cluster_pct=d.get("max_expiry_cluster_pct", 0.50),
        )
