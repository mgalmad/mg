import json
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))
import risk  # noqa: E402
import signals  # noqa: E402

LIMITS = json.loads((Path(__file__).resolve().parents[4] / "config" / "trading.json").read_text())["limits"]


def bars_from(closes, spread=0.01):
    return [{"o": c, "h": c * (1 + spread), "l": c * (1 - spread), "c": c, "v": 1, "t": f"d{i}"}
            for i, c in enumerate(closes)]


class TestIndicators(unittest.TestCase):
    def test_sma(self):
        self.assertEqual(signals.sma([1, 2, 3, 4], 2), 3.5)
        self.assertIsNone(signals.sma([1], 2))

    def test_rsi_extremes(self):
        self.assertEqual(signals.rsi(list(range(1, 30))), 100.0)
        self.assertLess(signals.rsi(list(range(30, 1, -1))), 1)

    def test_atr_constant_range(self):
        c = [100.0] * 30
        self.assertAlmostEqual(signals.atr([101] * 30, [99] * 30, c), 2.0)

    def test_uptrend_is_buy_downtrend_is_exit(self):
        up = [100 * 1.0015 ** i for i in range(300)]
        # gentle noise so RSI is not pinned at 100
        up = [x * (1 + (0.004 if i % 2 else -0.004)) for i, x in enumerate(up)]
        self.assertEqual(signals.analyze(bars_from(up))["signal"], "buy")
        down = [100 * 0.998 ** i for i in range(300)]
        self.assertEqual(signals.analyze(bars_from(down))["signal"], "exit")

    def test_overextended_blocks_buy(self):
        up = [100 * 1.0015 ** i for i in range(299)] + [100 * 1.0015 ** 299 * 1.15]
        a = signals.analyze(bars_from(up))
        self.assertNotEqual(a["signal"], "buy")

    def test_insufficient(self):
        self.assertEqual(signals.analyze(bars_from([1.0] * 10))["signal"], "insufficient_data")


class TestRisk(unittest.TestCase):
    def pf(self, **kw):
        d = dict(equity=100_000, cash=100_000, last_equity=100_000, peak_equity=100_000, positions={}, trades_today=0)
        d.update(kw)
        return risk.Portfolio(**d)

    def test_sizing_risk_vs_cap(self):
        # risk qty = 500 / (2*2) = 125 sh; cap 15% of 100k at $100 = 150 sh -> 125
        self.assertEqual(risk.size_position(100_000, 100, 2.0, LIMITS, 15), 125)
        # tiny ATR -> cap binds: 10% at $100 = 100 sh
        self.assertEqual(risk.size_position(100_000, 100, 0.1, LIMITS, 10), 100)

    def test_stop_capped_at_max_pct(self):
        stop, tgt = risk.stop_and_target("buy", 100, 10, LIMITS)  # 2*ATR = 20% -> capped at 8%
        self.assertEqual(stop, 92.0)
        self.assertEqual(tgt, 116.0)

    def q(self, bid=99.99, ask=100.01):
        return {"bp": bid, "ap": ask}

    def test_valid_order_passes(self):
        v = risk.validate("buy", "SPY", 100, 100.05, self.q(), self.pf(), LIMITS, 15, {"SPY"}, True)
        self.assertTrue(v.ok, v.reasons)

    def test_market_closed_rejected(self):
        v = risk.validate("buy", "SPY", 10, 100.05, self.q(), self.pf(), LIMITS, 15, {"SPY"}, False)
        self.assertFalse(v.ok)

    def test_session_edges_rejected(self):
        v = risk.validate("buy", "SPY", 10, 100.05, self.q(), self.pf(), LIMITS, 15, {"SPY"}, True, 5, 300)
        self.assertFalse(v.ok)
        v = risk.validate("buy", "SPY", 10, 100.05, self.q(), self.pf(), LIMITS, 15, {"SPY"}, True, 300, 5)
        self.assertFalse(v.ok)

    def test_position_cap(self):
        v = risk.validate("buy", "SPY", 200, 100.05, self.q(), self.pf(), LIMITS, 15, {"SPY"}, True)
        self.assertTrue(any("cap" in r for r in v.reasons))

    def test_cash_reserve(self):
        p = self.pf(cash=30_000, positions={"QQQ": 15_000, "IWM": 15_000, "EFA": 15_000, "TLT": 15_000, "GLD": 10_000})
        v = risk.validate("buy", "SPY", 100, 100.05, self.q(), p, LIMITS, 15, {"SPY"}, True)
        self.assertTrue(any("cash reserve" in r for r in v.reasons))

    def test_kill_switch_daily_loss_and_drawdown(self):
        self.assertTrue(risk.kill_switch(self.pf(equity=97_900), LIMITS))
        self.assertTrue(risk.kill_switch(self.pf(equity=95_000, last_equity=95_000, peak_equity=106_000), LIMITS))
        self.assertFalse(risk.kill_switch(self.pf(), LIMITS))

    def test_kill_switch_allows_exits(self):
        v = risk.validate("sell", "SPY", 10, 99.95, self.q(), self.pf(equity=90_000), LIMITS, 15, {"SPY"}, True)
        self.assertTrue(v.ok, v.reasons)

    def test_slippage_and_spread(self):
        v = risk.validate("buy", "SPY", 10, 101.0, self.q(), self.pf(), LIMITS, 15, {"SPY"}, True)
        self.assertTrue(any("above ask" in r for r in v.reasons))
        v = risk.validate("buy", "SPY", 10, 100.05, self.q(99, 101), self.pf(), LIMITS, 15, {"SPY"}, True)
        self.assertTrue(any("spread" in r for r in v.reasons))

    def test_not_in_watchlist(self):
        v = risk.validate("buy", "GME", 10, 100.05, self.q(), self.pf(), LIMITS, 15, {"SPY"}, True)
        self.assertFalse(v.ok)


if __name__ == "__main__":
    unittest.main()
