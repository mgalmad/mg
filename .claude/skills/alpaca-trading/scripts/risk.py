"""Hard risk gate. Every order passes here before it reaches the broker.

The limits come from config/trading.json and nothing else. The LLM cannot
loosen them at runtime. Pure functions: easy to unit test.
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field


@dataclass
class Portfolio:
    equity: float
    cash: float
    last_equity: float          # prior session close equity (Alpaca account.last_equity)
    peak_equity: float          # high-water mark, tracked in state/peak.json
    positions: dict[str, float] = field(default_factory=dict)  # symbol -> market value
    trades_today: int = 0


@dataclass
class Verdict:
    ok: bool
    reasons: list[str]
    qty: int = 0


def size_position(equity: float, price: float, atr: float, limits: dict, max_alloc_pct: float) -> int:
    """Volatility-based sizing: risk a fixed % of equity per trade at a stop k*ATR away,
    then cap by the per-symbol allocation limit. Whole shares (brackets reject fractional)."""
    stop_dist = limits["stop_atr_mult"] * atr
    if stop_dist <= 0 or price <= 0:
        return 0
    risk_qty = (equity * limits["risk_per_trade_pct"] / 100) / stop_dist
    cap_qty = (equity * min(max_alloc_pct, limits["max_position_pct"]) / 100) / price
    return max(0, math.floor(min(risk_qty, cap_qty)))


def stop_and_target(side: str, entry: float, atr: float, limits: dict) -> tuple[float, float]:
    """Stop at k*ATR, but never wider than the hard max_stop_pct. Target at reward:risk."""
    dist = min(limits["stop_atr_mult"] * atr, entry * limits["max_stop_pct"] / 100)
    rr = limits["reward_risk"]
    if side == "buy":
        return round(entry - dist, 2), round(entry + rr * dist, 2)
    return round(entry + dist, 2), round(entry - rr * dist, 2)


def kill_switch(p: Portfolio, limits: dict) -> list[str]:
    """Conditions that block ALL new entries (exits stay allowed)."""
    why = []
    if p.last_equity > 0:
        day_pnl = (p.equity - p.last_equity) / p.last_equity * 100
        if day_pnl <= -limits["daily_loss_halt_pct"]:
            why.append(f"daily loss {day_pnl:.2f}% hit halt -{limits['daily_loss_halt_pct']}%")
    if p.peak_equity > 0:
        dd = (p.equity - p.peak_equity) / p.peak_equity * 100
        if dd <= -limits["max_drawdown_halt_pct"]:
            why.append(f"drawdown {dd:.2f}% from peak hit halt -{limits['max_drawdown_halt_pct']}%")
    if p.trades_today >= limits["max_trades_per_day"]:
        why.append(f"max trades/day ({limits['max_trades_per_day']}) reached")
    return why


def session_window(minutes_since_open: float, minutes_to_close: float, limits: dict) -> list[str]:
    """Opening auction noise and closing imbalance flows make spreads and fills worst at the edges."""
    why = []
    if minutes_since_open < limits.get("no_trade_open_min", 15):
        why.append(f"within first {limits.get('no_trade_open_min', 15)} min of session")
    if minutes_to_close < limits.get("no_trade_close_min", 10):
        why.append(f"within last {limits.get('no_trade_close_min', 10)} min of session")
    return why


def validate(side: str, symbol: str, qty: int, limit_price: float, quote: dict,
             p: Portfolio, limits: dict, max_alloc_pct: float, allowed: set[str],
             market_open: bool, minutes_since_open: float = 999, minutes_to_close: float = 999) -> Verdict:
    r: list[str] = []
    if not market_open:
        r.append("market is not open (clock.is_open=false)")
    else:
        r += session_window(minutes_since_open, minutes_to_close, limits)
    if symbol not in allowed:
        r.append(f"{symbol} not in watchlist")
    if qty <= 0:
        r.append("qty must be > 0")
    if side == "buy":
        r += kill_switch(p, limits)
        value = qty * limit_price
        cur = p.positions.get(symbol, 0.0)
        cap = min(max_alloc_pct, limits["max_position_pct"])
        if (cur + value) / p.equity * 100 > cap + 1e-9:
            r.append(f"{symbol} would be {(cur + value) / p.equity:.1%} of equity > cap {cap}%")
        invested = sum(p.positions.values())
        if (invested + value) / p.equity * 100 > 100 - limits["cash_reserve_pct"] + 1e-9:
            r.append(f"gross exposure would exceed {100 - limits['cash_reserve_pct']}% (cash reserve {limits['cash_reserve_pct']}%)")
        if value > p.cash:
            r.append(f"order value {value:.2f} > cash {p.cash:.2f} (no margin)")
        if len([s for s, v in p.positions.items() if v > 0]) >= limits["max_open_positions"] and symbol not in p.positions:
            r.append(f"max open positions ({limits['max_open_positions']}) reached")
        ask = quote.get("ap") or 0
        if ask > 0 and limit_price > ask * (1 + limits["max_limit_slippage_pct"] / 100):
            r.append(f"limit {limit_price} more than {limits['max_limit_slippage_pct']}% above ask {ask}")
    else:
        bid = quote.get("bp") or 0
        if bid > 0 and limit_price < bid * (1 - limits["max_limit_slippage_pct"] / 100):
            r.append(f"limit {limit_price} more than {limits['max_limit_slippage_pct']}% below bid {bid}")
    bid, ask = quote.get("bp") or 0, quote.get("ap") or 0
    if bid > 0 and ask > 0:
        spread = (ask - bid) / ((ask + bid) / 2) * 100
        if spread > limits["max_spread_pct"]:
            r.append(f"spread {spread:.2f}% > {limits['max_spread_pct']}%: illiquid right now")
    return Verdict(ok=not r, reasons=r, qty=qty)
