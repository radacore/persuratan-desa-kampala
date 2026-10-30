"""Penanganan pesan masuk yang dipakai bersama oleh semua kanal percakapan."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import ConversationSession
from app.services import chat as chatsvc

#: Sesi baru dibuat bila pesan terakhir lebih lama dari ini.
JEDA_SESI_BARU = timedelta(hours=6)


def sesi_untuk(db: Session, channel: str, kontak: str) -> ConversationSession:
    """Ambil sesi aktif terakhir untuk kanal+kontak, atau buat yang baru."""
    sesi = db.execute(
        select(ConversationSession)
        .where(
            ConversationSession.channel == channel,
            ConversationSession.kontak == kontak[:60],
        )
        .order_by(ConversationSession.last_activity_at.desc())
    ).scalars().first()

    batas = datetime.now(timezone.utc) - JEDA_SESI_BARU
    if sesi is not None:
        terakhir = sesi.last_activity_at
        if terakhir is not None and terakhir.tzinfo is None:
            terakhir = terakhir.replace(tzinfo=timezone.utc)
        if terakhir is not None and terakhir >= batas:
            return sesi

    return chatsvc.sesi_baru(db, channel, kontak)


def proses(db: Session, channel: str, kontak: str, teks: str) -> dict[str, Any]:
    """Proses satu pesan dari kanal mana pun. Tidak melakukan commit."""
    sesi = sesi_untuk(db, channel, kontak)
    return chatsvc.tangani(db, sesi, teks)


def gabung_balasan(hasil: dict[str, Any]) -> str:
    """Gabungkan daftar balasan menjadi satu pesan utuh untuk WhatsApp/Telegram."""
    return "\n\n".join(hasil.get("balasan") or [])
