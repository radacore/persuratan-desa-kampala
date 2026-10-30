"""Webhook Telegram dan WhatsApp (Fonnte)."""

from __future__ import annotations

import logging
import secrets
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session

from app.channels import base as channel
from app.config import settings
from app.db import get_db
from app.services import ratelimit
from app.services.notifications import kirim_telegram, kirim_whatsapp

log = logging.getLogger("siladesa.webhook")

router = APIRouter(tags=["webhook"])


def _cek_secret(secret: str, harapan: str) -> None:
    if not harapan:
        raise HTTPException(status_code=503, detail="Webhook belum dikonfigurasi.")
    if not secrets.compare_digest(secret, harapan):
        raise HTTPException(status_code=403, detail="Secret webhook salah.")


async def _payload(request: Request) -> dict[str, Any]:
    tipe = request.headers.get("content-type", "")
    if "application/json" in tipe:
        data = await request.json()
        return data if isinstance(data, dict) else {}
    form = await request.form()
    return {k: v for k, v in form.items()}


# --------------------------------------------------------------------------- #
# Telegram
# --------------------------------------------------------------------------- #
@router.post("/telegram/{secret}")
async def telegram(secret: str, request: Request, db: Session = Depends(get_db)):
    ratelimit.batasi_webhook(request)
    _cek_secret(secret, settings.telegram_webhook_secret)
    data = await _payload(request)

    pesan = data.get("message") or data.get("edited_message") or {}
    chat = (pesan.get("chat") or {})
    chat_id = chat.get("id")
    teks = pesan.get("text") or ""
    if chat_id is None or not teks:
        return {"ok": True, "dilewati": True}

    if teks.strip().lower() in {"/start", "/menu"}:
        teks = "menu"

    hasil = channel.proses(db, "telegram", str(chat_id), teks)
    db.commit()

    balasan = channel.gabung_balasan(hasil)
    kirim_telegram(str(chat_id), balasan)
    return {"ok": True, "state": hasil.get("state"), "tiket": hasil.get("tiket")}


# --------------------------------------------------------------------------- #
# WhatsApp (Fonnte)
# --------------------------------------------------------------------------- #
@router.post("/whatsapp/{secret}")
async def whatsapp(secret: str, request: Request, db: Session = Depends(get_db)):
    ratelimit.batasi_webhook(request)
    _cek_secret(secret, settings.fonnte_webhook_token)
    data = await _payload(request)

    # Fonnte mengirim field `sender`, `message`, `name`, `device`.
    pengirim = data.get("sender") or data.get("from") or data.get("phone")
    teks = data.get("message") or data.get("text") or ""
    if not pengirim or not teks:
        return {"ok": True, "dilewati": True}

    # Abaikan pesan grup dan pesan dari perangkat sendiri.
    if str(data.get("isgroup", "false")).lower() == "true":
        return {"ok": True, "dilewati": "grup"}
    if str(data.get("fromMe", data.get("from_me", "false"))).lower() == "true":
        return {"ok": True, "dilewati": "pesan sendiri"}

    hasil = channel.proses(db, "whatsapp", str(pengirim), teks)
    db.commit()

    balasan = channel.gabung_balasan(hasil)
    kirim_whatsapp(str(pengirim), balasan)
    return {"ok": True, "state": hasil.get("state"), "tiket": hasil.get("tiket")}
