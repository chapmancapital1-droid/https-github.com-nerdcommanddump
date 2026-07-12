"""
Regime detection — multi-method weighted scoring.

Five detectors vote, each producing evidence for one or more regimes:

  1. Volatility clustering   (ATR vs baseline → expansion / compression)
  2. Trend strength          (ADX + structure direction → trending)
  3. Range structure         (narrow high-low band → ranging / coil)
  4. News pressure           (impact score → news-driven)
  5. Coil detection          (compression + rising ADX → pre-breakout)

Scores are combined with configurable weights; the winner becomes the
regime, with confidence = winner share of total score. Deterministic and
pure: same snapshot in, same RegimeState out.
"""

from __future__ import annotations

from .models import MarketSnapshot, Regime, RegimeState

# How much each detector's vote counts.
DEFAULT_WEIGHTS: dict[str, float] = {
    "volatility": 1.0,
    "trend": 1.2,
    "range": 1.0,
    "news": 1.4,
    # A coil IS compression plus building pressure — the more specific read
    # must outweigh the generic volatility vote or it can never win.
    "coil": 1.3,
}

# Detector thresholds — tune per market/timeframe.
ATR_EXPANSION_RATIO = 1.5     # ATR this many times baseline = expansion
ATR_COMPRESSION_RATIO = 0.65
ADX_TRENDING = 25.0
ADX_STRONG = 40.0
RANGE_TIGHT_PCT = 0.35        # range narrower than this % of price = tight
NEWS_HOT = 0.6


class RegimeDetector:
    def __init__(self, weights: dict[str, float] | None = None):
        self.weights = dict(DEFAULT_WEIGHTS)
        if weights:
            self.weights.update(weights)

    def detect(self, snap: MarketSnapshot) -> RegimeState:
        scores: dict[Regime, float] = {r: 0.0 for r in Regime}
        notes: list[str] = []

        # 1. Volatility clustering
        if snap.atr_baseline > 0:
            ratio = snap.atr / snap.atr_baseline
            if ratio >= ATR_EXPANSION_RATIO:
                scores[Regime.HIGH_VOL_EXPANSION] += self.weights["volatility"]
                notes.append(f"ATR ratio {ratio:.2f} → volatility expansion")
            elif ratio <= ATR_COMPRESSION_RATIO:
                scores[Regime.LOW_VOL_COMPRESSION] += self.weights["volatility"]
                notes.append(f"ATR ratio {ratio:.2f} → volatility compression")

        # 2. Trend strength + direction
        if snap.adx >= ADX_TRENDING and snap.trend_direction != 0:
            strength = self.weights["trend"] * (
                1.0 if snap.adx < ADX_STRONG else 1.5
            )
            target = (
                Regime.TRENDING_BULLISH
                if snap.trend_direction > 0
                else Regime.TRENDING_BEARISH
            )
            scores[target] += strength
            notes.append(f"ADX {snap.adx:.0f} dir {snap.trend_direction:+d} → {target.value}")

        # 3. Range structure
        if 0 < snap.range_width_pct <= RANGE_TIGHT_PCT and snap.adx < ADX_TRENDING:
            scores[Regime.RANGING_CHOPPY] += self.weights["range"]
            notes.append(f"Range {snap.range_width_pct:.2f}% + ADX {snap.adx:.0f} → ranging")

        # 4. News pressure — dominates when hot
        if snap.news_impact >= NEWS_HOT:
            scores[Regime.NEWS_DRIVEN] += self.weights["news"] * (
                1.0 + snap.news_impact
            )
            notes.append(f"News impact {snap.news_impact:.2f} → news-driven")

        # 5. Pre-breakout coil: compression + building trend pressure
        if (
            snap.atr_baseline > 0
            and snap.atr / snap.atr_baseline <= ATR_COMPRESSION_RATIO
            and snap.adx >= ADX_TRENDING * 0.7
        ):
            scores[Regime.PRE_BREAKOUT_COIL] += self.weights["coil"]
            notes.append("Compression with rising ADX → pre-breakout coil")

        total = sum(scores.values())
        if total <= 0:
            return RegimeState(regime=Regime.UNKNOWN, confidence=0.0, notes=notes)

        winner = max(scores, key=lambda r: scores[r])
        confidence = scores[winner] / total
        return RegimeState(
            regime=winner,
            confidence=round(confidence, 4),
            scores={r.value: round(s, 4) for r, s in scores.items() if s > 0},
            notes=notes,
        )
