#!/usr/bin/env python3
"""Entrypoint: python3 .claude/skills/crypto-trading/scripts/crypto.py [--demo] <command> ..."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from cryptobot.cli import main  # noqa: E402

main()
