"""Driips opening-session engine.

Backtests an opening-session stop-run reversion strategy on 1-minute bars:

1. Track working swing pivots inside the session.
2. Detect a stop-run: price trades through a prior pivot by a buffer,
   then fails to hold beyond it.
3. Require a structure-shift confirmation: a close back through the level
   that was run, which fixes the session bias.
4. Enter at the midpoint of a price-imbalance zone (a three-bar gap)
   that forms in the bias direction, subject to a value-zone filter.
5. Stop beyond the run extreme; targets at session-range quartiles with
   the runner aimed at the prior range extreme.

All results are reported in R (multiples of the initial per-trade risk).
Costs (commission + slippage) are converted to R per trade and deducted
from the net figures; gross figures are kept alongside.

See ``spec/strategy_spec.md`` for the full numbered rule set.
"""
from dataclasses import dataclass, asdict

import numpy as np
import pandas as pd

NY = "America/New_York"


@dataclass
class Params:
    """Strategy and cost parameters (defaults sized for NQ futures)."""

    swing_lookback: int = 2            # pivot fractal half-width, bars
    stop_run_buffer_ticks: int = 2     # penetration needed to count as a stop-run
    atr_period: int = 14
    gap_min_ticks: int = 4             # minimum size of a price-imbalance zone
    require_value_zone: bool = True    # longs only in lower half of session range
    stop_buffer_ticks: int = 4         # stop placed this far beyond the run extreme
    tp1_min_rr: float = 1.0            # first target must be at least this many R
    min_stop_atr: float = 0.5          # volatility floor on stop distance
    tick: float = 0.25
    commission_pts: float = 0.225      # round-turn commission, in points
    slippage_pts: float = 0.5          # round-turn slippage assumption, in points
    entry_start: str = "09:30"         # session window: entries allowed
    entry_end: str = "11:00"
    session_end: str = "16:00"         # runner managed until here


@dataclass
class Trade:
    date: str
    direction: int          # +1 long, -1 short
    entry: float
    stop: float
    tp1: float
    tp2: float
    outcome: str = "open"   # full | tp1_only | loss | scratch
    r: float = 0.0          # net R, after costs
    r_gross: float = 0.0    # gross R, before costs
    n: int = 1              # entry number within the session
    entry_bar: int = 0


def _atr(df, n):
    h, l, c = df["high"], df["low"], df["close"]
    pc = c.shift(1)
    tr = pd.concat([h - l, (h - pc).abs(), (l - pc).abs()], axis=1).max(axis=1)
    return tr.rolling(n, min_periods=1).mean()


def _pivots(df, k):
    """Fractal swing pivots: bar i is a pivot high/low if it is the extreme
    of the window [i-k, i+k]."""
    hi = df["high"].values
    lo = df["low"].values
    n = len(df)
    ph = np.zeros(n, bool)
    pl = np.zeros(n, bool)
    for i in range(k, n - k):
        if hi[i] == max(hi[i - k:i + k + 1]):
            ph[i] = True
        if lo[i] == min(lo[i - k:i + k + 1]):
            pl[i] = True
    return ph, pl


def _max_dd(equity):
    if len(equity) == 0:
        return 0.0
    peak = equity.cummax()
    return float((equity - peak).min())


def _resolve_trades(trades, df, p: Params):
    """Walk each trade forward bar by bar and settle it.

    Management: 50% off at TP1 and stop moved to breakeven; the runner
    exits at TP2, at breakeven, or at the session close. Costs are one
    round turn per trade, converted to R via the initial stop distance.
    """
    h, l, c = (df[x].values for x in ("high", "low", "close"))
    cost_pts = p.commission_pts + p.slippage_pts
    for t in trades:
        risk = abs(t.entry - t.stop)
        if risk <= 0:
            t.outcome, t.r, t.r_gross = "scratch", 0.0, 0.0
            continue
        r_tp1 = abs(t.tp1 - t.entry) / risk
        r_tp2 = abs(t.tp2 - t.entry) / risk
        cost_r = cost_pts / risk
        d = t.direction

        # Phase 1: stop or first target, whichever is touched first.
        phase1 = None
        idx_tp1 = None
        for j in range(t.entry_bar + 1, len(df)):
            if d == 1:
                if l[j] <= t.stop:
                    phase1 = "loss"; break
                if h[j] >= t.tp1:
                    phase1 = "tp1"; idx_tp1 = j; break
            else:
                if h[j] >= t.stop:
                    phase1 = "loss"; break
                if l[j] <= t.tp1:
                    phase1 = "tp1"; idx_tp1 = j; break
        if phase1 == "loss":
            t.outcome = "loss"
            t.r_gross = -1.0
            t.r = round(-1.0 - cost_r, 3)
            continue
        if phase1 is None:
            # Neither side touched by the session close: flat exit.
            t.outcome = "scratch"
            t.r_gross = 0.0
            t.r = round(-cost_r, 3)
            continue

        # Phase 2: runner to TP2, breakeven, or session close.
        first_half_gross = 0.5 * r_tp1
        runner = None
        for j in range(idx_tp1 + 1, len(df)):
            if d == 1:
                if l[j] <= t.entry:
                    runner = "be"; break
                if h[j] >= t.tp2:
                    runner = "tp2"; break
            else:
                if h[j] >= t.entry:
                    runner = "be"; break
                if l[j] <= t.tp2:
                    runner = "tp2"; break
        if runner == "tp2":
            second_half = 0.5 * r_tp2
            t.outcome = "full"
        elif runner == "be":
            second_half = 0.0
            t.outcome = "tp1_only"
        else:
            last = c[-1]
            second_half = 0.5 * ((last - t.entry) * d / risk)
            t.outcome = "tp1_only"
        t.r_gross = round(first_half_gross + second_half, 3)
        t.r = round(first_half_gross + second_half - cost_r, 3)
    return trades


def run_session(day_df, p: Params, date_str, entry_end_idx=None,
                max_trades: int = 3):
    """Run the gate chain over one session's bars.

    ``day_df`` covers entry window through session end; ``entry_end_idx``
    is the last bar index on which a new entry may trigger. Returns the
    session's settled trades.
    """
    df = day_df.reset_index(drop=True)
    if len(df) < 10:
        return []
    if entry_end_idx is None:
        entry_end_idx = len(df) - 1
    buf = p.stop_run_buffer_ticks * p.tick
    atr = _atr(df, p.atr_period).values
    ph, pl = _pivots(df, p.swing_lookback)
    h, l, c = (df[x].values for x in ("high", "low", "close"))

    last_pivot_high = last_pivot_low = np.nan
    run_above = run_below = np.nan       # pivot levels that were run
    shift_confirmed = False
    bias = 0
    trades = []
    first_trade = None
    await_first_result = False
    count = 0

    for i in range(1, entry_end_idx + 1):
        if ph[i]:
            last_pivot_high = h[i]
        if pl[i]:
            last_pivot_low = l[i]
        if not np.isnan(last_pivot_high) and h[i] > last_pivot_high + buf:
            run_above = last_pivot_high
        if not np.isnan(last_pivot_low) and l[i] < last_pivot_low - buf:
            run_below = last_pivot_low

        # Entry #1 must resolve before anything else can happen: reaching
        # TP1 closes the session for new entries (spec 6.3 — continuation
        # after a success belongs to the trend variant), while a stop-out
        # resets the whole chain so a fresh stop-run and confirmation can
        # unlock one further attempt.
        if await_first_result and first_trade is not None:
            if first_trade.direction == 1:
                if h[i] >= first_trade.tp1:
                    await_first_result = False; count = 2
                elif l[i] <= first_trade.stop:
                    await_first_result = False; shift_confirmed = False
                    bias = 0; run_above = run_below = np.nan
            else:
                if l[i] <= first_trade.tp1:
                    await_first_result = False; count = 2
                elif h[i] >= first_trade.stop:
                    await_first_result = False; shift_confirmed = False
                    bias = 0; run_above = run_below = np.nan

        # Structure-shift confirmation: a close back through the level
        # that was run fixes the session bias.
        if not shift_confirmed and not np.isnan(run_below) and c[i] > run_below:
            shift_confirmed, bias = True, 1
        elif not shift_confirmed and not np.isnan(run_above) and c[i] < run_above:
            shift_confirmed, bias = True, -1

        # Price-imbalance zone: three-bar gap of at least gap_min_ticks.
        bull_gap = i >= 2 and l[i] > h[i - 2] and (l[i] - h[i - 2]) >= p.gap_min_ticks * p.tick
        bear_gap = i >= 2 and h[i] < l[i - 2] and (l[i - 2] - h[i]) >= p.gap_min_ticks * p.tick
        gap_in_bias = (bias == 1 and bull_gap) or (bias == -1 and bear_gap)

        if gap_in_bias and (count == 0 or (count == 1 and not await_first_result)):
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
            q25 = sess_lo + (sess_hi - sess_lo) * 0.25
            q50 = sess_lo + (sess_hi - sess_lo) * 0.50
            q75 = sess_lo + (sess_hi - sess_lo) * 0.75
            if bias == 1:
                ups = [lvl for lvl in (q25, q50, q75, sess_hi) if lvl > zone_mid]
                tp1 = min(ups) if ups else sess_hi
                tp2 = sess_hi
            else:
                dns = [lvl for lvl in (q75, q50, q25, sess_lo) if lvl < zone_mid]
                tp1 = max(dns) if dns else sess_lo
                tp2 = sess_lo
            risk = abs(zone_mid - stop)
            tp1_rr = abs(tp1 - zone_mid) / risk if risk > 0 else 0
            rr_ok = risk > 0 and tp1_rr >= p.tp1_min_rr
            if value_ok and rr_ok:
                count += 1
                t = Trade(date_str, bias, zone_mid, stop, tp1, tp2,
                          n=count, entry_bar=i)
                trades.append(t)
                if count == 1:
                    first_trade, await_first_result = t, True
                if count >= max_trades:
                    break

    return _resolve_trades(trades, df, p)


def backtest(df, p: Params, max_trades: int = 3):
    """Run the engine over every session in ``df``.

    ``df`` must be indexed by tz-aware America/New_York timestamps with
    columns [open, high, low, close, volume]. Returns (trades_df, summary).
    """
    all_trades = []
    for day, day_df in df.groupby(df.index.normalize()):
        window = day_df.between_time(p.entry_start, p.entry_end)
        session = day_df.between_time(p.entry_start, p.session_end)
        if len(window) < 10:
            continue
        all_trades += run_session(session, p, str(day.date()),
                                  entry_end_idx=len(window) - 1,
                                  max_trades=max_trades)
    tdf = pd.DataFrame([asdict(t) for t in all_trades])
    return tdf, summarize_trades(tdf)


def summarize_trades(tdf):
    """Compact summary of a settled trades DataFrame (net R based)."""
    if tdf.empty:
        return {"trades": 0}
    taken = tdf[tdf.outcome.isin(["full", "tp1_only", "loss", "scratch"])]
    full = (taken.outcome == "full").sum()
    tp1_only = (taken.outcome == "tp1_only").sum()
    losses = (taken.outcome == "loss").sum()
    scratches = (taken.outcome == "scratch").sum()
    wins = full + tp1_only
    total_r = float(taken.r.sum())
    gross_win = float(taken[taken.r > 0].r.sum())
    gross_loss = abs(float(taken[taken.r < 0].r.sum()))
    n = len(taken)
    return {
        "trades": int(n),
        "wins(TP1+)": int(wins),
        "full(TP2)": int(full),
        "tp1_only": int(tp1_only),
        "losses": int(losses),
        "scratches": int(scratches),
        "hit_rate": round(100 * wins / n, 1) if n else 0.0,
        "total_R_net": round(total_r, 2),
        "total_R_gross": round(float(taken.r_gross.sum()), 2),
        "expectancy_R": round(total_r / n, 3) if n else 0.0,
        "profit_factor": round(gross_win / gross_loss, 2) if gross_loss else float("inf"),
        "max_drawdown_R": round(_max_dd(taken.r.cumsum()), 2),
    }
