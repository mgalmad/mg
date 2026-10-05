# Lessons and change log

Newest first. Each weekly review appends an entry like:

```
## YYYY-MM-DD weekly review
- Performance (3M): return x% vs SPY y%, Sharpe s, maxDD d%, orders n
- Rule violations: none / list
- Process fixes: ...
- Hypotheses opened (not acted on): ...
- Parameter changes (old -> new, why, rollback trigger): none
- Knowledge changes: ...
- Swiss turnover check: annualised turnover t× portfolio, median hold h days
```

## 2026-10-05 initial build
- Built from https://www.mindstudio.ai/blog/build-ai-trading-agent-claude-code-alpaca, with these corrections:
  - Source: "verify market status is closed before trading". Corrected: trading requires `clock.is_open == true`.
  - Source gives three conflicting position caps (5% / 10% / 15%). Corrected: one config, `min(symbol cap, max_position_pct)`.
  - Source: the stop-loss is an instruction the agent follows. Corrected: the stop is a broker-side bracket leg. An agent that runs 3×/day cannot enforce a stop.
  - Source sends data/news requests to the trading base URL. Corrected: they go to `data.alpaca.markets`, with news at `/v1beta1/news`.
  - Source: `.claude/routines.json`. Corrected: not a Claude Code file. See scheduling.md.
  - Added: partial-bar exclusion, ATR sizing, kill switch, spread filter, session-edge filter, live-trading interlock, graduation rule, and the self-update loops.
- Knowledge at build: PDT rule removal approved 2026-04-14, effective 2026-06-04, broker deadline 2027-10-20. Alpaca MCP server is v2.
