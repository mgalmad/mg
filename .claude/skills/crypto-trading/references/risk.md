# Risk system

## Sizing
`units = min( equity·risk% · mult / stop_dist , equity·alloc% / price , free_cash / price )`
- `risk%` is 1% of equity lost if the stop is hit. The stop sits 2.5–3 ATR away, so it isn't triggered by ordinary noise.
- `alloc%` is the symbol's cap × the strategy's target exposure (volatility-scaled).
- **Fractional Kelly** (`risk.kelly_fraction`) works as an *upper bound* on risk%, using ¼-Kelly capped at 2%. Estimates of win rate and payoff from fewer than 30 trades are noise. Full Kelly has a high chance of a 50%+ drawdown even when the edge is real.

## Circuit breakers (adapted from agiprolabs `risk-management`, tightened for a long-only spot book)
| Trigger | Action |
|---|---|
| 3 consecutive losses | size × 0.5 |
| 5 consecutive losses | size × 0.25 |
| 7 consecutive losses | halt entries, human review |
| realised vol > 2× its 180-bar average | size × 0.5 |
| drawdown ≥ 10% from peak | size × 0.5 |
| daily loss ≥ 4% (UTC day) | halt entries until the next UTC day |
| drawdown ≥ 20% | halt entries; human review before reset |

Recovery asymmetry: −20% needs +25% to recover, and −50% needs +100%. This is why the halts sit where they do.

## Exposure
- Cash reserve of at least 30%. Maximum 30% in BTC, 20% in ETH, 8% in other large caps (`config/crypto.json`).
- Treat crypto as **one correlated bucket** in a crash: BTC and ETH correlation goes above 0.8 under stress. Diversification across coins doesn't stand in for cash.

## Crypto-specific risks (not covered by price stops)
- **Exchange or custody failure** (Mt. Gox 2014, FTX 2022): the `max_per_exchange_pct` counterparty cap plus self-custody of profits.
- **Stablecoin depeg** (UST 2022, USDC's brief depeg in March 2023): spread cash across USD, USDC and fiat, and don't leave it parked in a single stablecoin.
- **API key compromise:** keys with withdrawals disabled limit the damage to trades made against you.
- **Exchange outages during crashes:** bot-side stops can't fire if the API is down. Use native stop orders where the venue supports them, and keep size small enough to survive a gap.
- **Weekend and holiday liquidity:** spreads widen. The `max_spread_bps` filter blocks entries when they do.
