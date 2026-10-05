"""Minimal, dependency-free Alpaca REST client (stdlib only).

Trading endpoints live on APCA_BASE_URL (paper by default); market data and
news live on data.alpaca.markets regardless of paper/live. Accepts both the
SDK env names (APCA_*) and the MCP-server env names (ALPACA_*).
"""
from __future__ import annotations

import json
import os
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timedelta, timezone

PAPER_URL = "https://paper-api.alpaca.markets"
LIVE_URL = "https://api.alpaca.markets"
DATA_URL = os.getenv("APCA_DATA_URL", "https://data.alpaca.markets")


def _env(*names: str, default: str | None = None) -> str | None:
    for n in names:
        v = os.getenv(n)
        if v:
            return v
    return default


def load_dotenv(path: str = ".env") -> None:
    """Load KEY=VALUE lines into os.environ without overriding existing vars."""
    if not os.path.exists(path):
        return
    with open(path) as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            k, v = line.split("=", 1)
            os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))


class AlpacaError(RuntimeError):
    pass


class Alpaca:
    def __init__(self) -> None:
        load_dotenv()
        self.key = _env("APCA_API_KEY_ID", "ALPACA_API_KEY")
        self.secret = _env("APCA_API_SECRET_KEY", "ALPACA_SECRET_KEY")
        self.base = _env("APCA_BASE_URL", default=PAPER_URL).rstrip("/")
        self.feed = _env("APCA_DATA_FEED", default="iex")  # 'sip' needs a paid plan
        if not self.key or not self.secret:
            raise AlpacaError("Missing APCA_API_KEY_ID / APCA_API_SECRET_KEY (or ALPACA_* equivalents)")

    @property
    def is_paper(self) -> bool:
        return "paper-api" in self.base

    def _req(self, method: str, url: str, params: dict | None = None, body: dict | None = None):
        if params:
            url += "?" + urllib.parse.urlencode({k: v for k, v in params.items() if v is not None})
        data = json.dumps(body).encode() if body is not None else None
        req = urllib.request.Request(url, data=data, method=method)
        req.add_header("APCA-API-KEY-ID", self.key)
        req.add_header("APCA-API-SECRET-KEY", self.secret)
        req.add_header("Content-Type", "application/json")
        try:
            with urllib.request.urlopen(req, timeout=20) as r:
                raw = r.read()
                return json.loads(raw) if raw else None
        except urllib.error.HTTPError as e:
            raise AlpacaError(f"{method} {url} -> {e.code}: {e.read().decode(errors='replace')}") from e

    # ---- trading API ----
    def account(self):
        return self._req("GET", f"{self.base}/v2/account")

    def positions(self):
        return self._req("GET", f"{self.base}/v2/positions")

    def clock(self):
        return self._req("GET", f"{self.base}/v2/clock")

    def orders(self, status: str = "open", after: str | None = None, limit: int = 100):
        return self._req("GET", f"{self.base}/v2/orders",
                         {"status": status, "after": after, "limit": limit, "nested": "true"})

    def portfolio_history(self, period: str = "1M", timeframe: str = "1D"):
        return self._req("GET", f"{self.base}/v2/account/portfolio/history",
                         {"period": period, "timeframe": timeframe})

    def asset(self, symbol: str):
        return self._req("GET", f"{self.base}/v2/assets/{symbol}")

    def submit_order(self, payload: dict):
        return self._req("POST", f"{self.base}/v2/orders", body=payload)

    def cancel_order(self, order_id: str):
        return self._req("DELETE", f"{self.base}/v2/orders/{order_id}")

    def cancel_all_orders(self):
        return self._req("DELETE", f"{self.base}/v2/orders")

    def close_position(self, symbol: str):
        return self._req("DELETE", f"{self.base}/v2/positions/{symbol}")

    # ---- market data API ----
    def bars(self, symbol: str, days: int = 300, timeframe: str = "1Day") -> list[dict]:
        """Daily bars, oldest first. 300 calendar days ≈ 200+ sessions for SMA200."""
        start = (datetime.now(timezone.utc) - timedelta(days=days)).strftime("%Y-%m-%dT%H:%M:%SZ")
        out, token = [], None
        while True:
            r = self._req("GET", f"{DATA_URL}/v2/stocks/{symbol}/bars",
                          {"timeframe": timeframe, "start": start, "limit": 10000,
                           "adjustment": "all", "feed": self.feed, "page_token": token})
            out.extend(r.get("bars") or [])
            token = r.get("next_page_token")
            if not token:
                return out

    def latest_quote(self, symbol: str) -> dict:
        r = self._req("GET", f"{DATA_URL}/v2/stocks/{symbol}/quotes/latest", {"feed": self.feed})
        return r.get("quote", {})

    def news(self, symbols: list[str], limit: int = 5, hours: int = 48) -> list[dict]:
        start = (datetime.now(timezone.utc) - timedelta(hours=hours)).strftime("%Y-%m-%dT%H:%M:%SZ")
        r = self._req("GET", f"{DATA_URL}/v1beta1/news",
                      {"symbols": ",".join(symbols), "limit": limit, "start": start, "sort": "desc"})
        return r.get("news", [])
