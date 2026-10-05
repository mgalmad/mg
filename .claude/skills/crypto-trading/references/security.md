# Security and key management

Order of defence, strongest first:
1. **Exchange-side permissions:** trade-only keys with withdrawals **disabled**, an IP allow-list (a static IP for the bot host), a dedicated sub-account holding only bot capital, 2FA on the account, and an address allow-list for withdrawals.
2. **Process isolation:** only `crypto.py` talks to the exchange. In Claude Code, scope Bash permission to `python3 .claude/skills/crypto-trading/scripts/crypto.py:*`.
3. **Secrets at rest:** environment variables (`KRAKEN_API_KEY`, `KRAKEN_API_SECRET`, `KRAKEN_API_PASSWORD` if needed), *or* the encrypted keystore `~/.cryptobot/keys.enc`. The keystore uses Fernet (AES-128-CBC + HMAC-SHA256) with a scrypt-derived key (n=2¹⁵, r=8, p=1). The file is chmod 600 and written atomically. The passphrase comes from `CRYPTOBOT_PASSPHRASE` or a prompt.
   - In cloud sessions, use the environment's secret settings and not the keystore.
4. **Audit:** `state/crypto_ledger.jsonl` is hash-chained, and `cb verify-ledger` detects any edit. Commit it so the history lives in git as well.
5. **Rotation:** rotate keys every 90 days, and immediately after any suspected exposure (pasted in chat, committed, or logged).

Never: print keys, send them to the LLM, keep them in `config/`, or give withdrawal rights to a bot.
