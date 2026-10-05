# Weekly self-update (Sunday 18:00 UTC)

## 1. Knowledge freshness
1. `cb freshness` lists the sources in `sources.json` that are past `max_age_days`.
2. For each one, re-fetch it and check its `notes` claim. Pay particular attention to:
   - CCXT: run `pip index versions ccxt`, read the changelog for breaking unified-API changes, check which venues have a sandbox and `createStopLossOrder` support, and run `python3 -m unittest discover -s .claude/skills/crypto-trading/tests` after any upgrade.
   - Exchanges: fee tiers, Swiss onboarding, outages or incidents, and any withdrawal halts.
   - agiprolabs/claude-trading-skills: new or changed skills worth adopting. Read them; don't trust them blindly.
   - Swiss tax (ESTV) and FINMA guidance.
   - New peer-reviewed or replicated crypto strategy evidence.
3. Update the references and `last_verified`. Note the changes in `lessons.md`. If a claim can't be verified, write "I don't know" rather than guess.

## 2. Performance learning
1. Run `cb walkforward SYM` on the **freshly fetched** real data for each symbol in the universe. If the verdict flips from pass to fail, cut that symbol's allocation in half and open a review.
2. From the ledger, count the closed trades, the average trade against round-trip cost, and how often each halt or de-risk triggered.
3. Classify each issue as a process bug (fix it now), variance (do nothing) or a model hypothesis (write it down; don't act on it yet).
4. A parameter changes only if: at least 30 closed trades have happened since the last change, the hypothesis was written *before* testing, the walk-forward passes **counting all trials**, only one change is made at a time, and the rollback value is recorded. Limits may be tightened at any time but loosened only with human approval.
5. Swiss check: annualised turnover ÷ portfolio and median holding period, measured against the KS 36 thresholds.
6. Add a dated entry to `lessons.md`.
