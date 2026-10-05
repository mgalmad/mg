"""Cross-exchange arbitrage DETECTION on executable depth, net of all costs.

Reality check (Makarov & Schoar, JFE 2020): large, persistent crypto price gaps are mostly
ACROSS countries/fiat rails (capital controls), not between liquid venues in the same region,
where spreads are arbitraged within seconds by colocated firms. Retail-viable cases need
PRE-FUNDED inventory on both venues (no transfers mid-trade) and IOC on both legs.
The detector therefore reports only what the books can actually fill at size.
"""
from __future__ import annotations


def walk_book(levels: list[list[float]], quote_amount: float | None = None, base_amount: float | None = None):
    """VWAP and filled base units when consuming `levels` ([[price, size], ...]) best-first."""
    filled_base = spent = 0.0
    for price, size in levels:
        take = size
        if base_amount is not None:
            take = min(size, base_amount - filled_base)
        elif quote_amount is not None:
            take = min(size, (quote_amount - spent) / price)
        if take <= 0:
            break
        filled_base += take
        spent += take * price
    return (spent / filled_base if filled_base else None), filled_base


def best_opportunity(books: dict, fees_bps: dict, size_quote: float, min_edge_bps: float = 10.0,
                     transfer_cost_quote: float = 0.0) -> dict | None:
    """books: {exchange: {'bids': [[p, s]...], 'asks': [[p, s]...]}}; buy on A's asks, sell into B's bids."""
    best = None
    for a, ba in books.items():
        for b, bb in books.items():
            if a == b:
                continue
            buy_px, base = walk_book(ba["asks"], quote_amount=size_quote)
            if not buy_px:
                continue
            sell_px, sold = walk_book(bb["bids"], base_amount=base)
            if not sell_px or sold < base * 0.999:
                continue  # not enough depth on the sell side
            gross = (sell_px / buy_px - 1) * 1e4
            cost = fees_bps.get(a, 0) + fees_bps.get(b, 0) + transfer_cost_quote / size_quote * 1e4
            net = gross - cost
            opp = {"buy_on": a, "sell_on": b, "base_units": base, "buy_vwap": buy_px, "sell_vwap": sell_px,
                   "gross_bps": gross, "cost_bps": cost, "net_bps": net,
                   "net_profit_quote": base * sell_px - base * buy_px - cost / 1e4 * size_quote,
                   "actionable": net >= min_edge_bps}
            if best is None or opp["net_bps"] > best["net_bps"]:
                best = opp
    return best
