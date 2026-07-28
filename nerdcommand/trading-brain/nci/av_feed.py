"""Alpha Vantage FX Live Data Feed — NCI Brain connection.

Fetches realtime and historical FX candle data from Alpha Vantage,
computes NCI-compatible indicators (ADX, FER, ATR, RSI, MACD, DMA, ABC stage,
buy/sell confluence), and writes NCI_LiveData.json in the SAME FORMAT as the
MT4 EA so the Bridge and LLM brain work without MT4 running.

Data flow:
  Alpha Vantage API
      ├─ CURRENCY_EXCHANGE_RATE  → realtime spot (free tier)
      └─ FX_INTRADAY / FX_DAILY → OHLCV candles (premium / free)
               ↓
        av_feed.py (indicators engine)
               ↓  writes same files as MT4 EA
        NCI_LiveData.json + signal_proposal.json
               ↓
        nci_bridge.py (reads, displays, consolidates)
               ↓
        nci_signal_approval.py (LLM second opinion)

Rate limits:
  Free tier:  25 req/day  → use --once or --interval 3600 (hourly)
  Premium:    75 req/min  → watch mode with --interval 60 (1 min)

Indicators computed (8 of the EA's 15 voters available in Python):
  1. DMA      — price vs displaced 21 EMA
  2. RSI      — RSI(14) directional bias
  3. RSI Slope — RSI momentum direction
  4. MACD     — MACD signal vs histogram
  5. ADX      — trend strength (>22 = trending)
  6. ATR      — volatility filter
  7. FER      — Fractal Efficiency Ratio (trend quality)
  8. Momentum — close vs N-bar prior close

ABC Stage detection:
  A (consolidation): ADX < 20 AND FER < 0.45
  B (expansion):     ADX >= 22 AND FER >= 0.50
  C (contraction):   ADX falling AND FER < 0.55
"""
from __future__ import annotations

import json
import os
import sys
import time
from dataclasses import dataclass, asdict
from datetime import datetime, timedelta, timezone
from typing import Dict, List, Optional, Tuple
import urllib.request
import urllib.parse

from config import (
    AV_API_KEY,
    AV_BASE_URL,
    AV_CACHE_MINUTES,
    AV_INTERVAL,
    AV_OUTPUTSIZE,
    AV_PAIRS,
    AV_MODE,
    NCI_LIVE_JSON,
    SIGNAL_PROPOSAL_JSON,
    MT4_FILES_DIR,
)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

STAGE_A = 0   # consolidation — block entries
STAGE_B = 1   # expansion     — trade
STAGE_C = 2   # contraction   — trail only

# Confluence thresholds (same as EA defaults)
MIN_CONFLUENCE = 5    # of 8 voters (≈ 67% agreement)
MAX_SPREAD_PIPS = 3   # block entry if spread > this

# Standard SL/TP for signal proposals
DEFAULT_SL_ATR_MULT = 2.0
DEFAULT_TP_RR       = 1.5


# ---------------------------------------------------------------------------
# Candle dataclass
# ---------------------------------------------------------------------------

@dataclass
class Candle:
    timestamp: str
    open:  float
    high:  float
    low:   float
    close: float

    @classmethod
    def from_av_dict(cls, ts: str, d: dict) -> "Candle":
        return cls(
            timestamp=ts,
            open=float(d.get("1. open",  d.get("open",  0))),
            high=float(d.get("2. high",  d.get("high",  0))),
            low=float(d.get("3. low",   d.get("low",   0))),
            close=float(d.get("4. close", d.get("close", 0))),
        )


# ---------------------------------------------------------------------------
# HTTP helpers (no extra dependencies)
# ---------------------------------------------------------------------------

_cache: Dict[str, Tuple[float, dict]] = {}   # url → (fetched_at, data)


def _fetch_json(url: str, cache_sec: int = 300) -> Optional[dict]:
    """Fetch URL with in-memory cache. Returns None on error."""
    now = time.time()
    if url in _cache:
        cached_at, data = _cache[url]
        if now - cached_at < cache_sec:
            return data

    try:
        with urllib.request.urlopen(url, timeout=15) as resp:
            raw = resp.read().decode("utf-8")
        data = json.loads(raw)
        # Alpha Vantage wraps errors in "Note" or "Information" keys
        if "Note" in data or "Information" in data:
            note = data.get("Note") or data.get("Information", "")
            print(f"[AV] API notice: {note[:120]}", file=sys.stderr)
            if "limit" in note.lower() or "premium" in note.lower():
                return None
        _cache[url] = (now, data)
        return data
    except Exception as e:
        print(f"[AV] Fetch error: {e}", file=sys.stderr)
        return None


def _av_url(**params) -> str:
    params["apikey"] = AV_API_KEY
    return AV_BASE_URL + "?" + urllib.parse.urlencode(params)


# ---------------------------------------------------------------------------
# Alpha Vantage data fetchers
# ---------------------------------------------------------------------------

def fetch_spot(from_sym: str, to_sym: str) -> Optional[dict]:
    """Realtime spot rate via CURRENCY_EXCHANGE_RATE (free tier)."""
    url = _av_url(function="CURRENCY_EXCHANGE_RATE",
                  from_currency=from_sym, to_currency=to_sym)
    data = _fetch_json(url, cache_sec=AV_CACHE_MINUTES * 60)
    if not data:
        return None
    return data.get("Realtime Currency Exchange Rate")


def fetch_fx_candles(from_sym: str, to_sym: str, interval: str = AV_INTERVAL,
                     outputsize: str = AV_OUTPUTSIZE) -> Optional[List[Candle]]:
    """Intraday candles via FX_INTRADAY (premium) or daily via FX_DAILY (free)."""
    cache_sec = AV_CACHE_MINUTES * 60

    # Try intraday first (premium endpoint)
    url = _av_url(function="FX_INTRADAY", from_symbol=from_sym,
                  to_symbol=to_sym, interval=interval, outputsize=outputsize)
    data = _fetch_json(url, cache_sec=cache_sec)

    key_intraday = f"Time Series FX ({interval})"
    if data and key_intraday in data:
        series = data[key_intraday]
        candles = [Candle.from_av_dict(ts, v) for ts, v in sorted(series.items(), reverse=True)]
        return candles[:100]

    # Fallback: daily candles (free tier)
    url = _av_url(function="FX_DAILY", from_symbol=from_sym,
                  to_symbol=to_sym, outputsize=outputsize)
    data = _fetch_json(url, cache_sec=3600)  # cache daily data for 1 hour

    if data and "Time Series FX (Daily)" in data:
        series = data["Time Series FX (Daily)"]
        candles = [Candle.from_av_dict(ts, v) for ts, v in sorted(series.items(), reverse=True)]
        return candles[:100]

    return None


# ---------------------------------------------------------------------------
# Indicator engine
# ---------------------------------------------------------------------------

def _ema(values: List[float], period: int) -> List[float]:
    """Exponential Moving Average."""
    if len(values) < period:
        return []
    k = 2.0 / (period + 1)
    result = [sum(values[:period]) / period]
    for v in values[period:]:
        result.append(v * k + result[-1] * (1 - k))
    return result


def calc_atr(candles: List[Candle], period: int = 14) -> float:
    """Average True Range."""
    if len(candles) < period + 1:
        return 0.0
    trs = []
    for i in range(1, len(candles)):
        h, l, pc = candles[i-1].high, candles[i-1].low, candles[i].close
        trs.append(max(h - l, abs(h - pc), abs(l - pc)))
    if len(trs) < period:
        return sum(trs) / len(trs) if trs else 0.0
    # Wilder smoothing
    atr = sum(trs[:period]) / period
    for tr in trs[period:]:
        atr = (atr * (period - 1) + tr) / period
    return atr


def calc_adx(candles: List[Candle], period: int = 14) -> Tuple[float, bool]:
    """Average Directional Index. Returns (adx_value, is_rising)."""
    n = len(candles)
    if n < period * 2 + 1:
        return 0.0, False

    plus_dms, minus_dms, trs = [], [], []
    for i in range(1, n):
        prev, cur = candles[i], candles[i - 1]
        up_move   = prev.high - cur.high
        down_move = cur.low  - prev.low
        plus_dm   = up_move   if up_move > down_move and up_move > 0   else 0.0
        minus_dm  = down_move if down_move > up_move and down_move > 0 else 0.0
        plus_dms.append(plus_dm)
        minus_dms.append(minus_dm)
        trs.append(max(prev.high - prev.low, abs(prev.high - cur.close), abs(prev.low - cur.close)))

    def _wilder(vals: List[float], p: int) -> float:
        if len(vals) < p:
            return sum(vals) / len(vals) if vals else 0.0
        s = sum(vals[:p])
        for v in vals[p:]:
            s = s - s / p + v
        return s

    sm_tr  = _wilder(trs, period)
    sm_pdm = _wilder(plus_dms, period)
    sm_ndm = _wilder(minus_dms, period)

    pdi = 100 * sm_pdm / sm_tr if sm_tr else 0.0
    ndi = 100 * sm_ndm / sm_tr if sm_tr else 0.0
    dx  = 100 * abs(pdi - ndi) / (pdi + ndi) if (pdi + ndi) else 0.0

    # Need enough history for ADX smoothing — simplified one-shot calc
    adx = dx

    # Detect rising: compare last two DX values
    if n >= period * 2 + 2:
        sm_tr2  = _wilder(trs[:-1],     period)
        sm_pdm2 = _wilder(plus_dms[:-1], period)
        sm_ndm2 = _wilder(minus_dms[:-1], period)
        pdi2 = 100 * sm_pdm2 / sm_tr2 if sm_tr2 else 0.0
        ndi2 = 100 * sm_ndm2 / sm_tr2 if sm_tr2 else 0.0
        dx2  = 100 * abs(pdi2 - ndi2) / (pdi2 + ndi2) if (pdi2 + ndi2) else 0.0
        adx_rising = dx > dx2
    else:
        adx_rising = True

    return adx, adx_rising


def calc_fer(candles: List[Candle], period: int = 10) -> float:
    """Fractal Efficiency Ratio — |net move| / sum(bar-to-bar moves)."""
    if len(candles) < period + 1:
        return 0.0
    closes = [c.close for c in candles[:period + 1]]
    net_move = abs(closes[0] - closes[-1])
    path = sum(abs(closes[i] - closes[i + 1]) for i in range(period))
    return net_move / path if path > 0 else 0.0


def calc_rsi(candles: List[Candle], period: int = 14) -> Tuple[float, float]:
    """RSI. Returns (rsi_value, rsi_slope: last_rsi - prev_rsi)."""
    closes = [c.close for c in candles]
    if len(closes) < period + 2:
        return 50.0, 0.0

    gains, losses = [], []
    for i in range(1, len(closes)):
        d = closes[i - 1] - closes[i]  # newest first, so positive = up
        gains.append(max(d, 0))
        losses.append(max(-d, 0))

    ag = sum(gains[:period]) / period
    al = sum(losses[:period]) / period
    for g, l in zip(gains[period:], losses[period:]):
        ag = (ag * (period - 1) + g) / period
        al = (al * (period - 1) + l) / period

    rsi = 100 - 100 / (1 + ag / al) if al > 0 else 100.0

    # Previous RSI (exclude last candle)
    gains2, losses2 = gains[1:], losses[1:]
    if len(gains2) >= period:
        ag2 = sum(gains2[:period]) / period
        al2 = sum(losses2[:period]) / period
        for g, l in zip(gains2[period:], losses2[period:]):
            ag2 = (ag2 * (period - 1) + g) / period
            al2 = (al2 * (period - 1) + l) / period
        prev_rsi = 100 - 100 / (1 + ag2 / al2) if al2 > 0 else 100.0
    else:
        prev_rsi = rsi

    return rsi, rsi - prev_rsi


def calc_macd(candles: List[Candle], fast: int = 12, slow: int = 26,
              signal: int = 9) -> Tuple[float, float, float]:
    """MACD. Returns (macd_line, signal_line, histogram)."""
    closes = [c.close for c in reversed(candles)]  # oldest first for EMA
    if len(closes) < slow + signal:
        return 0.0, 0.0, 0.0
    fast_ema  = _ema(closes, fast)
    slow_ema  = _ema(closes, slow)
    # Align by trimming fast_ema to match slow_ema length
    offset = len(fast_ema) - len(slow_ema)
    macd_line = [f - s for f, s in zip(fast_ema[offset:], slow_ema)]
    if len(macd_line) < signal:
        return 0.0, 0.0, 0.0
    signal_ema = _ema(macd_line, signal)
    if not signal_ema:
        return 0.0, 0.0, 0.0
    m = macd_line[-1]
    s = signal_ema[-1]
    return m, s, m - s


def calc_dma(candles: List[Candle], period: int = 21, displacement: int = 5) -> Tuple[float, bool]:
    """Displaced Moving Average. Returns (dma_value, price_above_dma)."""
    closes = [c.close for c in reversed(candles)]  # oldest first
    if len(closes) < period + displacement:
        return 0.0, False
    ema_vals = _ema(closes, period)
    if len(ema_vals) <= displacement:
        return 0.0, False
    dma_val = ema_vals[-(displacement + 1)]  # displaced back N bars
    current_price = closes[-1]
    return dma_val, current_price > dma_val


# ---------------------------------------------------------------------------
# ABC Stage + Confluence Score
# ---------------------------------------------------------------------------

def determine_abc_stage(adx: float, adx_rising: bool, fer: float) -> int:
    """Determine ABC market stage from ADX + FER (mirrors MT4 EA logic)."""
    if adx >= 22 and fer >= 0.50:
        return STAGE_B
    elif adx < 20 and fer < 0.45:
        return STAGE_A
    else:
        return STAGE_C


def compute_confluence(
    candles: List[Candle],
    adx: float,
    adx_rising: bool,
    fer: float,
    atr: float,
    direction: str,  # "BUY" or "SELL"
) -> Tuple[int, List[str]]:
    """
    Compute buy or sell confluence score from available Python indicators.
    Returns (score, voter_names).
    Max score = 8 (vs 15 in MT4 EA — MT4-only voters not available here).
    """
    score = 0
    voters = []
    closes = [c.close for c in candles]
    current = closes[0]

    rsi, rsi_slope = calc_rsi(candles)
    macd_line, macd_sig, macd_hist = calc_macd(candles)
    dma_val, price_above_dma = calc_dma(candles)

    is_buy = direction == "BUY"

    # 1. DMA — price above/below displaced MA
    if (is_buy and price_above_dma) or (not is_buy and not price_above_dma):
        score += 1
        voters.append("DMA")

    # 2. RSI — bias
    if is_buy and 40 < rsi < 70:
        score += 1
        voters.append("RSI")
    elif not is_buy and 30 < rsi < 60:
        score += 1
        voters.append("RSI")

    # 3. RSI Slope — momentum direction
    if (is_buy and rsi_slope > 0.5) or (not is_buy and rsi_slope < -0.5):
        score += 1
        voters.append("RSI+")

    # 4. MACD — signal crossover
    if (is_buy and macd_line > macd_sig and macd_hist > 0):
        score += 1
        voters.append("MACD")
    elif (not is_buy and macd_line < macd_sig and macd_hist < 0):
        score += 1
        voters.append("MACD")

    # 5. ADX — trend is strong
    if adx >= 22:
        score += 1
        voters.append("ADX")

    # 6. ATR — volatility not too low (avoids flat choppy entries)
    if atr > 0:
        avg_atr = sum(abs(candles[i].high - candles[i].low) for i in range(min(14, len(candles)))) / 14
        if atr > avg_atr * 0.7:
            score += 1
            voters.append("ATR")

    # 7. FER — efficient trend movement
    if fer >= 0.45:
        score += 1
        voters.append("FER")

    # 8. Momentum — price moved in direction over last 5 bars
    if len(closes) >= 6:
        momentum = closes[0] - closes[5]
        if (is_buy and momentum > 0) or (not is_buy and momentum < 0):
            score += 1
            voters.append("MOM5")

    return score, voters


# ---------------------------------------------------------------------------
# Main analysis engine
# ---------------------------------------------------------------------------

@dataclass
class AVAnalysis:
    """Full NCI-compatible analysis for one FX pair."""
    symbol: str          # e.g. "EURUSD"
    spot_price: float
    spread_estimate: float
    bid: float
    ask: float
    candle_interval: str

    # Indicators
    adx: float
    adx_rising: bool
    fer: float
    atr: float
    rsi: float
    rsi_slope: float
    macd_line: float
    macd_hist: float
    dma: float
    price_above_dma: bool
    abc_stage: int

    # Confluence
    buy_score: int
    buy_voters: List[str]
    sell_score: int
    sell_voters: List[str]

    # Proposal
    proposed_direction: str   # "BUY" | "SELL" | "NONE"
    proposed_sl_pips: float
    proposed_tp_pips: float
    proposed_rr: float
    qualifies: bool

    timestamp: str
    candle_count: int
    source: str = "alphavantage"


def analyse_pair(from_sym: str, to_sym: str) -> Optional[AVAnalysis]:
    """Fetch data and compute full NCI analysis for one FX pair."""
    if not AV_API_KEY:
        print("[AV] ERROR: AV_API_KEY not set. "
              "Run: export AV_API_KEY=YOUR_KEY (see .env.example)", file=sys.stderr)
        return None

    symbol = from_sym + to_sym  # e.g. "EURUSD"

    # 1. Realtime spot (free tier)
    spot_data = fetch_spot(from_sym, to_sym)
    if spot_data:
        bid = float(spot_data.get("8. Bid Price", 0) or spot_data.get("5. Exchange Rate", 0))
        ask = float(spot_data.get("9. Ask Price", 0) or spot_data.get("5. Exchange Rate", 0))
        spot = (bid + ask) / 2 if bid and ask else float(spot_data.get("5. Exchange Rate", 0))
    else:
        bid = ask = spot = 0.0

    # 2. OHLCV candles for indicators
    candles = fetch_fx_candles(from_sym, to_sym)
    if not candles or len(candles) < 30:
        print(f"[AV] Not enough candles for {symbol} ({len(candles) if candles else 0} bars)", file=sys.stderr)
        return None

    # Use spot price as latest close if spot is fresher
    if spot and abs(spot - candles[0].close) / candles[0].close < 0.002:
        candles[0] = Candle(
            timestamp=datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S"),
            open=candles[0].open, high=max(candles[0].high, spot),
            low=min(candles[0].low, spot), close=spot,
        )

    # 3. Compute indicators
    atr         = calc_atr(candles)
    adx, adx_r  = calc_adx(candles)
    fer         = calc_fer(candles)
    rsi, rsi_sl = calc_rsi(candles)
    ml, ms, mh  = calc_macd(candles)
    dma_val, p_above_dma = calc_dma(candles)
    abc_stage   = determine_abc_stage(adx, adx_r, fer)

    # 4. Confluence scores
    buy_score,  buy_voters  = compute_confluence(candles, adx, adx_r, fer, atr, "BUY")
    sell_score, sell_voters = compute_confluence(candles, adx, adx_r, fer, atr, "SELL")

    # 5. Signal proposal — favour the higher-scoring direction
    if buy_score > sell_score and buy_score >= MIN_CONFLUENCE:
        direction = "BUY"
        score     = buy_score
        voters    = buy_voters
    elif sell_score > buy_score and sell_score >= MIN_CONFLUENCE:
        direction = "SELL"
        score     = sell_score
        voters    = sell_voters
    else:
        direction = "NONE"
        score     = max(buy_score, sell_score)
        voters    = []

    # Pip value: 4-digit pairs = 0.0001 pip, JPY pairs = 0.01 pip
    pip = 0.01 if "JPY" in to_sym else 0.0001
    sl_pips = (atr * DEFAULT_SL_ATR_MULT) / pip if atr else 20
    tp_pips = sl_pips * DEFAULT_TP_RR

    spread_pips = (ask - bid) / pip if ask > bid else 1.5
    qualifies = (
        abc_stage == STAGE_B
        and direction != "NONE"
        and score >= MIN_CONFLUENCE
        and spread_pips <= MAX_SPREAD_PIPS
    )

    return AVAnalysis(
        symbol=symbol,
        spot_price=spot or candles[0].close,
        spread_estimate=spread_pips,
        bid=bid,
        ask=ask,
        candle_interval=AV_INTERVAL,
        adx=round(adx, 2),
        adx_rising=adx_r,
        fer=round(fer, 4),
        atr=round(atr, 6),
        rsi=round(rsi, 2),
        rsi_slope=round(rsi_sl, 3),
        macd_line=round(ml, 6),
        macd_hist=round(mh, 6),
        dma=round(dma_val, 6),
        price_above_dma=p_above_dma,
        abc_stage=abc_stage,
        buy_score=buy_score,
        buy_voters=buy_voters,
        sell_score=sell_score,
        sell_voters=sell_voters,
        proposed_direction=direction,
        proposed_sl_pips=round(sl_pips, 1),
        proposed_tp_pips=round(tp_pips, 1),
        proposed_rr=DEFAULT_TP_RR,
        qualifies=qualifies,
        timestamp=datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        candle_count=len(candles),
        source="alphavantage",
    )


# ---------------------------------------------------------------------------
# JSON writers — same format as MT4 EA outputs
# ---------------------------------------------------------------------------

def write_live_json(analysis: AVAnalysis, path: str = NCI_LIVE_JSON) -> None:
    """Write NCI_LiveData.json in same format as MT4 EA v3.2 Fusion."""
    stage_labels = {STAGE_A: "A_CONSOLIDATION", STAGE_B: "B_EXPANSION", STAGE_C: "C_CONTRACTION"}
    data = {
        "balance":       0.0,         # not available from AV
        "equity":        0.0,
        "margin":        0.0,
        "drawdown":      0.0,
        "trades_daily":  0,
        "consec_losses": 0,
        "phase":         stage_labels.get(analysis.abc_stage, "?"),
        "abc_stage":     analysis.abc_stage,
        "abc_stage_h4":  analysis.abc_stage,  # same timeframe without H4 data
        "adx":           analysis.adx,
        "fer":           analysis.fer,
        "buy_score":     analysis.buy_score,
        "sell_score":    analysis.sell_score,
        "atr":           analysis.atr,
        "timestamp":     analysis.timestamp,

        # Extended fields (not in v3.2 but included for v4.0 / bridge)
        "source":        "alphavantage",
        "symbol":        analysis.symbol,
        "spot":          analysis.spot_price,
        "spread_pips":   round(analysis.spread_estimate, 1),
        "rsi":           analysis.rsi,
        "macd_hist":     analysis.macd_hist,
        "price_above_dma": analysis.price_above_dma,
        "buy_voters":    analysis.buy_voters,
        "sell_voters":   analysis.sell_voters,
        "candle_interval": analysis.candle_interval,
        "candle_count":  analysis.candle_count,
    }
    os.makedirs(os.path.dirname(path) if os.path.dirname(path) else ".", exist_ok=True)
    with open(path, "w") as f:
        json.dump(data, f, indent=2)


def write_signal_json(analysis: AVAnalysis, path: str = SIGNAL_PROPOSAL_JSON) -> None:
    """Write signal_proposal.json in same format as MT4 EA v3.2 Fusion."""
    stage_labels = {STAGE_A: "A_CONSOLIDATION", STAGE_B: "B_EXPANSION", STAGE_C: "C_CONTRACTION"}
    score    = analysis.buy_score if analysis.proposed_direction == "BUY" else analysis.sell_score
    voters   = analysis.buy_voters if analysis.proposed_direction == "BUY" else analysis.sell_voters
    data = {
        "symbol":          analysis.symbol,
        "action":          analysis.proposed_direction,
        "mode":            stage_labels.get(analysis.abc_stage, "?"),
        "godmode_score":   round(score / 8 * 10, 1),  # normalise to /10
        "confluence":      score,
        "confluence_max":  8,        # 8 Python voters (15 in full MT4 EA)
        "abc_stage":       stage_labels.get(analysis.abc_stage, "?"),
        "sl_pips":         analysis.proposed_sl_pips,
        "tp_pips":         analysis.proposed_tp_pips,
        "risk_reward":     analysis.proposed_rr,
        "qualifies":       analysis.qualifies,
        "timestamp":       analysis.timestamp,
        "approved":        False,
        "voters":          voters,
        "source":          "alphavantage",
        "spot":            analysis.spot_price,
        "spread_pips":     round(analysis.spread_estimate, 1),
    }
    os.makedirs(os.path.dirname(path) if os.path.dirname(path) else ".", exist_ok=True)
    with open(path, "w") as f:
        json.dump(data, f, indent=2)


# ---------------------------------------------------------------------------
# Display + watch
# ---------------------------------------------------------------------------

STAGE_LABEL = {STAGE_A: "A_CONSOL", STAGE_B: "B_EXPAND", STAGE_C: "C_CONTRL"}


def format_analysis(a: AVAnalysis) -> str:
    bar = lambda s, mx: ("█" * s) + ("░" * (mx - s))
    q = "✅ QUALIFIES" if a.qualifies else "❌ BLOCKED"
    stage = STAGE_LABEL.get(a.abc_stage, "?")
    voters = ", ".join(a.buy_voters if a.proposed_direction == "BUY" else a.sell_voters)
    return "\n".join([
        f"╔══ AV LIVE  {a.symbol}  {a.timestamp} ══╗",
        f"  Spot: {a.spot_price:.5f}   Spread: {a.spread_estimate:.1f}p",
        f"  Stage: {stage}   ADX {a.adx:.1f}  FER {a.fer:.3f}  ATR {a.atr:.5f}",
        f"  RSI {a.rsi:.1f} ({a.rsi_slope:+.2f})   MACD hist {a.macd_hist:.6f}",
        f"",
        f"  BUY  [{bar(a.buy_score, 8)}] {a.buy_score}/8  voters: {', '.join(a.buy_voters) or '--'}",
        f"  SELL [{bar(a.sell_score, 8)}] {a.sell_score}/8  voters: {', '.join(a.sell_voters) or '--'}",
        f"",
        f"  Proposal: {a.proposed_direction or 'NONE':5}  SL={a.proposed_sl_pips:.0f}p  TP={a.proposed_tp_pips:.0f}p  RR {a.proposed_rr:.1f}",
        f"  Gate: {q}",
        f"  ({a.candle_count} bars @ {a.candle_interval})",
        f"╚{'═' * 52}╝",
    ])


def run_once(pairs: Optional[List[str]] = None) -> None:
    """Fetch, compute, display and write JSON for each pair."""
    if not AV_API_KEY:
        print("ERROR: Set AV_API_KEY environment variable first.")
        print("  Windows: set AV_API_KEY=MUY2H3V41ZYL9X2E")
        print("  Linux:   export AV_API_KEY=MUY2H3V41ZYL9X2E")
        return

    pairs = pairs or AV_PAIRS
    best: Optional[AVAnalysis] = None

    for pair_str in pairs:
        parts = pair_str.replace("-", "/").split("/")
        if len(parts) != 2:
            continue
        from_sym, to_sym = parts[0].strip().upper(), parts[1].strip().upper()
        print(f"[AV] Fetching {from_sym}/{to_sym}...")
        analysis = analyse_pair(from_sym, to_sym)
        if not analysis:
            continue

        print(format_analysis(analysis))
        print()

        # Track best qualifying signal
        score = analysis.buy_score if analysis.proposed_direction == "BUY" else analysis.sell_score
        best_score = (best.buy_score if best and best.proposed_direction == "BUY"
                      else best.sell_score if best else 0)
        if best is None or (analysis.qualifies and score > best_score):
            best = analysis

    # Write best signal to MT4 files dir for bridge consumption
    if best:
        write_live_json(best)
        write_signal_json(best)
        print(f"[AV] Wrote NCI_LiveData.json + signal_proposal.json for {best.symbol}")
    else:
        print("[AV] No qualifying signals this scan.")


def watch_mode(interval_sec: int = 300, pairs: Optional[List[str]] = None) -> None:
    """Continuous watch — re-scan every interval_sec seconds."""
    print(f"🔴 AV Live Feed — WATCH MODE  (interval={interval_sec}s, pairs={pairs or AV_PAIRS})")
    print("   Press Ctrl+C to stop.\n")
    try:
        while True:
            print(f"\n{'─' * 60}")
            print(f"  Scan @ {datetime.now(timezone.utc).strftime('%H:%M:%S UTC')}")
            print(f"{'─' * 60}")
            run_once(pairs)
            time.sleep(interval_sec)
    except KeyboardInterrupt:
        print("\n✋ Stopped.")


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(
        description="Alpha Vantage FX live feed for NCI Bridge"
    )
    parser.add_argument(
        "--pairs",
        help="Comma-separated pairs, e.g. EUR/USD,GBP/USD (default: from config)",
    )
    parser.add_argument(
        "--watch", action="store_true",
        help="Watch mode — re-scan continuously"
    )
    parser.add_argument(
        "--interval", type=int, default=AV_CACHE_MINUTES * 60,
        help=f"Watch interval in seconds (default: {AV_CACHE_MINUTES * 60})"
    )
    parser.add_argument(
        "--pair",
        help="Single pair override, e.g. EUR/USD"
    )
    args = parser.parse_args()

    pairs = None
    if args.pair:
        pairs = [args.pair]
    elif args.pairs:
        pairs = [p.strip() for p in args.pairs.split(",")]

    if args.watch:
        watch_mode(interval_sec=args.interval, pairs=pairs)
    else:
        run_once(pairs)
