# OptionScope Board of Directors — Minutes, Working Session 1

**Date:** 2026-07-12
**Directive:** Product Completion Directive v1.0 (`docs/OPTIONSCOPE_DIRECTIVE.md`)
**Attendees (all five seats, quorum present):**

| Seat | Member | Domain |
|---|---|---|
| 1 | Dr. Elena Voss | Master program developer — systems architecture |
| 2 | Prof. Adrian Kade | Master program developer — AI & learning systems |
| 3 | Victor Ashford | Options market-making & algo operator |
| 4 | Sana Qureshi | Volatility-arbitrage founder |
| 5 | Ray Delgado | Fintech product & business builder |

**Scope:** Decisions D1–D6 for the Active Analysis completion feature.
**Ground rule (read into the record by the chair):** every decision must be
implementable this week, stdlib-only, against the code as it exists today
(`nci-phase-4/nci_strategy_selector/*`, `nci-dashboard/nci_dashboard/api.py`).
No external pricing libraries. Honest labeling beats added sophistication.

---

## D1. Probability-of-profit methodology

**Code reality on the table:** `strategy_selector.build_recommendation` currently
sets `probability_profit = min(0.40 + fit_score * 0.15, 0.95)` — a linear map of
the fit score, unconnected to any price distribution. Meanwhile `payoff.py`
already prices legs under a Bachelier (normal) terminal distribution with
σ = `expected_move`, and the payoff curve already yields breakevens and
profitable regions. The distribution needed for an honest PoP is already in the
codebase; it is simply not being used for PoP.

### Debate

**Ashford (lead):** The current number is a fit score wearing a probability
costume — it would be laughed off any desk, and it is the single most dangerous
number on the card because users anchor on it. The fix is nearly free: PoP =
P(payoff at expiry > 0) under the *same* Bachelier distribution the entry price
already came from, computed as Φ-mass over the curve's profitable intervals.
Same model in, same model out — the premium and the probability can never
disagree. And expectancy must ship next to PoP, computed under the same
distribution, or a 95%-PoP short strangle will keep masquerading as "safe."

**Qureshi (co-lead):** I accept Bachelier for the binding number on internal-
consistency grounds, but I want the failure modes named on the card, not in a
docstring: the normal model puts mass below zero, has no skew, and understates
tails — it breaks hardest on long-dated, low-priced, and hard-to-borrow names.
I pushed for a lognormal cross-check as a second displayed number; if the two
models disagree by more than a few points, the user deserves to see the spread.

**Delgado:** Two probabilities on one card is how you teach a retail user to
trust neither. One PoP, clearly labeled "model estimate," with the derivation
one tap away — that passes the glance test. Put the lognormal cross-check
inside the derivation notes, not on the card face.

**Kade:** Provenance concern with the *old* field: `probability_profit` is
persisted in recommendation dicts and the offline template narrates it
("moderate-to-good probability"). Whatever we decide must replace the number at
the source, not overlay it in the UI, and the fallback/offline path must produce
the identical PoP — same function, no divergent code shape.

**Voss:** One source of truth: the PoP function lives next to `payoff_curve` in
the engine layer and is the only producer of the number, everywhere it appears.
No UI math. It must also handle the degenerate cases the curve already flags —
unbounded sides, zero-width profitable intervals, σ floor.

### VOTE
**5–0** for curve-derived Bachelier PoP as the single binding number, with the
lognormal cross-check relegated to derivation notes.
(Qureshi votes aye after her cross-check is guaranteed a place in the notes.)

### BINDING DECISION (D1)
Implement, in `nci-phase-4/nci_strategy_selector/payoff.py` (or a sibling
`probability.py` in the same package):

1. `pop_from_curve(curve: PayoffCurve, spot: float, sigma: float) -> PopEstimate`
   — PoP = Σ over each maximal interval `[a, b]` of the sampled curve where
   `pnl > 0` of `Φ((b − spot)/σ) − Φ((a − spot)/σ)`, using the curve's
   interpolated breakevens as interval edges and handling open-ended intervals
   with the curve's `unbounded_gain`/tail slopes (upper edge → 1.0 mass side,
   lower edge floored at spot = 0 mass under the normal, stated in notes).
   σ is the same `expected_move`-derived sigma used by `net_entry_price`
   (including the `max(expected_move, spot*0.02)` floor), so price and
   probability share one distribution.
2. `expectancy_from_curve(curve, spot, sigma) -> float` — E[P/L] as the
   discrete sum of `pnl(p_i)` weighted by normal CDF mass between grid
   midpoints, plus closed-form tail terms using the curve's outer slopes.
   Stdlib only (`math.erf`).
3. A lognormal cross-check PoP (same interval method, `ln S_T` normal with
   matched variance) computed and stored in the derivation notes ONLY — never
   on the card face.
4. `build_recommendation` replaces `0.40 + fit_score * 0.15` with the
   curve-derived PoP. The fit score remains what it is — a ranking score —
   and stops impersonating a probability.
5. Every PoP is delivered with a machine-readable label object:
   `{"model": "bachelier", "sigma": <$>, "horizon_days": <n>,
   "assumptions": ["at-expiry intrinsic", "no skew/fat tails",
   "no early exit"], "cross_check_lognormal": <float>}`.

### CONDITIONS (testable)
- C1.1 Put/call parity of the pricing layer is untouched (existing tests stay green).
- C1.2 For a long straddle and short straddle with identical strikes/σ,
  `pop(long) + pop(short) == 1.0` within grid tolerance (1e-6 on the shared breakevens).
- C1.3 PoP ∈ [0, 1] for all 13 strategies across a property sweep of spot ∈
  {5, 50, 500}, expected_move ∈ {1%, 5%, 20% of spot}.
- C1.4 Expectancy of any zero-cost symmetric structure at σ-consistent pricing
  is ≈ 0 within tolerance.
- C1.5 Offline and live paths call the same `pop_from_curve` (assert by
  construction: no second implementation exists in the repo).
- C1.6 The string `0.40 + fit_score` no longer exists in the codebase.

### DISSENT
None. Qureshi notes for the record: "The day this product touches real chains,
D1 gets reopened for an empirical-distribution option. Bachelier is honest for
demo-grade σ; it is not the end state."

---

## D2. Intent mapping (income / directional / volatility / hedge)

**Code reality on the table:** `StrategySelector.select_strategies` consumes
`UserPreferences` (bias, risk_profile, time_horizon) and scores against a
declared `strategy_db` with per-strategy attributes (`iv_preference`,
`time_decay`, `direction_profit`, `risk_level`). There is no intent concept.
The attributes needed to express all four intents already exist in the db.

### Debate

**Qureshi (co-lead):** The mapping must be a published table, not tuning buried
in score arithmetic. And it must respect the vol regime: income is a short-
premium business — running the income intent at iv_rank 20 without a warning is
selling cheap insurance and calling it yield. Volatility intent buying premium
at iv_rank 85 is the mirror error. Both must degrade with a visible warning,
never silently. Separately: `event_proximity_days=None` means *unknown*, not
*none* — short-premium intents must say "events unknown" when the field is null.

**Ashford:** Agreed on the table. One addition — the intent layer must not
mutate the selector's scoring internals. Filter and annotate on the declared
`strategy_db` attributes so anyone can read why an intent produced its list.
The strikes those intents produce come from `build_legs`' fixed 3%/5% offsets;
acceptable for now because it's deterministic and labeled, but the preset table
must record that widths are spot-fraction templates, not chain-derived.

**Kade:** The directional intent has a trap: if the user's bias is neutral and
we infer direction from `spot_trend`, that inference must be labeled "derived
from trend," or we've laundered a model signal into a user preference.

**Delgado:** Four intents, four verdict cards, each stating its preset in one
line of plain language ("Income = short-premium, positive-theta structures;
works best when IV is rich"). If a preset produces zero survivors after the
max-loss gate, the empty state must teach ("nothing fits within your $X limit
because…"), not apologize.

**Voss:** The preset is data, not code: one frozen constant, serialized into
every report, versioned when it changes. If the mapping ever changes, past
stored analyses must still show the preset they were run with.

### VOTE
**5–0** for a declared constant preset table with regime guards and labeled
inference.

### BINDING DECISION (D2)
Create `INTENT_PRESETS` as a frozen module-level constant in the new Active
Analysis module (see D6), with exactly this semantics — filters and warnings
operate on existing `strategy_db` attributes; the base selector's scoring is
NOT modified:

| Intent | prefs.bias | Eligible strategies (attribute filter) | Regime guard (warning, not block) |
|---|---|---|---|
| income | `"neutral"` (user's bias ignored, stated on card) | `time_decay == "positive"` | if `iv_rank < 50`: warn "IV not rich — premium is thin for income" |
| directional | user's bias if bullish/bearish; else sign of `spot_trend`, labeled `"derived from trend"` | `direction_profit in {"bullish","bearish"}` matching the resolved bias | if `abs(spot_trend) < 0.1` and bias was derived: warn "weak trend signal" |
| volatility | `"neutral"` | `direction_profit == "volatile"` | if `iv_rank > 70`: warn "buying premium in rich IV" |
| hedge | opposite of portfolio net-delta sign (`Portfolio.net_greeks()`); if book is flat, `"neutral"` with note "no book exposure to hedge" | defined-risk only: exclude `SHORT_STRADDLE`, `SHORT_STRANGLE`; require bounded `max_loss` (no `unbounded_loss`) | always show current net delta being hedged |

Plus two cross-intent rules (Qureshi rules, both mandatory):
1. **Event gate:** if `event_proximity_days is not None and <= 3`, every
   short-premium recommendation (`time_decay == "positive"`) carries the
   warning "known event in N days — short premium into events is a choice,
   never a default." If `event_proximity_days is None`, every intent card
   displays "events: unknown."
2. **Preset provenance:** the exact preset row used (as a dict) is embedded in
   each intent verdict; the stored analysis persists it verbatim.

The per-intent evaluation calls the existing `select_strategies` with the
preset-resolved `UserPreferences`, applies the attribute filter to its output,
then runs the existing `build_recommendation` + max-loss hard gate unchanged.

### CONDITIONS (testable)
- C2.1 Income preset never emits a `time_decay == "negative"` strategy;
  volatility preset only emits `direction_profit == "volatile"`; hedge preset
  never emits an `unbounded_loss` structure. (Property tests over random contexts.)
- C2.2 With `iv_rank = 20`, the income verdict contains the thin-premium
  warning; with `iv_rank = 85`, the volatility verdict contains the rich-IV warning.
- C2.3 With `event_proximity_days = 2`, every short-premium card carries the
  event warning; with `None`, every intent card carries "events: unknown."
- C2.4 A directional verdict on neutral user bias carries the
  `"derived from trend"` label.
- C2.5 `INTENT_PRESETS` serializes into every stored analysis and round-trips.

### DISSENT
None.

---

## D3. Learning boundary — autonomous vs gated

**Code reality on the table:** `ConfidenceCalibrator` is already bounded by
construction: factor clamped to `[0.5, 1.5]`, EMA α = 0.25, neutral below 3
samples, only ever touches `confidence_score`. `create_knowledge_version` and
`rollback_knowledge` (append-only) exist on `QuantumAIBrain` but nothing
automates them. There is no blacklisting mechanism.

### Debate

**Kade (lead):** The boundary writes itself from blast radius. Calibration is
safe to run autonomously *because of its existing clamps* — a factor bounded in
[0.5, 1.5] and neutral under 3 samples cannot destroy a ranking, only tilt it,
and it is exactly the "report 55% and be right 55%" mechanism I exist to defend.
Those clamps therefore stop being tuning constants and become contract: the
board freezes them. Knowledge-version promotion changes what the brain *cites*
— that is a claim, and claims need a human. Blacklisting is a user preference
wearing a learning costume; the system may recommend it, never do it.

**Delgado:** One requirement from the product side: when learning changes what
the user sees, the user must see the learning. If calibration re-ranked the
cards, the card says so — "adjusted ×0.82 from your 7 logged outcomes." That
transforms the same mechanism from spooky to sticky: it's the user teaching
their assistant, visibly.

**Ashford:** Then guard the input: calibration learns from `outcome.pnl > 0`,
and `record_outcome`/`close_position` accept whatever P&L the user types. Fine
— it's the user's own ledger — but a fat-fingered $1M outcome should be
confirmed before it becomes training data. Cheap sanity band, big honesty win.

**Voss:** Promotion needs a wire, not just a rule: a gated endpoint that shows
the version diff (what changed in `strategy_performance` / `user_learnings`)
and requires an explicit confirm, mirroring the two-step `add_position`
pattern already in `api.py`. Rollback stays append-only exactly as implemented.

### VOTE
**5–0** for the three-tier boundary with frozen calibration constants and
visible-diff promotion.

### BINDING DECISION (D3)
Three tiers, enforced in code:

1. **Autonomous (no confirmation):** `ConfidenceCalibrator.observe/adjust`
   exactly as implemented. The constants `FACTOR_MIN = 0.5`, `FACTOR_MAX = 1.5`,
   `EMA_ALPHA = 0.25`, `MIN_SAMPLES = 3` are hereby board-frozen: changing them
   requires a recorded board decision (assert them in a test).
2. **Gated (explicit user confirmation, two-step like `add_position`):**
   `create_knowledge_version` — the API returns a diff of
   `strategy_performance`, `user_learnings`, and calibration factors vs the
   parent version; promotion happens only on `confirm: true`. Strategy
   blacklisting (new, small): a user-maintained exclusion list stored with
   preferences; the system MAY surface "consider excluding X (0/5 wins)" as a
   suggestion but MUST NOT add to the list itself.
3. **Never automated:** deleting history, editing past outcomes, changing risk
   limits. Rollback remains append-only as implemented.

Disclosure rule: any Active Analysis card whose confidence was modified by a
non-neutral calibration factor displays `calibration ×F (n outcomes)`; any
card whose *rank position* changed relative to raw confidence ordering is
flagged "re-ranked by your outcome history."
Input guard: outcome logging with `abs(pnl)` > 5× the position's modeled
max loss requires a confirm flag before it enters calibration.

### CONDITIONS (testable)
- C3.1 A test asserts the four calibration constants at their frozen values.
- C3.2 `create_knowledge_version` via API without `confirm: true` returns the
  diff and does NOT mutate `knowledge.current_version`.
- C3.3 No code path adds to the blacklist except the explicit user endpoint.
- C3.4 An analysis run after 3+ logged outcomes for a strategy shows the
  `calibration ×F` disclosure and provably differs from the fresh-brain
  analysis (this is also directive acceptance criterion #3).
- C3.5 An outcome with `pnl` 6× modeled max loss is rejected without the
  confirm flag; with it, it is accepted and marked `"outlier_confirmed": true`.

### DISSENT
None.

---

## D4. Evaluation depth vs latency — backtest inside Active Analysis

**Code reality on the table:** `run_backtest` walks up to 5 years of synthetic
GBM bars and runs a 5000-path block bootstrap — seconds of work, deliberately
run *outside* the API lock today. The engine's own docstring and
`BACKTEST_HONESTY_NOTES` state that synthetic backtests "demonstrate the
engine, not an edge." `bars_from_csv` exists for real bars but nothing feeds it
from the dashboard yet. The directive's acceptance bar is "end-to-end in ≤ a
few seconds."

### Debate

**Voss (lead):** Latency budget first: four intent evaluations through the
selector and payoff engine are milliseconds; one AI synthesis call is the only
legitimately slow step. Putting a multi-second backtest plus 5000 MC paths
inline quadruples worst-case latency for evidence that doesn't change
intra-day. Cache it, stamp it, refresh it explicitly. And the cache read must
degrade gracefully: no cached run is a labeled empty state, never a blocker.

**Ashford:** I'd normally fight for evidence-rich inline — but look at what the
evidence *is*: synthetic GBM. Its honest role is engine demonstration, not
edge. I will not have a synthetic MC verdict recomputed fresh inside every
analysis, because freshness implies weight it hasn't earned. Cached, stamped
"synthetic," and — my condition — it must never move the PoP or the rankings.
Evidence chip, not input.

**Qureshi:** Supporting Victor with one sharpening: the moment a user loads
real bars via `bars_from_csv`, that backtest earns a different label
("historical CSV") and becomes worth showing prominently — same cache
mechanics, different badge. Build the label distinction in now.

**Delgado:** Cached is also the right product. "Run Active Analysis" must feel
instant or it won't get pressed twice. A stale-stamped chip with a one-click
refresh is more trustworthy than a spinner.

**Kade:** Condition on provenance: the cached artifact must persist the exact
plan and seed it was run with, so the chip can say what the evidence actually
is, and so a stored analysis citing it remains reproducible.

### VOTE
**5–0** for cached/on-demand. (Ashford, the seat most likely to dissent toward
inline depth, votes aye on the grounds that synthetic evidence has not earned
inline status; he reserves the right to reopen D4 when real-bar backtests land.)

### BINDING DECISION (D4)
Active Analysis NEVER runs a backtest inline. Implement:

1. A backtest evidence cache in the existing state dir: on every
   `run_backtest`, persist `{symbol, params (full plan + seed + years),
   result.stats, mc report, synthetic: true|false, as_of}` via the existing
   `atomic_write_json` (one file per symbol, latest run wins;
   append a compact entry to a per-symbol history list, append-only).
2. Active Analysis reads the cache for its symbol. Present: an evidence chip
   with win rate, expectancy, MC verdict, `as_of` timestamp, and the
   `synthetic` badge (or `historical CSV` when the run used `bars_from_csv`).
   Absent: the chip reads "no backtest evidence yet — run one" with a
   one-click trigger to the existing endpoint.
3. Backtest evidence is display-only in pass 3: it MUST NOT enter PoP,
   confidence, fit scores, or ranking. (Reopen only after real-bar evidence
   exists — recorded as future board business.)
4. Latency budget, enforced by test: Active Analysis on demo data, offline AI,
   completes in < 2 seconds; the only network call permitted in the whole
   pipeline is the single optional Claude synthesis call.

### CONDITIONS (testable)
- C4.1 An Active Analysis run performs zero calls into `BacktestEngine.run`
  and `validate` (assert via instrumentation/monkeypatch in tests).
- C4.2 Cache round-trip: run backtest → run analysis → chip carries matching
  `as_of`, stats, and `synthetic: true`.
- C4.3 With no cache file, analysis succeeds and the evidence field is an
  explicit labeled-absent state, not null-crash, not silence.
- C4.4 Offline end-to-end analysis wall time < 2s on demo data (timed test).
- C4.5 Deleting/corrupting the cache file mid-flight degrades to the absent
  state with a visible note (Voss's corrupt-state failure mode).

### DISSENT
None recorded. Ashford's reservation to reopen upon real-bar support is minuted.

---

## D5. Presentation of uncertainty — PoP, confidence, MC on one card

**Code reality on the table:** three numbers of different epistemic species
exist: PoP (post-D1: model-derived probability), `confidence_score`
(fit-derived, calibration-adjusted trust score), MC gate (`accepted` +
ruin/expectancy stats on synthetic paths). Today the UI could show all three
raw, and a retail user would average them in their head.

### Debate

**Delgado (lead):** Three numbers, three different species — probability,
trust, and evidence — and if they share a card without hierarchy the user will
blend them into one imaginary "score." My design: PoP is the *only* percentage
on the card face, wearing an "est." badge with its model named in six words.
Confidence is not a percentage — render it as a labeled level (Low/Moderate/
High) with the calibration disclosure from D3. MC is a badge with words, never
a number on the face. Every card ends with "what would change this call" — one
sentence from the synthesis. That's the glance test passed.

**Ashford:** Accepted, with my non-negotiable from D1: expectancy sits directly
beside PoP, same font size, signed dollars. "PoP 78% est. · Expected P/L
−$14" is the honest pair — high-PoP-negative-expectancy structures exist, and
the card must make that visible in one eye movement. Max loss vs the user's
limit stays on the face too; it's a hard gate, so show the gate.

**Kade:** Confidence-as-words is right — a second percentage would be laundering
a heuristic into a probability, the exact crime we just convicted PoP of. Two
conditions: the Low/Moderate/High thresholds are declared constants shipped in
`meta()` (no hidden bucketing), and the derivation notes are one tap away with
the full label object from D1, including the lognormal cross-check.

**Qureshi:** The face must also carry the tail when there is one: any
`unbounded_loss` structure shows "loss beyond window: UNBOUNDED" in the
max-loss slot, and short-premium cards show the event-gate warning from D2 in
the same visual weight as PoP. A tail note in a tooltip is a tail ignored.

**Voss:** Every element on that card maps to a named engine field — the panel
renders a `to_dict()` of the report, computes nothing. If a designer wants a
new number, they come back through this board.

### VOTE
**5–0** for the hierarchy: PoP + expectancy + max-loss-vs-limit on the face;
confidence as calibrated words; MC as labeled evidence badge; derivation one
tap away.

### BINDING DECISION (D5)
Card face (exactly these, all sourced from engine fields):
1. **PoP** — one percentage, "est." badge, model name inline
   ("Bachelier, σ = $EM"). From D1's `PopEstimate`.
2. **Expected P/L** — signed dollars from `expectancy_from_curve`, adjacent to
   PoP at equal visual weight.
3. **Max loss vs limit** — "max loss $X of your $Y limit"; renders
   "UNBOUNDED beyond window" when `unbounded_loss` is true.
4. **Confidence level** — word-rendered (Low < 0.45 ≤ Moderate < 0.70 ≤ High),
   thresholds published in `meta()`; carries the D3 calibration disclosure
   when factor ≠ 1.0.
5. **Evidence badge** — one of: `MC gate: PASSED (synthetic)`,
   `MC gate: FAILED (synthetic)`, `insufficient history`,
   `no backtest evidence yet`. Words, never a bare number on the face.
6. **Warnings strip** — D2 regime/event warnings, portfolio `check()`
   warnings, at equal visual weight to PoP.
7. **"What would change this call"** — one sentence from the brain synthesis.
8. Educational disclaimer on the panel (constraint #4).

Tap-through derivation panel: the full D1 label object (model, σ, horizon,
assumptions, lognormal cross-check), raw confidence + factor + sample count,
full MC report dict, and the intent preset row. UI computes nothing; the panel
is a pure rendering of `ActiveAnalysisReport.to_dict()` (D6).

### CONDITIONS (testable)
- C5.1 Exactly one percentage appears on the card face (render-layer test:
  the card template contains a single %-formatted field, PoP).
- C5.2 Confidence thresholds are served by `meta()` and used by the renderer
  (no literals in the page).
- C5.3 An `unbounded_loss` structure renders the UNBOUNDED string; a bounded
  one renders the dollar figure (snapshot tests both ways).
- C5.4 A card with calibration factor ≠ 1.0 renders the disclosure; factor
  1.0 renders none.
- C5.5 Every rendered field name on the card exists as a key in
  `ActiveAnalysisReport.to_dict()` (contract test).

### DISSENT
None.

---

## D6. Architecture — where Active Analysis lives, and its contract

**Code reality on the table:** engines live in `nci-phase-4/
nci_strategy_selector` (pure, stdlib, no I/O beyond explicit CSV); the
dashboard's `DashboardAPI` is a transport-agnostic service layer holding the
lock, the brain, the portfolio, persistence, and the selection/session store.
`server.py` is a thin adapter. Every existing engine speaks dataclasses with
`to_dict`/`from_dict`.

### Debate

**Voss (lead):** The orchestration is domain logic — which engines run, in what
order, producing a versioned report — so it belongs in the engine package where
it can be unit-tested without a server: a new module
`nci_strategy_selector/active_analysis.py`. The dashboard contributes exactly
what only it has: the market provider, the shared brain with its lock, the
portfolio, and persistence. The contract is a dataclass or it isn't designed;
`ActiveAnalysisReport` with full dict round-trip, an `analysis_id`, and a
`schema_version` field from day one, because stored analyses will outlive the
first schema. Failure modes: market fetch fails → analysis proceeds on the
caller-provided context with `data_source` labeled; AI call fails → offline
synthesis with `model_used: "fallback"`; a report that can't be persisted is
still returned (persistence failure is a warning, not an error).

**Kade:** The module boundary is also the learning boundary: `active_analysis.py`
receives the brain and portfolio as arguments — it never constructs them — so
the offline test path exercises the identical orchestration code as production.
One Claude call per analysis, fed the complete curated bundle; four separate
calls would multiply cost and let per-intent narratives contradict each other.
The stored-analysis history is what lets the brain cite its own track record —
append-only, like everything else the brain remembers.

**Ashford:** Wherever it lives, one rule: the orchestrator composes engine
outputs; it computes no financial number itself. If I find a stray
`* 100` in the orchestration layer that isn't in an engine, I'm calling the
meeting back.

**Delgado:** Contract must carry everything D5 renders — if the UI has to
compute or fetch anything beyond this dict plus the payoff-curve endpoint,
the contract failed. And the endpoint slots into `server.py` exactly like
its siblings; no new transport concepts this week.

### VOTE
**5–0** for engine-layer orchestration module + thin dashboard endpoint.

### BINDING DECISION (D6)
1. New module `nci-phase-4/nci_strategy_selector/active_analysis.py` exposing:
   ```
   run_active_analysis(
       context: MarketContext,
       base_prefs: UserPreferences,
       brain: QuantumAIBrain,
       portfolio: Portfolio,
       backtest_evidence: dict | None,   # D4 cache payload, pre-read by caller
       use_claude: bool = True,
   ) -> ActiveAnalysisReport
   ```
   plus dataclasses `IntentVerdict` (intent, preset row used, ordered enriched
   recommendations — each with PoP estimate object, expectancy, calibration
   disclosure, warnings, rejected-for-risk list) and `ActiveAnalysisReport`
   (schema_version, analysis_id, symbol, as_of, data_source label, context
   echo, four IntentVerdicts, portfolio impact — `check()` warnings + current
   aggregates, backtest evidence or labeled-absent, ai_synthesis text,
   model_used, disclaimer). Both with `to_dict`/`from_dict` round-trip.
   `INTENT_PRESETS` (D2) lives here. The module performs no I/O and
   constructs no brain/portfolio — pure composition of existing engines.
2. `DashboardAPI.active_analysis(payload)` in `nci-dashboard/nci_dashboard/api.py`:
   parses input with the existing `_parse_context`/`_parse_prefs`, reads the
   D4 cache, calls `run_active_analysis` under `self._lock` (calibration
   reads shared state), registers a reasoning session for Q&A handoff
   (existing `start_reasoning_session` pattern), appends the report to an
   append-only `analyses` history in the state dir via `atomic_write_json`,
   and returns `report.to_dict()` + `session_id`. `server.py` gains one
   route, thin as its siblings.
3. Exactly one Claude synthesis call per analysis (the full curated bundle in
   one prompt); offline fallback produces the same report shape via the
   template path.
4. Failure modes per Voss: provider-down → proceed with labeled caller
   context; AI-down → fallback synthesis, `model_used: "fallback"`;
   persistence-write failure → report still returned with a
   `persistence_warning` field.

### CONDITIONS (testable)
- C6.1 `ActiveAnalysisReport.from_dict(report.to_dict())` round-trips equal.
- C6.2 The orchestration module imports no dashboard code and performs no
  file/network I/O (import-graph + monkeypatch test).
- C6.3 Offline (`use_claude=False`, no key) produces a complete report with
  all four verdicts — same shape as live (schema-diff test).
- C6.4 Every dollar/probability field in the report is traceable to an engine
  function (no arithmetic on financial quantities in `active_analysis.py`
  beyond composition — enforced by review checklist + grep for multiplier
  literals).
- C6.5 Two analyses in the same second get distinct `analysis_id`s
  (uuid suffix, mirroring `create_knowledge_version`).
- C6.6 The suite stays green; orchestration layer has full test coverage
  (directive acceptance criterion #4).

### DISSENT
None.

---

## Build order for pass 3 (board-agreed sequencing)

Rationale: honest numbers first (everything downstream displays them), contract
before presentation, UI last so it renders finished truth rather than
placeholder math.

1. **D1 — PoP + expectancy engine** in the strategy-selector package; replace
   the fit-score PoP at the source; tests C1.1–C1.6. *(Everything else
   displays these numbers; nothing may proceed on the old heuristic.)*
2. **D2 — `INTENT_PRESETS` + intent evaluation** (filters, regime guards,
   event gate); tests C2.1–C2.5.
3. **D6 — `active_analysis.py` orchestrator + report contract**, composing
   D1/D2 outputs, calibration disclosure (D3 display fields), portfolio
   impact; tests C6.1–C6.6.
4. **D4 — backtest evidence cache** (write on `run_backtest`, read in
   analysis, labeled-absent state); tests C4.1–C4.5.
5. **D3 — learning-boundary hardening**: frozen-constants test, gated
   version-promotion endpoint with diff, blacklist store, outlier-outcome
   guard; tests C3.1–C3.5.
6. **D6.2 — dashboard endpoint + persistence of analyses** + Q&A session
   handoff.
7. **D5 — Active Analysis panel** rendering `ActiveAnalysisReport.to_dict()`
   verbatim per the card hierarchy; tests C5.1–C5.5.
8. **Acceptance pass** — the directive's five acceptance criteria run
   end-to-end (including the < 2s offline latency test and the
   calibration-alters-analysis proof), full suite green, then board sign-off
   on the implementation is appended to these minutes.

---

## Disclaimer

OptionScope is **educational analysis tooling — not investment advice**. Every
probability, P/L figure, and verdict discussed in these minutes is a model
output carrying labeled assumptions. The board signs off on software design —
never on trades. All five board personas are fictional composites serving as
design-review roles.

*Minutes recorded 2026-07-12. Adopted 5–0 on all six decisions; reservations
by Ashford (D4 reopening upon real-bar support) and Qureshi (D1 reopening upon
real-chain data) entered into the record as future board business.*
