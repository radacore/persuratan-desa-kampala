"""Verifikasi dokumen melalui token QR."""

from __future__ import annotations

import hashlib
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import settings
from app.models import Document, VerificationScan
from app.services.applications import mask_nik

#: Panjang maksimum token QR. `document.qr_token` adalah String(64); token lebih
#: panjang tidak mungkin cocok dan akan memicu DataError di PostgreSQL.
MAKS_TOKEN = 64

_HASIL_TIDAK_DITEMUKAN = {
    "valid": False,
    "hasil": "TIDAK_DITEMUKAN",
    "pesan": (
        "Dokumen tidak ditemukan. QR code mungkin rusak, salah ketik, "
        "atau bukan diterbitkan oleh Desa Kampala."
    ),
}


def _berkas_utuh(dokumen: Document) -> bool:
    """True bila isi berkas di disk masih cocok dengan `sha256` saat diterbitkan.

    Tanpa pemeriksaan ini, PDF yang ditukar di penyimpanan tetap dilaporkan sah
    karena halaman verifikasi hanya membaca nilai hash dari basis data.
    """
    path = Path(dokumen.file_path)
    if not path.is_absolute():
        path = settings.storage_path / path
    try:
        sidik = hashlib.sha256(path.read_bytes()).hexdigest()
    except OSError:
        return False
    return sidik == dokumen.sha256


def verifikasi(
    db: Session, token: str, *, ip: str | None = None, user_agent: str | None = None
) -> dict:
    """Cari dokumen berdasarkan token QR, catat pemindaian, kembalikan hasilnya."""
    if not token or len(token) > MAKS_TOKEN:
        # Tidak dicatat: token sepanjang ini pasti karangan, dan mencatatnya
        # hanya menggelembungkan `verification_scan`.
        return dict(_HASIL_TIDAK_DITEMUKAN)

    dokumen = db.execute(
        select(Document).where(Document.qr_token == token)
    ).scalar_one_or_none()

    if dokumen is None:
        db.add(
            VerificationScan(
                document_id=None, qr_token=token, ip_address=ip, user_agent=user_agent,
                hasil="TIDAK_DITEMUKAN",
            )
        )
        return dict(_HASIL_TIDAK_DITEMUKAN)

    app = dokumen.application
    citizen = app.citizen if app else None
    dibatalkan = dokumen.status == "DIBATALKAN" or (app is not None and app.status == "DIBATALKAN")
    utuh = _berkas_utuh(dokumen)

    db.add(
        VerificationScan(
            document_id=dokumen.id,
            qr_token=token,
            ip_address=ip,
            user_agent=user_agent,
            hasil="DIBATALKAN" if dibatalkan else ("VALID" if utuh else "TIDAK_DITEMUKAN"),
        )
    )

    if dibatalkan:
        pesan = (
            "Dokumen ini pernah diterbitkan namun telah DIBATALKAN oleh Desa Kampala. "
            "Jangan gunakan dokumen ini sebagai bukti yang sah."
        )
        hasil = "DIBATALKAN"
    elif not utuh:
        # Token benar tetapi berkasnya hilang/berubah: jangan pernah menyatakan sah.
        pesan = (
            "Berkas dokumen ini tidak cocok dengan arsip desa. "
            "Hubungi kantor desa untuk meminta salinan resmi."
        )
        hasil = "TIDAK_DITEMUKAN"
    else:
        pesan = "Dokumen sah dan diterbitkan oleh Pemerintah Desa Kampala."
        hasil = "VALID"

    return {
        "valid": hasil == "VALID",
        "hasil": hasil,
        "nomor_surat": dokumen.nomor_surat,
        "jenis_surat": app.service.nama if app and app.service else None,
        "nama_pemohon": citizen.nama_lengkap if citizen else None,
        "nik_masked": mask_nik(citizen.nik if citizen else None),
        "tanggal_terbit": dokumen.issued_at,
        "sha256": dokumen.sha256,
        "berkas_utuh": utuh,
        "pesan": pesan,
        "dibatalkan_pada": dokumen.revoked_at,
        "alasan_pembatalan": dokumen.revoked_reason,
    }


def cabut_dokumen(db: Session, dokumen: Document, alasan: str) -> Document:
    from datetime import datetime, timezone

    dokumen.status = "DIBATALKAN"
    dokumen.revoked_at = datetime.now(timezone.utc)
    dokumen.revoked_reason = alasan
    db.flush()
    return dokumen
