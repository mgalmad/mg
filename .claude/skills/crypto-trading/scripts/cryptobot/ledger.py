"""Tamper-evident trade log + paper broker.

Every event is one JSON line carrying sha256(prev_line). `verify()` detects any edited,
deleted or reordered line, which is useful for audit trails and for trusting your own stats.
"""
from __future__ import annotations

import hashlib
import json
import time
from pathlib import Path


class Ledger:
    def __init__(self, path: Path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)

    def _last_hash(self) -> str:
        if not self.path.exists():
            return "0" * 64
        last = ""
        with open(self.path) as f:
            for line in f:
                if line.strip():
                    last = line
        return hashlib.sha256(last.strip().encode()).hexdigest() if last else "0" * 64

    def append(self, event: dict) -> dict:
        rec = {"ts": time.time(), **event, "prev": self._last_hash()}
        with open(self.path, "a") as f:
            f.write(json.dumps(rec, sort_keys=True, default=str) + "\n")
        return rec

    def read(self) -> list[dict]:
        if not self.path.exists():
            return []
        with open(self.path) as f:
            return [json.loads(l) for l in f if l.strip()]

    def verify(self) -> tuple[bool, int | None]:
        prev = "0" * 64
        with open(self.path) as f:
            lines = [l.strip() for l in f if l.strip()]
        for n, line in enumerate(lines):
            if json.loads(line).get("prev") != prev:
                return False, n
            prev = hashlib.sha256(line.encode()).hexdigest()
        return True, None


class PaperBroker:
    """Fills limit orders against a live/simulated ticker with fees and slippage. Spot, long-only."""

    def __init__(self, state_path: Path, ledger: Ledger, start_cash: float, fee_bps: float, slippage_bps: float):
        self.path = Path(state_path)
        self.ledger, self.fee, self.slip = ledger, fee_bps / 1e4, slippage_bps / 1e4
        self.s = json.loads(self.path.read_text()) if self.path.exists() else \
            {"cash": start_cash, "pos": {}, "peak": start_cash, "day": None, "day_start": start_cash,
             "loss_streak": 0, "orders_today": 0}

    def save(self):
        self.path.write_text(json.dumps(self.s, indent=2))

    def equity(self, prices: dict) -> float:
        return self.s["cash"] + sum(p["units"] * prices.get(sym, p["avg"]) for sym, p in self.s["pos"].items())

    def roll_day(self, utc_day: str, equity: float):
        if self.s["day"] != utc_day:
            self.s.update(day=utc_day, day_start=equity, orders_today=0)
        self.s["peak"] = max(self.s["peak"], equity)

    def buy(self, symbol, units, limit, ticker, stop=None, reason=""):
        ask = ticker["ask"]
        if limit < ask:  # passive limit below the ask does not fill in this simple model
            return self.ledger.append({"type": "order_unfilled", "symbol": symbol, "side": "buy", "limit": limit, "ask": ask})
        px = ask * (1 + self.slip)
        cost = units * px * (1 + self.fee)
        if cost > self.s["cash"]:
            return self.ledger.append({"type": "reject", "symbol": symbol, "reason": "insufficient cash"})
        self.s["cash"] -= cost
        p = self.s["pos"].get(symbol, {"units": 0.0, "avg": 0.0, "stop": None})
        p["avg"] = (p["avg"] * p["units"] + px * units) / (p["units"] + units)
        p["units"] += units
        p["stop"] = max(p["stop"] or 0, stop or 0) or None
        self.s["pos"][symbol] = p
        self.s["orders_today"] += 1
        return self.ledger.append({"type": "fill", "mode": "paper", "symbol": symbol, "side": "buy", "units": units,
                                   "price": px, "fee": units * px * self.fee, "stop": p["stop"], "reason": reason})

    def sell(self, symbol, ticker, reason="", units=None):
        p = self.s["pos"].get(symbol)
        if not p:
            return None
        units = units or p["units"]
        px = ticker["bid"] * (1 - self.slip)
        self.s["cash"] += units * px * (1 - self.fee)
        pnl = (px * (1 - self.fee)) / (p["avg"] * (1 + self.fee)) - 1
        p["units"] -= units
        if p["units"] <= 1e-12:
            del self.s["pos"][symbol]
        self.s["loss_streak"] = self.s["loss_streak"] + 1 if pnl <= 0 else 0
        self.s["orders_today"] += 1
        return self.ledger.append({"type": "fill", "mode": "paper", "symbol": symbol, "side": "sell", "units": units,
                                   "price": px, "pnl_pct": pnl, "reason": reason})

    def check_stops(self, tickers: dict):
        hits = []
        for sym, p in list(self.s["pos"].items()):
            t = tickers.get(sym)
            if t and p.get("stop") and t["bid"] <= p["stop"]:
                hits.append(self.sell(sym, t, reason=f"stop {p['stop']:.6g} hit"))
        return hits


class LiveBroker:
    """Same interface as PaperBroker, backed by a real (or sandbox) exchange via exchange.Exchange.

    Entries/exits are marketable IOC limit orders (no resting orders, bounded slippage).
    Stops: exchange-native stop-loss when CCXT exposes createStopLossOrder for the venue,
    otherwise bot-side (checked every `run`, so schedule `run` at least hourly when holding).
    """

    def __init__(self, ex, state_path: Path, ledger: Ledger, quote: str, slippage_bps: float):
        self.ex, self.path, self.ledger, self.quote = ex, Path(state_path), ledger, quote
        self.slip = slippage_bps / 1e4
        self.s = json.loads(self.path.read_text()) if self.path.exists() else \
            {"pos": {}, "peak": 0.0, "day": None, "day_start": 0.0, "loss_streak": 0, "orders_today": 0}
        self._bal = ex.balance()
        self.s["cash"] = float(self._bal.get(quote, {}).get("free") or 0)
        # reconcile: exchange balances are the truth, local state only keeps stops/avg cost
        for sym in list(self.s["pos"]):
            units = float(self._bal.get(sym.split("/")[0], {}).get("total") or 0)
            if units <= 0:
                del self.s["pos"][sym]
            else:
                self.s["pos"][sym]["units"] = units

    save = PaperBroker.save
    roll_day = PaperBroker.roll_day

    def equity(self, prices: dict) -> float:
        q = float(self._bal.get(self.quote, {}).get("total") or 0)
        return q + sum(float(self._bal.get(sym.split("/")[0], {}).get("total") or 0) * px for sym, px in prices.items())

    def buy(self, symbol, units, limit, ticker, stop=None, reason=""):
        o = self.ex.limit_order(symbol, "buy", units, limit, {"timeInForce": "IOC"})
        filled = float(o.get("filled") or 0)
        rec = {"type": "fill" if filled else "order_unfilled", "mode": "live", "symbol": symbol, "side": "buy",
               "units": filled, "price": o.get("average") or limit, "order_id": o.get("id"), "reason": reason}
        if filled:
            p = self.s["pos"].get(symbol, {"units": 0.0, "avg": 0.0, "stop": None})
            px = float(o.get("average") or limit)
            p["avg"] = (p["avg"] * p["units"] + px * filled) / (p["units"] + filled)
            p["units"] += filled
            p["stop"] = stop
            if stop and self.ex.x.has.get("createStopLossOrder"):
                try:
                    so = self.ex.x.create_stop_loss_order(symbol, "market", "sell", filled, None, stop)
                    p["native_stop_id"] = so.get("id")
                except Exception as e:
                    rec["stop_warning"] = f"native stop failed, bot-side stop active: {e}"
            self.s["pos"][symbol] = p
            self.s["orders_today"] += 1
        return self.ledger.append(rec)

    def sell(self, symbol, ticker, reason="", units=None):
        p = self.s["pos"].get(symbol)
        if not p:
            return None
        try:
            for o in self.ex.x.fetch_open_orders(symbol):  # release native stop / leftovers first
                self.ex.x.cancel_order(o["id"], symbol)
        except Exception:
            pass
        units = units or float(self.ex.balance().get(symbol.split("/")[0], {}).get("free") or p["units"])
        o = self.ex.limit_order(symbol, "sell", units, ticker["bid"] * (1 - self.slip), {"timeInForce": "IOC"})
        filled = float(o.get("filled") or 0)
        px = float(o.get("average") or ticker["bid"])
        pnl = px / p["avg"] - 1 if p.get("avg") else None
        if filled >= units * 0.999:
            del self.s["pos"][symbol]
            self.s["loss_streak"] = self.s["loss_streak"] + 1 if (pnl or 0) <= 0 else 0
        self.s["orders_today"] += 1
        return self.ledger.append({"type": "fill" if filled else "order_unfilled", "mode": "live", "symbol": symbol,
                                   "side": "sell", "units": filled, "price": px, "pnl_pct": pnl,
                                   "order_id": o.get("id"), "reason": reason})

    check_stops = PaperBroker.check_stops
