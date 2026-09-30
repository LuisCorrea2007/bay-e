"""Seguridad de emparejamiento para nodos móviles BAY-E.

Los códigos son efímeros y viven solo en memoria del Core. Los tokens de
dispositivo nunca se guardan en claro: SQLite conserva únicamente SHA-256.
"""
from __future__ import annotations

import hashlib
import hmac
import secrets
import threading
import time

_LOCK = threading.RLock()
_PAIRINGS: dict[str, float] = {}
DEFAULT_TTL_SECONDS = 300


def token_hash(token: str) -> str:
    return hashlib.sha256((token or "").encode("utf-8")).hexdigest()


def verify_token(token: str, expected_hash: str) -> bool:
    if not token or not expected_hash:
        return False
    return hmac.compare_digest(token_hash(token), expected_hash)


def create_pairing_code(ttl_seconds: int = DEFAULT_TTL_SECONDS) -> dict:
    ttl = max(30, min(900, int(ttl_seconds)))
    now = time.time()
    with _LOCK:
        _purge_expired(now)
        for _ in range(20):
            code = f"{secrets.randbelow(1_000_000):06d}"
            if code not in _PAIRINGS:
                break
        else:
            raise RuntimeError("no se pudo generar un código de emparejamiento")
        expires_at = now + ttl
        _PAIRINGS[code] = expires_at
    return {"code": code, "expires_at": expires_at, "ttl_seconds": ttl}


def claim_pairing_code(code: str) -> str | None:
    normalized = "".join(ch for ch in str(code or "") if ch.isdigit())
    now = time.time()
    with _LOCK:
        _purge_expired(now)
        expires_at = _PAIRINGS.pop(normalized, None)
        if not expires_at or expires_at < now:
            return None
    return secrets.token_urlsafe(32)


def _purge_expired(now: float | None = None) -> None:
    current = time.time() if now is None else now
    expired = [code for code, expires in _PAIRINGS.items() if expires < current]
    for code in expired:
        _PAIRINGS.pop(code, None)


def active_pairing_count() -> int:
    with _LOCK:
        _purge_expired()
        return len(_PAIRINGS)
