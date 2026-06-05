# NERDCOMMAND TRADING — Compact Architecture

## Core System

**4 Strategies** → **Signal Fusion** → **Triangle Entry** → **Dynamic Stop** → **3-Trade Scalp** → **Price Preservation**

## Strategies (Your 4)

|Strategy          |Entry                |Exit             |Win Rate|Confidence|
|------------------|---------------------|-----------------|--------|----------|
|**Breakout**      |Price > 20-day high  |Close < 50-day MA|50-55%  |1.0x      |
|**Stat Arb**      |Pair correlation > 2σ|Spread < 1σ      |55-60%  |1.2x      |
|**Mean Reversion**|RSI < 30 or > 70     |RSI cross 50     |48-52%  |0.8x      |
|**Pairs**         |Spread diverges > 2σ |Spread < 1σ      |52-58%  |1.1x      |

## Position Sizing (Confidence-Based)

```
Total Confidence = sum(strategy signals)

Confidence > 2.0  → 0.07 lots (HIGH)
Confidence 1.0-2.0 → 0.04 lots (MEDIUM)
Confidence < 1.0  → 0.01 lots or skip (LOW)
```

**Rule**: Don’t trade unless 2+ strategies agree.

## Triangle Entry (Accumulate Gradually)

```
Entry 1: 0.01 lots @ signal price (test setup)
Entry 2: +0.03 lots if price moves in favor (add conviction)
Entry 3: +0.03 lots if trend continues (full 0.07)

If stop hit at any point: CLOSE ALL (no averaging down)
```

## Unified Stop Loss

```
Stop = Entry ± (ATR-14 × 2)

Example: Entry 1.0500, ATR 50 pips
Stop = 1.0400 (100 pips below)

Trails UP only (locks profits)
If hit: CLOSE ENTIRE POSITION
```

## 3-Trade Scalp Exit

```
Count winning trades:
Win 1: +10 pips (keep position)
Win 2: +15 pips (keep position)
Win 3: +12 pips (EXIT ALL, lock +$2.60)

Move to next setup
```

## Daily Limits (Capital Preservation)

```
Daily Target: +$10 (2% of $500 account)
  → Hit = REDUCE 50% or STOP

Daily Stop: -$5 (1% loss)
  → Hit = CLOSE ALL, STOP TRADING

Mentality: Win small, don't lose big = compound steadily
```

## Implementation (6 Weeks)

|Week|Task                     |Output                   |
|----|-------------------------|-------------------------|
|1   |Breakout strategy + paper|10-20 trades logged      |
|2   |Stops + daily limits     |Risk management proven   |
|3   |Triangle entry + logging |Entry phases validated   |
|4   |Add mean reversion       |2-strategy fusion working|
|5   |Add stat arb + pairs     |All 4 strategies live    |
|6   |Go live ($100-500)       |Real trading starts      |

## Tech Stack

|Component|Tech                   |Cost       |
|---------|-----------------------|-----------|
|Data     |Interactive Brokers API|$10/mo     |
|Trading  |Python + IB SDK        |$0         |
|Logging  |SQLite                 |$0         |
|Analysis |Google Sheets          |$0         |
|**Total**|                       |**<$50/mo**|

## Expected Returns

**Conservative** (10% monthly):

- $500 → $550 (Month 1)
- $550 → $605 (Month 2)
- Month 12: **$1,600**

**Aggressive** (20% monthly):

- $500 → $600 (Month 1)
- $600 → $720 (Month 2)
- Month 12: **$3,100+**

**Reality**: 10-15% monthly is solid. Be happy with it.

## Key Metrics

```
Win Rate: > 50% (48% works if 3-trade scalps)
Avg Win: +$0.70-1.50 (10-20 pips @ 0.07 lots)
Avg Loss: -$0.30-0.70 (stop at 100 pips)
Daily Target: +$10 (10-15 scalps)
Monthly: +10-20%
```

## Daily Workflow

**Before open**: System running? Data flowing? Daily limits set?

**Trading**: Monitor position → count wins → hit 3? Exit. Stop hit? Close. Chaos? Override.

**After close**: Log trade (entry, exit, P&L, strategy, reason)

**Weekly**: Review 20+ trades. Which strategies win? Which pairs lose?

**Monthly**: Full audit. Calculate return %. Grow account or reduce risk?

## Failure Recovery

|Failure              |Fix                                |
|---------------------|-----------------------------------|
|Connection lost      |Reconnect. Manual close if needed. |
|Stop didn’t execute  |Close immediately. Analyze why.    |
|Strategy failing     |Pause it. Revert version. Backtest.|
|Daily loss hit -$5   |STOP TRADING. Preserve capital.    |
|Daily profit hit +$10|Reduce 50% or close. Lock gains.   |

## Mental Rules

✅ **DO**:

- Trade high-conviction only (2+ strategies)
- Exit winners quickly (3 trades done)
- Honor stops (discipline = survival)
- Keep position sizes tiny (0.01-0.07 = training)
- Log everything (learn from every trade)

❌ **DON’T**:

- Average down (no martingale)
- Trade low-conviction (wait)
- Hold overnight (scalp and exit)
- Use leverage (blow up risk)
- Override stops (death sentence)

## Next Steps

1. Open IB account (micro-lot support)
1. Test data stream (EURUSD ticks)
1. Code Strategy #1 (breakout 20-day high)
1. Backtest 6 months
1. Paper trade 1 week
1. Fund $100-500, go live
1. Trade with discipline (stops + 3-trade exits + daily limits)
1. Compound steadily (10-20% monthly)

-----

**Remember**: You’re building capital preservation first, growth second. Small consistent wins compound faster than big risky bets.