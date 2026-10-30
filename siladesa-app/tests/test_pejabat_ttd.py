"""FR-30/FR-41: unggah scan tanda tangan dan masa berlaku pejabat."""

from __future__ import annotations

import io
from datetime import date, timedelta

from PIL import Image as PilImage
from sqlalchemy import select

from conftest import buat_pengajuan_domisili, csrf_dari, id_pengajuan, masuk, nik_unik


def _png(w: int = 200, h: int = 80) -> bytes:
    buf = io.BytesIO()
    PilImage.new("RGB", (w, h), "white").save(buf, format="PNG")
    return buf.getvalue()


def _pejabat(db, jabatan: str = "Kepala Desa"):
    from app.models import Official

    return db.execute(
        select(Official).where(Official.jabatan == jabatan, Official.aktif.is_(True))
    ).scalar_one_or_none()


def _diproses(client, tiket: str) -> int:
    """Bawa pengajuan ke status DIPROSES, kembalikan id-nya."""
    masuk(client, "operator")
    app_id = id_pengajuan(client, tiket)
    csrf = csrf_dari(client.get(f"/admin/pengajuan/{app_id}").text)
    r = client.post(
        f"/admin/pengajuan/{app_id}/status",
        data={"csrf": csrf, "ke": "DIPROSES", "catatan": "Berkas lengkap."},
    )
    assert r.status_code == 303 and "err" not in r.headers["location"]
    return app_id


def test_unggah_ttd_disimpan_dan_dipakai_pdf(client):
    from app.db import SessionLocal
    from app.models import Official
    from app.services import documents as docsvc

    masuk(client, "kepala_desa")
    csrf = csrf_dari(client.get("/admin/pejabat").text)
    with SessionLocal() as db:
        pejabat = _pejabat(db)
        oid = pejabat.id

    r = client.post(
        f"/admin/pejabat/{oid}/ttd",
        data={"csrf": csrf},
        files={"berkas": ("ttd.png", _png(), "image/png")},
    )
    assert r.status_code == 303, r.text[:300]
    assert "err" not in r.headers["location"], r.headers["location"]

    with SessionLocal() as db:
        pejabat = db.get(Official, oid)
        assert pejabat.ttd_path == f"officials/ttd-{oid}.png"
        berkas = docsvc.path_ttd(pejabat)
        assert berkas is not None and berkas.is_file()
        # Blok tanda tangan memakai gambar, bukan ruang kosong.
        jenis = [type(f).__name__ for f in docsvc._ruang_ttd(pejabat, 34)]
        assert "Image" in jenis


def test_unggah_ttd_menolak_berkas_besar_dan_format_lain(client):
    from app.db import SessionLocal

    masuk(client, "kepala_desa")
    csrf = csrf_dari(client.get("/admin/pejabat").text)
    with SessionLocal() as db:
        oid = _pejabat(db).id

    besar = _png(1500, 1500) + b"\x00" * (2 * 1024 * 1024)
    r = client.post(
        f"/admin/pejabat/{oid}/ttd",
        data={"csrf": csrf},
        files={"berkas": ("ttd.png", besar, "image/png")},
    )
    assert r.status_code == 303
    assert "err" in r.headers["location"]

    buf = io.BytesIO()
    PilImage.new("RGB", (20, 20), "white").save(buf, format="GIF")
    r = client.post(
        f"/admin/pejabat/{oid}/ttd",
        data={"csrf": csrf},
        files={"berkas": ("ttd.gif", buf.getvalue(), "image/gif")},
    )
    assert r.status_code == 303
    assert "err" in r.headers["location"]


def test_unggah_ttd_ditolak_untuk_admin_teknis(client):
    """Materi tanda tangan adalah kewenangan pejabat, bukan admin teknis."""
    from app.db import SessionLocal

    masuk(client, "admin")
    csrf = csrf_dari(client.get("/admin/pejabat").text)
    with SessionLocal() as db:
        oid = _pejabat(db).id

    r = client.post(
        f"/admin/pejabat/{oid}/ttd",
        data={"csrf": csrf},
        files={"berkas": ("ttd.png", _png(), "image/png")},
    )
    assert r.status_code == 403

def test_sekdes_boleh_unggah_ttd(client):
    from app.db import SessionLocal

    masuk(client, "sekdes")
    csrf = csrf_dari(client.get("/admin/pejabat").text)
    with SessionLocal() as db:
        oid = _pejabat(db).id

    r = client.post(
        f"/admin/pejabat/{oid}/ttd",
        data={"csrf": csrf},
        files={"berkas": ("ttd.png", _png(), "image/png")},
    )
    assert r.status_code == 303
    assert "err" not in r.headers["location"]

def test_data_pejabat_kepala_desa_hanya_boleh_diubah_kepala_desa(client):
    """Sekdes tidak boleh mengganti nama penanda tangan Kepala Desa."""
    from app.db import SessionLocal
    from app.models import Official

    with SessionLocal() as db:
        oid = _pejabat(db).id
        nama_asli = db.get(Official, oid).nama

    masuk(client, "sekdes")
    csrf = csrf_dari(client.get("/admin/pejabat").text)
    r = client.post(
        f"/admin/pejabat/{oid}",
        data={"csrf": csrf, "nama": "NAMA DIGANTI SEKDES"},
    )
    assert r.status_code == 403
    with SessionLocal() as db:
        assert db.get(Official, oid).nama == nama_asli

    masuk(client, "kepala_desa")
    csrf = csrf_dari(client.get("/admin/pejabat").text)
    r = client.post(
        f"/admin/pejabat/{oid}",
        data={"csrf": csrf, "nama": nama_asli},
    )
    assert r.status_code == 303
    assert "err" not in r.headers["location"]


def test_pejabat_kedaluwarsa_tidak_boleh_menerbitkan(client):
    from app.db import SessionLocal
    from app.models import Official
    from app.services import documents as docsvc

    tiket = buat_pengajuan_domisili(client, nik_unik())
    app_id = _diproses(client, tiket)

    with SessionLocal() as db:
        penanda, _saksi = docsvc.pejabat_untuk(db, "DOM")
        assert penanda is not None
        oid = penanda.id
        penanda.berlaku_sampai = date.today() - timedelta(days=1)
        db.commit()
        # Pejabat tidak lagi dianggap penanda tangan sah.
        assert docsvc.pejabat_untuk(db, "DOM")[0] is None

    try:
        masuk(client, "sekdes")
        csrf = csrf_dari(client.get(f"/admin/pengajuan/{app_id}").text)
        r = client.post(f"/admin/pengajuan/{app_id}/terbitkan", data={"csrf": csrf})
        assert r.status_code == 303
        assert "err" in r.headers["location"]
        assert "pejabat" in r.headers["location"].lower()
        from app import constants as C
        from app.models import Application

        with SessionLocal() as db:
            assert db.get(Application, app_id).status == C.Status.DIPROSES.value
    finally:
        with SessionLocal() as db:
            db.get(Official, oid).berlaku_sampai = None
            db.commit()
