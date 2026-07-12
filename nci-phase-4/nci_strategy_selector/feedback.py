"""
Confidence calibration — Phase 5 interactive learning upgrade.

The selector emits a predicted confidence for every recommendation. This
module compares predicted confidence against realized outcomes and
produces a per-strategy calibration factor, so a strategy the model is
chronically overconfident about gets its future confidence trimmed —
and vice versa.

Calibration factor = realized win rate / mean predicted confidence,
EMA-smoothed, clamped to [0.5, 1.5] so one streak can't whipsaw scores.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from .models import StrategyType, TradeOutcome

EMA_ALPHA = 0.25
FACTOR_MIN = 0.5
FACTOR_MAX = 1.5
MIN_SAMPLES = 3  # below this, factor stays neutral (1.0)


@dataclass
class CalibrationRecord:
    """Running calibration state for one strategy."""
    samples: int = 0
    wins: int = 0
    confidence_sum: float = 0.0
    factor: float = 1.0  # EMA-smoothed calibration multiplier

    def to_dict(self) -> dict:
        return {
            "samples": self.samples,
            "wins": self.wins,
            "confidence_sum": self.confidence_sum,
            "factor": self.factor,
        }

    @classmethod
    def from_dict(cls, d: dict) -> "CalibrationRecord":
        return cls(**d)


class ConfidenceCalibrator:
    """Learns how much to trust each strategy's predicted confidence."""

    def __init__(self):
        self.records: dict[str, CalibrationRecord] = {}

    def observe(
        self,
        strategy: StrategyType,
        predicted_confidence: float,
        outcome: TradeOutcome,
    ) -> None:
        """Record one (prediction, outcome) pair and update the factor."""
        rec = self.records.setdefault(strategy.value, CalibrationRecord())
        rec.samples += 1
        rec.confidence_sum += max(min(predicted_confidence, 1.0), 0.0)
        if outcome.pnl > 0:
            rec.wins += 1

        if rec.samples >= MIN_SAMPLES:
            mean_conf = rec.confidence_sum / rec.samples
            win_rate = rec.wins / rec.samples
            raw = win_rate / mean_conf if mean_conf > 0 else 1.0
            raw = max(min(raw, FACTOR_MAX), FACTOR_MIN)
            rec.factor = (1 - EMA_ALPHA) * rec.factor + EMA_ALPHA * raw

    def adjust(self, strategy: StrategyType, confidence: float) -> float:
        """Apply the learned factor to a fresh confidence estimate."""
        rec = self.records.get(strategy.value)
        if rec is None or rec.samples < MIN_SAMPLES:
            return confidence
        return round(max(min(confidence * rec.factor, 1.0), 0.05), 4)

    def to_dict(self) -> dict:
        return {name: r.to_dict() for name, r in self.records.items()}

    @classmethod
    def from_dict(cls, d: dict) -> "ConfidenceCalibrator":
        cal = cls()
        cal.records = {name: CalibrationRecord.from_dict(r) for name, r in d.items()}
        return cal
