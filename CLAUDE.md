# mg: autonomous trading agents (paper by default)

Two skills, each with its own risk gate. Load the relevant one before touching markets, journals or configs:

| Skill | Markets | Entrypoint | Limits |
|---|---|---|---|
| `alpaca-trading` | US ETFs/stocks via Alpaca | `python3 .claude/skills/alpaca-trading/scripts/agent.py` | `config/trading.json` |
| `crypto-trading` | crypto via CCXT (Kraken default) | `python3 .claude/skills/crypto-trading/scripts/crypto.py` | `config/crypto.json` |

- Only call brokers or exchanges through those entrypoints. Never use raw `curl`, MCP order tools, or third-party skills to place orders, because they bypass the risk gates.
- Edit config limits only during the weekly review (each skill's `references/self-update.md`). Limits may be tightened at any time; loosening them needs human approval.
- Commit `journal/` and `state/` after every routine. Kill switches depend on the peak/day state persisting. The crypto ledger is hash-chained, so never edit it by hand.
- Tests (stdlib + ccxt): `python3 -m unittest discover -s .claude/skills/alpaca-trading/tests` and `python3 -m unittest discover -s .claude/skills/crypto-trading/tests`.
- Never commit `.env`, API keys or `~/.cryptobot/keys.enc`.
