"""Regresi untuk celah keamanan & integritas data yang ditemukan saat audit.

Setiap kasus di sini gagal pada kode sebelum perbaikan:

- K1  API publik menimpa data induk warga (nama/alamat orang lain).
- K2  Nomor tiket berurutan → surat orang lain bisa dibaca dan diunduh.
- K3  `app.seed` mengembalikan editan admin setiap kontainer restart.
- K4  Mengaktifkan kembali pejabat bentrok menghasilkan galat 500.
- K5  `/v/{token}` tanpa batas laju/panjang menulis baris scan tanpa batas.
- M1  `sha256` tidak pernah dicocokkan dengan berkas di disk.
- M2  Dua penerbitan untuk satu pengajuan menghasilkan dua surat.
- M7  Lampiran pengajuan bisa diunggah, diunduh, dan dihapus petugas.
"""

from __future__ import annotations

import io

from PIL import Image as PilImage
from sqlalchemy import select

from conftest import csrf_dari, id_pengajuan, masuk, nik_unik

NIK_UJI = "7304123456780001"


def _ajukan(client, nik: str, nama: str, **form):
    """Kirim pengajuan lewat API publik (jalur tanpa autentikasi)."""
    data = {
        "tempat_lahir": "Jeneponto",
        "tanggal_lahir": "1990-01-12",
        "jenis_kelamin": "Perempuan",
        "status_perkawinan": "Kawin",
        "agama": "Islam",
        "pekerjaan": "Petani",
        "alamat": "Jl. Poros",
        "dusun": "Buntulu",
        "rt": "001",
        "rw": "002",
        "no_hp": "081234567890",
        "keperluan": "Administrasi",
    }
    data.update(form)
    return client.post(
        "/api/v1/applications",
        json={
            "service_kode": "DOM",
            "citizen": {"nik": nik, "nama_lengkap": nama},
            "form_data": data,
        },
    )


# --------------------------------------------------------------------------- #
# K1 — data induk warga tidak boleh ditimpa lewat pengajuan
# --------------------------------------------------------------------------- #
def test_pengajuan_kedua_tidak_menimpa_data_warga(client):
    from app.db import SessionLocal
    from app.models import Citizen

    nik = nik_unik()
    assert _ajukan(client, nik, "SITI RAHMAWATI").status_code == 201
    assert _ajukan(client, nik, "NAMA PALSU PENYUSUP", alamat="Alamat dipalsukan").status_code == 201

    with SessionLocal() as db:
        warga = db.execute(select(Citizen).where(Citizen.nik == nik)).scalar_one()
        assert warga.nama_lengkap == "SITI RAHMAWATI"
        assert warga.alamat == "Jl. Poros"


def test_pengajuan_mengisi_kolom_kosong_yang_belum_ada(client):
    """Data induk yang kosong tetap boleh diisi dari pengajuan pertama."""
    from app.db import SessionLocal
    from app.models import Citizen

    nik = nik_unik()
    with SessionLocal() as db:
        db.add(Citizen(nik=nik, nama_lengkap="WARGA LAMA"))
        db.commit()

    assert _ajukan(client, nik, "WARGA LAMA").status_code == 201
    with SessionLocal() as db:
        warga = db.execute(select(Citizen).where(Citizen.nik == nik)).scalar_one()
        assert warga.nama_lengkap == "WARGA LAMA"
        assert warga.pekerjaan == "Petani"  # sebelumnya kosong, jadi terisi


# --------------------------------------------------------------------------- #
# K2 — nomor tiket saja tidak cukup untuk membuka surat orang lain
# --------------------------------------------------------------------------- #
def test_tiket_tanpa_nik_tidak_membocorkan_surat(client):
    from conftest import buat_pengajuan_domisili

    nik = nik_unik()
    tiket = buat_pengajuan_domisili(client, nik)

    assert client.get(f"/api/v1/track/{tiket}").status_code == 422
    assert client.get(f"/api/v1/track/{tiket}?nik={nik_unik()}").status_code == 404

    halaman = client.get(f"/lacak?tiket={tiket}")
    assert "Riwayat proses" not in halaman.text


def test_tautan_unduh_tidak_keluar_dari_chat_tanpa_nik(client):
    from conftest import buat_pengajuan_domisili

    nik = nik_unik()
    tiket = buat_pengajuan_domisili(client, nik)

    sid = client.post(
        "/api/v1/chat/sessions", json={"channel": "web", "kontak": "uji-tiket"}
    ).json()["session_id"]
    data = client.post(
        "/api/v1/chat/messages", json={"session_id": sid, "pesan": f"cek {tiket}"}
    ).json()
    assert "/d/" not in " ".join(data["balasan"])

    data = client.post(
        "/api/v1/chat/messages", json={"session_id": sid, "pesan": nik}
    ).json()
    assert tiket in " ".join(data["balasan"])


# --------------------------------------------------------------------------- #
# K3 — seed tidak mengembalikan editan admin
# --------------------------------------------------------------------------- #
def test_seed_tidak_menimpa_editan_admin(client):
    from app.db import SessionLocal
    from app.models import Faq, Service
    from app.seed import jalankan

    masuk(client, "sekdes")
    csrf = csrf_dari(client.get("/admin/layanan/DOM").text)
    r = client.post(
        "/admin/layanan/DOM",
        data={
            "csrf": csrf,
            "nama": "Surat Domisili (versi desa)",
            "estimasi_hari": "3",
            "urutan": "1",
            "aktif": "1",
            "syarat": "KTP\nKK",
        },
    )
    assert r.status_code == 303

    with SessionLocal() as db:
        faq = db.execute(select(Faq)).scalars().first()
        faq.jawaban = "JAWABAN HASIL EDIT PANEL"
        db.commit()

    # Simulasi restart kontainer: entrypoint menjalankan `python -m app.seed`.
    jalankan()

    with SessionLocal() as db:
        layanan = db.execute(select(Service).where(Service.kode == "DOM")).scalar_one()
        assert layanan.nama == "Surat Domisili (versi desa)"
        assert layanan.syarat == ["KTP", "KK"]
        faq = db.get(Faq, faq.id)
        assert faq.jawaban == "JAWABAN HASIL EDIT PANEL"


# --------------------------------------------------------------------------- #
# K4 — bentrok pejabat aktif ditolak dengan pesan, bukan galat 500
# --------------------------------------------------------------------------- #
def test_aktifkan_pejabat_bentrok_ditolak(client):
    from app.db import SessionLocal
    from app.models import Official

    masuk(client, "kepala_desa")
    csrf = csrf_dari(client.get("/admin/pejabat").text)

    with SessionLocal() as db:
        lama = db.execute(
            select(Official).where(Official.jabatan == "Sekretaris Desa", Official.aktif.is_(True))
        ).scalar_one()
        lama_id = lama.id

    assert client.post(
        f"/admin/pejabat/{lama_id}/nonaktif", data={"csrf": csrf}
    ).status_code == 303
    r = client.post(
        "/admin/pejabat",
        data={"csrf": csrf, "nama": "PENGGANTI SEKDES", "jabatan": "Sekretaris Desa"},
    )
    assert r.status_code == 303 and "err" not in r.headers["location"]

    csrf = csrf_dari(client.get("/admin/pejabat").text)
    r = client.post(f"/admin/pejabat/{lama_id}/nonaktif", data={"csrf": csrf})
    assert r.status_code == 303
    assert "err" in r.headers["location"]
    from urllib.parse import unquote

    assert "PENGGANTI SEKDES" in unquote(r.headers["location"])

    with SessionLocal() as db:
        assert db.get(Official, lama_id).aktif is False


# --------------------------------------------------------------------------- #
# K5 — token verifikasi dibatasi panjang dan laju
# --------------------------------------------------------------------------- #
def test_token_verifikasi_terlalu_panjang_ditolak(client):
    assert client.get("/v/" + "x" * 300).status_code == 404
    r = client.get("/api/v1/verify/" + "x" * 300)
    assert r.status_code == 200
    assert r.json()["hasil"] == "TIDAK_DITEMUKAN"


def test_token_terlalu_panjang_tidak_dicatat(client):
    from app.db import SessionLocal
    from app.models import VerificationScan

    with SessionLocal() as db:
        sebelum = len(db.execute(select(VerificationScan)).scalars().all())
    client.get("/v/" + "y" * 200)
    with SessionLocal() as db:
        sesudah = len(db.execute(select(VerificationScan)).scalars().all())
    assert sesudah == sebelum


# --------------------------------------------------------------------------- #
# M1 — keaslian dokumen ikut memeriksa berkas di disk
# --------------------------------------------------------------------------- #
def _terbitkan(client, tiket: str) -> int:
    app_id = id_pengajuan(client, tiket)
    masuk(client, "operator")
    csrf = csrf_dari(client.get(f"/admin/pengajuan/{app_id}").text)
    client.post(
        f"/admin/pengajuan/{app_id}/status",
        data={"csrf": csrf, "ke": "DIPROSES", "catatan": "Berkas lengkap."},
    )
    masuk(client, "sekdes")
    csrf = csrf_dari(client.get(f"/admin/pengajuan/{app_id}").text)
    r = client.post(f"/admin/pengajuan/{app_id}/terbitkan", data={"csrf": csrf})
    assert r.status_code == 303 and "err" not in r.headers["location"]
    return app_id


def test_verifikasi_menolak_berkas_yang_diubah(client):
    from conftest import buat_pengajuan_domisili

    from app.db import SessionLocal
    from app.models import Document
    from app.services.documents import path_dokumen

    tiket = buat_pengajuan_domisili(client, nik_unik())
    _terbitkan(client, tiket)

    with SessionLocal() as db:
        dokumen = db.execute(select(Document).order_by(Document.id.desc())).scalars().first()
        token = dokumen.qr_token
        path = path_dokumen(dokumen)

    sah = client.get(f"/api/v1/verify/{token}")
    assert sah.status_code == 200
    assert sah.json()["valid"] is True

    path.write_bytes(path.read_bytes() + b"% tambahan")

    palsu = client.get(f"/api/v1/verify/{token}")
    assert palsu.status_code == 200
    assert palsu.json()["valid"] is False
    assert palsu.json()["berkas_utuh"] is False


# --------------------------------------------------------------------------- #
# M2 — satu pengajuan hanya boleh punya satu surat
# --------------------------------------------------------------------------- #
def test_terbitkan_dua_kali_ditolak(client):
    from conftest import buat_pengajuan_domisili

    from app.db import SessionLocal
    from app.models import Document

    tiket = buat_pengajuan_domisili(client, nik_unik())
    app_id = _terbitkan(client, tiket)

    masuk(client, "sekdes")
    csrf = csrf_dari(client.get(f"/admin/pengajuan/{app_id}").text)
    r = client.post(f"/admin/pengajuan/{app_id}/terbitkan", data={"csrf": csrf})
    assert r.status_code == 303
    assert "err" in r.headers["location"]

    with SessionLocal() as db:
        dokumen = db.execute(
            select(Document).where(Document.application_id == app_id)
        ).scalars().all()
        assert len(dokumen) == 1


def test_indeks_unik_dokumen_menahan_duplikat(client):
    """Penjaga terakhir di tingkat basis data, bukan hanya di handler."""
    import pytest
    from sqlalchemy.exc import IntegrityError

    from app.db import SessionLocal
    from app.models import Document

    with SessionLocal() as db:
        asal = db.execute(select(Document)).scalars().first()
        salinan = Document(
            application_id=asal.application_id,
            template_id=asal.template_id,
            nomor_surat="999/DKP/X/2099",
            file_path=asal.file_path,
            sha256=asal.sha256,
            qr_token="token-duplikat-uji",
            status="TERBIT",
        )
        db.add(salinan)
        with pytest.raises(IntegrityError):
            db.commit()


# --------------------------------------------------------------------------- #
# M6 — surat yang dicabut tidak tampil sebagai terbit
# --------------------------------------------------------------------------- #
def test_surat_dicabut_tidak_menampilkan_tautan_unduh(client):
    from conftest import buat_pengajuan_domisili

    from app.db import SessionLocal
    from app.models import Application

    nik = nik_unik()
    tiket = buat_pengajuan_domisili(client, nik)
    app_id = _terbitkan(client, tiket)

    masuk(client, "kepala_desa")
    csrf = csrf_dari(client.get(f"/admin/pengajuan/{app_id}").text)
    r = client.post(
        f"/admin/pengajuan/{app_id}/cabut",
        data={"csrf": csrf, "alasan": "Data pemohon tidak sah."},
    )
    assert r.status_code == 303

    halaman = client.get(f"/lacak?tiket={tiket}&nik={nik}")
    assert "Unduh surat" not in halaman.text
    assert "dicabut" in halaman.text.lower()

    api = client.get(f"/api/v1/track/{tiket}?nik={nik}").json()
    assert api["nomor_surat"] is None
    assert api["nomor_surat_dicabut"] is not None
    assert api["dokumen_terbit"] is False

    with SessionLocal() as db:
        assert db.get(Application, app_id).status == "TERBIT"


# --------------------------------------------------------------------------- #
# M7 — lampiran pengajuan
# --------------------------------------------------------------------------- #
def _png(w: int = 60, h: int = 40) -> bytes:
    buf = io.BytesIO()
    PilImage.new("RGB", (w, h), "white").save(buf, format="PNG")
    return buf.getvalue()


def test_petugas_unggah_unduh_dan_hapus_lampiran(client):
    from conftest import buat_pengajuan_domisili

    from app.db import SessionLocal
    from app.models import Attachment
    from app.services import attachments

    tiket = buat_pengajuan_domisili(client, nik_unik())
    app_id = id_pengajuan(client, tiket)

    masuk(client, "operator")
    csrf = csrf_dari(client.get(f"/admin/pengajuan/{app_id}").text)
    r = client.post(
        f"/admin/pengajuan/{app_id}/lampiran",
        data={"csrf": csrf},
        files={"berkas": ("ktp.png", _png(), "image/png")},
    )
    assert r.status_code == 303 and "err" not in r.headers["location"]

    with SessionLocal() as db:
        lampiran = db.execute(
            select(Attachment).where(Attachment.application_id == app_id)
        ).scalar_one()
        aid = lampiran.id
        path = attachments.path_berkas(lampiran)
        assert path.is_file()
        assert path.parent.name == str(app_id)

    unduh = client.get(f"/admin/pengajuan/{app_id}/lampiran/{aid}")
    assert unduh.status_code == 200
    assert unduh.content == _png()

    csrf = csrf_dari(client.get(f"/admin/pengajuan/{app_id}").text)
    r = client.post(
        f"/admin/pengajuan/{app_id}/lampiran/{aid}/hapus", data={"csrf": csrf}
    )
    assert r.status_code == 303
    assert not path.exists()
    with SessionLocal() as db:
        assert db.get(Attachment, aid) is None


def test_lampiran_menolak_berkas_bukan_pdf_atau_gambar(client):
    from conftest import buat_pengajuan_domisili

    from app.db import SessionLocal
    from app.models import Attachment

    tiket = buat_pengajuan_domisili(client, nik_unik())
    app_id = id_pengajuan(client, tiket)

    masuk(client, "operator")
    csrf = csrf_dari(client.get(f"/admin/pengajuan/{app_id}").text)
    r = client.post(
        f"/admin/pengajuan/{app_id}/lampiran",
        data={"csrf": csrf},
        files={"berkas": ("skrip.png", b"<script>alert(1)</script>", "image/png")},
    )
    assert r.status_code == 303
    assert "err" in r.headers["location"]

    with SessionLocal() as db:
        assert db.execute(
            select(Attachment).where(Attachment.application_id == app_id)
        ).scalar_one_or_none() is None


def test_lampiran_tidak_bisa_diakses_dari_pengajuan_lain(client):
    from conftest import buat_pengajuan_domisili

    tiket = buat_pengajuan_domisili(client, nik_unik())
    app_id = id_pengajuan(client, tiket)

    masuk(client, "operator")
    csrf = csrf_dari(client.get(f"/admin/pengajuan/{app_id}").text)
    client.post(
        f"/admin/pengajuan/{app_id}/lampiran",
        data={"csrf": csrf},
        files={"berkas": ("ktp.png", _png(), "image/png")},
    )

    from app.db import SessionLocal
    from app.models import Attachment

    with SessionLocal() as db:
        aid = db.execute(select(Attachment)).scalars().first().id

    r = client.get(f"/admin/pengajuan/{app_id + 9999}/lampiran/{aid}")
    assert r.status_code == 404
