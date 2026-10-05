# Running the routines unattended

The source article uses `.claude/routines.json`. That file is **not** a Claude Code configuration file, and Claude Code ignores it. Use one of these instead. All times are US/Eastern. Use `CRON_TZ=America/New_York` so DST is handled for you (in Zurich the 09:45 ET run is 15:45 CET/CEST most of the year, except for the weeks when the US and EU DST switch dates differ).

## Option A: Claude Code cloud Routines (no machine to keep on)
Create one Routine per job, each running in a fresh session on this repo, with the API keys set as environment secrets:

| Name | Cron | Prompt |
|---|---|---|
| Trading: research | `CRON_TZ=America/New_York 45 9 * * 1-5` | `Use the alpaca-trading skill. Run the 09:45 morning research routine. Commit journal/ and state/ and push to the working branch.` |
| Trading: session | `CRON_TZ=America/New_York 2 10 * * 1-5` | `Use the alpaca-trading skill. Run the 10:00 trade session routine. Commit journal/ and state/ and push.` |
| Trading: EOD | `CRON_TZ=America/New_York 15 16 * * 1-5` | `Use the alpaca-trading skill. Run the 16:15 end-of-day journal routine. Commit and push.` |
| Trading: weekly review | `CRON_TZ=America/New_York 30 16 * * 5` | `Use the alpaca-trading skill. Run the weekly review and self-update procedure in references/self-update.md. Commit and push.` |

Cloud containers are ephemeral, so **state must be committed** (`journal/`, `state/peak.json`, `state/trades.jsonl`, `state/heartbeat.json`). Otherwise the peak-equity kill switch resets every run.

## Option B: local cron with headless Claude Code
```cron
CRON_TZ=America/New_York
45 9  * * 1-5 cd ~/mg && claude -p "Use the alpaca-trading skill: run the morning research routine." --allowedTools "Bash(python3 .claude/skills/alpaca-trading/scripts/agent.py:*),Read,Write,Edit" >> state/cron.log 2>&1
2  10 * * 1-5 cd ~/mg && claude -p "Use the alpaca-trading skill: run the trade session routine." --allowedTools "Bash(python3 .claude/skills/alpaca-trading/scripts/agent.py:*),Read,Write,Edit" >> state/cron.log 2>&1
15 16 * * 1-5 cd ~/mg && claude -p "Use the alpaca-trading skill: run the end-of-day journal routine." --allowedTools "Bash(python3 .claude/skills/alpaca-trading/scripts/agent.py:*),Read,Write,Edit" >> state/cron.log 2>&1
```
Restricting Bash to the `agent.py` entrypoint is a fourth safety layer: the agent cannot run `curl` against the order endpoint and bypass `risk.py`.

## Monitoring
- `state/heartbeat.json` should have `research`, `trade` and `eod` entries stamped today by 16:30 ET on trading days. If an entry is missing, the run failed.
- Optional: a daily digest. The journal file is the digest, so mail or push it with whatever channel you already use.
