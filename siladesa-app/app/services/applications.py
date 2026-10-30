"""Mesin status pengajuan surat."""

from __future__ import annotations

from datetime import date, datetime, timezone
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app import constants as C
from app.models import AdminUser, Application, ApplicationEvent, Citizen, Service
from app.services.numbering import next_ticket_no

#: Field yang disimpan pada tabel CITIZEN, sisanya masuk `application.form_data`.
CITIZEN_FIELDS = {
    "nik",
    "nama_lengkap",
    "jenis_kelamin",
    "tempat_lahir",
    "tanggal_lahir",
    "agama",
    "status_perkawinan",
    "pekerjaan",
    "alamat",
    "dusun",
    "rt",
    "rw",
    "no_hp",
    "email",
}


class KesalahanPengajuan(Exception):
    """Pelanggaran aturan bisnis pengajuan."""


def _now() -> datetime:
    return datetime.now(timezone.utc)


# --------------------------------------------------------------------------- #
# Validasi
# --------------------------------------------------------------------------- #
def validasi_nilai(field, nilai: Any) -> str | None:
    """Validasi satu field. Kembalikan pesan kesalahan atau None."""
    kosong = nilai is None or (isinstance(nilai, str) and not nilai.strip())
    if kosong:
        return f"{field.label} wajib diisi." if field.wajib else None

    teks = str(nilai).strip()
    if field.tipe == "nik":
        if not (teks.isdigit() and len(teks) == 16):
            return f"{field.label} harus 16 digit angka."
        if not teks.startswith(C.NIK_PREFIX):
            return f"{field.label} bukan NIK Kabupaten Jeneponto."
    elif field.tipe == "phone":
        digit = "".join(ch for ch in teks if ch.isdigit())
        if not (10 <= len(digit) <= 15):
            return f"{field.label} harus 10–15 digit angka."
    elif field.tipe == "date":
        try:
            date.fromisoformat(teks)
        except ValueError:
            return f"{field.label} harus berformat YYYY-MM-DD."
    elif field.tipe == "email":
        if "@" not in teks or "." not in teks.split("@")[-1]:
            return f"{field.label} bukan alamat email yang sah."
    elif field.tipe == "number":
        if not teks.replace(".", "").replace(",", "").isdigit():
            return f"{field.label} harus berupa angka."
    elif field.tipe == "select" and field.pilihan:
        if teks not in field.pilihan:
            return f"{field.label} harus salah satu dari: {', '.join(field.pilihan)}."
    return None


def validasi_form(service: Service, data: dict[str, Any]) -> list[str]:
    """Kembalikan daftar pesan kesalahan; kosong berarti lolos validasi."""
    errors: list[str] = []
    for field in service.fields:
        pesan = validasi_nilai(field, data.get(field.nama_field))
        if pesan:
            errors.append(pesan)
    return errors


# --------------------------------------------------------------------------- #
# Warga
# --------------------------------------------------------------------------- #
def cari_citizen(db: Session, nik: str) -> Citizen | None:
    """Cari data warga berdasarkan NIK (16 digit)."""
    return db.execute(select(Citizen).where(Citizen.nik == nik.strip())).scalar_one_or_none()


def upsert_citizen(db: Session, data: dict[str, Any]) -> Citizen:
    """Catat warga dari pengajuan tanpa pernah menimpa data induk yang sudah ada.

    Data induk (`citizen`) adalah arsip kantor desa: pengajuan hanya boleh
    membuat baris baru atau **mengisi kolom yang masih kosong**. Nilai yang
    sudah terisi tidak ditimpa, sehingga pemohon tidak dapat mengubah nama,
    alamat, atau NIK warga lain lewat jalur pengajuan. Koreksi data induk
    dilakukan petugas lewat Panel → Data warga.
    """
    nik = str(data.get("nik", "")).strip()
    if not nik:
        raise KesalahanPengajuan("NIK wajib diisi sebelum pengajuan dikirim.")

    citizen = cari_citizen(db, nik)
    if citizen is not None and not citizen.aktif:
        raise KesalahanPengajuan(
            "NIK ini tercatat nonaktif. Hubungi kantor desa untuk mengaktifkan kembali."
        )

    baru = citizen is None
    if baru:
        citizen = Citizen(nik=nik, nama_lengkap=str(data.get("nama_lengkap") or "").strip() or "-")
        db.add(citizen)

    for nama in CITIZEN_FIELDS - {"nik"}:
        if nama not in data:
            continue
        nilai = data[nama]
        if nilai is None or (isinstance(nilai, str) and not nilai.strip()):
            continue
        if not baru and getattr(citizen, nama, None) not in (None, ""):
            continue
        if nama == "tanggal_lahir" and isinstance(nilai, str):
            try:
                nilai = date.fromisoformat(nilai)
            except ValueError:
                continue
        setattr(citizen, nama, nilai.strip() if isinstance(nilai, str) else nilai)
    db.flush()
    return citizen


def jumlah_pengajuan_aktif(db: Session, nik: str) -> int:
    return (
        db.execute(
            select(func.count(Application.id))
            .join(Citizen, Application.citizen_id == Citizen.id)
            .where(Citizen.nik == nik, Application.status.in_([s.value for s in C.STATUS_AKTIF]))
        ).scalar_one()
        or 0
    )


# --------------------------------------------------------------------------- #
# Pembuatan & transisi
# --------------------------------------------------------------------------- #
def buat_draft(
    db: Session,
    *,
    service: Service,
    form_data: dict[str, Any],
    channel: str = "web",
    session_id: str | None = None,
) -> Application:
    app = Application(
        ticket_no="",
        service_id=service.id,
        status=C.Status.DRAFT.value,
        form_data=dict(form_data),
        channel=channel,
        session_id=session_id,
    )
    db.add(app)
    next_ticket_no(db, app)
    db.add(
        ApplicationEvent(
            application_id=app.id,
            dari_status=None,
            ke_status=C.Status.DRAFT.value,
            aktor_label="sistem",
            catatan=f"Draft dibuat melalui kanal {channel}.",
        )
    )
    db.flush()
    return app


def kirim_pengajuan(db: Session, app: Application) -> Application:
    """DRAFT → MENUNGGU_VERIFIKASI setelah data lengkap dan valid."""
    if app.status != C.Status.DRAFT.value:
        raise KesalahanPengajuan(f"Pengajuan berstatus {app.status}, bukan DRAFT.")

    service = app.service
    data = dict(app.form_data or {})
    errors = validasi_form(service, data)
    if errors:
        raise KesalahanPengajuan(" ".join(errors))

    citizen = upsert_citizen(db, data)
    if jumlah_pengajuan_aktif(db, citizen.nik) >= C.BATAS_PENGAJUAN_AKTIF:
        raise KesalahanPengajuan(
            f"NIK ini sudah memiliki {C.BATAS_PENGAJUAN_AKTIF} pengajuan aktif. "
            "Selesaikan atau batalkan salah satunya lebih dulu."
        )

    app.citizen_id = citizen.id
    app.status = C.Status.MENUNGGU_VERIFIKASI.value
    app.submitted_at = _now()
    db.add(
        ApplicationEvent(
            application_id=app.id,
            dari_status=C.Status.DRAFT.value,
            ke_status=C.Status.MENUNGGU_VERIFIKASI.value,
            aktor_label="warga",
            catatan="Pengajuan dikirim untuk verifikasi.",
        )
    )
    db.flush()
    return app


def transisi(
    db: Session,
    app: Application,
    ke: str,
    *,
    aktor: AdminUser | None,
    aktor_label: str | None = None,
    catatan: str | None = None,
) -> Application:
    dari = app.status
    izin = C.TRANSISI.get((C.Status(dari), C.Status(ke)))
    if izin is None:
        raise KesalahanPengajuan(f"Transisi {dari} → {ke} tidak sah.")
    if aktor is not None and C.Role(aktor.role) not in izin:
        raise KesalahanPengajuan(f"Peran {aktor.role} tidak berhak mengubah {dari} → {ke}.")
    if ke == C.Status.DITOLAK.value and not (catatan or "").strip():
        raise KesalahanPengajuan("Alasan penolakan wajib diisi.")

    app.status = ke
    now = _now()
    if ke == C.Status.DIPROSES.value:
        app.verified_at = now
    elif ke == C.Status.TERBIT.value:
        app.issued_at = now
        app.closed_at = now
    elif ke in {C.Status.DITOLAK.value, C.Status.DIBATALKAN.value}:
        app.closed_at = now
        if ke == C.Status.DITOLAK.value:
            app.alasan_penolakan = catatan
    if catatan and ke != C.Status.TERBIT.value:
        # Catatan penerbitan tidak menimpa catatan petugas: alasannya sudah
        # tersimpan di riwayat (ApplicationEvent) dan nomor surat tampil di
        # halaman lacak. Catatan operator tetap yang paling berguna bagi warga.
        app.catatan_operator = catatan

    db.add(
        ApplicationEvent(
            application_id=app.id,
            dari_status=dari,
            ke_status=ke,
            aktor_id=aktor.id if aktor else None,
            aktor_label=aktor_label or (aktor.nama_lengkap if aktor else "sistem"),
            catatan=catatan,
        )
    )
    db.flush()
    return app


# --------------------------------------------------------------------------- #
# Pelacakan publik
# --------------------------------------------------------------------------- #
def lacak(db: Session, ticket_no: str, nik: str | None = None) -> Application | None:
    """Cari pengajuan berdasarkan tiket **dan** NIK pemohon.

    NIK wajib: nomor tiket berurutan (`APP-{tahun}-{id}`), jadi tanpa NIK
    siapa pun bisa menebak tiket dan membaca status surat orang lain.
    Tanpa NIK atau bila NIK tidak cocok, hasilnya `None` — pemanggil tidak
    boleh membedakan "tiket tidak ada" dari "NIK salah".
    """
    if not nik or not nik.strip():
        return None
    app = db.execute(
        select(Application).where(Application.ticket_no == ticket_no.strip().upper())
    ).scalar_one_or_none()
    if app is None:
        return None
    if app.citizen is None or app.citizen.nik != nik.strip():
        return None
    return app


def ringkasan_status(app: Application) -> dict[str, Any]:
    dokumen = app.documents[-1] if app.documents else None
    terbit = dokumen is not None and dokumen.status == "TERBIT"
    return {
        "ticket_no": app.ticket_no,
        "status": app.status,
        "nomor_surat": dokumen.nomor_surat if terbit else None,
        #: Nomor tetap ditampilkan pada halaman lacak meski surat dicabut,
        #: tetapi tanpa tautan unduh.
        "nomor_surat_dicabut": dokumen.nomor_surat
        if dokumen is not None and dokumen.status == "DIBATALKAN"
        else None,
        "dokumen_terbit": terbit,
        "service_nama": app.service.nama if app.service else "-",
        "pemohon": app.citizen.nama_lengkap if app.citizen else "-",
        "dibuat": app.created_at,
        "diperbarui": app.updated_at,
        "catatan": app.alasan_penolakan or app.catatan_operator,
        "riwayat": [
            {
                "dari": e.dari_status,
                "ke": e.ke_status,
                "aktor": e.aktor_label,
                "catatan": e.catatan,
                "waktu": e.created_at,
            }
            for e in app.events
        ],
    }


def mask_nik(nik: str | None) -> str:
    if not nik or len(nik) < 8:
        return C.MASK_NIK
    return f"{nik[:4]}{'*' * 8}{nik[-4:]}"
