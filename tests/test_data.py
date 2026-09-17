import numpy as np
import pandas as pd
import pytest

from src.data import load_csv, load_data_dir, make_synthetic, merge_csvs

CSV = """time,open,high,low,close,volume
2025-01-02T09:30:00-05:00,100.0,101.0,99.5,100.5,1200
2025-01-02T09:31:00-05:00,100.5,101.5,100.0,101.0,900
2025-01-02T09:32:00-05:00,101.0,101.2,100.2,100.4,800
"""

CSV_NO_VOLUME = """time,open,high,low,close
2025-01-02T09:33:00-05:00,100.4,100.9,100.1,100.7
"""

CSV_OVERLAP = """time,open,high,low,close,volume
2025-01-02T09:32:00-05:00,999.0,999.0,999.0,999.0,1
2025-01-02T09:33:00-05:00,100.4,100.9,100.1,100.7,700
"""


def _write(tmp_path, name, text):
    p = tmp_path / name
    p.write_text(text)
    return str(p)


def test_load_csv_shape_and_timezone(tmp_path):
    df = load_csv(_write(tmp_path, "a.csv", CSV))
    assert list(df.columns) == ["open", "high", "low", "close", "volume"]
    assert str(df.index.tz) == "America/New_York"
    assert len(df) == 3
    assert df.index.is_monotonic_increasing
    assert df.iloc[0]["open"] == 100.0
    assert df.index[0].hour == 9 and df.index[0].minute == 30


def test_load_csv_fills_missing_volume(tmp_path):
    df = load_csv(_write(tmp_path, "b.csv", CSV_NO_VOLUME))
    assert (df["volume"] == 0).all()


def test_load_csv_requires_time_column(tmp_path):
    p = _write(tmp_path, "bad.csv", "open,high,low,close\n1,2,0,1\n")
    with pytest.raises(ValueError):
        load_csv(p)


def test_merge_dedupes_keeping_later_file(tmp_path):
    a = _write(tmp_path, "a.csv", CSV)
    b = _write(tmp_path, "b.csv", CSV_OVERLAP)
    df = merge_csvs([a, b])
    assert len(df) == 4  # 3 + 2 with one overlapping timestamp
    # the overlapping 09:32 bar comes from the later file
    assert df.loc["2025-01-02 09:32:00-05:00", "open"] == 999.0


def test_load_data_dir(tmp_path):
    assert load_data_dir(str(tmp_path)) is None
    _write(tmp_path, "a.csv", CSV)
    df = load_data_dir(str(tmp_path))
    assert len(df) == 3


def test_synthetic_is_deterministic():
    a = make_synthetic(days=5, seed=42)
    b = make_synthetic(days=5, seed=42)
    pd.testing.assert_frame_equal(a, b)
    c = make_synthetic(days=5, seed=43)
    assert not a.equals(c)


def test_synthetic_session_structure():
    df = make_synthetic(days=10, seed=1)
    assert str(df.index.tz) == "America/New_York"
    assert df.index.normalize().nunique() == 10
    assert set(df.index.dayofweek) <= {0, 1, 2, 3, 4}  # weekdays only
    # full 09:30-16:00 sessions: 390 one-minute bars per day
    per_day = df.groupby(df.index.normalize()).size()
    assert (per_day == 390).all()
    first = df.between_time("09:30", "09:30")
    assert len(first) == 10  # every session starts at 09:30


def test_synthetic_ohlc_sanity():
    df = make_synthetic(days=10, seed=1)
    assert (df.high >= df[["open", "close"]].max(axis=1) - 1e-9).all()
    assert (df.low <= df[["open", "close"]].min(axis=1) + 1e-9).all()
    assert (df.volume > 0).all()
    assert np.isfinite(df[["open", "high", "low", "close"]].values).all()
