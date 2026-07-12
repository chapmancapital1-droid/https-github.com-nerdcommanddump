"""
PID position-sizing controller.

Controls the lot multiplier the EA applies to its base lot, steering the
equity curve's slope (measured in R/day) toward a setpoint:

  * equity growing faster than target  → integral builds, sizing eases up
    (don't over-press a hot streak)
  * equity bleeding                    → error goes negative, sizing shrinks
    fast via the proportional + derivative terms

Anti-windup clamps the integral; output is clamped to [output_min,
output_max] so sizing can never explode or hit zero silently.
"""

from __future__ import annotations

from .models import PIDConfig


class PIDController:
    def __init__(self, config: PIDConfig | None = None):
        self.config = config or PIDConfig()
        self._integral = 0.0
        self._prev_error: float | None = None

    def reset(self) -> None:
        self._integral = 0.0
        self._prev_error = None

    def update(self, measured_r_per_day: float, dt_days: float = 1.0) -> float:
        """
        Feed the latest equity slope; get back the lot multiplier.

        error > 0  → performing under target → controller trims size
        error < 0  → performing over target  → controller allows more
        (Sizing follows performance rather than fighting it: the multiplier
        is 1 - PID(error), clamped.)
        """
        cfg = self.config
        dt = max(dt_days, 1e-9)
        error = cfg.setpoint_r_per_day - measured_r_per_day

        self._integral += error * dt
        self._integral = max(-cfg.integral_limit,
                             min(cfg.integral_limit, self._integral))

        derivative = 0.0
        if self._prev_error is not None:
            derivative = (error - self._prev_error) / dt
        self._prev_error = error

        control = cfg.kp * error + cfg.ki * self._integral + cfg.kd * derivative
        multiplier = 1.0 - control * 0.25   # gentle: full-scale error trims 25%/unit
        return max(cfg.output_min, min(cfg.output_max, multiplier))

    def state(self) -> dict:
        return {
            "integral": self._integral,
            "prev_error": self._prev_error,
            "config": self.config.to_dict(),
        }
