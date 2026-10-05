"""Crypto trading CLI. Every command prints JSON. --demo uses synthetic data (no network, no keys).

  fetch SYM [--since YYYY-MM-DD]          download & cache OHLCV (closed candles only)
  backtest SYM [--strategy S] [--params JSON] [--html PATH]
  walkforward SYM [--strategy S]          parameter grid, rolling OOS, deflated Sharpe, verdict
  signal                                  latest target exposure per universe symbol
  run [--execute]                         one decision cycle (stops, halts, exits, entries)
  arb [--size QUOTE]                      cross-exchange depth-aware arbitrage scan (REST snapshot)
  stream [--seconds N]                    WebSocket order-book monitor + live arb scan (read-only)
  mm-quote SYM [--inventory U]            market-making quotes (paper/sandbox only)
  status | verify-ledger | dashboard [--html PATH] | freshness | keys-set EXCHANGE
"""
from __future__ import annotations

import argparse
import asyncio
import csv
import json
import os
import shutil
import sys
import time
import zlib
from datetime import date, datetime, timezone
from pathlib import Path

from . import arbitrage, backtest as bt, dashboard, demo, indicators as ind, risk
from .alerts import alert
from .ledger import Ledger, LiveBroker, PaperBroker
from .strategies import MarketMaker, build

SKILL_DIR = Path(__file__).resolve().parents[2]


def home() -> Path:
    if os.getenv("TRADING_HOME"):
        return Path(os.environ["TRADING_HOME"])
    for d in [Path.cwd(), *Path.cwd().parents]:
        if (d / "config" / "crypto.json").exists():
            return d
    # Standalone install (e.g. uploaded to claude.ai): seed the working dir from the bundled default
    (Path.cwd() / "config").mkdir(exist_ok=True)
    shutil.copy(SKILL_DIR / "assets" / "default-config.json", Path.cwd() / "config" / "crypto.json")
    return Path.cwd()


HOME = home()
CFG = json.loads((HOME / "config" / "crypto.json").read_text())
LIM = CFG["limits"]
UNIVERSE = {u["symbol"]: u for u in CFG["universe"]}
STATE = HOME / "state"
DATA = HOME / "data"
PPY = CFG.get("periods_per_year", 365)
GRIDS = {
    "momentum": [{"fast": f, "slow": s, "breakout": b} for f in (10, 20, 50) for s in (100, 200) for b in (20, 55)],
    "mean_reversion": [{"n": n, "entry_z": z} for n in (10, 20, 40) for z in (-1.5, -2.0, -2.5)],
}


def out(o):
    print(json.dumps(o, indent=2, default=str))


def costs():
    return bt.Costs(LIM["fee_bps"], LIM["slippage_bps"], LIM["rebalance_band"])


def cache_path(sym):
    return DATA / f"{CFG['exchange']}_{sym.replace('/', '-')}_{CFG['timeframe']}.csv"


def load_rows(sym, demo_mode, since=None):
    if demo_mode:
        return demo.ohlcv(seed=zlib.crc32(sym.encode()) % 1000)
    p = cache_path(sym)
    if not p.exists() or time.time() - p.stat().st_mtime > 6 * 3600:
        fetch(sym, since or "2018-01-01")
    return [[float(x) for x in r] for r in csv.reader(open(p))]


def fetch(sym, since):
    from .exchange import public
    ex = public(CFG["exchange"])
    ms = int(datetime.fromisoformat(since).replace(tzinfo=timezone.utc).timestamp() * 1000)
    rows = ex.ohlcv(sym, CFG["timeframe"], ms)
    DATA.mkdir(exist_ok=True)
    with open(cache_path(sym), "w", newline="") as f:
        csv.writer(f).writerows(rows)
    return rows


def strategy_for(sym, name=None, params=None):
    return build(name or UNIVERSE.get(sym, {}).get("strategy", "momentum"), params, PPY)


# ---------------- commands ----------------

def cmd_fetch(a):
    rows = fetch(a.symbol, a.since)
    out({"symbol": a.symbol, "rows": len(rows), "first": rows[0][0] if rows else None,
         "last": rows[-1][0] if rows else None, "path": str(cache_path(a.symbol))})


def cmd_backtest(a):
    rows = load_rows(a.symbol, a.demo)
    s = strategy_for(a.symbol, a.strategy, json.loads(a.params) if a.params else None)
    r = bt.run(rows, s, costs(), ppy=PPY)
    bh = bt.buy_and_hold(rows, ppy=PPY, costs=costs())
    if a.html:
        Path(a.html).write_text(dashboard.render(f"Backtest {a.symbol} {s.name}", r.equity, r.metrics,
                                                 [{**t, "symbol": a.symbol} for t in r.trades],
                                                 [x[ind.C] for x in rows]))
    out({"symbol": a.symbol, "strategy": s.name, "params": s.params, "demo": a.demo, "bars": len(rows),
         "metrics": r.metrics, "buy_and_hold": bh, "costs": vars(costs()),
         "warning": "Single in-sample run. Use walkforward before believing any of this."})


def cmd_walkforward(a):
    rows = load_rows(a.symbol, a.demo)
    name = a.strategy or UNIVERSE.get(a.symbol, {}).get("strategy", "momentum")
    res = bt.walk_forward(rows, name, GRIDS[name], costs(), train=a.train, test=a.test, ppy=PPY)
    out({"symbol": a.symbol, "strategy": name, "demo": a.demo, **res})


def latest_signals(demo_mode):
    sigs = {}
    for sym in UNIVERSE:
        rows = load_rows(sym, demo_mode)
        s = strategy_for(sym)
        s.prepare(rows)
        tgt = 0.0
        for i in range(len(rows)):  # replay so stateful strategies reach today's state
            tgt = s.target(rows, i)
        c = [r[ind.C] for r in rows]
        vol = ind.realized_vol(c, 30, PPY)
        vols = [v for v in vol[-180:] if v]
        sigs[sym] = {"target": round(tgt, 4), "close": c[-1], "last_bar": rows[-1][0],
                     "stop_dist": s.stop_distance(rows, len(rows) - 1), "vol_now": vol[-1],
                     "vol_avg_180": sum(vols) / len(vols) if vols else None, "strategy": s.name}
    return sigs


def cmd_signal(a):
    out(latest_signals(a.demo))


def _tickers(syms, demo_mode, sigs):
    if demo_mode:
        return {s: {"bid": sigs[s]["close"] * 0.9998, "ask": sigs[s]["close"] * 1.0002, "timestamp": time.time() * 1000}
                for s in syms}
    from .exchange import public
    ex = public(CFG["exchange"])
    return {s: ex.ticker(s) for s in syms}


def cmd_run(a):
    live = CFG["mode"] == "live"
    if live and a.execute and os.getenv("ALLOW_LIVE_TRADING") != "yes":
        sys.exit("mode=live requires ALLOW_LIVE_TRADING=yes")
    STATE.mkdir(exist_ok=True)
    if live and a.demo:
        sys.exit("--demo cannot be combined with mode=live")
    ledger = Ledger(STATE / ("crypto_demo_ledger.jsonl" if a.demo else "crypto_ledger.jsonl"))
    if live:
        from . import keystore
        from .exchange import Exchange
        ex = Exchange(CFG["exchange"], sandbox=CFG.get("sandbox", False), credentials=keystore.credentials(CFG["exchange"]))
        quote = next(iter(UNIVERSE)).split("/")[1]
        pb = LiveBroker(ex, STATE / "crypto_live.json", ledger, quote, LIM["slippage_bps"])
    else:
        pb = PaperBroker(STATE / ("crypto_demo_paper.json" if a.demo else "crypto_paper.json"), ledger,
                         CFG["paper_start_cash"], LIM["fee_bps"], LIM["slippage_bps"])
    sigs = latest_signals(a.demo)
    tick = _tickers(list(UNIVERSE), a.demo, sigs)
    prices = {s: (t["bid"] + t["ask"]) / 2 for s, t in tick.items()}
    eq = pb.equity(prices)
    pb.roll_day(datetime.now(timezone.utc).strftime("%Y-%m-%d"), eq)
    actions = {"stops": [x for x in pb.check_stops(tick) if x] if a.execute else [], "exits": [], "entries": [], "skipped": []}
    for sym, sg in sigs.items():  # exits first
        if sg["target"] == 0 and sym in pb.s["pos"]:
            if a.execute:
                actions["exits"].append(pb.sell(sym, tick[sym], reason="signal exit"))
            else:
                actions["exits"].append({"dry_run": True, "symbol": sym})
    eq = pb.equity(prices)
    book = risk.Book(equity=eq, free_quote=pb.s["cash"], exchange_equity=eq if live else 0.0,
                     total_capital=CFG.get("total_capital_quote"), day_start_equity=pb.s["day_start"],
                     peak_equity=pb.s["peak"],
                     positions={s: p["units"] * prices[s] for s, p in pb.s["pos"].items()},
                     consecutive_losses=pb.s["loss_streak"], orders_today=pb.s["orders_today"])
    halted = risk.halts(book, LIM)
    if halted:
        alert("CRITICAL", "crypto entries halted: " + "; ".join(halted))
    for sym, sg in sorted(sigs.items(), key=lambda kv: -kv[1]["target"]):
        if sg["target"] <= 0 or sym in pb.s["pos"] or halted:
            continue
        t = tick[sym]
        mult = risk.de_risk_multiplier(book, LIM, sg["vol_now"], sg["vol_avg_180"])
        limit_px = t["ask"] * (1 + 5 / 1e4)
        stop_dist = sg["stop_dist"] or limit_px * 0.1
        alloc = min(UNIVERSE[sym]["max_allocation_pct"], LIM["max_position_pct"]) * sg["target"]
        units = risk.size_order(book, limit_px, stop_dist, LIM, alloc, mult)
        age = time.time() - (t.get("timestamp") or 0) / 1000
        v = risk.validate_buy(sym, units, limit_px, t, {}, book, LIM, UNIVERSE[sym]["max_allocation_pct"],
                              set(UNIVERSE), age)
        if not v.ok:
            actions["skipped"].append({"symbol": sym, "reasons": v.reasons})
            continue
        if a.execute:
            fill = pb.buy(sym, units, limit_px, t, stop=limit_px - stop_dist, reason=f"{sg['strategy']} target {sg['target']}")
            actions["entries"].append(fill)
            book.positions[sym] = units * limit_px
            book.free_quote = pb.s["cash"]
        else:
            actions["entries"].append({"dry_run": True, "symbol": sym, "units": units, "limit": limit_px,
                                       "stop": limit_px - stop_dist, "size_mult": mult})
    if a.execute:
        pb.save()
    out({"mode": ("live" if live else "paper") + (" demo" if a.demo else ""), "execute": a.execute, "equity": pb.equity(prices), "halts": halted, **actions})


def cmd_arb(a):
    if a.demo:
        books = demo.books(60_000.0)
    else:
        from .exchange import public
        books = {}
        for v in CFG["arbitrage_venues"]:
            try:
                books[v] = public(v).order_book(a.symbol, 50)
            except Exception as e:
                books[v] = None
                alert("WARN", f"arb: {v} book failed: {e}")
        books = {k: b for k, b in books.items() if b}
    fees = {v: LIM["fee_bps"] for v in books}
    out(arbitrage.best_opportunity(books, fees, a.size, LIM["min_arb_edge_bps"]))


def cmd_stream(a):
    from .stream import Staleness, run
    books, st = {}, Staleness(LIM["max_data_age_s"])
    fees = {v: LIM["fee_bps"] for v in CFG["arbitrage_venues"]}

    def on_update(ex, sym, book):
        if "error" in book:
            print(json.dumps({"venue": ex, "error": book["error"]}))
            return
        books[ex] = book
        st.touch(ex)
        live = {k: v for k, v in books.items() if k not in st.stale()}
        if len(live) >= 2:
            opp = arbitrage.best_opportunity(live, fees, a.size, LIM["min_arb_edge_bps"])
            if opp and opp["actionable"]:
                alert("INFO", f"arb {opp['buy_on']}->{opp['sell_on']} net {opp['net_bps']:.1f}bps", opp=opp)
                print(json.dumps(opp, default=str))

    asyncio.run(run([(v, a.symbol) for v in CFG["arbitrage_venues"]], on_update, seconds=a.seconds))


def cmd_mm(a):
    rows = load_rows(a.symbol, a.demo)
    c = [r[ind.C] for r in rows]
    daily_bps = (ind.realized_vol(c, 30, PPY)[-1] / (PPY ** 0.5)) * 1e4
    horizon_bps = daily_bps * (a.horizon_min / 1440) ** 0.5  # sigma over the expected quote lifetime
    mid = c[-1]
    out({"symbol": a.symbol, "mid": mid, "daily_sigma_bps": daily_bps, "horizon_sigma_bps": horizon_bps,
         **MarketMaker(max_inventory=a.max_inventory).quotes(mid, horizon_bps, a.inventory, a.maker_fee_bps),
         "note": "Paper/sandbox only. Needs maker fees << taker and L2 data to evaluate."})


def cmd_status(a):
    p = STATE / ("crypto_demo_paper.json" if a.demo else "crypto_paper.json")
    s = json.loads(p.read_text()) if p.exists() else None
    out({"mode": CFG["mode"], "exchange": CFG["exchange"], "paper_state": s})


def cmd_verify(a):
    ok, bad = Ledger(STATE / "crypto_ledger.jsonl").verify() if (STATE / "crypto_ledger.jsonl").exists() else (True, None)
    out({"ledger_intact": ok, "first_bad_line": bad})


def cmd_dashboard(a):
    sym = a.symbol or next(iter(UNIVERSE))
    rows = load_rows(sym, a.demo)
    r = bt.run(rows, strategy_for(sym), costs(), ppy=PPY)
    trades = [{**t, "symbol": sym} for t in r.trades]
    led = STATE / "crypto_ledger.jsonl"
    if led.exists() and not a.demo:
        trades = [e for e in Ledger(led).read() if e.get("type") == "fill"]
    Path(a.html).write_text(dashboard.render(f"Crypto: {sym}", r.equity, r.metrics, trades, [x[ind.C] for x in rows]))
    out({"html": a.html})


def cmd_freshness(a):
    src = json.loads((SKILL_DIR / "references" / "sources.json").read_text())
    stale = [{**s, "age_days": (date.today() - date.fromisoformat(s["last_verified"])).days}
             for s in src["sources"]
             if (date.today() - date.fromisoformat(s["last_verified"])).days > s.get("max_age_days", 30)]
    out({"stale": stale, "total": len(src["sources"])})
    sys.exit(1 if stale else 0)


def cmd_keys(a):
    import getpass
    from . import keystore
    data = keystore.load() if keystore.DEFAULT_PATH.exists() else {}
    data[a.exchange] = {"apiKey": getpass.getpass("API key: "), "secret": getpass.getpass("API secret: ")}
    pw = getpass.getpass("API password/passphrase (blank if none): ")
    if pw:
        data[a.exchange]["password"] = pw
    keystore.save(data)
    out({"stored": a.exchange, "path": str(keystore.DEFAULT_PATH)})


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--demo", action="store_true", help="synthetic data, no network/keys")
    sp = ap.add_subparsers(dest="cmd", required=True)
    p = sp.add_parser("fetch"); p.add_argument("symbol"); p.add_argument("--since", default="2018-01-01")
    p = sp.add_parser("backtest"); p.add_argument("symbol"); p.add_argument("--strategy"); p.add_argument("--params")
    p.add_argument("--html")
    p = sp.add_parser("walkforward"); p.add_argument("symbol"); p.add_argument("--strategy")
    p.add_argument("--train", type=int, default=730); p.add_argument("--test", type=int, default=180)
    sp.add_parser("signal")
    p = sp.add_parser("run"); p.add_argument("--execute", action="store_true")
    p = sp.add_parser("arb"); p.add_argument("--symbol", default="BTC/USD"); p.add_argument("--size", type=float, default=1000)
    p = sp.add_parser("stream"); p.add_argument("--symbol", default="BTC/USD"); p.add_argument("--seconds", type=float, default=60)
    p.add_argument("--size", type=float, default=1000)
    p = sp.add_parser("mm-quote"); p.add_argument("symbol"); p.add_argument("--inventory", type=float, default=0.0)
    p.add_argument("--max-inventory", type=float, default=1.0)
    p.add_argument("--horizon-min", type=float, default=5.0); p.add_argument("--maker-fee-bps", type=float, default=25.0)
    sp.add_parser("status"); sp.add_parser("verify-ledger"); sp.add_parser("freshness")
    p = sp.add_parser("dashboard"); p.add_argument("--symbol"); p.add_argument("--html", default="state/crypto_dashboard.html")
    p = sp.add_parser("keys-set"); p.add_argument("exchange")
    a = ap.parse_args(argv)
    {"fetch": cmd_fetch, "backtest": cmd_backtest, "walkforward": cmd_walkforward, "signal": cmd_signal,
     "run": cmd_run, "arb": cmd_arb, "stream": cmd_stream, "mm-quote": cmd_mm, "status": cmd_status,
     "verify-ledger": cmd_verify, "dashboard": cmd_dashboard, "freshness": cmd_freshness,
     "keys-set": cmd_keys}[a.cmd](a)


if __name__ == "__main__":
    main()
