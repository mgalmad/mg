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
```

Scheduling: see `.claude/skills/alpaca-trading/references/scheduling.md`.
Not financial advice. Paper-trade until the graduation rule in `config/trading.json` is met.
