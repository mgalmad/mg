# CCXT integration notes (verified against ccxt 4.5.85; recheck weekly)

- `pip install ccxt` installs both REST and WebSockets. **ccxt.pro has been bundled since v4**, so `import ccxt.pro` is free.
- Always construct exchanges with `enableRateLimit: True`. Keep one exchange instance per process, because rate-limit state is per instance.
- Use unified symbols such as `BTC/USD`, `ETH/USDT`, and `BTC/USDT:USDT` for perpetuals.
- `fetch_ohlcv(symbol, tf, since, limit)` returns `[ts, o, h, l, c, v]`. Paginate with `since`. The last candle is still forming, so drop it.
- Round to the exchange's precision with `amount_to_precision` / `price_to_precision`. Check `market['limits']['amount'|'cost']['min']`.
- **Retryable errors:** `NetworkError`, `RequestTimeout`, `ExchangeNotAvailable`, `RateLimitExceeded`, with exponential backoff and jitter. **Errors that must never be retried:** `AuthenticationError`, `InsufficientFunds`, `InvalidOrder`, `BadSymbol`.
- **Idempotency:** pass `clientOrderId` in params. After an ambiguous failure, look it up in open and closed orders before resubmitting (`exchange.limit_order`).
- Sandboxes: call `set_sandbox_mode(True)` right after construction. **Only some venues have one.** In ccxt 4.5.85, `binance` and `alpaca` (crypto paper) have test URLs, while `kraken`, `bitstamp` and `coinbase` don't. For those, use the built-in `PaperBroker` with live public data.
- Native stop orders (`has['createStopLossOrder']`): `binance` is true, while `kraken`, `bitstamp`, `coinbase` and `alpaca` are false or unified-unsupported. For those, `LiveBroker` keeps **bot-side stops**, so run `cb run --execute` at least hourly while holding positions.
- Fees: `fetch_trading_fee(symbol)` where it's supported (kraken, bitstamp, binance), falling back to `market['taker']`. **Kraken Pro entry tier (verified 2026-10-05): taker 0.80%, maker 0.40%**, so a round trip costs 1.6% plus slippage. Config `fee_bps` is 80. The consequences: trade rarely (daily or weekly signals), prefer post-only maker entries when urgency is low, and compare venues' fee tiers before choosing an exchange.
- WebSockets: `await ex.watch_order_book(sym, depth)` in a loop. Reconnect with backoff, call `await ex.close()` on exit, and treat a feed with no update for more than `max_data_age_s` as stale.

## Exchange choice for a Swiss resident (verify availability)
Kraken, Bitstamp and Coinbase all have CHF and/or EUR rails and established compliance. If you want a Swiss-regulated venue for custody of long-term holdings, consider a Swiss bank or broker that offers crypto, separately from the trading venue. Before deciding, check the current FINMA status and fees of each venue yourself. **I don't know** which venues currently onboard Swiss residents on which product tiers.
