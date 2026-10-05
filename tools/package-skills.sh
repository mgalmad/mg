#!/usr/bin/env bash
# Build uploadable skill zips (claude.ai > Settings > Skills > Add > Upload skill) into dist/.
set -euo pipefail
cd "$(dirname "$0")/.."
cp config/trading.json .claude/skills/alpaca-trading/assets/default-config.json
cp config/crypto.json .claude/skills/crypto-trading/assets/default-config.json
find .claude/skills -name __pycache__ -prune -exec rm -rf {} +
mkdir -p dist && rm -f dist/*.zip
cd .claude/skills
for s in alpaca-trading crypto-trading; do
  zip -qr "../../dist/$s.zip" "$s" -x "$s/tests/*" "*/__pycache__/*" "*.pyc"
done
ls -la ../../dist
