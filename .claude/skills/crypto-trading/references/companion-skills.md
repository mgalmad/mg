# Companion skills: agiprolabs/claude-trading-skills

Source: https://github.com/agiprolabs/claude-trading-skills (MIT, 68 skills, needs `uv` and Python ≥ 3.9). Install:
```bash
/plugin marketplace add agiprolabs/claude-trading-skills
/plugin install trading-skills@agiprolabs-claude-trading-skills
```
Or copy only selected folders: `git clone ... && cp -r claude-trading-skills/skills/<name> .claude/skills/`. **Read every file before installing.** They are third-party instructions and code that will run with your permissions.

## Worth adding for this setup
| Skill | Use it for | Notes |
|---|---|---|
| `walk-forward-validation` | CPCV / PBO before going live | Use the DSR from *our* `backtesting.md`. Their formula uses the annualised SR and leaves out the trial-variance term |
| `vectorbt` | fast parameter sweeps | count every sweep as trials for the DSR |
| `regime-detection`, `volatility-modeling` | HMM regimes, GARCH/EWMA vol | candidate improvements to the vol targeting. Paper-test one at a time |
| `correlation-analysis`, `portfolio-analytics` | portfolio-level risk | |
| `slippage-modeling`, `market-microstructure-traditional` | calibrating `slippage_bps`, evaluating MM | |
| `ohlcv-processing` | finding gaps and outliers in fetched data | |
| `coingecko-api`, `defillama-api` | universe selection, market-wide context | |
| `custom-indicators` | MVRV, NVT, exchange flows | only as regime or veto inputs |
| `cost-basis-engine`, `trade-journal`, `crypto-tax-export` | bookkeeping | skip the US-only tax outputs |

## Not recommended here
- PumpFun, copy-trading, Jito/MEV, shredstream, and memecoin tooling: very high variance and adversarial microstructure. They don't fit "capital preservation first".
- Prediction markets (Kalshi/Polymarket): a different product. Kalshi isn't available to non-US residents.
- US tax skills (wash sale, Form 8949) don't apply to a Swiss resident.

## Precedence
If a companion skill conflicts with this skill's non-negotiable rules or with `config/crypto.json`, **this skill wins**. Companion skills are for analysis. Orders go only through `crypto.py`.
