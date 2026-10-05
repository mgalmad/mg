"""Indicators on plain lists (CCXT OHLCV rows: [ts_ms, open, high, low, close, volume]).

All functions return a list aligned to the input (None until warm-up) so that
strategies can index bar t without ever touching bar t+1.
"""
from __future__ import annotations

import math
from statistics import mean, pstdev

TS, O, H, L, C, V = range(6)


def col(rows, i):
    return [r[i] for r in rows]


def sma(xs, n):
    out, s = [None] * len(xs), 0.0
    for i, x in enumerate(xs):
        s += x
        if i >= n:
            s -= xs[i - n]
        if i >= n - 1:
            out[i] = s / n
    return out


def ema(xs, n):
    out, k, e = [None] * len(xs), 2 / (n + 1), None
    for i, x in enumerate(xs):
        if i == n - 1:
            e = mean(xs[:n])
        elif i >= n:
            e = x * k + e * (1 - k)
        out[i] = e
    return out


def rolling_std(xs, n):
    return [pstdev(xs[i - n + 1:i + 1]) if i >= n - 1 else None for i in range(len(xs))]


def zscore(xs, n):
    m, s = sma(xs, n), rolling_std(xs, n)
    return [None if m[i] is None or not s[i] else (xs[i] - m[i]) / s[i] for i in range(len(xs))]


def atr(rows, n=14):
    out = [None] * len(rows)
    trs = [None] + [max(r[H] - r[L], abs(r[H] - p[C]), abs(r[L] - p[C])) for p, r in zip(rows, rows[1:])]
    a = None
    for i in range(1, len(rows)):
        if i == n:
            a = mean(trs[1:n + 1])
        elif i > n:
            a = (a * (n - 1) + trs[i]) / n
        out[i] = a
    return out


def rsi(xs, n=14):
    out = [None] * len(xs)
    if len(xs) <= n:
        return out
    d = [b - a for a, b in zip(xs, xs[1:])]
    ag = mean(max(x, 0) for x in d[:n])
    al = mean(max(-x, 0) for x in d[:n])
    for i in range(n, len(xs)):
        if i > n:
            ag = (ag * (n - 1) + max(d[i - 1], 0)) / n
            al = (al * (n - 1) + max(-d[i - 1], 0)) / n
        out[i] = 100.0 if al == 0 else 100 - 100 / (1 + ag / al)
    return out


def donchian(rows, n):
    """Highest high / lowest low of the n bars BEFORE bar i (excludes i: no self-breakout bias)."""
    hi, lo = [None] * len(rows), [None] * len(rows)
    for i in range(n, len(rows)):
        w = rows[i - n:i]
        hi[i], lo[i] = max(r[H] for r in w), min(r[L] for r in w)
    return hi, lo


def log_returns(xs):
    return [math.log(b / a) for a, b in zip(xs, xs[1:])]


def realized_vol(xs, n, periods_per_year):
    r = [None] + log_returns(xs)
    return [pstdev(r[i - n + 1:i + 1]) * math.sqrt(periods_per_year) if i >= n else None for i in range(len(xs))]


def hurst(xs, max_lag=20):
    """Hurst exponent via the variance-of-lagged-differences method on log prices.
    H < 0.5 mean-reverting, ~0.5 random walk, > 0.5 trending. Noisy on < ~200 points."""
    lp = [math.log(x) for x in xs]
    lags = range(2, max_lag)
    pts = []
    for lag in lags:
        diffs = [b - a for a, b in zip(lp[:-lag], lp[lag:])]
        sd = pstdev(diffs)
        if sd > 0:
            pts.append((math.log(lag), math.log(sd)))
    if len(pts) < 3:
        return None
    mx, my = mean(p[0] for p in pts), mean(p[1] for p in pts)
    num = sum((x - mx) * (y - my) for x, y in pts)
    den = sum((x - mx) ** 2 for x, _ in pts)
    return num / den if den else None
