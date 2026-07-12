#!/usr/bin/env python3
"""
update_nci_brain.py — regenerate the NCI Phoenix brain JSON on demand.

This is the maintained version of the one-liner pattern:

    import json
    json_data = { ... }
    with open("C:/NCI_Brain_updated.txt", "w") as f:
        json.dump(json_data, f, ensure_ascii=False, indent=4)

…but instead of hand-editing a raw dict, you tune the config blocks below,
run the script, and it emits a fresh, schema-valid brain state — and
(optionally) snapshots it into the version store so every regeneration is
recoverable.

Usage (Windows):
    python update_nci_brain.py                          → C:\\NCI\\Brain\\brain_state.json
    python update_nci_brain.py --out C:\\NCI_Brain_updated.txt
    python update_nci_brain.py --snapshot "v2.1.2" --notes "widened breaker to 14%"

Usage (anywhere):
    python3 examples/update_nci_brain.py --out ./brain_state.json
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from nci_phoenix import (  # noqa: E402
    BrainVersionStore,
    MonteCarloConfig,
    NCIPhoenixBrain,
    PIDConfig,
    PoolConfig,
    RiskConfig,
)

# ---------------------------------------------------------------------------
# TUNE HERE — these blocks are the knobs the dev team edits, then re-runs.
# ---------------------------------------------------------------------------

POOL = PoolConfig(
    promotion_score_threshold=0.65,
    demotion_score_threshold=0.35,
    exploration_rate=0.05,
    specialization_bonus=0.15,
    min_trades_for_promotion=10,
    score_smoothing=0.30,
)

PID = PIDConfig(
    kp=0.8, ki=0.15, kd=0.25,
    setpoint_r_per_day=0.5,
    output_min=0.10, output_max=2.00,
    integral_limit=5.0,
)

RISK = RiskConfig(
    daily_loss_limit_r=3.0,
    weekly_loss_limit_r=8.0,
    max_drawdown_pct=12.0,
    max_concurrent_positions=4,
    max_correlated_exposure=2,
    news_blackout_minutes=15,
    news_impact_block=0.75,
)

MONTE_CARLO = MonteCarloConfig(
    simulations=7500,
    block_size=10,
    ruin_threshold_pct=30.0,
    max_ruin_probability=0.02,
    min_expectancy_r=0.05,
    max_median_drawdown_r=12.0,
)

DEFAULT_OUT = r"C:\NCI\Brain\brain_state.json"
DEFAULT_VERSIONS = r"C:\NCI\Brain\versions"


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--out", default=DEFAULT_OUT,
                    help=f"output path (default: {DEFAULT_OUT})")
    ap.add_argument("--merge", metavar="EXISTING",
                    help="load an existing brain_state.json first so learned "
                         "scores/memory carry over; only configs are refreshed")
    ap.add_argument("--snapshot", metavar="LABEL",
                    help="also snapshot into the version store under this label")
    ap.add_argument("--notes", default="", help="notes for the snapshot")
    ap.add_argument("--versions", default=DEFAULT_VERSIONS,
                    help=f"version store root (default: {DEFAULT_VERSIONS})")
    args = ap.parse_args()

    brain = NCIPhoenixBrain(
        pool_config=POOL, pid_config=PID,
        risk_config=RISK, mc_config=MONTE_CARLO,
    )

    if args.merge:
        # Carry learned state forward; the fresh configs above still apply.
        existing = json.loads(Path(args.merge).read_text())
        brain.load_state(existing)
        brain.pool.config = POOL
        brain.risk.config = RISK
        brain.pid.config = PID
        print(f"merged learned state from {args.merge} "
              f"({len(brain.memory)} trades in memory)")

    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    state = brain.to_state()
    out.write_text(json.dumps(state, ensure_ascii=False, indent=4))
    print(f"brain state written → {out}")

    if args.snapshot:
        store = BrainVersionStore(args.versions)
        vid = store.snapshot(state, label=args.snapshot, notes=args.notes)
        print(f"snapshotted as {vid} in {args.versions}")

    print("Educational analysis tooling — not investment advice.")


if __name__ == "__main__":
    main()
