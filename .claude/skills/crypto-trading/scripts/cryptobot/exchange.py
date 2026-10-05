"""CCXT wrapper: rate limiting, retry policy, idempotent orders, precision, sandbox.

Retry policy matters more in trading than anywhere else:
  - SAFE to retry: reads (tickers, OHLCV, balances) on NetworkError / RateLimitExceeded /
    ExchangeNotAvailable / RequestTimeout, with exponential backoff + jitter.
  - NEVER blindly retry create_order: a timeout does not mean the order failed. We tag every
    order with a clientOrderId and, after an ambiguous error, look it up before resubmitting.
  - Never retry AuthenticationError, InsufficientFunds, InvalidOrder, BadSymbol.
"""
from __future__ import annotations

import os
import random
import time
import uuid

try:
    import ccxt
except ImportError:  # demo/backtest mode works without ccxt
    ccxt = None

RETRYABLE = ()
if ccxt:
    RETRYABLE = (ccxt.NetworkError, ccxt.RateLimitExceeded, ccxt.ExchangeNotAvailable, ccxt.RequestTimeout)


def backoff(attempt: int, base: float = 0.5, cap: float = 30.0) -> float:
    return min(cap, base * 2 ** attempt) * (0.5 + random.random() / 2)


class Exchange:
    def __init__(self, exchange_id: str, sandbox: bool = True, credentials: dict | None = None, max_retries: int = 5):
        if ccxt is None:
            raise RuntimeError("ccxt not installed: pip install ccxt")
        cls = getattr(ccxt, exchange_id)
        cfg = {"enableRateLimit": True, "timeout": 20_000, "options": {"adjustForTimeDifference": True}}
        cfg.update(credentials or {})
        self.x = cls(cfg)
        self.id = exchange_id
        self.sandbox = sandbox
        if sandbox:
            try:
                self.x.set_sandbox_mode(True)
            except Exception as e:  # many venues have no testnet
                raise RuntimeError(f"{exchange_id} has no sandbox via CCXT ({e}); use the paper broker instead") from e
        self.max_retries = max_retries
        self.x.load_markets()

    # ---- reads with retry ----
    def _read(self, fn, *a, **kw):
        for attempt in range(self.max_retries + 1):
            try:
                return fn(*a, **kw)
            except RETRYABLE:
                if attempt == self.max_retries:
                    raise
                time.sleep(backoff(attempt))

    def ohlcv(self, symbol: str, timeframe: str = "1d", since_ms: int | None = None, limit: int = 1000) -> list:
        """Paginate forward from since_ms. Drops the last (still-forming) candle."""
        out, since = [], since_ms
        tf_ms = self.x.parse_timeframe(timeframe) * 1000
        while True:
            batch = self._read(self.x.fetch_ohlcv, symbol, timeframe, since, limit)
            if not batch:
                break
            out.extend(b for b in batch if not out or b[0] > out[-1][0])
            if len(batch) < limit or since is None:
                break
            since = batch[-1][0] + tf_ms
        now = self.x.milliseconds()
        return [r for r in out if r[0] + tf_ms <= now]

    def ticker(self, symbol):
        return self._read(self.x.fetch_ticker, symbol)

    def order_book(self, symbol, limit=20):
        return self._read(self.x.fetch_order_book, symbol, limit)

    def balance(self):
        return self._read(self.x.fetch_balance)

    def market(self, symbol):
        return self.x.market(symbol)

    def taker_fee_bps(self, symbol, default_bps: float) -> float:
        try:
            f = self._read(self.x.fetch_trading_fee, symbol)
            return float(f["taker"]) * 1e4
        except Exception:
            m = self.x.market(symbol)
            return float(m["taker"]) * 1e4 if m.get("taker") is not None else default_bps

    # ---- writes: idempotent ----
    def limit_order(self, symbol: str, side: str, amount: float, price: float, params: dict | None = None) -> dict:
        amount = float(self.x.amount_to_precision(symbol, amount))
        price = float(self.x.price_to_precision(symbol, price))
        coid = f"cb{uuid.uuid4().hex[:20]}"
        p = {"clientOrderId": coid, **(params or {})}
        try:
            return self.x.create_order(symbol, "limit", side, amount, price, p)
        except RETRYABLE:
            found = self._find_by_client_id(symbol, coid)
            if found:
                return found
            time.sleep(backoff(1))
            found = self._find_by_client_id(symbol, coid)
            if found:
                return found
            raise  # surface it: a human/agent decides, never a silent double order

    def _find_by_client_id(self, symbol, coid):
        try:
            for o in self._read(self.x.fetch_open_orders, symbol) or []:
                if o.get("clientOrderId") == coid:
                    return o
            if self.x.has.get("fetchClosedOrders"):
                for o in self._read(self.x.fetch_closed_orders, symbol, None, 20) or []:
                    if o.get("clientOrderId") == coid:
                        return o
        except Exception:
            return None
        return None

    def cancel_all(self, symbol=None):
        return self.x.cancel_all_orders(symbol) if self.x.has.get("cancelAllOrders") else [
            self.x.cancel_order(o["id"], o["symbol"]) for o in self.x.fetch_open_orders(symbol)]


def public(exchange_id: str) -> "Exchange":
    """Unauthenticated, live-data client for research/backtests (no sandbox needed)."""
    e = Exchange.__new__(Exchange)
    e.x = getattr(ccxt, exchange_id)({"enableRateLimit": True, "timeout": 20_000})
    e.id, e.sandbox, e.max_retries = exchange_id, False, 5
    e.x.load_markets()
    return e


def credentials_from_env(exchange_id: str) -> dict:
    p = exchange_id.upper()
    c = {"apiKey": os.getenv(f"{p}_API_KEY"), "secret": os.getenv(f"{p}_API_SECRET")}
    if os.getenv(f"{p}_API_PASSWORD"):
        c["password"] = os.getenv(f"{p}_API_PASSWORD")
    return {k: v for k, v in c.items() if v}
