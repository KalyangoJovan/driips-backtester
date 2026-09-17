"""Data loading for the Driips opening-session backtests.

Two sources, one output shape: a pandas DataFrame indexed by tz-aware
America/New_York timestamps with columns [open, high, low, close, volume].
The engine never cares which source produced the frame.

- ``load_csv`` / ``merge_csvs`` / ``load_data_dir``: TradingView
  "Export chart data" CSVs (see ``data/README.md`` for the format and
  export steps).
- ``make_synthetic``: generated 1-minute sessions with plausible
  open-auction structure (stop-runs, impulse legs, quiet afternoons).
  Synthetic data exists to prove the pipeline executes end to end —
  it supports NO performance claims.
"""
import glob
import os

import numpy as np
import pandas as pd

NY = "America/New_York"


def load_csv(path):
    """Load one TradingView export: columns time,open,high,low,close,volume.

    ``time`` must be ISO-8601 with an offset (TradingView exports include
    it). Returns a frame indexed by tz-aware New York timestamps.
    """
    df = pd.read_csv(path)
    df.columns = [c.strip().lower() for c in df.columns]
    if "time" not in df.columns:
        raise ValueError(f"{path}: expected a 'time' column")
    df["time"] = pd.to_datetime(df["time"], utc=True).dt.tz_convert(NY)
    df = df.set_index("time").sort_index()
    if "volume" not in df.columns:
        df["volume"] = 0
    return df[["open", "high", "low", "close", "volume"]].astype(float)


def merge_csvs(paths):
    """Merge several exports into one continuous, deduplicated series."""
    parts = [load_csv(p) for p in paths]
    merged = pd.concat(parts)
    return merged[~merged.index.duplicated(keep="last")].sort_index()


def load_data_dir(data_dir):
    """Merge every ``*.csv`` under ``data_dir``; None if there are none."""
    paths = sorted(glob.glob(os.path.join(data_dir, "*.csv")))
    if not paths:
        return None
    return merge_csvs(paths)


def make_synthetic(days=120, seed=7, interval_min=1, start_price=18000.0):
    """Generate 1-minute sessions (09:30–16:00 NY, weekdays) with enough
    open-auction structure for the engine's gates to fire.

    Session archetypes:
    - ``run_reversal``: an opening push runs the early extreme (stop-run),
      then reverses hard with impulse legs — the pattern the strategy trades.
    - ``trend``: a steady directional day.
    - ``chop``: no dominant direction.

    Deterministic for a given ``seed``. For pipeline validation only,
    never for performance claims.
    """
    rng = np.random.default_rng(seed)
    rows = []
    day = pd.Timestamp.now(tz=NY).normalize() - pd.Timedelta(days=int(days * 1.6) + 7)
    made = 0
    while made < days:
        if day.weekday() < 5:
            made += 1
            base = start_price + rng.normal(0, 300)
            direction = int(rng.choice([1, -1]))
            archetype = rng.choice(
                ["run_reversal", "run_reversal", "trend", "chop"])
            steps = _session_steps(rng, archetype, direction, interval_min)
            t = day.replace(hour=9, minute=30)
            price = base
            for k, step in enumerate(steps):
                o = price
                c = o + step
                wick = rng.uniform(0.5, 3.0)
                hi = max(o, c) + rng.uniform(0, wick)
                lo = min(o, c) - rng.uniform(0, wick)
                vol = int(rng.integers(500, 3000))
                if k < 60:  # heavier participation in the first hour
                    vol = int(vol * rng.uniform(1.5, 2.5))
                rows.append((t, o, hi, lo, c, vol))
                price = c
                t += pd.Timedelta(minutes=interval_min)
        day += pd.Timedelta(days=1)
    df = pd.DataFrame(
        rows, columns=["time", "open", "high", "low", "close", "volume"]
    ).set_index("time")
    df.index = df.index.tz_convert(NY) if df.index.tz else df.index.tz_localize(NY)
    return df.astype(float)


def _session_steps(rng, archetype, d, interval_min):
    """Per-bar close-to-close increments for one 09:30–16:00 session."""
    n = int(390 / interval_min)
    scale = interval_min  # increments sized for 1-minute bars, scaled up
    steps = []
    if archetype == "run_reversal":
        # Opening push against the eventual direction: forms swing pivots,
        # then runs the early extreme.
        n_push = int(rng.integers(10, 22))
        for _ in range(n_push):
            steps.append((-d * rng.uniform(0.8, 2.5) + rng.normal(0, 1.5)) * scale)
        # Reversal: impulse leg back through the run level.
        n_imp = int(rng.integers(4, 9))
        for _ in range(n_imp):
            steps.append(d * rng.uniform(6, 14) * scale)
        # Continuation into late morning: pullbacks and further impulses.
        while len(steps) < min(150, n):
            r = rng.random()
            if r < 0.15:
                for _ in range(int(rng.integers(2, 5))):
                    steps.append(-d * rng.uniform(1, 3) * scale)
            elif r < 0.30:
                for _ in range(int(rng.integers(2, 4))):
                    steps.append(d * rng.uniform(4, 10) * scale)
            else:
                steps.append((d * rng.uniform(0.3, 1.5) + rng.normal(0, 2)) * scale)
    elif archetype == "trend":
        while len(steps) < min(180, n):
            if rng.random() < 0.10:
                for _ in range(int(rng.integers(2, 4))):
                    steps.append(d * rng.uniform(5, 11) * scale)
            else:
                steps.append((d * rng.uniform(0.5, 2.5) + rng.normal(0, 2)) * scale)
    # Chop archetype and every afternoon: mean-zero noise.
    while len(steps) < n:
        steps.append(rng.normal(0, 2.5) * scale)
    return steps[:n]
