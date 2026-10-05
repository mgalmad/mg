"""Modular strategies. Contract: target(rows, i) -> desired exposure in [0, 1] (spot, long-only)
using ONLY rows[:i+1]. The backtester executes at bar i+1's open, so lookahead is impossible
as long as strategies respect the slice. `prepare` precomputes indicators once per series.

Market making is quote generation, not a bar strategy: see MarketMaker.
"""
from __future__ import annotations

from dataclasses import dataclass, field

from . import indicators as ind


class Strategy:
    name = "base"
    params: dict

    def prepare(self, rows):  # pragma: no cover - interface
        pass

    def target(self, rows, i) -> float:  # pragma: no cover - interface
        raise NotImplementedError

    def stop_distance(self, rows, i) -> float | None:
        """Price distance for the protective stop (None = no stop)."""
        a = self._atr[i] if hasattr(self, "_atr") else None
        return a * self.params.get("stop_atr", 2.5) if a else None


@dataclass
class Momentum(Strategy):
    """Trend/time-series momentum: EMA fast > slow AND close above prior Donchian high (entry);
    exit on EMA cross down or close below prior Donchian low. Liu & Tsyvinski (RFS 2021) document
    time-series momentum in crypto. Vol-scaled exposure keeps risk roughly constant."""
    params: dict = field(default_factory=lambda: {"fast": 20, "slow": 100, "breakout": 20, "exit": 10,
                                                  "vol_n": 30, "vol_target": 0.6, "stop_atr": 3.0})
    name: str = "momentum"

    def prepare(self, rows):
        p, c = self.params, ind.col(rows, ind.C)
        self._f, self._s = ind.ema(c, p["fast"]), ind.ema(c, p["slow"])
        self._hi, _ = ind.donchian(rows, p["breakout"])
        _, self._lo = ind.donchian(rows, p["exit"])
        self._vol = ind.realized_vol(c, p["vol_n"], self.params.get("ppy", 365))
        self._atr = ind.atr(rows)
        self._in = [False] * len(rows)

    def target(self, rows, i):
        if None in (self._f[i], self._s[i], self._hi[i], self._lo[i], self._vol[i]):
            return 0.0
        c = rows[i][ind.C]
        was_in = self._in[i - 1] if i else False
        if not was_in and self._f[i] > self._s[i] and c > self._hi[i]:
            now_in = True
        elif was_in and (self._f[i] < self._s[i] or c < self._lo[i]):
            now_in = False
        else:
            now_in = was_in
        self._in[i] = now_in
        if not now_in:
            return 0.0
        return min(1.0, self.params["vol_target"] / max(self._vol[i], 1e-9))


@dataclass
class MeanReversion(Strategy):
    """Buy oversold dips (z-score of close vs SMA < -entry_z) only when the long trend is up
    (close > SMA_trend) and the series is not strongly trending (Hurst < max_hurst).
    Exit at z >= exit_z or time stop. Evidence for short-horizon reversal in crypto is weaker
    and less stable than for momentum: treat as a diversifier, not a core engine."""
    params: dict = field(default_factory=lambda: {"n": 20, "entry_z": -2.0, "exit_z": 0.0, "trend": 200,
                                                  "max_hurst": 0.55, "hurst_window": 200, "max_hold": 10,
                                                  "size": 0.5, "stop_atr": 2.0})
    name: str = "mean_reversion"

    def prepare(self, rows):
        p, c = self.params, ind.col(rows, ind.C)
        self._z, self._t, self._atr = ind.zscore(c, p["n"]), ind.sma(c, p["trend"]), ind.atr(rows)
        self._c = c
        self._held = [0] * len(rows)

    def target(self, rows, i):
        p = self.params
        if self._z[i] is None or self._t[i] is None:
            return 0.0
        held = self._held[i - 1] if i else 0
        if held:
            if self._z[i] >= p["exit_z"] or held >= p["max_hold"]:
                self._held[i] = 0
                return 0.0
            self._held[i] = held + 1
            return p["size"]
        if self._z[i] <= p["entry_z"] and rows[i][ind.C] > self._t[i]:
            hw = p["hurst_window"]
            h = ind.hurst(self._c[max(0, i - hw + 1):i + 1]) if i >= hw - 1 else None
            if h is not None and h < p["max_hurst"]:
                self._held[i] = 1
                return p["size"]
        return 0.0


STRATEGIES = {"momentum": Momentum, "mean_reversion": MeanReversion}


def build(name: str, overrides: dict | None = None, ppy: int = 365) -> Strategy:
    s = STRATEGIES[name]()
    s.params = {**s.params, **(overrides or {}), "ppy": ppy}
    return s


@dataclass
class MarketMaker:
    """Inventory-aware quoting in the spirit of Avellaneda & Stoikov (Quant. Finance 2008):
    reservation price r = mid - q * gamma * sigma^2 * T, half-spread widened by volatility.
    q is inventory in units of max_inventory (0..1 for spot; negative only where shorting exists). Output quotes only; bar-data backtests
    of market making are meaningless (fills depend on queue position), so this is
    paper/live-sandbox only and must be evaluated on recorded order-book data."""
    gamma: float = 0.1
    min_half_spread_bps: float = 10.0
    vol_mult: float = 0.5
    max_inventory: float = 1.0

    def quotes(self, mid: float, sigma_bps: float, inventory: float, fee_bps: float) -> dict:
        q = max(-1.0, min(1.0, inventory / self.max_inventory))
        half = max(self.min_half_spread_bps, fee_bps + self.vol_mult * sigma_bps)  # never quote inside fees
        skew = q * self.gamma * sigma_bps
        r = mid * (1 - skew / 1e4)
        bid, ask = r * (1 - half / 1e4), r * (1 + half / 1e4)
        return {"bid": bid, "ask": ask, "reservation": r, "half_spread_bps": half,
                "quote_bid": q < 1.0, "quote_ask": inventory > 0}  # spot: cannot sell what you do not hold
