# Results

Placeholder. Result tables and figures generated from **real** 1-minute
data are added here after a local run of `notebooks/backtest.ipynb` in
own-data mode.

Every artifact added to this folder must be labelled with:

- **Data period** — exact date range of the bars used.
- **Mode** — own-data (vendor export) or synthetic; synthetic outputs
  never leave the notebook and are not results.
- **Split** — which sessions were in-sample (development) and which were
  the held-out out-of-sample period.
- **Costs** — gross or net, and the commission/slippage assumptions if
  they differ from the defaults in `src/engine.py`.

The README results tables remain marked **TBD** until the real-data run
lands here.
