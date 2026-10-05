# mg: Claude Code trading agent for Alpaca

A risk-first trading agent that runs as a Claude Code skill. It is based on [MindStudio's Claude Code + Alpaca guide](https://www.mindstudio.ai/blog/build-ai-trading-agent-claude-code-alpaca), with that guide's bugs fixed and a self-update loop added.

## Quick start
```bash
cp .env.example .env              # add your Alpaca PAPER keys
python3 .claude/skills/alpaca-trading/scripts/agent.py status
python3 .claude/skills/alpaca-trading/scripts/agent.py research
python3 .claude/skills/alpaca-trading/scripts/agent.py buy SPY          # dry run
python3 -m unittest discover -s .claude/skills/alpaca-trading/tests
```
In Claude Code, say: *"run the morning research routine"*, *"run the trade session"*, *"weekly review"*.

## Crypto (CCXT): `crypto-trading` skill
```bash
pip install ccxt cryptography
C=.claude/skills/crypto-trading/scripts/crypto.py
python3 $C --demo backtest BTC/USD --html state/bt.html   # plumbing check, synthetic data
python3 $C fetch BTC/USD && python3 $C walkforward BTC/USD # the real test (DSR + OOS verdict)
python3 $C run                                           # paper decision cycle (dry run); add --execute
python3 $C arb --symbol BTC/USD                          # depth-aware cross-exchange scan
python3 $C stream --seconds 120                          # WebSocket books + live arb alerts
python3 $C dashboard --html state/crypto_dashboard.html
python3 $C keys-set kraken                               # encrypted keystore (trade-only keys!)
```
Optional companion analysis skills: `/plugin marketplace add agiprolabs/claude-trading-skills`. See `.claude/skills/crypto-trading/references/companion-skills.md` for which ones to use and which to skip.

## Layout
```
CLAUDE.md                         repo rules for the agent
config/trading.json               watchlist + every risk limit (single source of truth)
journal/YYYY-MM-DD.md             daily journal (written by the agent)
state/                            peak equity, trade log, heartbeats (commit these)
.claude/skills/alpaca-trading/
  SKILL.md                        routines and non-negotiable rules
  scripts/agent.py                CLI: status | research | buy | sell | flatten | journal | heartbeat | review | freshness
  scripts/signals.py              trend/momentum model (pure)
  scripts/risk.py                 hard risk gate + kill switch (pure)
  scripts/alpaca.py               stdlib Alpaca REST client
  references/                     strategy evidence, API notes, regulation, scheduling, self-update, lessons
  tests/                          unit + fake-broker integration tests
config/crypto.json                crypto universe, fees, risk limits
.claude/skills/crypto-trading/
  SKILL.md                        crypto expert brief, architecture, non-negotiable rules
  scripts/crypto.py               CLI: fetch | backtest | walkforward | signal | run | arb | stream | mm-quote | dashboard | ...
  scripts/cryptobot/              indicators, strategies, backtest (+DSR), risk, exchange (CCXT), ledger, keystore, stream, arbitrage, alerts, dashboard
  references/                     evidence, backtesting, risk, CCXT, arbitrage/MM, security, Swiss tax, companion skills, self-update
```

Scheduling: see `.claude/skills/alpaca-trading/references/scheduling.md`.
Not financial advice. Paper-trade until the graduation rule in `config/trading.json` is met.
