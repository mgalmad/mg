#!/usr/bin/env python3
"""Single CLI entrypoint for the trading skill. Every subcommand prints JSON.

  status                 account, clock, positions, kill-switch state
  research [SYM ...]     signals for the watchlist (completed bars only) + news
  buy SYM [--execute]    size, validate and (optionally) submit a bracket limit order
  sell SYM [--execute]   cancel the symbol's open orders, then exit with a marketable limit
  flatten --execute      cancel all orders and close all positions (emergency)
  journal                create today's journal file from the template if missing
  heartbeat ROUTINE      record that a routine ran
  review [--period 3M]   performance vs SPY, drawdown, trade count
  freshness              list knowledge sources older than their max age

Orders are dry-run unless --execute is passed. Live trading additionally
requires ALLOW_LIVE_TRADING=yes in the environment.
"""
from __future__ import annotations

import argparse
import json
import math
import os
import shutil
import sys
from datetime import date, datetime, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

sys.path.insert(0, str(Path(__file__).resolve().parent))
from alpaca import Alpaca, AlpacaError  # noqa: E402
import risk  # noqa: E402
import signals  # noqa: E402

ET = ZoneInfo("America/New_York")
SKILL_DIR = Path(__file__).resolve().parent.parent


def find_home() -> Path:
    if os.getenv("TRADING_HOME"):
        return Path(os.environ["TRADING_HOME"])
    p = Path.cwd()
    for d in [p, *p.parents]:
        if (d / "config" / "trading.json").exists():
            return d
    # Standalone install (e.g. uploaded to claude.ai): seed the working dir from the bundled default
    (p / "config").mkdir(exist_ok=True)
    shutil.copy(Path(__file__).resolve().parent.parent / "assets" / "default-config.json", p / "config" / "trading.json")
    return p


HOME = find_home()
os.chdir(HOME)  # so .env, journal/ and state/ resolve consistently
CFG = json.loads((HOME / "config" / "trading.json").read_text())
LIMITS = CFG["limits"]
WATCH = {w["symbol"]: w for w in CFG["watchlist"]}
STATE = HOME / "state"
STATE.mkdir(exist_ok=True)


def out(obj) -> None:
    print(json.dumps(obj, indent=2, default=str))


def today_et() -> date:
    return datetime.now(ET).date()


def completed_bars(bars: list[dict], market_open: bool) -> list[dict]:
    """Drop today's still-forming daily bar: deciding on a partial bar is lookahead noise."""
    if bars and market_open:
        last = datetime.fromisoformat(bars[-1]["t"].replace("Z", "+00:00")).astimezone(ET).date()
        if last == today_et():
            return bars[:-1]
    return bars


def session_minutes(clock: dict) -> tuple[float, float]:
    """Minutes since the 09:30 ET open and until the (possibly early) close."""
    now = datetime.fromisoformat(clock["timestamp"]).astimezone(ET)
    close = datetime.fromisoformat(clock["next_close"]).astimezone(ET)
    open_ = now.replace(hour=9, minute=30, second=0, microsecond=0)
    return (now - open_).total_seconds() / 60, (close - now).total_seconds() / 60


def read_json(path: Path, default):
    try:
        return json.loads(path.read_text())
    except (FileNotFoundError, json.JSONDecodeError):
        return default


def portfolio(api: Alpaca) -> risk.Portfolio:
    acct = api.account()
    pos = {p["symbol"]: float(p["market_value"]) for p in api.positions()}
    equity = float(acct["equity"])
    peak_file = STATE / "peak.json"
    peak = max(read_json(peak_file, {}).get("peak_equity", 0.0), equity)
    peak_file.write_text(json.dumps({"peak_equity": peak, "updated": datetime.now(timezone.utc).isoformat()}))
    start = datetime.combine(today_et(), datetime.min.time(), ET).astimezone(timezone.utc).isoformat()
    todays = [o for o in api.orders(status="all", after=start)
              if o["side"] == "buy" and o["status"] not in ("canceled", "rejected", "expired")]
    return risk.Portfolio(equity=equity, cash=float(acct["cash"]), last_equity=float(acct["last_equity"]),
                          peak_equity=peak, positions=pos, trades_today=len(todays))


def guard_live(api: Alpaca, execute: bool) -> None:
    if execute and not api.is_paper and os.getenv("ALLOW_LIVE_TRADING") != "yes":
        sys.exit("LIVE endpoint detected. Refusing to execute without ALLOW_LIVE_TRADING=yes.")


def cmd_status(api: Alpaca, a) -> None:
    clock = api.clock()
    p = portfolio(api)
    out({"paper": api.is_paper, "clock": clock, "equity": p.equity, "cash": p.cash,
         "day_pnl_pct": round((p.equity / p.last_equity - 1) * 100, 3) if p.last_equity else None,
         "drawdown_from_peak_pct": round((p.equity / p.peak_equity - 1) * 100, 3),
         "positions": api.positions(), "open_orders": api.orders(status="open"),
         "trades_today": p.trades_today, "kill_switch": risk.kill_switch(p, LIMITS)})


def cmd_research(api: Alpaca, a) -> None:
    syms = a.symbols or list(WATCH)
    is_open = api.clock()["is_open"]
    res = {}
    for s in syms:
        try:
            res[s] = signals.analyze(completed_bars(api.bars(s), is_open))
        except AlpacaError as e:
            res[s] = {"signal": "error", "error": str(e)}
    news = {}
    if not a.no_news:
        for s in syms:
            try:
                news[s] = [{"t": n["created_at"], "headline": n["headline"], "source": n.get("source")}
                           for n in api.news([s], limit=LIMITS.get("news_per_symbol", 5))]
            except AlpacaError as e:
                news[s] = [{"error": str(e)}]
    out({"as_of": datetime.now(ET).isoformat(), "market_open": is_open, "signals": res, "news": news})


def cmd_buy(api: Alpaca, a) -> None:
    guard_live(api, a.execute)
    s = a.symbol.upper()
    clock = api.clock()
    p = portfolio(api)
    an = signals.analyze(completed_bars(api.bars(s), clock["is_open"]))
    if an.get("signal") != "buy":
        out({"ok": False, "reasons": [f"model signal is '{an.get('signal')}', not 'buy'"], "analysis": an})
        return
    q = api.latest_quote(s)
    ask = q.get("ap") or an["price"]
    limit_px = round(ask * (1 + LIMITS["entry_offset_pct"] / 100), 2)
    max_alloc = WATCH.get(s, {}).get("max_allocation_pct", LIMITS["max_position_pct"])
    qty = risk.size_position(p.equity, limit_px, an["atr14"], LIMITS, max_alloc)
    stop, target = risk.stop_and_target("buy", limit_px, an["atr14"], LIMITS)
    since, to_close = session_minutes(clock)
    v = risk.validate("buy", s, qty, limit_px, q, p, LIMITS, max_alloc, set(WATCH), clock["is_open"], since, to_close)
    payload = {"symbol": s, "qty": str(qty), "side": "buy", "type": "limit", "time_in_force": "day",
               "limit_price": str(limit_px), "order_class": "bracket",
               "take_profit": {"limit_price": str(target)},
               "stop_loss": {"stop_price": str(stop)},
               "client_order_id": f"agent-{s}-{datetime.now(timezone.utc):%Y%m%d%H%M%S}"}
    result = {"ok": v.ok, "reasons": v.reasons, "payload": payload, "analysis": an, "quote": q,
              "risk_at_stop": round(qty * (limit_px - stop), 2),
              "risk_at_stop_pct_equity": round(qty * (limit_px - stop) / p.equity * 100, 3)}
    if v.ok and a.execute:
        result["order"] = api.submit_order(payload)
        log_trade({"action": "buy", **payload, "analysis": an})
    out(result)


def cmd_sell(api: Alpaca, a) -> None:
    guard_live(api, a.execute)
    s = a.symbol.upper()
    clock = api.clock()
    pos = next((x for x in api.positions() if x["symbol"] == s), None)
    if not pos:
        out({"ok": False, "reasons": [f"no position in {s}"]})
        return
    q = api.latest_quote(s)
    bid = q.get("bp") or float(pos["current_price"])
    limit_px = round(bid * (1 - LIMITS["exit_offset_pct"] / 100), 2)
    qty = int(math.floor(float(pos["qty"])))
    held = [o for o in api.orders(status="open") if o["symbol"] == s]
    reasons = [] if clock["is_open"] else ["market is not open"]
    payload = {"symbol": s, "qty": str(qty), "side": "sell", "type": "limit",
               "time_in_force": "day", "limit_price": str(limit_px)}
    result = {"ok": not reasons, "reasons": reasons, "payload": payload, "cancels_first": [o["id"] for o in held]}
    if not reasons and a.execute:
        for o in held:  # bracket legs reserve the shares; release them first
            api.cancel_order(o["id"])
        result["order"] = api.submit_order(payload)
        log_trade({"action": "sell", **payload, "reason": a.reason})
    out(result)


def cmd_flatten(api: Alpaca, a) -> None:
    guard_live(api, a.execute)
    if not a.execute:
        out({"dry_run": True, "would_cancel": len(api.orders()), "would_close": [p["symbol"] for p in api.positions()]})
        return
    api.cancel_all_orders()
    closed = [api.close_position(p["symbol"]) for p in api.positions()]
    log_trade({"action": "flatten", "reason": a.reason})
    out({"canceled_all": True, "closed": closed})


def log_trade(rec: dict) -> None:
    rec["ts"] = datetime.now(timezone.utc).isoformat()
    with open(STATE / "trades.jsonl", "a") as f:
        f.write(json.dumps(rec, default=str) + "\n")


def cmd_journal(api, a) -> None:
    d = HOME / "journal" / f"{today_et():%Y-%m-%d}.md"
    d.parent.mkdir(exist_ok=True)
    if not d.exists():
        tpl = (SKILL_DIR / "references" / "journal-template.md").read_text()
        d.write_text(tpl.replace("{{DATE}}", f"{today_et():%Y-%m-%d}"))
    out({"journal": str(d.relative_to(HOME))})


def cmd_heartbeat(api, a) -> None:
    hb = read_json(STATE / "heartbeat.json", {})
    hb[a.routine] = {"ts": datetime.now(timezone.utc).isoformat(), "status": a.status}
    (STATE / "heartbeat.json").write_text(json.dumps(hb, indent=2))
    out(hb)


def cmd_review(api: Alpaca, a) -> None:
    h = api.portfolio_history(period=a.period)
    eq = [x for x in (h.get("equity") or []) if x]
    if len(eq) < 5:
        out({"error": "not enough equity history yet", "points": len(eq)})
        return
    rets = [b / a_ - 1 for a_, b in zip(eq[:-1], eq[1:])]
    mu = sum(rets) / len(rets)
    sd = (sum((r - mu) ** 2 for r in rets) / len(rets)) ** 0.5
    peak, mdd = eq[0], 0.0
    for x in eq:
        peak = max(peak, x)
        mdd = min(mdd, x / peak - 1)
    spy = [b["c"] for b in api.bars("SPY", days={"1M": 31, "3M": 92, "6M": 183, "1A": 366}.get(a.period, 92))]
    trades = [json.loads(l) for l in open(STATE / "trades.jsonl")] if (STATE / "trades.jsonl").exists() else []
    out({"period": a.period, "total_return": round(eq[-1] / eq[0] - 1, 4),
         "spy_return": round(spy[-1] / spy[0] - 1, 4) if len(spy) > 1 else None,
         "sharpe_daily_ann": round(mu / sd * 252 ** 0.5, 2) if sd else None,
         "max_drawdown": round(mdd, 4), "sessions": len(eq),
         "orders_logged": len(trades),
         "graduation_ready": len(trades) >= CFG["graduation"]["min_trades"] and len(eq) >= CFG["graduation"]["min_sessions"],
         "note": "Sharpe on <60 sessions is noise; judge process adherence first."})


def cmd_freshness(api, a) -> None:
    src = json.loads((SKILL_DIR / "references" / "sources.json").read_text())
    stale = []
    for s in src["sources"]:
        age = (date.today() - date.fromisoformat(s["last_verified"])).days
        if age > s.get("max_age_days", 30):
            stale.append({**s, "age_days": age})
    out({"stale": stale, "total": len(src["sources"])})
    sys.exit(1 if stale else 0)


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sp = ap.add_subparsers(dest="cmd", required=True)
    sp.add_parser("status")
    r = sp.add_parser("research"); r.add_argument("symbols", nargs="*"); r.add_argument("--no-news", action="store_true")
    b = sp.add_parser("buy"); b.add_argument("symbol"); b.add_argument("--execute", action="store_true")
    s = sp.add_parser("sell"); s.add_argument("symbol"); s.add_argument("--execute", action="store_true")
    s.add_argument("--reason", default="")
    f = sp.add_parser("flatten"); f.add_argument("--execute", action="store_true"); f.add_argument("--reason", default="")
    sp.add_parser("journal")
    h = sp.add_parser("heartbeat"); h.add_argument("routine"); h.add_argument("--status", default="ok")
    rv = sp.add_parser("review"); rv.add_argument("--period", default="3M", choices=["1M", "3M", "6M", "1A"])
    sp.add_parser("freshness")
    a = ap.parse_args()

    offline = {"journal": cmd_journal, "heartbeat": cmd_heartbeat, "freshness": cmd_freshness}
    if a.cmd in offline:
        return offline[a.cmd](None, a)
    try:
        api = Alpaca()
        {"status": cmd_status, "research": cmd_research, "buy": cmd_buy, "sell": cmd_sell,
         "flatten": cmd_flatten, "review": cmd_review}[a.cmd](api, a)
    except AlpacaError as e:
        out({"error": str(e)})
        sys.exit(2)


if __name__ == "__main__":
    main()
