# Driips Opening-Session Strategy — Specification

This document is the normative rule set. The code in `src/` implements it;
where prose and code disagree, this specification is the bug tracker's
source of truth. All times are America/New_York. All levels are computed
from 1-minute bars. The reference instrument is the Nasdaq-100 E-mini
future (tick 0.25); parameter defaults below are sized for it.

## 1. Hypothesis

In the first minutes of the US equity cash session, resting stop orders
cluster just beyond the early session extremes. An opening push that runs
those stops and then fails — confirmed by a close back through the level
that was run — frequently marks the session's directional low or high.
The strategy positions for the reversion move on a pullback, targeting
the opposite extreme of the developing session range.

## 2. Session windows

2.1. **Entry window:** new positions may be initiated from 09:30:00 to
     11:00:00 inclusive.
2.2. **Management window:** open positions are managed until 16:00:00;
     anything still open at the session close is exited at the last
     1-minute close.
2.3. A session is skipped entirely if it has fewer than 10 bars in the
     entry window (holiday half-days, data gaps).

## 3. Structure tracking

3.1. **Working pivots:** a bar is a pivot high (low) if its high (low) is
     the extreme of the 5-bar window centered on it (lookback `k = 2`).
     Only the most recent pivot high and pivot low are kept.
3.2. **Stop-run:** a stop-run above is recorded when a bar's high exceeds
     the working pivot high by more than 2 ticks; a stop-run below when a
     bar's low undercuts the working pivot low by more than 2 ticks. The
     level recorded is the pivot that was run.
3.3. **Structure-shift confirmation:** after a stop-run below, a 1-minute
     close back **above** the run level confirms a bullish shift and sets
     session bias = long. After a stop-run above, a close back **below**
     the run level sets bias = short. The first confirmation fixes the
     bias; it is not re-evaluated unless rule 6.3 resets the chain.

## 4. Entry

4.1. **Trigger — price-imbalance zone:** a three-bar gap in the bias
     direction. Bullish: bar *i*'s low is above bar *i−2*'s high by at
     least 4 ticks; bearish: mirrored. The zone spans from the older
     bar's extreme to the newer bar's extreme.
4.2. **Entry price — zone midpoint:** a limit order at the midpoint of
     the zone, assumed filled at that price if the zone forms (fill
     realism is addressed in the cost model, rule 8).
4.3. **Value-zone filter:** the entry midpoint must sit in the favorable
     half of the session range so far — at or below the range midpoint
     for longs, at or above it for shorts.
4.4. **Reward filter:** the first target (rule 6.1) must be at least
     1.0 R from entry, measured against the initial stop.

## 5. Stop placement

5.1. The stop is placed beyond the stop-run extreme: 4 ticks below the
     run level for longs (above for shorts).
5.2. **Volatility floor:** the stop must be at least `0.5 × ATR(14)` from
     entry (ATR on the session's 1-minute bars). The wider of 5.1 and
     5.2 governs.

## 6. Targets and trade management

6.1. **Targets:** the session range so far is divided into quartiles.
     TP1 is the nearest quartile level beyond entry; TP2 — the runner's
     target — is the session-range extreme opposite the entry (the prior
     range extreme the reversion is drawn toward).
6.2. **Scale-out:** 50% of the position is closed at TP1 and the stop
     moves to breakeven. The runner exits at TP2, at breakeven, or at
     the session close, whichever comes first.
6.3. **Sequencing (base variant):** entry #2 is not permitted until
     entry #1 resolves. If entry #1 reaches TP1, the base variant is
     done for the session — continuation entries after a success are
     exclusively the trend variant's rules (section 7). If entry #1 is
     stopped out, the chain resets — a new stop-run and a new
     structure-shift confirmation are required — and one further
     attempt is permitted.

## 7. Re-entry — trend-continuation variant (validated configuration)

7.1. Up to **3 entries** per session in total.
7.2. A re-entry is allowed only while entry #1's **runner is alive**:
     its breakeven level has not been touched after TP1 sequencing began
     and TP2 has not traded. A live runner is the operational definition
     of "trend intact".
7.3. Re-entries must be in the session bias direction and pass every
     filter in section 4.
7.4. When the runner dies — breakeven touch or TP2 — the session is
     done: no further entries that day.

## 8. Costs

8.1. Commission: 0.225 points per round turn (≈ $4.50 on NQ at $20/pt).
8.2. Slippage: 0.5 points per round turn, a deliberately conservative
     allowance for limit-order queue position at the zone midpoint and
     market-order exits.
8.3. Costs are converted to R via the trade's initial stop distance and
     deducted once per trade. Gross figures are reported alongside net.

## 9. Risk

9.1. Risk per trade is 1R — a fixed fraction of account equity, set by
     the initial stop distance. The backtest accounts in R; position
     sizing to contracts is the deployer's mapping of R to currency.
9.2. Maximum concurrent exposure: 3 entries (variant, rule 7.1) or the
     base sequencing cap (rule 6.3), all in the same direction by
     construction.

## 10. Data requirements

10.1. 1-minute OHLCV bars, timestamps tz-aware America/New_York,
      covering at least 09:30–16:00 each session (see `data/README.md`).
10.2. The engine evaluates intrabar touch priority conservatively: on a
      bar where both stop and target ranges are touched, the stop is
      assumed filled first.

## Parameter table

| Parameter | Default | Rule |
|---|---|---|
| `swing_lookback` | 2 | 3.1 |
| `stop_run_buffer_ticks` | 2 | 3.2 |
| `gap_min_ticks` | 4 | 4.1 |
| `require_value_zone` | True | 4.3 |
| `tp1_min_rr` | 1.0 | 4.4 |
| `stop_buffer_ticks` | 4 | 5.1 |
| `min_stop_atr` | 0.5 | 5.2 |
| `atr_period` | 14 | 5.2 |
| `tick` | 0.25 | — |
| `commission_pts` | 0.225 | 8.1 |
| `slippage_pts` | 0.5 | 8.2 |
| `entry_start` / `entry_end` | 09:30 / 11:00 | 2.1 |
| `session_end` | 16:00 | 2.2 |
| `max_trades` (caller argument) | 3 | 7.1 |
