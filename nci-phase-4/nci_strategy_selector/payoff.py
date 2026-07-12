"""
Payoff-at-expiry engine for the NCI nerdcommand options assistant (Phase 6a).

Turns a strategy's *legs* into a real profit/loss curve so the dashboard chart
and the recommendation's headline numbers are computed from a single source of
truth and can never contradict each other.

Two responsibilities live here:

1. ``build_legs`` — upgrade the placeholder legs in ``strategy_selector`` into
   correctly structured, priceable option legs for all 13 ``StrategyType``
   values (right call/put/stock, strike offsets around spot, long/short side).
2. ``payoff_curve`` — sample the position's P/L at expiry across a price range,
   locate breakevens by *sign-change interpolation* (not closed-form formulas),
   and report max profit / max loss within the sampled window, flagging any
   side whose gain or loss is unbounded.

Option premiums are estimated with the **Bachelier (normal) model at zero
rates**, using the provided ``expected_move`` as the one-standard-deviation
terminal move. That choice is deliberate: it is pure stdlib, deterministic, and
respects put/call parity, so the net debit/credit derived from the legs is
internally consistent with the intrinsic-value payoff we chart.

Approximations (be honest — this is educational tooling, not a pricing desk):
  * Payoff is evaluated at *expiry* using intrinsic value only.
  * Multi-expiration structures (calendar / diagonal) are charted at the NEAR
    leg's expiry; the far leg's remaining extrinsic value is ignored, so those
    two curves understate the real position. Clearly flagged per strategy.
  * Early assignment, dividends, and financing are ignored.

Educational analysis tooling — not investment advice.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field, asdict

from .models import StrategyType, MarketContext, UserPreferences


CONTRACT_MULTIPLIER = 100  # one option contract controls 100 shares


# ── option leg ────────────────────────────────────────────────────────
@dataclass
class Leg:
    """
    A single option (or stock) leg of a strategy.

    ``right`` is ``"call" | "put" | "stock"``. For a stock leg ``strike`` is the
    cost basis. ``side`` is ``"long" | "short"``. ``qty`` is the (positive)
    number of contracts; direction is carried by ``side``. ``expiration`` is a
    label (e.g. ``"near"`` / ``"far"`` or an ISO date) — only its *ordering*
    matters to the intrinsic model.
    """

    right: str
    strike: float
    qty: int
    side: str
    expiration: str = "near"
    symbol: str = ""

    @property
    def sign(self) -> int:
        return 1 if self.side == "long" else -1

    def intrinsic(self, spot: float) -> float:
        """Per-share intrinsic value at expiry (unsigned by side)."""
        if self.right == "call":
            return max(spot - self.strike, 0.0)
        if self.right == "put":
            return max(self.strike - spot, 0.0)
        if self.right == "stock":
            return spot - self.strike  # basis carried in strike
        raise ValueError(f"unknown right: {self.right!r}")

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: dict) -> "Leg":
        return cls(
            right=d["right"],
            strike=float(d["strike"]),
            qty=int(d.get("qty", 1)),
            side=d.get("side", "long"),
            expiration=d.get("expiration", "near"),
            symbol=d.get("symbol", ""),
        )


# ── Bachelier (normal) pricing, zero rates ────────────────────────────
def _norm_cdf(x: float) -> float:
    return 0.5 * (1.0 + math.erf(x / math.sqrt(2.0)))


def _norm_pdf(x: float) -> float:
    return math.exp(-0.5 * x * x) / math.sqrt(2.0 * math.pi)


def bachelier_price(spot: float, strike: float, sigma: float, right: str) -> float:
    """
    Undiscounted Bachelier price of a call/put where ``sigma`` is the standard
    deviation of the terminal underlying price (i.e. the 1-sigma expected move).

    Respects put/call parity: ``call - put == spot - strike``.
    """
    sigma = max(sigma, 1e-9)
    d = (spot - strike) / sigma
    straddle_extrinsic = sigma * _norm_pdf(d)
    if right == "call":
        return (spot - strike) * _norm_cdf(d) + straddle_extrinsic
    if right == "put":
        return (strike - spot) * _norm_cdf(-d) + straddle_extrinsic
    raise ValueError(f"unpriceable right: {right!r}")


def price_leg(leg: Leg, spot: float, expected_move: float, horizon_days: int) -> float:
    """
    Estimate one leg's per-share premium.

    Time is folded in through ``expected_move``: the near leg uses the provided
    move as its 1-sigma; a ``"far"`` leg (roughly twice the horizon) scales the
    sigma by ``sqrt(2)`` to reflect its longer life. Stock legs have no premium.
    """
    if leg.right == "stock":
        return 0.0
    sigma = max(expected_move, spot * 0.02)
    if leg.expiration == "far":
        sigma *= math.sqrt(2.0)
    return bachelier_price(spot, leg.strike, sigma, leg.right)


def net_entry_price(
    legs: list[Leg], spot: float, expected_move: float, horizon_days: int
) -> float:
    """
    Net per-share options premium: positive == net debit paid, negative ==
    net credit received. Stock legs contribute nothing (their cost basis is
    captured by the payoff's ``spot - basis`` term).
    """
    total = 0.0
    for leg in legs:
        total += leg.sign * leg.qty * price_leg(leg, spot, expected_move, horizon_days)
    return total


# ── leg construction for all 13 strategies ────────────────────────────
def _round_strike(x: float) -> float:
    """Round to a sensible strike grid so legs read cleanly and deterministically."""
    return round(x, 2)


def build_legs(
    strategy: StrategyType,
    context: MarketContext,
    prefs: UserPreferences,
) -> list[Leg]:
    """
    Produce correctly structured, priceable legs for ``strategy`` centred on the
    current spot. Widths scale with spot so max losses stay realistic across
    underlyings; the near-OTM offset and wing width are modest on purpose.

    Same-strike / multi-expiry structures (calendar, diagonal) carry ``near`` /
    ``far`` expiration labels — see the module docstring for how they are
    charted.
    """
    s = context.price
    sym = context.symbol
    # near-OTM offset and vertical/wing width, as fractions of spot
    otm = _round_strike(max(0.01, 0.03 * s))       # ~3% OTM anchor
    width = _round_strike(max(0.01, 0.05 * s))      # ~5% vertical width

    def call(strike, side, exp="near"):
        return Leg("call", _round_strike(strike), 1, side, exp, sym)

    def put(strike, side, exp="near"):
        return Leg("put", _round_strike(strike), 1, side, exp, sym)

    if strategy == StrategyType.COVERED_CALL:
        return [
            Leg("stock", _round_strike(s), 1, "long", "near", sym),
            call(s + otm, "short"),
        ]
    if strategy == StrategyType.CASH_SECURED_PUT:
        return [put(s - otm, "short")]
    if strategy == StrategyType.BULL_CALL_SPREAD:
        return [call(s, "long"), call(s + width, "short")]
    if strategy == StrategyType.BEAR_CALL_SPREAD:
        return [call(s + otm, "short"), call(s + otm + width, "long")]
    if strategy == StrategyType.BULL_PUT_SPREAD:
        return [put(s - otm, "short"), put(s - otm - width, "long")]
    if strategy == StrategyType.BEAR_PUT_SPREAD:
        return [put(s, "long"), put(s - width, "short")]
    if strategy == StrategyType.IRON_CONDOR:
        return [
            put(s - otm, "short"), put(s - otm - width, "long"),
            call(s + otm, "short"), call(s + otm + width, "long"),
        ]
    if strategy == StrategyType.LONG_STRADDLE:
        return [call(s, "long"), put(s, "long")]
    if strategy == StrategyType.SHORT_STRADDLE:
        return [call(s, "short"), put(s, "short")]
    if strategy == StrategyType.LONG_STRANGLE:
        return [call(s + otm, "long"), put(s - otm, "long")]
    if strategy == StrategyType.SHORT_STRANGLE:
        return [call(s + otm, "short"), put(s - otm, "short")]
    if strategy == StrategyType.DIAGONAL_SPREAD:
        # Long a further-dated lower-strike call, short a near-dated higher call.
        return [call(s, "long", "far"), call(s + width, "short", "near")]
    if strategy == StrategyType.CALENDAR_SPREAD:
        # Same strike, long far / short near.
        return [call(s, "long", "far"), call(s, "short", "near")]
    raise ValueError(f"no leg template for {strategy!r}")


# ── payoff curve ──────────────────────────────────────────────────────
@dataclass
class PayoffCurve:
    """
    Sampled profit/loss at expiry for one position (per the legs' contract
    quantities, at the 100x multiplier).

    ``prices`` / ``pnl`` are parallel lists. ``breakevens`` are found by linear
    interpolation across P/L sign changes. ``max_profit`` / ``max_loss`` are the
    extremes *within the sampled window*; ``unbounded_gain`` / ``unbounded_loss``
    flag a side whose P/L keeps growing past the highest sampled price (i.e. the
    window figure is a floor, not the true bound).
    """

    prices: list[float]
    pnl: list[float]
    breakevens: list[float]
    max_profit: float
    max_loss: float
    unbounded_gain: bool
    unbounded_loss: bool

    def to_dict(self) -> dict:
        return {
            "prices": [round(p, 4) for p in self.prices],
            "pnl": [round(v, 4) for v in self.pnl],
            "breakevens": [round(b, 4) for b in self.breakevens],
            "max_profit": round(self.max_profit, 4),
            "max_loss": round(self.max_loss, 4),
            "unbounded_gain": self.unbounded_gain,
            "unbounded_loss": self.unbounded_loss,
        }

    @classmethod
    def from_dict(cls, d: dict) -> "PayoffCurve":
        return cls(
            prices=list(d["prices"]),
            pnl=list(d["pnl"]),
            breakevens=list(d["breakevens"]),
            max_profit=d["max_profit"],
            max_loss=d["max_loss"],
            unbounded_gain=d["unbounded_gain"],
            unbounded_loss=d["unbounded_loss"],
        )


def default_price_range(
    legs: list[Leg], spot: float, width_frac: float = 0.40, n: int = 201
) -> list[float]:
    """
    Build a price grid that brackets every strike with margin so spread plateaus
    and breakevens are captured. Spans at least +-``width_frac`` around spot, and
    always extends a half-width beyond the outermost strike.
    """
    strikes = [leg.strike for leg in legs] + [spot]
    lo_strike, hi_strike = min(strikes), max(strikes)
    span = max(hi_strike - lo_strike, spot * width_frac)
    lo = max(0.01, min(spot * (1.0 - width_frac), lo_strike - 0.5 * span))
    hi = max(spot * (1.0 + width_frac), hi_strike + 0.5 * span)
    if n < 2:
        n = 2
    step = (hi - lo) / (n - 1)
    return [lo + i * step for i in range(n)]


def _position_pnl(legs: list[Leg], entry_price: float, spot: float) -> float:
    """P/L at expiry for the whole position at one underlying price."""
    intrinsic_sum = sum(leg.sign * leg.qty * leg.intrinsic(spot) for leg in legs)
    return CONTRACT_MULTIPLIER * (intrinsic_sum - entry_price)


def _slope_beyond_high(legs: list[Leg]) -> float:
    """Marginal P/L per $1 of spot above the highest strike (calls + stock)."""
    slope = 0.0
    for leg in legs:
        if leg.right in ("call", "stock"):
            slope += leg.sign * leg.qty
    return slope


def _slope_below_low(legs: list[Leg]) -> float:
    """Marginal P/L per $1 of spot below the lowest strike (puts + stock)."""
    slope = 0.0
    for leg in legs:
        if leg.right == "put":
            slope += leg.sign * leg.qty * (-1.0)  # long put gains as spot falls
        elif leg.right == "stock":
            slope += leg.sign * leg.qty
    return slope


def payoff_curve(
    legs: list[Leg],
    entry_price: float,
    price_range: list[float],
) -> PayoffCurve:
    """
    Sample the position P/L at expiry across ``price_range`` and summarise it.

    ``entry_price`` is the net per-share options premium (positive debit /
    negative credit); it is the same number stored on the recommendation, so the
    chart and the headline can never disagree.
    """
    prices = list(price_range)
    pnl = [_position_pnl(legs, entry_price, p) for p in prices]

    # breakevens: linear interpolation wherever P/L crosses zero
    breakevens: list[float] = []
    for i in range(1, len(prices)):
        y0, y1 = pnl[i - 1], pnl[i]
        if y0 == 0.0:
            breakevens.append(prices[i - 1])
        elif y0 * y1 < 0.0:
            x0, x1 = prices[i - 1], prices[i]
            breakevens.append(x0 + (x1 - x0) * (-y0) / (y1 - y0))
    if pnl and pnl[-1] == 0.0:
        breakevens.append(prices[-1])
    # de-duplicate near-identical crossings
    deduped: list[float] = []
    for b in breakevens:
        if not deduped or abs(b - deduped[-1]) > 1e-6:
            deduped.append(round(b, 4))

    max_profit = max(pnl)
    max_loss = min(pnl)

    # slope past the outer strikes tells us whether the window bounds are real.
    # Upside (spot -> +inf) can genuinely be unbounded; downside is capped at
    # spot = 0, so we only flag the downside when the position still loses money
    # while falling *and* would keep doing so below the sampled floor.
    high_slope = _slope_beyond_high(legs)
    low_slope = _slope_below_low(legs)
    unbounded_gain = high_slope > 1e-9
    unbounded_loss = high_slope < -1e-9

    return PayoffCurve(
        prices=prices,
        pnl=pnl,
        breakevens=deduped,
        max_profit=max_profit,
        max_loss=max_loss,
        unbounded_gain=unbounded_gain,
        unbounded_loss=unbounded_loss,
    )


# ── reconciliation: one source of truth for the selector ──────────────
@dataclass
class ReconciledPayoff:
    """
    Curve-derived numbers the selector should trust over its old analytic
    guesses, plus the full curve for charting.
    """

    entry_price: float
    max_profit: float
    max_loss: float
    breakeven_price: float
    breakevens: list[float]
    unbounded_gain: bool
    unbounded_loss: bool
    curve: PayoffCurve

    def to_dict(self) -> dict:
        return {
            "entry_price": round(self.entry_price, 4),
            "max_profit": round(self.max_profit, 4),
            "max_loss": round(self.max_loss, 4),
            "breakeven_price": round(self.breakeven_price, 4),
            "breakevens": [round(b, 4) for b in self.breakevens],
            "unbounded_gain": self.unbounded_gain,
            "unbounded_loss": self.unbounded_loss,
            "curve": self.curve.to_dict(),
        }


def reconcile_payoff(
    strategy: StrategyType,
    context: MarketContext,
    prefs: UserPreferences,
    legs: list[Leg] | None = None,
) -> ReconciledPayoff:
    """
    Single source of truth the selector calls so recommendation headline numbers
    and the payoff chart are always derived from the same curve.

    Returns net entry price, max profit / loss (as positive magnitudes for the
    recommendation's convention), the primary breakeven nearest spot, all
    breakevens, unbounded flags, and the full :class:`PayoffCurve`.
    """
    if legs is None:
        legs = build_legs(strategy, context, prefs)
    entry = net_entry_price(
        legs, context.price, context.expected_move, prefs.time_horizon_days
    )
    grid = default_price_range(legs, context.price)
    curve = payoff_curve(legs, entry, grid)

    # Recommendation convention: max_profit / max_loss are positive magnitudes.
    max_profit = max(curve.max_profit, 0.0)
    max_loss = abs(min(curve.max_loss, 0.0))

    # Primary breakeven: the one closest to spot (what the UI labels headline).
    if curve.breakevens:
        breakeven = min(curve.breakevens, key=lambda b: abs(b - context.price))
    else:
        breakeven = context.price

    return ReconciledPayoff(
        entry_price=entry,
        max_profit=max_profit,
        max_loss=max_loss,
        breakeven_price=breakeven,
        breakevens=curve.breakevens,
        unbounded_gain=curve.unbounded_gain,
        unbounded_loss=curve.unbounded_loss,
        curve=curve,
    )


def legs_from_dicts(leg_dicts: list[dict]) -> list[Leg]:
    """Rebuild :class:`Leg` objects from a recommendation's ``legs`` dicts."""
    return [Leg.from_dict(d) for d in leg_dicts]


def curve_from_recommendation(rec, spot: float | None = None) -> PayoffCurve:
    """
    Rebuild the payoff curve for an existing :class:`StrategyRecommendation`
    from its (now-real) legs and stored ``entry_price`` — no market context
    required. This is what the dashboard calls to draw the chart later.

    Keeping this a helper (rather than a new field on the recommendation) means
    the recommendation dict shape is untouched and we never persist a large,
    redundant curve on every recommendation: the curve is fully reconstructable.
    """
    legs = legs_from_dicts(rec.legs)
    if spot is None:
        strikes = [leg.strike for leg in legs]
        spot = (min(strikes) + max(strikes)) / 2.0 if strikes else 0.0
    grid = default_price_range(legs, spot)
    return payoff_curve(legs, rec.entry_price, grid)
