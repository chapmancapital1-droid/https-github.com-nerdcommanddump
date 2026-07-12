"""
AgentPool — the self-organizing layer.

Responsibilities:
  * keep an AgentRecord per registered agent (score, status, performance)
  * rescore agents from realized trade evidence (EMA-smoothed)
  * promote / demote automatically at the configured thresholds
  * select the primary agent for the current regime, with a specialization
    bonus and an exploration channel so dormant agents can earn their way back

Scores live in [0, 1]. New evidence updates a score as:
    score = (1 - smoothing) * score + smoothing * evidence
where evidence maps the trade's R-multiple into [0, 1].
"""

from __future__ import annotations

import random
import time

from .agents.base import BaseTradingAgent
from .models import (
    AgentRecord,
    AgentStatus,
    PoolConfig,
    RegimeState,
    TradeResult,
)


def _evidence_from_r(pnl_r: float) -> float:
    """Map an R-multiple to score evidence in [0,1]; +1R→0.75, -1R→0.25."""
    return max(0.0, min(1.0, 0.5 + pnl_r * 0.25))


class AgentPool:
    def __init__(
        self,
        agents: list[BaseTradingAgent],
        config: PoolConfig | None = None,
        records: dict[str, AgentRecord] | None = None,
        rng: random.Random | None = None,
    ):
        self.config = config or PoolConfig()
        self.agents: dict[str, BaseTradingAgent] = {a.name: a for a in agents}
        self.records: dict[str, AgentRecord] = records or {}
        self.rng = rng or random.Random()
        for agent in agents:
            self.records.setdefault(
                agent.name,
                AgentRecord(
                    name=agent.name,
                    version=agent.version,
                    specializations=list(agent.specializations),
                ),
            )

    # -- scoring -----------------------------------------------------------

    def record_trade(self, result: TradeResult) -> None:
        rec = self.records.get(result.agent_name)
        if rec is None:
            return
        rec.performance.record(result)
        evidence = _evidence_from_r(result.pnl_r)
        s = self.config.score_smoothing
        rec.score = round((1 - s) * rec.score + s * evidence, 6)
        agent = self.agents.get(result.agent_name)
        if agent:
            agent.on_trade_closed(result)
        self._apply_status(rec)

    def _apply_status(self, rec: AgentRecord) -> None:
        cfg = self.config
        if (
            rec.score >= cfg.promotion_score_threshold
            and rec.performance.trades >= cfg.min_trades_for_promotion
            and rec.status is not AgentStatus.ACTIVE
        ):
            rec.status = AgentStatus.ACTIVE
            rec.promotions += 1
        elif rec.score <= cfg.demotion_score_threshold:
            if rec.status is AgentStatus.ACTIVE:
                rec.status = AgentStatus.PROBATION
                rec.demotions += 1
            elif rec.status is AgentStatus.PROBATION:
                rec.status = AgentStatus.DORMANT
                rec.demotions += 1

    # -- ranking & selection -------------------------------------------------

    def effective_score(self, rec: AgentRecord, regime: RegimeState) -> float:
        """Score + specialization bonus when the agent claims this regime."""
        bonus = (
            self.config.specialization_bonus
            if regime.regime in rec.specializations
            else 0.0
        )
        return min(1.0, rec.score + bonus)

    def evaluate_and_rank(self, regime: RegimeState) -> list[AgentRecord]:
        """All records sorted by effective score for this regime, best first."""
        return sorted(
            self.records.values(),
            key=lambda r: self.effective_score(r, regime),
            reverse=True,
        )

    def select_primary_agent(
        self, regime: RegimeState
    ) -> tuple[BaseTradingAgent | None, list[str]]:
        """
        Pick the agent that leads this evaluation. Returns (agent, notes).

        Normal path: best ACTIVE (or PROBATION at half weight) agent by
        effective score. Exploration path: with probability
        `exploration_rate`, the best DORMANT agent gets the slot instead so
        it can rebuild a track record.
        """
        notes: list[str] = []
        ranked = self.evaluate_and_rank(regime)

        dormant = [r for r in ranked if r.status is AgentStatus.DORMANT]
        if dormant and self.rng.random() < self.config.exploration_rate:
            rec = dormant[0]
            notes.append(f"exploration slot → dormant agent {rec.name}")
            rec.last_selected_at = time.time()
            return self.agents.get(rec.name), notes

        for rec in ranked:
            if rec.status is AgentStatus.ACTIVE:
                rec.last_selected_at = time.time()
                notes.append(
                    f"selected {rec.name} "
                    f"(score {rec.score:.2f}, eff {self.effective_score(rec, regime):.2f})"
                )
                return self.agents.get(rec.name), notes
            if rec.status is AgentStatus.PROBATION:
                # Probation agents may lead only with a clearly strong score.
                if rec.score >= (self.config.promotion_score_threshold +
                                 self.config.demotion_score_threshold) / 2:
                    rec.last_selected_at = time.time()
                    notes.append(f"selected probation agent {rec.name}")
                    return self.agents.get(rec.name), notes

        notes.append("no eligible agent — pool degraded")
        return None, notes

    # -- health ---------------------------------------------------------------

    def health(self) -> dict[str, int]:
        counts: dict[str, int] = {}
        for rec in self.records.values():
            counts[rec.status.value] = counts.get(rec.status.value, 0) + 1
        return counts

    def is_degraded(self) -> bool:
        """Pool is degraded when no agent is ACTIVE."""
        return not any(
            r.status is AgentStatus.ACTIVE for r in self.records.values()
        )

    # -- persistence ------------------------------------------------------------

    def to_dict(self) -> dict:
        return {
            "config": self.config.to_dict(),
            "records": {name: rec.to_dict() for name, rec in self.records.items()},
        }
