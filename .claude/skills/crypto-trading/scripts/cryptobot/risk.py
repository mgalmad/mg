"""Hard risk gate for crypto orders. Pure functions; limits come from config/crypto.json only.

Crypto-specific additions over the equity gate:
  - counterparty cap per exchange (custody risk: Mt.Gox, FTX)
  - stablecoin quote risk (a depeg is a loss on 'cash')
  - consecutive-loss and volatility-spike de-risking
  - stale-data and min-notional checks (exchange market limits)
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field


@dataclass
class Book:
    equity: float                      # total equity in quote currency, all venues
    free_quote: float                  # free quote balance on the target exchange
    exchange_equity: float             # equity held on the target exchange
    day_start_equity: float            # equity at 00:00 UTC (crypto never closes)
    peak_equity: float
    positions: dict[str, float] = field(default_factory=dict)  # symbol -> quote value
    consecutive_losses: int = 0
    orders_today: int = 0
    total_capital: float | None = None  # all crypto/cash you own incl. cold storage; enables counterparty cap


@dataclass
class Verdict:
    ok: bool
    reasons: list[str]
    size_mult: float = 1.0


def kelly_fraction(win_rate: float, payoff: float, fraction: float = 0.25, cap: float = 0.02) -> float:
    """Fractional Kelly as an UPPER BOUND on risk per trade, never a target.
    Full Kelly f* = p - (1-p)/b. Estimation error in p and b makes full Kelly ruinous in practice,
    so take a quarter and cap at `cap`. Returns 0 when the edge is negative."""
    if payoff <= 0:
        return 0.0
    f = win_rate - (1 - win_rate) / payoff
    return max(0.0, min(cap, f * fraction))


def de_risk_multiplier(b: Book, limits: dict, vol_now: float | None = None, vol_avg: float | None = None) -> float:
    m = 1.0
    if b.consecutive_losses >= limits["loss_streak_min_size"]:
        m = min(m, 0.25)
    elif b.consecutive_losses >= limits["loss_streak_half_size"]:
        m = min(m, 0.5)
    if vol_now and vol_avg and vol_now > limits["vol_spike_mult"] * vol_avg:
        m = min(m, 0.5)
    if b.peak_equity > 0 and (b.equity / b.peak_equity - 1) * 100 <= -limits["drawdown_reduce_pct"]:
        m = min(m, 0.5)
    return m


def size_order(b: Book, price: float, stop_dist: float, limits: dict, max_alloc_pct: float, mult: float = 1.0) -> float:
    """Units to buy: risk_per_trade of equity at the stop, capped by allocation and free cash."""
    if price <= 0 or stop_dist <= 0:
        return 0.0
    risk_units = b.equity * limits["risk_per_trade_pct"] / 100 * mult / stop_dist
    cap_units = b.equity * min(max_alloc_pct, limits["max_position_pct"]) / 100 / price
    cash_units = b.free_quote / (price * (1 + limits["fee_bps"] / 1e4))
    return max(0.0, min(risk_units, cap_units, cash_units))


def halts(b: Book, limits: dict) -> list[str]:
    why = []
    if b.day_start_equity > 0:
        d = (b.equity / b.day_start_equity - 1) * 100
        if d <= -limits["daily_loss_halt_pct"]:
            why.append(f"daily loss {d:.2f}% <= -{limits['daily_loss_halt_pct']}% (UTC day)")
    if b.peak_equity > 0:
        dd = (b.equity / b.peak_equity - 1) * 100
        if dd <= -limits["max_drawdown_halt_pct"]:
            why.append(f"drawdown {dd:.2f}% <= -{limits['max_drawdown_halt_pct']}%")
    if b.consecutive_losses >= limits["loss_streak_halt"]:
        why.append(f"{b.consecutive_losses} consecutive losses: halt and review")
    if b.orders_today >= limits["max_orders_per_day"]:
        why.append("max orders per day reached")
    return why


def validate_buy(symbol: str, units: float, price: float, ticker: dict, market: dict, b: Book, limits: dict,
                 max_alloc_pct: float, allowed: set[str], data_age_s: float) -> Verdict:
    r = list(halts(b, limits))
    if symbol not in allowed:
        r.append(f"{symbol} not in universe")
    notional = units * price
    if units <= 0:
        r.append("size computed to 0")
    cap = min(max_alloc_pct, limits["max_position_pct"])
    if b.equity and (b.positions.get(symbol, 0) + notional) / b.equity * 100 > cap + 1e-9:
        r.append(f"position would exceed {cap}% of equity")
    if b.equity and (sum(b.positions.values()) + notional) / b.equity * 100 > 100 - limits["cash_reserve_pct"] + 1e-9:
        r.append(f"gross exposure would breach {limits['cash_reserve_pct']}% cash reserve")
    if b.total_capital and (b.exchange_equity + notional) / b.total_capital * 100 > limits["max_per_exchange_pct"] + 1e-9:
        r.append(f"exchange would hold > {limits['max_per_exchange_pct']}% of total capital (counterparty cap)")
    mins = (market.get("limits") or {})
    min_cost = (mins.get("cost") or {}).get("min") or 0
    min_amt = (mins.get("amount") or {}).get("min") or 0
    if notional < max(min_cost, limits["min_notional"]) or units < min_amt:
        r.append(f"below exchange/config minimum (notional {notional:.2f}, units {units})")
    bid, ask = ticker.get("bid"), ticker.get("ask")
    if bid and ask:
        spread_bps = (ask - bid) / ((ask + bid) / 2) * 1e4
        if spread_bps > limits["max_spread_bps"]:
            r.append(f"spread {spread_bps:.1f} bps > {limits['max_spread_bps']}")
        if price > ask * (1 + limits["max_slippage_bps"] / 1e4):
            r.append("limit price too far above ask")
    else:
        r.append("no bid/ask: refusing to trade blind")
    if data_age_s > limits["max_data_age_s"]:
        r.append(f"market data {data_age_s:.0f}s old > {limits['max_data_age_s']}s")
    return Verdict(ok=not r, reasons=r)


def round_down(x: float, step: float) -> float:
    return math.floor(x / step) * step if step else x
