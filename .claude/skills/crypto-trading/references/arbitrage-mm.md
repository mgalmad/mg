# Arbitrage and market making: honest evaluation

## Arbitrage
- Detection walks real order-book depth for a given quote size and reports VWAP on both sides, the gross spread, the cost (taker fee × 2, plus transfer cost if any) and the **net bps**. It's actionable only when net ≥ `min_arb_edge_bps`.
- **Execution prerequisites** (none of them are automated, deliberately):
  1. Inventory pre-funded on both venues. Moving coins mid-trade takes minutes to hours.
  2. Both legs placed at the same time as IOC, with a limit equal to the observed VWAP ± tolerance.
  3. Leg risk: if one leg fills and the other doesn't, you hold an unhedged position. You need a rule for unwinding it.
  4. Periodic rebalancing of inventory, whose transfer fees eat the edge.
- Expect to see "opportunities" mostly at times when they can't be executed: a venue with stale data, withdrawals suspended (which is often *why* the price differs), or thin depth. Check the deposit and withdrawal status of both venues before believing a spread.

## Market making
- `MarketMaker.quotes` uses an Avellaneda–Stoikov-style reservation price, skewed by inventory, with a half-spread of at least the maker fee plus a multiple of volatility.
- **You can't backtest it on OHLCV.** Fills depend on queue position and on adverse selection. To evaluate it you need: recorded L2 data and trades, a queue model, and a paper run on a sandbox (`binance` testnet) for at least 2 weeks.
- Viability test: the spread captured per round trip must exceed 2 × maker fee plus the adverse-selection cost (mid-price drift against you after a fill, measured over 1–60 s). With retail maker fees of 10–40 bps (Kraken's entry tier is 40), BTC/USD spreads are usually far too tight. Wider spreads exist only on illiquid pairs, where adverse selection is worst.
