"""Bar-based backtester with honest costs, plus walk-forward and overfitting statistics.

Execution model (conservative):
  - Decide on bar i close, trade at bar i+1 OPEN +/- slippage, pay taker fee.
  - Rebalance only if |target - current| exceeds `rebalance_band` (turnover control).
  - Protective stop: if bar's LOW crosses the stop, exit at min(open, stop) - slippage
    (gaps through the stop fill at the open, as they would in reality).
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field
from statistics import NormalDist, mean, pstdev

from . import indicators as ind
from .strategies import build


@dataclass
class Costs:
    fee_bps: float = 40.0        # taker fee per side; set from your exchange tier
    slippage_bps: float = 10.0   # per side; raise for small caps / thin books
    rebalance_band: float = 0.10


@dataclass
class Result:
    equity: list = field(default_factory=list)
    trades: list = field(default_factory=list)
    metrics: dict = field(default_factory=dict)


def run(rows, strategy, costs: Costs = Costs(), start_equity: float = 10_000.0, start: int = 0, end: int | None = None,
        ppy: int = 365) -> Result:
    end = len(rows) if end is None else end
    strategy.prepare(rows)
    cash, units, stop = start_equity, 0.0, None
    eq, trades, entry = [], [], None
    fee, slip = costs.fee_bps / 1e4, costs.slippage_bps / 1e4
    tgt = 0.0
    for i in range(start, end):
        o, lo, c = rows[i][ind.O], rows[i][ind.L], rows[i][ind.C]
        if i > start:
            # 1) protective stop on existing position
            if units > 0 and stop is not None and lo <= stop:
                px = min(o, stop) * (1 - slip)
                cash += units * px * (1 - fee)
                trades.append(_trade(rows[i][ind.TS], "stop", units, px, entry))
                units, stop, entry = 0.0, None, None
                tgt = 0.0
            # 2) execute yesterday's decision at today's open
            value = cash + units * o
            cur = units * o / value if value else 0.0
            if abs(tgt - cur) > costs.rebalance_band or (tgt == 0 and units > 0):
                delta_val = (tgt - cur) * value
                if delta_val > 0:
                    px = o * (1 + slip)
                    q = min(delta_val, cash) / (px * (1 + fee))
                    if q > 0:
                        cash -= q * px * (1 + fee)
                        entry = px if units == 0 else (entry * units + px * q) / (units + q)
                        units += q
                        trades.append(_trade(rows[i][ind.TS], "buy", q, px, None))
                elif units > 0:
                    px = o * (1 - slip)
                    q = units if tgt == 0 else min(units, -delta_val / o)
                    cash += q * px * (1 - fee)
                    trades.append(_trade(rows[i][ind.TS], "sell", q, px, entry))
                    units -= q
                    if units <= 1e-12:
                        units, stop, entry = 0.0, None, None
        # 3) decide at close for tomorrow
        tgt = max(0.0, min(1.0, strategy.target(rows, i)))
        if units > 0:
            d = strategy.stop_distance(rows, i)
            if d:
                stop = max(stop or 0.0, c - d)  # ratchets up only (trailing)
        eq.append((rows[i][ind.TS], cash + units * c))
    res = Result(equity=eq, trades=trades)
    res.metrics = metrics([e for _, e in eq], trades, ppy)
    return res


def _trade(ts, side, qty, px, entry):
    t = {"ts": ts, "side": side, "qty": qty, "price": px}
    if entry is not None and side in ("sell", "stop"):
        t["pnl_pct"] = px / entry - 1
    return t


def metrics(equity: list[float], trades: list[dict], ppy: int = 365) -> dict:
    if len(equity) < 3:
        return {}
    rets = [b / a - 1 for a, b in zip(equity, equity[1:])]
    mu, sd = mean(rets), pstdev(rets)
    downside = pstdev([min(r, 0) for r in rets])
    years = len(rets) / ppy
    cagr = (equity[-1] / equity[0]) ** (1 / years) - 1 if years > 0 and equity[0] > 0 and equity[-1] > 0 else None
    peak, mdd = equity[0], 0.0
    for x in equity:
        peak = max(peak, x)
        mdd = min(mdd, x / peak - 1)
    closed = [t["pnl_pct"] for t in trades if "pnl_pct" in t]
    wins, losses = [x for x in closed if x > 0], [x for x in closed if x <= 0]
    sr_bar = mu / sd if sd else 0.0
    return {
        "total_return": equity[-1] / equity[0] - 1,
        "cagr": cagr,
        "sharpe": sr_bar * math.sqrt(ppy),
        "sharpe_per_bar": sr_bar,
        "sortino": mu / downside * math.sqrt(ppy) if downside else None,
        "max_drawdown": mdd,
        "calmar": (cagr / abs(mdd)) if cagr is not None and mdd < 0 else None,
        "trades": len(closed),
        "win_rate": len(wins) / len(closed) if closed else None,
        "profit_factor": (sum(wins) / abs(sum(losses))) if losses and sum(losses) else None,
        "avg_trade": mean(closed) if closed else None,
        "skew": _moment(rets, 3), "kurtosis": _moment(rets, 4), "n": len(rets),
    }


def _moment(xs, k):
    m, s = mean(xs), pstdev(xs)
    return mean(((x - m) / s) ** k for x in xs) if s else 0.0


# ---------- overfitting statistics ----------

def expected_max_sharpe(n_trials: int, var_trials: float) -> float:
    """E[max SR] of n_trials unskilled strategies (Bailey & López de Prado 2014), per-bar units.
    var_trials = variance of the per-bar Sharpe ratios across the trials you actually ran."""
    if n_trials < 2:
        return 0.0
    g, nd = 0.5772156649, NormalDist()
    return math.sqrt(var_trials) * ((1 - g) * nd.inv_cdf(1 - 1 / n_trials) + g * nd.inv_cdf(1 - 1 / (n_trials * math.e)))


def deflated_sharpe(sr_bar: float, n_obs: int, skew: float, kurt: float, n_trials: int, var_trials: float) -> float:
    """Probability the true Sharpe exceeds what the best of n_trials lucky strategies would show.
    Uses PER-BAR Sharpe (not annualised) and non-excess kurtosis. > 0.95 = evidence of skill."""
    sr0 = expected_max_sharpe(n_trials, var_trials)
    denom = math.sqrt(max(1e-12, (1 - skew * sr_bar + (kurt - 1) / 4 * sr_bar ** 2) / max(1, n_obs - 1)))
    return NormalDist().cdf((sr_bar - sr0) / denom)


def walk_forward(rows, strategy_name: str, grid: list[dict], costs: Costs = Costs(), train: int = 730,
                 test: int = 180, embargo: int = 5, ppy: int = 365, warmup: int = 250) -> dict:
    """Rolling walk-forward: pick the best grid point on each train window (by Sharpe), evaluate it
    on the following unseen test window (after an embargo). Reports the stitched out-of-sample
    performance, the in-sample/out-of-sample Sharpe decay and a deflated Sharpe over all trials."""
    folds, oos_eq, all_trial_srs = [], [10_000.0], []
    i = warmup
    while i + train + embargo + test <= len(rows):
        tr_s, tr_e = i, i + train
        te_s, te_e = tr_e + embargo, tr_e + embargo + test
        scored = []
        for params in grid:
            r = run(rows, build(strategy_name, params, ppy), costs, start=tr_s, end=tr_e, ppy=ppy)
            sr = r.metrics.get("sharpe_per_bar", 0.0)
            scored.append((sr, params))
            all_trial_srs.append(sr)
        best_sr, best = max(scored, key=lambda x: x[0])
        oos = run(rows, build(strategy_name, best, ppy), costs, start=te_s, end=te_e, ppy=ppy)
        scale = oos_eq[-1] / oos.equity[0][1]
        oos_eq += [e * scale for _, e in oos.equity[1:]]
        folds.append({"train": [rows[tr_s][0], rows[tr_e - 1][0]], "test": [rows[te_s][0], rows[te_e - 1][0]],
                      "params": best, "is_sharpe": best_sr * math.sqrt(ppy),
                      "oos_sharpe": oos.metrics.get("sharpe"), "oos_return": oos.metrics.get("total_return"),
                      "oos_trades": oos.metrics.get("trades")})
        i += test
    if not folds:
        return {"error": f"need >= {warmup + train + embargo + test} bars, have {len(rows)}"}
    m = metrics(oos_eq, [], ppy)
    var_t = pstdev(all_trial_srs) ** 2 if len(all_trial_srs) > 1 else 0.0
    dsr = deflated_sharpe(m["sharpe_per_bar"], m["n"], m["skew"], m["kurtosis"], len(grid), var_t)
    is_mean = mean(f["is_sharpe"] for f in folds)
    oos_mean = mean((f["oos_sharpe"] or 0.0) for f in folds)
    return {"folds": folds, "oos_metrics": m, "trials_per_fold": len(grid),
            "deflated_sharpe": dsr, "is_sharpe_mean": is_mean, "oos_sharpe_mean": oos_mean,
            "sharpe_decay": (oos_mean / is_mean) if is_mean > 0 else None,
            "verdict": _verdict(dsr, is_mean, oos_mean, m)}


def _verdict(dsr, is_mean, oos_mean, m):
    notes = []
    if dsr < 0.95:
        notes.append(f"DSR {dsr:.2f} < 0.95: not distinguishable from the luckiest of the trials")
    if is_mean > 0 and oos_mean / is_mean < 0.5:
        notes.append("out-of-sample Sharpe < 50% of in-sample: likely overfit")
    if (m.get("max_drawdown") or 0) < -0.35:
        notes.append("OOS max drawdown worse than -35%")
    return {"pass": not notes, "notes": notes}


def buy_and_hold(rows, start=0, end=None, ppy=365, costs: Costs = Costs()) -> dict:
    end = len(rows) if end is None else end
    entry = rows[start][ind.C] * (1 + (costs.fee_bps + costs.slippage_bps) / 1e4)
    eq = [10_000 * r[ind.C] / entry for r in rows[start:end]]
    return metrics(eq, [], ppy)
