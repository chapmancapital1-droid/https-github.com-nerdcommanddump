"""
Daily-bar backtest engine for the NCI nerdcommand options assistant (Phase 6b).

Simulates repeatedly opening the strategy the live :class:`StrategySelector`
would pick, and holding it to a fixed horizon (or an earlier max-loss breach),
scoring each trade against the Phase-6a payoff curve at the exit day's close.

Honest about its approximations — this is educational tooling, not a pricing
desk:

  * Daily granularity only; no intraday path.
  * A trade's exit P/L is the payoff-curve value at the exit-day close, i.e. an
    *intrinsic-value-at-expiry* approximation. When a position is closed BEFORE
    its horizon (a max-loss stop), that curve ignores the remaining extrinsic
    value the position would still carry — real early exits are usually less bad
    than intrinsic implies. Documented, not hidden.
  * Implied volatility is not observable from price bars, so ``iv_rank`` is a
    *realized-volatility proxy*: the percentile of trailing realized vol within
    the backtest window, clearly labelled ``iv_proxy`` in every reconstructed
    context.
  * Early assignment, dividends, financing, and commissions are ignored.

No network calls live in this module. Bars come from :func:`synthetic_bars`
(deterministic GBM with regime shifts) or :func:`bars_from_csv`.

The Monte Carlo promotion gate (:func:`validate`) applies the SAME
block-bootstrap idea used by ``nci-hybrid-phoenix`` so backtests get the same
statistical honesty as the Phoenix agents. A small local implementation is used
on purpose — we do not import across packages.

Educational analysis tooling — not investment advice.
"""

from __future__ import annotations

import csv
import math
import random
import statistics
from dataclasses import dataclass, field, asdict
from datetime import date, timedelta

from .models import (
    StrategyType, MarketContext, UserPreferences, RiskProfile,
)
from .strategy_selector import StrategySelector
from .payoff import build_legs, payoff_curve, default_price_range, net_entry_price


# ── price bars ────────────────────────────────────────────────────────
@dataclass
class Bar:
    """One daily OHLCV bar."""

    date: str  # ISO date
    open: float
    high: float
    low: float
    close: float
    volume: float

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: dict) -> "Bar":
        return cls(
            date=str(d["date"]),
            open=float(d["open"]),
            high=float(d["high"]),
            low=float(d["low"]),
            close=float(d["close"]),
            volume=float(d.get("volume", 0.0)),
        )


def synthetic_bars(
    symbol: str,
    days: int,
    seed: int,
    start_price: float = 100.0,
    start_date: str = "2022-01-03",
) -> list[Bar]:
    """
    Deterministic geometric-Brownian-motion bars with regime shifts.

    The same ``seed`` always yields the same series. Volatility and drift switch
    between calm / trending / turbulent regimes at pseudo-random block
    boundaries so the series has the streaky, non-stationary character that
    makes a block bootstrap meaningful.
    """
    rng = random.Random(f"{seed}:{symbol}")
    regimes = [
        (0.0006, 0.010),   # gentle uptrend, low vol
        (-0.0004, 0.018),  # drift down, higher vol
        (0.0002, 0.008),   # flat, calm
        (0.0000, 0.032),   # turbulent, no drift
    ]
    mu, sigma = regimes[rng.randrange(len(regimes))]
    bars: list[Bar] = []
    price = start_price
    d0 = date.fromisoformat(start_date)
    days_ahead = 0
    for i in range(days):
        # occasionally switch regime (streak-preserving blocks ~ 30 sessions)
        if rng.random() < 1.0 / 30.0:
            mu, sigma = regimes[rng.randrange(len(regimes))]
        shock = rng.gauss(mu, sigma)
        open_p = price
        close_p = max(0.01, price * math.exp(shock))
        # intrabar range around the open/close
        hi = max(open_p, close_p) * (1.0 + abs(rng.gauss(0.0, sigma * 0.5)))
        lo = min(open_p, close_p) * (1.0 - abs(rng.gauss(0.0, sigma * 0.5)))
        vol = round(1_000_000 * (1.0 + abs(rng.gauss(0.0, 0.4))), 0)
        # advance calendar, skipping weekends
        while True:
            cur = d0 + timedelta(days=days_ahead)
            days_ahead += 1
            if cur.weekday() < 5:
                break
        bars.append(Bar(cur.isoformat(), round(open_p, 4), round(hi, 4),
                        round(lo, 4), round(close_p, 4), vol))
        price = close_p
    return bars


def bars_from_csv(path: str) -> list[Bar]:
    """
    Load daily bars from a CSV with a header row. Column names are matched
    case-insensitively; ``date,open,high,low,close,volume`` (volume optional).
    Never performs any network access.
    """
    bars: list[Bar] = []
    with open(path, newline="") as fh:
        reader = csv.DictReader(fh)
        norm = {name.lower().strip(): name for name in (reader.fieldnames or [])}

        def col(row, key, default=None):
            src = norm.get(key)
            return row[src] if src is not None else default

        for row in reader:
            bars.append(Bar(
                date=str(col(row, "date")),
                open=float(col(row, "open")),
                high=float(col(row, "high")),
                low=float(col(row, "low")),
                close=float(col(row, "close")),
                volume=float(col(row, "volume", 0.0) or 0.0),
            ))
    return bars


# ── realized-vol / context reconstruction ─────────────────────────────
def realized_vol(closes: list[float], window: int = 20) -> float:
    """Annualised realized volatility from trailing daily log returns."""
    rets = [
        math.log(closes[i] / closes[i - 1])
        for i in range(1, len(closes))
        if closes[i - 1] > 0 and closes[i] > 0
    ]
    tail = rets[-window:]
    if len(tail) < 2:
        return 0.0
    return statistics.pstdev(tail) * math.sqrt(252.0)


def _percentile_rank(value: float, history: list[float]) -> float:
    """Percentile rank (0-100) of ``value`` within ``history``."""
    if not history:
        return 50.0
    below = sum(1 for h in history if h <= value)
    return 100.0 * below / len(history)


def reconstruct_context(
    symbol: str, bars: list[Bar], idx: int, vol_history: list[float]
) -> MarketContext:
    """
    Build a :class:`MarketContext` at bar ``idx`` from price action alone.

    ``iv_rank`` is an IV *proxy*: the percentile of the current 20-day realized
    vol within the vols seen so far in the window. ``expected_move`` is one
    standard deviation over the horizon derived from that same realized vol.
    ``iv_trend`` / ``spot_trend`` come from short vs longer moving averages.
    """
    closes = [b.close for b in bars[: idx + 1]]
    price = closes[-1]
    rv = realized_vol(closes)
    iv_proxy_rank = _percentile_rank(rv, vol_history) if vol_history else 50.0

    # spot_trend: 10-day vs 30-day SMA premium, saturating at +-3%.
    def sma(n):
        w = closes[-n:]
        return sum(w) / len(w) if w else price
    fast, slow = sma(10), sma(30)
    spot_trend = max(-1.0, min(1.0, ((fast - slow) / slow) / 0.03)) if slow else 0.0

    # iv_trend: recent realized vol vs a slightly older reading.
    older_rv = realized_vol(closes[:-5]) if len(closes) > 25 else rv
    iv_trend = max(-1.0, min(1.0, (rv - older_rv) / 0.10)) if older_rv else 0.0

    # expected_move over ~21 sessions (one option cycle) from realized vol.
    expected_move = price * rv * math.sqrt(21.0 / 252.0) if rv > 0 else price * 0.03

    return MarketContext(
        symbol=symbol,
        price=round(price, 4),
        iv_rank=round(iv_proxy_rank, 2),          # labelled iv_proxy below
        iv_trend=round(iv_trend, 4),
        spot_trend=round(spot_trend, 4),
        expected_move=round(expected_move, 4),
        liquidity_score=0.9,                      # synthetic: assume liquid
        news_sentiment=0.0,
    )


# ── backtest plan / results ───────────────────────────────────────────
@dataclass
class BacktestPlan:
    """
    How the backtest enters and exits.

    * ``entry_every_n_days`` — cadence of entry attempts.
    * ``iv_proxy_min`` — only enter when the IV proxy percentile is at/above
      this (``None`` disables the filter). Lets you test "sell premium only when
      vol is rich" style rules against the realized-vol proxy.
    * ``holding_days`` — horizon; exit at this many sessions after entry.
    * ``max_loss_stop`` — if set, exit early on the first day the position's
      payoff-at-close breaches ``-max_loss_stop`` dollars (intrinsic approx).
    * ``bias`` / ``risk_profile`` / ``max_loss_dollars`` feed the selector.
    """

    entry_every_n_days: int = 21
    iv_proxy_min: float | None = None
    holding_days: int = 21
    max_loss_stop: float | None = None
    bias: str = "neutral"
    risk_profile: RiskProfile = RiskProfile.MODERATE
    max_loss_dollars: float = 5000.0
    time_horizon_days: int = 21
    warmup_days: int = 30

    def to_dict(self) -> dict:
        d = asdict(self)
        d["risk_profile"] = self.risk_profile.value
        return d

    @classmethod
    def from_dict(cls, d: dict) -> "BacktestPlan":
        d = dict(d)
        if "risk_profile" in d and not isinstance(d["risk_profile"], RiskProfile):
            d["risk_profile"] = RiskProfile(d["risk_profile"])
        return cls(**d)


@dataclass
class BacktestTrade:
    """One simulated round-trip."""

    entry_date: str
    exit_date: str
    strategy: str
    entry_price: float          # net per-share debit(+)/credit(-)
    entry_spot: float
    exit_spot: float
    pnl: float                  # dollars, at 100x multiplier
    exit_reason: str            # "horizon" | "max_loss_stop"

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: dict) -> "BacktestTrade":
        return cls(**d)


@dataclass
class BacktestResult:
    """Full backtest output: trades, equity curve, and summary stats."""

    symbol: str
    trades: list[BacktestTrade]
    equity_curve: list[float]
    stats: dict

    def to_dict(self) -> dict:
        return {
            "symbol": self.symbol,
            "trades": [t.to_dict() for t in self.trades],
            "equity_curve": [round(e, 4) for e in self.equity_curve],
            "stats": self.stats,
        }

    @classmethod
    def from_dict(cls, d: dict) -> "BacktestResult":
        return cls(
            symbol=d["symbol"],
            trades=[BacktestTrade.from_dict(t) for t in d["trades"]],
            equity_curve=list(d["equity_curve"]),
            stats=dict(d["stats"]),
        )

    def r_series(self, risk_per_trade: float | None = None) -> list[float]:
        """
        Convert trade P/L into an R-multiple series for the MC gate.

        R is P/L divided by a per-trade risk unit. If ``risk_per_trade`` is not
        given, we use the average absolute modeled max-loss across trades (a
        stand-in for "1R of risk"), so a trade that loses its whole modeled risk
        is about -1R.
        """
        if not self.trades:
            return []
        if risk_per_trade is None:
            losses = [abs(min(t.pnl, 0.0)) for t in self.trades]
            unit = max(statistics.mean([l for l in losses if l > 0] or [1.0]), 1.0)
        else:
            unit = max(risk_per_trade, 1.0)
        return [t.pnl / unit for t in self.trades]


# ── the engine ────────────────────────────────────────────────────────
class BacktestEngine:
    """Runs a :class:`BacktestPlan` over a list of :class:`Bar`."""

    def __init__(self, selector: StrategySelector | None = None):
        self.selector = selector or StrategySelector()

    def _pnl_at_close(
        self, strategy, context, prefs, close_price: float
    ) -> tuple[float, float]:
        """
        (entry_price, pnl_dollars) of the position opened in ``context`` when the
        underlying is at ``close_price`` on the scoring day — payoff at expiry
        (intrinsic approximation).
        """
        legs = build_legs(strategy, context, prefs)
        entry = net_entry_price(
            legs, context.price, context.expected_move, prefs.time_horizon_days
        )
        # single-point payoff at the given close
        curve = payoff_curve(legs, entry, [close_price])
        return entry, curve.pnl[0]

    def run(self, symbol: str, bars: list[Bar], plan: BacktestPlan) -> BacktestResult:
        """
        Walk the bars, open the selector's pick at each eligible entry, and hold
        to horizon or an earlier max-loss stop. Deterministic given the bars and
        plan (no RNG in the loop).
        """
        trades: list[BacktestTrade] = []
        equity = 0.0
        equity_curve: list[float] = []

        prefs = UserPreferences(
            symbol=symbol,
            risk_profile=plan.risk_profile,
            max_loss_pct=2.0,
            max_loss_dollars=plan.max_loss_dollars,
            bias=plan.bias,
            time_horizon_days=plan.time_horizon_days,
        )

        # rolling realized-vol history so iv_proxy percentile has a reference
        vol_history: list[float] = []
        n = len(bars)
        last_entry_idx = -10**9

        for idx in range(n):
            closes = [b.close for b in bars[: idx + 1]]
            if idx >= plan.warmup_days:
                vol_history.append(realized_vol(closes))

            # equity curve tracks realized P/L day by day
            equity_curve.append(equity)

            if idx < plan.warmup_days:
                continue
            if idx - last_entry_idx < plan.entry_every_n_days:
                continue
            exit_idx = idx + plan.holding_days
            if exit_idx >= n:
                continue

            context = reconstruct_context(symbol, bars, idx, vol_history)

            # IV-proxy gate
            if plan.iv_proxy_min is not None and context.iv_rank < plan.iv_proxy_min:
                continue

            picks = self.selector.select_strategies(context, prefs, top_n=1)
            if not picks:
                continue
            strategy = picks[0][0]

            # scan for a max-loss stop between entry+1 and horizon
            exit_reason = "horizon"
            chosen_exit = exit_idx
            entry_price = None
            for j in range(idx + 1, exit_idx + 1):
                entry_price, pnl_j = self._pnl_at_close(
                    strategy, context, prefs, bars[j].close
                )
                if plan.max_loss_stop is not None and pnl_j <= -abs(plan.max_loss_stop):
                    chosen_exit = j
                    exit_reason = "max_loss_stop"
                    break

            entry_price, final_pnl = self._pnl_at_close(
                strategy, context, prefs, bars[chosen_exit].close
            )
            equity += final_pnl
            trades.append(BacktestTrade(
                entry_date=bars[idx].date,
                exit_date=bars[chosen_exit].date,
                strategy=strategy.value,
                entry_price=round(entry_price, 4),
                entry_spot=round(context.price, 4),
                exit_spot=round(bars[chosen_exit].close, 4),
                pnl=round(final_pnl, 4),
                exit_reason=exit_reason,
            ))
            last_entry_idx = idx

        stats = _compute_stats(trades, equity_curve, bars)
        return BacktestResult(symbol, trades, equity_curve, stats)


def _compute_stats(
    trades: list[BacktestTrade], equity_curve: list[float], bars: list[Bar]
) -> dict:
    """Summary stats: win rate, expectancy, drawdown, profit factor, CAGR-ish."""
    n = len(trades)
    if n == 0:
        return {
            "total_trades": 0, "win_rate": 0.0, "expectancy": 0.0,
            "total_pnl": 0.0, "max_drawdown": 0.0, "profit_factor": 0.0,
            "annualized_return_pct": 0.0, "gross_profit": 0.0, "gross_loss": 0.0,
        }
    pnls = [t.pnl for t in trades]
    wins = [p for p in pnls if p > 0]
    losses = [p for p in pnls if p < 0]
    total_pnl = sum(pnls)
    gross_profit = sum(wins)
    gross_loss = abs(sum(losses))

    # max drawdown on the realized equity curve
    peak = equity_curve[0] if equity_curve else 0.0
    max_dd = 0.0
    for e in equity_curve:
        peak = max(peak, e)
        max_dd = max(max_dd, peak - e)

    # CAGR-ish: total P/L relative to peak risk deployed, annualised by span.
    if len(bars) > 1:
        span_days = (date.fromisoformat(bars[-1].date)
                     - date.fromisoformat(bars[0].date)).days or 1
        years = span_days / 365.25
    else:
        years = 1.0
    risk_base = max(max((abs(min(t.pnl, 0.0)) for t in trades), default=1.0), 1.0)
    ann = ((total_pnl / risk_base) / years * 100.0) if years > 0 else 0.0

    return {
        "total_trades": n,
        "win_rate": round(len(wins) / n, 4),
        "expectancy": round(total_pnl / n, 4),
        "total_pnl": round(total_pnl, 4),
        "gross_profit": round(gross_profit, 4),
        "gross_loss": round(gross_loss, 4),
        "max_drawdown": round(max_dd, 4),
        "profit_factor": round(gross_profit / gross_loss, 4) if gross_loss > 0
        else (float("inf") if gross_profit > 0 else 0.0),
        "annualized_return_pct": round(ann, 4),
    }


# ── Monte Carlo promotion gate (local block-bootstrap) ────────────────
@dataclass
class MCConfig:
    """
    Local mirror of the ``nci-hybrid-phoenix`` Monte Carlo config so backtests
    get the same statistical gate without importing across packages.
    """

    simulations: int = 5000
    block_size: int = 10
    ruin_threshold_r: float = 30.0
    max_ruin_probability: float = 0.02
    min_expectancy_r: float = 0.0
    seed: int | None = 12345

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: dict) -> "MCConfig":
        return cls(**{k: d[k] for k in asdict(cls()) if k in d})


@dataclass
class MCReport:
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


def _block_resample(series: list[float], block_size: int, rng: random.Random) -> list[float]:
    """Sample contiguous blocks (with replacement) until length matches."""
    n = len(series)
    out: list[float] = []
    while len(out) < n:
        start = rng.randrange(n)
        out.extend(series[start:start + block_size])
    return out[:n]


def _path_stats(r_series: list[float], ruin_threshold_r: float) -> tuple[float, float, bool]:
    """Walk one resampled path -> (expectancy, max drawdown in R, ruined?)."""
    equity = peak = max_dd = 0.0
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


def validate(
    result: BacktestResult,
    config: MCConfig | None = None,
    risk_per_trade: float | None = None,
) -> MCReport:
    """
    Run the backtest's R-series through a block-bootstrap Monte Carlo, mirroring
    the Phoenix promotion gate: accept only when P(ruin) and median expectancy
    clear the configured floors. Deterministic under ``config.seed``.
    """
    cfg = config or MCConfig()
    r_series = result.r_series(risk_per_trade)
    reasons: list[str] = []

    if len(r_series) < cfg.block_size * 2:
        return MCReport(
            accepted=False, simulations=0, ruin_probability=1.0,
            median_expectancy_r=0.0, median_max_drawdown_r=0.0,
            p95_max_drawdown_r=0.0,
            reasons=[f"insufficient history: {len(r_series)} trades "
                     f"(need >= {cfg.block_size * 2})"],
        )

    rng = random.Random(cfg.seed)
    expectancies: list[float] = []
    drawdowns: list[float] = []
    ruins = 0
    for _ in range(cfg.simulations):
        path = _block_resample(r_series, cfg.block_size, rng)
        exp, dd, ruined = _path_stats(path, cfg.ruin_threshold_r)
        expectancies.append(exp)
        drawdowns.append(dd)
        ruins += int(ruined)

    ruin_p = ruins / cfg.simulations
    med_exp = statistics.median(expectancies)
    med_dd = statistics.median(drawdowns)
    p95_dd = sorted(drawdowns)[min(len(drawdowns) - 1, round(0.95 * (len(drawdowns) - 1)))]

    if ruin_p > cfg.max_ruin_probability:
        reasons.append(f"P(ruin) {ruin_p:.3f} > limit {cfg.max_ruin_probability:.3f}")
    if med_exp < cfg.min_expectancy_r:
        reasons.append(f"median expectancy {med_exp:.3f}R < floor {cfg.min_expectancy_r}R")

    return MCReport(
        accepted=not reasons,
        simulations=cfg.simulations,
        ruin_probability=ruin_p,
        median_expectancy_r=med_exp,
        median_max_drawdown_r=med_dd,
        p95_max_drawdown_r=p95_dd,
        reasons=reasons or ["all acceptance criteria met"],
    )
