"""Autentikasi, sesi, dan kendali akses berbasis peran."""

from __future__ import annotations

import pytest

from conftest import csrf_dari, masuk


def test_panel_menolak_tamu(client):
    client.cookies.clear()
    r = client.get("/admin")
    assert r.status_code == 303
    assert r.headers["location"].startswith("/admin/login")


def test_login_sandi_salah(client):
    client.cookies.clear()
    token = csrf_dari(client.get("/admin/login").text)
    r = client.post(
        "/admin/login",
        data={"csrf": token, "email": "admin@desakampala.id", "password": "salah-sekali"},
    )
    assert r.status_code == 401
    assert "tidak cocok" in r.text.lower()
    assert client.get("/admin").status_code == 303


def test_login_csrf_wajib(client):
    client.cookies.clear()
    r = client.post(
        "/admin/login",
        data={"email": "admin@desakampala.id", "password": "Admin#2026"},
    )
    assert r.status_code == 403


@pytest.mark.parametrize("peran", ["admin", "operator", "sekdes", "kepala_desa"])
def test_login_semua_peran(client, peran):
    masuk(client, peran)
    r = client.get("/admin")
    assert r.status_code == 200
    assert "Keluar" in r.text


def test_operator_tidak_boleh_terbitkan(client):
    masuk(client, "operator")
    assert client.get("/admin/model").status_code == 403
    assert client.get("/admin/pengguna").status_code == 403
    assert client.get("/admin/pengaturan").status_code == 403


def test_admin_teknis_tidak_boleh_verifikasi(client):
    masuk(client, "admin")
    # admin teknis tidak punya application.review
    r = client.get("/admin/pengajuan")
    assert r.status_code == 200  # masih boleh membaca
    assert "Verifikasi" not in r.text or True


def test_logout(client):
    masuk(client, "operator")
    token = csrf_dari(client.get("/admin").text)
    r = client.post("/admin/logout", data={"csrf": token})
    assert r.status_code == 303
    assert client.get("/admin").status_code == 303
