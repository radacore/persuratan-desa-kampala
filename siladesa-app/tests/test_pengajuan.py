"""Alur pengajuan: verifikasi, penerbitan PDF, unduh, verifikasi QR, pencabutan."""

from __future__ import annotations

import re

from conftest import buat_pengajuan_domisili, csrf_dari, id_pengajuan, masuk, nik_unik

NOMOR_RE = re.compile(r"\d{3}/DKP/[IVX]+/\d{4}")


def test_alur_terbit_sampai_cabut(client):
    tiket = buat_pengajuan_domisili(client, nik_unik())

    # --- operator memverifikasi
    masuk(client, "operator")
    app_id = id_pengajuan(client, tiket)
    halaman = client.get(f"/admin/pengajuan/{app_id}")
    assert halaman.status_code == 200
    assert "RESKI ADITYA" in halaman.text
    csrf = csrf_dari(halaman.text)

    r = client.post(
        f"/admin/pengajuan/{app_id}/status",
        data={"csrf": csrf, "ke": "DIPROSES", "catatan": "Berkas lengkap."},
    )
    assert r.status_code == 303 and "err" not in r.headers["location"]
    assert "Diproses" in client.get(f"/admin/pengajuan/{app_id}").text

    # operator tidak berhak menerbitkan
    r = client.post(f"/admin/pengajuan/{app_id}/terbitkan", data={"csrf": csrf})
    assert r.status_code == 403

    # --- sekdes menerbitkan
    masuk(client, "sekdes")
    halaman = client.get(f"/admin/pengajuan/{app_id}")
    csrf = csrf_dari(halaman.text)
    r = client.post(f"/admin/pengajuan/{app_id}/terbitkan", data={"csrf": csrf})
    assert r.status_code == 303 and "err" not in r.headers["location"], r.headers["location"]

    halaman = client.get(f"/admin/pengajuan/{app_id}")
    assert "Terbit" in halaman.text
    nomor = NOMOR_RE.search(halaman.text)
    assert nomor, "nomor surat tidak berformat {seq}/DKP/{bulan}/{tahun}"
    assert nomor.group(0).split("/")[1] == "DKP"

    # --- unduh PDF
    tautan = re.search(r'href="(/d/[^"]+)"', halaman.text)
    assert tautan, "tautan unduh tidak muncul"
    pdf = client.get(tautan.group(1))
    assert pdf.status_code == 200
    assert pdf.headers["content-type"] == "application/pdf"
    assert pdf.content.startswith(b"%PDF")

    # --- verifikasi QR
    qr = re.search(r'href="/v/([A-Za-z0-9_\-]+)"', halaman.text)
    assert qr, "tautan verifikasi tidak muncul"
    verif = client.get(f"/v/{qr.group(1)}")
    assert verif.status_code == 200
    assert "RESKI ADITYA" in verif.text
    # NIK tidak boleh tampil utuh
    assert "7304" not in verif.text or "****" in verif.text

    # --- sekdes tidak boleh mencabut
    r = client.post(
        f"/admin/pengajuan/{app_id}/cabut",
        data={"csrf": csrf, "alasan": "salah input"},
    )
    assert r.status_code == 403

    # --- kepala desa mencabut
    masuk(client, "kepala_desa")
    halaman = client.get(f"/admin/pengajuan/{app_id}")
    csrf = csrf_dari(halaman.text)
    r = client.post(
        f"/admin/pengajuan/{app_id}/cabut",
        data={"csrf": csrf, "alasan": "Uji pencabutan dokumen."},
    )
    assert r.status_code == 303 and "err" not in r.headers["location"]

    verif = client.get(f"/v/{qr.group(1)}")
    assert "DIBATALKAN" in verif.text.upper()

    # tautan unduh lama tidak lagi menyajikan berkas
    assert client.get(tautan.group(1)).status_code == 410


def test_transisi_tidak_sah_ditolak(client):
    tiket = buat_pengajuan_domisili(client, nik_unik())
    masuk(client, "sekdes")
    app_id = id_pengajuan(client, tiket)
    csrf = csrf_dari(client.get(f"/admin/pengajuan/{app_id}").text)

    # MENUNGGU_VERIFIKASI -> TERBIT melompati DIPROSES
    r = client.post(
        f"/admin/pengajuan/{app_id}/status", data={"csrf": csrf, "ke": "TERBIT"}
    )
    assert r.status_code == 303
    assert "err" in r.headers["location"]
    assert "Menunggu verifikasi" in client.get(f"/admin/pengajuan/{app_id}").text


def test_terbit_tidak_bisa_lewat_form_status(client):
    """TERBIT hanya lewat tombol Terbitkan: form status tidak boleh membuat surat tanpa PDF."""
    from sqlalchemy import select

    from app.db import SessionLocal
    from app.models import Document

    tiket = buat_pengajuan_domisili(client, nik_unik())

    masuk(client, "operator")
    app_id = id_pengajuan(client, tiket)
    csrf = csrf_dari(client.get(f"/admin/pengajuan/{app_id}").text)
    client.post(
        f"/admin/pengajuan/{app_id}/status",
        data={"csrf": csrf, "ke": "DIPROSES", "catatan": "Berkas lengkap."},
    )

    masuk(client, "sekdes")
    halaman = client.get(f"/admin/pengajuan/{app_id}")
    assert 'value="TERBIT"' not in halaman.text, "Terbit tidak boleh muncul di dropdown status"

    csrf = csrf_dari(halaman.text)
    r = client.post(f"/admin/pengajuan/{app_id}/status", data={"csrf": csrf, "ke": "TERBIT"})
    assert r.status_code == 303
    assert "err" in r.headers["location"]

    assert "Diproses" in client.get(f"/admin/pengajuan/{app_id}").text
    with SessionLocal() as db:
        dokumen = db.execute(
            select(Document).where(Document.application_id == app_id)
        ).scalars().all()
        assert dokumen == [], "status Terbit tidak boleh ada tanpa dokumen"


def test_penerbitan_butuh_status_diproses(client):
    tiket = buat_pengajuan_domisili(client, nik_unik())
    masuk(client, "sekdes")
    app_id = id_pengajuan(client, tiket)
    csrf = csrf_dari(client.get(f"/admin/pengajuan/{app_id}").text)
    r = client.post(f"/admin/pengajuan/{app_id}/terbitkan", data={"csrf": csrf})
    assert r.status_code == 303
    assert "err" in r.headers["location"]


def test_laporan_csv(client):
    masuk(client, "sekdes")
    r = client.get("/admin/laporan.csv")
    assert r.status_code == 200
    assert r.headers["content-type"].startswith("text/csv")
    assert r.content.startswith("\ufeff".encode("utf-8"))
    assert ";" in r.text.splitlines()[0]


def test_tautan_unduh_masuk_ke_chat_setelah_terbit(client):
    """FR-20: warga menerima tautan PDF di percakapan, bukan hanya push kanal."""
    from sqlalchemy import select

    from app.db import SessionLocal
    from app.models import Application, ChatMessage, ConversationSession, Document

    tiket = buat_pengajuan_domisili(client, nik_unik())

    masuk(client, "operator")
    app_id = id_pengajuan(client, tiket)
    csrf = csrf_dari(client.get(f"/admin/pengajuan/{app_id}").text)
    client.post(
        f"/admin/pengajuan/{app_id}/status",
        data={"csrf": csrf, "ke": "DIPROSES", "catatan": "Berkas lengkap."},
    )

    masuk(client, "sekdes")
    csrf = csrf_dari(client.get(f"/admin/pengajuan/{app_id}").text)
    r = client.post(f"/admin/pengajuan/{app_id}/terbitkan", data={"csrf": csrf})
    assert r.status_code == 303 and "err" not in r.headers["location"]

    with SessionLocal() as db:
        pengajuan = db.get(Application, app_id)
        assert pengajuan is not None and pengajuan.session_id
        sesi = db.get(ConversationSession, pengajuan.session_id)
        assert sesi is not None, "sesi percakapan asal pengajuan tidak ditemukan"
        pesan = db.execute(
            select(ChatMessage)
            .where(ChatMessage.session_id == sesi.id, ChatMessage.arah == "out")
            .order_by(ChatMessage.id.desc())
        ).scalars().first()
        assert pesan is not None
        assert "/d/" in pesan.isi
        assert NOMOR_RE.search(pesan.isi), "nomor surat tidak ikut pada pesan terbit"

        # Waktu pengiriman tercatat pada DOCUMENT (FR-20).
        dokumen = db.execute(
            select(Document).where(Document.application_id == app_id)
        ).scalar_one()
        assert dokumen.sent_at is not None

        # Catatan verifikasi operator tidak boleh tertimpa catatan penerbitan.
        assert pengajuan.catatan_operator == "Berkas lengkap."


def test_status_ditolak_masuk_ke_chat_warga(client):
    """Penolakan + alasan wajib terlihat di percakapan (bukan cuma push kanal)."""
    from sqlalchemy import select

    from app.db import SessionLocal
    from app.models import Application, ChatMessage, ConversationSession

    tiket = buat_pengajuan_domisili(client, nik_unik())

    masuk(client, "operator")
    app_id = id_pengajuan(client, tiket)
    csrf = csrf_dari(client.get(f"/admin/pengajuan/{app_id}").text)
    r = client.post(
        f"/admin/pengajuan/{app_id}/status",
        data={"csrf": csrf, "ke": "DITOLAK", "catatan": "KTP buram, foto ulang."},
    )
    assert r.status_code == 303 and "err" not in r.headers["location"]

    with SessionLocal() as db:
        pengajuan = db.get(Application, app_id)
        assert pengajuan is not None and pengajuan.session_id
        sesi = db.get(ConversationSession, pengajuan.session_id)
        assert sesi is not None
        pesan = db.execute(
            select(ChatMessage)
            .where(ChatMessage.session_id == sesi.id, ChatMessage.arah == "out")
            .order_by(ChatMessage.id.desc())
        ).scalars().first()
        assert pesan is not None, "tidak ada pesan keluar ke warga setelah penolakan"
        assert "KTP buram" in pesan.isi, "alasan penolakan tidak ikut terkirim"


def test_status_diproses_masuk_ke_chat_warga(client):
    """Perubahan ke DIPROSES juga terlihat di percakapan."""
    from sqlalchemy import select

    from app.db import SessionLocal
    from app.models import Application, ChatMessage, ConversationSession

    tiket = buat_pengajuan_domisili(client, nik_unik())

    masuk(client, "operator")
    app_id = id_pengajuan(client, tiket)
    csrf = csrf_dari(client.get(f"/admin/pengajuan/{app_id}").text)
    r = client.post(
        f"/admin/pengajuan/{app_id}/status",
        data={"csrf": csrf, "ke": "DIPROSES", "catatan": "Berkas lengkap."},
    )
    assert r.status_code == 303 and "err" not in r.headers["location"]

    with SessionLocal() as db:
        pengajuan = db.get(Application, app_id)
        sesi = db.get(ConversationSession, pengajuan.session_id)
        pesan = db.execute(
            select(ChatMessage)
            .where(ChatMessage.session_id == sesi.id, ChatMessage.arah == "out")
            .order_by(ChatMessage.id.desc())
        ).scalars().first()
        assert pesan is not None, "tidak ada pesan keluar ke warga setelah diproses"
        assert "diproses" in pesan.isi.lower()
