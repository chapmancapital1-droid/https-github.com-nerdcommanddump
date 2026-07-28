"""Benchmark Ollama vs direct llama-cpp on 10 canned trading signals.

Run BEFORE flipping USE_LOCAL_LLAMA to compare latency:
    python benchmark.py

Run AFTER flipping:
    USE_LOCAL_LLAMA=true python benchmark.py

Results are printed as a table and saved to ANALYSIS_DIR/benchmark_results.json.
"""
import json
import os
import time
from datetime import datetime

from config import ANALYSIS_DIR

CANNED_SIGNALS = [
    "AUDCAD ranging 40 pips for 3h, ATR(14)=0.00042, spread=1.1. Session overlap starts in 20m.",
    "GBPUSD sold off 80 pips into 1.2700 support. RSI(14)=28 on H1. London open in 5m.",
    "EURUSD H4 doji at 1.0850 resistance. ADX=18, no momentum. Spread=0.9.",
    "USDJPY breaking 155.00 with volume spike. ATR=0.65. BOJ meeting risk tomorrow.",
    "NZDUSD double bottom at 0.5920 on H1. MACD bullish cross. NY session.",
    "GBPCAD H4 engulfing candle at descending trendline. Spread=2.4. Thin liquidity.",
    "AUDNZD inside bar on D1 at 1.0750. Breakout trade setup. ATR(14)=0.0048.",
    "USDCAD daily pin bar at 1.3800 round number. Oil up 1.2% today.",
    "EURJPY H1 bullish flag forming after 120-pip impulse. Retrace 38.2% Fib.",
    "GBPUSD news trade: UK CPI beat by 0.3%. Spot at 1.2750, IV elevated.",
]


def _run_backend(module_name: str, signals: list[str]) -> dict:
    import importlib
    mod = importlib.import_module(module_name)

    ok = mod.health()
    if not ok:
        return {"backend": module_name, "available": False, "results": []}

    results = []
    for prompt in signals:
        t0 = time.perf_counter()
        try:
            answer = mod.generate(prompt)
            elapsed = time.perf_counter() - t0
            results.append({"ok": True, "latency_ms": round(elapsed * 1000), "signal": answer})
        except Exception as e:
            elapsed = time.perf_counter() - t0
            results.append({"ok": False, "latency_ms": round(elapsed * 1000), "error": str(e)})

    latencies = [r["latency_ms"] for r in results if r["ok"]]
    return {
        "backend": module_name,
        "available": True,
        "results": results,
        "stats": {
            "success_rate": f"{sum(r['ok'] for r in results)}/{len(results)}",
            "avg_ms": round(sum(latencies) / len(latencies)) if latencies else None,
            "min_ms": min(latencies) if latencies else None,
            "max_ms": max(latencies) if latencies else None,
        },
    }


def main():
    print(f"\nNCI Benchmark  {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"{len(CANNED_SIGNALS)} signals × 2 backends\n")

    backends = {
        "Ollama": "nci_agent_ollama",
        "llama-cpp-direct": "nci_agent_local",
    }

    all_results = {}
    for label, module in backends.items():
        print(f"Running {label}...", flush=True)
        result = _run_backend(module, CANNED_SIGNALS)
        all_results[label] = result

        if not result["available"]:
            print(f"  ⚠  {label} not available — skipping\n")
            continue

        s = result["stats"]
        print(f"  ✓  {s['success_rate']} ok  |  avg {s['avg_ms']}ms  "
              f"min {s['min_ms']}ms  max {s['max_ms']}ms\n")

    # -- Comparison summary --------------------------------------------------
    avail = {k: v for k, v in all_results.items() if v["available"]}
    if len(avail) == 2:
        ol = avail["Ollama"]["stats"]["avg_ms"]
        lc = avail["llama-cpp-direct"]["stats"]["avg_ms"]
        if ol and lc:
            faster = "llama-cpp-direct" if lc < ol else "Ollama"
            diff_pct = abs(ol - lc) / max(ol, lc) * 100
            print(f"Winner: {faster} is {diff_pct:.0f}% faster  "
                  f"(Ollama {ol}ms vs llama-cpp {lc}ms)")

    # -- Save results --------------------------------------------------------
    os.makedirs(ANALYSIS_DIR, exist_ok=True)
    out_path = os.path.join(
        ANALYSIS_DIR, f"benchmark_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    )
    with open(out_path, "w") as f:
        json.dump(all_results, f, indent=2)
    print(f"\nSaved → {out_path}\n")


if __name__ == "__main__":
    main()
