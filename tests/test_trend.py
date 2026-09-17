import pytest

from src.data import make_synthetic
from src.engine import Params, run_session
from src.trend import backtest_trend, run_session_trend
from tests.fixtures import (TREND_DEAD_RUNNER_TAIL, TREND_REENTRY_TAIL,
                            make_day)

# Relaxed filters isolate the re-entry gating: continuation zones sit
# high in the range with stops still anchored at the original run level,
# so the default value/reward filters would reject them by construction.
RELAXED = Params(require_value_zone=False, tp1_min_rr=0.2)


def test_reentry_allowed_while_runner_alive():
    day = make_day(TREND_REENTRY_TAIL)
    trades = run_session_trend(day, RELAXED, "2025-03-03",
                               entry_end_idx=len(day) - 1, max_trades=3)
    assert [t.n for t in trades] == [1, 2]
    assert all(t.direction == 1 for t in trades)
    assert trades[0].entry_bar == 11
    assert trades[1].entry_bar == 14
    # second zone: low 101.4 over bar 12's high 100.4
    assert trades[1].entry == pytest.approx((101.4 + 100.4) / 2)


def test_no_reentry_after_runner_dies():
    """Bar 13 touches entry #1's breakeven: the session is done, even
    though a fresh zone gaps in at bar 15."""
    day = make_day(TREND_DEAD_RUNNER_TAIL)
    trades = run_session_trend(day, RELAXED, "2025-03-03",
                               entry_end_idx=len(day) - 1, max_trades=3)
    assert len(trades) == 1
    assert trades[0].outcome == "tp1_only"
    assert trades[0].r_gross == pytest.approx(0.5)  # runner back to breakeven


def test_base_engine_stops_after_tp1_success():
    """Contrast with the base variant: once entry #1 reaches TP1 the base
    sequencing is done for the session (spec 6.3), so it ignores the
    continuation zone at bar 14 that the trend variant takes."""
    day = make_day(TREND_REENTRY_TAIL)
    base = run_session(day, RELAXED, "2025-03-03")
    assert len(base) == 1


def test_max_trades_caps_the_session():
    day = make_day(TREND_REENTRY_TAIL)
    trades = run_session_trend(day, RELAXED, "2025-03-03",
                               entry_end_idx=len(day) - 1, max_trades=1)
    assert len(trades) == 1


def test_trend_sessions_are_single_direction():
    df = make_synthetic(days=30, seed=11)
    tdf, summary = backtest_trend(df, Params(), max_trades=3)
    assert summary["trades"] == len(tdf)
    if len(tdf):
        assert tdf.groupby("date").size().max() <= 3
        # bias never resets in the trend variant: one direction per session
        assert (tdf.groupby("date")["direction"].nunique() == 1).all()
