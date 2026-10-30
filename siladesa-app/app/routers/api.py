"""API JSON publik (dipakai widget web, bot, dan aplikasi lain)."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app import constants as C
from app.db import get_db
from app.deps import client_ip
from app.models import (
    ConversationSession,
    FeedbackResponse,
    Service,
)
from app.schemas import (
    ApplicationCreate,
    ApplicationOut,
    FeedbackIn,
    MessageIn,
    MessageOut,
    PredictIn,
    PredictOut,
    ServiceOut,
    SessionCreate,
    SessionOut,
    TrackingOut,
    VerifyOut,
)
from app.services import applications as appsvc
from app.services import chat as chatsvc
from app.services import ratelimit
from app.services import verification as verif
from app.services.nlp import nlp

router = APIRouter()


# --------------------------------------------------------------------------- #
# Layanan
# --------------------------------------------------------------------------- #
@router.get("/services", response_model=list[ServiceOut], tags=["layanan"])
def daftar_layanan(db: Session = Depends(get_db)):
    rows = db.execute(
        select(Service).where(Service.aktif.is_(True)).order_by(Service.urutan)
    ).scalars().all()
    return rows


@router.get("/services/{kode}", response_model=ServiceOut, tags=["layanan"])
def detail_layanan(kode: str, db: Session = Depends(get_db)):
    row = db.execute(
        select(Service).where(Service.kode == kode.upper(), Service.aktif.is_(True))
    ).scalar_one_or_none()
    if row is None:
        raise HTTPException(status_code=404, detail=f"Layanan '{kode}' tidak ditemukan.")
    return row


# --------------------------------------------------------------------------- #
# Chat
# --------------------------------------------------------------------------- #
@router.post(
    "/chat/sessions", response_model=SessionOut, status_code=status.HTTP_201_CREATED,
    tags=["chat"], dependencies=[Depends(ratelimit.batasi_chat)],
)
def buka_sesi(payload: SessionCreate, db: Session = Depends(get_db)):
    sesi, sapaan = chatsvc.buka_sesi(db, payload.channel, payload.kontak)
    db.commit()
    return SessionOut(
        session_id=sesi.id,
        channel=sesi.channel,
        state=sesi.state,
        balasan=sapaan,
        pilihan=chatsvc.PILIHAN_MENU,
    )


@router.post(
    "/chat/messages", response_model=MessageOut, tags=["chat"],
    dependencies=[Depends(ratelimit.batasi_chat)],
)
def kirim_pesan(payload: MessageIn, db: Session = Depends(get_db)):
    sesi = chatsvc.ambil_sesi(db, payload.session_id)
    if sesi is None:
        raise HTTPException(
            status_code=404, detail="Sesi tidak ditemukan atau sudah kedaluwarsa."
        )
    hasil = chatsvc.tangani(db, sesi, payload.pesan)
    db.commit()
    return MessageOut(**hasil)


@router.get("/chat/sessions/{session_id}/messages", tags=["chat"])
def riwayat_sesi(session_id: str, db: Session = Depends(get_db)):
    sesi = chatsvc.ambil_sesi(db, session_id)
    if sesi is None:
        raise HTTPException(status_code=404, detail="Sesi tidak ditemukan.")
    return {
        "session_id": sesi.id,
        "state": sesi.state,
        "pesan": [
            {
                "arah": m.arah,
                "isi": m.isi,
                "intent": m.intent_kode,
                "confidence": m.confidence,
                "waktu": m.created_at,
            }
            for m in sesi.messages
        ],
    }


@router.post("/chat/feedback", status_code=status.HTTP_201_CREATED, tags=["chat"])
def kirim_umpan_balik(payload: FeedbackIn, db: Session = Depends(get_db)):
    sesi = db.get(ConversationSession, payload.session_id)
    if sesi is None:
        raise HTTPException(status_code=404, detail="Sesi tidak ditemukan.")
    row = FeedbackResponse(
        session_id=payload.session_id,
        chat_message_id=payload.chat_message_id,
        rating=payload.rating,
        komentar=payload.komentar,
    )
    db.add(row)
    db.commit()
    return {"status": "tersimpan", "id": row.id}


# --------------------------------------------------------------------------- #
# Pengajuan
# --------------------------------------------------------------------------- #
@router.post(
    "/applications", response_model=ApplicationOut, status_code=status.HTTP_201_CREATED,
    tags=["pengajuan"],
)
def ajukan(payload: ApplicationCreate, db: Session = Depends(get_db)):
    service = db.execute(
        select(Service).where(Service.kode == payload.service_kode.upper(), Service.aktif.is_(True))
    ).scalar_one_or_none()
    if service is None:
        raise HTTPException(status_code=404, detail="Layanan tidak ditemukan.")

    data: dict[str, Any] = {
        k: v for k, v in payload.citizen.model_dump().items() if v not in (None, "")
    }
    data.update({k: v for k, v in payload.form_data.items() if v not in (None, "")})

    draft = appsvc.buat_draft(
        db, service=service, form_data=data, channel=payload.channel,
        session_id=payload.session_id,
    )
    try:
        appsvc.kirim_pengajuan(db, draft)
    except appsvc.KesalahanPengajuan as exc:
        db.rollback()
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    db.commit()
    return ApplicationOut(
        id=draft.id,
        ticket_no=draft.ticket_no,
        status=draft.status,
        channel=draft.channel,
        created_at=draft.created_at,
        submitted_at=draft.submitted_at,
        service_kode=service.kode,
        service_nama=service.nama,
    )


@router.get("/track/{ticket_no}", response_model=TrackingOut, tags=["pengajuan"])
def lacak(
    ticket_no: str,
    nik: str = Query(min_length=16, max_length=16, description="NIK pemohon, wajib"),
    db: Session = Depends(get_db),
):
    """Status pengajuan. NIK wajib karena nomor tiket berurutan dan mudah ditebak."""
    app = appsvc.lacak(db, ticket_no, nik)
    if app is None:
        raise HTTPException(status_code=404, detail="Tiket atau NIK tidak cocok.")
    ringkas = appsvc.ringkasan_status(app)
    return TrackingOut(**ringkas)


# --------------------------------------------------------------------------- #
# Verifikasi
# --------------------------------------------------------------------------- #
@router.get(
    "/verify/{token}",
    response_model=VerifyOut,
    tags=["verifikasi"],
    dependencies=[Depends(ratelimit.batasi_verifikasi)],
)
def verifikasi(token: str, request: Request, db: Session = Depends(get_db)):
    hasil = verif.verifikasi(
        db, token, ip=client_ip(request), user_agent=request.headers.get("user-agent", "")[:250]
    )
    db.commit()
    return VerifyOut(**hasil)


# --------------------------------------------------------------------------- #
# Diagnostik model
# --------------------------------------------------------------------------- #
@router.post(
    "/predict", response_model=PredictOut, tags=["nlp"],
    dependencies=[Depends(ratelimit.batasi_prediksi)],
)
def prediksi(payload: PredictIn):
    hasil = nlp.prediksi(payload.teks)
    tinggi, rendah = C.CONFIDENCE_TINGGI, C.CONFIDENCE_RENDAH
    if hasil.confidence >= tinggi:
        keputusan = "jawab"
    elif hasil.confidence >= rendah:
        keputusan = "klarifikasi"
    else:
        keputusan = "eskalasi"
    return PredictOut(
        intent=hasil.intent,
        confidence=hasil.confidence,
        keputusan=keputusan,
        alternatif=[{"intent": k, "confidence": v} for k, v in hasil.peringkat],
    )
