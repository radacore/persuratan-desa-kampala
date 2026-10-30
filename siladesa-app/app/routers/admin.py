"""Panel admin SILADESA: verifikasi, penerbitan surat, dan pengelolaan konten.

Semua route di sini berada di bawah prefiks `/admin` (dipasang di `main.py`).
Akses dijaga tiga lapis:

1. `require_login` — cookie sesi bertanda tangan wajib ada dan masih berlaku.
2. `require_permission` / `_izin` — peran harus punya izin aksi terkait.
3. `assert_csrf` — setiap POST wajib membawa token CSRF dari sesi.
"""

from __future__ import annotations

import csv
import io
import logging
import secrets
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, Request, UploadFile
from fastapi.responses import (
    FileResponse,
    HTMLResponse,
    RedirectResponse,
    Response,
    StreamingResponse,
)
from PIL import Image as PilImage
from sqlalchemy import func, or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, selectinload
from starlette.concurrency import run_in_threadpool

from app import constants as C
from app.config import settings
from app.db import get_db
from app.deps import (
    CurrentUser,
    assert_csrf,
    client_ip,
    require_login,
)
from app.models import (
    AdminUser,
    Application,
    Attachment,
    AuditLog,
    ChatMessage,
    Citizen,
    Document,
    Faq,
    FeedbackResponse,
    Intent,
    LetterNumberCounter,
    LetterTemplate,
    ModelMetric,
    NlpModel,
    Official,
    Service,
    ServiceField,
    Setting,
    TrainingSample,
    VerificationScan,
)
from app.security import (
    CSRF_COOKIE,
    SESSION_COOKIE,
    SESSION_MAX_AGE,
    hash_password,
    issue_session,
    sign_download,
    verify_password,
)
from app.services import applications as appsvc
from app.services import attachments
from app.services import chat as chatsvc
from app.services import documents as docsvc
from app.services import ratelimit
from app.services import verification as verif
from app.services.audit import catat
from app.services.nlp import nlp
from app.services.numbering import next_letter_number, peek_letter_number
from app.templating import render

log = logging.getLogger(__name__)

router = APIRouter(tags=["admin"])

PER_HALAMAN = 25

#: FR-41: unggahan scan tanda tangan dibatasi 2 MB.
TTD_MAKS_BYTE = 2 * 1024 * 1024

#: Jabatan penanda tangan tertinggi; datanya hanya boleh diubah akun Kepala Desa.
JABATAN_KEPALA_DESA = "Kepala Desa"

#: Peran yang boleh menangani materi tanda tangan (unggah/hapus scan).
ROLE_PEMEGANG_TTD = (C.Role.KEPALA_DESA.value, C.Role.SEKDES.value)


# --------------------------------------------------------------------------- #
# Utilitas
# --------------------------------------------------------------------------- #
def _ke_int(nilai: Any, bawaan: int = 0) -> int:
    try:
        return int(str(nilai).strip())
    except (TypeError, ValueError):
        return bawaan


def _bersih(nilai: Any) -> str:
    return str(nilai or "").strip()


def _ke_tanggal(nilai: Any) -> date | None:
    """Parse tanggal ISO dari form; None bila kosong, ValueError bila tidak valid."""
    teks = _bersih(nilai)
    if not teks:
        return None
    return date.fromisoformat(teks)


def _halaman(total: int, page: int, per: int = PER_HALAMAN) -> dict[str, int]:
    jumlah_halaman = max(1, (total + per - 1) // per)
    page = min(max(1, page), jumlah_halaman)
    return {
        "total": total,
        "page": page,
        "per": per,
        "jumlah_halaman": jumlah_halaman,
        "mulai": (page - 1) * per + 1 if total else 0,
        "selesai": min(page * per, total),
    }


def _kembali(url: str, pesan: str, jenis: str = "ok") -> RedirectResponse:
    from urllib.parse import quote

    return RedirectResponse(
        f"{url}{'&' if '?' in url else '?'}pesan={quote(pesan)}&jenis={jenis}",
        status_code=303,
    )


def _izin(user: AdminUser, permission: str) -> None:
    if not C.boleh(user.role, permission):
        raise HTTPException(
            status_code=403,
            detail=f"Peran '{user.role}' tidak berhak mengakses bagian ini.",
        )


def _csrf_form(form) -> str:
    return _bersih(form.get("csrf"))


def _opsi_nav(user: AdminUser) -> list[dict[str, Any]]:
    """Menu sidebar, disaring sesuai izin peran."""
    kandidat = [
        ("Ringkasan", "/admin", "dashboard", None),
        ("Pengajuan", "/admin/pengajuan", "inbox", "application.read"),
        ("Data warga", "/admin/warga", "users", "citizen.read"),
        ("Pertanyaan gagal", "/admin/pertanyaan", "help", "faq.manage"),
        ("Layanan", "/admin/layanan", "layers", "service.manage"),
        ("Template surat", "/admin/template", "file-text", "template.manage"),
        ("Nomor surat", "/admin/nomor", "hash", "number.manage"),
        ("FAQ", "/admin/faq", "message-circle", "faq.manage"),
        ("Pejabat", "/admin/pejabat", "user-check", "official.manage"),
        ("Model NLP", "/admin/model", "cpu", "model.manage"),
        ("Dataset latih", "/admin/dataset", "database", "dataset.manage"),
        ("Pengguna", "/admin/pengguna", "users", "user.manage"),
        ("Pengaturan", "/admin/pengaturan", "settings", "setting.manage"),
        ("Laporan", "/admin/laporan", "bar-chart", "report.read"),
        ("Jejak audit", "/admin/audit", "shield", "audit.read"),
    ]
    return [
        {"label": label, "href": href, "ikon": ikon}
        for label, href, ikon, izin in kandidat
        if izin is None or C.boleh(user.role, izin)
    ]


# --------------------------------------------------------------------------- #
# Autentikasi
# --------------------------------------------------------------------------- #
@router.get("/login", response_class=HTMLResponse)
def halaman_login(request: Request, user: CurrentUser, next: str = "/admin"):
    if user is not None:
        return RedirectResponse(url="/admin", status_code=303)
    if not next.startswith("/admin"):
        next = "/admin"
    token = secrets.token_urlsafe(24)
    respons = render(request, "admin/login.html", {"csrf": token, "next": next})
    respons.set_cookie(
        CSRF_COOKIE,
        token,
        max_age=SESSION_MAX_AGE,
        httponly=True,
        samesite="lax",
        secure=settings.is_production,
        path="/",
    )
    return respons


@router.post("/login")
async def proses_login(request: Request, db: Session = Depends(get_db)):
    ratelimit.batasi_login(request)
    form = await request.form()
    assert_csrf(request, _csrf_form(form))

    email = _bersih(form.get("email")).lower()
    sandi = str(form.get("password") or "")
    next_url = _bersih(form.get("next")) or "/admin"
    if not next_url.startswith("/admin"):
        next_url = "/admin"

    user = db.execute(select(AdminUser).where(AdminUser.email == email)).scalar_one_or_none()
    if user is None or not user.aktif or not verify_password(sandi, user.password_hash):
        respons = render(
            request,
            "admin/login.html",
            {
                "csrf": _bersih(form.get("csrf")),
                "next": next_url,
                "email": email,
                "galat": "Email atau kata sandi tidak cocok.",
            },
            status_code=401,
        )
        return respons

    user.last_login_at = datetime.now(timezone.utc)
    catat(
        db,
        aksi="login",
        entitas="admin_user",
        entitas_id=user.id,
        aktor=user,
        ip=client_ip(request),
    )
    db.commit()

    token = issue_session(user.id, user.role)
    respons = RedirectResponse(url=next_url, status_code=303)
    respons.set_cookie(
        SESSION_COOKIE,
        token,
        max_age=SESSION_MAX_AGE,
        httponly=True,
        samesite="lax",
        secure=settings.is_production,
        path="/",
    )
    return respons


@router.post("/logout")
async def proses_logout(
    request: Request,
    db: Session = Depends(get_db),
    user: AdminUser = Depends(require_login),
):
    form = await request.form()
    assert_csrf(request, _csrf_form(form))
    catat(db, aksi="logout", entitas="admin_user", entitas_id=user.id, aktor=user,
          ip=client_ip(request))
    db.commit()
    respons = RedirectResponse(url="/admin/login", status_code=303)
    respons.delete_cookie(SESSION_COOKIE, path="/")
    respons.delete_cookie(CSRF_COOKIE, path="/")
    return respons


# --------------------------------------------------------------------------- #
# Ringkasan
# --------------------------------------------------------------------------- #
@router.get("", response_class=HTMLResponse)
@router.get("/", response_class=HTMLResponse)
def dashboard(request: Request, db: Session = Depends(get_db), user: AdminUser = Depends(require_login)):
    hitung_status = {
        status: jumlah
        for status, jumlah in db.execute(
            select(Application.status, func.count(Application.id)).group_by(Application.status)
        ).all()
    }
    total = sum(hitung_status.values())
    menunggu = hitung_status.get(C.Status.MENUNGGU_VERIFIKASI.value, 0)
    diproses = hitung_status.get(C.Status.DIPROSES.value, 0)
    terbit = hitung_status.get(C.Status.TERBIT.value, 0)

    batas = datetime.now(timezone.utc) - timedelta(days=30)
    masuk_30 = db.execute(
        select(func.count(Application.id)).where(Application.submitted_at >= batas)
    ).scalar_one()

    terbaru = db.execute(
        select(Application)
        .options(selectinload(Application.service), selectinload(Application.citizen))
        .order_by(Application.created_at.desc())
        .limit(8)
    ).scalars().all()

    antrean = db.execute(
        select(Application)
        .options(selectinload(Application.service), selectinload(Application.citizen))
        .where(Application.status == C.Status.MENUNGGU_VERIFIKASI.value)
        .order_by(Application.submitted_at.asc())
        .limit(6)
    ).scalars().all()

    model = db.execute(select(NlpModel).where(NlpModel.aktif.is_(True))).scalar_one_or_none()
    rating = db.execute(select(func.avg(FeedbackResponse.rating))).scalar()
    gagal = db.execute(
        select(func.count(ChatMessage.id)).where(
            ChatMessage.arah == "in",
            or_(
                ChatMessage.intent_kode.is_(None),
                ChatMessage.intent_kode == "LAINNYA",
                ChatMessage.confidence < C.CONFIDENCE_RENDAH,
            ),
        )
    ).scalar_one()
    scans = db.execute(
        select(func.count(VerificationScan.id)).where(
            VerificationScan.created_at >= batas, VerificationScan.hasil == "VALID"
        )
    ).scalar_one()

    return render(
        request,
        "admin/dashboard.html",
        {
            "nav": _opsi_nav(user),
            "aktif": "/admin",
            "judul": "Ringkasan",
            "hitung_status": hitung_status,
            "total": total,
            "menunggu": menunggu,
            "diproses": diproses,
            "terbit": terbit,
            "masuk_30": masuk_30,
            "terbaru": terbaru,
            "antrean": antrean,
            "model": model,
            "rating": float(rating) if rating else None,
            "gagal": gagal,
            "scans": scans,
            "sekarang": datetime.now(timezone.utc),
        },
    )


# --------------------------------------------------------------------------- #
# Pengajuan
# --------------------------------------------------------------------------- #
@router.get("/pengajuan", response_class=HTMLResponse)
def daftar_pengajuan(
    request: Request,
    db: Session = Depends(get_db),
    user: AdminUser = Depends(require_login),
    status: str = Query(default=""),
    layanan: str = Query(default=""),
    q: str = Query(default=""),
    page: int = Query(default=1, ge=1),
):
    _izin(user, "application.read")

    stmt = select(Application).options(
        selectinload(Application.service), selectinload(Application.citizen)
    )
    if status:
        stmt = stmt.where(Application.status == status)
    if layanan:
        stmt = stmt.join(Service, Application.service_id == Service.id).where(Service.kode == layanan)
    if q:
        pola = f"%{q.strip()}%"
        stmt = stmt.outerjoin(Citizen, Application.citizen_id == Citizen.id).where(
            or_(
                Application.ticket_no.ilike(pola),
                Citizen.nama_lengkap.ilike(pola),
                Citizen.nik.like(pola),
            )
        )

    total = db.execute(select(func.count()).select_from(stmt.subquery())).scalar_one()
    info = _halaman(total, page)
    baris = db.execute(
        stmt.order_by(Application.created_at.desc())
        .offset((info["page"] - 1) * info["per"])
        .limit(info["per"])
    ).scalars().all()

    daftar_layanan = db.execute(select(Service).order_by(Service.urutan)).scalars().all()

    return render(
        request,
        "admin/applications.html",
        {
            "nav": _opsi_nav(user),
            "aktif": "/admin/pengajuan",
            "judul": "Pengajuan",
            "baris": baris,
            "info": info,
            "filter": {"status": status, "layanan": layanan, "q": q},
            "daftar_layanan": daftar_layanan,
            "status_semua": [s.value for s in C.Status],
        },
    )


def _ambil_pengajuan(db: Session, app_id: int, *, kunci: bool = False) -> Application:
    """Ambil pengajuan beserta relasinya.

    `kunci=True` memakai `SELECT ... FOR UPDATE` pada baris pengajuan sehingga
    dua permintaan penerbitan untuk surat yang sama diserialkan di PostgreSQL;
    tanpa itu keduanya lolos pemeriksaan status dan membuat dua dokumen.
    """
    stmt = (
        select(Application)
        .options(
            selectinload(Application.service).selectinload(Service.fields),
            selectinload(Application.citizen),
            selectinload(Application.events),
            selectinload(Application.documents),
            selectinload(Application.attachments),
        )
        .where(Application.id == app_id)
    )
    if kunci:
        stmt = stmt.with_for_update()
    app = db.execute(stmt).scalar_one_or_none()
    if app is None:
        raise HTTPException(status_code=404, detail="Pengajuan tidak ditemukan.")
    return app


@router.get("/pengajuan/{app_id}", response_class=HTMLResponse)
def detail_pengajuan(
    app_id: int,
    request: Request,
    db: Session = Depends(get_db),
    user: AdminUser = Depends(require_login),
):
    _izin(user, "application.read")
    app = _ambil_pengajuan(db, app_id)

    label = {f.nama_field: f for f in app.service.fields}
    data = dict(app.form_data or {})
    urutan = [f.nama_field for f in app.service.fields]
    sisa = [k for k in data if k not in urutan]
    baris = [
        {
            "nama": kunci,
            "label": label[kunci].label if kunci in label else kunci.replace("_", " ").title(),
            "nilai": data.get(kunci),
            "tipe": label[kunci].tipe if kunci in label else "text",
        }
        for kunci in urutan + sisa
        if data.get(kunci) not in (None, "")
    ]

    tujuan = [
        s.value
        for s in C.Status
        if s is not C.Status.TERBIT  # TERBIT lewat tombol "Terbitkan & buat PDF"
        and (C.Status(app.status), s) in C.TRANSISI
        and C.Role(user.role) in C.TRANSISI[(C.Status(app.status), s)]
    ]
    dokumen = app.documents[-1] if app.documents else None
    template = docsvc.template_aktif(db, app.service_id)

    return render(
        request,
        "admin/application_detail.html",
        {
            "nav": _opsi_nav(user),
            "aktif": "/admin/pengajuan",
            "judul": app.ticket_no,
            "app": app,
            "baris": baris,
            "tujuan": tujuan,
            "dokumen": dokumen,
            "template": template,
            "unduh": sign_download(dokumen.id) if dokumen and dokumen.status == "TERBIT" else None,
            "nomor_berikut": peek_letter_number(db),
            "boleh_terbitkan": C.boleh(user.role, "application.approve"),
            "boleh_cabut": C.boleh(user.role, "application.revoke"),
            "boleh_ubah_lampiran": C.boleh(user.role, "application.review"),
        },
    )


@router.post("/pengajuan/{app_id}/status")
async def ubah_status(
    app_id: int,
    request: Request,
    db: Session = Depends(get_db),
    user: AdminUser = Depends(require_login),
):
    _izin(user, "application.review")
    form = await request.form()
    assert_csrf(request, _csrf_form(form))

    app = _ambil_pengajuan(db, app_id)
    ke = _bersih(form.get("ke")).upper()
    catatan = _bersih(form.get("catatan")) or None
    if not ke:
        return _kembali(f"/admin/pengajuan/{app_id}", "Status tujuan belum dipilih.", "err")

    # TERBIT hanya boleh lewat tombol "Terbitkan & buat PDF": di situ nomor surat
    # dipakai, PDF dibuat, dan tautan unduh dikirim ke warga. Mengubah status ke
    # TERBIT lewat form ini akan menghasilkan surat tanpa dokumen.
    if ke == C.Status.TERBIT.value:
        return _kembali(
            f"/admin/pengajuan/{app_id}",
            "Status Terbit hanya dapat dicapai lewat tombol “Terbitkan & buat PDF” "
            "agar nomor surat dan berkas PDF ikut dibuat.",
            "err",
        )

    try:
        appsvc.transisi(db, app, ke, aktor=user, catatan=catatan)
    except appsvc.KesalahanPengajuan as exc:
        db.rollback()
        return _kembali(f"/admin/pengajuan/{app_id}", str(exc), "err")

    catat(
        db,
        aksi="application.status",
        entitas="application",
        entitas_id=app.id,
        aktor=user,
        detail={"ke": ke, "catatan": catatan},
        ip=client_ip(request),
    )
    db.commit()

    if ke in {C.Status.DIPROSES.value, C.Status.DITOLAK.value, C.Status.DIBATALKAN.value}:
        from app.services.notifications import TEMPLATE, beri_tahu_warga

        kunci = {
            C.Status.DIPROSES.value: "diproses",
            C.Status.DITOLAK.value: "ditolak",
            C.Status.DIBATALKAN.value: "dibatalkan",
        }[ke]
        pesan = TEMPLATE[kunci].format(
            nama=app.citizen.nama_lengkap if app.citizen else "Bapak/Ibu",
            layanan=app.service.nama,
            tiket=app.ticket_no,
            alasan=catatan or "-",
        )
        kontak = app.citizen.no_hp if app.citizen else None
        # Panggilan HTTP keluar (timeout 10 dtk) tidak boleh menahan event loop.
        await run_in_threadpool(beri_tahu_warga, app.channel, kontak, pesan)

    return _kembali(f"/admin/pengajuan/{app_id}", f"Status diubah ke {ke}.")


@router.post("/pengajuan/{app_id}/terbitkan")
async def terbitkan(
    app_id: int,
    request: Request,
    db: Session = Depends(get_db),
    user: AdminUser = Depends(require_login),
):
    _izin(user, "application.approve")
    form = await request.form()
    assert_csrf(request, _csrf_form(form))

    app = _ambil_pengajuan(db, app_id, kunci=True)
    if app.status != C.Status.DIPROSES.value:
        return _kembali(
            f"/admin/pengajuan/{app_id}",
            "Surat hanya dapat diterbitkan dari status DIPROSES.",
            "err",
        )
    if app.documents:
        # Penjaga kedua setelah kunci baris: indeks unik `uq_document_application`
        # tetap berlaku bila kunci diabaikan (SQLite).
        return _kembali(
            f"/admin/pengajuan/{app_id}",
            "Pengajuan ini sudah punya surat terbit.",
            "err",
        )
    template = docsvc.template_aktif(db, app.service_id)
    if template is None:
        return _kembali(
            f"/admin/pengajuan/{app_id}",
            "Layanan ini belum punya template aktif. Unggah template lebih dulu.",
            "err",
        )

    # FR-30/FR-41: surat tidak boleh terbit tanpa pejabat yang sah.
    penanda_tangan, _saksi = docsvc.pejabat_untuk(db, app.service.kode)
    if penanda_tangan is None:
        return _kembali(
            f"/admin/pengajuan/{app_id}",
            "Tidak ada pejabat penanda tangan yang aktif dan masih berlaku. "
            "Lengkapi data pejabat lebih dulu.",
            "err",
        )
    if penanda_tangan.jabatan not in docsvc.JABATAN_PENANDATANGAN:
        return _kembali(
            f"/admin/pengajuan/{app_id}",
            f"Penanda tangan surat {app.service.kode} harus Kepala Desa atau Sekretaris Desa, "
            f"bukan {penanda_tangan.jabatan}. Perbaiki di menu Pengaturan.",
            "err",
        )

    nomor = next_letter_number(db)
    token = docsvc.token_baru()
    try:
        # Render ReportLab + tulis berkas adalah kerja CPU/disk: jalankan di
        # threadpool. Sesi SQLAlchemy tetap dipakai dari thread ini saja karena
        # `simpan_dokumen` hanya menyentuh objek yang sudah dimuat.
        dokumen = await run_in_threadpool(
            docsvc.simpan_dokumen,
            db,
            app,
            template=template,
            nomor_surat=nomor,
            qr_token=token,
            aktor_id=user.id,
        )
        appsvc.transisi(
            db, app, C.Status.TERBIT.value, aktor=user, catatan=f"Surat diterbitkan: {nomor}."
        )
    except Exception as exc:  # noqa: BLE001 — tampilkan penyebab ke operator
        db.rollback()
        return _kembali(f"/admin/pengajuan/{app_id}", f"Gagal menerbitkan surat: {exc}", "err")

    catat(
        db,
        aksi="document.issue",
        entitas="document",
        entitas_id=dokumen.id,
        aktor=user,
        detail={"nomor_surat": nomor, "application_id": app.id},
        ip=client_ip(request),
    )
    db.commit()

    from app.services.notifications import TEMPLATE, kirim_dokumen

    tautan = f"{settings.app_url.rstrip('/')}/d/{sign_download(dokumen.id)}"
    pesan = TEMPLATE["terbit"].format(
        nama=app.citizen.nama_lengkap if app.citizen else "Bapak/Ibu",
        layanan=app.service.nama,
        nomor=nomor,
        unduh=tautan,
    )

    # FR-20: kirim PDF ke percakapan warga. Kegagalan kanal tidak boleh
    # menggagalkan penerbitan — tautan bertoken tetap disimpan di chat.
    try:
        berkas: bytes | None = (settings.storage_path / dokumen.file_path).read_bytes()
    except OSError as exc:  # pragma: no cover — berkas hilang di disk
        log.warning("Berkas surat %s tidak terbaca: %s", dokumen.file_path, exc)
        berkas = None

    hasil = await run_in_threadpool(
        kirim_dokumen,
        app.channel,
        app.citizen.no_hp if app.citizen else None,
        berkas=berkas,
        nama_berkas=f"{nomor.replace('/', '-')}.pdf",
        tautan=tautan,
        keterangan=pesan,
    )

    masuk_chat = chatsvc.kirim_pesan_keluar(db, app.id, pesan)
    if masuk_chat or hasil.terkirim:
        dokumen.sent_at = datetime.now(timezone.utc)
    db.commit()

    return _kembali(f"/admin/pengajuan/{app_id}", f"Surat {nomor} diterbitkan.")


@router.get("/pengajuan/{app_id}/pratinjau")
def pratinjau_pdf(
    app_id: int,
    db: Session = Depends(get_db),
    user: AdminUser = Depends(require_login),
):
    _izin(user, "application.read")
    app = _ambil_pengajuan(db, app_id)
    template = docsvc.template_aktif(db, app.service_id)
    if template is None:
        raise HTTPException(status_code=409, detail="Template aktif belum tersedia untuk layanan ini.")
    try:
        isi = docsvc.buat_dokumen_draf(db, app, template)
    except (KeyError, ValueError, IndexError) as exc:
        raise HTTPException(
            status_code=422, detail=f"Template tidak dapat dirender: {exc}"
        ) from exc
    return Response(
        content=isi,
        media_type="application/pdf",
        headers={
            "Content-Disposition": f'inline; filename="pratinjau-{app.ticket_no}.pdf"',
            "Cache-Control": "private, no-store",
        },
    )


@router.post("/pengajuan/{app_id}/cabut")
async def cabut_surat(
    app_id: int,
    request: Request,
    db: Session = Depends(get_db),
    user: AdminUser = Depends(require_login),
):
    _izin(user, "application.revoke")
    form = await request.form()
    assert_csrf(request, _csrf_form(form))

    app = _ambil_pengajuan(db, app_id)
    alasan = _bersih(form.get("alasan"))
    if not alasan:
        return _kembali(f"/admin/pengajuan/{app_id}", "Alasan pencabutan wajib diisi.", "err")
    if not app.documents:
        return _kembali(f"/admin/pengajuan/{app_id}", "Pengajuan ini belum punya surat terbit.", "err")

    dokumen = app.documents[-1]
    verif.cabut_dokumen(db, dokumen, alasan)
    catat(
        db,
        aksi="document.revoke",
        entitas="document",
        entitas_id=dokumen.id,
        aktor=user,
        detail={"nomor_surat": dokumen.nomor_surat, "alasan": alasan},
        ip=client_ip(request),
    )
    db.commit()
    return _kembali(f"/admin/pengajuan/{app_id}", f"Surat {dokumen.nomor_surat} dicabut.")

# --------------------------------------------------------------------------- #
# Lampiran pengajuan
# --------------------------------------------------------------------------- #
@router.post("/pengajuan/{app_id}/lampiran")
async def unggah_lampiran(
    app_id: int,
    request: Request,
    csrf: str = Form(""),
    berkas: UploadFile = File(...),
    db: Session = Depends(get_db),
    user: AdminUser = Depends(require_login),
):
    """Petugas mengarsipkan berkas pendukung (KTP, KK, foto lokasi usaha)."""
    _izin(user, "application.review")
    assert_csrf(request, csrf)
    app = _ambil_pengajuan(db, app_id)

    isi = await berkas.read()
    try:
        sah = attachments.periksa(berkas.filename or "", isi)
    except attachments.LampiranTidakSah as exc:
        return _kembali(f"/admin/pengajuan/{app_id}", str(exc), "err")

    lampiran = attachments.simpan(app.id, sah, berkas.filename or "")
    db.add(lampiran)
    db.flush()
    catat(
        db,
        aksi="attachment.upload",
        entitas="attachment",
        entitas_id=lampiran.id,
        aktor=user,
        detail={
            "application_id": app.id,
            "nama_file": lampiran.nama_file,
            "ukuran": lampiran.ukuran,
            "sha256": lampiran.sha256,
        },
        ip=client_ip(request),
    )
    db.commit()
    return _kembali(f"/admin/pengajuan/{app_id}", f"Lampiran {lampiran.nama_file} diunggah.")


@router.get("/pengajuan/{app_id}/lampiran/{aid}")
def unduh_lampiran(
    app_id: int,
    aid: int,
    db: Session = Depends(get_db),
    user: AdminUser = Depends(require_login),
):
    _izin(user, "application.read")
    lampiran = db.get(Attachment, aid)
    if lampiran is None or lampiran.application_id != app_id:
        raise HTTPException(status_code=404, detail="Lampiran tidak ditemukan.")

    path = attachments.path_berkas(lampiran)
    if not path.is_file():
        raise HTTPException(status_code=410, detail="Berkas lampiran tidak ada di penyimpanan.")
    return FileResponse(
        path,
        media_type=lampiran.mime,
        filename=lampiran.nama_file,
        headers={"Cache-Control": "private, no-store"},
    )


@router.post("/pengajuan/{app_id}/lampiran/{aid}/hapus")
async def hapus_lampiran(
    app_id: int,
    aid: int,
    request: Request,
    db: Session = Depends(get_db),
    user: AdminUser = Depends(require_login),
):
    _izin(user, "application.review")
    form = await request.form()
    assert_csrf(request, _csrf_form(form))

    lampiran = db.get(Attachment, aid)
    if lampiran is None or lampiran.application_id != app_id:
        raise HTTPException(status_code=404, detail="Lampiran tidak ditemukan.")

    nama = lampiran.nama_file
    attachments.hapus_berkas(lampiran)
    db.delete(lampiran)
    catat(
        db,
        aksi="attachment.delete",
        entitas="attachment",
        entitas_id=aid,
        aktor=user,
        detail={"application_id": app_id, "nama_file": nama},
        ip=client_ip(request),
    )
    db.commit()
    return _kembali(f"/admin/pengajuan/{app_id}", f"Lampiran {nama} dihapus.")


# --------------------------------------------------------------------------- #
# Layanan & field
# --------------------------------------------------------------------------- #
@router.get("/layanan", response_class=HTMLResponse)
def daftar_layanan(
    request: Request, db: Session = Depends(get_db), user: AdminUser = Depends(require_login)
):
    _izin(user, "service.manage")
    rows = db.execute(
        select(Service).options(selectinload(Service.fields)).order_by(Service.urutan)
    ).scalars().all()
    return render(
        request,
        "admin/layanan.html",
        {"nav": _opsi_nav(user), "aktif": "/admin/layanan", "judul": "Layanan", "rows": rows},
    )


@router.get("/layanan/{kode}", response_class=HTMLResponse)
def edit_layanan(
    kode: str,
    request: Request,
    db: Session = Depends(get_db),
    user: AdminUser = Depends(require_login),
):
    _izin(user, "service.manage")
    service = db.execute(
        select(Service).options(selectinload(Service.fields)).where(Service.kode == kode.upper())
    ).scalar_one_or_none()
    if service is None:
        raise HTTPException(status_code=404, detail="Layanan tidak ditemukan.")
    return render(
        request,
        "admin/layanan_edit.html",
        {
            "nav": _opsi_nav(user),
            "aktif": "/admin/layanan",
            "judul": f"Layanan {service.kode}",
            "service": service,
            "fields": sorted(service.fields, key=lambda f: f.urutan),
        },
    )


@router.post("/layanan/{kode}")
async def simpan_layanan(
    kode: str,
    request: Request,
    db: Session = Depends(get_db),
    user: AdminUser = Depends(require_login),
):
    _izin(user, "service.manage")
    form = await request.form()
    assert_csrf(request, _csrf_form(form))

    service = db.execute(
        select(Service).options(selectinload(Service.fields)).where(Service.kode == kode.upper())
    ).scalar_one_or_none()
    if service is None:
        raise HTTPException(status_code=404, detail="Layanan tidak ditemukan.")

    service.nama = _bersih(form.get("nama")) or service.nama
    service.deskripsi = _bersih(form.get("deskripsi")) or None
    service.estimasi_hari = max(1, _ke_int(form.get("estimasi_hari"), service.estimasi_hari))
    service.urutan = _ke_int(form.get("urutan"), service.urutan)
    service.aktif = _bersih(form.get("aktif")) in {"1", "on", "true", "ya"}
    syarat = [
        baris.strip()
        for baris in str(form.get("syarat") or "").splitlines()
        if baris.strip()
    ]
    service.syarat = syarat

    for field in service.fields:
        field.label = _bersih(form.get(f"label_{field.id}")) or field.label
        field.wajib = _bersih(form.get(f"wajib_{field.id}")) in {"1", "on", "true", "ya"}
        field.urutan = _ke_int(form.get(f"urutan_{field.id}"), field.urutan)
        field.bantuan = _bersih(form.get(f"bantuan_{field.id}")) or None
        field.placeholder = _bersih(form.get(f"placeholder_{field.id}")) or None
        if field.tipe == "select":
            pilihan = [
                baris.strip()
                for baris in str(form.get(f"pilihan_{field.id}") or "").splitlines()
                if baris.strip()
            ]
            field.pilihan = pilihan or None

    catat(db, aksi="service.update", entitas="service", entitas_id=service.id, aktor=user,
          detail={"kode": service.kode}, ip=client_ip(request))
    db.commit()
    return _kembali(f"/admin/layanan/{service.kode}", "Layanan diperbarui.")


# --------------------------------------------------------------------------- #
# Template surat
# --------------------------------------------------------------------------- #
@router.get("/template", response_class=HTMLResponse)
def daftar_template(
    request: Request, db: Session = Depends(get_db), user: AdminUser = Depends(require_login)
):
    _izin(user, "template.manage")
    rows = db.execute(
        select(LetterTemplate)
        .options(selectinload(LetterTemplate.service))
        .order_by(LetterTemplate.service_id, LetterTemplate.versi.desc())
    ).scalars().all()
    return render(
        request,
        "admin/template.html",
        {"nav": _opsi_nav(user), "aktif": "/admin/template", "judul": "Template surat", "rows": rows},
    )


@router.get("/template/{tid}", response_class=HTMLResponse)
def edit_template(
    tid: int,
    request: Request,
    db: Session = Depends(get_db),
    user: AdminUser = Depends(require_login),
):
    _izin(user, "template.manage")
    row = db.get(LetterTemplate, tid)
    if row is None:
        raise HTTPException(status_code=404, detail="Template tidak ditemukan.")
    contoh = _contoh_placeholder(db, row.service_id)
    return render(
        request,
        "admin/template_edit.html",
        {
            "nav": _opsi_nav(user),
            "aktif": "/admin/template",
            "judul": f"Template {row.service.kode} v{row.versi}",
            "row": row,
            "placeholder": sorted(contoh),
        },
    )


def _contoh_placeholder(db: Session, service_id: int) -> set[str]:
    dasar = {
        "nomor_surat", "nama_lengkap", "nik", "tempat_lahir", "tanggal_lahir",
        "tanggal_lahir_panjang", "jenis_kelamin", "status_perkawinan", "agama",
        "pekerjaan", "alamat", "dusun", "rt", "rw", "no_hp", "alamat_penuh",
        "keperluan", "penghasilan_bulanan", "jumlah_tanggungan", "nama_usaha",
        "jenis_usaha", "alamat_usaha", "bentuk_usaha", "modal_usaha", "tahun_mulai",
        "tujuan_instansi", "pejabat_nama", "pejabat_jabatan", "tanggal_surat",
    }
    service = db.get(Service, service_id)
    if service is not None:
        dasar.update(f.nama_field for f in service.fields)
    return dasar


@router.post("/template/{tid}")
async def simpan_template(
    tid: int,
    request: Request,
    db: Session = Depends(get_db),
    user: AdminUser = Depends(require_login),
):
    _izin(user, "template.manage")
    form = await request.form()
    assert_csrf(request, _csrf_form(form))

    lama = db.get(LetterTemplate, tid)
    if lama is None:
        raise HTTPException(status_code=404, detail="Template tidak ditemukan.")
    konten = str(form.get("konten") or "").strip()
    nama = _bersih(form.get("nama")) or lama.nama
    if not konten:
        return _kembali(f"/admin/template/{tid}", "Isi template tidak boleh kosong.", "err")

    if _bersih(form.get("mode")) == "baru":
        versi = (
            db.execute(
                select(func.max(LetterTemplate.versi)).where(
                    LetterTemplate.service_id == lama.service_id
                )
            ).scalar_one()
            or lama.versi
        ) + 1
        db.execute(
            LetterTemplate.__table__.update()
            .where(LetterTemplate.service_id == lama.service_id)
            .values(aktif=False)
        )
        baru = LetterTemplate(
            service_id=lama.service_id,
            nama=nama,
            versi=versi,
            konten_html=konten,
            aktif=True,
            created_by=user.id,
        )
        db.add(baru)
        db.flush()
        catat(db, aksi="template.create", entitas="letter_template", entitas_id=baru.id, aktor=user,
              detail={"versi": versi, "service_id": lama.service_id}, ip=client_ip(request))
        db.commit()
        return _kembali(f"/admin/template/{baru.id}", f"Versi {versi} dibuat dan diaktifkan.")

    lama.nama = nama
    lama.konten_html = konten
    catat(db, aksi="template.update", entitas="letter_template", entitas_id=lama.id, aktor=user,
          ip=client_ip(request))
    db.commit()
    return _kembali(f"/admin/template/{lama.id}", "Template diperbarui.")


@router.post("/template/{tid}/aktifkan")
async def aktifkan_template(
    tid: int,
    request: Request,
    db: Session = Depends(get_db),
    user: AdminUser = Depends(require_login),
):
    _izin(user, "template.manage")
    form = await request.form()
    assert_csrf(request, _csrf_form(form))
    row = db.get(LetterTemplate, tid)
    if row is None:
        raise HTTPException(status_code=404, detail="Template tidak ditemukan.")
    db.execute(
        LetterTemplate.__table__.update()
        .where(LetterTemplate.service_id == row.service_id)
        .values(aktif=False)
    )
    row.aktif = True
    catat(db, aksi="template.activate", entitas="letter_template", entitas_id=row.id, aktor=user,
          ip=client_ip(request))
    db.commit()
    return _kembali("/admin/template", f"Template v{row.versi} diaktifkan.")


# --------------------------------------------------------------------------- #
# FAQ
# --------------------------------------------------------------------------- #
@router.get("/faq", response_class=HTMLResponse)
def daftar_faq(
    request: Request, db: Session = Depends(get_db), user: AdminUser = Depends(require_login)
):
    _izin(user, "faq.manage")
    rows = db.execute(
        select(Faq).options(selectinload(Faq.intent)).order_by(Faq.urutan, Faq.id)
    ).scalars().all()
    intents = db.execute(select(Intent).order_by(Intent.kode)).scalars().all()
    return render(
        request,
        "admin/faq.html",
        {
            "nav": _opsi_nav(user),
            "aktif": "/admin/faq",
            "judul": "FAQ",
            "rows": rows,
            "intents": intents,
        },
    )


@router.post("/faq")
async def tambah_faq(
    request: Request, db: Session = Depends(get_db), user: AdminUser = Depends(require_login)
):
    _izin(user, "faq.manage")
    form = await request.form()
    assert_csrf(request, _csrf_form(form))

    pertanyaan = _bersih(form.get("pertanyaan"))
    jawaban = _bersih(form.get("jawaban"))
    if not pertanyaan or not jawaban:
        return _kembali("/admin/faq", "Pertanyaan dan jawaban wajib diisi.", "err")

    kata = [k.strip() for k in str(form.get("kata_kunci") or "").split(",") if k.strip()]
    row = Faq(
        intent_id=_ke_int(form.get("intent_id")) or None,
        pertanyaan=pertanyaan,
        jawaban=jawaban,
        kata_kunci=kata,
        aktif=True,
        urutan=_ke_int(form.get("urutan")),
    )
    db.add(row)
    db.flush()
    catat(db, aksi="faq.create", entitas="faq", entitas_id=row.id, aktor=user,
          detail={"pertanyaan": pertanyaan[:80]}, ip=client_ip(request))
    db.commit()
    return _kembali("/admin/faq", "FAQ ditambahkan.")


@router.post("/faq/{fid}")
async def ubah_faq(
    fid: int,
    request: Request,
    db: Session = Depends(get_db),
    user: AdminUser = Depends(require_login),
):
    _izin(user, "faq.manage")
    form = await request.form()
    assert_csrf(request, _csrf_form(form))
    row = db.get(Faq, fid)
    if row is None:
        raise HTTPException(status_code=404, detail="FAQ tidak ditemukan.")

    row.pertanyaan = _bersih(form.get("pertanyaan")) or row.pertanyaan
    row.jawaban = _bersih(form.get("jawaban")) or row.jawaban
    row.intent_id = _ke_int(form.get("intent_id")) or None
    row.urutan = _ke_int(form.get("urutan"), row.urutan)
    row.aktif = _bersih(form.get("aktif")) in {"1", "on", "true", "ya"}
    row.kata_kunci = [
        k.strip() for k in str(form.get("kata_kunci") or "").split(",") if k.strip()
    ]
    catat(db, aksi="faq.update", entitas="faq", entitas_id=row.id, aktor=user,
          ip=client_ip(request))
    db.commit()
    return _kembali("/admin/faq", "FAQ diperbarui.")


@router.post("/faq/{fid}/hapus")
async def hapus_faq(
    fid: int,
    request: Request,
    db: Session = Depends(get_db),
    user: AdminUser = Depends(require_login),
):
    _izin(user, "faq.manage")
    form = await request.form()
    assert_csrf(request, _csrf_form(form))
    row = db.get(Faq, fid)
    if row is None:
        raise HTTPException(status_code=404, detail="FAQ tidak ditemukan.")
    row.aktif = False
    catat(db, aksi="faq.deactivate", entitas="faq", entitas_id=row.id, aktor=user,
          ip=client_ip(request))
    db.commit()
    return _kembali("/admin/faq", "FAQ dinonaktifkan (riwayat chat tetap utuh).")


# --------------------------------------------------------------------------- #
# Data warga
# --------------------------------------------------------------------------- #
def _opsi_field(db: Session, nama_field: str) -> list[str]:
    """Pilihan select yang dipakai layanan, untuk form data warga."""
    field = db.execute(
        select(ServiceField).where(ServiceField.nama_field == nama_field)
    ).scalars().first()
    return list(field.pilihan or []) if field else []


def _baca_warga(form) -> tuple[dict[str, Any], str | None]:
    """Validasi form data warga; kembalikan (data, pesan_error)."""
    nik = "".join(ch for ch in _bersih(form.get("nik")) if ch.isdigit())
    if len(nik) != 16:
        return {}, "NIK harus 16 digit angka."

    nama = _bersih(form.get("nama_lengkap"))
    if not nama:
        return {}, "Nama lengkap wajib diisi."

    jk = _bersih(form.get("jenis_kelamin")) or None
    if jk is not None and jk not in {"Laki-Laki", "Perempuan"}:
        return {}, "Jenis kelamin harus Laki-Laki atau Perempuan."

    try:
        tanggal_lahir = _ke_tanggal(form.get("tanggal_lahir"))
    except ValueError:
        return {}, "Tanggal lahir harus berformat YYYY-MM-DD."

    data = {
        "nik": nik,
        "nama_lengkap": nama,
        "jenis_kelamin": jk,
        "tempat_lahir": _bersih(form.get("tempat_lahir")) or None,
        "tanggal_lahir": tanggal_lahir,
        "agama": _bersih(form.get("agama")) or None,
        "status_perkawinan": _bersih(form.get("status_perkawinan")) or None,
        "pekerjaan": _bersih(form.get("pekerjaan")) or None,
        "alamat": _bersih(form.get("alamat")) or None,
        "dusun": _bersih(form.get("dusun")) or None,
        "rt": _bersih(form.get("rt")) or None,
        "rw": _bersih(form.get("rw")) or None,
        "no_hp": _bersih(form.get("no_hp")) or None,
        "email": _bersih(form.get("email")) or None,
    }
    return data, None


@router.get("/warga", response_class=HTMLResponse)
def daftar_warga(
    request: Request,
    db: Session = Depends(get_db),
    user: AdminUser = Depends(require_login),
    q: str = Query(default=""),
    status: str = Query(default=""),
    page: int = Query(default=1, ge=1),
):
    _izin(user, "citizen.read")

    stmt = select(Citizen)
    if q:
        pola = f"%{q.strip()}%"
        stmt = stmt.where(
            or_(
                Citizen.nik.like(pola),
                Citizen.nama_lengkap.ilike(pola),
                Citizen.dusun.ilike(pola),
            )
        )
    if status == "aktif":
        stmt = stmt.where(Citizen.aktif.is_(True))
    elif status == "nonaktif":
        stmt = stmt.where(Citizen.aktif.is_(False))

    total = db.execute(select(func.count()).select_from(stmt.subquery())).scalar_one()
    info = _halaman(total, page)
    rows = db.execute(
        stmt.order_by(Citizen.nama_lengkap)
        .offset((info["page"] - 1) * info["per"])
        .limit(info["per"])
    ).scalars().all()

    jumlah: dict[int, int] = {}
    if rows:
        hasil = db.execute(
            select(Application.citizen_id, func.count(Application.id))
            .where(Application.citizen_id.in_([r.id for r in rows]))
            .group_by(Application.citizen_id)
        ).all()
        jumlah = {cid: n for cid, n in hasil}

    return render(
        request,
        "admin/warga.html",
        {
            "nav": _opsi_nav(user),
            "aktif": "/admin/warga",
            "judul": "Data warga",
            "baris": rows,
            "info": info,
            "filter": {"q": q, "status": status},
            "jumlah": jumlah,
            "opsi_jk": ["Laki-Laki", "Perempuan"],
            "opsi_agama": _opsi_field(db, "agama"),
            "opsi_status": _opsi_field(db, "status_perkawinan"),
            "opsi_dusun": _opsi_field(db, "dusun"),
            "boleh_ubah": C.boleh(user.role, "citizen.manage"),
        },
    )


def _ambil_warga(db: Session, warga_id: int) -> Citizen:
    warga = db.get(Citizen, warga_id)
    if warga is None:
        raise HTTPException(status_code=404, detail="Data warga tidak ditemukan.")
    return warga


@router.get("/warga/{warga_id}", response_class=HTMLResponse)
def detail_warga(
    warga_id: int,
    request: Request,
    db: Session = Depends(get_db),
    user: AdminUser = Depends(require_login),
):
    _izin(user, "citizen.read")
    warga = _ambil_warga(db, warga_id)
    riwayat = db.execute(
        select(Application)
        .options(selectinload(Application.service))
        .where(Application.citizen_id == warga.id)
        .order_by(Application.created_at.desc())
    ).scalars().all()

    return render(
        request,
        "admin/warga_detail.html",
        {
            "nav": _opsi_nav(user),
            "aktif": "/admin/warga",
            "judul": warga.nama_lengkap,
            "warga": warga,
            "riwayat": riwayat,
            "opsi_jk": ["Laki-Laki", "Perempuan"],
            "opsi_agama": _opsi_field(db, "agama"),
            "opsi_status": _opsi_field(db, "status_perkawinan"),
            "opsi_dusun": _opsi_field(db, "dusun"),
            "boleh_ubah": C.boleh(user.role, "citizen.manage"),
        },
    )


@router.post("/warga")
async def tambah_warga(
    request: Request, db: Session = Depends(get_db), user: AdminUser = Depends(require_login)
):
    _izin(user, "citizen.manage")
    form = await request.form()
    assert_csrf(request, _csrf_form(form))

    data, error = _baca_warga(form)
    if error:
        return _kembali("/admin/warga", error, "err")
    if appsvc.cari_citizen(db, data["nik"]) is not None:
        return _kembali("/admin/warga", "NIK tersebut sudah terdaftar.", "err")

    row = Citizen(**data)
    db.add(row)
    db.flush()
    catat(
        db, aksi="citizen.create", entitas="citizen", entitas_id=row.id, aktor=user,
        detail={"nik": row.nik}, ip=client_ip(request),
    )
    db.commit()
    return _kembali("/admin/warga", f"Data warga {row.nama_lengkap} ditambahkan.")


@router.post("/warga/{warga_id}")
async def ubah_warga(
    warga_id: int,
    request: Request,
    db: Session = Depends(get_db),
    user: AdminUser = Depends(require_login),
):
    _izin(user, "citizen.manage")
    form = await request.form()
    assert_csrf(request, _csrf_form(form))
    row = _ambil_warga(db, warga_id)

    data, error = _baca_warga(form)
    if error:
        return _kembali(f"/admin/warga/{warga_id}", error, "err")

    lain = appsvc.cari_citizen(db, data["nik"])
    if lain is not None and lain.id != row.id:
        return _kembali(f"/admin/warga/{warga_id}", "NIK tersebut sudah dipakai warga lain.", "err")

    for nama, nilai in data.items():
        setattr(row, nama, nilai)
    catat(
        db, aksi="citizen.update", entitas="citizen", entitas_id=row.id, aktor=user,
        detail={"nik": row.nik}, ip=client_ip(request),
    )
    db.commit()
    return _kembali(f"/admin/warga/{warga_id}", "Data warga diperbarui.")


@router.post("/warga/{warga_id}/aktif")
async def aktif_warga(
    warga_id: int,
    request: Request,
    db: Session = Depends(get_db),
    user: AdminUser = Depends(require_login),
):
    _izin(user, "citizen.manage")
    form = await request.form()
    assert_csrf(request, _csrf_form(form))
    row = _ambil_warga(db, warga_id)

    row.aktif = not row.aktif
    catat(
        db, aksi="citizen.toggle", entitas="citizen", entitas_id=row.id, aktor=user,
        detail={"nik": row.nik, "aktif": row.aktif}, ip=client_ip(request),
    )
    db.commit()
    pesan = f"{row.nama_lengkap} {'diaktifkan kembali' if row.aktif else 'dinonaktifkan'}."
    return _kembali(f"/admin/warga/{warga_id}", pesan)


@router.post("/warga/{warga_id}/hapus")
async def hapus_warga(
    warga_id: int,
    request: Request,
    db: Session = Depends(get_db),
    user: AdminUser = Depends(require_login),
):
    _izin(user, "citizen.manage")
    form = await request.form()
    assert_csrf(request, _csrf_form(form))
    row = _ambil_warga(db, warga_id)

    jumlah = db.execute(
        select(func.count(Application.id)).where(Application.citizen_id == row.id)
    ).scalar_one()
    if jumlah:
        return _kembali(
            f"/admin/warga/{warga_id}",
            f"Warga ini punya {jumlah} riwayat pengajuan. Nonaktifkan saja agar riwayat tetap utuh.",
            "err",
        )

    nama = row.nama_lengkap
    nik = row.nik
    db.delete(row)
    catat(
        db, aksi="citizen.delete", entitas="citizen", entitas_id=warga_id, aktor=user,
        detail={"nik": nik}, ip=client_ip(request),
    )
    db.commit()
    return _kembali("/admin/warga", f"Data warga {nama} dihapus.")


# --------------------------------------------------------------------------- #
# Pejabat
# --------------------------------------------------------------------------- #
@router.get("/pejabat", response_class=HTMLResponse)
def daftar_pejabat(
    request: Request, db: Session = Depends(get_db), user: AdminUser = Depends(require_login)
):
    _izin(user, "official.manage")
    rows = db.execute(select(Official).order_by(Official.urutan, Official.id)).scalars().all()
    return render(
        request,
        "admin/pejabat.html",
        {
            "nav": _opsi_nav(user),
            "aktif": "/admin/pejabat",
            "judul": "Pejabat",
            "rows": rows,
            "hari_ini": date.today(),
        },
    )


@router.post("/pejabat")
async def tambah_pejabat(
    request: Request, db: Session = Depends(get_db), user: AdminUser = Depends(require_login)
):
    _izin(user, "official.manage")
    form = await request.form()
    assert_csrf(request, _csrf_form(form))

    nama = _bersih(form.get("nama"))
    jabatan = _bersih(form.get("jabatan"))
    if not nama or not jabatan:
        return _kembali("/admin/pejabat", "Nama dan jabatan wajib diisi.", "err")

    ada = db.execute(
        select(Official).where(Official.jabatan == jabatan, Official.aktif.is_(True))
    ).scalar_one_or_none()
    if ada is not None:
        if ada.berlaku_sampai and ada.berlaku_sampai < date.today():
            # Masa berlaku habis: lepas jabatan otomatis agar penggantinya bisa masuk.
            ada.aktif = False
            catat(
                db,
                aksi="official.expire",
                entitas="official",
                entitas_id=ada.id,
                aktor=user,
                detail={"jabatan": jabatan, "berlaku_sampai": ada.berlaku_sampai.isoformat()},
                ip=client_ip(request),
            )
            db.flush()
        else:
            return _kembali(
                "/admin/pejabat",
                f"Jabatan '{jabatan}' sudah dipegang {ada.nama}. Nonaktifkan dulu.",
                "err",
            )

    try:
        berlaku = _ke_tanggal(form.get("berlaku_sampai"))
    except ValueError:
        return _kembali("/admin/pejabat", "Format masa berlaku harus YYYY-MM-DD.", "err")

    row = Official(
        nama=nama,
        jabatan=jabatan,
        nip=_bersih(form.get("nip")) or None,
        pangkat=_bersih(form.get("pangkat")) or None,
        berlaku_sampai=berlaku,
        aktif=True,
        urutan=_ke_int(form.get("urutan")),
    )
    db.add(row)
    db.flush()
    catat(db, aksi="official.create", entitas="official", entitas_id=row.id, aktor=user,
          detail={"jabatan": jabatan}, ip=client_ip(request))
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        return _kembali(
            "/admin/pejabat",
            f"Jabatan '{jabatan}' sudah dipegang pejabat aktif lain. Muat ulang halaman.",
            "err",
        )
    return _kembali("/admin/pejabat", "Pejabat ditambahkan.")


@router.post("/pejabat/{oid}")
async def ubah_pejabat(
    oid: int,
    request: Request,
    db: Session = Depends(get_db),
    user: AdminUser = Depends(require_login),
):
    _izin(user, "official.manage")
    form = await request.form()
    assert_csrf(request, _csrf_form(form))
    row = db.get(Official, oid)
    if row is None:
        raise HTTPException(status_code=404, detail="Pejabat tidak ditemukan.")

    # Pemisahan tugas: data penanda tangan tertinggi hanya boleh diubah oleh
    # Kepala Desa sendiri. Sekdes dan admin teknis mengelola jabatan lain.
    if row.jabatan == JABATAN_KEPALA_DESA and user.role != C.Role.KEPALA_DESA.value:
        raise HTTPException(
            status_code=403,
            detail="Data pejabat Kepala Desa hanya dapat diubah oleh akun Kepala Desa.",
        )

    row.nama = _bersih(form.get("nama")) or row.nama
    row.nip = _bersih(form.get("nip")) or None
    row.pangkat = _bersih(form.get("pangkat")) or None
    try:
        row.berlaku_sampai = _ke_tanggal(form.get("berlaku_sampai"))
    except ValueError:
        return _kembali("/admin/pejabat", "Format masa berlaku harus YYYY-MM-DD.", "err")
    row.urutan = _ke_int(form.get("urutan"), row.urutan)
    catat(db, aksi="official.update", entitas="official", entitas_id=row.id, aktor=user,
          ip=client_ip(request))
    db.commit()
    return _kembali("/admin/pejabat", "Data pejabat diperbarui.")


@router.post("/pejabat/{oid}/ttd")
async def unggah_ttd(
    oid: int,
    request: Request,
    csrf: str = Form(""),
    berkas: UploadFile = File(...),
    db: Session = Depends(get_db),
    user: AdminUser = Depends(require_login),
):
    """Unggah scan tanda tangan (FR-30/FR-41): PNG/JPG, maksimal 2 MB.

    Pemisahan tugas: materi tanda tangan adalah kewenangan pejabat desa, bukan
    admin teknis. Hanya Kepala Desa dan Sekretaris Desa yang boleh mengunggah
    atau menghapusnya.
    """
    _izin(user, "official.manage")
    if user.role not in ROLE_PEMEGANG_TTD:
        raise HTTPException(
            status_code=403,
            detail="Hanya Kepala Desa atau Sekretaris Desa yang boleh mengunggah tanda tangan.",
        )
    assert_csrf(request, csrf)

    row = db.get(Official, oid)
    if row is None:
        raise HTTPException(status_code=404, detail="Pejabat tidak ditemukan.")

    isi = await berkas.read()
    if not isi:
        return _kembali("/admin/pejabat", "Berkas tanda tangan kosong.", "err")
    if len(isi) > TTD_MAKS_BYTE:
        return _kembali(
            "/admin/pejabat",
            f"Berkas tanda tangan {len(isi) / 1024 / 1024:.1f} MB melebihi batas 2 MB.",
            "err",
        )

    try:
        gambar = PilImage.open(io.BytesIO(isi))
        gambar.verify()
        gambar = PilImage.open(io.BytesIO(isi))
    except Exception:  # noqa: BLE001 — Pillow melempar beragam tipe untuk berkas rusak
        return _kembali("/admin/pejabat", "Berkas bukan gambar PNG/JPG yang valid.", "err")

    if gambar.format not in {"PNG", "JPEG"}:
        return _kembali("/admin/pejabat", "Format tanda tangan harus PNG atau JPG.", "err")

    tujuan = settings.storage_path / "officials" / f"ttd-{row.id}.png"
    tujuan.parent.mkdir(parents=True, exist_ok=True)
    if gambar.mode not in ("RGB", "RGBA"):
        gambar = gambar.convert("RGBA")
    gambar.save(tujuan, format="PNG")

    row.ttd_path = f"officials/ttd-{row.id}.png"
    catat(db, aksi="official.ttd", entitas="official", entitas_id=row.id, aktor=user,
          detail={"berkas": row.ttd_path, "byte": len(isi)}, ip=client_ip(request))
    db.commit()
    return _kembali("/admin/pejabat", f"Tanda tangan {row.nama} diperbarui.")


@router.post("/pejabat/{oid}/ttd/hapus")
async def hapus_ttd(
    oid: int,
    request: Request,
    db: Session = Depends(get_db),
    user: AdminUser = Depends(require_login),
):
    _izin(user, "official.manage")
    if user.role not in ROLE_PEMEGANG_TTD:
        raise HTTPException(
            status_code=403,
            detail="Hanya Kepala Desa atau Sekretaris Desa yang boleh menghapus tanda tangan.",
        )
    form = await request.form()
    assert_csrf(request, _csrf_form(form))

    row = db.get(Official, oid)
    if row is None:
        raise HTTPException(status_code=404, detail="Pejabat tidak ditemukan.")

    if row.ttd_path:
        path = Path(row.ttd_path)
        if not path.is_absolute():
            path = settings.storage_path / path
        path.unlink(missing_ok=True)
    row.ttd_path = None
    catat(db, aksi="official.ttd_hapus", entitas="official", entitas_id=row.id, aktor=user,
          ip=client_ip(request))
    db.commit()
    return _kembali("/admin/pejabat", f"Tanda tangan {row.nama} dihapus.")


@router.post("/pejabat/{oid}/nonaktif")
async def nonaktif_pejabat(
    oid: int,
    request: Request,
    db: Session = Depends(get_db),
    user: AdminUser = Depends(require_login),
):
    _izin(user, "official.manage")
    form = await request.form()
    assert_csrf(request, _csrf_form(form))
    row = db.get(Official, oid)
    if row is None:
        raise HTTPException(status_code=404, detail="Pejabat tidak ditemukan.")

    if not row.aktif:
        # Mengaktifkan kembali: jabatan hanya boleh dipegang satu pejabat aktif
        # (indeks unik parsial `uq_official_aktif`). Periksa lebih dulu agar
        # pengguna mendapat pesan, bukan halaman galat 500.
        lain = db.execute(
            select(Official).where(
                Official.jabatan == row.jabatan,
                Official.aktif.is_(True),
                Official.id != row.id,
            )
        ).scalar_one_or_none()
        if lain is not None:
            return _kembali(
                "/admin/pejabat",
                f"Jabatan '{row.jabatan}' masih dipegang {lain.nama}. "
                "Nonaktifkan pejabat tersebut lebih dulu.",
                "err",
            )

    row.aktif = not row.aktif
    catat(db, aksi="official.toggle", entitas="official", entitas_id=row.id, aktor=user,
          detail={"aktif": row.aktif}, ip=client_ip(request))
    try:
        db.commit()
    except IntegrityError:
        # Balapan dua tab admin: indeks unik tetap penjaga terakhir.
        db.rollback()
        return _kembali(
            "/admin/pejabat",
            f"Jabatan '{row.jabatan}' sudah dipegang pejabat lain. Muat ulang halaman.",
            "err",
        )
    return _kembali("/admin/pejabat", f"{row.nama} {'diaktifkan' if row.aktif else 'dinonaktifkan'}.")


# --------------------------------------------------------------------------- #
# Nomor surat
# --------------------------------------------------------------------------- #
@router.get("/nomor", response_class=HTMLResponse)
def halaman_nomor(
    request: Request, db: Session = Depends(get_db), user: AdminUser = Depends(require_login)
):
    _izin(user, "number.manage")
    rows = db.execute(
        select(LetterNumberCounter).order_by(
            LetterNumberCounter.tahun.desc(), LetterNumberCounter.bulan.desc()
        )
    ).scalars().all()
    terpakai = db.execute(
        select(Document).options(selectinload(Document.application)).order_by(Document.id.desc()).limit(15)
    ).scalars().all()
    return render(
        request,
        "admin/nomor.html",
        {
            "nav": _opsi_nav(user),
            "aktif": "/admin/nomor",
            "judul": "Nomor surat",
            "rows": rows,
            "terpakai": terpakai,
            "berikut": peek_letter_number(db),
        },
    )


@router.post("/nomor")
async def set_nomor(
    request: Request, db: Session = Depends(get_db), user: AdminUser = Depends(require_login)
):
    _izin(user, "number.manage")
    form = await request.form()
    assert_csrf(request, _csrf_form(form))

    tahun = _ke_int(form.get("tahun"), datetime.now(timezone.utc).year)
    bulan = _ke_int(form.get("bulan"), datetime.now(timezone.utc).month)
    urutan = _ke_int(form.get("urutan"), 0)
    if not 1 <= bulan <= 12:
        return _kembali("/admin/nomor", "Bulan harus 1–12.", "err")
    if urutan < 0:
        return _kembali("/admin/nomor", "Urutan tidak boleh negatif.", "err")

    row = db.execute(
        select(LetterNumberCounter).where(
            LetterNumberCounter.kode == "DKP",
            LetterNumberCounter.tahun == tahun,
            LetterNumberCounter.bulan == bulan,
        )
    ).scalar_one_or_none()
    if row is None:
        row = LetterNumberCounter(kode="DKP", tahun=tahun, bulan=bulan, urutan=urutan)
        db.add(row)
    else:
        row.urutan = urutan
    catat(db, aksi="number.set", entitas="letter_number_counter",
          entitas_id=f"{tahun}-{bulan:02d}", aktor=user,
          detail={"urutan": urutan}, ip=client_ip(request))
    db.commit()
    return _kembali("/admin/nomor", f"Urutan {bulan:02d}/{tahun} diset ke {urutan}.")


# --------------------------------------------------------------------------- #
# Model NLP
# --------------------------------------------------------------------------- #
@router.get("/model", response_class=HTMLResponse)
def halaman_model(
    request: Request, db: Session = Depends(get_db), user: AdminUser = Depends(require_login)
):
    _izin(user, "model.manage")
    rows = db.execute(select(NlpModel).order_by(NlpModel.id.desc())).scalars().all()
    aktif = next((m for m in rows if m.aktif), None)
    metrik = (
        db.execute(
            select(ModelMetric).where(ModelMetric.model_id == aktif.id).order_by(ModelMetric.label)
        ).scalars().all()
        if aktif
        else []
    )
    jumlah_sampel = db.execute(
        select(func.count(TrainingSample.id)).where(TrainingSample.aktif.is_(True))
    ).scalar_one()
    return render(
        request,
        "admin/model.html",
        {
            "nav": _opsi_nav(user),
            "aktif": "/admin/model",
            "judul": "Model NLP",
            "rows": rows,
            "model_aktif": aktif,
            "metrik": metrik,
            "jumlah_sampel": jumlah_sampel,
            "runtime_siap": nlp.siap,
            "runtime_versi": nlp.versi,
        },
    )


@router.post("/model/latih")
async def latih_model(
    request: Request, db: Session = Depends(get_db), user: AdminUser = Depends(require_login)
):
    _izin(user, "model.manage")
    form = await request.form()
    assert_csrf(request, _csrf_form(form))

    rows = db.execute(
        select(TrainingSample).where(TrainingSample.aktif.is_(True))
    ).scalars().all()
    sampel = [(r.teks, r.intent_kode) for r in rows]
    try:
        # Pelatihan memakan 10–20 detik CPU; jalankan di threadpool agar event
        # loop tetap melayani permintaan lain selama proses berjalan.
        hasil = await run_in_threadpool(
            nlp.latih, sampel, catatan=f"Dilatih ulang oleh {user.email}."
        )
    except ValueError as exc:
        return _kembali("/admin/model", str(exc), "err")

    db.execute(NlpModel.__table__.update().values(aktif=False))
    model = NlpModel(
        versi=hasil.versi,
        file_path=hasil.file_path,
        aktif=True,
        akurasi=hasil.akurasi,
        macro_f1=hasil.macro_f1,
        jumlah_sampel=hasil.jumlah_sampel,
        jumlah_intent=hasil.jumlah_intent,
        dilatih_oleh=user.id,
        catatan=f"Dilatih ulang oleh {user.email}. Evaluasi: {hasil.metode}.",
    )
    db.add(model)
    db.flush()
    for m in hasil.metrik_per_kelas:
        db.add(ModelMetric(model_id=model.id, **m))
    catat(db, aksi="model.train", entitas="nlp_model", entitas_id=model.id, aktor=user,
          detail={"akurasi": hasil.akurasi, "macro_f1": hasil.macro_f1}, ip=client_ip(request))
    db.commit()
    return _kembali(
        "/admin/model",
        f"Model {model.versi} aktif — akurasi {hasil.akurasi:.1%}, macro F1 {hasil.macro_f1:.3f}.",
    )


@router.post("/model/{mid}/aktifkan")
async def aktifkan_model(
    mid: int,
    request: Request,
    db: Session = Depends(get_db),
    user: AdminUser = Depends(require_login),
):
    _izin(user, "model.manage")
    form = await request.form()
    assert_csrf(request, _csrf_form(form))
    row = db.get(NlpModel, mid)
    if row is None:
        raise HTTPException(status_code=404, detail="Model tidak ditemukan.")

    from pathlib import Path

    from app.config import BASE_DIR

    path = Path(row.file_path)
    if not path.is_absolute():
        path = BASE_DIR / path
    if not nlp.muat(path):
        return _kembali("/admin/model", "Berkas model tidak ditemukan atau rusak.", "err")

    db.execute(NlpModel.__table__.update().values(aktif=False))
    row.aktif = True
    catat(db, aksi="model.activate", entitas="nlp_model", entitas_id=row.id, aktor=user,
          ip=client_ip(request))
    db.commit()
    return _kembali("/admin/model", f"Model {row.versi} diaktifkan.")


# --------------------------------------------------------------------------- #
# Dataset latih & pertanyaan gagal
# --------------------------------------------------------------------------- #
@router.get("/dataset", response_class=HTMLResponse)
def halaman_dataset(
    request: Request,
    db: Session = Depends(get_db),
    user: AdminUser = Depends(require_login),
    intent: str = Query(default=""),
    q: str = Query(default=""),
    page: int = Query(default=1, ge=1),
):
    _izin(user, "dataset.manage")

    stmt = select(TrainingSample)
    if intent:
        stmt = stmt.where(TrainingSample.intent_kode == intent)
    if q:
        stmt = stmt.where(TrainingSample.teks.ilike(f"%{q.strip()}%"))
    total = db.execute(select(func.count()).select_from(stmt.subquery())).scalar_one()
    info = _halaman(total, page, 50)
    rows = db.execute(
        stmt.order_by(TrainingSample.intent_kode, TrainingSample.id)
        .offset((info["page"] - 1) * info["per"])
        .limit(info["per"])
    ).scalars().all()

    sebaran = db.execute(
        select(TrainingSample.intent_kode, func.count(TrainingSample.id))
        .where(TrainingSample.aktif.is_(True))
        .group_by(TrainingSample.intent_kode)
        .order_by(func.count(TrainingSample.id).desc())
    ).all()
    intents = db.execute(select(Intent).order_by(Intent.kode)).scalars().all()
    return render(
        request,
        "admin/dataset.html",
        {
            "nav": _opsi_nav(user),
            "aktif": "/admin/dataset",
            "judul": "Dataset latih",
            "rows": rows,
            "info": info,
            "intents": intents,
            "sebaran": sebaran,
            "filter": {"intent": intent, "q": q},
        },
    )


@router.post("/dataset")
async def tambah_sampel(
    request: Request, db: Session = Depends(get_db), user: AdminUser = Depends(require_login)
):
    _izin(user, "dataset.manage")
    form = await request.form()
    assert_csrf(request, _csrf_form(form))

    teks = _bersih(form.get("teks"))
    intent_kode = _bersih(form.get("intent_kode")).upper()
    if not teks or not intent_kode:
        return _kembali("/admin/dataset", "Teks dan intent wajib diisi.", "err")
    ada = db.execute(select(Intent).where(Intent.kode == intent_kode)).scalar_one_or_none()
    if ada is None:
        return _kembali("/admin/dataset", f"Intent '{intent_kode}' tidak dikenal.", "err")

    row = TrainingSample(intent_kode=intent_kode, teks=teks, sumber="manual", aktif=True)
    db.add(row)
    db.flush()
    catat(db, aksi="dataset.create", entitas="training_sample", entitas_id=row.id, aktor=user,
          detail={"intent": intent_kode}, ip=client_ip(request))
    db.commit()
    return _kembali("/admin/dataset", "Sampel ditambahkan. Latih ulang model agar berlaku.")


@router.post("/dataset/{sid}/hapus")
async def hapus_sampel(
    sid: int,
    request: Request,
    db: Session = Depends(get_db),
    user: AdminUser = Depends(require_login),
):
    _izin(user, "dataset.manage")
    form = await request.form()
    assert_csrf(request, _csrf_form(form))
    row = db.get(TrainingSample, sid)
    if row is None:
        raise HTTPException(status_code=404, detail="Sampel tidak ditemukan.")
    db.delete(row)
    catat(db, aksi="dataset.delete", entitas="training_sample", entitas_id=sid, aktor=user,
          ip=client_ip(request))
    db.commit()
    return _kembali("/admin/dataset", "Sampel dihapus.")


@router.get("/pertanyaan", response_class=HTMLResponse)
def pertanyaan_gagal(
    request: Request,
    db: Session = Depends(get_db),
    user: AdminUser = Depends(require_login),
    page: int = Query(default=1, ge=1),
):
    """Antrean pertanyaan yang tidak dikenali model (confidence rendah / LAINNYA)."""
    _izin(user, "faq.manage")

    stmt = (
        select(ChatMessage)
        .options(selectinload(ChatMessage.session))
        .where(
            ChatMessage.arah == "in",
            or_(
                ChatMessage.intent_kode.is_(None),
                ChatMessage.intent_kode == "LAINNYA",
                ChatMessage.confidence < C.CONFIDENCE_RENDAH,
            ),
        )
    )
    total = db.execute(select(func.count()).select_from(stmt.subquery())).scalar_one()
    info = _halaman(total, page)
    rows = db.execute(
        stmt.order_by(ChatMessage.created_at.desc())
        .offset((info["page"] - 1) * info["per"])
        .limit(info["per"])
    ).scalars().all()
    intents = db.execute(select(Intent).order_by(Intent.kode)).scalars().all()
    return render(
        request,
        "admin/pertanyaan.html",
        {
            "nav": _opsi_nav(user),
            "aktif": "/admin/pertanyaan",
            "judul": "Pertanyaan gagal",
            "rows": rows,
            "info": info,
            "intents": intents,
        },
    )


@router.post("/pertanyaan/label")
async def label_pertanyaan(
    request: Request, db: Session = Depends(get_db), user: AdminUser = Depends(require_login)
):
    _izin(user, "faq.manage")
    form = await request.form()
    assert_csrf(request, _csrf_form(form))

    teks = _bersih(form.get("teks"))
    intent_kode = _bersih(form.get("intent_kode")).upper()
    if not teks or not intent_kode:
        return _kembali("/admin/pertanyaan", "Teks dan label intent wajib diisi.", "err")
    # Label salah ketik akan menjadi kelas hantu yang tidak pernah diprediksi
    # model, jadi intent harus ada di tabel INTENT.
    ada = db.execute(select(Intent).where(Intent.kode == intent_kode)).scalar_one_or_none()
    if ada is None:
        return _kembali("/admin/pertanyaan", f"Intent '{intent_kode}' tidak dikenal.", "err")

    row = TrainingSample(intent_kode=intent_kode, teks=teks, sumber="koreksi", aktif=True)
    db.add(row)
    db.flush()
    catat(db, aksi="dataset.label", entitas="training_sample", entitas_id=row.id, aktor=user,
          detail={"intent": intent_kode}, ip=client_ip(request))
    db.commit()
    return _kembali(
        "/admin/pertanyaan",
        "Pertanyaan dilabeli dan masuk dataset. Latih ulang model di halaman Model NLP.",
    )


# --------------------------------------------------------------------------- #
# Pengguna
# --------------------------------------------------------------------------- #
@router.get("/pengguna", response_class=HTMLResponse)
def daftar_pengguna(
    request: Request, db: Session = Depends(get_db), user: AdminUser = Depends(require_login)
):
    _izin(user, "user.manage")
    rows = db.execute(select(AdminUser).order_by(AdminUser.role, AdminUser.nama_lengkap)).scalars().all()
    return render(
        request,
        "admin/pengguna.html",
        {
            "nav": _opsi_nav(user),
            "aktif": "/admin/pengguna",
            "judul": "Pengguna",
            "rows": rows,
            "peran": [r.value for r in C.Role],
        },
    )


@router.post("/pengguna")
async def tambah_pengguna(
    request: Request, db: Session = Depends(get_db), user: AdminUser = Depends(require_login)
):
    _izin(user, "user.manage")
    form = await request.form()
    assert_csrf(request, _csrf_form(form))

    email = _bersih(form.get("email")).lower()
    nama = _bersih(form.get("nama_lengkap"))
    sandi = str(form.get("password") or "")
    peran = _bersih(form.get("role"))
    if not email or not nama or len(sandi) < 8:
        return _kembali("/admin/pengguna", "Nama, email, dan sandi minimal 8 karakter wajib diisi.", "err")
    if peran not in {r.value for r in C.Role}:
        return _kembali("/admin/pengguna", "Peran tidak dikenal.", "err")
    ada = db.execute(select(AdminUser).where(AdminUser.email == email)).scalar_one_or_none()
    if ada is not None:
        return _kembali("/admin/pengguna", "Email sudah terdaftar.", "err")

    row = AdminUser(
        email=email,
        nama_lengkap=nama,
        password_hash=hash_password(sandi),
        role=peran,
        aktif=True,
    )
    db.add(row)
    db.flush()
    catat(db, aksi="user.create", entitas="admin_user", entitas_id=row.id, aktor=user,
          detail={"email": email, "role": peran}, ip=client_ip(request))
    db.commit()
    return _kembali("/admin/pengguna", "Pengguna ditambahkan.")


@router.post("/pengguna/{uid}")
async def ubah_pengguna(
    uid: int,
    request: Request,
    db: Session = Depends(get_db),
    user: AdminUser = Depends(require_login),
):
    _izin(user, "user.manage")
    form = await request.form()
    assert_csrf(request, _csrf_form(form))
    row = db.get(AdminUser, uid)
    if row is None:
        raise HTTPException(status_code=404, detail="Pengguna tidak ditemukan.")

    peran = _bersih(form.get("role")) or row.role
    if peran not in {r.value for r in C.Role}:
        return _kembali("/admin/pengguna", "Peran tidak dikenal.", "err")
    if row.id == user.id and peran != row.role:
        return _kembali("/admin/pengguna", "Tidak bisa mengubah peran akun sendiri.", "err")

    row.nama_lengkap = _bersih(form.get("nama_lengkap")) or row.nama_lengkap
    row.role = peran
    row.aktif = _bersih(form.get("aktif")) in {"1", "on", "true", "ya"}
    if row.id == user.id and not row.aktif:
        return _kembali("/admin/pengguna", "Tidak bisa menonaktifkan akun sendiri.", "err")

    sandi = str(form.get("password") or "")
    if sandi:
        if len(sandi) < 8:
            return _kembali("/admin/pengguna", "Sandi baru minimal 8 karakter.", "err")
        row.password_hash = hash_password(sandi)

    catat(db, aksi="user.update", entitas="admin_user", entitas_id=row.id, aktor=user,
          detail={"role": peran, "aktif": row.aktif, "ganti_sandi": bool(sandi)},
          ip=client_ip(request))
    db.commit()
    return _kembali("/admin/pengguna", "Pengguna diperbarui.")


# --------------------------------------------------------------------------- #
# Pengaturan
# --------------------------------------------------------------------------- #
@router.get("/pengaturan", response_class=HTMLResponse)
def halaman_pengaturan(
    request: Request, db: Session = Depends(get_db), user: AdminUser = Depends(require_login)
):
    _izin(user, "setting.manage")
    rows = db.execute(select(Setting).order_by(Setting.kunci)).scalars().all()
    pejabat = db.execute(
        select(Official).where(Official.aktif.is_(True)).order_by(Official.urutan)
    ).scalars().all()
    return render(
        request,
        "admin/pengaturan.html",
        {
            "nav": _opsi_nav(user),
            "aktif": "/admin/pengaturan",
            "judul": "Pengaturan",
            "rows": rows,
            "pejabat": pejabat,
            "jabatan_ttd": docsvc.JABATAN_PENANDATANGAN,
            "env": {
                "app_env": settings.app_env,
                "app_url": settings.app_url,
                "database": settings.resolved_database_url.split("///")[0],
                "telegram": bool(settings.telegram_bot_token),
                "fonnte": bool(settings.fonnte_token),
            },
        },
    )


@router.post("/pengaturan")
async def simpan_pengaturan(
    request: Request, db: Session = Depends(get_db), user: AdminUser = Depends(require_login)
):
    _izin(user, "setting.manage")
    form = await request.form()
    assert_csrf(request, _csrf_form(form))

    diubah: dict[str, str] = {}
    rows = db.execute(select(Setting)).scalars().all()
    for row in rows:
        kunci_form = f"nilai_{row.id}"
        if kunci_form not in form:
            continue
        nilai = _bersih(form.get(kunci_form))
        if row.kunci.startswith("penandatangan_") and nilai not in docsvc.JABATAN_PENANDATANGAN:
            return _kembali(
                "/admin/pengaturan",
                f"{row.kunci}: penanda tangan harus Kepala Desa atau Sekretaris Desa.",
                "err",
            )
        if row.tipe == "float":
            try:
                float(nilai)
            except ValueError:
                return _kembali("/admin/pengaturan", f"{row.kunci} harus angka desimal.", "err")
        elif row.tipe == "int":
            if not nilai.isdigit():
                return _kembali("/admin/pengaturan", f"{row.kunci} harus bilangan bulat.", "err")
        if nilai != row.nilai:
            diubah[row.kunci] = nilai
            row.nilai = nilai

    catat(db, aksi="setting.update", entitas="setting", aktor=user, detail=diubah,
          ip=client_ip(request))
    db.commit()
    return _kembali(
        "/admin/pengaturan",
        f"{len(diubah)} pengaturan diperbarui." if diubah else "Tidak ada perubahan.",
    )


# --------------------------------------------------------------------------- #
# Audit
# --------------------------------------------------------------------------- #
@router.get("/audit", response_class=HTMLResponse)
def halaman_audit(
    request: Request,
    db: Session = Depends(get_db),
    user: AdminUser = Depends(require_login),
    aksi: str = Query(default=""),
    q: str = Query(default=""),
    page: int = Query(default=1, ge=1),
):
    _izin(user, "audit.read")

    stmt = select(AuditLog)
    if aksi:
        stmt = stmt.where(AuditLog.aksi == aksi)
    if q:
        stmt = stmt.where(AuditLog.actor_email.ilike(f"%{q.strip()}%"))
    total = db.execute(select(func.count()).select_from(stmt.subquery())).scalar_one()
    info = _halaman(total, page, 40)
    rows = db.execute(
        stmt.order_by(AuditLog.created_at.desc())
        .offset((info["page"] - 1) * info["per"])
        .limit(info["per"])
    ).scalars().all()
    aksi_semua = db.execute(
        select(AuditLog.aksi, func.count(AuditLog.id)).group_by(AuditLog.aksi).order_by(AuditLog.aksi)
    ).all()
    return render(
        request,
        "admin/audit.html",
        {
            "nav": _opsi_nav(user),
            "aktif": "/admin/audit",
            "judul": "Jejak audit",
            "rows": rows,
            "info": info,
            "aksi_semua": aksi_semua,
            "filter": {"aksi": aksi, "q": q},
        },
    )


# --------------------------------------------------------------------------- #
# Laporan
# --------------------------------------------------------------------------- #
def _data_laporan(db: Session, mulai: date, selesai: date) -> dict[str, Any]:
    awal = datetime.combine(mulai, datetime.min.time(), tzinfo=timezone.utc)
    akhir = datetime.combine(selesai + timedelta(days=1), datetime.min.time(), tzinfo=timezone.utc)

    per_status = db.execute(
        select(Application.status, func.count(Application.id))
        .where(Application.created_at >= awal, Application.created_at < akhir)
        .group_by(Application.status)
    ).all()
    per_layanan = db.execute(
        select(Service.nama, func.count(Application.id))
        .join(Application, Application.service_id == Service.id)
        .where(Application.created_at >= awal, Application.created_at < akhir)
        .group_by(Service.nama)
        .order_by(func.count(Application.id).desc())
    ).all()
    per_kanal = db.execute(
        select(Application.channel, func.count(Application.id))
        .where(Application.created_at >= awal, Application.created_at < akhir)
        .group_by(Application.channel)
    ).all()

    selesai_rows = db.execute(
        select(Application.submitted_at, Application.issued_at).where(
            Application.issued_at.is_not(None),
            Application.created_at >= awal,
            Application.created_at < akhir,
        )
    ).all()
    jam: list[float] = []
    for masuk, terbit in selesai_rows:
        if masuk and terbit:
            jam.append((terbit - masuk).total_seconds() / 3600)
    rata_jam = sum(jam) / len(jam) if jam else None

    scans = db.execute(
        select(func.count(VerificationScan.id)).where(
            VerificationScan.created_at >= awal, VerificationScan.created_at < akhir
        )
    ).scalar_one()
    rating = db.execute(
        select(func.avg(FeedbackResponse.rating)).where(
            FeedbackResponse.created_at >= awal, FeedbackResponse.created_at < akhir
        )
    ).scalar()

    return {
        "per_status": per_status,
        "per_layanan": per_layanan,
        "per_kanal": per_kanal,
        "jumlah": sum(j for _, j in per_status),
        "rata_jam": rata_jam,
        "scans": scans,
        "rating": float(rating) if rating else None,
    }


@router.get("/laporan", response_class=HTMLResponse)
def halaman_laporan(
    request: Request,
    db: Session = Depends(get_db),
    user: AdminUser = Depends(require_login),
    mulai: str = Query(default=""),
    selesai: str = Query(default=""),
):
    _izin(user, "report.read")
    hari_ini = datetime.now(timezone.utc).date()
    try:
        awal = date.fromisoformat(mulai) if mulai else hari_ini.replace(day=1)
        akhir = date.fromisoformat(selesai) if selesai else hari_ini
    except ValueError:
        awal, akhir = hari_ini.replace(day=1), hari_ini
    if akhir < awal:
        awal, akhir = akhir, awal

    data = _data_laporan(db, awal, akhir)
    return render(
        request,
        "admin/laporan.html",
        {
            "nav": _opsi_nav(user),
            "aktif": "/admin/laporan",
            "judul": "Laporan",
            "data": data,
            "mulai": awal.isoformat(),
            "selesai": akhir.isoformat(),
        },
    )


@router.get("/laporan.csv")
def ekspor_laporan(
    db: Session = Depends(get_db),
    user: AdminUser = Depends(require_login),
    mulai: str = Query(default=""),
    selesai: str = Query(default=""),
):
    _izin(user, "report.read")
    hari_ini = datetime.now(timezone.utc).date()
    try:
        awal = date.fromisoformat(mulai) if mulai else hari_ini.replace(day=1)
        akhir = date.fromisoformat(selesai) if selesai else hari_ini
    except ValueError:
        awal, akhir = hari_ini.replace(day=1), hari_ini
    if akhir < awal:
        awal, akhir = akhir, awal

    batas_awal = datetime.combine(awal, datetime.min.time(), tzinfo=timezone.utc)
    batas_akhir = datetime.combine(akhir + timedelta(days=1), datetime.min.time(), tzinfo=timezone.utc)
    rows = db.execute(
        select(Application)
        .options(selectinload(Application.service), selectinload(Application.citizen))
        .where(Application.created_at >= batas_awal, Application.created_at < batas_akhir)
        .order_by(Application.created_at)
    ).scalars().all()

    buffer = io.StringIO()
    buffer.write("\ufeff")  # BOM agar Excel membaca UTF-8 dengan benar.
    tulis = csv.writer(buffer, delimiter=";")
    tulis.writerow(
        [
            "tiket", "tanggal", "layanan", "pemohon", "nik", "dusun",
            "status", "kanal", "nomor_surat", "diajukan", "terbit",
        ]
    )
    for app in rows:
        warga = app.citizen
        tulis.writerow(
            [
                app.ticket_no,
                app.created_at.strftime("%Y-%m-%d %H:%M"),
                app.service.nama if app.service else "-",
                warga.nama_lengkap if warga else "-",
                warga.nik if warga else "-",
                (warga.dusun if warga else "") or "-",
                app.status,
                app.channel,
                app.documents[-1].nomor_surat if app.documents else "",
                app.submitted_at.strftime("%Y-%m-%d %H:%M") if app.submitted_at else "",
                app.issued_at.strftime("%Y-%m-%d %H:%M") if app.issued_at else "",
            ]
        )

    nama = f"laporan-persuratan-{awal.isoformat()}_{akhir.isoformat()}.csv"
    return StreamingResponse(
        iter([buffer.getvalue()]),
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="{nama}"'},
    )
