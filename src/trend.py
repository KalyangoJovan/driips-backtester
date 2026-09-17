"""Trend-continuation variant of the Driips opening-session engine.

Extends the base engine with disciplined re-entries:

- A re-entry is allowed ONLY while entry #1's runner is still alive —
  i.e. the runner has not returned to breakeven and has not reached its
  final target. A live runner is the working definition of "trend intact".
- The trigger is any new price-imbalance zone forming in the established
  bias direction, subject to the same value-zone and reward filters.
- Entries are capped at ``max_trades`` per session (3 in the validated
  configuration) and restricted to the entry window.
- Once the runner dies (breakeven touch or final target), the session is
  done: no further entries.

Only the entry-gating loop differs from the base engine; stop-run
detection, structure-shift confirmation, zone construction, and trade
resolution are the shared primitives from ``engine``.
"""
import numpy as np
import pandas as pd
from dataclasses import asdict

from .engine import Params, Trade, _atr, _pivots, _resolve_trades, summarize_trades


def run_session_trend(day_df, p: Params, date_str, entry_end_idx,
                      max_trades: int = 3):
    """Run one session with trend-continuation re-entry rules."""
    df = day_df.reset_index(drop=True)
    if len(df) < 10:
        return []
    buf = p.stop_run_buffer_ticks * p.tick
    atr = _atr(df, p.atr_period).values
    ph, pl = _pivots(df, p.swing_lookback)
    h, l, c = (df[x].values for x in ("high", "low", "close"))

    last_pivot_high = last_pivot_low = np.nan
    run_above = run_below = np.nan
    shift_confirmed = False
    bias = 0
    trades = []
    count = 0
    runner_alive = False
    runner_dir = 0

    for i in range(1, entry_end_idx + 1):
        if ph[i]:
            last_pivot_high = h[i]
        if pl[i]:
            last_pivot_low = l[i]
        if not np.isnan(last_pivot_high) and h[i] > last_pivot_high + buf:
            run_above = last_pivot_high
        if not np.isnan(last_pivot_low) and l[i] < last_pivot_low - buf:
            run_below = last_pivot_low

        # Is entry #1's runner still alive? It dies on a breakeven touch
        # (trend broke) or when its final target trades (trend complete).
        if runner_alive:
            t0 = trades[0]
            if runner_dir == 1:
                if l[i] <= t0.entry:
                    runner_alive = False
                elif h[i] >= t0.tp2:
                    runner_alive = False
            else:
                if h[i] >= t0.entry:
                    runner_alive = False
                elif l[i] <= t0.tp2:
                    runner_alive = False

        if not shift_confirmed and not np.isnan(run_below) and c[i] > run_below:
            shift_confirmed, bias = True, 1
        elif not shift_confirmed and not np.isnan(run_above) and c[i] < run_above:
            shift_confirmed, bias = True, -1

        bull_gap = i >= 2 and l[i] > h[i - 2] and (l[i] - h[i - 2]) >= p.gap_min_ticks * p.tick
        bear_gap = i >= 2 and h[i] < l[i - 2] and (l[i - 2] - h[i]) >= p.gap_min_ticks * p.tick
        gap_in_bias = (bias == 1 and bull_gap) or (bias == -1 and bear_gap)

        # Entry gate: first entry as normal; continuation entries only
        # while the runner is alive and in the same direction.
        allow = False
        if gap_in_bias:
            if count == 0:
                allow = True
            elif count < max_trades and runner_alive and bias == runner_dir:
                allow = True
        if allow:
            top = l[i] if bias == 1 else l[i - 2]
            bot = h[i - 2] if bias == 1 else h[i]
            zone_mid = (top + bot) / 2
            sess_hi, sess_lo = h[:i + 1].max(), l[:i + 1].min()
            range_mid = (sess_hi + sess_lo) / 2
            value_ok = (not p.require_value_zone) or (
                zone_mid <= range_mid if bias == 1 else zone_mid >= range_mid)
            atr_now = atr[i] if not np.isnan(atr[i]) else (sess_hi - sess_lo) * 0.1
            floor = p.min_stop_atr * atr_now
            sbuf = p.stop_buffer_ticks * p.tick
            if bias == 1:
                run_stop = (run_below - sbuf) if not np.isnan(run_below) else (bot - sbuf)
                stop = min(run_stop, zone_mid - floor)
            else:
                run_stop = (run_above + sbuf) if not np.isnan(run_above) else (top + sbuf)
                stop = max(run_stop, zone_mid + floor)
            quartiles = [sess_lo + (sess_hi - sess_lo) * q for q in (0.25, 0.5, 0.75)]
            if bias == 1:
                ups = [x for x in quartiles + [sess_hi] if x > zone_mid]
                tp1 = min(ups) if ups else sess_hi
                tp2 = sess_hi
            else:
                dns = [x for x in quartiles + [sess_lo] if x < zone_mid]
                tp1 = max(dns) if dns else sess_lo
                tp2 = sess_lo
            risk = abs(zone_mid - stop)
            tp1_rr = abs(tp1 - zone_mid) / risk if risk > 0 else 0
            if value_ok and risk > 0 and tp1_rr >= p.tp1_min_rr:
                count += 1
                t = Trade(date_str, bias, zone_mid, stop, tp1, tp2,
                          n=count, entry_bar=i)
                trades.append(t)
                if count == 1:
                    runner_alive = True
                    runner_dir = bias
                if count >= max_trades:
                    break

    return _resolve_trades(trades, df, p)


def backtest_trend(df, p: Params, max_trades: int = 3):
    """Run the trend-continuation engine over every session in ``df``."""
    all_trades = []
    for day, day_df in df.groupby(df.index.normalize()):
        window = day_df.between_time(p.entry_start, p.entry_end)
        session = day_df.between_time(p.entry_start, p.session_end)
        if len(window) < 10:
            continue
        all_trades += run_session_trend(session, p, str(day.date()),
                                        len(window) - 1, max_trades)
    tdf = pd.DataFrame([asdict(t) for t in all_trades])
    return tdf, summarize_trades(tdf)
