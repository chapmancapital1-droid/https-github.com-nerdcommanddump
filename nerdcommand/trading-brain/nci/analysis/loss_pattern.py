"""Loss pattern analyzer — cross-tabs closed trades from MT4/bridge logs.

Reads all closed-trade JSON files from BRIDGE_DATA_DIR/closed_trades/
and cross-tabs losses (vs wins) by:
  - pair, session, signal score band, direction, voter combo,
    time-to-red, ATR regime, spread

Output: ANALYSIS_DIR/loss_pattern_report.md + loss_pattern_data.json

Run:
    python analysis/loss_pattern.py
"""
import json
import os
import sys
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

# Allow running from analysis/ subfolder
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
from config import ANALYSIS_DIR, BRIDGE_DATA_DIR

CLOSED_DIR = os.path.join(BRIDGE_DATA_DIR, "closed_trades")
VALIDATED_WIN_RATES = {
    "OVERLAP": 85.9,
    "GAP_FILL": 84.1,
}


def _session(hour_utc: int) -> str:
    if 0 <= hour_utc < 7:
        return "ASIA"
    if 7 <= hour_utc < 12:
        return "LONDON"
    if 12 <= hour_utc < 17:
        return "OVERLAP"
    if 17 <= hour_utc < 21:
        return "NY_CLOSE"
    return "OFF_HOURS"


def _score_band(score: float) -> str:
    if score >= 90:
        return "90+"
    if score >= 80:
        return "80-89"
    if score >= 70:
        return "70-79"
    return "<70"


def _atr_regime(atr: float | None) -> str:
    if atr is None:
        return "unknown"
    if atr < 0.0003:
        return "low"
    if atr < 0.0008:
        return "medium"
    return "high"


def load_trades(closed_dir: str) -> list[dict]:
    trades = []
    p = Path(closed_dir)
    if not p.exists():
        return trades
    for f in sorted(p.glob("*.json")):
        try:
            with open(f) as fh:
                data = json.load(fh)
            if isinstance(data, list):
                trades.extend(data)
            else:
                trades.append(data)
        except Exception:
            continue
    return trades


def analyze(trades: list[dict]) -> dict:
    losses = [t for t in trades if t.get("profit", 0) < 0]
    wins   = [t for t in trades if t.get("profit", 0) >= 0]

    def cross_tab(group: list[dict], key_fn) -> dict:
        counts: dict[str, dict] = defaultdict(lambda: {"count": 0, "total_pnl": 0.0})
        for t in group:
            k = key_fn(t)
            counts[k]["count"] += 1
            counts[k]["total_pnl"] += t.get("profit", 0)
        return dict(sorted(counts.items(), key=lambda x: x[1]["count"], reverse=True))

    def session_key(t):
        ts = t.get("close_time", t.get("open_time", 0))
        dt = datetime.fromtimestamp(ts, tz=timezone.utc) if ts else datetime.now(timezone.utc)
        return _session(dt.hour)

    by_pair       = cross_tab(losses, lambda t: t.get("symbol", "?"))
    by_session    = cross_tab(losses, session_key)
    by_direction  = cross_tab(losses, lambda t: t.get("side", "?"))
    by_score_band = cross_tab(losses, lambda t: _score_band(t.get("score", 0)))
    by_atr        = cross_tab(losses, lambda t: _atr_regime(t.get("atr")))
    by_spread     = cross_tab(losses, lambda t: (
        "wide (>2.0)" if (t.get("spread") or 0) > 2.0 else
        "normal (≤2.0)"
    ))
    by_voters     = cross_tab(losses, lambda t: str(sorted(t.get("voters", []))))

    # Win-rate delta vs validated config
    strategy_compare = {}
    for strat, claimed in VALIDATED_WIN_RATES.items():
        strat_trades = [t for t in trades if t.get("strategy") == strat]
        strat_wins   = [t for t in strat_trades if t.get("profit", 0) >= 0]
        actual_wr = (len(strat_wins) / len(strat_trades) * 100) if strat_trades else None
        strategy_compare[strat] = {
            "claimed_wr": claimed,
            "actual_wr":  round(actual_wr, 1) if actual_wr is not None else "n/a",
            "sample":     len(strat_trades),
            "delta":      round(actual_wr - claimed, 1) if actual_wr is not None else "n/a",
        }

    return {
        "total_trades": len(trades),
        "total_losses": len(losses),
        "total_wins":   len(wins),
        "overall_wr":   round(len(wins) / len(trades) * 100, 1) if trades else 0,
        "total_loss_pnl": round(sum(t.get("profit", 0) for t in losses), 2),
        "by_pair":        by_pair,
        "by_session":     by_session,
        "by_direction":   by_direction,
        "by_score_band":  by_score_band,
        "by_atr_regime":  by_atr,
        "by_spread":      by_spread,
        "by_voter_combo": by_voters,
        "strategy_vs_config": strategy_compare,
    }


def top_n(d: dict, n: int = 5) -> list[tuple]:
    return list(d.items())[:n]


def write_report(results: dict, out_dir: str) -> str:
    os.makedirs(out_dir, exist_ok=True)
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    md_path   = os.path.join(out_dir, "loss_pattern_report.md")
    json_path = os.path.join(out_dir, f"loss_pattern_data_{ts}.json")

    r = results

    def fmt_table(rows: list[tuple]) -> str:
        lines = ["| Bucket | Losses | Total P&L |", "|--------|--------|-----------|"]
        for k, v in rows:
            lines.append(f"| {k} | {v['count']} | ${v['total_pnl']:+.2f} |")
        return "\n".join(lines)

    md = f"""# NCI Loss Pattern Report
Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}

## Overview
| Metric | Value |
|--------|-------|
| Total trades | {r['total_trades']} |
| Wins | {r['total_wins']} ({r['overall_wr']}%) |
| Losses | {r['total_losses']} |
| Total loss P&L | ${r['total_loss_pnl']:+.2f} |

## Strategy vs Validated Config
| Strategy | Claimed WR | Actual WR | Delta | Sample |
|----------|-----------|-----------|-------|--------|
"""
    for strat, s in r["strategy_vs_config"].items():
        md += f"| {strat} | {s['claimed_wr']}% | {s['actual_wr']}% | {s['delta']}pp | {s['sample']} |\n"

    md += f"""
## Top Loss Pairs
{fmt_table(top_n(r['by_pair']))}

## By Session
{fmt_table(top_n(r['by_session']))}

## By Direction
{fmt_table(top_n(r['by_direction']))}

## By Signal Score Band
{fmt_table(top_n(r['by_score_band']))}

## By ATR Regime
{fmt_table(top_n(r['by_atr_regime']))}

## By Spread
{fmt_table(top_n(r['by_spread']))}

## Top Losing Voter Combos
{fmt_table(top_n(r['by_voter_combo'], 3))}
"""

    with open(md_path, "w") as f:
        f.write(md)
    with open(json_path, "w") as f:
        json.dump(results, f, indent=2)

    return md_path


def main():
    print(f"Loading trades from {CLOSED_DIR}")
    trades = load_trades(CLOSED_DIR)
    if not trades:
        print(f"No closed trade files found in {CLOSED_DIR}")
        print("Expected format: {BRIDGE_DATA_DIR}/closed_trades/*.json")
        print("Each file: list of trade dicts with keys: symbol, side, profit,")
        print("  open_time, close_time, score, voters, atr, spread, strategy")
        return

    print(f"Analyzing {len(trades)} trades…")
    results = analyze(trades)

    r = results
    print(f"\n{'='*50}")
    print(f"LOSS PATTERN ANALYSIS  ({r['total_trades']} trades)")
    print(f"{'='*50}")
    print(f"Overall WR: {r['overall_wr']}%   "
          f"Losses: {r['total_losses']}   Total loss P&L: ${r['total_loss_pnl']:+.2f}")

    print("\nTop 3 patterns driving losses:")
    patterns = [
        ("Pair",     r["by_pair"]),
        ("Session",  r["by_session"]),
        ("Score",    r["by_score_band"]),
    ]
    for label, d in patterns:
        top = top_n(d, 1)
        if top:
            k, v = top[0]
            print(f"  {label:8}: {k:20} — {v['count']} losses  ${v['total_pnl']:+.2f}")

    path = write_report(results, ANALYSIS_DIR)
    print(f"\nFull report → {path}")


if __name__ == "__main__":
    main()
