# Strategy: what the edge is, and what it is not

## Thesis
The LLM's advantage is **discipline at scale**: it applies the rules every time, keeps a complete journal and never revenge-trades. It is not an advantage in forecasting. So the signal model is a small, well-documented, slow **trend and momentum** system on liquid ETFs. Its stops and sizing are volatility-aware and its risk is enforced at the broker. Retail investors who trade often underperform mostly because of turnover and behaviour (Barber & Odean 2000, *J. Finance* 55(2)). The design targets those two leaks directly.

## Signal components (scripts/signals.py)
| Component | Rule | Evidence | Known failure mode |
|---|---|---|---|
| Regime filter | price > SMA200 | Faber 2007, "A Quantitative Approach to Tactical Asset Allocation" (SSRN 962461) | whipsaws in sideways markets; misses V-shaped rebounds |
| Trend | SMA20 > SMA50 | Hurst, Ooi & Pedersen 2017, "A Century of Evidence on Trend-Following Investing" (*JPM*) | lag; late entry, late exit |
| Momentum | 12-1 month return > 0 | Jegadeesh & Titman 1993 (*J. Finance* 48(1)); Moskowitz, Ooi & Pedersen 2012, "Time Series Momentum" (*JFE* 104(2)) | **momentum crashes** in sharp rebounds after bear markets (Daniel & Moskowitz 2016, *JFE* 122(2)) |
| Overextension guard | RSI14 > 75 or > 3 ATR above SMA20 → wait | practitioner heuristic, **not** strong academic evidence | can miss strong breakouts; that cost is accepted |
| News | veto only | LLM headline sentiment had predictive power early on (Lopez-Lira & Tang 2023, SSRN 4412788), but published edges decay once crowded | hallucinated or stale context, so news never *creates* a trade |

Score: regime ±(1/−2), trend ±1, momentum ±1. **buy** = score ≥ 2 and not overextended. **exit** = score ≤ −1. Otherwise **hold**.

## Sizing and exits
- Each trade risks a fixed fraction: qty = (equity × 0.5%) / (2 × ATR14), then capped by allocation. This is volatility-normalised, so a calm ETF gets a bigger position than a volatile one.
- Stop = min(2 ATR, 8%). Target = 2R. Both are **broker-side** via the bracket.
- A trend exit (signal turns to `exit`) can happen before the stop does. Whichever comes first wins.

## Contrarian views to keep in mind
- **Volatility targeting may not survive out of sample.** Moreira & Muir 2017 (*J. Finance* 72(4)) found gains. Cederburg, O'Doherty, Wang & Yan 2020 (*JFE* 138(1)) found most of the improvement disappears out of sample. Here ATR sizing is used for **risk control**, not as an alpha source.
- **Buy-and-hold SPY is the honest benchmark.** If after 60+ sessions the system trails SPY on a risk-adjusted basis *and* its drawdown is no better, the right answer may be to trade less, not to add indicators.
- **Overfitting is the default outcome of tuning.** Each parameter tweak is another trial. Use the Deflated Sharpe Ratio idea (Bailey & López de Prado 2014, *JPM* 40(5)) and require t > 3 for any "new factor" (Harvey, Liu & Zhu 2016, *RFS* 29(1)). With fewer than 50 trades, no parameter change is justified by performance alone.

## Ideas for later (speculative; paper-test only, one at a time)
- Cross-asset momentum rotation: hold the top N of the watchlist by 12-1 momentum, monthly. Lower turnover, and better evidenced than daily signals.
- A regime overlay from credit spreads or VIX term structure (contango vs backwardation) as an extra risk-off switch.
- A two-agent "trader vs risk reviewer" debate before execution (the pattern from the source article) for high-impact trades.
- Options overlays (covered calls) only once the equity system has graduated.
