"""Deterministic indicators and the signal model. Pure functions: no I/O.

The model is deliberately simple and evidence-based (see references/strategy.md):
  - Regime: price vs SMA200 (Faber 2007 trend filter)
  - Trend: SMA20 vs SMA50 alignment
  - Momentum: 12-1 month return (Jegadeesh & Titman 1993; skip last month)
  - Overextension guard: RSI(14) and distance from SMA20 in ATRs
  - Risk unit: ATR(14) for stop distance and position sizing
Numbers decide; the LLM only explains and can veto (news), never upgrade.
"""
from __future__ import annotations

import math
from statistics import mean, pstdev


def sma(xs: list[float], n: int) -> float | None:
    return mean(xs[-n:]) if len(xs) >= n else None


def rsi(closes: list[float], n: int = 14) -> float | None:
    if len(closes) < n + 1:
        return None
    gains, losses = [], []
    for a, b in zip(closes[:-1], closes[1:]):
        d = b - a
        gains.append(max(d, 0.0))
        losses.append(max(-d, 0.0))
    # Wilder smoothing
    ag, al = mean(gains[:n]), mean(losses[:n])
    for g, l in zip(gains[n:], losses[n:]):
        ag = (ag * (n - 1) + g) / n
        al = (al * (n - 1) + l) / n
    if al == 0:
        return 100.0
    return 100 - 100 / (1 + ag / al)


def atr(highs: list[float], lows: list[float], closes: list[float], n: int = 14) -> float | None:
    if len(closes) < n + 1:
        return None
    trs = [max(h - l, abs(h - pc), abs(l - pc))
           for h, l, pc in zip(highs[1:], lows[1:], closes[:-1])]
    a = mean(trs[:n])
    for tr in trs[n:]:
        a = (a * (n - 1) + tr) / n
    return a


def realized_vol(closes: list[float], n: int = 20) -> float | None:
    """Annualized close-to-close volatility."""
    if len(closes) < n + 1:
        return None
    rets = [math.log(b / a) for a, b in zip(closes[-n - 1:-1], closes[-n:])]
    return pstdev(rets) * math.sqrt(252)


def momentum_12_1(closes: list[float]) -> float | None:
    """Return from t-252 to t-21 sessions (skips the short-term reversal month)."""
    if len(closes) < 253:
        return None
    return closes[-22] / closes[-253] - 1


def analyze(bars: list[dict]) -> dict:
    """bars: Alpaca bar dicts (o,h,l,c,v,t), oldest first, COMPLETED sessions only."""
    c = [b["c"] for b in bars]
    h = [b["h"] for b in bars]
    lo = [b["l"] for b in bars]
    if len(c) < 60:
        return {"signal": "insufficient_data", "bars": len(c)}

    px = c[-1]
    s20, s50, s200 = sma(c, 20), sma(c, 50), sma(c, 200)
    a14 = atr(h, lo, c)
    r14 = rsi(c)
    vol = realized_vol(c)
    mom = momentum_12_1(c)
    ext_atr = (px - s20) / a14 if a14 else None

    score = 0
    reasons = []
    if s200 is not None:
        if px > s200:
            score += 1; reasons.append("above SMA200 (risk-on regime)")
        else:
            score -= 2; reasons.append("below SMA200 (risk-off regime)")
    if s20 > s50:
        score += 1; reasons.append("SMA20 > SMA50 (uptrend)")
    else:
        score -= 1; reasons.append("SMA20 < SMA50 (downtrend)")
    if mom is not None:
        if mom > 0:
            score += 1; reasons.append(f"12-1 momentum +{mom:.1%}")
        else:
            score -= 1; reasons.append(f"12-1 momentum {mom:.1%}")

    overextended = (r14 is not None and r14 > 75) or (ext_atr is not None and ext_atr > 3)
    if overextended:
        reasons.append("overextended (RSI>75 or >3 ATR above SMA20): wait for pullback")

    if score >= 2 and not overextended:
        signal = "buy"
    elif score <= -1:
        signal = "exit"
    else:
        signal = "hold"

    return {
        "signal": signal, "score": score, "reasons": reasons,
        "price": round(px, 4), "sma20": _r(s20), "sma50": _r(s50), "sma200": _r(s200),
        "atr14": _r(a14), "rsi14": _r(r14, 1), "vol20_ann": _r(vol, 4),
        "mom_12_1": _r(mom, 4), "ext_atr": _r(ext_atr, 2), "bars": len(c),
        "last_bar": bars[-1].get("t"),
    }


def _r(x, d: int = 4):
    return None if x is None else round(x, d)
