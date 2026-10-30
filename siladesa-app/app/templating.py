"""Konfigurasi Jinja2 dan filter tampilan."""

from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
from urllib.parse import urlencode
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from fastapi.templating import Jinja2Templates

from app.config import BASE_DIR, settings
from app.constants import BULAN_ROMAWI

try:
    ZONA_LOKAL = ZoneInfo("Asia/Makassar")
except ZoneInfoNotFoundError:  # pragma: no cover - Windows tanpa paket tzdata
    ZONA_LOKAL = timezone(timedelta(hours=8), "WITA")

TEMPLATE_DIR = BASE_DIR / "app" / "templates"

templates = Jinja2Templates(directory=str(TEMPLATE_DIR))

BULAN_SINGKAT = (
    "", "Jan", "Feb", "Mar", "Apr", "Mei", "Jun",
    "Jul", "Agu", "Sep", "Okt", "Nov", "Des",
)

BULAN_PANJANG = (
    "", "Januari", "Februari", "Maret", "April", "Mei", "Juni",
    "Juli", "Agustus", "September", "Oktober", "November", "Desember",
)


def _ke_lokal(nilai: datetime) -> datetime:
    if nilai.tzinfo is None:
        nilai = nilai.replace(tzinfo=timezone.utc)
    return nilai.astimezone(ZONA_LOKAL)


def filter_tanggal(nilai) -> str:
    if not nilai:
        return "-"
    if isinstance(nilai, datetime):
        nilai = _ke_lokal(nilai)
        return f"{nilai.day:02d} {BULAN_SINGKAT[nilai.month]} {nilai.year}"
    if isinstance(nilai, date):
        return f"{nilai.day:02d} {BULAN_SINGKAT[nilai.month]} {nilai.year}"
    return str(nilai)


def filter_tanggal_panjang(nilai) -> str:
    if not nilai:
        return "-"
    if isinstance(nilai, str):
        try:
            nilai = date.fromisoformat(nilai)
        except ValueError:
            return nilai
    if isinstance(nilai, datetime):
        nilai = nilai.date()
    return f"{nilai.day:02d} {BULAN_PANJANG[nilai.month]} {nilai.year}"


def filter_waktu(nilai) -> str:
    """Jam lokal (WITA) saja: '14:05'."""
    if not nilai:
        return "-"
    if isinstance(nilai, datetime):
        return f"{_ke_lokal(nilai):%H:%M}"
    return str(nilai)


def filter_rupiah(nilai) -> str:
    if nilai in (None, ""):
        return "-"
    teks = str(nilai).replace(".", "").replace(",", "").replace("Rp", "").strip()
    if not teks.isdigit():
        return str(nilai)
    return "Rp " + f"{int(teks):,}".replace(",", ".")


def filter_status_label(nilai: str) -> str:
    return {
        "DRAFT": "Draf",
        "MENUNGGU_VERIFIKASI": "Menunggu verifikasi",
        "DIPROSES": "Diproses",
        "TERBIT": "Terbit",
        "DITOLAK": "Ditolak",
        "DIBATALKAN": "Dibatalkan",
    }.get(nilai, nilai)


def filter_status_kelas(nilai: str) -> str:
    return {
        "DRAFT": "badge--netral",
        "MENUNGGU_VERIFIKASI": "badge--tunggu",
        "DIPROSES": "badge--proses",
        "TERBIT": "badge--terbit",
        "DITOLAK": "badge--tolak",
        "DIBATALKAN": "badge--batal",
    }.get(nilai, "badge--netral")


def filter_sejak(nilai) -> str:
    """Jarak waktu singkat: '3 jam lalu', '2 hari lalu'."""
    if not isinstance(nilai, datetime):
        return "-"
    if nilai.tzinfo is None:
        nilai = nilai.replace(tzinfo=timezone.utc)
    selisih = datetime.now(timezone.utc) - nilai
    detik = int(selisih.total_seconds())
    if detik < 60:
        return "baru saja"
    if detik < 3600:
        return f"{detik // 60} menit lalu"
    if detik < 86400:
        return f"{detik // 3600} jam lalu"
    if detik < 86400 * 30:
        return f"{detik // 86400} hari lalu"
    return filter_tanggal(nilai)


templates.env.filters["tanggal"] = filter_tanggal
templates.env.filters["tanggal_panjang"] = filter_tanggal_panjang
templates.env.filters["waktu"] = filter_waktu
templates.env.filters["rupiah"] = filter_rupiah
templates.env.filters["status_label"] = filter_status_label
templates.env.filters["status_kelas"] = filter_status_kelas
templates.env.filters["sejak"] = filter_sejak


def filter_mask_nik(nilai) -> str:
    """Sembunyikan 8 digit tengah NIK untuk tampilan daftar."""
    teks = "".join(ch for ch in str(nilai or "") if ch.isdigit())
    if len(teks) < 8:
        return teks or "-"
    return f"{teks[:4]}{'*' * 8}{teks[-4:]}"


templates.env.filters["mask_nik"] = filter_mask_nik


def filter_romawi(bulan) -> str:
    """Angka bulan (1–12) menjadi angka Romawi untuk nomor surat."""
    try:
        return BULAN_ROMAWI[int(bulan)]
    except (TypeError, ValueError, IndexError):
        return str(bulan)


templates.env.filters["romawi"] = filter_romawi


def url_dengan(request, **ubah) -> str:
    """Bangun URL halaman ini dengan sebagian query string diubah.

    Nilai kosong menghapus parameter, sehingga filter bisa direset.
    """
    params = {k: v for k, v in request.query_params.items()}
    for kunci, nilai in ubah.items():
        if nilai in (None, ""):
            params.pop(kunci, None)
        else:
            params[kunci] = str(nilai)
    qs = urlencode(params)
    return request.url.path + (f"?{qs}" if qs else "")


templates.env.globals.update(
    app_url=settings.app_url.rstrip("/"),
    versi=settings.app_version,
    nama_aplikasi="Persuratan Desa Kampala",
    nama_desa="Desa Kampala",
    peran_label={
        "operator": "Operator",
        "sekdes": "Sekretaris Desa",
        "kepala_desa": "Kepala Desa",
        "admin_teknis": "Admin Teknis",
    },
    url_dengan=url_dengan,
)


def render(request, nama: str, konteks: dict | None = None, *, status_code: int = 200):
    data = {
        "request": request,
        "user": getattr(request.state, "user", None),
        "csrf": getattr(request.state, "csrf", ""),
        "pesan": request.query_params.get("pesan", ""),
        "jenis_pesan": request.query_params.get("jenis", "ok"),
        "path": request.url.path,
    }
    if konteks:
        data.update(konteks)
    return templates.TemplateResponse(request, nama, data, status_code=status_code)
