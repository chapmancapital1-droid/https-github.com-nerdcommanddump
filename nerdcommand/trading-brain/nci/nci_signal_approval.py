"""NCI signal approval loop — LLM second-opinion on EA signal proposals.

The EA (NCI_GodMode_v3_2_Fusion.mq4) writes signal_proposal.json on every new bar.
This script reads that file, sends the proposal to the configured LLM backend
(Ollama or direct llama-cpp), and logs the verdict.

The EA does NOT currently read back an approval file — it executes autonomously
based on its own InpTradingEnabled flag. This script provides:
  1. A second-opinion log alongside every proposal (audit trail)
  2. A foundation for a future "approval gate" if you wire the bridge to check it

Usage:
    # One-shot: analyse current proposal
    python nci_signal_approval.py

    # Watch mode: analyse every new bar's proposal as the EA runs
    python nci_signal_approval.py --watch

    # Dry run (no LLM, just print proposal)
    python nci_signal_approval.py --dry-run
"""
from __future__ import annotations

import json
import os
import sys
import time
from datetime import datetime

from config import ANALYSIS_DIR, SIGNAL_LOG_DIR
from nci_agent import backend_name, generate
from nci_live import NCILiveData, SignalProposal, read_live, read_proposal, watch

APPROVAL_LOG = os.path.join(SIGNAL_LOG_DIR, "approvals.jsonl")

_SYSTEM = (
    "You are the NerdCommand Core Intelligence (NCI) signal review engine. "
    "A trading EA has proposed a trade. Your job: output exactly one of "
    "APPROVE or REJECT on the first line, followed by a single-line reason "
    "(max 15 words). No prose, no disclaimers, no markdown."
)


def analyse_proposal(
    proposal: SignalProposal,
    live: NCILiveData | None,
) -> dict:
    prompt = proposal.to_agent_prompt(live)
    t0 = time.perf_counter()
    try:
        response = generate(prompt, system=_SYSTEM)
        elapsed_ms = round((time.perf_counter() - t0) * 1000)
    except Exception as e:
        return {
            "timestamp": datetime.utcnow().isoformat(),
            "symbol": proposal.symbol,
            "action": proposal.action,
            "confluence": proposal.confluence,
            "qualifies": proposal.qualifies,
            "verdict": "ERROR",
            "reason": str(e),
            "latency_ms": round((time.perf_counter() - t0) * 1000),
            "backend": backend_name,
        }

    first_line = response.strip().split("\n")[0].upper()
    verdict = "APPROVE" if "APPROVE" in first_line else "REJECT"
    reason_lines = response.strip().split("\n")
    reason = reason_lines[1].strip() if len(reason_lines) > 1 else first_line

    record = {
        "timestamp": datetime.utcnow().isoformat(),
        "ea_timestamp": proposal.timestamp,
        "symbol": proposal.symbol,
        "action": proposal.action,
        "confluence": proposal.confluence,
        "confluence_max": proposal.confluence_max,
        "sl_pips": proposal.sl_pips,
        "tp_pips": proposal.tp_pips,
        "risk_reward": proposal.risk_reward,
        "abc_stage": proposal.abc_stage,
        "qualifies": proposal.qualifies,
        "verdict": verdict,
        "reason": reason,
        "raw_response": response.strip(),
        "latency_ms": elapsed_ms,
        "backend": backend_name,
    }
    if live:
        record["adx"] = live.adx
        record["fer"] = live.fer
        record["atr"] = live.atr
        record["consec_losses"] = live.consec_losses

    return record


def log_record(record: dict) -> None:
    os.makedirs(SIGNAL_LOG_DIR, exist_ok=True)
    with open(APPROVAL_LOG, "a") as f:
        f.write(json.dumps(record) + "\n")


def print_record(record: dict) -> None:
    v = record["verdict"]
    icon = "✅" if v == "APPROVE" else ("❌" if v == "REJECT" else "⚠️")
    print(
        f"{icon} {v:7}  {record['symbol']} {record['action']}"
        f"  conf={record['confluence']}/{record['confluence_max']}"
        f"  R:R={record['risk_reward']:.2f}"
        f"  [{record['latency_ms']}ms {record['backend']}]"
        f"  → {record['reason']}"
    )


def run_once(dry_run: bool = False) -> None:
    live     = read_live()
    proposal = read_proposal()

    if not proposal:
        print("[NCI approval] No signal_proposal.json found. EA not running or MT4_FILES_DIR not set.")
        return

    print(proposal.format_table())
    if live:
        print(f"\n  ADX {live.adx:.1f}  FER {live.fer:.3f}  Stage {live.abc_stage}")

    if dry_run:
        print("\n[dry-run] Skipping LLM call.")
        return

    record = analyse_proposal(proposal, live)
    print()
    print_record(record)
    log_record(record)
    print(f"  Logged → {APPROVAL_LOG}")


def run_watch(dry_run: bool = False) -> None:
    print(f"[NCI approval] Watch mode — polling every {2}s. Ctrl+C to stop.")
    seen: str | None = None
    for live, proposal in watch():
        if proposal is None:
            continue
        key = f"{proposal.symbol}_{proposal.action}_{proposal.timestamp}"
        if key == seen:
            continue
        seen = key
        print(f"\n{'─'*60}")
        print(proposal.format_table())
        if not dry_run and proposal.qualifies:
            record = analyse_proposal(proposal, live)
            print_record(record)
            log_record(record)
        elif not proposal.qualifies:
            print("  [skip] EA says not qualifying — no LLM call.")


def main() -> None:
    dry_run = "--dry-run" in sys.argv
    if "--watch" in sys.argv:
        run_watch(dry_run)
    else:
        run_once(dry_run)


if __name__ == "__main__":
    main()
