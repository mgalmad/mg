# Alpaca API notes (last verified: see sources.json)

## Hosts
| Purpose | Host |
|---|---|
| Paper trading | `https://paper-api.alpaca.markets` |
| Live trading | `https://api.alpaca.markets` |
| Market data + news (both modes) | `https://data.alpaca.markets` |

A common bug (and one in the source article): sending bars or news requests to the trading host. Data always goes to `data.alpaca.markets`.

## Endpoints used
- `GET /v2/account`: `equity`, `cash`, `last_equity` (prior close, used by the daily-loss kill switch), `buying_power`
- `GET /v2/positions`, `DELETE /v2/positions/{sym}`
- `GET /v2/clock`: `is_open`, `next_open`, `next_close` (handles early closes)
- `GET|POST|DELETE /v2/orders`, `DELETE /v2/orders/{id}`
- `GET /v2/account/portfolio/history`
- `GET /v2/stocks/{sym}/bars`: use `adjustment=all` for split/dividend-adjusted series; `feed=iex` on the free plan
- `GET /v2/stocks/{sym}/quotes/latest`
- `GET /v1beta1/news?symbols=...`

## Order constraints that matter
- **Bracket** (`order_class: bracket`): `take_profit.limit_price` plus `stop_loss.stop_price` (optionally `limit_price`). Requires TIF `day` or `gtc`. **Not allowed in extended hours.**
- **OCO** is for exits only; **OTO** is an entry plus one exit.
- **Fractional/notional**: TIF `day` only, no `gtc`, no brackets, and notional orders can't be replaced. So the skill uses whole shares.
- **Trailing stop**: `trail_percent` or `trail_price`, TIF day/gtc, no extended hours, single orders only.
- **Extended hours**: limit orders only, TIF day/gtc, `extended_hours: true`.
- Price precision: 2 decimals at or above $1, 4 decimals below $1.
- `gtc` orders expire after 90 days.
- Bracket child legs **reserve the shares**. Cancel them before sending a manual exit, otherwise Alpaca rejects it for insufficient quantity. `agent sell` does this automatically.

## Data feed caveat
The free plan uses the **IEX** feed, which is a single venue (low single-digit % of consolidated volume). Daily OHLC from IEX can differ from consolidated SIP prints, especially the high and low. That's fine for ETF trend signals but not for intraday microstructure work. Set `APCA_DATA_FEED=sip` if you have the subscription.

## Official MCP server (optional, for interactive use)
Alpaca MCP server **v2** is a full rewrite (FastMCP + OpenAPI, 60+ tools) and is **not backward compatible with v1**.
```bash
claude mcp add alpaca --scope user --transport stdio uvx alpaca-mcp-server \
  --env ALPACA_API_KEY=... --env ALPACA_SECRET_KEY=...
# optional: --env ALPACA_PAPER_TRADE=true (default) --env ALPACA_TOOLSETS=account,trading,...
```
**Never place orders through the MCP tools in the routines**, because they bypass `risk.py`. Use MCP for read-only exploration. For autonomous runs, consider `ALPACA_TOOLSETS` without trading.

## Env var names
The scripts accept both conventions: `APCA_API_KEY_ID` / `APCA_API_SECRET_KEY` / `APCA_BASE_URL` (SDK style) and `ALPACA_API_KEY` / `ALPACA_SECRET_KEY` (MCP style).
