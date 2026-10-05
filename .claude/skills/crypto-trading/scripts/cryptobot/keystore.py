"""Encrypted API-key store (Fernet: AES-128-CBC + HMAC-SHA256, key derived with scrypt).

Precedence: environment variables > encrypted keystore. The passphrase comes from
CRYPTOBOT_PASSPHRASE or an interactive prompt; it is never written to disk.

Encryption at rest is the LAST line of defence. The first lines are on the exchange side:
trade-only keys (withdrawals DISABLED), IP allow-listing, and a separate sub-account.
"""
from __future__ import annotations

import base64
import getpass
import json
import os
from pathlib import Path

DEFAULT_PATH = Path(os.getenv("CRYPTOBOT_KEYSTORE", Path.home() / ".cryptobot" / "keys.enc"))


def _fernet(passphrase: str, salt: bytes):
    from cryptography.fernet import Fernet
    from cryptography.hazmat.primitives.kdf.scrypt import Scrypt
    key = Scrypt(salt=salt, length=32, n=2 ** 15, r=8, p=1).derive(passphrase.encode())
    return Fernet(base64.urlsafe_b64encode(key))


def _passphrase(confirm=False) -> str:
    p = os.getenv("CRYPTOBOT_PASSPHRASE")
    if p:
        return p
    p = getpass.getpass("Keystore passphrase: ")
    if confirm and p != getpass.getpass("Repeat: "):
        raise SystemExit("passphrases differ")
    return p


def load(path: Path = DEFAULT_PATH, passphrase: str | None = None) -> dict:
    if not path.exists():
        return {}
    blob = json.loads(path.read_text())
    f = _fernet(passphrase or _passphrase(), base64.b64decode(blob["salt"]))
    return json.loads(f.decrypt(blob["data"].encode()))


def save(secrets: dict, path: Path = DEFAULT_PATH, passphrase: str | None = None) -> None:
    salt = os.urandom(16)
    f = _fernet(passphrase or _passphrase(confirm=True), salt)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps({"v": 1, "salt": base64.b64encode(salt).decode(),
                               "data": f.encrypt(json.dumps(secrets).encode()).decode()}))
    os.chmod(tmp, 0o600)
    tmp.replace(path)


def credentials(exchange_id: str, path: Path = DEFAULT_PATH) -> dict:
    from .exchange import credentials_from_env
    env = credentials_from_env(exchange_id)
    if env:
        return env
    return load(path).get(exchange_id, {})
