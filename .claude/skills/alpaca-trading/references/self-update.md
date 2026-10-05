# Self-update procedure (weekly, Friday after the close)

The skill stays current through two loops. They are kept separate so that new *knowledge* never gets mistaken for proof of a better *strategy*.

## Loop 1: knowledge freshness (external facts)
1. `agent freshness` lists every entry in `sources.json` older than its `max_age_days`.
2. For each stale source, fetch the URL and check the claim in `notes`. Look in particular for:
   - Alpaca changelog: new or removed endpoints, order-class changes, PDT implementation, data-feed or plan changes, MCP server major versions.
   - Regulation: PDT/intraday margin rollout, and Swiss ESTV guidance.
   - New, **peer-reviewed or replicated** evidence on trend, momentum and volatility sizing. Blog posts and backtests on social media don't count.
3. Update the relevant `references/*.md`. If a script is affected (an endpoint changed, say), fix it and run `python3 -m unittest discover -s .claude/skills/alpaca-trading/tests`.
4. Set `last_verified` to today. Where a fact has changed, record it in `lessons.md` under **Knowledge changes**.
5. If a source can't be verified, leave `last_verified` alone and write "I don't know / could not verify" rather than guessing.

## Loop 2: performance learning (internal evidence)
1. Run `agent review --period 3M` and write down total return vs SPY, Sharpe, max drawdown and number of orders.
2. Read the week's journals. Tally rule violations, vetoes and their outcomes, skipped trades and what they would have done, and stops vs targets hit.
3. Classify each issue:
   - **Process bug** (a rule was broken, the script misbehaved, a fill was bad): fix it now.
   - **Variance** (the process was right and the outcome was bad): **do nothing.**
   - **Possible model flaw**: open a hypothesis in `lessons.md`. Don't act on it yet.
4. **Parameter change gate.** Every condition must hold:
   - at least 50 closed trades since the last change to that parameter
   - the hypothesis was written down *before* looking at the data that tests it
   - the change makes sense from first principles, not just from fitting the data
   - an out-of-sample test (walk-forward, using the crypto skill's `backtest.walk_forward` on daily ETF bars) passes, with a Deflated Sharpe ≥ 0.95 **counting every variant tried**
   - only one parameter changes at a time, and the old value is recorded so it can be rolled back
   - risk limits may be **tightened** at any time but **loosened** only with explicit human approval in the journal
5. Add a dated entry to `lessons.md`.
6. Check turnover and holding periods against the Swiss professional-trader criteria (regulation.md) and flag any drift.

## Things that never self-update
- The non-negotiable rules in SKILL.md and the existence of the kill switch
- Paper to live: needs the graduation rule in `config/trading.json` **and** a human
