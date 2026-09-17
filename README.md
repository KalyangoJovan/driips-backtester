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

Values are **TBD** pending the real-data run (the repository ships no
vendor data; see [Reproduction](#reproduction) and
[`results/`](results/README.md)). Cost assumptions: 0.225 pts commission
+ 0.5 pts slippage per round turn.

| Metric | IS gross | IS net | OOS gross | OOS net |
|---|---|---|---|---|
| Trades | TBD | TBD | TBD | TBD |
| Hit rate (TP1 reached) | TBD | TBD | TBD | TBD |
| Total R | TBD | TBD | TBD | TBD |
| Avg R / trade | TBD | TBD | TBD | TBD |
| Sharpe (annualized, full period) | TBD | TBD | TBD | TBD |
| Max drawdown (R) | TBD | TBD | TBD | TBD |
| Max drawdown duration (sessions) | TBD | TBD | TBD | TBD |
| Sessions with exposure (%) | TBD | TBD | TBD | TBD |

The headline Sharpe is always the full-period, honestly-annualized
figure: per-session returns include every session in the window, flat
sessions counted as zero. Any Sharpe conditioned on invested days only
is labelled as conditional and shown second.

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
- **Own-data mode.** Export 1-minute bars from TradingView into `data/`
  (format and steps in [`data/README.md`](data/README.md)) and re-run
  the notebook; it auto-detects the CSVs and labels the run OWN-DATA.
  Set the out-of-sample start date in the notebook's parameters cell to
  reproduce the IS/OOS split.

## Limitations

- **Sample size.** An opening-session strategy takes at most a few
  trades per day and skips many days; confidence intervals on hit rate
  and expectancy are wide at these trade counts.
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

## License

MIT — see [LICENSE](LICENSE).
