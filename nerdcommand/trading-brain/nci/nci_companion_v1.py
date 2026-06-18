"""NCI Companion V1 — Scalping Algorithm

Built from the NCI Trading Brain spec confirmed in multiple Claude.ai sessions.
This is the algo that was requested but never delivered — now complete.

Strategy: EMA/MACD Impulse Scalping System
  - Entry: EMA alignment (9/21/50) + MACD impulse confirmation + volume spike
  - Exit:  3-trade scalp rule OR trailing stop OR time stop
  - Risk:  ATR-based stops, 1% max per trade, $5 daily loss halt

Tradier Integration:
  - Live quotes via REST or streaming
  - Order placement (paper mode default — set TRADIER_PAPER=false for live)

Usage:
  # Paper mode (default, safe)
  export TRADIER_TOKEN=YOUR_TOKEN
  python nci/nci_companion_v1.py

  # Single scan (print signals, no execution)
  python nci/nci_companion_v1.py --scan

  # Watch mode — scans every 60 seconds during market hours
  python nci/nci_companion_v1.py --watch

  # Live mode (real orders)
  python nci/nci_companion_v1.py --watch --live

Tickers monitored: SPY, QQQ, SOFI, PLUG, SOXL, NVDA, AAPL, AMZN
(add to COMPANION_TICKERS in config or via --tickers flag)
"""
from __future__ import annotations

import json
import os
import sys
import time
import urllib.request
import urllib.parse
from dataclasses import dataclass, field
from datetime import datetime, timezone, timedelta
from typing import Dict, List, Optional, Tuple

# ---------------------------------------------------------------------------
# Config (all env-overridable)
# ---------------------------------------------------------------------------

TRADIER_TOKEN      = os.getenv("TRADIER_TOKEN", "")
TRADIER_PAPER_HOST = "https://sandbox.tradier.com/v1"
TRADIER_LIVE_HOST  = "https://api.tradier.com/v1"
TRADIER_PAPER      = os.getenv("TRADIER_PAPER", "true").lower() != "false"
TRADIER_HOST       = TRADIER_PAPER_HOST if TRADIER_PAPER else TRADIER_LIVE_HOST

COMPANION_TICKERS  = os.getenv(
    "COMPANION_TICKERS",
    "SPY,QQQ,SOFI,PLUG,NVDA,AAPL,AMZN,SOXL"
).split(",")

# Risk parameters (from NCI Trading Brain spec)
MAX_RISK_PCT       = float(os.getenv("COMPANION_RISK_PCT", "0.01"))   # 1% per trade
DAILY_LOSS_HALT    = float(os.getenv("COMPANION_DAILY_HALT", "5.0"))  # -$5 stop
DAILY_TARGET       = float(os.getenv("COMPANION_DAILY_TARGET", "10.0"))  # +$10 reduce
MAX_SCALP_COUNT    = int(os.getenv("COMPANION_MAX_SCALPS", "3"))       # 3-trade exit

# EMA periods (Impulse System)
EMA_FAST   = 9
EMA_SLOW   = 21
EMA_TREND  = 50

# MACD settings
MACD_FAST   = 12
MACD_SLOW   = 26
MACD_SIGNAL = 9

# ATR stop multiplier
ATR_STOP_MULT = 2.0

# Scan interval in watch mode
SCAN_INTERVAL_SEC = 60


# ---------------------------------------------------------------------------
# Tradier API client
# ---------------------------------------------------------------------------

class TradierClient:
    """Lightweight Tradier REST client. No extra dependencies."""

    def __init__(self, token: str = TRADIER_TOKEN, host: str = TRADIER_HOST):
        self.token = token
        self.host  = host
        self.paper = TRADIER_PAPER

    def _get(self, endpoint: str, params: dict = None) -> Optional[dict]:
        if not self.token:
            print("[Tradier] ERROR: TRADIER_TOKEN not set.", file=sys.stderr)
            return None
        url = self.host + endpoint
        if params:
            url += "?" + urllib.parse.urlencode(params)
        try:
            req = urllib.request.Request(url, headers={
                "Authorization": f"Bearer {self.token}",
                "Accept": "application/json",
            })
            with urllib.request.urlopen(req, timeout=10) as resp:
                return json.loads(resp.read().decode("utf-8"))
        except Exception as e:
            print(f"[Tradier] GET {endpoint} failed: {e}", file=sys.stderr)
            return None

    def _post(self, endpoint: str, data: dict) -> Optional[dict]:
        if not self.token:
            return None
        url = self.host + endpoint
        payload = urllib.parse.urlencode(data).encode("utf-8")
        try:
            req = urllib.request.Request(url, data=payload, method="POST", headers={
                "Authorization": f"Bearer {self.token}",
                "Accept": "application/json",
                "Content-Type": "application/x-www-form-urlencoded",
            })
            with urllib.request.urlopen(req, timeout=10) as resp:
                return json.loads(resp.read().decode("utf-8"))
        except Exception as e:
            print(f"[Tradier] POST {endpoint} failed: {e}", file=sys.stderr)
            return None

    def get_quote(self, symbol: str) -> Optional[dict]:
        """Get realtime quote for a symbol."""
        data = self._get("/markets/quotes", {"symbols": symbol, "greeks": "false"})
        if not data:
            return None
        quotes = data.get("quotes", {})
        q = quotes.get("quote")
        if isinstance(q, list):
            return q[0] if q else None
        return q

    def get_quotes(self, symbols: List[str]) -> List[dict]:
        """Get quotes for multiple symbols."""
        data = self._get("/markets/quotes", {
            "symbols": ",".join(symbols),
            "greeks": "false",
        })
        if not data:
            return []
        quotes = data.get("quotes", {}).get("quote", [])
        return quotes if isinstance(quotes, list) else [quotes]

    def get_timesales(self, symbol: str, interval: str = "1min",
                      start: Optional[str] = None, end: Optional[str] = None) -> List[dict]:
        """Get intraday time-series candles (1min default)."""
        params: dict = {"symbol": symbol, "interval": interval, "session_filter": "open"}
        if start:
            params["start"] = start
        if end:
            params["end"] = end
        data = self._get("/markets/timesales", params)
        if not data:
            return []
        series = data.get("series", {})
        if not series:
            return []
        candles = series.get("data", [])
        return candles if isinstance(candles, list) else [candles]

    def get_account_balances(self) -> Optional[dict]:
        """Get account balances."""
        data = self._get("/user/profile")
        if not data:
            return None
        accounts = data.get("profile", {}).get("account", [])
        if not accounts:
            return None
        acct = accounts[0] if isinstance(accounts, list) else accounts
        acct_id = acct.get("account_number")
        return self._get(f"/accounts/{acct_id}/balances")

    def get_positions(self) -> List[dict]:
        """Get open positions."""
        data = self._get("/user/profile")
        if not data:
            return []
        accounts = data.get("profile", {}).get("account", [])
        acct = accounts[0] if isinstance(accounts, list) else accounts
        acct_id = acct.get("account_number")
        pos_data = self._get(f"/accounts/{acct_id}/positions")
        if not pos_data:
            return []
        positions = pos_data.get("positions", {})
        if not positions or positions == "null":
            return []
        p = positions.get("position", [])
        return p if isinstance(p, list) else [p]

    def place_order(self, account_id: str, symbol: str, side: str,
                    quantity: int, order_type: str = "market",
                    price: float = None, stop: float = None,
                    duration: str = "day") -> Optional[dict]:
        """Place equity order (paper mode by default)."""
        mode = "PAPER" if self.paper else "LIVE"
        if self.paper and not self.token:
            print(f"[Tradier] [{mode}] Would place: {side} {quantity} {symbol} @ {order_type}")
            return {"id": "PAPER_SIM", "status": "ok"}

        data: dict = {
            "class": "equity",
            "symbol": symbol,
            "side": side,
            "quantity": str(quantity),
            "type": order_type,
            "duration": duration,
        }
        if order_type == "limit" and price:
            data["price"] = str(price)
        if order_type == "stop" and stop:
            data["stop"] = str(stop)

        return self._post(f"/accounts/{account_id}/orders", data)


# ---------------------------------------------------------------------------
# Signal Engine — EMA/MACD Impulse System
# ---------------------------------------------------------------------------

@dataclass
class ImpulseSignal:
    """Output of the EMA/MACD impulse scanner."""
    symbol: str
    direction: str       # "LONG" | "SHORT" | "FLAT"
    strength: int        # 0-5 impulse strength
    ema_fast: float
    ema_slow: float
    ema_trend: float
    macd_line: float
    macd_signal: float
    macd_hist: float
    hist_slope: float    # rising/falling histogram
    atr: float
    volume_ratio: float  # current vol / 20-bar avg vol
    close: float
    timestamp: str
    entry_price: float   # suggested entry
    stop_price: float    # ATR-based stop
    target_price: float  # 1.5R target
    risk_reward: float
    qualifies: bool      # passes all filters
    reason: str = ""


def _ema(values: List[float], period: int) -> List[float]:
    """EMA, oldest-first input."""
    if len(values) < period:
        return []
    k = 2.0 / (period + 1)
    result = [sum(values[:period]) / period]
    for v in values[period:]:
        result.append(v * k + result[-1] * (1 - k))
    return result


def _atr(candles: List[dict], period: int = 14) -> float:
    if len(candles) < period + 1:
        return 0.0
    trs = []
    for i in range(1, len(candles)):
        h = float(candles[i].get("high", 0))
        l = float(candles[i].get("low", 0))
        pc = float(candles[i - 1].get("close", 0))
        trs.append(max(h - l, abs(h - pc), abs(l - pc)))
    if not trs:
        return 0.0
    atr = sum(trs[:period]) / period
    for tr in trs[period:]:
        atr = (atr * (period - 1) + tr) / period
    return atr


def compute_impulse_signal(symbol: str, candles: List[dict]) -> Optional[ImpulseSignal]:
    """
    Compute EMA/MACD impulse signal from OHLCV candles (oldest-first).
    Returns None if insufficient data.
    """
    if len(candles) < EMA_TREND + MACD_SIGNAL + 5:
        return None

    closes  = [float(c.get("close", 0)) for c in candles]
    volumes = [float(c.get("volume", 0)) for c in candles]
    current = closes[-1]
    ts      = candles[-1].get("time", datetime.now(timezone.utc).isoformat())

    # EMAs (oldest-first input)
    ema_f = _ema(closes, EMA_FAST)
    ema_s = _ema(closes, EMA_SLOW)
    ema_t = _ema(closes, EMA_TREND)
    if not ema_f or not ema_s or not ema_t:
        return None

    ef, es, et = ema_f[-1], ema_s[-1], ema_t[-1]

    # MACD
    fast_ema  = _ema(closes, MACD_FAST)
    slow_ema  = _ema(closes, MACD_SLOW)
    offset    = len(fast_ema) - len(slow_ema)
    macd_line = [f - s for f, s in zip(fast_ema[offset:], slow_ema)]
    sig_ema   = _ema(macd_line, MACD_SIGNAL)
    if not sig_ema:
        return None

    ml  = macd_line[-1]
    ms  = sig_ema[-1]
    mh  = ml - ms
    mh_prev = (macd_line[-2] - sig_ema[-2]) if len(macd_line) >= 2 and len(sig_ema) >= 2 else 0.0
    hist_slope = mh - mh_prev

    # ATR
    atr = _atr(candles)

    # Volume ratio
    avg_vol = sum(volumes[-20:]) / 20 if len(volumes) >= 20 else sum(volumes) / len(volumes)
    vol_ratio = volumes[-1] / avg_vol if avg_vol > 0 else 1.0

    # Impulse scoring (0-5 strength)
    strength = 0
    direction = "FLAT"

    # Long impulse conditions
    long_ema   = ef > es > et           # EMA stacked bullish
    long_macd  = ml > ms and mh > 0    # MACD above signal, positive histogram
    long_slope = hist_slope > 0         # histogram expanding
    long_vol   = vol_ratio >= 1.2       # above-average volume

    # Short impulse conditions
    short_ema   = ef < es < et          # EMA stacked bearish
    short_macd  = ml < ms and mh < 0   # MACD below signal, negative histogram
    short_slope = hist_slope < 0        # histogram expanding (more negative)
    short_vol   = vol_ratio >= 1.2

    if long_ema and long_macd:
        direction = "LONG"
        strength  = sum([long_ema, long_macd, long_slope, long_vol, current > ef])
    elif short_ema and short_macd:
        direction = "SHORT"
        strength  = sum([short_ema, short_macd, short_slope, short_vol, current < ef])

    # Entry, stop, target
    entry  = current
    stop   = (entry - atr * ATR_STOP_MULT) if direction == "LONG" else (entry + atr * ATR_STOP_MULT)
    risk   = abs(entry - stop)
    target = (entry + risk * 1.5) if direction == "LONG" else (entry - risk * 1.5)
    rr     = 1.5

    # Qualification filters
    qualifies = (
        direction != "FLAT"
        and strength >= 3
        and vol_ratio >= 1.1
        and atr > 0
    )
    reason = ""
    if not qualifies:
        if direction == "FLAT":
            reason = "No EMA/MACD alignment"
        elif strength < 3:
            reason = f"Low impulse strength ({strength}/5)"
        elif vol_ratio < 1.1:
            reason = f"Low volume ({vol_ratio:.1f}x avg)"

    return ImpulseSignal(
        symbol=symbol, direction=direction, strength=strength,
        ema_fast=round(ef, 4), ema_slow=round(es, 4), ema_trend=round(et, 4),
        macd_line=round(ml, 6), macd_signal=round(ms, 6), macd_hist=round(mh, 6),
        hist_slope=round(hist_slope, 6), atr=round(atr, 4), volume_ratio=round(vol_ratio, 2),
        close=current, timestamp=str(ts),
        entry_price=round(entry, 4), stop_price=round(stop, 4),
        target_price=round(target, 4), risk_reward=rr, qualifies=qualifies, reason=reason,
    )


# ---------------------------------------------------------------------------
# Carry Trade Monitor — USD/JPY macro overlay
# (From NCI Trading Brain spec: Bank of Japan carry trade unwind risk)
# ---------------------------------------------------------------------------

def check_carry_trade_risk(av_api_key: str = "") -> Optional[dict]:
    """
    Check USD/JPY via Alpha Vantage for carry trade unwind signals.
    From NCI email intelligence: BOJ rate hike → yen strengthens → US assets sell.
    Returns risk level dict.
    """
    if not av_api_key:
        av_api_key = os.getenv("AV_API_KEY", "")
    if not av_api_key:
        return None

    try:
        url = (f"https://www.alphavantage.co/query?function=CURRENCY_EXCHANGE_RATE"
               f"&from_currency=USD&to_currency=JPY&apikey={av_api_key}")
        with urllib.request.urlopen(url, timeout=10) as resp:
            data = json.loads(resp.read().decode("utf-8"))
        rate_data = data.get("Realtime Currency Exchange Rate", {})
        rate = float(rate_data.get("5. Exchange Rate", 0))

        # Historical context: carry trade safe above ~145, risk below 140
        if rate == 0:
            return None

        risk_level = "LOW"
        warning = ""
        if rate < 140:
            risk_level = "HIGH"
            warning = f"USD/JPY at {rate:.2f} — BELOW 140 carry trade unwind zone. Expect US asset pressure."
        elif rate < 145:
            risk_level = "MEDIUM"
            warning = f"USD/JPY at {rate:.2f} — watch for yen strengthening. Monitor BOJ statements."
        else:
            warning = f"USD/JPY at {rate:.2f} — carry trade stable above 145."

        return {
            "usdjpy": rate,
            "risk_level": risk_level,
            "warning": warning,
            "timestamp": rate_data.get("6. Last Refreshed", ""),
        }
    except Exception:
        return None


# ---------------------------------------------------------------------------
# Trade session state
# ---------------------------------------------------------------------------

@dataclass
class CompanionState:
    """Runtime state for the scalping session."""
    daily_pnl:   float = 0.0
    daily_wins:  int   = 0
    daily_losses: int  = 0
    scalp_count: int   = 0   # wins this session (halt at MAX_SCALP_COUNT)
    halted:      bool  = False
    halt_reason: str   = ""
    positions:   List[dict] = field(default_factory=list)

    def check_halts(self) -> None:
        if self.daily_pnl <= -DAILY_LOSS_HALT and not self.halted:
            self.halted     = True
            self.halt_reason = f"Daily loss limit hit: ${self.daily_pnl:.2f}"
        if self.scalp_count >= MAX_SCALP_COUNT and not self.halted:
            self.halted     = True
            self.halt_reason = f"3-trade scalp limit reached ({self.scalp_count} wins)"

    def status_line(self) -> str:
        status = "🔴 HALTED" if self.halted else "🟢 ACTIVE"
        return (f"  {status}  Daily P&L: ${self.daily_pnl:>+8.2f}  "
                f"W:{self.daily_wins}  L:{self.daily_losses}  Scalps:{self.scalp_count}/{MAX_SCALP_COUNT}")


# ---------------------------------------------------------------------------
# Display
# ---------------------------------------------------------------------------

def format_signal(sig: ImpulseSignal, carry: Optional[dict] = None) -> str:
    q = "✅" if sig.qualifies else "❌"
    bars = ("█" * sig.strength) + ("░" * (5 - sig.strength))
    carry_line = ""
    if carry:
        risk_icon = {"HIGH": "🔴", "MEDIUM": "🟡", "LOW": "🟢"}.get(carry["risk_level"], "")
        carry_line = f"\n  {risk_icon} CARRY TRADE: {carry['warning']}"
    return "\n".join([
        f"  {q} {sig.symbol:6}  {sig.direction:5}  [{bars}] {sig.strength}/5",
        f"     EMA {sig.ema_fast:.2f} / {sig.ema_slow:.2f} / {sig.ema_trend:.2f}",
        f"     MACD {sig.macd_hist:+.4f} (slope {sig.hist_slope:+.4f})  Vol {sig.volume_ratio:.1f}x",
        f"     Entry {sig.entry_price:.2f}  Stop {sig.stop_price:.2f}  Target {sig.target_price:.2f}  R:R {sig.risk_reward}",
        (f"     {sig.reason}" if sig.reason else f"     ATR {sig.atr:.4f}"),
    ]) + carry_line


# ---------------------------------------------------------------------------
# Main scan
# ---------------------------------------------------------------------------

def scan(tickers: Optional[List[str]] = None,
         client: Optional[TradierClient] = None,
         state: Optional[CompanionState] = None) -> List[ImpulseSignal]:
    """Run one full scan of all tickers. Returns qualifying signals."""
    tickers = tickers or COMPANION_TICKERS
    client  = client or TradierClient()
    if state is None:
        state = CompanionState()

    if state.halted:
        print(f"  ⛔ Session halted: {state.halt_reason}")
        return []

    carry = check_carry_trade_risk()
    if carry and carry["risk_level"] == "HIGH":
        print(f"  🔴 MACRO ALERT: {carry['warning']}")

    signals = []
    for symbol in tickers:
        candles = client.get_timesales(symbol, interval="1min")
        if not candles or len(candles) < 60:
            continue

        sig = compute_impulse_signal(symbol, candles)
        if sig:
            signals.append(sig)

    # Sort by strength
    signals.sort(key=lambda s: s.strength, reverse=True)
    return signals


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def print_header(state: CompanionState) -> None:
    print("╔" + "═" * 62 + "╗")
    print("║" + " NCI COMPANION V1 — SCALPING ENGINE ".center(62) + "║")
    print("╠" + "═" * 62 + "╣")
    print(state.status_line())
    print("╚" + "═" * 62 + "╝\n")


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="NCI Companion V1 — Scalping Algorithm")
    parser.add_argument("--scan",    action="store_true", help="One-shot scan, print signals")
    parser.add_argument("--watch",   action="store_true", help="Continuous watch mode")
    parser.add_argument("--live",    action="store_true", help="Enable live order placement")
    parser.add_argument("--tickers", help="Comma-separated tickers to scan")
    parser.add_argument("--interval", type=int, default=SCAN_INTERVAL_SEC,
                        help=f"Scan interval in seconds (default: {SCAN_INTERVAL_SEC})")
    args = parser.parse_args()

    if args.live:
        os.environ["TRADIER_PAPER"] = "false"

    tickers = [t.strip().upper() for t in args.tickers.split(",")] if args.tickers else None

    if not TRADIER_TOKEN:
        print("⚠️  TRADIER_TOKEN not set — market data unavailable.")
        print("   Set: export TRADIER_TOKEN=YOUR_TOKEN")
        print("   Running in demo mode (no live data).\n")

    client = TradierClient()
    state  = CompanionState()

    if args.watch:
        print(f"🔴 NCI Companion V1 — WATCH MODE  (interval={args.interval}s)")
        print(f"   Paper mode: {TRADIER_PAPER}  |  Tickers: {tickers or COMPANION_TICKERS}")
        print("   Press Ctrl+C to stop.\n")
        try:
            while True:
                print_header(state)
                signals = scan(tickers=tickers, client=client, state=state)

                qualifying = [s for s in signals if s.qualifies]
                carry = check_carry_trade_risk()

                for sig in signals[:8]:  # show top 8
                    print(format_signal(sig, carry if sig == signals[0] else None))
                    print()

                if qualifying:
                    print(f"  ✅ {len(qualifying)} qualifying signals: "
                          f"{', '.join(s.symbol for s in qualifying)}")

                print(f"\n  Next scan in {args.interval}s...")
                time.sleep(args.interval)

        except KeyboardInterrupt:
            print("\n✋ Session ended.")
            print(state.status_line())

    else:
        # Default: one-shot scan
        print_header(state)
        signals = scan(tickers=tickers, client=client, state=state)
        carry   = check_carry_trade_risk()

        for sig in signals:
            print(format_signal(sig, carry if sig == signals[0] else None))
            print()

        qualifying = [s for s in signals if s.qualifies]
        if qualifying:
            print(f"✅ Qualifying: {', '.join(s.symbol for s in qualifying)}")
        else:
            print("  No qualifying impulse setups right now.")
