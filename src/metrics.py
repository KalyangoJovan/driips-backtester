"""Performance metrics for the Driips opening-session backtests.

Reporting standard implemented here (and mirrored in the notebook):

- Gross AND net figures, with the cost assumptions stated by the caller.
- The headline Sharpe ratio is the honestly-annualized, full-period
  figure: the per-session net R series includes EVERY session in the
  data window, counting flat sessions as zero. A Sharpe conditioned on
  invested days only is also computed, but it must always be labelled
  as conditional and shown after the unconditional figure.
- Max drawdown in R and max drawdown duration in sessions.
- Percentage of sessions with any exposure.
- Explicit in-sample / out-of-sample split via ``split_data``.

All figures are in R (multiples of initial per-trade risk).
"""
import numpy as np
import pandas as pd

TRADING_DAYS_PER_YEAR = 252


def split_data(df, oos_start):
    """Split a bar frame into in-sample (before ``oos_start``) and
    out-of-sample (from ``oos_start`` on). ``oos_start`` is anything
    ``pd.Timestamp`` accepts, interpreted in the frame's timezone."""
    ts = pd.Timestamp(oos_start)
    if ts.tz is None:
        ts = ts.tz_localize(df.index.tz)
    return df[df.index < ts], df[df.index >= ts]


def _session_index(sessions):
    """Normalize any collection of session dates to a tz-naive, sorted,
    unique DatetimeIndex so trade dates (naive strings) always align."""
    idx = pd.DatetimeIndex(pd.to_datetime(list(sessions)))
    if idx.tz is not None:
        idx = idx.tz_localize(None)
    return idx.normalize().unique().sort_values()


def session_returns(trades_df, sessions, column="r"):
    """Net (or gross) R per session over ALL sessions in the data window.

    ``sessions`` is the full list/index of session dates covered by the
    bar data — including sessions with no trade, which count as 0.0.
    This is what makes the annualized Sharpe unconditional.
    """
    idx = _session_index(sessions)
    out = pd.Series(0.0, index=idx)
    if trades_df is not None and len(trades_df):
        per_day = trades_df.groupby(pd.to_datetime(trades_df["date"]))[column].sum()
        per_day.index = per_day.index.normalize()
        out = out.add(per_day.reindex(idx, fill_value=0.0), fill_value=0.0)
    return out


def sharpe_annualized(daily_r, periods_per_year=TRADING_DAYS_PER_YEAR):
    """Annualized Sharpe of a per-session R series (risk-free rate 0).

    Pass the FULL-period series from ``session_returns`` for the honest,
    unconditional figure. NaN if the series cannot support the estimate.
    """
    r = pd.Series(daily_r).astype(float)
    if len(r) < 2 or r.std(ddof=1) == 0:
        return float("nan")
    return float(r.mean() / r.std(ddof=1) * np.sqrt(periods_per_year))


def max_drawdown(equity):
    """Deepest peak-to-trough decline of a cumulative R equity curve."""
    eq = pd.Series(equity).astype(float)
    if eq.empty:
        return 0.0
    return float((eq - eq.cummax()).min())


def max_drawdown_duration(equity):
    """Longest stretch (in sessions) below a prior equity peak.

    Counts sessions from the peak until the curve makes a new high; an
    unrecovered drawdown at the end of the series counts in full.
    """
    eq = pd.Series(equity).astype(float)
    if eq.empty:
        return 0
    peak = eq.cummax()
    under = eq < peak
    longest = run = 0
    for u in under:
        run = run + 1 if u else 0
        longest = max(longest, run)
    return int(longest)


def summarize(trades_df, sessions, label=""):
    """Full metrics dict for one backtest run.

    ``trades_df``: settled trades with columns r (net), r_gross, outcome.
    ``sessions``: every session date in the data window (traded or not).
    """
    idx = _session_index(sessions)
    n_sessions = len(idx)
    empty = trades_df is None or len(trades_df) == 0
    n = 0 if empty else len(trades_df)

    daily_net = session_returns(trades_df, idx, "r")
    daily_gross = session_returns(trades_df, idx, "r_gross")
    eq_net = daily_net.cumsum()

    if empty:
        hit = traded_days = 0
        cond_sharpe = float("nan")
    else:
        hit = int(trades_df.outcome.isin(["full", "tp1_only"]).sum())
        traded_days = int(trades_df["date"].nunique())
        traded_r = daily_net[daily_net.index.isin(
            pd.to_datetime(trades_df["date"]).dt.normalize().unique())]
        cond_sharpe = sharpe_annualized(traded_r)

    return {
        "label": label,
        "sessions": int(n_sessions),
        "trades": n,
        "hit_rate_pct": round(100 * hit / n, 1) if n else float("nan"),
        "total_R_gross": round(float(daily_gross.sum()), 2),
        "total_R_net": round(float(daily_net.sum()), 2),
        "avg_R_net_per_trade": round(float(trades_df.r.mean()), 3) if n else float("nan"),
        "sharpe_annualized": round(sharpe_annualized(daily_net), 2),
        "sharpe_traded_days_only (conditional)": round(cond_sharpe, 2),
        "max_drawdown_R": round(max_drawdown(eq_net), 2),
        "max_drawdown_duration_sessions": max_drawdown_duration(eq_net),
        "pct_sessions_with_exposure": round(100 * traded_days / n_sessions, 1) if n_sessions else float("nan"),
    }


def metrics_table(runs):
    """Stack several ``summarize`` dicts into a comparison DataFrame."""
    return pd.DataFrame(runs).set_index("label").T
