"""Lampiran pengajuan: validasi berkas dan penyimpanan di disk.

Petugas mengarsipkan berkas pendukung yang dibawa warga (KTP, KK, foto lokasi
usaha) pada pengajuan. Unggahan dari chat belum dibuka (ROADMAP fase 2), jadi
semua berkas melewati panel admin dan diperiksa di sini.
"""

from __future__ import annotations

import hashlib
import io
import secrets
from dataclasses import dataclass
from pathlib import Path

from PIL import Image as PilImage

from app.config import settings
from app.models import Attachment

#: Jenis berkas yang diterima: ekstensi, MIME, dan label untuk UI.
JENIS_DIIZINKAN = {
    ".pdf": ("application/pdf", "PDF"),
    ".png": ("image/png", "PNG"),
    ".jpg": ("image/jpeg", "JPG"),
    ".jpeg": ("image/jpeg", "JPG"),
}


class LampiranTidakSah(ValueError):
    """Berkas ditolak: kosong, terlalu besar, atau bukan PDF/gambar sah."""


@dataclass(frozen=True)
class BerkasSah:
    ekstensi: str
    mime: str
    isi: bytes
    sha256: str

    @property
    def ukuran(self) -> int:
        return len(self.isi)


def _deteksi_gambar(isi: bytes) -> str | None:
    """Kembalikan ekstensi gambar bila isi benar-benar PNG/JPEG."""
    try:
        gambar = PilImage.open(io.BytesIO(isi))
        gambar.verify()
        gambar = PilImage.open(io.BytesIO(isi))
    except Exception:  # noqa: BLE001 — Pillow melempar beragam tipe untuk berkas rusak
        return None
    if gambar.format == "PNG":
        return ".png"
    if gambar.format == "JPEG":
        return ".jpg"
    return None


def periksa(nama_asli: str, isi: bytes) -> BerkasSah:
    """Validasi isi berkas (bukan hanya nama) dan kembalikan metadata aman."""
    if not isi:
        raise LampiranTidakSah("Berkas kosong.")

    batas = settings.max_upload_mb * 1024 * 1024
    if len(isi) > batas:
        raise LampiranTidakSah(
            f"Berkas {len(isi) / 1024 / 1024:.1f} MB melebihi batas {settings.max_upload_mb} MB."
        )

    ekstensi = Path(nama_asli or "").suffix.lower()
    if ekstensi not in JENIS_DIIZINKAN:
        raise LampiranTidakSah("Format berkas harus PDF, PNG, atau JPG.")

    # Isi yang menentukan jenis, bukan ekstensi: berkas .png berisi skrip tetap ditolak.
    if isi[:5] == b"%PDF-":
        if ekstensi != ".pdf":
            raise LampiranTidakSah("Isi berkas PDF tidak cocok dengan ekstensinya.")
        ekstensi = ".pdf"
    else:
        gambar_ext = _deteksi_gambar(isi)
        if gambar_ext is None:
            raise LampiranTidakSah("Berkas bukan PDF atau gambar PNG/JPG yang sah.")
        ekstensi = gambar_ext

    mime, _label = JENIS_DIIZINKAN[ekstensi]
    return BerkasSah(
        ekstensi=ekstensi,
        mime=mime,
        isi=isi,
        sha256=hashlib.sha256(isi).hexdigest(),
    )


def simpan(application_id: int, berkas: BerkasSah, nama_asli: str) -> Attachment:
    """Tulis berkas ke `storage/attachments/{application_id}/` dan buat baris ORM.

    Nama di disk dibangkitkan acak: nama dari pengguna tidak pernah dipakai
    sebagai path, sehingga `../` atau nama aneh tidak bisa keluar dari folder.
    """
    folder = settings.storage_path / "attachments" / str(application_id)
    folder.mkdir(parents=True, exist_ok=True)
    nama_disk = f"{secrets.token_hex(16)}{berkas.ekstensi}"
    (folder / nama_disk).write_bytes(berkas.isi)

    return Attachment(
        application_id=application_id,
        nama_file=Path(nama_asli or f"lampiran{berkas.ekstensi}").name[:255],
        file_path=str((folder / nama_disk).relative_to(settings.storage_path)),
        mime=berkas.mime,
        ukuran=berkas.ukuran,
        sha256=berkas.sha256,
        uploaded_by="petugas",
    )


def path_berkas(lampiran: Attachment) -> Path:
    path = Path(lampiran.file_path)
    if not path.is_absolute():
        path = settings.storage_path / path
    return path


def hapus_berkas(lampiran: Attachment) -> None:
    """Hapus berkas dari disk; baris ORM dihapus oleh pemanggil."""
    path_berkas(lampiran).unlink(missing_ok=True)
