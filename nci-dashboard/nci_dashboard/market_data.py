"""
Live market-data provider layer for the Options Assistant.

Pre-fills the MarketContext form from a real feed instead of manual entry.
Follows the same zero-dependency, never-raises, degrade-gracefully shape as
``nci_strategy_selector.claude_client``:

  * stdlib ``urllib`` only — no pip runtime dependency;
  * reads credentials from the environment;
  * a network/parse failure returns ``None`` (never raises) so the product
    keeps working — the caller falls back to manual entry or the DemoProvider;
  * retries on 429 / 5xx with exponential backoff.

Two providers ship:

  * :class:`AlpacaProvider` — real quotes from the Alpaca Market Data API,
    active when ``APCA_API_KEY_ID`` / ``APCA_API_SECRET_KEY`` are set.
  * :class:`DemoProvider` — deterministic, realistic values per symbol so the
    feature is demo-able with no keys. Clearly labelled ``source: "demo"``.

Several MarketContext fields are not directly reported by any snapshot API and
must be *estimated*. Every estimate records how it was derived in ``notes`` and
labels itself ``estimated`` — we never fabricate precision.

Derivation summary (see the functions for the exact math):

  * ``spot_trend``   — last close vs 20-day SMA, where a +5% premium to the SMA
                       maps to +1 and −5% to −1 (clamped).
  * ``expected_move``— ATM straddle mid (call mid + put mid) for the nearest
                       standard-monthly expiry.
  * ``iv_rank``      — 52-week IV history is NOT in the snapshot API, so this is
                       ESTIMATED by mapping current ATM IV onto a 10%–50% band
                       (10% IV → rank 0, 50% IV → rank 100). Labelled estimated.
  * ``iv_trend``     — not derivable from a single snapshot; returned as 0 with
                       an "unknown" note.
  * ``liquidity_score`` — 1 − (avg ATM bid/ask relative spread ÷ 25%), clamped
                       to 0–1. A 0%-wide market → 1.0, a ≥25%-wide market → 0.
"""

from __future__ import annotations

import json
import math
import os
import time
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass, field
from datetime import datetime, timezone, date

# ── Alpaca endpoints ──────────────────────────────────────────────────
ALPACA_DATA_BASE = "https://data.alpaca.markets"
SNAPSHOT_URL = ALPACA_DATA_BASE + "/v2/stocks/{symbol}/snapshot"
BARS_URL = ALPACA_DATA_BASE + "/v2/stocks/{symbol}/bars"
OPTION_SNAPSHOTS_URL = ALPACA_DATA_BASE + "/v1beta1/options/snapshots/{symbol}"

MAX_RETRIES = 3
RETRY_BACKOFF_S = 1.5

# ── estimation bands (documented, tunable) ────────────────────────────
# spot_trend: fractional premium/discount to the SMA that saturates to ±1.
SPOT_TREND_FULL_SCALE = 0.05          # ±5% vs SMA → ±1.0
SMA_WINDOW = 20                       # trailing sessions for the SMA
# iv_rank estimate band (annualised ATM IV → 0–100 rank).
IV_RANK_FLOOR = 0.10                  # 10% IV → rank 0
IV_RANK_CEIL = 0.50                   # 50% IV → rank 100
# liquidity: relative bid/ask spread that saturates to 0 liquidity.
LIQ_MAX_REL_SPREAD = 0.25             # ≥25%-wide market → score 0.0


def _clamp(x: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, x))


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


# ── result type ───────────────────────────────────────────────────────
@dataclass
class MarketPrefill:
    """
    Values to pre-fill the MarketContext form, plus provenance.

    ``notes`` explains how each estimated field was derived and flags the
    estimates as such. ``source`` is the provider name ("alpaca"/"demo").
    """

    price: float
    iv_rank: float               # 0–100 (may be estimated)
    iv_trend: float              # −1..+1 (0 when unknown)
    spot_trend: float            # −1..+1
    expected_move: float         # dollars
    liquidity_score: float       # 0–1
    source: str
    as_of: str                   # ISO-8601 UTC timestamp
    notes: list[str] = field(default_factory=list)

    def prefill_fields(self) -> dict:
        """Just the numeric form values (rounded for display)."""
        return {
            "price": round(self.price, 2),
            "iv_rank": round(self.iv_rank, 1),
            "iv_trend": round(self.iv_trend, 2),
            "spot_trend": round(self.spot_trend, 2),
            "expected_move": round(self.expected_move, 2),
            "liquidity_score": round(self.liquidity_score, 3),
        }

    def to_response(self) -> dict:
        """The ``/api/market/{symbol}`` response body."""
        return {
            "prefill": self.prefill_fields(),
            "source": self.source,
            "as_of": self.as_of,
            "notes": list(self.notes),
        }


# ── provider interface ────────────────────────────────────────────────
class MarketDataProvider:
    """Transport-agnostic interface: ``fetch(symbol) -> MarketPrefill | None``."""

    name = "base"

    def fetch(self, symbol: str) -> MarketPrefill | None:  # pragma: no cover
        raise NotImplementedError


# ── OCC option-symbol helpers (module-level for testability) ──────────
def parse_occ_symbol(occ: str) -> dict | None:
    """
    Parse an OCC option symbol like ``AAPL240119C00190000`` →
    ``{"underlying": "AAPL", "expiry": date(2024,1,19), "right": "C",
       "strike": 190.0}``. Returns None if it does not parse.

    Parsed from the right so variable-length underlyings are handled: the last
    8 chars are the strike (×1000), preceded by the C/P right, preceded by a
    6-digit YYMMDD expiry, and whatever remains is the underlying.
    """
    if not occ or len(occ) < 16:
        return None
    try:
        strike = int(occ[-8:]) / 1000.0
        right = occ[-9].upper()
        if right not in ("C", "P"):
            return None
        yymmdd = occ[-15:-9]
        expiry = datetime.strptime(yymmdd, "%y%m%d").date()
        underlying = occ[:-15]
        if not underlying:
            return None
        return {"underlying": underlying, "expiry": expiry,
                "right": right, "strike": strike}
    except (ValueError, IndexError):
        return None


def _is_third_friday(d: date) -> bool:
    return d.weekday() == 4 and 15 <= d.day <= 21


def choose_expiry(expiries: list[date], today: date | None = None) -> date | None:
    """
    Pick the nearest *standard monthly* (3rd-Friday) expiry on/after today.
    Falls back to the nearest expiry on/after today, then to the latest
    available. Returns None for an empty list.
    """
    if not expiries:
        return None
    today = today or datetime.now(timezone.utc).date()
    future = sorted(e for e in expiries if e >= today)
    monthlies = [e for e in future if _is_third_friday(e)]
    if monthlies:
        return monthlies[0]
    if future:
        return future[0]
    return max(expiries)


def _mid(bid: float | None, ask: float | None, last: float | None) -> float | None:
    """Mid of a two-sided quote; falls back to the last trade price."""
    if bid is not None and ask is not None and bid > 0 and ask > 0:
        return (bid + ask) / 2.0
    return last if (last and last > 0) else None


# ── derivations (module-level, pure, unit-testable) ───────────────────
def derive_spot_trend(closes: list[float]) -> tuple[float, str]:
    """
    Normalised last-vs-SMA trend in [-1, +1] plus a provenance note.

    ``(last_close − SMA) / SMA`` is the fractional premium to the moving
    average; dividing by SPOT_TREND_FULL_SCALE maps ±5% to ±1, then clamp.
    """
    closes = [c for c in closes if c and c > 0]
    if len(closes) < 2:
        return 0.0, "spot_trend: insufficient bar history — defaulted to 0 (estimated)"
    window = closes[-SMA_WINDOW:]
    sma = sum(window) / len(window)
    if sma <= 0:
        return 0.0, "spot_trend: non-positive SMA — defaulted to 0 (estimated)"
    premium = (closes[-1] - sma) / sma
    trend = _clamp(premium / SPOT_TREND_FULL_SCALE, -1.0, 1.0)
    note = (
        f"spot_trend: last close {closes[-1]:.2f} vs {len(window)}-day SMA "
        f"{sma:.2f} ({premium * 100:+.1f}%) → {trend:+.2f} "
        f"(±{SPOT_TREND_FULL_SCALE * 100:.0f}% saturates)"
    )
    return trend, note


def derive_iv_rank(atm_iv: float) -> tuple[float, str]:
    """
    ESTIMATE iv_rank (0–100) from current ATM IV mapped onto a fixed band.

    52-week IV history is not exposed by the snapshot API, so this is a coarse
    proxy — labelled estimated so the UI never presents it as a true rank.
    """
    span = IV_RANK_CEIL - IV_RANK_FLOOR
    rank = _clamp((atm_iv - IV_RANK_FLOOR) / span * 100.0, 0.0, 100.0)
    note = (
        f"iv_rank: ESTIMATED — no 52-week IV history in the API; mapped ATM IV "
        f"{atm_iv * 100:.1f}% onto a {IV_RANK_FLOOR * 100:.0f}–"
        f"{IV_RANK_CEIL * 100:.0f}% band → rank {rank:.0f}"
    )
    return rank, note


def derive_liquidity(rel_spreads: list[float]) -> tuple[float, str]:
    """
    liquidity_score (0–1) from average ATM bid/ask relative spread.

    ``1 − avg_rel_spread / LIQ_MAX_REL_SPREAD``, clamped. A perfectly tight
    market scores 1.0; a market ≥25% wide scores 0.0.
    """
    spreads = [s for s in rel_spreads if s is not None and s >= 0]
    if not spreads:
        return 0.7, "liquidity_score: no ATM quotes — defaulted to 0.70 (estimated)"
    avg = sum(spreads) / len(spreads)
    score = _clamp(1.0 - avg / LIQ_MAX_REL_SPREAD, 0.0, 1.0)
    note = (
        f"liquidity_score: avg ATM bid/ask spread {avg * 100:.1f}% of mid "
        f"across {len(spreads)} contract(s) → {score:.2f}"
    )
    return score, note


# ── Alpaca provider ───────────────────────────────────────────────────
class AlpacaProvider(MarketDataProvider):
    """
    Live provider over the Alpaca Market Data API (stdlib urllib).

    Never raises: any HTTP/parse failure returns ``None`` with the reason kept
    in :attr:`last_error`. Retries 429/5xx with exponential backoff.
    """

    name = "alpaca"

    def __init__(
        self,
        key_id: str | None = None,
        secret_key: str | None = None,
        timeout_s: float = 8.0,
        retry_backoff_s: float = RETRY_BACKOFF_S,
        options_feed: str = "indicative",
    ):
        self.key_id = key_id or os.environ.get("APCA_API_KEY_ID") \
            or os.environ.get("ALPACA_API_KEY_ID", "")
        self.secret_key = secret_key or os.environ.get("APCA_API_SECRET_KEY") \
            or os.environ.get("ALPACA_API_SECRET_KEY", "")
        self.timeout_s = timeout_s
        self.retry_backoff_s = retry_backoff_s
        self.options_feed = options_feed
        self.last_error: str | None = None

    @property
    def available(self) -> bool:
        return bool(self.key_id and self.secret_key)

    # ── HTTP ──────────────────────────────────────────────────────────
    def _get_json(self, url: str) -> dict | None:
        """GET → parsed JSON dict, or None (never raises). Retries 429/5xx."""
        last_error = "unknown error"
        for attempt in range(MAX_RETRIES):
            try:
                req = urllib.request.Request(
                    url,
                    headers={
                        "APCA-API-KEY-ID": self.key_id,
                        "APCA-API-SECRET-KEY": self.secret_key,
                        "accept": "application/json",
                    },
                    method="GET",
                )
                with urllib.request.urlopen(req, timeout=self.timeout_s) as resp:
                    return json.loads(resp.read().decode("utf-8"))
            except urllib.error.HTTPError as e:
                last_error = f"HTTP {e.code}: {e.reason}"
                if e.code not in (429, 500, 502, 503, 504):
                    break
            except (urllib.error.URLError, TimeoutError, OSError) as e:
                last_error = f"network error: {e}"
            except (json.JSONDecodeError, ValueError) as e:
                last_error = f"malformed response: {e}"
                break
            if attempt < MAX_RETRIES - 1 and self.retry_backoff_s > 0:
                time.sleep(self.retry_backoff_s * (2 ** attempt))
        self.last_error = last_error
        return None

    # ── fetch ─────────────────────────────────────────────────────────
    def fetch(self, symbol: str) -> MarketPrefill | None:
        symbol = (symbol or "").strip().upper()
        if not symbol:
            self.last_error = "empty symbol"
            return None
        self.last_error = None
        enc = urllib.parse.quote(symbol, safe="")

        snapshot = self._get_json(SNAPSHOT_URL.format(symbol=enc))
        if snapshot is None:
            return None  # last_error already set

        price = self._extract_price(snapshot)
        if price is None:
            self.last_error = f"no last price for {symbol}"
            return None

        notes: list[str] = []

        # spot_trend from daily bars
        bars = self._get_json(
            BARS_URL.format(symbol=enc) + "?timeframe=1Day&limit=30"
        )
        closes = [b.get("c") for b in (bars or {}).get("bars", []) if isinstance(b, dict)]
        spot_trend, st_note = derive_spot_trend([c for c in closes if c is not None])
        notes.append(st_note)

        # options-derived: ATM IV → iv_rank, straddle → expected_move, spreads → liquidity
        iv_rank = 50.0
        expected_move = round(price * 0.04, 2)  # coarse fallback: ~4% of spot
        liquidity_score = 0.7
        opt = self._get_json(
            OPTION_SNAPSHOTS_URL.format(symbol=enc)
            + f"?feed={urllib.parse.quote(self.options_feed)}&limit=1000"
        )
        derived = self._derive_from_options(opt, price) if opt else None
        if derived is not None:
            iv_rank, expected_move, liquidity_score, opt_notes = derived
            notes.extend(opt_notes)
        else:
            notes.append(
                "options chain unavailable — iv_rank defaulted to 50 (estimated), "
                f"expected_move estimated as 4% of spot ({expected_move:.2f})"
            )

        notes.append("iv_trend: not derivable from a single snapshot → 0 (unknown)")

        return MarketPrefill(
            price=price,
            iv_rank=iv_rank,
            iv_trend=0.0,
            spot_trend=spot_trend,
            expected_move=expected_move,
            liquidity_score=liquidity_score,
            source=self.name,
            as_of=self._extract_as_of(snapshot),
            notes=notes,
        )

    # ── snapshot parsing ──────────────────────────────────────────────
    @staticmethod
    def _unwrap_snapshot(snapshot: dict) -> dict:
        """Accept both the bare snapshot and a ``{SYMBOL: {...}}`` wrapper."""
        if "latestTrade" in snapshot or "dailyBar" in snapshot:
            return snapshot
        # single-symbol wrapper
        for v in snapshot.values():
            if isinstance(v, dict) and ("latestTrade" in v or "dailyBar" in v):
                return v
        return snapshot

    def _extract_price(self, snapshot: dict) -> float | None:
        s = self._unwrap_snapshot(snapshot)
        trade = s.get("latestTrade") or {}
        p = trade.get("p")
        if p and p > 0:
            return float(p)
        daily = s.get("dailyBar") or s.get("minuteBar") or {}
        c = daily.get("c")
        return float(c) if c and c > 0 else None

    def _extract_as_of(self, snapshot: dict) -> str:
        s = self._unwrap_snapshot(snapshot)
        trade = s.get("latestTrade") or {}
        t = trade.get("t")
        if isinstance(t, str) and t:
            # Normalise Alpaca RFC-3339 (…Z or nanoseconds) to seconds UTC.
            try:
                iso = t.replace("Z", "+00:00")
                # trim sub-second precision beyond microseconds
                if "." in iso:
                    head, tail = iso.split(".", 1)
                    frac = "".join(ch for ch in tail if ch.isdigit())[:6]
                    tz = tail[len(frac):] if len(tail) > len(frac) else ""
                    # recover tz suffix if present
                    for suf in ("+00:00", "-00:00"):
                        if tail.endswith(suf):
                            tz = suf
                            break
                    iso = f"{head}.{frac}{tz}" if tz else f"{head}.{frac}+00:00"
                dt = datetime.fromisoformat(iso).astimezone(timezone.utc)
                return dt.strftime("%Y-%m-%dT%H:%M:%SZ")
            except ValueError:
                pass
        return _utc_now_iso()

    # ── options parsing ───────────────────────────────────────────────
    def _derive_from_options(
        self, opt: dict, price: float
    ) -> tuple[float, float, float, list[str]] | None:
        """
        From an options-snapshots payload compute
        ``(iv_rank, expected_move, liquidity_score, notes)`` or None.
        """
        snapshots = opt.get("snapshots") or {}
        if not isinstance(snapshots, dict) or not snapshots:
            return None

        parsed = []
        for occ, snap in snapshots.items():
            info = parse_occ_symbol(occ)
            if info and isinstance(snap, dict):
                info["snap"] = snap
                parsed.append(info)
        if not parsed:
            return None

        expiry = choose_expiry([p["expiry"] for p in parsed])
        if expiry is None:
            return None
        leg = [p for p in parsed if p["expiry"] == expiry]

        # nearest strike to spot with a call and a put available
        strikes = sorted({p["strike"] for p in leg})
        atm_strike = min(strikes, key=lambda k: abs(k - price))

        def _pick(right: str):
            cands = [p for p in leg if p["right"] == right
                     and abs(p["strike"] - atm_strike) < 1e-6]
            return cands[0] if cands else None

        call, put = _pick("C"), _pick("P")

        # ATM IV: mean of available call/put implied vols
        ivs = []
        for p in (call, put):
            if p:
                iv = p["snap"].get("impliedVolatility")
                if isinstance(iv, (int, float)) and iv > 0:
                    ivs.append(float(iv))
        notes: list[str] = []
        if ivs:
            atm_iv = sum(ivs) / len(ivs)
            iv_rank, iv_note = derive_iv_rank(atm_iv)
            notes.append(iv_note)
        else:
            iv_rank, atm_iv = 50.0, None
            notes.append("iv_rank: no ATM implied vol in chain → defaulted to 50 (estimated)")

        # expected_move ≈ ATM straddle mid (nearest monthly)
        def _quote_mid(p):
            if not p:
                return None
            q = p["snap"].get("latestQuote") or {}
            t = p["snap"].get("latestTrade") or {}
            return _mid(q.get("bp"), q.get("ap"), t.get("p"))

        call_mid, put_mid = _quote_mid(call), _quote_mid(put)
        if call_mid is not None and put_mid is not None:
            expected_move = call_mid + put_mid
            notes.append(
                f"expected_move: ATM straddle @ {expiry.isoformat()} "
                f"(strike {atm_strike:g}) = call {call_mid:.2f} + put {put_mid:.2f} "
                f"= {expected_move:.2f}"
            )
        else:
            expected_move = round(price * 0.04, 2)
            notes.append(
                f"expected_move: no ATM straddle quote → estimated 4% of spot "
                f"({expected_move:.2f})"
            )

        # liquidity from ATM bid/ask relative spreads
        rel_spreads = []
        for p in (call, put):
            if not p:
                continue
            q = p["snap"].get("latestQuote") or {}
            bid, ask = q.get("bp"), q.get("ap")
            m = _mid(bid, ask, None)
            if m and bid is not None and ask is not None:
                rel_spreads.append((ask - bid) / m)
        liquidity_score, liq_note = derive_liquidity(rel_spreads)
        notes.append(liq_note)

        return iv_rank, round(expected_move, 2), liquidity_score, notes


# ── Demo provider ─────────────────────────────────────────────────────
# Realistic anchor values for well-known symbols; anything else is derived
# deterministically from a stable hash of the symbol so the demo is repeatable.
_DEMO_ANCHORS: dict[str, dict] = {
    "SPY": {"price": 548.20, "iv_rank": 32.0, "iv_trend": 0.1, "spot_trend": 0.42,
            "expected_move": 8.10, "liquidity_score": 0.98},
    "QQQ": {"price": 476.90, "iv_rank": 41.0, "iv_trend": 0.2, "spot_trend": 0.35,
            "expected_move": 9.40, "liquidity_score": 0.97},
    "IWM": {"price": 203.15, "iv_rank": 28.0, "iv_trend": -0.1, "spot_trend": -0.18,
            "expected_move": 5.20, "liquidity_score": 0.93},
    "AAPL": {"price": 224.80, "iv_rank": 46.0, "iv_trend": 0.15, "spot_trend": 0.28,
             "expected_move": 6.70, "liquidity_score": 0.95},
    "TSLA": {"price": 251.30, "iv_rank": 63.0, "iv_trend": 0.3, "spot_trend": 0.55,
             "expected_move": 15.80, "liquidity_score": 0.9},
    "NVDA": {"price": 128.40, "iv_rank": 58.0, "iv_trend": 0.25, "spot_trend": 0.61,
             "expected_move": 7.90, "liquidity_score": 0.94},
}


class DemoProvider(MarketDataProvider):
    """
    Deterministic, realistic values per symbol — no network, no keys.

    Known symbols use hand-tuned anchors; unknown symbols derive stable values
    from a hash of the ticker so repeated calls return identical numbers.
    """

    name = "demo"

    def fetch(self, symbol: str) -> MarketPrefill | None:
        symbol = (symbol or "").strip().upper()
        if not symbol:
            return None
        v = _DEMO_ANCHORS.get(symbol) or self._synthesize(symbol)
        notes = [
            "source: demo — deterministic synthetic values, not a live feed.",
            f"iv_rank {v['iv_rank']:.0f} is an illustrative (estimated) demo value.",
            f"expected_move {v['expected_move']:.2f} ≈ demo ATM straddle proxy.",
        ]
        return MarketPrefill(
            price=v["price"],
            iv_rank=v["iv_rank"],
            iv_trend=v["iv_trend"],
            spot_trend=v["spot_trend"],
            expected_move=v["expected_move"],
            liquidity_score=v["liquidity_score"],
            source=self.name,
            as_of=_utc_now_iso(),
            notes=notes,
        )

    @staticmethod
    def _synthesize(symbol: str) -> dict:
        # Deterministic pseudo-random values from a stable hash of the symbol.
        h = 0
        for ch in symbol:
            h = (h * 131 + ord(ch)) & 0xFFFFFFFF
        r = lambda n: ((h >> n) & 0xFF) / 255.0  # noqa: E731 — 0..1 knobs
        price = round(40 + r(0) * 360, 2)                 # $40–$400
        iv_rank = round(15 + r(4) * 70, 1)                # 15–85
        expected_move = round(price * (0.02 + r(8) * 0.05), 2)  # 2%–7% of spot
        spot_trend = round(r(12) * 2 - 1, 2)              # −1..+1
        iv_trend = round((r(16) * 2 - 1) * 0.4, 2)        # −0.4..+0.4
        liquidity_score = round(0.6 + r(20) * 0.39, 3)    # 0.60–0.99
        return {
            "price": price, "iv_rank": iv_rank, "iv_trend": iv_trend,
            "spot_trend": spot_trend, "expected_move": expected_move,
            "liquidity_score": liquidity_score,
        }


# ── selection ─────────────────────────────────────────────────────────
def alpaca_keys_present(env: dict | None = None) -> bool:
    env = env if env is not None else os.environ
    kid = env.get("APCA_API_KEY_ID") or env.get("ALPACA_API_KEY_ID")
    sec = env.get("APCA_API_SECRET_KEY") or env.get("ALPACA_API_SECRET_KEY")
    return bool(kid and sec)


def select_provider(env: dict | None = None) -> MarketDataProvider:
    """AlpacaProvider when keys are present, else DemoProvider."""
    if alpaca_keys_present(env):
        return AlpacaProvider()
    return DemoProvider()
