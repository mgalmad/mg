"""Self-contained HTML performance dashboard (no JS libs): KPI tiles, equity vs benchmark,
drawdown, recent trades. Works for backtest results and for the live/paper ledger."""
from __future__ import annotations

import html
from datetime import datetime, timezone


def _fmt(v, pct=False, d=2):
    if v is None:
        return "–"
    return f"{v * 100:.{d}f}%" if pct else f"{v:.{d}f}"


def _path(series, w, h, lo, hi):
    n = len(series)
    if n < 2 or hi == lo:
        return ""
    pts = [f"{i / (n - 1) * w:.1f},{h - (v - lo) / (hi - lo) * h:.1f}" for i, v in enumerate(series)]
    return "M" + " L".join(pts)


def render(title: str, equity: list[tuple], metrics: dict, trades: list[dict], bench: list[float] | None = None,
           bench_label: str = "Buy & hold") -> str:
    eq = [e for _, e in equity]
    b = [x * eq[0] / bench[0] for x in bench] if bench and eq else None
    allv = eq + (b or [])
    lo, hi = min(allv), max(allv)
    peak, dd = eq[0], []
    for x in eq:
        peak = max(peak, x)
        dd.append(x / peak - 1)
    W, H = 900, 260
    kpis = [("Total return", _fmt(metrics.get("total_return"), True)), ("CAGR", _fmt(metrics.get("cagr"), True)),
            ("Sharpe", _fmt(metrics.get("sharpe"))), ("Sortino", _fmt(metrics.get("sortino"))),
            ("Max drawdown", _fmt(metrics.get("max_drawdown"), True)), ("Calmar", _fmt(metrics.get("calmar"))),
            ("Trades", str(metrics.get("trades", "–"))), ("Win rate", _fmt(metrics.get("win_rate"), True, 1)),
            ("Profit factor", _fmt(metrics.get("profit_factor")))]
    rows = "".join(
        f"<tr><td>{datetime.fromtimestamp(t['ts'] / 1000 if t['ts'] > 1e11 else t['ts'], timezone.utc):%Y-%m-%d}</td>"
        f"<td>{html.escape(str(t.get('symbol', '')))}</td><td>{t['side']}</td><td>{t['price']:.6g}</td>"
        f"<td>{_fmt(t.get('pnl_pct'), True)}</td></tr>" for t in trades[-25:][::-1])
    tiles = "".join(f"<div class=k><span>{k}</span><b>{v}</b></div>" for k, v in kpis)
    return f"""<!doctype html><html><head><meta charset=utf-8><meta name=viewport content="width=device-width,initial-scale=1">
<title>{html.escape(title)}</title><style>
:root{{--bg:#fff;--fg:#1a1a1a;--mut:#666;--line:#2563eb;--bench:#9ca3af;--neg:#dc2626;--card:#f5f5f4}}
@media(prefers-color-scheme:dark){{:root{{--bg:#111;--fg:#eee;--mut:#999;--line:#60a5fa;--bench:#6b7280;--neg:#f87171;--card:#1c1c1c}}}}
body{{background:var(--bg);color:var(--fg);font:14px system-ui;margin:0;padding:16px;max-width:960px;margin:auto}}
.g{{display:grid;grid-template-columns:repeat(auto-fit,minmax(130px,1fr));gap:8px}}
.k{{background:var(--card);padding:10px;border-radius:8px}}.k span{{color:var(--mut);font-size:12px;display:block}}.k b{{font-size:18px}}
svg{{width:100%;height:auto}}table{{width:100%;border-collapse:collapse}}td,th{{padding:4px;border-bottom:1px solid var(--card);text-align:left}}
</style></head><body><h1>{html.escape(title)}</h1><div class=g>{tiles}</div>
<h3>Equity <small style="color:var(--line)">■ strategy</small> {f'<small style="color:var(--bench)">■ {html.escape(bench_label)}</small>' if b else ''}</h3>
<svg viewBox="0 0 {W} {H}"><path d="{_path(b, W, H, lo, hi) if b else ''}" fill=none stroke="var(--bench)" stroke-width=1.5 />
<path d="{_path(eq, W, H, lo, hi)}" fill=none stroke="var(--line)" stroke-width=2 /></svg>
<h3>Drawdown</h3><svg viewBox="0 0 {W} 120"><path d="{_path(dd, W, 120, min(dd + [-0.01]), 0)}" fill=none stroke="var(--neg)" stroke-width=1.5 /></svg>
<h3>Recent trades</h3><table><tr><th>Date</th><th>Symbol</th><th>Side</th><th>Price</th><th>P&L</th></tr>{rows}</table>
<p style="color:var(--mut)">Generated {datetime.now(timezone.utc):%Y-%m-%d %H:%M} UTC. Past/simulated performance is not predictive.</p>
</body></html>"""
