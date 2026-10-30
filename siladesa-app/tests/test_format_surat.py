"""Format surat resmi: kop berlogo, judul di atas nomor, dan penanda tangan sah."""

from __future__ import annotations

import base64
import re
import zlib

from sqlalchemy import select

from conftest import buat_pengajuan_domisili, csrf_dari, id_pengajuan, masuk, nik_unik

FORM = {
    "nama_lengkap": "RESKI ADITYA",
    "nik": "7304091506980003",
    "tempat_lahir": "Kampala",
    "tanggal_lahir": "1998-06-15",
    "jenis_kelamin": "Laki-laki",
    "status_perkawinan": "Belum Kawin",
    "agama": "Islam",
    "pekerjaan": "Petani/Pekebun",
    "dusun": "Kalukuang",
    "rt": "002",
    "rw": "001",
    "no_hp": "081234567890",
    "alamat": "Dusun Kalukuang",
    "keperluan": "Kelengkapan berkas pendaftaran kerja",
    "penghasilan_bulanan": "1200000",
    "jumlah_tanggungan": "4",
    "nama_usaha": "UD. Karsut",
    "jenis_usaha": "Jual Beli Beras",
    "alamat_usaha": "Dusun Sepeka Desa Kampala",
    "bentuk_usaha": "Milik Sendiri",
    "modal_usaha": "50000000",
    "tahun_mulai": "2021",
    "tujuan_instansi": "Kantor Camat Arungkeke",
}


def _teks_pdf(data: bytes) -> str:
    """Baca teks dari stream PDF (ReportLab memakai ASCII85 + Flate)."""
    potongan: list[str] = []
    for cocok in re.finditer(rb"stream\r?\n(.*?)endstream", data, re.S):
        mentah = cocok.group(1).strip()
        for olah in (
            lambda b: zlib.decompress(b),
            lambda b: zlib.decompress(base64.a85decode(b, adobe=True)),
        ):
            try:
                potongan.append(olah(mentah).decode("latin-1"))
                break
            except (ValueError, zlib.error):
                continue
    return "\n".join(potongan)


def _render(kode: str) -> bytes:
    from app.db import SessionLocal
    from app.models import Application, Service
    from app.services import documents as docsvc

    with SessionLocal() as db:
        layanan = db.execute(select(Service).where(Service.kode == kode)).scalar_one()
        template = docsvc.template_aktif(db, layanan.id)
        assert template is not None
        pengajuan = Application(
            service_id=layanan.id,
            ticket_no=f"UJI-{kode}",
            status="DRAFT",
            form_data=dict(FORM),
        )
        pengajuan.service = layanan
        return docsvc.buat_dokumen_draf(db, pengajuan, template)


def test_judul_dicetak_sebelum_nomor(seeded):
    teks = _teks_pdf(_render("USH"))
    judul = teks.index("SURAT KETERANGAN USAHA")
    nomor = teks.index("NO :")
    assert judul < nomor


def test_kop_memuat_logo_kabupaten(seeded):
    from app.db import SessionLocal
    from app.services import documents as docsvc

    with SessionLocal() as db:
        logo = docsvc.logo_kop(db)
    assert logo is not None and logo.is_file()
    # Objek gambar ikut tertulis pada PDF pratinjau.
    assert b"/Subtype /Image" in _render("DOM")


def test_pemegang_surat_hanya_pada_surat_usaha(seeded):
    assert "Pemegang Surat" in _teks_pdf(_render("USH"))
    assert "Pemegang Surat" not in _teks_pdf(_render("DOM"))


def test_sekdes_menandatangani_atas_nama_kepala_desa(seeded):
    teks = _teks_pdf(_render("DOM"))
    assert "a/n Kepala Desa Kampala" in teks
    # Tanda kurung di-escape ReportLab di dalam stream PDF.
    assert re.search(r"\\?\(Sekretaris Desa\\?\)", teks)
    assert "Menyaksikan" in teks


def test_kepala_desa_menandatangani_langsung(seeded):
    teks = _teks_pdf(_render("SKTM"))
    assert "Kepala Desa Kampala" in teks
    assert "a/n Kepala Desa" not in teks
    assert not re.search(r"\\?\(Sekretaris Desa\\?\)", teks)


def test_pengantar_ditandatangani_sekdes_dengan_saksi_kapolsek(seeded):
    teks = _teks_pdf(_render("PGG"))
    assert "SURAT PENGANTAR" in teks
    assert "a/n Kepala Desa Kampala" in teks
    assert "Menyaksikan" in teks
    assert "Kapolsek Arungkeke" in teks


def test_surat_dengan_qr_tetap_satu_halaman(seeded):
    """QR diletakkan di kolom ketiga; blok TTD tidak boleh pecah ke halaman 2."""
    from app.db import SessionLocal
    from app.models import Application, Service
    from app.services import documents as docsvc

    with SessionLocal() as db:
        layanan = db.execute(select(Service).where(Service.kode == "SKTM")).scalar_one()
        template = docsvc.template_aktif(db, layanan.id)
        pengajuan = Application(
            service_id=layanan.id,
            ticket_no="UJI-SKTM-QR",
            status="DRAFT",
            form_data=dict(FORM),
        )
        pengajuan.service = layanan
        pdf = docsvc.render_pdf(
            db,
            pengajuan,
            template=template,
            nomor_surat="999/DKP/X/2026",
            qr_url="http://contoh.test/v/token",
        )

    halaman = pdf.count(b"/Type /Page") - pdf.count(b"/Type /Pages")
    assert halaman == 1


def test_pengaturan_menolak_penanda_tangan_bukan_kepala_desa_atau_sekdes(client):
    from app.db import SessionLocal
    from app.models import Setting

    masuk(client, "admin")
    csrf = csrf_dari(client.get("/admin/pengaturan").text)
    with SessionLocal() as db:
        row = db.execute(
            select(Setting).where(Setting.kunci == "penandatangan_DOM")
        ).scalar_one()
        sid, awal = row.id, row.nilai

    r = client.post(
        "/admin/pengaturan",
        data={"csrf": csrf, f"nilai_{sid}": "Kapolsek Arungkeke"},
    )
    assert r.status_code == 303
    assert "err" in r.headers["location"]

    with SessionLocal() as db:
        assert db.get(Setting, sid).nilai == awal


def test_terbitkan_menolak_penanda_tangan_bukan_kepala_desa_atau_sekdes(client):
    from app import constants as C
    from app.db import SessionLocal
    from app.models import Application, Setting

    tiket = buat_pengajuan_domisili(client, nik_unik())
    masuk(client, "operator")
    app_id = id_pengajuan(client, tiket)
    csrf = csrf_dari(client.get(f"/admin/pengajuan/{app_id}").text)
    r = client.post(
        f"/admin/pengajuan/{app_id}/status",
        data={"csrf": csrf, "ke": C.Status.DIPROSES.value, "catatan": "berkas lengkap"},
    )
    assert r.status_code == 303

    with SessionLocal() as db:
        row = db.execute(
            select(Setting).where(Setting.kunci == "penandatangan_DOM")
        ).scalar_one()
        sid, awal = row.id, row.nilai
        row.nilai = "Kapolsek Arungkeke"
        db.commit()

    try:
        masuk(client, "sekdes")
        csrf = csrf_dari(client.get(f"/admin/pengajuan/{app_id}").text)
        r = client.post(f"/admin/pengajuan/{app_id}/terbitkan", data={"csrf": csrf})
        assert r.status_code == 303
        assert "err" in r.headers["location"]
        assert "penanda" in r.headers["location"].lower()

        with SessionLocal() as db:
            assert db.get(Application, app_id).status == C.Status.DIPROSES.value
    finally:
        with SessionLocal() as db:
            db.get(Setting, sid).nilai = awal
            db.commit()
