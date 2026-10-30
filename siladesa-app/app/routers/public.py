"""Halaman publik: beranda, pelacakan, verifikasi QR, dan unduh dokumen."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import FileResponse, HTMLResponse, RedirectResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import settings
from app.db import get_db
from app.deps import client_ip
from app.models import Document, Service
from app.security import read_download
from app.services import applications as appsvc
from app.services import ratelimit
from app.services import verification as verif
from app.services.documents import path_dokumen
from app.templating import render

router = APIRouter(tags=["publik"])

#: Panjang maksimum token QR (`document.qr_token` = String(64)).
#: Token lebih panjang ditolak sebelum menyentuh basis data agar PostgreSQL
#: tidak melempar DataError.
MAKS_TOKEN_VERIFIKASI = 64


@router.get("/", response_class=HTMLResponse)
def beranda(request: Request, db: Session = Depends(get_db)):
    layanan = db.execute(
        select(Service).where(Service.aktif.is_(True)).order_by(Service.urutan)
    ).scalars().all()
    return render(request, "public/index.html", {"layanan": layanan})


@router.get("/lacak", response_class=HTMLResponse)
def lacak(
    request: Request,
    tiket: str | None = Query(default=None),
    nik: str | None = Query(default=None),
    db: Session = Depends(get_db),
):
    hasil = None
    pesan = None
    tiket = (tiket or "").strip().upper()
    nik = "".join(ch for ch in (nik or "") if ch.isdigit())
    if tiket:
        if len(nik) != 16:
            pesan = (
                "Masukkan NIK pemohon (16 digit) bersama nomor tiket. "
                "NIK dipakai untuk memastikan tiket ini benar milik Anda."
            )
        else:
            app = appsvc.lacak(db, tiket, nik)
            if app is None:
                # Pesan sama untuk tiket salah dan NIK salah: jangan bocorkan
                # tiket mana yang benar-benar terdaftar.
                pesan = "Tiket atau NIK tidak cocok. Periksa kembali keduanya."
            else:
                hasil = appsvc.ringkasan_status(app)
                hasil["unduh_url"] = None
                hasil["berkas_belum_siap"] = False
                if app.status == "TERBIT":
                    if hasil["dokumen_terbit"] and app.documents:
                        from app.security import sign_download

                        hasil["unduh_url"] = f"/d/{sign_download(app.documents[-1].id)}"
                    elif app.documents:
                        # Surat pernah terbit lalu dicabut kepala desa.
                        hasil["berkas_dicabut"] = True
                    else:
                        # Seharusnya tidak terjadi: surat terbit selalu lewat
                        # "Terbitkan & buat PDF" yang juga membuat dokumennya.
                        hasil["berkas_belum_siap"] = True
    return render(
        request,
        "public/lacak.html",
        {"tiket": tiket, "nik": nik, "hasil": hasil, "pesan": pesan},
    )


@router.get("/v/{token}", response_class=HTMLResponse)
def verifikasi(
    token: str,
    request: Request,
    db: Session = Depends(get_db),
    _: None = Depends(ratelimit.batasi_halaman_verifikasi),
):
    if len(token) > MAKS_TOKEN_VERIFIKASI:
        raise HTTPException(status_code=404, detail="Token verifikasi tidak dikenal.")
    hasil = verif.verifikasi(
        db, token, ip=client_ip(request), user_agent=request.headers.get("user-agent", "")[:250]
    )
    db.commit()
    return render(request, "public/verify.html", {"hasil": hasil, "token": token})


@router.get("/d/{token}")
def unduh(token: str, db: Session = Depends(get_db)):
    document_id = read_download(token)
    if document_id is None:
        raise HTTPException(status_code=410, detail="Tautan unduh tidak sah atau sudah kedaluwarsa.")

    dokumen = db.get(Document, document_id)
    if dokumen is None or dokumen.status != "TERBIT":
        raise HTTPException(status_code=410, detail="Dokumen tidak tersedia untuk diunduh.")

    path = path_dokumen(dokumen)
    if not path.exists():
        raise HTTPException(status_code=410, detail="Berkas dokumen tidak ditemukan di penyimpanan.")

    nama = f"{dokumen.nomor_surat.replace('/', '-')}.pdf"
    return FileResponse(
        path,
        media_type="application/pdf",
        filename=nama,
        headers={"Cache-Control": "private, max-age=0, no-store"},
    )


@router.get("/unduh", response_class=HTMLResponse)
def halaman_unduh(request: Request):
    return render(
        request,
        "public/unduh.html",
        {"ttl": settings.download_token_ttl_days},
    )


@router.get("/favicon.ico")
def favicon():
    return RedirectResponse(url="/static/favicon.svg", status_code=307)
