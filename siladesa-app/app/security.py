"""Hashing kata sandi, cookie sesi bertanda tangan, dan token CSRF."""

from __future__ import annotations

import hmac
import secrets
from dataclasses import dataclass

from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerifyMismatchError
from itsdangerous import BadSignature, SignatureExpired, URLSafeTimedSerializer

from app.config import settings

_hasher = PasswordHasher(time_cost=3, memory_cost=65536, parallelism=2)

SESSION_COOKIE = "siladesa_session"
CSRF_COOKIE = "siladesa_csrf"
SESSION_MAX_AGE = 8 * 60 * 60  # 8 jam

_serializer = URLSafeTimedSerializer(settings.secret_key, salt="siladesa-session-v1")
_download_serializer = URLSafeTimedSerializer(settings.secret_key, salt="siladesa-download-v1")


def hash_password(plain: str) -> str:
    return _hasher.hash(plain)


def verify_password(plain: str, hashed: str) -> bool:
    try:
        return _hasher.verify(hashed, plain)
    except (VerifyMismatchError, InvalidHashError, ValueError):
        return False


def needs_rehash(hashed: str) -> bool:
    try:
        return _hasher.check_needs_rehash(hashed)
    except InvalidHashError:
        return True


@dataclass(frozen=True)
class SessionData:
    user_id: int
    role: str
    csrf: str


def issue_session(user_id: int, role: str) -> str:
    payload = {"uid": user_id, "role": role, "csrf": secrets.token_urlsafe(24)}
    return _serializer.dumps(payload)


def read_session(token: str | None) -> SessionData | None:
    if not token:
        return None
    try:
        payload = _serializer.loads(token, max_age=SESSION_MAX_AGE)
    except (BadSignature, SignatureExpired):
        return None
    try:
        return SessionData(
            user_id=int(payload["uid"]), role=str(payload["role"]), csrf=str(payload["csrf"])
        )
    except (KeyError, TypeError, ValueError):
        return None


def csrf_valid(expected: str | None, received: str | None) -> bool:
    if not expected or not received:
        return False
    return hmac.compare_digest(expected, received)


# --------------------------------------------------------------------------- #
# Token unduh dokumen (tanpa kolom DB, TTL terbatas)
# --------------------------------------------------------------------------- #
def sign_download(document_id: int) -> str:
    return _download_serializer.dumps({"doc": document_id})


def read_download(token: str) -> int | None:
    ttl = settings.download_token_ttl_days * 24 * 60 * 60
    try:
        payload = _download_serializer.loads(token, max_age=ttl)
        return int(payload["doc"])
    except (BadSignature, SignatureExpired, KeyError, TypeError, ValueError):
        return None
