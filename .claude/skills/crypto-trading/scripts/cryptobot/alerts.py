"""Alerts: POST to ALERT_WEBHOOK_URL (ntfy.sh topic, Slack/Discord webhook...) and always log locally."""
from __future__ import annotations

import json
import os
import time
import urllib.request
from pathlib import Path


def alert(level: str, msg: str, log_path: Path = Path("state/crypto_alerts.log"), **data) -> None:
    rec = {"ts": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()), "level": level, "msg": msg, **data}
    log_path.parent.mkdir(parents=True, exist_ok=True)
    with open(log_path, "a") as f:
        f.write(json.dumps(rec, default=str) + "\n")
    url = os.getenv("ALERT_WEBHOOK_URL")
    if not url:
        return
    body = json.dumps({"text": f"[{level}] {msg}", "content": f"[{level}] {msg}"}).encode() \
        if ("slack" in url or "discord" in url) else f"[{level}] {msg}".encode()
    try:
        urllib.request.urlopen(urllib.request.Request(url, data=body, method="POST"), timeout=10)
    except Exception as e:  # alerting must never crash trading logic
        with open(log_path, "a") as f:
            f.write(json.dumps({"level": "warn", "msg": f"alert delivery failed: {e}"}) + "\n")
