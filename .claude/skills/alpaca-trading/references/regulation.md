# Regulation and tax notes (not legal or tax advice; verify before relying on any of it)

## US: Pattern Day Trader rule replaced (2026)
- The SEC approved FINRA's removal of the PDT designation and the $25,000 minimum on **14 Apr 2026**. FINRA set the **effective date at 4 Jun 2026**. Brokers have until **20 Oct 2027** to implement it.
- The replacement is an intraday margin framework based on real-time exposure, for margin accounts above $2,000. Day trades are no longer counted.
- **Whether Alpaca has switched yet: I don't know.** Check the Alpaca changelog and account fields (`pattern_day_trader`, `daytrade_count`) during the weekly self-update. This skill is a swing system (holding for days to weeks) and uses no margin, so the PDT rule rarely binds anyway.
- Sources: https://international.schwab.com/story/sec-approves-scrapping-25000-day-trader-minimum · https://us.etrade.com/knowledge/library/margin/pattern-day-trading-rule-change

## Algorithmic trading
SEC and FINRA regulate algorithmic trading. Rules are heavier for professionals and registered entities, while personal accounts mostly face broker terms of service. Don't run strategies that look like spoofing or layering (placing and cancelling orders to move price). Limit orders that are cancelled because they don't fill are normal.

## Wash sales (US taxpayers only)
Selling at a loss and buying back the same or a substantially identical security within 30 days disallows the loss. The journal should flag re-entries within 30 days of a losing exit.

## Swiss residents (relevant to the owner of this repo)
- **Professional securities trader classification:** private capital gains are normally tax-free in Switzerland. The ESTV Kreisschreiben Nr. 36 (27 Jul 2012; https://kanton.baselland.ch/finanz-und-kirchendirektion/steuerverwaltung-kurzmitteilungen/2012/476/downloads-1/476_beilage.pdf) safe-harbour criteria are holding period ≥ 6 months, annual transaction volume ≤ 5× portfolio value, gains < 50% of taxable income, no debt financing, and derivatives only for hedging. Frequent automated trading can fail these. If it does, gains can become taxable income and subject to AHV contributions. **A high-turnover bot is a tax decision, not just a trading one.** Track turnover and holding periods in the weekly review.
- US dividends: 15% withholding under the US–CH treaty with a W-8BEN on file. It is reclaimable or creditable via form DA-1. Verify with your tax adviser.
- US estate-tax exposure for non-residents holding US-situs assets (US-domiciled ETFs and stocks) above the US threshold can matter. The US–CH estate tax treaty gives a pro-rata credit. Irish-domiciled UCITS ETFs avoid this, but they are not tradable on Alpaca.
- **Whether Alpaca accepts Swiss-resident individual accounts right now: I don't know.** Check on alpaca.markets before funding. Paper trading works regardless of residence.
