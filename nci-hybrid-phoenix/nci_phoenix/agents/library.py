"""
The Phoenix agent roster — six reference agents.

These carry real, if intentionally simple, decision logic so the whole
brain runs end-to-end today. Each one is a template: the dev team replaces
`propose()` internals with the production EA logic while keeping the
interface, and the pool/orchestrator/risk layers don't change at all.

Roster:
  Scalper_Phoenix       — M1/M5 micro-scalps in calm, tight markets
  Breakout_Phoenix      — trades coil → expansion transitions
  MeanRev_Adaptive      — fades edges of established ranges
  Trend_Rider_Quantum   — rides confirmed ADX trends
  News_Shield           — defensive: flattens exposure around red news
  Hybrid_Rescue         — conservative blend used when the pool degrades
"""

from __future__ import annotations

from ..models import MarketSnapshot, Regime, RegimeState, Signal
from .base import BaseTradingAgent


class ScalperPhoenix(BaseTradingAgent):
    name = "Scalper_Phoenix"
    version = "4.0"
    specializations = (Regime.RANGING_CHOPPY, Regime.LOW_VOL_COMPRESSION)

    MAX_SPREAD_PTS = 12.0
    SESSIONS = {"london", "newyork", "overlap"}

    def propose(self, regime: RegimeState, snap: MarketSnapshot) -> Signal:
        if snap.spread_pts > self.MAX_SPREAD_PTS:
            return Signal.FLAT
        if snap.session not in self.SESSIONS:
            return Signal.FLAT
        if snap.news_impact >= 0.4:          # scalps hate news wicks
            return Signal.FLAT
        if regime.regime not in self.specializations:
            return Signal.FLAT
        # Fade micro-drift against short-term direction inside quiet tape.
        if snap.trend_direction > 0:
            return Signal.SHORT
        if snap.trend_direction < 0:
            return Signal.LONG
        return Signal.FLAT

    def risk_fraction(self, regime: RegimeState, snap: MarketSnapshot) -> float:
        return 0.5   # many small bets, half allocation each


class BreakoutPhoenix(BaseTradingAgent):
    name = "Breakout_Phoenix"
    version = "3.0"
    specializations = (Regime.PRE_BREAKOUT_COIL, Regime.HIGH_VOL_EXPANSION)

    def propose(self, regime: RegimeState, snap: MarketSnapshot) -> Signal:
        if regime.regime == Regime.PRE_BREAKOUT_COIL:
            # Position with the pressure building under the coil.
            if snap.trend_direction > 0:
                return Signal.LONG
            if snap.trend_direction < 0:
                return Signal.SHORT
            return Signal.FLAT
        if regime.regime == Regime.HIGH_VOL_EXPANSION and snap.adx >= 25:
            return Signal.LONG if snap.trend_direction >= 0 else Signal.SHORT
        return Signal.FLAT


class MeanRevAdaptive(BaseTradingAgent):
    name = "MeanRev_Adaptive"
    version = "2.0"
    specializations = (Regime.RANGING_CHOPPY,)

    def propose(self, regime: RegimeState, snap: MarketSnapshot) -> Signal:
        if regime.regime is not Regime.RANGING_CHOPPY:
            return Signal.FLAT
        if regime.confidence < 0.4:          # only fade well-formed ranges
            return Signal.FLAT
        # Fade the latest push back toward the middle of the range.
        if snap.trend_direction > 0:
            return Signal.SHORT
        if snap.trend_direction < 0:
            return Signal.LONG
        return Signal.FLAT


class TrendRiderQuantum(BaseTradingAgent):
    name = "Trend_Rider_Quantum"
    version = "1.0"
    specializations = (Regime.TRENDING_BULLISH, Regime.TRENDING_BEARISH)

    MIN_ADX = 25.0

    def propose(self, regime: RegimeState, snap: MarketSnapshot) -> Signal:
        if snap.adx < self.MIN_ADX:
            return Signal.FLAT
        if regime.regime is Regime.TRENDING_BULLISH and snap.trend_direction > 0:
            return Signal.LONG
        if regime.regime is Regime.TRENDING_BEARISH and snap.trend_direction < 0:
            return Signal.SHORT
        return Signal.FLAT


class NewsShield(BaseTradingAgent):
    name = "News_Shield"
    version = "1.0"
    specializations = (Regime.NEWS_DRIVEN,)

    def propose(self, regime: RegimeState, snap: MarketSnapshot) -> Signal:
        # Defensive specialist: its whole job is to keep the book flat
        # while news volatility is in charge.
        return Signal.FLAT

    def risk_fraction(self, regime: RegimeState, snap: MarketSnapshot) -> float:
        return 0.0


class HybridRescue(BaseTradingAgent):
    name = "Hybrid_Rescue"
    version = "2.0"
    specializations = ()   # generalist by design

    def propose(self, regime: RegimeState, snap: MarketSnapshot) -> Signal:
        # Ultra-conservative: only take A+ trend setups, otherwise stand down.
        if snap.adx >= 35 and regime.confidence >= 0.5:
            if regime.regime is Regime.TRENDING_BULLISH and snap.trend_direction > 0:
                return Signal.LONG
            if regime.regime is Regime.TRENDING_BEARISH and snap.trend_direction < 0:
                return Signal.SHORT
        return Signal.FLAT

    def risk_fraction(self, regime: RegimeState, snap: MarketSnapshot) -> float:
        return 0.35  # rescue mode trades small on purpose


def default_roster() -> list[BaseTradingAgent]:
    """The stock six-agent Phoenix roster."""
    return [
        ScalperPhoenix(),
        BreakoutPhoenix(),
        MeanRevAdaptive(),
        TrendRiderQuantum(),
        NewsShield(),
        HybridRescue(),
    ]
