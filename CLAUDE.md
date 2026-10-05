# mg: autonomous trading agent (Alpaca, paper by default)

This repo is a trading agent. All trading behaviour lives in the `alpaca-trading` skill (`.claude/skills/alpaca-trading/SKILL.md`). Load it before doing anything that touches the market, the journal or `config/trading.json`.

- Only call the broker through `python3 .claude/skills/alpaca-trading/scripts/agent.py`. Never use raw `curl` and never use MCP order tools. Those bypass the risk gate.
- `config/trading.json` is the only source of risk limits. Edit it only in the weekly review, as described in `references/self-update.md`.
- Commit `journal/` and `state/` after every routine. The kill switch depends on `state/peak.json` persisting.
- Tests: `python3 -m unittest discover -s .claude/skills/alpaca-trading/tests` (stdlib only, Python ≥ 3.11).
- Never commit `.env`.
