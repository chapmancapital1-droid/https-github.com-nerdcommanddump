"""Market data provider — yfinance (default) with IB API stub.

Usage:
    feed = get_feed()
    bars = feed.fetch("EURUSD=X", period="60d", interval="1d")
    # bars: dict with numpy arrays: close, high, low, volume
"""
import logging
from abc import ABC, abstractmethod
from typing import Dict

import numpy as np

from config import DATA_PROVIDER, IB_CLIENT_ID, IB_HOST, IB_PORT

logger = logging.getLogger(__name__)


class DataFeed(ABC):
    @abstractmethod
    def fetch(self, symbol: str, period: str = "60d",
              interval: str = "1d") -> Dict[str, np.ndarray]:
        """Return dict with arrays: close, high, low, volume."""


class YFinanceFeed(DataFeed):
    def fetch(self, symbol: str, period: str = "60d",
              interval: str = "1d") -> Dict[str, np.ndarray]:
        try:
            import yfinance as yf
        except ImportError:
            raise RuntimeError("yfinance not installed — run: pip install yfinance")

        ticker = yf.Ticker(symbol)
        df = ticker.history(period=period, interval=interval)
        if df.empty:
            raise ValueError(f"No data returned for {symbol}")
        return {
            "close":  df["Close"].values.astype(float),
            "high":   df["High"].values.astype(float),
            "low":    df["Low"].values.astype(float),
            "volume": df["Volume"].values.astype(float),
        }


class IBFeed(DataFeed):
    """Interactive Brokers data feed stub — wire up ib_insync when ready."""

    def __init__(self) -> None:
        try:
            from ib_insync import IB, Stock, Forex
            self._IB = IB
            self._Stock = Stock
            self._Forex = Forex
        except ImportError:
            raise RuntimeError("ib_insync not installed — run: pip install ib_insync")

        self._ib = self._IB()
        self._ib.connect(IB_HOST, IB_PORT, clientId=IB_CLIENT_ID)
        logger.info("IB connected: %s:%d", IB_HOST, IB_PORT)

    def fetch(self, symbol: str, period: str = "60d",
              interval: str = "1d") -> Dict[str, np.ndarray]:
        import pandas as pd
        from ib_insync import util

        # duration / bar_size mapping (simplified)
        dur_map = {"60d": "60 D", "30d": "30 D", "90d": "90 D"}
        bar_map = {"1d": "1 day", "1h": "1 hour", "5m": "5 mins"}

        dur  = dur_map.get(period, "60 D")
        bar  = bar_map.get(interval, "1 day")

        if "/" in symbol:
            base, quote = symbol.split("/")
            contract = self._Forex(base + quote)
        else:
            contract = self._Stock(symbol, "SMART", "USD")

        bars = self._ib.reqHistoricalData(contract, endDateTime="",
                                          durationStr=dur, barSizeSetting=bar,
                                          whatToShow="MIDPOINT", useRTH=True)
        df = util.df(bars)
        return {
            "close":  df["close"].values.astype(float),
            "high":   df["high"].values.astype(float),
            "low":    df["low"].values.astype(float),
            "volume": df["volume"].values.astype(float),
        }


_feed_instance: DataFeed | None = None


def get_feed() -> DataFeed:
    global _feed_instance
    if _feed_instance is None:
        if DATA_PROVIDER == "ib":
            _feed_instance = IBFeed()
            logger.info("Using IB data feed")
        else:
            _feed_instance = YFinanceFeed()
            logger.info("Using yfinance data feed")
    return _feed_instance
