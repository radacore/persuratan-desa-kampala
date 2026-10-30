"""FR-32: batas laju endpoint publik.

Seluruh suite berjalan dengan `RATE_LIMIT_ENABLED=false` (lihat conftest) agar
kuota tidak habis di tengah pengujian. Kasus di sini menyalakannya kembali
untuk memastikan batas benar-benar terpasang pada endpoint yang berisiko.
"""

from __future__ import annotations

import pytest
from fastapi import HTTPException

from app.services import ratelimit


@pytest.fixture
def aktifkan(monkeypatch):
    """Nyalakan batas laju hanya selama satu kasus uji."""
    monkeypatch.setattr(ratelimit.settings, "rate_limit_enabled", True)
    ratelimit.reset()
    yield
    ratelimit.reset()


def test_verifikasi_dibatasi_60_per_menit(client, aktifkan):
    for i in range(ratelimit.BATAS):
        r = client.get("/api/v1/verify/token-tidak-ada")
        assert r.status_code == 200, f"permintaan ke-{i + 1}: {r.status_code}"

    r = client.get("/api/v1/verify/token-tidak-ada")
    assert r.status_code == 429
    assert r.headers.get("retry-after")
    assert "terlalu banyak" in r.json()["detail"].lower()


def test_halaman_verifikasi_dibatasi_lebih_ketat(client, aktifkan):
    """`/v/{token}` menulis baris verification_scan, jadi kuotanya lebih kecil."""
    for i in range(ratelimit.BATAS_HALAMAN):
        assert client.get(f"/v/token-palsu-{i}").status_code == 200

    r = client.get("/v/token-palsu-terakhir")
    assert r.status_code == 429


def test_login_dibatasi(client, aktifkan):
    for _ in range(ratelimit.BATAS_LOGIN):
        client.post("/admin/login", data={"email": "salah@contoh.id", "password": "x", "csrf": ""})

    r = client.post(
        "/admin/login", data={"email": "salah@contoh.id", "password": "x", "csrf": ""}
    )
    assert r.status_code == 429


def test_kuota_dihitung_per_ip(aktifkan):
    for _ in range(ratelimit.BATAS):
        ratelimit.cek_batas("198.51.100.9")

    with pytest.raises(HTTPException) as galat:
        ratelimit.cek_batas("198.51.100.9")
    assert galat.value.status_code == 429

    # IP lain punya kuota sendiri.
    ratelimit.cek_batas("198.51.100.10")


def test_kuota_pulih_setelah_jendela(aktifkan):
    for _ in range(ratelimit.BATAS):
        ratelimit.cek_batas("203.0.113.5", jendela=1)
    with pytest.raises(HTTPException):
        ratelimit.cek_batas("203.0.113.5", jendela=1)

    import time

    time.sleep(1.05)
    ratelimit.cek_batas("203.0.113.5", jendela=1)


def test_kuota_terpisah_antar_jenis_endpoint(aktifkan):
    """Pemakaian chat tidak boleh menghabiskan jatah login."""
    for _ in range(ratelimit.BATAS_CHAT):
        ratelimit.cek_batas("192.0.2.7", ratelimit.BATAS_CHAT, kunci="chat")
    with pytest.raises(HTTPException):
        ratelimit.cek_batas("192.0.2.7", ratelimit.BATAS_CHAT, kunci="chat")

    ratelimit.cek_batas("192.0.2.7", ratelimit.BATAS_LOGIN, kunci="login")


def test_batas_dimatikan_saat_pengujian(monkeypatch):
    monkeypatch.setattr(ratelimit.settings, "rate_limit_enabled", False)
    for _ in range(ratelimit.BATAS + 5):
        ratelimit.cek_batas("192.0.2.99")
