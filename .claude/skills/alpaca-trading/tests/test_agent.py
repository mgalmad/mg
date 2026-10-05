"""End-to-end CLI paths against a fake Alpaca (no network, no keys)."""
import io
import json
import os
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parents[4]
os.environ["TRADING_HOME"] = str(ROOT)
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))
import agent  # noqa: E402


def trend_bars(n=300):
    out = []
    for i in range(n):
        c = 100 * 1.0015 ** i * (1 + (0.004 if i % 2 else -0.004))
        out.append({"o": c, "h": c * 1.01, "l": c * 0.99, "c": c, "v": 1, "t": "2025-01-01T05:00:00Z"})
    return out


class FakeAlpaca:
    is_paper = True
    base = "fake"

    def __init__(self, bars, position=None, open_orders=()):
        self._bars, self._pos, self._open = bars, position, list(open_orders)
        self.submitted, self.canceled = [], []

    def clock(self):
        return {"is_open": True, "timestamp": "2026-10-05T10:05:00.123456789-04:00",
                "next_close": "2026-10-05T16:00:00-04:00", "next_open": "2026-10-06T09:30:00-04:00"}

    def account(self):
        return {"equity": "100000", "cash": "100000", "last_equity": "100000"}

    def positions(self):
        return [self._pos] if self._pos else []

    def orders(self, status="open", after=None, limit=100):
        return self._open if status == "open" else []

    def bars(self, s, days=300):
        return self._bars

    def latest_quote(self, s):
        last = self._bars[-1]["c"]
        return {"bp": round(last - 0.01, 2), "ap": round(last + 0.01, 2)}

    def submit_order(self, p):
        self.submitted.append(p)
        return {"id": "o1", **p}

    def cancel_order(self, oid):
        self.canceled.append(oid)


def run(fn, api, **kw):
    buf = io.StringIO()
    with redirect_stdout(buf):
        fn(api, SimpleNamespace(**kw))
    return json.loads(buf.getvalue())


class TestAgent(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        agent.STATE = Path(self.tmp.name)

    def tearDown(self):
        self.tmp.cleanup()

    def test_buy_dry_run_builds_valid_bracket(self):
        api = FakeAlpaca(trend_bars())
        r = run(agent.cmd_buy, api, symbol="spy", execute=False)
        self.assertTrue(r["ok"], r["reasons"])
        p = r["payload"]
        self.assertEqual(p["order_class"], "bracket")
        self.assertEqual(p["type"], "limit")
        self.assertLess(float(p["stop_loss"]["stop_price"]), float(p["limit_price"]))
        self.assertGreater(float(p["take_profit"]["limit_price"]), float(p["limit_price"]))
        self.assertLessEqual(r["risk_at_stop_pct_equity"], 0.5 + 1e-6)
        self.assertEqual(api.submitted, [])

    def test_buy_execute_submits_and_logs(self):
        api = FakeAlpaca(trend_bars())
        r = run(agent.cmd_buy, api, symbol="SPY", execute=True)
        self.assertEqual(len(api.submitted), 1)
        self.assertTrue((agent.STATE / "trades.jsonl").exists())

    def test_buy_refused_without_buy_signal(self):
        down = [{"o": c, "h": c, "l": c, "c": c, "v": 1, "t": "2025-01-01T05:00:00Z"} for c in [100 * 0.998 ** i for i in range(300)]]
        api = FakeAlpaca(down)
        r = run(agent.cmd_buy, api, symbol="SPY", execute=True)
        self.assertFalse(r["ok"])
        self.assertEqual(api.submitted, [])

    def test_sell_cancels_bracket_legs_first(self):
        pos = {"symbol": "SPY", "qty": "10", "current_price": "150"}
        api = FakeAlpaca(trend_bars(), position=pos, open_orders=[{"id": "leg1", "symbol": "SPY"}, {"id": "x", "symbol": "QQQ"}])
        r = run(agent.cmd_sell, api, symbol="SPY", execute=True, reason="test")
        self.assertEqual(api.canceled, ["leg1"])
        self.assertEqual(api.submitted[0]["side"], "sell")
        self.assertEqual(api.submitted[0]["type"], "limit")

    def test_partial_bar_dropped_only_while_open(self):
        from datetime import datetime, timezone
        today = datetime.now(agent.ET).replace(hour=0, minute=0).astimezone(timezone.utc)
        bars = trend_bars(5) + [{"o": 1, "h": 1, "l": 1, "c": 1, "v": 1, "t": today.strftime("%Y-%m-%dT%H:%M:%SZ")}]
        self.assertEqual(len(agent.completed_bars(bars, True)), 5)
        self.assertEqual(len(agent.completed_bars(bars, False)), 6)

    def test_live_guard(self):
        api = FakeAlpaca(trend_bars())
        api.is_paper = False
        os.environ.pop("ALLOW_LIVE_TRADING", None)
        with self.assertRaises(SystemExit):
            agent.guard_live(api, True)


if __name__ == "__main__":
    unittest.main()
