"""Synthetic OHLCV for --demo mode and tests: a seeded regime-switching random walk
(bull / bear / chop with fat-ish tails). It has NO real edge baked in, so a strategy that
looks great on it is probably exploiting the generator, not the market."""
from __future__ import annotations

import math
import random


def ohlcv(n: int = 1500, seed: int = 7, start_price: float = 30_000.0, start_ts: int = 1_600_000_000_000,
          tf_ms: int = 86_400_000) -> list[list[float]]:
    rnd = random.Random(seed)
    regimes = [(0.002, 0.03), (-0.002, 0.045), (0.0, 0.02)]
    reg, px, out = 2, start_price, []
    for i in range(n):
        if rnd.random() < 0.01:
            reg = rnd.randrange(3)
        mu, sig = regimes[reg]
        shock = rnd.gauss(0, 1) * (1.8 if rnd.random() < 0.05 else 1.0)
        o = px
        c = o * math.exp(mu - sig * sig / 2 + sig * shock)
        h = max(o, c) * (1 + abs(rnd.gauss(0, sig / 3)))
        l = min(o, c) * (1 - abs(rnd.gauss(0, sig / 3)))
        out.append([start_ts + i * tf_ms, o, h, l, c, rnd.uniform(100, 1000)])
        px = c
    return out


def books(mid: float, seed: int = 1, venues=("kraken", "bitstamp", "coinbase")) -> dict:
    rnd = random.Random(seed)
    res = {}
    for v in venues:
        m = mid * (1 + rnd.uniform(-0.0015, 0.0015))
        res[v] = {"bids": [[m * (1 - (k + 1) * 2e-4), rnd.uniform(0.1, 2)] for k in range(20)],
                  "asks": [[m * (1 + (k + 1) * 2e-4), rnd.uniform(0.1, 2)] for k in range(20)]}
    return res
