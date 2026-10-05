# Backtesting methodology

## Execution realism (built into backtest.py)
- Signal at bar *t* close, fill at *t+1* **open** ± slippage, with the taker fee charged on both sides.
- If a gap goes through the stop, the stop fills at the **open**, not at the stop price.
- A rebalance band of 10% stops the strategy from paying fees on tiny exposure tweaks.
- The candle that's still forming is dropped at fetch time.

## Pitfalls checklist
- [ ] **Survivorship:** today's top coins weren't the top coins in 2018. Backtest a universe that's fixed at the *start* date.
- [ ] **Exchange-specific history:** wicks on thin venues, and outages (data gaps). Check for gaps longer than 1 bar.
- [ ] **Stablecoin quote:** BTC/USDT returns include USDT credit risk. Prefer USD or USDC on venues that have them.
- [ ] **Regime coverage:** the test must include at least one bear market (2018, 2022) and one sideways year.
- [ ] **Number of trials:** count *every* parameter set you tried, including ones you didn't save.

## Walk-forward (`cb walkforward`)
Rolling windows: train 730 days, then an embargo of 5 days, then a test of 180 days, stepping forward by 180 days. On each fold, the best grid point in-sample (by Sharpe) is evaluated on the unseen test window. The out-of-sample segments are stitched into one equity curve.

## Deflated Sharpe Ratio (Bailey & López de Prado 2014, *J. Portfolio Mgmt* 40(5))
```
SR0  = sqrt(V[SR_trials]) * ((1-γ)·Φ⁻¹(1-1/N) + γ·Φ⁻¹(1-1/(N·e)))      γ = 0.5772…
DSR  = Φ( (SR - SR0) · sqrt(T-1) / sqrt(1 - skew·SR + (kurt-1)/4 · SR²) )
```
- `SR` and `SR_trials` are **per-bar (not annualised)**. `kurt` is raw kurtosis (3 for a normal distribution). `T` is the number of observations and `N` the number of trials.
- **Corrections to common versions:** some guides (including the agiprolabs walk-forward skill) feed in the *annualised* Sharpe and leave out the `sqrt(V[SR_trials])` factor. Doing either one makes DSR far too optimistic, or simply wrong.
- Pass threshold: DSR ≥ 0.95.
- Probability of Backtest Overfitting (PBO) by combinatorially purged cross-validation (CPCV) is a stronger test but costs a lot more compute (see agiprolabs `walk-forward-validation`). Use it before any live deployment of a strategy you tuned heavily.

## Reporting template
For each strategy and symbol, report: CAGR, Sharpe, Sortino, max drawdown, Calmar, number of trades, win rate, profit factor, average trade versus round-trip cost, exposure %, and the same metrics for buy-and-hold. Then the walk-forward verdict. Then a single paragraph on *why the edge should exist*.
