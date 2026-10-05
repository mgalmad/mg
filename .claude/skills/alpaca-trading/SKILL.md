---
name: alpaca-trading
description: Autonomous, risk-first trading agent for Alpaca (paper by default). Use for the daily routines (morning research, trade session, end-of-day journal, weekly review), for placing or exiting Alpaca orders, checking account/positions/kill-switch state, analysing the watchlist, reviewing performance, or refreshing the skill's own knowledge of Alpaca, regulation and strategy evidence. Triggers on "research", "trade session", "journal", "weekly review", "buy/sell <ticker>", "flatten", "how is the portfolio doing", "update the trading skill".
---

# Alpaca Trading Agent

The model is the analyst and the record-keeper. It never acts as the risk manager. Each layer guards against a different way of failing:

| Layer | Where | What it stops |
|---|---|---|
| 1. Rules | this file + `config/trading.json` | improvisation |
| 2. Code gate | `scripts/risk.py` (called by `agent.py buy/sell`) | the LLM talking itself past a rule |
| 3. Broker-side exits | bracket orders (stop + target live at Alpaca) | the agent not running when price moves |
| 4. Broker checks | Alpaca buying-power/paper engine | everything else |

**Key design point.** The agent wakes up a few times a day, so an "8% stop" it has to remember to check is not a stop. Every entry goes in as a **bracket order**, which puts the stop at the broker the moment the order fills.

All commands are run from the repo root:

```bash
python3 .claude/skills/alpaca-trading/scripts/agent.py <cmd>
```

Below, `agent` is short for that command. Every command prints JSON. Orders are **dry-run unless `--execute`** is passed. A live endpoint also requires `ALLOW_LIVE_TRADING=yes`.

## Non-negotiable rules

1. Trade only when `clock.is_open` is true. Never trade in the first 15 minutes or the last 10 minutes of the session.
2. Use limit orders only. Entries are placed `entry_offset_pct` above the ask, capped at 0.2%. Exits are placed `exit_offset_pct` below the bid. If the spread is wider than `max_spread_pct`, skip the trade.
3. Every entry is a whole-share **bracket** with `time_in_force: day`. The stop is `min(2×ATR, 8%)` and the target is at 2R. Fractional orders can't carry brackets, so whole shares only.
4. Each trade risks `risk_per_trade_pct` (0.5%) of equity at the stop. The position is then capped by the symbol's `max_allocation_pct` and by `max_position_pct`.
5. Keep at least 20% in cash, hold at most 6 positions, place at most 3 entries a day, and never use margin.
6. **Kill switch:** if the day's loss reaches 2% or the drawdown from peak reaches 10%, stop all new entries. Exits are still allowed. Write in the journal what triggered it. A human resets it.
7. Signals come from `signals.py`. The LLM may **veto** a buy because of news or events (earnings within 2 days, FOMC/CPI day, a halt, a pending M&A deal). It may **never upgrade** a `hold` or `exit` to a buy.
8. Only trade symbols on the watchlist. Never edit `config/trading.json` during a trading routine.
9. Write a journal entry every trading day, including days with no trades.
10. When something is uncertain or a check fails, do nothing and write down why. Doing nothing is a valid trade.

## Routines (US/Eastern; scheduling options are in references/scheduling.md)

### 09:45 Morning research
1. `agent status` → if `clock.is_open` is false (a holiday), write a short journal note, then run `agent heartbeat research` and stop.
2. `agent journal` → creates `journal/YYYY-MM-DD.md` from the template.
3. `agent research` → signals are computed on **completed** daily bars only, because today's partial bar is dropped while the market is open. News comes from the last 48 hours.
4. For each symbol, write one line in the journal: signal, score, the key reason, any news veto, and the planned action. Before deciding, read the last 5 journal entries' *Watch tomorrow* sections and look for anything you flagged then.
5. `agent heartbeat research`.

### 10:00 Trade session
1. `agent status`. If `kill_switch` is not empty, take no new entries. Exits still run.
2. **Exits first:** sell anything that is held and has `signal == exit`. Do it as `agent sell SYM --reason "..."`, review the output, then repeat with `--execute`.
3. **Entries:** go through the `buy` candidates ranked by score, then by lower `ext_atr`. For each one, answer the five questions below, run `agent buy SYM` as a dry run, read `reasons` and `risk_at_stop_pct_equity`, then `agent buy SYM --execute`.
   - What cash and exposure would remain after this trade?
   - Does it add to correlation with what's already held? (SPY, QQQ and IWM are close to one bet.)
   - What does the news say, and is there an event in the next 2 sessions?
   - Is the trend confirmed? (SMA20 > SMA50, price > SMA200, 12-1 momentum > 0)
   - What is lost if the stop is hit (dollars and % of equity), and is that acceptable?
4. Log each decision in the journal's execution table, including skips and the reason for each.
5. `agent heartbeat trade`.

### 16:15 End-of-day journal
1. `agent status`. Fill in *Portfolio status*, fills and P&L.
2. Write the reflection: what was decided, what happened, whether any rule was close to breaking, and what to watch tomorrow.
3. Fill in the *Rule adherence* checklist honestly. A violation counts more than a loss.
4. `agent heartbeat eod`.

### Friday 16:30 Weekly review and self-update
Follow `references/self-update.md` in full. In short:
1. Run `agent review --period 3M` and compare against SPY.
2. Run `agent freshness`, re-verify anything stale, and update the references.
3. Add an entry to `references/lessons.md`.

Parameters change **only** through the procedure in self-update.md, after enough trades, and with the change written down.

## Emergency
`agent flatten --reason "..."` shows what would happen. Adding `--execute` cancels every order and closes every position. Use it when an API or data anomaly appears, when the agent has behaved unexpectedly, or when a human asks for it.

## References (load when needed)
- `references/strategy.md`: why these signals and how sizing works, with the evidence and its limits
- `references/alpaca-api.md`: endpoints, order constraints, data feeds, the MCP server, gotchas
- `references/regulation.md`: the 2026 PDT change, wash sales, notes for non-US (Swiss) residents
- `references/scheduling.md`: running the routines unattended
- `references/self-update.md`: how the skill keeps itself current and learns from the journal
- `references/lessons.md`: the log of reviews and parameter changes
- `references/sources.json`: every external fact, with the date it was last verified

## Related
- **Crypto** (BTC, ETH, CCXT exchanges, backtesting, walk-forward, arbitrage): use the `crypto-trading` skill. Its `backtest.py` / `walk_forward` and the Deflated Sharpe maths also apply to any change to this skill's signal model.
- **Third-party analysis skills** (agiprolabs/claude-trading-skills, MIT): see `.claude/skills/crypto-trading/references/companion-skills.md`. They're useful for analysis such as regimes, volatility, correlation and walk-forward/CPCV. They must never place orders, and this skill's rules win any conflict.
