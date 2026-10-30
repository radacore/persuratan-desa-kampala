"""Pencatatan jejak audit (append-only)."""

from __future__ import annotations

from typing import Any

from sqlalchemy.orm import Session

from app.models import AdminUser, AuditLog


def catat(
    db: Session,
    *,
    aksi: str,
    entitas: str,
    entitas_id: str | int | None = None,
    aktor: AdminUser | None = None,
    aktor_email: str | None = None,
    detail: dict[str, Any] | None = None,
    ip: str | None = None,
) -> AuditLog:
    """Tambahkan satu baris audit. Tidak pernah melakukan commit sendiri."""
    row = AuditLog(
        actor_id=aktor.id if aktor else None,
        actor_email=aktor.email if aktor else aktor_email,
        aksi=aksi,
        entitas=entitas,
        entitas_id=str(entitas_id) if entitas_id is not None else None,
        detail=detail or {},
        ip_address=ip,
    )
    db.add(row)
    return row
