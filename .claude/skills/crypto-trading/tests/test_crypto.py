import json
import math
import os
import random
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[4]
os.environ["TRADING_HOME"] = str(ROOT)
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))
from cryptobot import arbitrage, backtest as bt, demo, indicators as ind, risk  # noqa: E402
from cryptobot.ledger import Ledger, PaperBroker  # noqa: E402
from cryptobot.strategies import MarketMaker, build  # noqa: E402

LIM = json.loads((ROOT / "config" / "crypto.json").read_text())["limits"]


def rows_from(closes):
    return [[i * 86_400_000, c, c * 1.01, c * 0.99, c, 1.0] for i, c in enumerate(closes)]


class TestIndicators(unittest.TestCase):
    def test_sma_ema_alignment(self):
        xs = list(range(1, 11))
        self.assertEqual(ind.sma(xs, 3)[:2], [None, None])
        self.assertEqual(ind.sma(xs, 3)[2], 2)
        self.assertAlmostEqual(ind.ema(xs, 3)[2], 2)

    def test_donchian_excludes_current_bar(self):
        r = rows_from([1, 2, 3, 100])
        hi, _ = ind.donchian(r, 3)
        self.assertAlmostEqual(hi[3], 3 * 1.01)

    def test_hurst_separates_trend_from_reversion(self):
        rnd = random.Random(0)
        # persistent increments (AR(1) phi=0.8 on returns): a drift alone does NOT raise H
        trend, x, r = [], 0.0, 0.0
        for _ in range(600):
            r = 0.8 * r + rnd.gauss(0, 0.01)
            x += r
            trend.append(math.exp(x))
        mr, y = [], 0.0
        for _ in range(600):
            y = -0.7 * y + rnd.gauss(0, 0.01)
            mr.append(math.exp(y) * 100)
        self.assertGreater(ind.hurst(trend), 0.6)
        self.assertLess(ind.hurst(mr), 0.4)


class TestBacktest(unittest.TestCase):
    def test_no_lookahead(self):
        """Changing the future must not change past decisions/equity."""
        rows = demo.ohlcv(800, seed=3)
        a = bt.run(rows, build("momentum"), bt.Costs())
        mutated = rows[:600] + [[r[0], r[1] * 3, r[2] * 3, r[3] * 3, r[4] * 3, r[5]] for r in rows[600:]]
        b = bt.run(mutated, build("momentum"), bt.Costs())
        self.assertEqual([e for _, e in a.equity[:600]], [e for _, e in b.equity[:600]])

    def test_costs_reduce_returns(self):
        rows = demo.ohlcv(1200, seed=5)
        cheap = bt.run(rows, build("momentum"), bt.Costs(0, 0))
        dear = bt.run(rows, build("momentum"), bt.Costs(100, 50))
        if cheap.metrics["trades"]:
            self.assertGreater(cheap.metrics["total_return"], dear.metrics["total_return"])

    def test_stop_fills_at_open_on_gap(self):
        class AlwaysIn:
            name, params = "x", {}
            def prepare(self, rows): pass
            def target(self, rows, i): return 1.0
            def stop_distance(self, rows, i): return 5.0
        rows = [[0, 100, 101, 99, 100, 1], [1, 100, 101, 99, 100, 1], [2, 100, 101, 99, 100, 1],
                [3, 80, 81, 79, 80, 1], [4, 80, 81, 79, 80, 1]]
        r = bt.run(rows, AlwaysIn(), bt.Costs(0, 0, 0.0))
        stop = [t for t in r.trades if t["side"] == "stop"][0]
        self.assertEqual(stop["price"], 80)  # gapped through 95 stop -> filled at open, not at 95

    def test_deflated_sharpe_penalises_trials(self):
        one = bt.deflated_sharpe(0.1, 1000, 0, 3, 1, 0.0004)
        many = bt.deflated_sharpe(0.1, 1000, 0, 3, 1000, 0.0004)
        self.assertGreater(one, many)
        self.assertGreater(one, 0.95)

    def test_walkforward_runs_and_reports(self):
        res = bt.walk_forward(demo.ohlcv(1600, seed=9), "momentum", [{"fast": 20, "slow": 100}, {"fast": 10, "slow": 200}],
                              train=500, test=150, warmup=250)
        self.assertIn("deflated_sharpe", res)
        self.assertGreaterEqual(len(res["folds"]), 2)


class TestRisk(unittest.TestCase):
    def book(self, **kw):
        d = dict(equity=10_000, free_quote=10_000, exchange_equity=10_000, day_start_equity=10_000, peak_equity=10_000)
        d.update(kw)
        return risk.Book(**d)

    t = {"bid": 99.95, "ask": 100.05}

    def test_kelly_bounds(self):
        self.assertEqual(risk.kelly_fraction(0.3, 1.0), 0.0)  # negative edge
        self.assertLessEqual(risk.kelly_fraction(0.6, 3.0), 0.02)

    def test_size_is_min_of_risk_cap_cash(self):
        u = risk.size_order(self.book(), 100, 5, LIM, 30)
        self.assertAlmostEqual(u, min(10_000 * 0.01 / 5, 10_000 * 0.30 / 100, 10_000 / (100 * 1.008)))

    def test_halts(self):
        self.assertTrue(risk.halts(self.book(equity=9_500), LIM))            # -5% day
        self.assertTrue(risk.halts(self.book(equity=7_900, day_start_equity=7_900), LIM))  # -21% dd
        self.assertTrue(risk.halts(self.book(consecutive_losses=7), LIM))
        self.assertFalse(risk.halts(self.book(), LIM))

    def test_de_risk(self):
        self.assertEqual(risk.de_risk_multiplier(self.book(consecutive_losses=3), LIM), 0.5)
        self.assertEqual(risk.de_risk_multiplier(self.book(consecutive_losses=5), LIM), 0.25)
        self.assertEqual(risk.de_risk_multiplier(self.book(), LIM, 1.0, 0.4), 0.5)

    def test_validate_ok_and_rejections(self):
        ok = risk.validate_buy("BTC/USD", 10, 100.06, self.t, {}, self.book(), LIM, 30, {"BTC/USD"}, 5)
        self.assertTrue(ok.ok, ok.reasons)
        bad = risk.validate_buy("BTC/USD", 10, 100.06, {"bid": 99, "ask": 101}, {}, self.book(), LIM, 30, {"BTC/USD"}, 500)
        self.assertTrue(any("spread" in r for r in bad.reasons) and any("old" in r for r in bad.reasons))
        cp = risk.validate_buy("BTC/USD", 10, 100.06, self.t, {}, self.book(total_capital=15_000), LIM, 30, {"BTC/USD"}, 5)
        self.assertTrue(any("counterparty" in r for r in cp.reasons))
        mn = risk.validate_buy("BTC/USD", 0.01, 100.06, self.t, {"limits": {"cost": {"min": 5}}}, self.book(), LIM, 30, {"BTC/USD"}, 5)
        self.assertTrue(any("minimum" in r for r in mn.reasons))


class TestArbMM(unittest.TestCase):
    def test_walk_book_vwap(self):
        px, base = arbitrage.walk_book([[100, 1], [101, 1]], quote_amount=150.5)
        self.assertAlmostEqual(base, 1.5)
        self.assertAlmostEqual(px, (100 + 0.5 * 101) / 1.5)

    def test_arb_net_of_fees(self):
        books = {"a": {"bids": [[99, 10]], "asks": [[100, 10]]}, "b": {"bids": [[101, 10]], "asks": [[102, 10]]}}
        o = arbitrage.best_opportunity(books, {"a": 10, "b": 10}, 500, min_edge_bps=10)
        self.assertEqual((o["buy_on"], o["sell_on"]), ("a", "b"))
        self.assertAlmostEqual(o["net_bps"], 100 - 20)
        self.assertTrue(o["actionable"])
        o2 = arbitrage.best_opportunity(books, {"a": 60, "b": 60}, 500, min_edge_bps=10)
        self.assertFalse(o2["actionable"])

    def test_mm_never_quotes_inside_fees_and_skews(self):
        mm = MarketMaker()
        flat = mm.quotes(100, 5, 0.0, 25)
        long_ = mm.quotes(100, 5, 0.8, 25)
        self.assertGreaterEqual(flat["half_spread_bps"], 25)
        self.assertLess(long_["reservation"], flat["reservation"])  # long inventory -> lean to sell
        self.assertFalse(flat["quote_ask"])  # spot: nothing to sell


class TestLedgerPaper(unittest.TestCase):
    def test_hash_chain_detects_tamper(self):
        with tempfile.TemporaryDirectory() as d:
            led = Ledger(Path(d) / "l.jsonl")
            for i in range(3):
                led.append({"type": "x", "i": i})
            self.assertEqual(led.verify(), (True, None))
            lines = (Path(d) / "l.jsonl").read_text().splitlines()
            lines[1] = lines[1].replace('"i": 1', '"i": 9')
            (Path(d) / "l.jsonl").write_text("\n".join(lines) + "\n")
            self.assertFalse(led.verify()[0])

    def test_paper_round_trip_pays_costs_and_tracks_streak(self):
        with tempfile.TemporaryDirectory() as d:
            pb = PaperBroker(Path(d) / "s.json", Ledger(Path(d) / "l.jsonl"), 10_000, 80, 10)
            t = {"bid": 100.0, "ask": 100.0}
            pb.buy("BTC/USD", 10, 100.1, t, stop=90)
            pb.sell("BTC/USD", t)
            self.assertLess(pb.s["cash"], 10_000)
            self.assertEqual(pb.s["loss_streak"], 1)
            pb.buy("BTC/USD", 1, 100.1, t, stop=95)
            hits = pb.check_stops({"BTC/USD": {"bid": 94.0, "ask": 94.1}})
            self.assertEqual(len(hits), 1)
            self.assertNotIn("BTC/USD", pb.s["pos"])


class TestExchangeIdempotency(unittest.TestCase):
    def test_timeout_then_found_by_client_id_no_double_order(self):
        import ccxt
        from cryptobot import exchange as exm

        class FakeX:
            has = {"fetchClosedOrders": True}
            def __init__(self): self.created = []
            def amount_to_precision(self, s, a): return str(round(a, 6))
            def price_to_precision(self, s, p): return str(round(p, 2))
            def create_order(self, sym, typ, side, amt, px, params):
                self.created.append(params["clientOrderId"])
                raise ccxt.RequestTimeout("timeout after send")  # order DID reach the exchange
            def fetch_open_orders(self, sym): return [{"id": "1", "clientOrderId": self.created[-1]}]
            def fetch_closed_orders(self, *a): return []

        e = exm.Exchange.__new__(exm.Exchange)
        e.x, e.id, e.sandbox, e.max_retries = FakeX(), "fake", True, 2
        o = e.limit_order("BTC/USD", "buy", 0.1, 100.0)
        self.assertEqual(o["id"], "1")
        self.assertEqual(len(e.x.created), 1)  # never resubmitted


if __name__ == "__main__":
    unittest.main()
