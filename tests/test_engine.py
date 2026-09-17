import pandas as pd
import pytest

from src.data import make_synthetic
from src.engine import Params, backtest, run_session
from tests.fixtures import (LOSS_TAIL, SCRATCH_TAIL, WIN_TAIL, make_day)

COST_R = (0.225 + 0.5) / 1.5  # round-turn cost over the fixture's 1.5-pt risk


def test_gate_chain_full_win():
    """Stop-run -> confirmation -> zone entry -> TP1 scale-out -> TP2."""
    day = make_day(WIN_TAIL)
    trades = run_session(day, Params(), "2025-03-03")
    assert len(trades) == 1
    t = trades[0]
    assert t.direction == 1
    assert t.entry_bar == 11
    assert t.entry == pytest.approx(98.5)
    assert t.stop == pytest.approx(97.0)   # run level 98.0 minus 4 ticks
    assert t.tp1 == pytest.approx(100.0)   # nearest quartile of 96-104
    assert t.tp2 == pytest.approx(104.0)   # session-range extreme
    assert t.outcome == "full"
    # 0.5 * 1R at TP1 + 0.5 * (104-98.5)/1.5 on the runner
    assert t.r_gross == pytest.approx(2.333, abs=1e-3)
    assert t.r == pytest.approx(2.333 - COST_R, abs=1e-3)


def test_stop_out_is_minus_one_r_plus_costs():
    trades = run_session(make_day(LOSS_TAIL), Params(), "2025-03-03")
    assert len(trades) == 1
    t = trades[0]
    assert t.outcome == "loss"
    assert t.r_gross == pytest.approx(-1.0)
    assert t.r == pytest.approx(-1.0 - COST_R, abs=1e-3)


def test_session_close_exit_is_scratch():
    trades = run_session(make_day(SCRATCH_TAIL), Params(), "2025-03-03")
    assert len(trades) == 1
    t = trades[0]
    assert t.outcome == "scratch"
    assert t.r_gross == pytest.approx(0.0)
    assert t.r == pytest.approx(-COST_R, abs=1e-3)


def test_value_zone_filter_blocks_entries_in_wrong_half():
    """With the whole session range compressed so the zone midpoint sits
    above the range midpoint, the value-zone filter must reject the long."""
    day = make_day(WIN_TAIL)
    # Flatten bar 0's spike high: session range becomes ~96-100.4 at entry
    # time, midpoint ~98.2 < entry 98.5.
    day.iloc[0] = [98.5, 99.0, 98.3, 98.4, 1000.0]
    p = Params()
    assert run_session(day, p, "2025-03-03") == []


def test_no_entry_without_structure_shift_confirmation():
    """Cut the day off before the confirming close and pad with flat bars
    that never close back through the run level: no trades."""
    day = make_day(WIN_TAIL).iloc[:8]  # bar 8 (the confirming close) removed
    pad_idx = pd.date_range(day.index[-1] + pd.Timedelta(minutes=1),
                            periods=4, freq="1min", tz=day.index.tz)
    pad = pd.DataFrame([[97.4, 97.6, 97.3, 97.5, 1000.0]] * 4,
                       columns=day.columns, index=pad_idx)
    day = pd.concat([day, pad])
    assert run_session(day, Params(), "2025-03-03") == []


def test_reward_filter_blocks_sub_1r_first_target():
    day = make_day(WIN_TAIL)
    p = Params(tp1_min_rr=1.5)  # fixture's TP1 is exactly 1.0 R
    assert run_session(day, p, "2025-03-03") == []


def test_backtest_runs_on_synthetic_data():
    df = make_synthetic(days=30, seed=11)
    tdf, summary = backtest(df, Params())
    assert summary["trades"] == len(tdf)
    if len(tdf):
        assert set(tdf.outcome) <= {"full", "tp1_only", "loss", "scratch"}
        # net never beats gross (costs are non-negative)
        assert (tdf.r <= tdf.r_gross + 1e-9).all()
        # base sequencing cap: never more than 3 entries in a session
        assert tdf.groupby("date").size().max() <= 3
        assert set(tdf.direction) <= {1, -1}


def test_value_zone_filter_never_adds_trades():
    df = make_synthetic(days=30, seed=11)
    n_filtered = backtest(df, Params(require_value_zone=True))[1]["trades"]
    n_open = backtest(df, Params(require_value_zone=False))[1]["trades"]
    assert n_filtered <= n_open


def test_max_trades_cap_respected():
    df = make_synthetic(days=30, seed=11)
    tdf, _ = backtest(df, Params(), max_trades=1)
    if len(tdf):
        assert tdf.groupby("date").size().max() == 1


def test_short_session_skipped():
    day = make_day(WIN_TAIL).iloc[:9]
    assert run_session(day, Params(), "2025-03-03") == []
