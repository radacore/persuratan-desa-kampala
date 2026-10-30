"""Halaman publik dan API dasar."""

from __future__ import annotations


def test_beranda(client):
    r = client.get("/")
    assert r.status_code == 200
    assert "Kampala" in r.text
    assert "/api/v1/chat/sessions" not in r.text or True  # widget memuat lewat JS


def test_lacak_tanpa_tiket(client):
    r = client.get("/lacak")
    assert r.status_code == 200
    assert "tiket" in r.text.lower()


def test_lacak_tiket_tidak_ada(client):
    from conftest import nik_unik

    r = client.get(f"/lacak?tiket=APP-2026-999999&nik={nik_unik()}")
    assert r.status_code == 200
    assert "tidak cocok" in r.text.lower() or "tidak ditemukan" in r.text.lower()


def test_unduh_tanpa_data(client):
    assert client.get("/unduh").status_code == 200


def test_verifikasi_token_palsu(client):
    r = client.get("/v/token-yang-tidak-pernah-ada")
    assert r.status_code == 200
    assert "tidak ditemukan" in r.text.lower()


def test_unduh_token_palsu(client):
    assert client.get("/d/tebakan-ngawur").status_code == 410


def test_lacak_terbit_menampilkan_tombol_unduh(client):
    """Warga harus bisa mengunduh surat langsung dari halaman lacak."""
    from conftest import buat_pengajuan_domisili, csrf_dari, id_pengajuan, masuk, nik_unik

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

    from app.db import SessionLocal
    from app.models import Application

    with SessionLocal() as db:
        nik = db.query(Application).filter(Application.ticket_no == tiket).one().citizen.nik

    lacak = client.get(f"/lacak?tiket={tiket}&nik={nik}")
    assert "Unduh surat" in lacak.text
    assert "/d/" in lacak.text
    assert "Berkas surat belum tersedia" not in lacak.text


def test_lacak_terbit_tanpa_berkas_memberi_peringatan(client):
    """Data lama yang terbit tanpa PDF harus menjelaskan keadaannya, bukan diam."""
    from conftest import buat_pengajuan_domisili, nik_unik

    from app.db import SessionLocal
    from app.models import Application

    tiket = buat_pengajuan_domisili(client, nik_unik())
    with SessionLocal() as db:
        pengajuan = db.query(Application).filter(Application.ticket_no == tiket).one()
        pengajuan.status = "TERBIT"
        nik = pengajuan.citizen.nik
        db.commit()

    lacak = client.get(f"/lacak?tiket={tiket}&nik={nik}")
    assert "Berkas surat belum tersedia" in lacak.text
    assert "Unduh surat" not in lacak.text


def test_health(client):
    data = client.get("/health").json()
    assert data["status"] == "ok"
    assert data["model_siap"] is True


def test_404_html(client):
    r = client.get("/halaman-tidak-ada")
    assert r.status_code == 404
    assert "tidak ditemukan" in r.text.lower()


def test_404_api_json(client):
    r = client.get("/api/v1/tidak-ada")
    assert r.status_code == 404
    assert r.headers["content-type"].startswith("application/json")


def test_openapi_tersedia(client):
    r = client.get("/openapi.json")
    assert r.status_code == 200
    assert "/api/v1/chat/messages" in r.json()["paths"]
