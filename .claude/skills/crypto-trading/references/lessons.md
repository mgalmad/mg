# Lessons and change log (newest first)

## 2026-10-05 initial build
- Scope comes from the user's crypto-expert brief: CCXT, momentum, mean reversion and market making, risk, backtesting, WebSockets, arbitrage, dashboards, encrypted keys, audit logs and alerts.
- Ideas adopted from agiprolabs/claude-trading-skills: the circuit-breaker ladder, fractional Kelly, the Hurst filter, `--demo` mode, walk-forward with an embargo.
- Corrections to agiprolabs: the DSR must use the per-bar Sharpe and the sqrt(V[SR_trials]) term.
- Demo backtests (synthetic regime-switching data, seed by symbol) are **only plumbing checks**. The generator has no edge built in, so their metrics mean nothing.
- Real-data walk-forward hasn't been run yet: the build container had no exchange network access. **That's the first task on the user's machine:** `cb fetch BTC/USD && cb walkforward BTC/USD`.
- ccxt 4.5.85: kraken has no sandbox and no unified createStopLossOrder, so it runs with PaperBroker plus bot-side stops.
