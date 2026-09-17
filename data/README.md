# Data directory

No vendor OHLC data is committed to this repository. Drop your own
1-minute CSV exports in this folder and the notebook will pick them up
automatically; with no CSVs present, the notebook runs in synthetic mode
(clearly labelled, pipeline validation only).

## Expected format

One or more `*.csv` files with a header row:

```
time,open,high,low,close,volume
2025-01-02T09:30:00-05:00,21301.25,21315.50,21298.75,21310.00,4821
2025-01-02T09:31:00-05:00,21310.00,21322.25,21306.50,21318.75,3907
```

- `time`: ISO-8601 timestamps **with a UTC offset** (tz-aware). They are
  converted to America/New_York internally; any consistent offset works.
- `open, high, low, close`: 1-minute bars for the instrument (the
  defaults in `src/engine.py` are sized for Nasdaq-100 E-mini futures).
- `volume`: optional; filled with 0 if the column is missing.
- Bars must cover at least 09:30–16:00 New York time on each session you
  want backtested. Multiple files are merged and deduplicated on
  timestamp (later files win), so overlapping exports are fine.

## Exporting from TradingView

1. Open a 1-minute chart of the instrument (e.g. the continuous
   Nasdaq-100 E-mini contract), with the chart timezone set to
   New York.
2. Load as much history as your plan allows by scrolling back — the
   export covers the bars the chart has loaded.
3. Chart menu → **Export chart data…**, choose ISO time format, and
   download the CSV.
4. Repeat with older windows if you need more history than one export
   holds, and drop all the files here — the loader merges them.

`.gitignore` excludes `data/*.csv`, so your data never ends up in a
commit.
