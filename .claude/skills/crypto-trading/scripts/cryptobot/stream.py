"""Real-time WebSocket market data via ccxt.pro (bundled with ccxt >= 4).

Watches tickers/order books across exchanges, flags stale feeds, reconnects with backoff,
and calls `on_update(exchange_id, symbol, book)`; used by `cli.py stream` for live
arbitrage scanning and spread monitoring. Read-only: it never places orders.
"""
from __future__ import annotations

import asyncio
import time

from .exchange import backoff


async def _watch(exchange_id: str, symbol: str, on_update, depth: int, stop: asyncio.Event):
    import ccxt.pro as ccxtpro
    attempt = 0
    while not stop.is_set():
        ex = getattr(ccxtpro, exchange_id)({"enableRateLimit": True})
        try:
            while not stop.is_set():
                book = await ex.watch_order_book(symbol, depth)
                attempt = 0
                on_update(exchange_id, symbol, book)
        except Exception as e:
            on_update(exchange_id, symbol, {"error": f"{type(e).__name__}: {e}"})
            await asyncio.sleep(backoff(attempt))
            attempt += 1
        finally:
            await ex.close()


async def run(pairs: list[tuple[str, str]], on_update, depth: int = 20, seconds: float | None = None):
    stop = asyncio.Event()
    tasks = [asyncio.create_task(_watch(e, s, on_update, depth, stop)) for e, s in pairs]
    if seconds:
        await asyncio.sleep(seconds)
        stop.set()
        for t in tasks:
            t.cancel()
    await asyncio.gather(*tasks, return_exceptions=True)


class Staleness:
    def __init__(self, max_age_s: float):
        self.max_age, self.seen = max_age_s, {}

    def touch(self, key):
        self.seen[key] = time.time()

    def stale(self):
        now = time.time()
        return [k for k, t in self.seen.items() if now - t > self.max_age]
