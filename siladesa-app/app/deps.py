"""Dependensi FastAPI: sesi admin, otorisasi peran, dan CSRF."""

from __future__ import annotations

from typing import Annotated

from fastapi import Depends, HTTPException, Request, status
from sqlalchemy.orm import Session

from app import constants as C
from app.db import get_db
from app.models import AdminUser
from app.security import CSRF_COOKIE, SESSION_COOKIE, csrf_valid, read_session

DbSession = Annotated[Session, Depends(get_db)]


class RedirectToLogin(Exception):
    """Dilempar agar handler dapat mengalihkan ke halaman masuk."""

    def __init__(self, next_url: str = "/admin") -> None:
        self.next_url = next_url


def current_user(request: Request, db: DbSession) -> AdminUser | None:
    data = read_session(request.cookies.get(SESSION_COOKIE))
    if data is None:
        return None
    user = db.get(AdminUser, data.user_id)
    if user is None or not user.aktif:
        return None
    request.state.csrf = data.csrf
    request.state.user = user
    return user


CurrentUser = Annotated[AdminUser | None, Depends(current_user)]


def require_login(request: Request, user: CurrentUser) -> AdminUser:
    if user is None:
        raise RedirectToLogin(next_url=str(request.url.path))
    return user


LoginUser = Annotated[AdminUser, Depends(require_login)]


def require_permission(permission: str):
    """Pabrik dependensi: pastikan pengguna memiliki izin tertentu."""

    def _dep(user: LoginUser) -> AdminUser:
        if not C.boleh(user.role, permission):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Peran '{user.role}' tidak berhak melakukan '{permission}'.",
            )
        return user

    return _dep


def assert_csrf(request: Request, token: str | None) -> None:
    expected = getattr(request.state, "csrf", None) or request.cookies.get(CSRF_COOKIE)
    if not csrf_valid(expected, token):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Token CSRF tidak valid atau kedaluwarsa. Muat ulang halaman.",
        )


def client_ip(request: Request) -> str:
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.client.host if request.client else "-"
