# NCI nerdcommand — Options Assistant Dashboard

A zero-dependency, single-page web dashboard over the two Python backends in
this repo:

- **Options Assistant** — a form + results view over
  `nci_strategy_selector.QuantumAIBrain` (`select_and_reason`), with a
  multi-turn "ask Quantum AI" box (`ReasoningSession`) and an outcome-logging
  affordance that feeds `record_trade_outcome` so confidence calibration learns.
- **Phoenix Brain** — the four read-only panels from
  `nci-hybrid-phoenix/docs/DESIGN.md` §5.3 (Regime / Agent pool / Risk & sizing
  / Versions), rendered from a `brain_state.json`.

Everything is **stdlib-only**: the API layer is `http.server`, the UI is one
self-contained `index.html` (inline vanilla HTML/CSS/JS). No Flask/FastAPI, no
npm, no build step.

## Run

```bash
cd nci-dashboard
python3 -m nci_dashboard              # → http://127.0.0.1:8765
# options: --host 0.0.0.0 --port 9000
```

Open http://127.0.0.1:8765 in a browser. The two library packages are added to
`sys.path` automatically (see `nci_dashboard/paths.py`) — no install or
`PYTHONPATH` needed, and the library packages are used **unmodified**.

### AI modes (offline by default)

- **No `ANTHROPIC_API_KEY`** → deterministic offline reasoning. Everything
  works; the badge reads *Claude: offline*.
- **`ANTHROPIC_API_KEY` set** → live Claude reasoning lights up automatically
  (the strategy reasoning and the ask box call the Messages API); the badge
  reads *Claude: live*. No code change or restart flag required beyond the env
  var.

```bash
ANTHROPIC_API_KEY=sk-ant-... python3 -m nci_dashboard
```

## Tests

```bash
cd nci-dashboard
python3 -m pytest tests/ -q          # 22 passed
```

- `tests/test_api.py` — service layer: endpoint shapes, the offline path,
  confidence ranking, **max-loss filtering is reflected** (returned recs always
  fit the limit; an impossible limit yields zero recs + a reasoning note),
  multi-turn ask, the calibration/outcome loop, input validation, and the
  Phoenix reader.
- `tests/test_smoke.py` — boots the real server on an OS-assigned port and hits
  it over a socket (page served, `/api/health`, `/api/phoenix`,
  `/api/strategies` returns cards, unknown route → 404).

## API contract

All bodies and responses are JSON. Errors return
`{"error": "...", "status": <code>}` with that HTTP status.

| Method | Path | Purpose |
|---|---|---|
| GET | `/` | The single-page UI |
| GET | `/api/health` | `{status, ai_mode:"live"\|"offline", claude_available, model, disclaimer, active_sessions}` |
| GET | `/api/meta` | Enum options: `{strategy_types[13], risk_profiles[3], biases[3]}` |
| POST | `/api/strategies` | Run a selection (see below) |
| POST | `/api/ask` | Multi-turn follow-up on a selection |
| POST | `/api/outcome` | Log a realized outcome → calibration learns |
| GET | `/api/phoenix` | Raw `brain_state.json` (DESIGN §5.3 data source) |
| GET | `/api/phoenix/versions` | Version lineage list for the Versions panel |

### POST `/api/strategies`

```jsonc
// request
{
  "context": {
    "symbol": "SPY", "price": 450, "iv_rank": 75, "iv_trend": 0.3,
    "spot_trend": 0.5, "expected_move": 13, "liquidity_score": 0.95,
    "event_proximity_days": null, "news_sentiment": 0.3
  },
  "prefs": {
    "symbol": "SPY", "risk_profile": "moderate", "bias": "bullish",
    "max_loss_dollars": 1000, "max_loss_pct": 2.0, "time_horizon_days": 30
  }
}
```

`symbol`, `price`, `expected_move`, `max_loss_dollars` are required; the rest
have sensible defaults.

```jsonc
// response
{
  "session_id": "4dbadf036b96",
  "ai_mode": "offline",
  "max_loss_dollars": 1000.0,
  "result": {
    "symbol": "SPY",
    "ai_reasoning": "…",                // Claude (live) or deterministic template
    "model_used": "…",
    "recommendations": [
      {
        "strategy": "cash_secured_put",
        "legs": [ … ],
        "entry_price": 9.0, "max_profit": 1350.0, "max_loss": 675.0,
        "breakeven_price": 450.0, "probability_profit": 0.95,
        "greeks": {"delta":…, "gamma":…, "theta":…, "vega":…, "rho":…},
        "confidence_score": 1.0, "risk_rating": "medium", "reasoning": "…",
        "recommendation_id": "4dbadf036b96:0",   // echo back on /api/outcome
        "within_max_loss": true                  // max_loss <= max_loss_dollars
      }
    ]
  },
  "disclaimer": "Educational analysis tooling — not investment advice."
}
```

Only strategies whose modeled max loss fits inside `max_loss_dollars` are
returned (the library enforces a hard risk gate); recommendations are ordered by
calibrated confidence.

### POST `/api/ask`

`{"session_id": "...", "question": "Why is the top pick ranked first?"}` →
`{"answer": "...", "transcript": [{role, content, timestamp}, …], "ai_mode": …}`.
Backed by a per-session `ReasoningSession` (full conversation history retained).

### POST `/api/outcome`

```jsonc
// request — entry price is taken from the recommendation server-side
{"session_id": "...", "rec_index": 0, "exit_price": 11.0,
 "user_rating": 5, "lessons_learned": "clean win"}
```

P&L is computed as `(exit_price - entry_price) * 100`, then
`register_prediction` + `record_trade_outcome` close the calibration loop.
Response includes the updated `strategy_performance`, `calibration`, and
`total_outcomes`. Because one shared `QuantumAIBrain` backs the process,
calibration accumulates across requests for the process lifetime.

## Layout

```
nci-dashboard/
  nci_dashboard/
    __main__.py        # python3 -m nci_dashboard
    server.py          # stdlib http.server routing → DashboardAPI
    api.py             # transport-agnostic service layer (the testable core)
    paths.py           # sys.path wiring to the two sibling packages
    static/index.html  # self-contained single-page UI (inline CSS/JS)
  data/
    brain_state.json     # Phoenix brain state (seeded from the phoenix example)
    versions_index.json  # version lineage for the Versions panel
  tests/               # test_api.py, test_smoke.py (22 tests)
  README.md
```

The Phoenix tab is a **pure reader** per DESIGN §5.3. To point it at a live
brain, overwrite `data/brain_state.json` (e.g. from
`NCIPhoenixBrain.to_state()`) — no restart of the reader logic required beyond
serving the new file.

### Rollback: deliberately not wired (decision, not oversight)

The "Roll back" buttons on the Versions panel are **intentionally inert**.
Decided 2026-07-12: rollback is a state-mutating action on what will
eventually be a live trading brain, and it must not be reachable from a
read-only browser view. The capability itself already exists and is tested
(`BrainVersionStore.rollback()`, append-only) — when needed today, run it
from Python on the brain host.

Wire it up only as part of Phoenix go-live (live brain at `C:\NCI\Brain`
with nightly snapshots), and then as a small endpoint **on the brain host**
with a confirmation step and an audit note (who rolled back, why). The
dashboard button should POST to that endpoint — the dashboard itself stays
a pure reader so nothing in a browser can ever hurt the brain.

> Educational analysis tooling — not investment advice.
