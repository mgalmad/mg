# What works in crypto (evidence, limits, contrarian views)

| Strategy | Evidence | Why it might persist | How it fails |
|---|---|---|---|
| **Time-series momentum** (core) | Liu & Tsyvinski 2021, "Risks and Returns of Cryptocurrency", *RFS* 34(6): momentum predicts returns at 1–8 week horizons. Liu, Tsyvinski & Wu 2022, "Common Risk Factors in Cryptocurrency", *J. Finance* 77(2): market, size and momentum factors explain the cross-section | slow information diffusion, retail herding, reflexive flows | sharp V-shaped reversals; chop after bubbles; crowding as institutions arrive |
| **Mean reversion** (diversifier) | weaker and less stable than momentum; mostly works intraday on liquid pairs and in ranges | liquidity provision to forced sellers (liquidation cascades) | trending regimes. That's why the Hurst < 0.55 and price > SMA200 filters exist |
| **Market making** | Avellaneda & Stoikov 2008, "High-frequency trading in a limit order book", *Quant. Finance* 8(3) | earns the spread plus maker rebates | adverse selection from informed flow; inventory risk in trends; retail latency and fees usually make it negative |
| **Cross-exchange arbitrage** | Makarov & Schoar 2020, "Trading and arbitrage in cryptocurrency markets", *JFE* 135(2): large gaps exist *across countries* because of capital controls, and are small *within* regions | segmented fiat rails | it's gone before a retail order lands; transfer time and withdrawal fees; frozen withdrawals |

## Design consequences
- Daily bars and slow signals. Retail has no latency edge, so don't compete where latency decides who wins.
- Volatility-scaled exposure (vol target 60% a year). BTC's realised vol moves between about 30% and 100%+, so constant-notional sizing is really a bet on volatility.
- A **trend filter plus breakout** (EMA cross + Donchian) over pure EMA crosses: it cuts whipsaw trades, and each one costs about 1% round trip at retail fees.
- A universe of large, liquid pairs only. Small caps add survivorship bias to backtests and slippage to live trading.

## Contrarian and cutting-edge (speculative; paper-test only, one at a time)
- **Buy-and-hold BTC with a 200-day filter** often beats complex bots after costs. Always run it as the benchmark.
- **Halving-cycle seasonality**: the sample is about 4 cycles, n is tiny, and it's probably already priced in. Don't trade it.
- **On-chain signals** (MVRV, exchange netflows, stablecoin supply): informative at cycle extremes, noisy elsewhere, and the data is often revised. The agiprolabs `custom-indicators` skill computes these.
- **Funding rate and basis** (perpetuals): a real carry premium, but it needs derivatives and margin, which is out of scope until you approve it.
- **LLM news or sentiment** as a *veto* (event risk: hacks, depegs, regulatory actions), never as a trade signal.
