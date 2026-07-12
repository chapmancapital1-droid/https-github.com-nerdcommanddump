# NCI nerdcommand — Options Assistant Dashboard

A zero-dependency, single-page web dashboard over the two Python backends in
this repo:

- **Options Assistant** — a form + results view over
  `nci_strategy_selector.QuantumAIBrain` (`select_and_reason`), with a
  multi-turn "ask Quantum AI" box (`ReasoningSession`) and an outcome-logging
  affordance that feeds `record_trade_outcome` so confidence calibration learns.
  Every recommendation card carries an **inline payoff-at-expiry chart** (Phase
  6a) and a **Take this trade** action that adds the position to the portfolio.
- **Backtest** — runs the live selector's pick repeatedly over deterministic
  **synthetic** bars (Phase 6b, `BacktestEngine`), then puts the trade R-series
  through the same Monte-Carlo promotion gate the Phoenix agents use
  (`validate`). Stats row, equity curve, MC verdict, and a trade table.
- **Portfolio** — a server-side `Portfolio` (Phase 7) aggregating taken
  positions: risk budget, net Greeks, concentration breakdowns, `check()`
  warnings before you add, and `suggest()` guidance.
- **Phoenix Brain** — the four read-only panels from
  `nci-hybrid-phoenix/docs/DESIGN.md` §5.3 (Regime / Agent pool / Risk & sizing
  / Versions), rendered from a `brain_state.json`.

All four tabs keep the "not investment advice" disclaimer visible in the header.
The charts are **inline SVG drawn by vanilla JS** — no chart library, no build
step.

Everything is **stdlib-only**: the API layer is `http.server`, the UI is one
self-contained `index.html` (inline vanilla HTML/CSS/JS). No Flask/FastAPI, no
npm, no build step.

## Run

```bash
cd nci-dashboard
python3 -m nci_dashboard              # → http://127.0.0.1:8765
# options: --host 0.0.0.0 --port 9000 --fresh
```

`--fresh` boots from a clean slate, ignoring any saved state (see
[Persistence](#persistence) below).

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

### Live market data (Inputs form pre-fill)

The Inputs form has a **Fetch live** button next to the Symbol field. It calls
`GET /api/market/{symbol}` and pre-fills `price`, `iv_rank`, `iv_trend`,
`spot_trend`, `expected_move`, and `liquidity_score` — the fields stay
**editable** (prefill, not lock). A provenance line under the Symbol row shows
the source/timestamp and the derivation notes; a header badge shows the active
source (**Data: Alpaca** or **Data: demo**), mirroring the Claude badge.

Two providers, selected automatically at startup:

- **Alpaca** — active when **both** `APCA_API_KEY_ID` and `APCA_API_SECRET_KEY`
  are set (aliases `ALPACA_API_KEY_ID` / `ALPACA_API_SECRET_KEY` are also
  accepted). Uses the stock **snapshot** (last price), **daily bars**
  (`spot_trend`), and the **options snapshots** feed (`iv_rank`, `expected_move`,
  `liquidity_score`). Stdlib `urllib` only; timeouts + retry-on-429/5xx with
  backoff; **never raises** — on any failure the endpoint returns a 404-style
  error and the form is simply left for manual entry.

  ```bash
  APCA_API_KEY_ID=... APCA_API_SECRET_KEY=... python3 -m nci_dashboard
  ```

- **Demo** (default, no keys) — deterministic, realistic per-symbol values so
  the feature is fully demo-able offline. Clearly labelled `source: "demo"` and
  never presented as a live feed. Known tickers (SPY/QQQ/IWM/AAPL/TSLA/NVDA) use
  hand-tuned anchors; any other ticker derives stable values from a hash of the
  symbol (repeat calls return identical numbers).

`GET /api/market/{symbol}` response:

```jsonc
{
  "prefill": {"price": 548.2, "iv_rank": 32.0, "iv_trend": 0.1,
              "spot_trend": 0.42, "expected_move": 8.1, "liquidity_score": 0.98},
  "source": "demo",                       // or "alpaca"
  "as_of": "2026-07-12T06:33:40Z",        // trade timestamp (alpaca) or now
  "notes": ["source: demo …", "iv_rank … (estimated)", …]
}
```

**How each field is derived (Alpaca):**

| Field | Derivation |
|---|---|
| `price` | last trade from the stock snapshot (falls back to the daily-bar close) |
| `spot_trend` | last close vs its 20-day SMA; a ±5% premium/discount to the SMA saturates to ±1 (clamped) |
| `expected_move` | ATM straddle mid (call mid + put mid) for the nearest standard-monthly (3rd-Friday) expiry |
| `liquidity_score` | `1 − avg(ATM bid/ask relative spread) ÷ 25%`, clamped to 0–1 (a ≥25%-wide market → 0) |
| `iv_rank` | **estimated** — see below |
| `iv_trend` | not derivable from a single snapshot → returned as `0` (labelled *unknown*) |

**iv_rank is an estimate.** The snapshot API does not expose 52-week IV history,
so a true percentile rank can't be computed. Instead the current **ATM implied
volatility** is mapped linearly onto a fixed **10%–50%** band (10% IV → rank 0,
50% IV → rank 100, clamped). Every response says so in `notes` (labelled
`ESTIMATED`) so the UI never presents it as a real historical rank. When the
options chain is unavailable, `iv_rank` defaults to 50 and `expected_move` falls
back to ~4% of spot — both noted.

## Tests

```bash
cd nci-dashboard
python3 -m pytest tests/ -q          # 83 passed
```

- `tests/test_api.py` — service layer: endpoint shapes, the offline path,
  confidence ranking, **max-loss filtering is reflected** (returned recs always
  fit the limit; an impossible limit yields zero recs + a reasoning note),
  multi-turn ask, the calibration/outcome loop, input validation, and the
  Phoenix reader.
- `tests/test_payoff.py` — the payoff endpoint: response shape and the
  SVG-relevant invariants (prices/pnl same length, prices sorted, breakevens
  inside the sampled window, max profit/loss = series extremes).
- `tests/test_backtest.py` — the backtest endpoint: determinism per seed, seed
  sensitivity, `years` clamping, and that the MC report + honesty notes are
  present.
- `tests/test_portfolio.py` — the add/check/close flow: clean adds vs the
  two-step warning preview, close moving a position to `closed_trades` and
  **linking calibration**, account-size rescaling, and Greeks scaling by qty.
- `tests/test_persistence.py` — round-trip across a fresh `DashboardAPI`
  instance, `--fresh` ignoring saved state, corrupt-file fallback, and
  persistence-off when no `state_dir` is given.
- `tests/test_market_data.py` — the market-data layer: provider selection,
  `AlpacaProvider` parsing against **canned JSON fixtures** (urllib mocked, no
  network) incl. retry-on-429, the spot_trend / iv_rank / expected_move /
  liquidity derivations, DemoProvider determinism, and the `/api/market`
  endpoint shape + error path + health source.
- `tests/test_smoke.py` — boots the real server on an OS-assigned port and hits
  it over a socket (page served, `/api/health` incl. `market_data`,
  `/api/phoenix`, `/api/strategies` returns cards, `/api/market/{symbol}`
  pre-fills, unknown route → 404).

## API contract

All bodies and responses are JSON. Errors return
`{"error": "...", "status": <code>}` with that HTTP status.

| Method | Path | Purpose |
|---|---|---|
| GET | `/` | The single-page UI |
| GET | `/api/health` | `{status, ai_mode:"live"\|"offline", claude_available, model, market_data:"alpaca"\|"demo", disclaimer, active_sessions}` |
| GET | `/api/meta` | Enum options: `{strategy_types[13], risk_profiles[3], biases[3]}` |
| GET | `/api/market/{symbol}` | Live market pre-fill for the Inputs form (see below) |
| POST | `/api/strategies` | Run a selection (see below) |
| POST | `/api/ask` | Multi-turn follow-up on a selection |
| POST | `/api/outcome` | Log a realized outcome → calibration learns |
| GET | `/api/payoff/{session_id}/{rec_index}` | Payoff-at-expiry curve for one recommendation (Phase 6a) |
| POST | `/api/backtest` | Run a synthetic backtest + MC gate (Phase 6b) |
| GET | `/api/portfolio` | Full serialized portfolio state + aggregates + suggestions (Phase 7) |
| POST | `/api/portfolio/positions` | Add a taken recommendation (two-step: preview warnings → confirm) |
| POST | `/api/portfolio/account` | Edit account size (rescales the risk budget) |
| POST | `/api/portfolio/close` | Close a position at an exit P&L → feeds calibration |
| GET | `/api/phoenix` | Raw `brain_state.json` (DESIGN §5.3 data source) |
| GET | `/api/phoenix/versions` | Version lineage list for the Versions panel |

### GET `/api/payoff/{session_id}/{rec_index}`

Rebuilds the payoff-at-expiry curve for a stored recommendation via
`curve_from_recommendation` (the same single source of truth as the card's
headline numbers), centred on the selection's spot:

```jsonc
{
  "session_id": "…", "rec_index": 0, "strategy": "bull_call_spread",
  "symbol": "SPY", "spot": 450.0, "entry_price": 4.97,
  "curve": {
    "prices": [ … ], "pnl": [ … ],           // parallel arrays, ~201 samples
    "breakevens": [454.97], "max_profit": 1753.42, "max_loss": -496.58,
    "unbounded_gain": false, "unbounded_loss": false
  },
  "disclaimer": "…"
}
```

The UI draws this as inline SVG: P/L line, zero axis, shaded profit/loss
regions, breakeven + current-spot markers, max-profit/loss annotations, and an
"unbounded →" arrow when a side is flagged.

### POST `/api/backtest`

```jsonc
// request (all but symbol have defaults)
{"symbol": "SPY", "years": 3, "seed": 7, "account_size": 100000,
 "entry_every_n_days": 21, "holding_days": 21, "bias": "neutral",
 "risk_profile": "moderate", "max_loss_dollars": 5000}
```

`years` is clamped to **1–5**. Bars come from `synthetic_bars(seed)` — the same
seed always yields the same series, so results are **deterministic per seed**.
Response carries `result` (stats, `equity_curve`, `trades`), the Monte-Carlo
gate `mc` (`accepted`, `ruin_probability`, `median_expectancy_r`, `reasons`),
and the engine's `notes` (honesty about the synthetic data and
intrinsic-value-at-expiry approximation). The request runs **without holding the
shared lock** (its own selector, no shared state) so long backtests never block
selection/calibration on other threads.

### Portfolio endpoints (Phase 7)

`POST /api/portfolio/positions` is **two-step**: `{session_id, rec_index, qty}`
returns `{"added": false, "warnings": [...]}` when `Portfolio.check` finds a
risk-budget / concentration / direction / expiry warning; resend with
`"confirm": true` to add anyway. Adding registers the prediction so the eventual
close feeds confidence calibration. `POST /api/portfolio/close`
`{index, exit_pnl}` records a `TradeOutcome` (same calibration loop as
`/api/outcome`) and moves the position to `closed_trades`. `GET /api/portfolio`
returns the full serialized state plus `aggregates` (net Greeks, budget used,
per-symbol/direction/expiry breakdowns) and `suggestions`.

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

## Persistence

The `QuantumAIBrain` state (calibration + knowledge, via `to_dict`/`from_dict`)
and the `Portfolio` are persisted to `data/state/` as JSON **on every
mutation** (recording an outcome, taking/closing a position, editing account
size). Writes are **atomic** (temp file + `os.replace`) and happen **under the
shared lock**, so a crash mid-write can never corrupt the state file.

- On boot the server loads `data/state/brain.json` and
  `data/state/portfolio.json` if present; a corrupt file falls back to a fresh
  instance rather than crashing.
- `--fresh` ignores any saved state and starts clean.
- `data/state/` is **git-ignored** (runtime data, not repo content).
- **Reasoning sessions stay in-memory** (they are cheap to recreate and hold a
  live `ReasoningSession`); after a restart, re-run a selection to get a fresh
  `session_id`. Persisted state is only the brain learning + the portfolio.

## Layout

```
nci-dashboard/
  nci_dashboard/
    __main__.py        # python3 -m nci_dashboard
    server.py          # stdlib http.server routing → DashboardAPI (+ --fresh)
    api.py             # transport-agnostic service layer (the testable core)
    state.py           # atomic JSON persistence (tmp + os.replace)
    market_data.py     # market-data providers (Alpaca / demo) for form pre-fill
    paths.py           # sys.path wiring + state-dir constants
    static/index.html  # self-contained single-page UI (inline CSS/JS)
  data/
    brain_state.json     # Phoenix brain state (seeded from the phoenix example)
    versions_index.json  # version lineage for the Versions panel
    state/               # runtime state (git-ignored): brain.json, portfolio.json
  tests/               # test_api / market_data / smoke / payoff / backtest /
                       # portfolio / persistence  (83 tests)
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
