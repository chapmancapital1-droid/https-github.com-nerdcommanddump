"""
Monte Carlo robustness engine — the promotion gate.

No agent (or parameter change) is trusted live until its realized R-series
survives block-bootstrap resampling:

  * blocks preserve win/loss streak structure (unlike naive shuffling)
  * each simulation replays a resampled equity path
  * acceptance requires ALL of:
      - P(ruin)              <= max_ruin_probability
      - median expectancy    >= min_expectancy_r
      - median max drawdown  <= max_median_drawdown_r

Deterministic under a seeded RNG so validation runs are reproducible.
"""

from __future__ import annotations

import random
import statistics
from dataclasses import dataclass, field

from .models import MonteCarloConfig


@dataclass
class MonteCarloReport:
    accepted: bool
    simulations: int
    ruin_probability: float
    median_expectancy_r: float
    median_max_drawdown_r: float
    p95_max_drawdown_r: float
    reasons: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "accepted": self.accepted,
            "simulations": self.simulations,
            "ruin_probability": round(self.ruin_probability, 4),
            "median_expectancy_r": round(self.median_expectancy_r, 4),
            "median_max_drawdown_r": round(self.median_max_drawdown_r, 4),
            "p95_max_drawdown_r": round(self.p95_max_drawdown_r, 4),
            "reasons": self.reasons,
        }


def _block_resample(
    series: list[float], block_size: int, rng: random.Random
) -> list[float]:
    """Sample contiguous blocks (with replacement) until length matches."""
    n = len(series)
    out: list[float] = []
    while len(out) < n:
        start = rng.randrange(n)
        out.extend(series[start : start + block_size])
    return out[:n]


def _path_stats(r_series: list[float], ruin_threshold_r: float) -> tuple[float, float, bool]:
    """Walk one resampled path → (expectancy, max drawdown in R, ruined?)."""
    equity = 0.0
    peak = 0.0
    max_dd = 0.0
    ruined = False
    for r in r_series:
        equity += r
        peak = max(peak, equity)
        dd = peak - equity
        max_dd = max(max_dd, dd)
        if dd >= ruin_threshold_r:
            ruined = True
    expectancy = equity / len(r_series) if r_series else 0.0
    return expectancy, max_dd, ruined


class MonteCarloEngine:
    def __init__(self, config: MonteCarloConfig | None = None, seed: int | None = None):
        self.config = config or MonteCarloConfig()
        self.rng = random.Random(seed)

    def validate(self, r_series: list[float]) -> MonteCarloReport:
        """
        Run the full bootstrap validation over a realized R-multiple series.
        Series shorter than 2 blocks is auto-rejected: not enough evidence.
        """
        cfg = self.config
        reasons: list[str] = []

        if len(r_series) < cfg.block_size * 2:
            return MonteCarloReport(
                accepted=False,
                simulations=0,
                ruin_probability=1.0,
                median_expectancy_r=0.0,
                median_max_drawdown_r=0.0,
                p95_max_drawdown_r=0.0,
                reasons=[
                    f"insufficient history: {len(r_series)} trades "
                    f"(need >= {cfg.block_size * 2})"
                ],
            )

        # Ruin measured in R: a drawdown this deep in R-terms ≈ the equity-%
        # ruin threshold under 1%-risk-per-R sizing.
        ruin_threshold_r = cfg.ruin_threshold_pct  # 30% ≈ 30R at 1% risk/trade

        expectancies: list[float] = []
        drawdowns: list[float] = []
        ruins = 0
        for _ in range(cfg.simulations):
            path = _block_resample(r_series, cfg.block_size, self.rng)
            exp, dd, ruined = _path_stats(path, ruin_threshold_r)
            expectancies.append(exp)
            drawdowns.append(dd)
            ruins += int(ruined)

        ruin_p = ruins / cfg.simulations
        med_exp = statistics.median(expectancies)
        med_dd = statistics.median(drawdowns)
        p95_dd = sorted(drawdowns)[int(0.95 * len(drawdowns)) - 1]

        if ruin_p > cfg.max_ruin_probability:
            reasons.append(
                f"P(ruin) {ruin_p:.3f} > limit {cfg.max_ruin_probability:.3f}"
            )
        if med_exp < cfg.min_expectancy_r:
            reasons.append(
                f"median expectancy {med_exp:.3f}R < floor {cfg.min_expectancy_r}R"
            )
        if med_dd > cfg.max_median_drawdown_r:
            reasons.append(
                f"median max DD {med_dd:.1f}R > cap {cfg.max_median_drawdown_r}R"
            )

        return MonteCarloReport(
            accepted=not reasons,
            simulations=cfg.simulations,
            ruin_probability=ruin_p,
            median_expectancy_r=med_exp,
            median_max_drawdown_r=med_dd,
            p95_max_drawdown_r=p95_dd,
            reasons=reasons or ["all acceptance criteria met"],
        )
