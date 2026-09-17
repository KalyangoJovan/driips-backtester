# Driips Opening-Session Backtester

A spec-first backtest of an **opening-session stop-run reversion**
strategy on Nasdaq-100 E-mini futures, 1-minute bars.

## Hypothesis

In the first minutes of the US cash session, resting stop orders cluster
just beyond the early session extremes. An opening push that runs those
stops and then fails — confirmed by a 1-minute close back through the
level that was run (a structure-shift confirmation) — frequently marks
the session's directional extreme. The strategy enters on a pullback to
the midpoint of a price-imbalance zone left by the reversal impulse,
filtered to the favorable half of the developing range (value-zone
filter), with the runner targeted at the prior range extreme. A
trend-continuation variant permits up to three entries per session while
the first position's runner remains alive.

## Methodology

The order of operations is the point:

1. **Specification first.** The full rule set was written down as
   numbered, testable rules before any backtest code:
   [`spec/strategy_spec.md`](spec/strategy_spec.md). The code implements
   the spec, not the other way round.
2. **Backtest.** The engine in [`src/`](src/) implements the spec's gate
   chain with a conservative cost model (commission + slippage deducted
   in R, stop-first intrabar priority) over a development data period.
3. **Out-of-sample confirmation.** Parameters were frozen, then the
   strategy was evaluated once on a held-out year that played no part in
   development.
4. Subsequently deployed to automated live execution for 12 months.

## Results

From a REAL-mode run on Nasdaq-100 E-mini 1-minute exports covering
**2025-07-04 → 2026-08-11** (285 usable cash sessions). Cost
assumptions: 0.225 pts commission + 0.5 pts slippage per round turn,
deducted in R; gross figures are before costs, net after.

**Split.** The strategy was developed *before* this window, on data not
shipped with the repository, so no in-sample figures are reproducible
here — that is a feature of the split, not an omission: everything below
is out of development's reach. The held-out out-of-sample year is
**Jul 2025 – Jun 2026**; the remaining **Jul – Aug 2026** bars form a
post-OOS forward sample.

**Trend-continuation variant (validated configuration, max 3 entries):**

| Metric | Held-out year (OOS) | Post-OOS forward |
|---|---|---|
| Sessions | 255 | 30 |
| Trades | 231 | 28 |
| Hit rate (TP1 reached) | 75.8% | 78.6% |
| Total R, gross | +292.95 | +34.67 |
| Total R, net | +277.32 | +33.40 |
| Avg net R / trade | 1.20 | 1.19 |
| Max drawdown (net R) | −2.80 | −3.14 |
| Max drawdown duration (sessions) | 10 | 3 |
| Sessions with exposure | 75.3% | 73.3% |
| R-unit Sharpe (annualized, unconditional) | 6.75 | 7.35 |
| R-unit Sharpe (traded days only — conditional) | 8.02 | 8.89 |

**Base variant (sequenced entries):**

| Metric | Held-out year (OOS) | Post-OOS forward |
|---|---|---|
| Trades | 212 | 24 |
| Hit rate (TP1 reached) | 74.5% | 75.0% |
| Total R, gross | +278.49 | +32.32 |
| Total R, net | +263.80 | +31.21 |
| Max drawdown (net R) | −6.34 | −2.09 |
| R-unit Sharpe (annualized, unconditional) | 7.52 | 7.79 |

### A note on the Sharpe figure

The Sharpe rows are computed on per-session risk-unit (R) returns of a
single intraday strategy whose scale-out and breakeven-runner mechanics
structurally suppress losing sessions. That makes the figure **not
comparable to portfolio-level Sharpe ratios on dollar returns** —
readers should weight the trade-level statistics and the drawdown
figures more heavily. The unconditional figure is honestly annualized
over the full period, every usable cash session included and flat
sessions counted as zero; the Sharpe conditioned on traded days only is
labelled conditional and shown last. Full metrics table, equity curve,
and R distribution are in [`results/`](results/README.md), each labelled
with period, mode, split, and cost assumptions.

## Reproduction

```bash
git clone <this repo> && cd driips-backtester
python -m venv .venv && .venv/Scripts/activate   # or source .venv/bin/activate
pip install -r requirements.txt
pytest                                            # engine/data/metrics tests
jupyter notebook notebooks/backtest.ipynb         # run all cells
```

- **Synthetic mode (out of the box).** With no CSVs in `data/`, the
  notebook generates deterministic synthetic sessions and runs the full
  pipeline end to end. The banner and every output are labelled
  SYNTHETIC — these numbers validate the code path, not the strategy.
- **Real mode.** Export 1-minute bars from TradingView into `data/`
  (format and steps in [`data/README.md`](data/README.md)) and re-run
  the notebook; it auto-detects the CSVs, labels the run REAL, and
  exports labelled result artifacts to `results/`. The parameters cell
  pins the held-out year (`OOS_START = 2025-07-01`,
  `OOS_END = 2026-07-01`) so the published split reproduces exactly.

## Limitations

- **Sample size.** The held-out year contains 231 trades (259 including
  the forward sample) — enough to estimate a hit rate, but confidence
  intervals on expectancy and especially on tail metrics like max
  drawdown are still wide at these counts; one year of sessions is one
  draw of the calendar.
- **Single-instrument concentration.** All evidence is from one index
  future. Nothing here demonstrates transfer to other instruments.
- **Regime dependence.** The edge is a property of how the 09:30
  auction has traded in the tested period; a structural change in
  opening liquidity provision can degrade it without warning.
- **Slippage uncertainty.** Fills are modelled at the zone midpoint with
  a flat slippage allowance. Real queue position on limit orders and
  stop-order slippage in fast conditions are both worse than any flat
  assumption on some days.
- **Capacity.** The strategy trades moments of thin, one-sided depth by
  design. It is a small-size strategy; the backtest says nothing about
  execution at institutional size.

As corroboration of the cost and fill assumptions: the held-out-year
backtest (+277.3R across 231 trades) agrees within about 4% with the
strategy's automated live execution over the same year (approximately
+274R across ~222 trades, in R terms).

## License

MIT — see [LICENSE](LICENSE).
