"""
Strategy Selector — recommends options strategies based on market context and user preferences.

Uses MarketContext signals to filter candidates, then ranks by fit.
"""

from __future__ import annotations

from .models import (
    StrategyType, MarketContext, UserPreferences, StrategyRecommendation,
    GreeksSummary, RiskProfile
)
from typing import Optional
import math


class StrategySelector:
    """Recommends options strategies based on market conditions and user preferences."""

    def __init__(self):
        self.strategy_db = self._build_strategy_db()

    def _build_strategy_db(self) -> dict[StrategyType, dict]:
        """Build strategy characteristics database."""
        return {
            StrategyType.COVERED_CALL: {
                "bias": ["neutral", "bullish"],
                "iv_preference": "high",
                "direction_profit": "neutral",
                "risk_level": "low",
                "capital_req": "high",
                "time_decay": "positive",
                "breakeven_shift": 0,
            },
            StrategyType.CASH_SECURED_PUT: {
                "bias": ["neutral", "bullish"],
                "iv_preference": "high",
                "direction_profit": "neutral",
                "risk_level": "medium",
                "capital_req": "high",
                "time_decay": "positive",
                "breakeven_shift": 0,
            },
            StrategyType.BULL_CALL_SPREAD: {
                "bias": ["bullish"],
                "iv_preference": "medium",
                "direction_profit": "bullish",
                "risk_level": "low",
                "capital_req": "medium",
                "time_decay": "negative",
                "breakeven_shift": 1,
            },
            StrategyType.BEAR_CALL_SPREAD: {
                "bias": ["bearish"],
                "iv_preference": "high",
                "direction_profit": "bearish",
                "risk_level": "low",
                "capital_req": "medium",
                "time_decay": "positive",
                "breakeven_shift": -1,
            },
            StrategyType.BULL_PUT_SPREAD: {
                "bias": ["neutral", "bullish"],
                "iv_preference": "high",
                "direction_profit": "bullish",
                "risk_level": "low",
                "capital_req": "medium",
                "time_decay": "positive",
                "breakeven_shift": -1,
            },
            StrategyType.BEAR_PUT_SPREAD: {
                "bias": ["neutral", "bearish"],
                "iv_preference": "high",
                "direction_profit": "bearish",
                "risk_level": "low",
                "capital_req": "medium",
                "time_decay": "positive",
                "breakeven_shift": 1,
            },
            StrategyType.IRON_CONDOR: {
                "bias": ["neutral"],
                "iv_preference": "high",
                "direction_profit": "neutral",
                "risk_level": "medium",
                "capital_req": "medium",
                "time_decay": "positive",
                "breakeven_shift": 0,
            },
            StrategyType.LONG_STRADDLE: {
                "bias": ["neutral"],
                "iv_preference": "low",
                "direction_profit": "volatile",
                "risk_level": "high",
                "capital_req": "medium",
                "time_decay": "negative",
                "breakeven_shift": 0,
            },
            StrategyType.SHORT_STRADDLE: {
                "bias": ["neutral"],
                "iv_preference": "high",
                "direction_profit": "neutral",
                "risk_level": "high",
                "capital_req": "high",
                "time_decay": "positive",
                "breakeven_shift": 0,
            },
            StrategyType.LONG_STRANGLE: {
                "bias": ["neutral"],
                "iv_preference": "low",
                "direction_profit": "volatile",
                "risk_level": "high",
                "capital_req": "low",
                "time_decay": "negative",
                "breakeven_shift": 0,
            },
            StrategyType.SHORT_STRANGLE: {
                "bias": ["neutral"],
                "iv_preference": "high",
                "direction_profit": "neutral",
                "risk_level": "medium",
                "capital_req": "low",
                "time_decay": "positive",
                "breakeven_shift": 0,
            },
            StrategyType.DIAGONAL_SPREAD: {
                "bias": ["neutral", "bullish"],
                "iv_preference": "medium",
                "direction_profit": "bullish",
                "risk_level": "medium",
                "capital_req": "low",
                "time_decay": "mixed",
                "breakeven_shift": 0,
            },
            StrategyType.CALENDAR_SPREAD: {
                "bias": ["neutral"],
                "iv_preference": "mixed",
                "direction_profit": "neutral",
                "risk_level": "low",
                "capital_req": "low",
                "time_decay": "positive",
                "breakeven_shift": 0,
            },
        }

    def select_strategies(
        self,
        context: MarketContext,
        prefs: UserPreferences,
        top_n: int = 3,
    ) -> list[tuple[StrategyType, float]]:
        """
        Select top N strategies ranked by fit score.

        Returns: [(strategy, fit_score), ...]
        """
        scores: dict[StrategyType, float] = {}

        for strategy, attrs in self.strategy_db.items():
            score = 0.0

            # Bias match (critical)
            if prefs.bias in attrs["bias"]:
                score += 2.0
            else:
                score -= 1.0

            # IV preference match
            if attrs["iv_preference"] == "high" and context.iv_rank > 70:
                score += 1.5
            elif attrs["iv_preference"] == "low" and context.iv_rank < 30:
                score += 1.5
            elif attrs["iv_preference"] == "medium" and 30 <= context.iv_rank <= 70:
                score += 1.0
            else:
                score -= 0.5

            # IV trend alignment
            if context.iv_trend > 0 and attrs["time_decay"] == "positive":
                score += 0.5
            elif context.iv_trend < 0 and attrs["time_decay"] == "negative":
                score += 0.5

            # Risk level vs user profile
            risk_map = {
                "conservative": ["low"],
                "moderate": ["low", "medium"],
                "aggressive": ["low", "medium", "high"],
            }
            if attrs["risk_level"] in risk_map[prefs.risk_profile.value]:
                score += 1.0
            else:
                score -= 1.0

            # Liquidity check (filter if too low)
            if context.liquidity_score < 0.5 and attrs["capital_req"] in ["high", "medium"]:
                score -= 2.0

            # Event risk
            if context.event_proximity_days and context.event_proximity_days < 1:
                if attrs["time_decay"] == "positive":
                    score += 0.5  # theta works for us
                else:
                    score -= 0.5

            # News sentiment
            if abs(context.news_sentiment) > 0.7:
                if attrs["direction_profit"] == "volatile":
                    score += 0.5
                elif attrs["direction_profit"] == "neutral":
                    score -= 0.5

            scores[strategy] = max(score, 0.1)

        # Sort by score
        sorted_strategies = sorted(scores.items(), key=lambda x: x[1], reverse=True)
        return sorted_strategies[:top_n]

    def estimate_greeks(
        self,
        strategy: StrategyType,
        context: MarketContext,
        prefs: UserPreferences,
    ) -> GreeksSummary:
        """Estimate Greeks for a strategy (simplified model)."""
        # Simplified Greeks estimation for demo
        price = context.price
        iv_rank = context.iv_rank / 100.0

        if strategy == StrategyType.COVERED_CALL:
            delta = 0.5
            gamma = 0.02
            theta = 0.05
            vega = -0.03
            rho = 0.01
        elif strategy == StrategyType.BULL_CALL_SPREAD:
            delta = 0.35
            gamma = 0.03
            theta = -0.02
            vega = 0.02
            rho = 0.005
        elif strategy == StrategyType.BULL_PUT_SPREAD:
            delta = 0.40
            gamma = -0.02
            theta = 0.08
            vega = -0.05
            rho = 0.01
        elif strategy == StrategyType.IRON_CONDOR:
            delta = 0.1
            gamma = -0.01
            theta = 0.10
            vega = -0.08
            rho = 0.005
        else:
            delta = 0.3
            gamma = 0.02
            theta = 0.03
            vega = 0.0
            rho = 0.005

        return GreeksSummary(
            delta=round(delta, 4),
            gamma=round(gamma, 4),
            theta=round(theta, 4),
            vega=round(vega, 4),
            rho=round(rho, 4),
        )

    def build_recommendation(
        self,
        strategy: StrategyType,
        context: MarketContext,
        prefs: UserPreferences,
        fit_score: float,
        reasoning: str,
    ) -> StrategyRecommendation:
        """Build a complete strategy recommendation."""
        greeks = self.estimate_greeks(strategy, context, prefs)

        # Estimate profit/loss zones (scaled to 1-2 contract typical sizes)
        price = context.price
        entry_price = max_loss = max_profit = 0.0
        contract_scalar = 100  # typical option contract

        if strategy == StrategyType.COVERED_CALL:
            entry_price = price * 0.02  # 2% credit
            max_profit = entry_price * contract_scalar
            max_loss = price * contract_scalar * 0.10  # 10% of stock value
            breakeven_price = price - entry_price
        elif strategy == StrategyType.BULL_CALL_SPREAD:
            entry_price = price * 0.01  # 1% debit
            max_profit = price * 0.05 * contract_scalar * 0.5
            max_loss = entry_price * contract_scalar
            breakeven_price = price + entry_price
        elif strategy == StrategyType.IRON_CONDOR:
            entry_price = price * -0.015  # 1.5% credit
            max_profit = abs(entry_price) * contract_scalar
            max_loss = price * 0.05 * contract_scalar * 0.5
            breakeven_price = price
        else:
            entry_price = price * 0.02
            max_profit = price * 0.10 * contract_scalar * 0.3
            max_loss = price * 0.05 * contract_scalar * 0.3
            breakeven_price = price

        # Risk rating based on max loss
        if max_loss > prefs.max_loss_dollars:
            risk_rating = "high"
        elif max_loss > prefs.max_loss_dollars * 0.6:
            risk_rating = "medium"
        else:
            risk_rating = "low"

        # Legs structure (simplified)
        legs = [{"symbol": context.symbol, "right": "call", "strike": price, "qty": 1}]

        return StrategyRecommendation(
            strategy=strategy,
            legs=legs,
            entry_price=round(entry_price, 2),
            max_profit=round(max_profit, 2),
            max_loss=round(max_loss, 2),
            breakeven_price=round(breakeven_price, 2),
            probability_profit=min(0.7 + fit_score * 0.2, 0.95),
            greeks=greeks,
            confidence_score=min(0.5 + fit_score * 0.25, 1.0),
            reasoning=reasoning,
            risk_rating=risk_rating,
        )
