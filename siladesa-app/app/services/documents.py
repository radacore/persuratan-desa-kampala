"""Pembuatan PDF surat resmi desa.

Alur: template HTML-sederhana → placeholder diisi → flowable ReportLab →
PDF bertanda QR verifikasi. Setiap PDF di-hash SHA-256 agar perubahan satu
byte pun dapat dideteksi.
"""

from __future__ import annotations

import hashlib
import io
import secrets
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any

import qrcode
from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_JUSTIFY, TA_LEFT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import cm
from reportlab.lib.utils import ImageReader
from reportlab.platypus import (
    HRFlowable,
    Image,
    KeepTogether,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)
from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.config import settings
from app.models import Application, Document, LetterTemplate, Official, Service, Setting

BULAN = (
    "", "Januari", "Februari", "Maret", "April", "Mei", "Juni",
    "Juli", "Agustus", "September", "Oktober", "November", "Desember",
)

#: Huruf dasar. Times-Roman adalah metrik-setara Times New Roman dan tersedia
#: di semua instalasi ReportLab, sehingga tidak perlu menyertakan font berlisensi.
FONT = "Times-Roman"
FONT_BOLD = "Times-Bold"
FONT_ITALIC = "Times-Italic"

WARNA_TINTA = colors.HexColor("#111827")
WARNA_ABU = colors.HexColor("#6B7280")
WARNA_GARIS = colors.HexColor("#111827")

#: Margin A4: kiri mengikuti arsip desa (2,75 cm), kanan dibatasi FR-26 (min 2,5 cm),
#: atas-bawah mengikuti arsip desa (2,54 cm).
MARGIN_KIRI = 2.75 * cm
MARGIN_KANAN = 2.5 * cm
MARGIN_ATAS = 2.54 * cm
MARGIN_BAWAH = 2.54 * cm

#: Lebar area teks (A4 dikurangi margin kiri-kanan).
CONTENT_W = A4[0] - MARGIN_KIRI - MARGIN_KANAN

#: Logo kabupaten bawaan, dipakai bila pengaturan `logo_kop` kosong.
LOGO_BAWAAN = Path(__file__).resolve().parent.parent / "static" / "img" / "logo-jeneponto.png"

#: Jabatan yang boleh menandatangani surat desa (lihat format surat resmi).
JABATAN_PENANDATANGAN = ("Kepala Desa", "Sekretaris Desa")


# --------------------------------------------------------------------------- #
# Gaya
# --------------------------------------------------------------------------- #
def _styles() -> dict[str, ParagraphStyle]:
    return {
        "kop": ParagraphStyle(
            "kop", fontName=FONT_BOLD, fontSize=14, leading=17, alignment=TA_CENTER,
            textColor=WARNA_TINTA, spaceAfter=0,
        ),
        "kop_besar": ParagraphStyle(
            "kop_besar", fontName=FONT_BOLD, fontSize=18, leading=22, alignment=TA_CENTER,
            textColor=WARNA_TINTA, spaceAfter=0,
        ),
        "kop_kecil": ParagraphStyle(
            "kop_kecil", fontName=FONT, fontSize=10, leading=13, alignment=TA_CENTER,
            textColor=WARNA_TINTA, spaceBefore=2,
        ),
        "judul": ParagraphStyle(
            "judul", fontName=FONT_BOLD, fontSize=12.5, leading=16, alignment=TA_CENTER,
            spaceBefore=6, spaceAfter=2,
        ),
        "nomor": ParagraphStyle(
            "nomor", fontName=FONT, fontSize=11, leading=14, alignment=TA_CENTER,
            spaceAfter=10,
        ),
        "isi": ParagraphStyle(
            "isi", fontName=FONT, fontSize=11, leading=15.5, alignment=TA_JUSTIFY,
            spaceAfter=6, textColor=WARNA_TINTA,
        ),
        "kiri": ParagraphStyle(
            "kiri", fontName=FONT, fontSize=11, leading=15.5, alignment=TA_LEFT,
            spaceAfter=4, textColor=WARNA_TINTA,
        ),
        "sel": ParagraphStyle(
            "sel", fontName=FONT, fontSize=11, leading=14.5, alignment=TA_LEFT,
        ),
        "sel_label": ParagraphStyle(
            "sel_label", fontName=FONT, fontSize=11, leading=14.5, alignment=TA_LEFT,
        ),
        "ttd": ParagraphStyle(
            "ttd", fontName=FONT, fontSize=11, leading=14, alignment=TA_CENTER,
        ),
        "ttd_nama": ParagraphStyle(
            "ttd_nama", fontName=FONT_BOLD, fontSize=11, leading=14, alignment=TA_CENTER,
        ),
        "kecil": ParagraphStyle(
            "kecil", fontName=FONT, fontSize=7.5, leading=9.5, alignment=TA_CENTER,
            textColor=WARNA_ABU,
        ),
        "watermark": ParagraphStyle(
            "watermark", fontName=FONT_BOLD, fontSize=52, leading=60, alignment=TA_CENTER,
            textColor=colors.HexColor("#E5E7EB"),
        ),
    }


def _esc(teks: Any) -> str:
    """Escape untuk Paragraph ReportLab (XML-like)."""
    if teks is None:
        return "-"
    s = str(teks)
    return s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


# --------------------------------------------------------------------------- #
# Pemformatan nilai
# --------------------------------------------------------------------------- #
def tanggal_panjang(nilai: Any) -> str:
    if not nilai:
        return "-"
    if isinstance(nilai, str):
        try:
            nilai = date.fromisoformat(nilai)
        except ValueError:
            return nilai
    if isinstance(nilai, datetime):
        nilai = nilai.date()
    return f"{nilai.day:02d} {BULAN[nilai.month]} {nilai.year}"


def rupiah(nilai: Any) -> str:
    if nilai in (None, ""):
        return "-"
    teks = str(nilai).replace("Rp", "").replace(".", "").replace(",", "").strip()
    if not teks.isdigit():
        return str(nilai)
    return f"{int(teks):,}".replace(",", ".")


def _setting(db: Session, kunci: str, bawaan: str = "") -> str:
    row = db.execute(select(Setting).where(Setting.kunci == kunci)).scalar_one_or_none()
    return row.nilai if row else bawaan


def pejabat_untuk(db: Session, service_kode: str) -> tuple[Official | None, Official | None]:
    """Kembalikan (penanda tangan, saksi) aktif yang masa berlakunya belum habis."""
    jabatan_ttd = _setting(db, f"penandatangan_{service_kode}", "Kepala Desa")
    jabatan_saksi = _setting(db, f"saksi_{service_kode}", "")
    ttd = cari_pejabat(db, jabatan_ttd)
    saksi = cari_pejabat(db, jabatan_saksi) if jabatan_saksi else None
    return ttd, saksi


def cari_pejabat(db: Session, jabatan: str) -> Official | None:
    """Pejabat aktif untuk jabatan tertentu, atau None bila kosong/kedaluwarsa."""
    if not jabatan:
        return None
    hari_ini = datetime.now(timezone.utc).date()
    return db.execute(
        select(Official).where(
            Official.jabatan == jabatan,
            Official.aktif.is_(True),
            or_(Official.berlaku_sampai.is_(None), Official.berlaku_sampai >= hari_ini),
        )
    ).scalar_one_or_none()


def path_ttd(official: Official | None) -> Path | None:
    """Lokasi berkas scan tanda tangan, bila ada dan masih tersimpan."""
    if official is None or not official.ttd_path:
        return None
    path = Path(official.ttd_path)
    if not path.is_absolute():
        path = settings.storage_path / path
    return path if path.is_file() else None


def logo_kop(db: Session) -> Path | None:
    """Logo pada kop surat: pengaturan `logo_kop`, atau logo kabupaten bawaan."""
    nilai = _setting(db, "logo_kop", "").strip()
    if nilai:
        path = Path(nilai)
        if not path.is_absolute():
            path = settings.storage_path / path
        if path.is_file():
            return path
    return LOGO_BAWAAN if LOGO_BAWAAN.is_file() else None


def _konteks(
    db: Session, app: Application, nomor: str, ttd: Official | None
) -> dict[str, str]:
    data = dict(app.form_data or {})
    citizen = app.citizen

    def ambil(kunci: str) -> str:
        nilai = data.get(kunci)
        if (nilai is None or nilai == "") and citizen is not None:
            nilai = getattr(citizen, kunci, None)
        return str(nilai) if nilai not in (None, "") else "-"

    dusun = ambil("dusun")
    alamat = ambil("alamat")
    if dusun != "-" and dusun.lower() not in alamat.lower():
        alamat_penuh = f"Dusun {dusun} Desa Kampala Kecamatan Arungkeke Kabupaten Jeneponto"
    elif alamat != "-":
        alamat_penuh = f"{alamat} Desa Kampala Kecamatan Arungkeke Kabupaten Jeneponto"
    else:
        alamat_penuh = "Desa Kampala Kecamatan Arungkeke Kabupaten Jeneponto"

    return {
        "nomor_surat": nomor,
        "nama_lengkap": ambil("nama_lengkap"),
        "nik": ambil("nik"),
        "tempat_lahir": ambil("tempat_lahir"),
        "tanggal_lahir": ambil("tanggal_lahir"),
        "tanggal_lahir_panjang": tanggal_panjang(
            data.get("tanggal_lahir")
            or (citizen.tanggal_lahir if citizen is not None else None)
        ),
        "jenis_kelamin": ambil("jenis_kelamin"),
        "status_perkawinan": ambil("status_perkawinan"),
        "agama": ambil("agama"),
        "pekerjaan": ambil("pekerjaan"),
        "alamat": alamat,
        "dusun": dusun,
        "rt": ambil("rt"),
        "rw": ambil("rw"),
        "no_hp": ambil("no_hp"),
        "alamat_penuh": alamat_penuh,
        "keperluan": ambil("keperluan"),
        "penghasilan_bulanan": rupiah(data.get("penghasilan_bulanan")),
        "jumlah_tanggungan": ambil("jumlah_tanggungan"),
        "nama_usaha": ambil("nama_usaha"),
        "jenis_usaha": ambil("jenis_usaha"),
        "alamat_usaha": ambil("alamat_usaha"),
        "bentuk_usaha": ambil("bentuk_usaha"),
        "modal_usaha": rupiah(data.get("modal_usaha")),
        "tahun_mulai": ambil("tahun_mulai"),
        "tujuan_instansi": ambil("tujuan_instansi"),
        "pejabat_nama": ttd.nama if ttd else "-",
        "pejabat_jabatan": ttd.jabatan if ttd else "-",
        "tanggal_surat": tanggal_panjang(datetime.now(timezone.utc)),
    }


# --------------------------------------------------------------------------- #
# QR
# --------------------------------------------------------------------------- #
def qr_png(url: str, *, ukuran_cm: float = 2.6) -> Image:
    """QR 2,6 cm — FR-27 mewajibkan minimal 2,5 × 2,5 cm."""
    qr = qrcode.QRCode(version=None, error_correction=qrcode.constants.ERROR_CORRECT_M, box_size=8, border=2)
    qr.add_data(url)
    qr.make(fit=True)
    gambar = qr.make_image(fill_color="black", back_color="white")
    buffer = io.BytesIO()
    gambar.save(buffer, format="PNG")
    buffer.seek(0)
    sisi = ukuran_cm * cm
    return Image(buffer, width=sisi, height=sisi)


# --------------------------------------------------------------------------- #
# Perakitan cerita
# --------------------------------------------------------------------------- #
def _kop_flowables(db: Session) -> list[Any]:
    """Kop surat resmi: logo kabupaten di kiri, tiga baris instansi di tengah."""
    kab = _setting(db, "nama_kabupaten", "Jeneponto").upper()
    kec = _setting(db, "nama_kecamatan", "Arungkeke").upper()
    desa = _setting(db, "nama_desa", "Kampala").upper()
    alamat = _setting(db, "alamat_kantor", "")
    st = _styles()

    teks: list[Any] = [
        Paragraph(f"PEMERINTAH KABUPATEN {_esc(kab)}", st["kop"]),
        Paragraph(f"KECAMATAN {_esc(kec)}", st["kop"]),
        Paragraph(f"DESA {_esc(desa)}", st["kop_besar"]),
    ]
    if alamat:
        teks.append(Paragraph(_esc(alamat), st["kop_kecil"]))

    logo = logo_kop(db)
    if logo is not None:
        sisi = 2.1 * cm
        kepala: list[Any] = [
            Table(
                [
                    [
                        Image(str(logo), width=sisi, height=sisi, kind="proportional"),
                        teks,
                        "",
                    ]
                ],
                colWidths=[sisi + 0.5 * cm, CONTENT_W - 2 * (sisi + 0.5 * cm), sisi + 0.5 * cm],
                style=TableStyle(
                    [
                        ("VALIGN", (0, 0), (0, 0), "MIDDLE"),
                        ("VALIGN", (1, 0), (1, 0), "MIDDLE"),
                        ("LEFTPADDING", (0, 0), (-1, -1), 0),
                        ("RIGHTPADDING", (0, 0), (-1, -1), 0),
                        ("TOPPADDING", (0, 0), (-1, -1), 0),
                        ("BOTTOMPADDING", (0, 0), (-1, -1), 0),
                    ]
                ),
            )
        ]
    else:
        kepala = teks

    kepala.append(Spacer(1, 4))
    kepala.append(HRFlowable(width="100%", thickness=1.6, color=WARNA_GARIS, spaceAfter=2))
    kepala.append(HRFlowable(width="100%", thickness=0.6, color=WARNA_GARIS, spaceBefore=1))
    return kepala


def _baris_tabel(baris: list[tuple[str, str]]) -> Table:
    st = _styles()
    # Kolom kosong pertama meniru indentasi format surat resmi (±0,8 cm).
    data = [
        [
            "",
            Paragraph(_esc(label), st["sel_label"]),
            Paragraph(":", st["sel"]),
            Paragraph(nilai, st["sel"]),
        ]
        for label, nilai in baris
    ]
    lebar_label = 4.2 * cm
    tabel = Table(data, colWidths=[0.8 * cm, lebar_label, 0.35 * cm, CONTENT_W - 0.8 * cm - lebar_label - 0.35 * cm])
    tabel.setStyle(
        TableStyle(
            [
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("LEFTPADDING", (0, 0), (-1, -1), 0),
                ("RIGHTPADDING", (0, 0), (-1, -1), 2),
                ("TOPPADDING", (0, 0), (-1, -1), 0.5),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 0.5),
            ]
        )
    )
    return tabel


def _blok_isi(konten: str) -> list[Any]:
    st = _styles()
    hasil: list[Any] = []
    buffer_baris: list[tuple[str, str]] = []

    def _flush() -> None:
        nonlocal buffer_baris
        if buffer_baris:
            hasil.append(_baris_tabel(buffer_baris))
            hasil.append(Spacer(1, 6))
            buffer_baris = []

    for mentah in konten.splitlines():
        baris = mentah.strip()
        if not baris:
            _flush()
            continue
        if baris.startswith("#JUDUL#"):
            _flush()
            judul = baris.replace("#JUDUL#", "").strip()
            hasil.append(Paragraph(f"<b><u>{_esc(judul)}</u></b>", st["judul"]))
            continue
        if baris.startswith("#PEMEGANG#"):
            # Penanda blok tanda tangan "Pemegang Surat"; tidak dicetak di badan surat.
            continue
        if baris.startswith("|"):
            bagian = [b.strip() for b in baris.strip("|").split("|")]
            if len(bagian) >= 2:
                label = bagian[0]
                nilai = bagian[1]
                buffer_baris.append((label, _esc(nilai)))
            continue
        _flush()
        hasil.append(Paragraph(_esc(baris), st["isi"]))
    _flush()
    return hasil


def _ruang_ttd(official: Official | None, tinggi: float) -> list[Any]:
    """Ruang tanda tangan: scan TTD bila ada, selain itu ruang kosong.

    Tinggi blok selalu sama (`tinggi` pt) agar nama penanda tangan tidak
    bergeser naik-turun antar surat, dan gambar tidak menimpa baris di atasnya.
    """
    berkas = path_ttd(official)
    if berkas is None:
        return [Spacer(1, tinggi)]

    lebar_maks = 3.4 * cm
    lebar_px, tinggi_px = ImageReader(str(berkas)).getSize()
    skala = min(lebar_maks / lebar_px, (tinggi - 8) / tinggi_px)
    lebar, gambar_tinggi = lebar_px * skala, tinggi_px * skala
    return [
        Spacer(1, max(0.0, tinggi - gambar_tinggi - 4)),
        Image(str(berkas), width=lebar, height=gambar_tinggi, hAlign="CENTER"),
        Spacer(1, 4),
    ]


def _blok_ttd(
    db: Session,
    *,
    ttd: Official | None,
    saksi: Official | None,
    pemegang: str | None,
    tanggal: str,
    qr_url: str | None,
) -> Any:
    st = _styles()
    desa = _setting(db, "nama_desa", "Kampala")

    # QR berdiri sebagai kolom sendiri di kanan blok tanda tangan. Kalau QR
    # ditumpuk di bawah nama, tinggi blok bertambah dan surat berisi banyak
    # baris (mis. SKTM) terdorong ke halaman kedua.
    qr_flow: list[Any] | None = None
    if qr_url:
        qr_flow = [
            qr_png(qr_url, ukuran_cm=2.5),
            Spacer(1, 2),
            Paragraph("Pindai untuk verifikasi", st["kecil"]),
        ]

    jabatan = ttd.jabatan if ttd else "Kepala Desa"
    tinggi = 44.0

    # --- kolom kanan: hanya Kepala Desa atau Sekretaris Desa yang menandatangani
    kanan_atas: list[Any] = [
        Paragraph(f"{_esc(desa)}, {_esc(tanggal)}", st["ttd"]),
        Paragraph("Mengetahui :", st["ttd"]),
    ]
    if jabatan.lower().startswith("kepala desa"):
        # Kepala desa menandatangani langsung — tanpa baris "a/n".
        kanan_atas.append(Paragraph(f"Kepala Desa {_esc(desa)}", st["ttd"]))
    else:
        kanan_atas.extend(
            [
                Paragraph(f"a/n Kepala Desa {_esc(desa)}", st["ttd"]),
                Paragraph(f"({_esc(jabatan)})", st["ttd"]),
            ]
        )

    # --- kolom kiri: pemegang surat (USH) atau saksi (DOM/SKTM)
    kiri_atas: list[Any] = []
    if pemegang:
        kiri_atas = [Paragraph("<b>Pemegang Surat</b>", st["ttd"])]
    elif saksi is not None:
        kiri_atas = [
            Paragraph("<b>Menyaksikan :</b>", st["ttd"]),
            Paragraph(_esc(saksi.jabatan), st["ttd"]),
        ]

    # Sejajarkan nama kiri & kanan: kolom yang lebih pendek diberi ruang kosong.
    baris_ttd = 14.0
    selisih = len(kanan_atas) - len(kiri_atas)
    kiri: list[Any] = [*kiri_atas, Spacer(1, max(0.0, selisih) * baris_ttd)]
    kanan: list[Any] = [*kanan_atas, Spacer(1, max(0.0, -selisih) * baris_ttd)]

    if pemegang:
        kiri.extend(
            [
                Spacer(1, tinggi),
                Paragraph(f"<b><u>{_esc(pemegang)}</u></b>", st["ttd_nama"]),
            ]
        )
    elif saksi is not None:
        kiri.extend(
            [
                *_ruang_ttd(saksi, tinggi),
                Paragraph(f"<b><u>{_esc(saksi.nama)}</u></b>", st["ttd_nama"]),
            ]
        )
    kanan.extend(
        [
            *_ruang_ttd(ttd, tinggi),
            Paragraph(f"<b><u>{_esc(ttd.nama if ttd else '...')}</u></b>", st["ttd_nama"]),
        ]
    )
    if qr_flow:
        data = [[kiri, kanan, qr_flow]]
        lebar = [6.3 * cm, 6.3 * cm, 2.6 * cm]
    else:
        data = [[kiri, kanan]]
        lebar = [7.4 * cm, 7.4 * cm]

    tabel = Table(data, colWidths=lebar)
    tabel.setStyle(
        TableStyle(
            [
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("ALIGN", (0, 0), (-1, -1), "CENTER"),
                ("LEFTPADDING", (0, 0), (-1, -1), 0),
                ("RIGHTPADDING", (0, 0), (-1, -1), 0),
                ("TOPPADDING", (0, 0), (-1, -1), 0),
            ]
        )
    )
    return tabel


def _footer(canvas, doc, teks: str) -> None:
    canvas.saveState()
    canvas.setFont(FONT, 7.5)
    canvas.setFillColor(WARNA_ABU)
    canvas.drawCentredString(A4[0] / 2, 1.15 * cm, teks)
    canvas.restoreState()


def _watermark(canvas, doc, teks: str) -> None:
    canvas.saveState()
    canvas.setFont(FONT_BOLD, 54)
    canvas.setFillColor(colors.HexColor("#EEF2F7"))
    canvas.translate(A4[0] / 2, A4[1] / 2)
    canvas.rotate(35)
    canvas.drawCentredString(0, 0, teks)
    canvas.restoreState()


# --------------------------------------------------------------------------- #
# Render
# --------------------------------------------------------------------------- #
def _pisah_judul(konten: str) -> tuple[str, str]:
    """Ambil baris `#JUDUL#` dari template agar bisa dicetak sebelum nomor surat."""
    baris = konten.splitlines()
    for i, b in enumerate(baris):
        if b.strip().startswith("#JUDUL#"):
            judul = b.strip().replace("#JUDUL#", "").strip()
            return judul, "\n".join(baris[:i] + baris[i + 1 :])
    return "", konten


def render_pdf(
    db: Session,
    app: Application,
    *,
    template: LetterTemplate,
    nomor_surat: str,
    qr_url: str | None = None,
    draf: bool = False,
) -> bytes:
    service: Service = app.service
    ttd, saksi = pejabat_untuk(db, service.kode)
    konteks = _konteks(db, app, nomor_surat, ttd)

    konten = template.konten_html.format(**{k: v for k, v in konteks.items()})
    pemegang = konteks["nama_lengkap"] if "#PEMEGANG#" in konten else None
    judul, isi = _pisah_judul(konten)
    st = _styles()

    cerita: list[Any] = []
    cerita.extend(_kop_flowables(db))
    cerita.append(Spacer(1, 8))
    if judul:
        cerita.append(Paragraph(f"<b><u>{_esc(judul)}</u></b>", st["judul"]))
    cerita.append(Paragraph(f"NO : {_esc(nomor_surat)}", st["nomor"]))
    cerita.extend(_blok_isi(isi))
    cerita.append(Spacer(1, 12))
    cerita.append(
        KeepTogether(
            _blok_ttd(
                db,
                ttd=ttd,
                saksi=saksi,
                pemegang=pemegang,
                tanggal=konteks["tanggal_surat"],
                qr_url=qr_url,
            )
        )
    )

    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        leftMargin=MARGIN_KIRI,
        rightMargin=MARGIN_KANAN,
        topMargin=MARGIN_ATAS,
        bottomMargin=MARGIN_BAWAH,
        title=f"{service.nama} - {konteks['nama_lengkap']}",
        author="Pemerintah Desa Kampala",
        subject=service.nama,
    )

    catatan = (
        "Dokumen ini dicetak dari SILADESA dan sah tanpa tanda tangan basah."
        if not draf
        else "DRAF — dokumen ini belum terbit dan tidak sah untuk digunakan."
    )
    if qr_url:
        catatan += f" Verifikasi: {qr_url}"

    def _on_page(canvas, doc_):
        if draf:
            _watermark(canvas, doc_, "DRAF")
        _footer(canvas, doc_, catatan)

    doc.build(cerita, onFirstPage=_on_page, onLaterPages=_on_page)
    return buffer.getvalue()


def buat_dokumen_draf(db: Session, app: Application, template: LetterTemplate) -> bytes:
    """Pratinjau sebelum nomor surat dipakai (tidak menaikkan counter)."""
    from app.services.numbering import peek_letter_number

    nomor = peek_letter_number(db)
    return render_pdf(db, app, template=template, nomor_surat=nomor, draf=True)


def simpan_dokumen(
    db: Session,
    app: Application,
    *,
    template: LetterTemplate,
    nomor_surat: str,
    qr_token: str,
    aktor_id: int | None,
) -> Document:
    url_verifikasi = f"{settings.app_url.rstrip('/')}/v/{qr_token}"
    isi_pdf = render_pdf(
        db, app, template=template, nomor_surat=nomor_surat, qr_url=url_verifikasi
    )

    folder = settings.storage_path / "documents" / str(datetime.now(timezone.utc).year)
    folder.mkdir(parents=True, exist_ok=True)
    # Nama berkas memuat nomor surat: nomor surat unik, sehingga penerbitan
    # ganda tidak saling menimpa PDF di disk.
    nama_file = f"{app.ticket_no}_{nomor_surat.replace('/', '-')}.pdf"
    path = folder / nama_file
    path.write_bytes(isi_pdf)

    dokumen = Document(
        application_id=app.id,
        template_id=template.id,
        nomor_surat=nomor_surat,
        file_path=str(path.relative_to(settings.storage_path)),
        sha256=hashlib.sha256(isi_pdf).hexdigest(),
        qr_token=qr_token,
        status="TERBIT",
        issued_by=aktor_id,
        issued_at=datetime.now(timezone.utc),
    )
    db.add(dokumen)
    db.flush()
    return dokumen


def template_aktif(db: Session, service_id: int) -> LetterTemplate | None:
    return db.execute(
        select(LetterTemplate)
        .where(LetterTemplate.service_id == service_id, LetterTemplate.aktif.is_(True))
        .order_by(LetterTemplate.versi.desc())
    ).scalars().first()


def path_dokumen(dokumen: Document) -> Path:
    return settings.storage_path / dokumen.file_path


def token_baru() -> str:
    """Token QR 256-bit (jauh di atas syarat minimum 128-bit)."""
    return secrets.token_urlsafe(32)
