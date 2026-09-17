import math

import numpy as np
import pandas as pd
import pytest

from src.metrics import (max_drawdown, max_drawdown_duration, metrics_table,
                         session_returns, sharpe_annualized, split_data,
                         summarize)

SESSIONS = pd.bdate_range("2025-01-02", periods=10)


def _trades():
    return pd.DataFrame({
        "date": ["2025-01-02", "2025-01-03", "2025-01-08", "2025-01-08"],
        "r": [1.0, -1.5, 0.6, -0.4],
        "r_gross": [1.2, -1.0, 0.8, -0.2],
        "outcome": ["full", "loss", "tp1_only", "loss"],
    })


def test_session_returns_covers_all_sessions_with_zeros():
    daily = session_returns(_trades(), SESSIONS)
    assert len(daily) == 10
    assert daily.sum() == pytest.approx(-0.3)
    assert daily.loc["2025-01-06"] == 0.0          # flat session counts as 0
    assert daily.loc["2025-01-08"] == pytest.approx(0.2)  # both trades summed


def test_session_returns_aligns_tz_aware_sessions():
    """Regression: bar data carries tz-aware NY session dates while trade
    dates are naive strings — the daily series must still line up."""
    tz_sessions = pd.bdate_range("2025-01-02", periods=10,
                                 tz="America/New_York")
    daily = session_returns(_trades(), tz_sessions)
    assert daily.sum() == pytest.approx(-0.3)
    s = summarize(_trades(), tz_sessions, label="tz")
    assert s["total_R_net"] == pytest.approx(-0.3)
    assert s["pct_sessions_with_exposure"] == pytest.approx(30.0)


def test_unconditional_sharpe_uses_flat_sessions():
    daily = session_returns(_trades(), SESSIONS)
    traded_only = daily[daily != 0]
    full = sharpe_annualized(daily)
    conditional = sharpe_annualized(traded_only)
    assert not math.isnan(full)
    assert full != pytest.approx(conditional)  # conditioning changes the figure


def test_sharpe_degenerate_series_is_nan():
    assert math.isnan(sharpe_annualized(pd.Series([0.5])))
    assert math.isnan(sharpe_annualized(pd.Series([0.0, 0.0, 0.0])))


def test_max_drawdown_and_duration():
    daily = pd.Series([1.0, -2.0, 0.5, 1.5, 0.0])
    eq = daily.cumsum()  # 1, -1, -0.5, 1, 1
    assert max_drawdown(eq) == pytest.approx(-2.0)
    assert max_drawdown_duration(eq) == 2  # two sessions below the peak
    # unrecovered drawdown at the end counts in full
    eq2 = pd.Series([1.0, 0.0, -1.0, -0.5])
    assert max_drawdown_duration(eq2) == 3


def test_split_data():
    idx = pd.date_range("2025-01-01 09:30", periods=100, freq="1D",
                        tz="America/New_York")
    df = pd.DataFrame({"close": np.arange(100.0)}, index=idx)
    ins, oos = split_data(df, "2025-02-01")
    assert len(ins) + len(oos) == 100
    assert ins.index.max() < oos.index.min()
    assert str(oos.index.min().date()) == "2025-02-01"


def test_summarize_full_metrics():
    s = summarize(_trades(), SESSIONS, label="test")
    assert s["sessions"] == 10
    assert s["trades"] == 4
    assert s["hit_rate_pct"] == pytest.approx(50.0)  # full + tp1_only of 4
    assert s["total_R_net"] == pytest.approx(-0.3)
    assert s["total_R_gross"] == pytest.approx(0.8)
    assert s["pct_sessions_with_exposure"] == pytest.approx(30.0)  # 3 of 10
    assert s["max_drawdown_R"] <= 0
    assert s["max_drawdown_duration_sessions"] >= 1
    assert not math.isnan(s["R_unit_sharpe_annualized (unconditional)"])
    # trade-level statistics lead; the conditional Sharpe is labelled and last
    keys = list(s)
    assert keys.index("trades") < keys.index("R_unit_sharpe_annualized (unconditional)")
    assert keys[-1] == "R_unit_sharpe_traded_days_only (conditional)"


def test_summarize_empty():
    s = summarize(pd.DataFrame(), SESSIONS, label="empty")
    assert s["trades"] == 0
    assert s["total_R_net"] == 0.0
    assert s["pct_sessions_with_exposure"] == 0.0


def test_metrics_table_stacks_runs():
    t = metrics_table([summarize(_trades(), SESSIONS, label="a"),
                       summarize(pd.DataFrame(), SESSIONS, label="b")])
    assert list(t.columns) == ["a", "b"]
    assert t.loc["trades", "a"] == 4
