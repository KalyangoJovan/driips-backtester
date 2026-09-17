"""Hand-crafted session fixtures with known engine outcomes.

The shared prefix (bars 0-11) walks the whole gate chain for a long:

- bar 3: working pivot low at 98.0
- bar 6: stop-run below — low 97.2 undercuts the pivot by > 2 ticks
- bar 8: structure-shift confirmation — close 98.5 back above 98.0,
  session bias = long
- bar 11: price-imbalance zone — low 99.0 gaps 1.0 pt over bar 9's
  high 98.0; entry at the zone midpoint 98.5

With the default parameters that gives entry 98.5, stop 97.0 (run level
98.0 minus 4 ticks), TP1 100.0 (nearest quartile of the 96-104 session
range), TP2 104.0 (range extreme), risk 1.5 pts — TP1 exactly 1.0 R.
"""
import pandas as pd

# (open, high, low, close)
PREFIX = [
    (102.5, 104.0, 101.8, 102.0),
    (102.0, 102.2, 99.0, 99.2),
    (99.2, 99.5, 98.5, 98.7),
    (98.7, 99.0, 98.0, 98.3),
    (98.3, 98.8, 98.2, 98.6),
    (98.6, 99.0, 98.4, 98.8),
    (98.8, 98.9, 97.2, 97.4),
    (97.4, 97.6, 96.0, 97.0),
    (97.0, 98.6, 97.2, 98.5),
    (97.9, 98.0, 97.6, 97.9),
    (97.9, 98.9, 97.8, 98.8),
    (99.2, 99.8, 99.0, 99.6),
]

# Rally to TP2 with no further gaps: full win.
WIN_TAIL = [
    (99.6, 100.4, 99.5, 100.2),
    (100.2, 100.9, 100.1, 100.8),
    (100.8, 101.5, 100.7, 101.4),
    (101.4, 102.1, 101.3, 102.0),
    (102.0, 102.7, 101.9, 102.6),
    (102.6, 103.3, 102.5, 103.2),
    (103.2, 103.9, 103.1, 103.8),
    (103.8, 104.5, 103.7, 104.4),
]

# Straight down through the stop before TP1: loss.
LOSS_TAIL = [
    (99.6, 99.7, 98.1, 98.3),
    (98.3, 98.4, 96.8, 96.9),
]

# Meanders between stop and TP1 into the close: scratch.
SCRATCH_TAIL = [
    (99.6, 99.7, 98.9, 99.0),
    (99.0, 99.3, 98.6, 98.8),
    (98.8, 99.1, 98.4, 98.6),
]

# TP1 trades at bar 12, runner stays alive, and a second zone gaps in at
# bar 14 (low 101.4 over bar 12's high 100.4).
TREND_REENTRY_TAIL = [
    (99.6, 100.4, 99.5, 100.2),
    (100.2, 100.9, 100.1, 100.8),
    (101.5, 102.0, 101.4, 101.9),
    (101.9, 102.3, 101.8, 102.2),
    (102.2, 102.5, 102.1, 102.4),
    (102.4, 102.6, 102.0, 102.1),
]

# TP1 trades at bar 12, then bar 13 touches breakeven (runner dies);
# a fresh zone gaps in at bar 15 — the trend variant must NOT take it.
TREND_DEAD_RUNNER_TAIL = [
    (99.6, 100.4, 99.5, 100.2),
    (100.2, 100.3, 98.4, 98.6),
    (98.6, 99.6, 98.5, 99.5),
    (101.4, 101.9, 101.35, 101.8),
]


def make_day(tail):
    bars = PREFIX + tail
    idx = pd.date_range("2025-03-03 09:30", periods=len(bars), freq="1min",
                        tz="America/New_York")
    df = pd.DataFrame(bars, columns=["open", "high", "low", "close"], index=idx)
    df["volume"] = 1000.0
    return df
